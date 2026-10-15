#!/usr/bin/env python3
# Copyright 2022-2026 Huntington Applied
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Container Status Collector
==========================
Live status of every reachable aspect of every FLEET project — landing app,
product app, backend/API, and infrastructure containers (db / redis / workers).

Two signals are merged per service:

1. HTTP reachability  — does the public endpoint answer 200? (via httpx)
2. Container state     — is the Docker container actually running/healthy?
                          (via `docker ps` over SSH to the owning EC2 host,
                          creds from config/domain_registry.yaml)

Both signals degrade gracefully: if SSH keys or hosts are unreachable the
container state becomes ``unknown`` but the HTTP result is still reported, and
vice-versa. Nothing here raises on a dead host — that is the whole point.

Port / domain / URL conventions follow PORT_ALLOCATION_STANDARDS.md and
config/domain_registry.yaml. Do NOT hardcode ports here — derive them from the
registries so this stays correct as allocations change.

AUTHORITATIVE REFERENCES:
- Port Allocation: /docs/standards/infrastructure/PORT_ALLOCATION_STANDARDS.md
- Domain Registry: config/domain_registry.yaml
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


# ---------------------------------------------------------------------------
# Status vocabulary
# ---------------------------------------------------------------------------
# Per-service status:
#   healthy  — container running (+ healthy if it has a healthcheck) AND, for
#              web services, HTTP 200.
#   running  — infra container (db/redis/worker) up; no HTTP endpoint to check.
#   degraded — container up but not serving correctly (non-200 / unhealthy).
#   down     — container exited/missing, or web endpoint unreachable.
#   unknown  — could not determine (host unreachable, no creds, not deployed).
S_HEALTHY = "healthy"
S_RUNNING = "running"
S_DEGRADED = "degraded"
S_DOWN = "down"
S_UNKNOWN = "unknown"
#   unreachable — the CONTAINER is running and its Docker healthcheck passes, but the
#                 public HTTP endpoint doesn't answer. The service itself is fine; the
#                 gap is routing/tunnel/DNS, not the container. Kept distinct from
#                 "degraded" (which means the container itself is impaired) so a healthy
#                 app behind an unrouted domain isn't a false red alarm.
S_UNREACHABLE = "unreachable"


@dataclass
class ServiceLive:
    """Live status of a single service (one container / one endpoint)."""

    name: str  # landing | product_app | api | database | redis | worker-N | ...
    kind: str  # "web" (has HTTP endpoint) | "infra" (container only)
    status: str = S_UNKNOWN
    detail: str = ""
    # HTTP signal
    url: Optional[str] = None
    http_status: Optional[int] = None
    http_ok: bool = False
    response_ms: Optional[float] = None
    # Container signal
    container: Optional[str] = None
    container_state: Optional[str] = None  # running | exited | restarting | ...
    container_health: Optional[str] = None  # healthy | unhealthy | starting | none
    # How many like-named containers this row represents (>1 when per-session
    # containers such as atlas-ide-<user_id> are collapsed into one row).
    count: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ProjectLive:
    """Live status of one project across all its services."""

    slug: str
    name: str
    phase: str  # demo | alpha | production
    instance: str = ""
    mode: str = ""  # deployment.mode (docker_isolated | shared_landing_docker | native_dev | ...)
    services: List[ServiceLive] = field(default_factory=list)
    overall: str = S_UNKNOWN
    declared_vs_actual: Optional[str] = None  # warning when phase != reality

    def compute_overall(self) -> None:
        # Consider ALL services (web + infra): a down database or exited worker is a
        # real outage and must not hide behind a healthy web endpoint.
        sts = [s.status for s in self.services]
        oks = [s for s in sts if s in (S_HEALTHY, S_RUNNING)]
        downs = [s for s in sts if s == S_DOWN]
        degs = [s for s in sts if s == S_DEGRADED]
        # "unreachable" is neutral for rollup: a healthy container behind an unrouted
        # public endpoint must not drag the project to degraded/down.
        unreach = [s for s in sts if s == S_UNREACHABLE]
        if not sts:
            self.overall = S_UNKNOWN
        elif oks and (downs or degs):
            # Some services serving, some genuinely impaired → partial outage.
            self.overall = S_DEGRADED
        elif oks:
            self.overall = S_HEALTHY if any(s == S_HEALTHY for s in oks) else S_RUNNING
        elif degs:
            self.overall = S_DEGRADED
        elif downs:
            self.overall = S_DOWN
        elif unreach:
            self.overall = S_UNREACHABLE
        else:
            self.overall = S_UNKNOWN
        # A "production" project with anything down/degraded is a real problem.
        if self.phase == "production" and self.overall in (S_DOWN, S_DEGRADED):
            self.declared_vs_actual = (
                f"Declared production but a service is {self.overall}."
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "slug": self.slug,
            "name": self.name,
            "phase": self.phase,
            "instance": self.instance,
            "mode": self.mode,
            "overall": self.overall,
            "declared_vs_actual": self.declared_vs_actual,
            "services": [s.to_dict() for s in self.services],
        }


def _norm(s: str) -> str:
    return (s or "").lower().replace("_", "-")


def _container_slug_suffix(name: str, slug: str) -> Optional[str]:
    """If ``name`` belongs to ``slug`` (by prefix), return the role suffix; else None.

    Handles slug/name separator differences (scanner_app ↔ scanner-app).
    e.g. ("hermes-backend", "hermes") -> "backend"; ("atlas-worker-1", ...) -> "worker-1".
    """
    n, s = _norm(name), _norm(slug)
    if n == s:
        return ""
    if n.startswith(s + "-"):
        return n[len(s) + 1 :]
    return None


def _classify_suffix(suffix: str) -> tuple[str, str]:
    """Map a container's role suffix to (service_name, kind)."""
    s = suffix.lower()
    if s.startswith("landing"):
        return "landing", "web"
    if s.startswith("product") or s == "app":
        return "product_app", "web"
    if s.startswith("frontend") or s == "web" or s.startswith("ui"):
        return "landing", "web"
    if s.startswith("backend") or s.startswith("api"):
        return "api", "web"
    if s.startswith("ide"):
        return "ide", "web"
    # Everything else is infra. Keep the real container suffix as the service name
    # (postgres / db / redis / worker-1 / celery-worker) so distinct containers
    # never collapse onto one label.
    return suffix or "container", "infra"


# Severity: higher = worse. Used to roll multiple like-named containers up to a
# single worst-case row, and to order the per-status breakdown text.
_STATUS_SEVERITY = {
    S_HEALTHY: 0,
    S_RUNNING: 1,
    S_UNKNOWN: 2,
    S_UNREACHABLE: 3,
    S_DEGRADED: 4,
    S_DOWN: 5,
}


def _collapse_duplicate_services(services: List[ServiceLive]) -> List[ServiceLive]:
    """Roll multiple containers that share a service name into one row.

    Atlas's IDE is one container per active user session
    (``atlas-ide-<user_id>``), so N live sessions would otherwise render as
    N identical ``ide`` rows. Collapse each such group into a single row whose
    ``count`` is the number of containers and whose ``status`` is the **worst**
    among them (so one crashed session still surfaces, and the project rollup is
    unchanged from the pre-collapse behaviour). ``detail`` becomes a per-status
    breakdown like ``"2× running, 1× down"``. Order is preserved by first
    appearance; singletons pass through untouched.
    """
    groups: Dict[str, List[ServiceLive]] = {}
    order: List[str] = []
    for s in services:
        if s.name not in groups:
            groups[s.name] = []
            order.append(s.name)
        groups[s.name].append(s)

    out: List[ServiceLive] = []
    for name in order:
        grp = groups[name]
        if len(grp) == 1:
            out.append(grp[0])
            continue
        worst = max(grp, key=lambda s: _STATUS_SEVERITY.get(s.status, 2))
        counts: Dict[str, int] = {}
        for s in grp:
            counts[s.status] = counts.get(s.status, 0) + 1
        breakdown = ", ".join(
            f"{n}× {st}"
            for st, n in sorted(
                counts.items(), key=lambda kv: -_STATUS_SEVERITY.get(kv[0], 2)
            )
        )
        out.append(
            ServiceLive(
                name=name,
                kind=worst.kind,
                status=worst.status,
                detail=breakdown,
                url=grp[0].url,
                container=worst.container,
                container_state=worst.container_state,
                container_health=worst.container_health,
                count=len(grp),
            )
        )
    return out


class ContainerStatusCollector:
    """
    Collect live status for all FLEET projects.

    Data sources:
      - ProjectConfigManager  -> project list, phase, deployment.services
      - domain_registry.yaml  -> EC2 instance SSH creds + public endpoint URLs

    Results are cached for ``cache_ttl`` seconds; call ``collect_all(force=True)``
    to bypass. Thread-safe enough for a Flask worker (single-process refresh).
    """

    WEB_ENDPOINTS = ("landing", "product_app", "api")

    def __init__(
        self,
        config_manager,
        domain_registry_path: Optional[Path] = None,
        http_timeout: float = 8.0,
        docker_timeout: int = 8,
        cache_ttl: float = 30.0,
        enable_local_docker: bool = True,
        enable_ssh: bool = False,
    ):
        self.config_manager = config_manager
        self.http_timeout = http_timeout
        self.docker_timeout = docker_timeout
        self.cache_ttl = cache_ttl
        # Current topology: containers run on local Mac Mini hosts, so the local
        # Docker daemon is the source of truth. SSH-to-remote is the FUTURE path
        # for when each project moves to its own EC2 (with new keys) — off by
        # default until those instances/keys exist.
        self.enable_local_docker = enable_local_docker
        self.enable_ssh = enable_ssh

        self._registry = self._load_registry(domain_registry_path)
        self._instances = (self._registry or {}).get("instances", {})
        self._reg_projects = (self._registry or {}).get("projects", {})

        self._cache: Dict[str, ProjectLive] = {}
        self._cache_ts: float = 0.0
        self._lock = threading.Lock()  # serialize full collections
        # Caches valid within a single collection pass.
        self._docker_ps_cache: Dict[str, Dict[str, Dict[str, str]]] = {}
        self._local_ps: Optional[Dict[str, Dict[str, str]]] = None
        self._docker_endpoint: Optional[str] = None
        self._all_slugs: List[str] = []  # longest-first, for prefix ownership

    # -- registry -----------------------------------------------------------
    @staticmethod
    def _load_registry(path: Optional[Path]) -> Optional[Dict[str, Any]]:
        if yaml is None:
            return None
        if path is None:
            here = Path(__file__).resolve()
            # engine/sega/probe/container_status.py -> repo root is 3 up from engine
            for parent in here.parents:
                cand = parent / "config" / "domain_registry.yaml"
                if cand.exists():
                    path = cand
                    break
        if not path or not Path(path).exists():
            return None
        try:
            with open(path) as f:
                return yaml.safe_load(f)
        except Exception:
            return None

    # -- HTTP signal --------------------------------------------------------
    def _check_http(self, url: str) -> tuple[Optional[int], bool, Optional[float], str]:
        start = time.perf_counter()
        try:
            with httpx.Client(timeout=self.http_timeout, follow_redirects=True, verify=False) as c:
                r = c.get(url)
            ms = (time.perf_counter() - start) * 1000
            ok = r.status_code == 200
            return r.status_code, ok, ms, ("" if ok else f"HTTP {r.status_code}")
        except httpx.TimeoutException:
            return None, False, (time.perf_counter() - start) * 1000, "timeout"
        except Exception as e:  # ConnectError, etc.
            return None, False, (time.perf_counter() - start) * 1000, str(e)[:60]

    # -- container signal (docker ps) ---------------------------------------
    _PS_FORMAT = "{{.Names}}\t{{.State}}\t{{.Status}}"

    @staticmethod
    def _parse_ps(text: str) -> Dict[str, Dict[str, str]]:
        out: Dict[str, Dict[str, str]] = {}
        for line in (text or "").splitlines():
            parts = line.split("\t")
            if len(parts) >= 3:
                out[parts[0].strip()] = {"state": parts[1].strip(), "status": parts[2].strip()}
        return out

    # Candidate Docker endpoints, tried in order when the default context fails.
    # macOS dev hosts often have both Colima and Docker Desktop installed with an
    # inactive context selected, so we probe known sockets rather than trusting
    # the ambient DOCKER_HOST / active context.
    _DOCKER_SOCKETS = (
        None,  # default (respect env / active context) first
        "unix://" + str(Path("~/.docker/run/docker.sock").expanduser()),  # Docker Desktop
        "unix:///var/run/docker.sock",  # standard / mounted socket
        "unix://" + str(Path("~/.colima/default/docker.sock").expanduser()),  # Colima
    )

    def _local_docker_ps(self) -> Dict[str, Dict[str, str]]:
        """`docker ps -a` on the host running the dashboard (Mac Mini / mounted
        docker.sock). Auto-detects a reachable Docker endpoint. Cached per pass."""
        if self._local_ps is not None:
            return self._local_ps
        result: Dict[str, Dict[str, str]] = {}
        if self.enable_local_docker:
            import os
            import subprocess

            for sock in self._DOCKER_SOCKETS:
                cmd = ["docker"]
                if sock:
                    cmd += ["-H", sock]
                cmd += ["ps", "-a", "--format", self._PS_FORMAT]
                try:
                    env = dict(os.environ)
                    if sock:
                        env.pop("DOCKER_HOST", None)  # -H must win
                    r = subprocess.run(cmd, capture_output=True, text=True,
                                       timeout=self.docker_timeout, env=env)
                except FileNotFoundError:
                    break  # no docker CLI (e.g. inside container) → try SDK below
                except Exception:
                    continue
                if r.returncode == 0:
                    result = self._parse_ps(r.stdout)
                    self._docker_endpoint = sock or "default"
                    break
            # Fallback: the Docker SDK talks to the socket directly — needed inside
            # the sega-dashboard container, which has the docker.sock mounted but no
            # docker CLI installed.
            if not result:
                result = self._sdk_docker_ps()
        self._local_ps = result
        return result

    def _sdk_docker_ps(self) -> Dict[str, Dict[str, str]]:
        """`docker ps` via the Python Docker SDK (no CLI needed). Probes the same
        candidate sockets; first that responds wins."""
        try:
            import docker
        except ImportError:
            return {}
        result: Dict[str, Dict[str, str]] = {}
        for sock in self._DOCKER_SOCKETS:
            try:
                # timeout= is essential: a wedged daemon accepts the socket
                # connection but never answers, and docker-py's default would
                # block ~60s per API call — hanging /v1/status indefinitely.
                client = (
                    docker.from_env(timeout=self.docker_timeout)
                    if sock is None
                    else docker.DockerClient(base_url=sock, timeout=self.docker_timeout)
                )
                client.ping()  # fail fast before the per-container list/inspect calls
                for c in client.containers.list(all=True):
                    state_obj = c.attrs.get("State", {}) or {}
                    state = state_obj.get("Status", c.status)
                    health = (state_obj.get("Health") or {}).get("Status")
                    # Mirror the Docker CLI's status text so _health_from_status matches.
                    if health == "starting":
                        status = "Up (health: starting)"
                    elif health:
                        status = f"Up ({health})"
                    else:
                        status = state
                    result[c.name] = {"state": state, "status": status}
                if result:
                    self._docker_endpoint = f"sdk:{sock or 'from_env'}"
                    break
            except Exception:
                continue
        return result

    def _remote_docker_ps(self, inst: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
        """FUTURE: `docker ps` on a remote per-project EC2 via SSH. Off unless
        enable_ssh and the instance has an ip + reachable key."""
        try:
            from sega.utils.ssh import SSHExecutor

            ssh = SSHExecutor(
                host=inst["ip"],
                user=inst.get("ssh_user", "ubuntu"),
                key_path=inst.get("ssh_key"),
                timeout=self.docker_timeout,
            )
            res = ssh.execute(f"docker ps -a --format '{self._PS_FORMAT}'")
            return self._parse_ps(res.stdout) if res.success else {}
        except FileNotFoundError:
            return {}  # key not present yet (instances not provisioned)
        except Exception:
            return {}

    def _docker_ps(self, instance_name: str) -> Dict[str, Dict[str, str]]:
        """Container states for an instance: local Docker now, remote SSH later."""
        if instance_name in self._docker_ps_cache:
            return self._docker_ps_cache[instance_name]

        result: Dict[str, Dict[str, str]] = dict(self._local_docker_ps())
        inst = self._instances.get(instance_name)
        if self.enable_ssh and inst and inst.get("ip"):
            result.update(self._remote_docker_ps(inst))  # remote overrides local

        self._docker_ps_cache[instance_name] = result
        return result

    @staticmethod
    def _health_from_status(status_str: str) -> Optional[str]:
        s = (status_str or "").lower()
        if "(healthy)" in s:
            return "healthy"
        if "(unhealthy)" in s:
            return "unhealthy"
        if "health: starting" in s or "(health: starting)" in s:
            return "starting"
        return None

    def _merge(self, svc: ServiceLive, ps: Dict[str, Dict[str, str]]) -> None:
        """Merge container state into a service and finalize its status."""
        info = ps.get(svc.container or "")
        if info is not None:
            svc.container_state = info.get("state")
            svc.container_health = self._health_from_status(info.get("status", ""))

        state = svc.container_state
        health = svc.container_health

        if svc.kind == "web" and svc.url:
            # Web service with a checkable URL: HTTP is primary, container refines.
            if svc.http_ok:
                if health == "unhealthy":
                    svc.status, svc.detail = S_DEGRADED, "serving but container unhealthy"
                else:
                    svc.status = S_HEALTHY
                    svc.detail = f"{svc.http_status} · {svc.response_ms:.0f}ms" if svc.response_ms is not None else "200"
            elif state in (None, ""):
                svc.status, svc.detail = S_DOWN, svc.detail or "unreachable"
            elif state == "running":
                if health == "healthy":
                    # Container's own healthcheck passes but the public URL fails →
                    # routing/tunnel gap, not a container fault.
                    svc.status, svc.detail = S_UNREACHABLE, f"container healthy · public endpoint unreachable ({svc.detail or 'no 200'})"
                else:
                    svc.status, svc.detail = S_DEGRADED, f"up, not serving ({svc.detail or 'no 200'})"
            elif state in ("restarting", "created"):
                svc.status, svc.detail = S_DEGRADED, f"container {state}"
            else:  # exited / dead / paused
                svc.status, svc.detail = S_DOWN, f"container {state}"
        else:
            # Infra service, OR a web container with no configured URL: judge purely
            # by container state (we can't confirm HTTP serving, so don't penalize).
            if state == "running":
                if health == "unhealthy":
                    svc.status, svc.detail = S_DEGRADED, "unhealthy"
                elif health == "starting":
                    svc.status, svc.detail = S_RUNNING, "starting"
                else:
                    svc.status, svc.detail = S_RUNNING, "running"
            elif state in (None, ""):
                svc.status, svc.detail = S_UNKNOWN, "state unknown"
            elif state in ("restarting", "created"):
                svc.status, svc.detail = S_DEGRADED, state
            else:
                svc.status, svc.detail = S_DOWN, state

    # -- per project --------------------------------------------------------
    def _build_services(self, project: Dict[str, Any], ps: Dict[str, Dict[str, str]]) -> List[ServiceLive]:
        """Build the service list from (a) domain-registry web endpoints for HTTP
        URLs and (b) the ACTUAL running containers matched to this project by name
        prefix from ``docker ps`` (the registry container lists are unreliable)."""
        slug = project.get("slug", "")
        services: List[ServiceLive] = []

        # 1) Web endpoints from the domain registry (for public HTTP URLs).
        reg = self._reg_projects.get(slug, {})
        endpoints = reg.get("endpoints", {})
        domain = (reg.get("domains", {}) or {}).get("production")
        for ep in self.WEB_ENDPOINTS:
            if ep not in endpoints:
                continue
            url = self._build_url(slug, ep, domain, endpoints[ep])
            services.append(ServiceLive(name=ep, kind="web", url=url))

        # 2) Real containers for this project, discovered by name prefix.
        for cname in sorted(ps.keys()):
            suffix = _container_slug_suffix(cname, slug)
            if suffix is None:
                continue
            # Most-specific slug wins: if a longer slug also prefixes this container
            # (e.g. "doc" vs "doc-scanner"), let that project claim it, not this one.
            if self._owner_slug(cname, slug) != slug:
                continue
            svc_name, kind = _classify_suffix(suffix)
            existing = next(
                (s for s in services if s.name == svc_name and s.container is None),
                None,
            )
            if existing is not None:
                existing.container = cname
                if kind == "web":
                    existing.kind = "web"
            elif not any(s.container == cname for s in services):
                services.append(ServiceLive(name=svc_name, kind=kind, container=cname))

        return services

    def _owner_slug(self, cname: str, fallback: str) -> str:
        """Return the longest known slug that prefixes ``cname`` (most specific
        project owns the container). Falls back when the slug set isn't populated."""
        for s in self._all_slugs:  # sorted longest-first
            if _container_slug_suffix(cname, s) is not None:
                return s
        return fallback

    def _build_url(self, slug: str, ep: str, domain: Optional[str], ep_cfg: Dict[str, Any]) -> Optional[str]:
        if not domain:
            return None
        path = ep_cfg.get("path", "/")
        host = domain
        if ep == "product_app":
            host = f"app.{domain}"
        elif ep == "api":
            host = f"api.{domain}"
        return f"https://{host}{path}"

    def _collect_project(self, project: Dict[str, Any]) -> ProjectLive:
        slug = project.get("slug", "")
        instance = (project.get("deployment", {}) or {}).get("instance", "")
        pl = ProjectLive(
            slug=slug,
            name=project.get("name", slug),
            phase=project.get("status", "demo"),
            instance=instance,
            mode=(project.get("deployment", {}) or {}).get("mode", ""),
        )
        # Container states first (drives which services actually exist).
        ps = self._docker_ps(instance)
        pl.services = self._build_services(project, ps)

        # HTTP checks (concurrent) for web services with a URL.
        web = [s for s in pl.services if s.kind == "web" and s.url]
        if web:
            with ThreadPoolExecutor(max_workers=min(8, len(web))) as ex:
                for svc, res in zip(web, ex.map(lambda s: self._check_http(s.url), web)):
                    svc.http_status, svc.http_ok, svc.response_ms, svc.detail = res

        for svc in pl.services:
            self._merge(svc, ps)

        # Collapse per-session duplicates (e.g. atlas-ide-<user_id>) into a
        # single counted row. Done after merge so each container's health is
        # evaluated before it's rolled up to the group's worst status.
        pl.services = _collapse_duplicate_services(pl.services)

        pl.compute_overall()
        return pl

    # -- public API ---------------------------------------------------------
    def collect_all(self, force: bool = False) -> Dict[str, ProjectLive]:
        now = time.time()
        if not force and self._cache and (now - self._cache_ts) < self.cache_ttl:
            return self._cache

        # Serialize collections: overlapping Flask requests share one refresh
        # instead of each spawning its own pool + docker calls.
        with self._lock:
            now = time.time()
            if not force and self._cache and (now - self._cache_ts) < self.cache_ttl:
                return self._cache

            self._docker_ps_cache = {}  # fresh docker snapshot per pass
            self._local_ps = None
            # Re-read the registry each pass so live phase edits in fleet-projects.json
            # appear without restarting the dashboard (ProjectConfigManager caches).
            try:
                self.config_manager.load_config(force_reload=True)
            except Exception:
                pass
            projects = self.config_manager.get_all_projects()
            self._all_slugs = sorted(
                (p.get("slug", "") for p in projects if p.get("slug")), key=len, reverse=True
            )
            self._local_docker_ps()  # pre-warm once so worker threads don't each shell out

            result: Dict[str, ProjectLive] = {}
            with ThreadPoolExecutor(max_workers=min(12, max(1, len(projects)))) as ex:
                for pl in ex.map(self._collect_project, projects):
                    result[pl.slug] = pl

            self._cache = result
            self._cache_ts = now
            return result

    def summary(self, statuses: Optional[Dict[str, ProjectLive]] = None) -> Dict[str, Any]:
        statuses = statuses if statuses is not None else self.collect_all()
        counts = {S_HEALTHY: 0, S_RUNNING: 0, S_UNREACHABLE: 0, S_DEGRADED: 0, S_DOWN: 0, S_UNKNOWN: 0}
        for pl in statuses.values():
            counts[pl.overall] = counts.get(pl.overall, 0) + 1
        return {
            "total": len(statuses),
            "counts": counts,
            "checked_at": self._cache_ts,
            "docker_endpoint": self._docker_endpoint,  # which docker source answered
        }

    def to_json(self, force: bool = False) -> Dict[str, Any]:
        statuses = self.collect_all(force=force)
        return {
            "summary": self.summary(statuses),
            "projects": [statuses[k].to_dict() for k in sorted(statuses)],
        }
