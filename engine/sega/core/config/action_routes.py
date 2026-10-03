#!/usr/bin/env python3
# Copyright 2022-2026 Huntington Applied
# License: Apache-2.0
#
# SEGA Dashboard action routes
# Local/internal-only controls to launch/stop/restart/rebuild projects and view
# logs, by shelling out to the same `sega local ...` CLI the operator uses.

"""
SEGA dashboard action routes (local/internal only).

Adds state-changing controls to the dashboard, wired to the existing SEGA CLI:

- ``POST /v1/actions/<slug>/<start|stop|restart|rebuild>`` → runs the action in a
  background job; returns ``{job_id}``.
- ``GET  /v1/jobs/<job_id>``    → job status + captured output.
- ``GET  /v1/logs/<slug>``      → recent logs (``sega local logs``).
- ``GET  /v1/capabilities``     → whether THIS request may take actions.

SAFETY — actions are refused unless ALL hold:
  1. env ``SEGA_DASHBOARD_ACTIONS`` is truthy (opt-in per deployment), AND
  2. the request carries no tunnel/proxy headers (CF-Connecting-IP /
     X-Forwarded-For) — Cloudflare-tunnelled public traffic arrives as 127.0.0.1,
     so loopback alone is NOT sufficient, AND
  3. the peer address is loopback/private.

So the PUBLIC segaapp.com container (tunnelled, flag unset) stays read-only, while
a locally-run dashboard (`SEGA_DASHBOARD_ACTIONS=1`, bound to 127.0.0.1) can act.
"""

from __future__ import annotations

import ipaddress
import os
import shutil
import subprocess
import sys
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

from flask import jsonify, request

# action -> argv builder (project slug substituted). Kept as lists (never shell
# strings) and the slug is validated against the registry, so no injection.
_TIMEOUTS = {"start": 600, "stop": 180, "restart": 300, "rebuild": 900, "launch": 60, "logs": 30}
_VALID_ACTIONS = ("start", "stop", "restart", "rebuild", "launch")

_AUTH_COOKIE = "sega_auth"
_SESSION_MAX_AGE = 8 * 3600  # unlocked session lifetime (seconds)


def _env_actions_enabled() -> bool:
    return str(os.environ.get("SEGA_DASHBOARD_ACTIONS", "")).lower() in ("1", "true", "yes", "on")


def _auth_token() -> str:
    """Operator-set shared secret (SEGA_DASHBOARD_TOKEN). Empty = remote auth disabled."""
    return os.environ.get("SEGA_DASHBOARD_TOKEN", "").strip()


def _signer():
    """Cookie signer keyed off the token — no second secret to manage."""
    import hashlib

    from itsdangerous import URLSafeTimedSerializer

    key = hashlib.sha256(("sega-dash::" + _auth_token()).encode()).hexdigest()
    return URLSafeTimedSerializer(key, salt="sega-dashboard-session")


def _session_valid(req) -> bool:
    """True if the request carries a valid, unexpired unlock cookie."""
    if not _auth_token():
        return False
    cookie = req.cookies.get(_AUTH_COOKIE)
    if not cookie:
        return False
    try:
        return _signer().loads(cookie, max_age=_SESSION_MAX_AGE) == "unlocked"
    except Exception:
        return False


def _is_local_addr(addr: str) -> bool:
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return addr in ("localhost", "")
    return ip.is_loopback or ip.is_private


def _local_trusted(req) -> bool:
    """Legacy local-trust mode: env flag + non-tunnelled + local/private peer."""
    if not _env_actions_enabled():
        return False
    # Tunnel/proxy fingerprint → treat as remote, refuse (loopback alone is unsafe
    # behind a Cloudflare tunnel).
    if req.headers.get("CF-Connecting-IP") or req.headers.get("X-Forwarded-For"):
        return False
    return _is_local_addr(req.remote_addr or "")


def _actions_allowed(req) -> bool:
    """Actions permitted when the caller is locally trusted OR holds a valid
    token-unlocked session (works remotely over the HTTPS tunnel)."""
    return _local_trusted(req) or _session_valid(req)


def _auth_state(req) -> str:
    """For /v1/capabilities: local | session | locked (token set, not unlocked) | disabled."""
    if _local_trusted(req):
        return "local"
    if _session_valid(req):
        return "session"
    return "locked" if _auth_token() else "disabled"


def _in_container() -> bool:
    return os.path.exists("/.dockerenv")


class _UnlockLimiter:
    """Tiny in-memory brute-force guard: 5 failures per IP → 120s lockout."""

    def __init__(self, max_fails: int = 5, lockout: int = 120):
        self._fails: Dict[str, list] = {}
        self._lock = threading.Lock()
        self.max_fails = max_fails
        self.lockout = lockout

    def blocked(self, ip: str) -> bool:
        with self._lock:
            entry = self._fails.get(ip)
            if not entry:
                return False
            count, until = entry
            if until <= time.time():
                self._fails.pop(ip, None)
                return False
            return count >= self.max_fails

    def record_failure(self, ip: str) -> None:
        with self._lock:
            entry = self._fails.get(ip)
            now = time.time()
            if entry and entry[1] > now:
                self._fails[ip] = (entry[0] + 1, now + self.lockout)
            else:
                self._fails[ip] = (1, now + self.lockout)

    def reset(self, ip: str) -> None:
        with self._lock:
            self._fails.pop(ip, None)


def _csrf_ok(req) -> bool:
    """CSRF guard for state-changing POSTs. Requires the custom header our own JS
    sends; a cross-site simple request can't set it without a CORS preflight (which
    this server does not honor), so drive-by POSTs from another origin are blocked."""
    if not req.headers.get("X-Requested-With"):
        return False
    origin = req.headers.get("Origin")
    if origin:  # if present, its host must exactly match ours
        from urllib.parse import urlparse

        if urlparse(origin).netloc != req.headers.get("Host", ""):
            return False
    return True


class JobRunner:
    """Runs CLI actions in background threads; keeps a bounded in-memory history."""

    def __init__(self, max_jobs: int = 50):
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._order: List[str] = []
        self._active: set = set()  # slugs with an in-flight action
        self._lock = threading.Lock()
        self._max = max_jobs

    def is_busy(self, slug: str) -> bool:
        with self._lock:
            return slug in self._active

    def _cli_base(self) -> List[str]:
        exe = shutil.which("sega")
        return [exe] if exe else [sys.executable, "-m", "sega.cli.main"]

    @staticmethod
    def _norm(s: str) -> str:
        return (s or "").lower().replace("_", "-")

    @staticmethod
    def _dc_base(compose_files: str, project: str) -> List[str]:
        """`docker compose` base with one -f per file (the config_files label is a
        comma-separated list when a project uses multiple compose files)."""
        cmd = ["docker", "compose"]
        for f in compose_files.split(","):
            f = f.strip()
            if f:
                cmd += ["-f", f]
        cmd += ["-p", project]
        return cmd

    def resolve_compose(self, slug: str) -> Optional[tuple]:
        """Find the REAL compose file + project name for a slug.

        `sega local` does not map to how these stacks actually run, so we drive
        `docker compose` against the real file. Preference:
          1. a running container's `com.docker.compose.project.config_files` label
             (authoritative — exactly what deployed the stack), matched by name prefix;
          2. the conventional path ~/fleet/<slug>/docker-compose.dev.yml (or .yml).
        Returns (compose_file, project_name) or None.
        """
        # 1) from a live container's compose labels
        try:
            fmt = '{{.Names}}\t{{index .Config.Labels "com.docker.compose.project"}}\t{{index .Config.Labels "com.docker.compose.project.config_files"}}'
            r = subprocess.run(["docker", "ps", "-a", "--format", "{{.Names}}"],
                               capture_output=True, text=True, timeout=8)
            names = [n.strip() for n in (r.stdout or "").splitlines() if n.strip()]
            ns = self._norm(slug)
            match = next((n for n in names if self._norm(n).startswith(ns + "-") or self._norm(n) == ns), None)
            if match:
                ins = subprocess.run(
                    ["docker", "inspect", match, "--format",
                     '{{index .Config.Labels "com.docker.compose.project"}}\t{{index .Config.Labels "com.docker.compose.project.config_files"}}'],
                    capture_output=True, text=True, timeout=8)
                parts = (ins.stdout or "").strip().split("\t")
                if len(parts) == 2 and parts[1]:
                    return (parts[1], parts[0] or ns)
        except Exception:
            pass
        # 2) conventional per-project path. SEGA_FLEET_ROOT overrides for containerized
        # runs, where ~ is the container user's home but the projects are mounted at
        # the host path (e.g. /Users/<user>/fleet).
        from pathlib import Path
        root = Path(os.environ.get("SEGA_FLEET_ROOT", "~/fleet")).expanduser()
        base = root / slug
        for rel in ("docker-compose.dev.yml", "docker-compose.yml", "deployment/docker-compose.yml"):
            p = base / rel
            if p.exists():
                return (str(p), self._norm(slug))
        return None

    def build_argv(self, action: str, slug: str) -> List[List[str]]:
        """One or more argv lists to run in sequence for an action.

        Uses `docker compose -f <real file> -p <project>` when the project's compose
        file can be resolved; otherwise falls back to `sega local` (best-effort)."""
        # Native launch: opens the project's desktop app in dev mode on the HOST.
        # Only meaningful when the dashboard runs on the host (not containerized) —
        # the route refuses it in-container before we get here.
        if action == "launch":
            return [self._cli_base() + ["local", "launch", "-p", slug, "-t", "desktop", "--dev"]]

        resolved = self.resolve_compose(slug)
        if resolved:
            cf, proj = resolved
            dc = self._dc_base(cf, proj)
            if action == "start":
                return [dc + ["up", "-d"]]
            if action == "stop":
                return [dc + ["stop"]]              # keep containers (fast restart)
            if action == "restart":
                return [dc + ["restart"]]
            if action == "rebuild":
                return [dc + ["up", "-d", "--build"]]
            raise ValueError(f"unknown action: {action}")
        # Fallback: sega local (may not match real deployment on all hosts)
        base = self._cli_base()
        if action == "start":
            return [base + ["local", "up", "-p", slug, "--no-ledger"]]
        if action == "stop":
            return [base + ["local", "down", "-p", slug]]
        if action == "restart":
            return [base + ["local", "restart", "-p", slug]]
        if action == "rebuild":
            return [base + ["local", "down", "-p", slug],
                    base + ["local", "up", "-p", slug, "--no-ledger"]]
        raise ValueError(f"unknown action: {action}")

    def start(self, action: str, slug: str) -> Optional[str]:
        """Start an action job. Returns the job id, or None if an action for this
        project is already in flight (caller should surface a 409)."""
        cmds = self.build_argv(action, slug)
        timeout = _TIMEOUTS.get(action, 300)
        job_id = uuid.uuid4().hex[:12]
        with self._lock:
            if slug in self._active:
                return None
            self._active.add(slug)
            self._jobs[job_id] = {
                "id": job_id, "action": action, "slug": slug, "status": "running",
                "output": "", "exit_code": None, "started_at": time.time(), "done_at": None,
            }
            self._order.append(job_id)
            while len(self._order) > self._max:
                self._jobs.pop(self._order.pop(0), None)
        try:
            threading.Thread(target=self._run, args=(job_id, slug, cmds, timeout), daemon=True).start()
        except Exception:
            # Thread failed to launch — release the busy lock so the project isn't
            # wedged at 409 forever, and drop the orphaned job record.
            with self._lock:
                self._active.discard(slug)
                self._jobs.pop(job_id, None)
                if job_id in self._order:
                    self._order.remove(job_id)
            raise
        return job_id

    def _run(self, job_id: str, slug: str, cmds: List[List[str]], timeout: int) -> None:
        chunks: List[str] = []
        code = 0
        try:
            for cmd in cmds:
                chunks.append("$ " + " ".join(cmd))
                try:
                    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
                    chunks.append((r.stdout or "") + (r.stderr or ""))
                    code = r.returncode
                    if code != 0:
                        break
                except subprocess.TimeoutExpired:
                    chunks.append(f"[timed out after {timeout}s]")
                    code = -1
                    break
                except Exception as e:  # CLI missing, etc.
                    chunks.append(f"[error: {e}]")
                    code = -1
                    break
        finally:
            with self._lock:
                self._active.discard(slug)  # always release the busy lock
                job = self._jobs.get(job_id)
                if job is not None:
                    job["output"] = "\n".join(chunks)[-20000:]
                    job["exit_code"] = code
                    job["status"] = "succeeded" if code == 0 else "failed"
                    job["done_at"] = time.time()

    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            job = self._jobs.get(job_id)
            return dict(job) if job else None


def register_action_routes(dash_app, config_manager) -> None:
    """Register action routes on the Dash app's Flask server."""
    server = dash_app.server
    runner = JobRunner()
    limiter = _UnlockLimiter()

    def _known_slugs() -> set:
        try:
            return {p.get("slug") for p in config_manager.get_all_projects() if p.get("slug")}
        except Exception:
            return set()

    @server.route("/v1/capabilities")
    def capabilities():
        return jsonify({
            "actions_enabled": _actions_allowed(request),
            "auth": _auth_state(request),
            # Native desktop launch only works when the dashboard runs on the host.
            "native_launch": _actions_allowed(request) and not _in_container(),
            "actions": list(_VALID_ACTIONS) + ["logs"],
            # Surfaced in the header settings popover's environment readout.
            "in_container": _in_container(),
        })

    @server.route("/v1/auth/unlock", methods=["POST"])
    def auth_unlock():
        if not _csrf_ok(request):
            return jsonify({"error": "missing X-Requested-With header"}), 403
        token = _auth_token()
        if not token:
            return jsonify({"error": "remote operations are not configured on this dashboard"}), 403
        ip = request.headers.get("CF-Connecting-IP") or request.remote_addr or "?"
        if limiter.blocked(ip):
            return jsonify({"error": "too many attempts — try again in a couple of minutes"}), 429
        supplied = (request.get_json(silent=True) or {}).get("password", "")
        import hmac

        if not (supplied and hmac.compare_digest(supplied, token)):
            limiter.record_failure(ip)
            return jsonify({"error": "invalid password"}), 401
        limiter.reset(ip)
        resp = jsonify({"ok": True, "expires_in": _SESSION_MAX_AGE})
        resp.set_cookie(
            _AUTH_COOKIE, _signer().dumps("unlocked"),
            max_age=_SESSION_MAX_AGE, httponly=True, secure=request.is_secure,
            samesite="Strict", path="/",
        )
        return resp

    @server.route("/v1/auth/lock", methods=["POST"])
    def auth_lock():
        resp = jsonify({"ok": True})
        resp.delete_cookie(_AUTH_COOKIE, path="/")
        return resp

    @server.route("/v1/actions/<slug>/<action>", methods=["POST"])
    def run_action(slug: str, action: str):
        if not _actions_allowed(request):
            return jsonify({"error": "operations locked — unlock with the dashboard password"}), 403
        if not _csrf_ok(request):
            return jsonify({"error": "missing X-Requested-With header (CSRF guard)"}), 403
        if action not in _VALID_ACTIONS:
            return jsonify({"error": f"unknown action: {action}"}), 400
        if action == "launch" and _in_container():
            return jsonify({"error": "native launch requires a host-run dashboard (this one is containerized)"}), 400
        if slug not in _known_slugs():
            return jsonify({"error": f"unknown project: {slug}"}), 404
        job_id = runner.start(action, slug)
        if job_id is None:
            return jsonify({"error": f"an action for {slug} is already running"}), 409
        return jsonify({"job_id": job_id, "slug": slug, "action": action}), 202

    @server.route("/v1/jobs/<job_id>")
    def job_status(job_id: str):
        if not _actions_allowed(request):  # job output is only for the local operator
            return jsonify({"error": "actions disabled"}), 403
        job = runner.get(job_id)
        if job is None:
            return jsonify({"error": "unknown job"}), 404
        return jsonify(job)

    @server.route("/v1/logs/<slug>")
    def project_logs(slug: str):
        if not _actions_allowed(request):
            return jsonify({"error": "actions disabled"}), 403
        if slug not in _known_slugs():
            return jsonify({"error": f"unknown project: {slug}"}), 404
        tail = request.args.get("tail", "200")
        service = request.args.get("service")
        resolved = runner.resolve_compose(slug)
        if resolved:
            cf, proj = resolved
            cmd = runner._dc_base(cf, proj) + ["logs", "--no-color", "--tail", str(tail)]
            if service:
                cmd += [service]
        else:  # fallback to the CLI
            cmd = runner._cli_base() + ["local", "logs", slug, "--no-follow", "--tail", str(tail)]
            if service:
                cmd += ["--service", service]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=_TIMEOUTS["logs"])
            return jsonify({"slug": slug, "output": ((r.stdout or "") + (r.stderr or ""))[-40000:]})
        except subprocess.TimeoutExpired:
            return jsonify({"slug": slug, "output": "[logs timed out]"}), 504
        except Exception as e:
            return jsonify({"slug": slug, "output": f"[error: {e}]"}), 500
