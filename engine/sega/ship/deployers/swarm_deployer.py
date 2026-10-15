#!/usr/bin/env python
# -*- coding: utf-8 -*-
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

# ===============================================================
# SEGA MODULE - Swarm Deployer (distributed swarm fleet)
# ===============================================================
# File: src/sega/ship/deployers/swarm_deployer.py
# Purpose: Deploy the distributed swarm continuous-train/sim stack onto a flat
#          pool of nodes (single host, Mac-mini LAN, or EC2) via Docker Swarm.
#
# Ownership boundary (see swarm/docs/DISTRIBUTED_FLEET_DEPLOY_PLAN.md):
#   - swarm OWNS the *artifact*: the swarm stack file + per-project workload env
#     (images, commands, measured cgroup reservations) + the images themselves.
#   - sega OWNS *getting it onto infrastructure and running it*: provisioning EC2,
#     forming the swarm across hosts, the fleet inventory/topology, `stack deploy`.
#
# This deployer is the sega side of that contract. It consumes swarm's published
# stack file + `env/<project>.env`, layers a sega-owned fleet definition
# (registry, shared-store path, placement, provisioning mode), provisions/forms
# the swarm, and deploys. Two axes:
#   workload  -> --sim/--train/--external + replica counts (swarm replicas; 0=off)
#   fleet     -> single | mini-net | ec2  (sega/config/fleets/<fleet>.env)
#
# Dependencies: subprocess, shutil, os, dataclasses, typing
# ===============================================================

import os
import shlex
import subprocess
import time
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List

from ...core.deployment_result import DeploymentResult
from .base_deployer import BaseDeployer


# --- contract defaults: where swarm publishes its artifact ---------------------
DEFAULT_INTEL_ROOT = os.path.expanduser(
    os.environ.get("INTEL_ROOT", "~/fleet/swarm")
)
# sega-owned fleet definitions (moved out of swarm as part of the split)
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_FLEET_DIR = os.path.abspath(
    os.path.join(_THIS_DIR, "..", "..", "..", "..", "config", "fleets")
)
DEFAULT_TF_DIR = os.path.abspath(
    os.path.join(
        _THIS_DIR, "..", "..", "..", "..",
        "infrastructure", "terraform", "modules", "intel_fleet",
    )
)


@dataclass
class FleetSpec:
    """A single deploy request: what workload, onto which fleet."""

    project: str
    fleet: str                       # single | mini-net | ec2
    sim: bool = False
    train: bool = False
    external: bool = False
    sim_workers: Optional[int] = None
    train_workers: Optional[int] = None
    version: str = "latest"
    nodes: Optional[int] = None      # ec2: instance count for terraform
    intel_root: str = DEFAULT_INTEL_ROOT
    fleet_dir: str = DEFAULT_FLEET_DIR
    tf_dir: str = DEFAULT_TF_DIR
    extra_env: Dict[str, str] = field(default_factory=dict)

    @property
    def stack_file(self) -> str:
        return os.path.join(
            self.intel_root, "deploy", "fleet", "docker-compose.swarm.yml"
        )

    @property
    def project_env(self) -> str:
        return os.path.join(
            self.intel_root, "deploy", "fleet", "env", f"{self.project}.env"
        )

    @property
    def fleet_env(self) -> str:
        return os.path.join(self.fleet_dir, f"{self.fleet}.env")

    @property
    def stack_name(self) -> str:
        return f"intel_{self.project}"


class SwarmDeployer(BaseDeployer):
    """Deploys swarm's swarm stack onto a fleet. sega side of the contract."""

    def __init__(self, intel_root: Optional[str] = None):
        super().__init__()
        self.intel_root = intel_root or DEFAULT_INTEL_ROOT

    # ---- BaseDeployer interface -------------------------------------------
    def deploy(
        self,
        target: str,
        strategy: str = "rolling",
        image_tag: str = "latest",
        force: bool = False,
        dry_run: bool = False,
        **kwargs: Any,
    ) -> DeploymentResult:
        """Router entrypoint. `target` doubles as the fleet name; swarm-specific
        params (project, sim/train, replica counts) arrive via **kwargs so the
        generic router/CLI can drive this without a bespoke signature."""
        try:
            spec = self._spec_from_kwargs(target, image_tag, kwargs)
        except ValueError as e:
            return self._create_deployment_result(False, str(e), error=str(e))
        return self.deploy_fleet(spec, dry_run=dry_run)

    def get_deployment_status(self, target: str) -> Dict[str, Any]:
        """`target` = project name -> report placed services for its stack."""
        stack = f"intel_{target}"
        out = self._run(
            self._dk() + ["stack", "services", stack], check=False, capture=True
        )
        return {"stack": stack, "services": out.stdout if out else ""}

    def status_report(self, project: str) -> Dict[str, Any]:
        """Read-only fleet status — per-service replicas/health + recent task errors +
        published ports. Pure CLI reads: NO docker-socket exposure (the safe alternative
        to Portainer for 'how do I see the fleet')."""
        stack = f"intel_{project}"
        svc = self._run(["docker", "stack", "services", stack,
                         "--format", "{{.Name}}\t{{.Replicas}}\t{{.Image}}\t{{.Ports}}"],
                        check=False, capture=True)
        services = []
        for ln in ((svc.stdout if svc else "") or "").splitlines():
            if not ln.strip():
                continue
            p = (ln.split("\t") + ["", "", "", ""])[:4]
            name, rep, img, ports = p
            run_s, _, des_s = rep.partition("/")
            run = int("".join(c for c in run_s if c.isdigit()) or 0)
            des = int("".join(c for c in des_s if c.isdigit()) or 0)
            state = "off" if des == 0 else ("healthy" if run >= des else "DEGRADED")
            services.append({"name": name.replace(f"{stack}_", ""), "replicas": rep,
                             "state": state, "image": img.split("/")[-1], "ports": ports.strip()})
        ps = self._run(["docker", "stack", "ps", stack, "--no-trunc",
                        "--format", "{{.Name}}\t{{.CurrentState}}\t{{.Error}}"],
                       check=False, capture=True)
        errors = [ln for ln in ((ps.stdout if ps else "") or "").splitlines()
                  if "\tFailed" in ln or (ln.rstrip() and ln.split("\t")[-1].strip())]
        return {"stack": stack, "services": services, "recent_errors": errors[:8],
                "healthy": bool(services) and all(s["state"] != "DEGRADED" for s in services)}

    def rollback(
        self, target: str, to_version: Optional[str] = None
    ) -> DeploymentResult:
        """Roll each service in the stack back to its previous spec."""
        stack = f"intel_{target}"
        svcs = self._run(
            ["docker", "stack", "services", "-q", stack],
            check=False, capture=True,
        )
        ids = (svcs.stdout.split() if svcs and svcs.stdout else [])
        for sid in ids:
            self._run(["docker", "service", "rollback", sid], check=False)
        return self._create_deployment_result(
            True, f"rolled back {len(ids)} services in {stack}"
        )

    # ---- fleet orchestration ----------------------------------------------
    def deploy_fleet(self, spec: FleetSpec, dry_run: bool = False,
                     wait: bool = True, timeout: int = 180) -> DeploymentResult:
        """provision (ec2) -> PREFLIGHT -> form swarm -> deploy -> HEALTH-GATE.
        Idempotent. A deploy whose services crash-loop returns FAILURE, not success
        (the lesson from live testing: `stack deploy` reports 'created', not 'healthy')."""
        for p in (spec.stack_file, spec.project_env, spec.fleet_env):
            if not os.path.exists(p):
                msg = f"missing required artifact: {p}"
                return self._create_deployment_result(False, msg, error=msg)

        env = self._compose_env(spec)

        # PREFLIGHT — fail fast on blank env / bad render BEFORE touching the cluster
        pf = self._preflight(spec, env)
        if not pf["ok"]:
            return self._create_deployment_result(
                False, f"preflight failed: {pf['msg']}", error=pf["msg"])
        warns = pf.get("warnings", [])
        wtxt = (" [WARN: " + "; ".join(warns) + "]") if warns else ""

        if dry_run:
            return self._create_deployment_result(
                True, f"dry-run: preflight OK + stack rendered{wtxt}",
                metadata={"rendered": pf.get("rendered", "")[:4000], "warnings": warns},
            )

        # 1. provision (ec2 only) -> materializes an inventory the swarm step uses
        inventory = env.get("INVENTORY", "")
        if env.get("PROVISION") == "terraform":
            inventory = self._provision_ec2(spec, env)
            env["INVENTORY"] = inventory

        # 2. form / verify the swarm across the fleet
        self._ensure_swarm(spec.fleet, inventory, env.get("DROP_PATH", "/opt/swarm/data"))

        # 2b. remote targeting: for a remote (multi-node) swarm the MANAGER is the EC2 head,
        # not this host — so `stack deploy`/status run against a context pointed at the head.
        self._deploy_ctx = (self._remote_context(inventory)
                            if (inventory and spec.fleet != "single") else None)

        # 2c. image delivery. sideload (default for ec2) = the k8s effort's approach:
        # `docker save | ssh node docker load` to every node, no ECR/registry/R2. Then
        # deploy with --resolve-image=never so swarm uses the loaded images, not a pull.
        delivery = env.get("IMAGE_DELIVERY") or ("sideload" if spec.fleet == "ec2" else "registry")
        opts = ["--with-registry-auth"]
        if delivery == "sideload" and inventory:
            self._sideload_images(env, inventory)
            opts.append("--resolve-image=never")

        # 2d. R2 durability (opt-in). Stage the sync script on the head (a fresh EC2 node
        # doesn't have it) so the archive sidecar can bind-mount it; then RESTORE prior
        # weights from R2 into the shared store BEFORE train starts, so warm-start
        # (INTEL_WARM_START) resumes from the fleet's cumulative weights instead of cold.
        # No-ops unless R2 is configured (EFS fleets persist weights natively).
        self._stage_host_assets(spec, env, inventory)
        self._stage_r2_script(spec, env, inventory)
        self._restore_weights(spec, env, inventory)

        # 3. deploy the stack (targeting the head context for remote swarms)
        self._run(self._dk() + ["stack", "deploy", *opts, "-c", spec.stack_file, spec.stack_name],
                  env=env, check=True)

        # 4. HEALTH-GATE — a crash-looping deploy is a FAILED deploy
        if wait:
            h = self._wait_for_convergence(spec.stack_name, timeout)
            if not h["ok"]:
                return self._create_deployment_result(
                    False, f"{spec.stack_name} deployed but UNHEALTHY: {h['summary']}",
                    error=h["summary"], metadata=h)
            summary = h["summary"]
        else:
            summary = "not health-checked (--no-wait)"

        status = self.get_deployment_status(spec.project)
        if warns:
            status = {**status, "warnings": warns}
        return self._create_deployment_result(
            True,
            f"deployed {spec.stack_name} on fleet={spec.fleet} "
            f"(sim={env['SIM_WORKERS']} train={env['TRAIN_WORKERS']}) — {summary}{wtxt}",
            metadata=status,
        )

    # ---- preflight + health gate (lessons from live testing) ---------------
    def _preflight(self, spec: FleetSpec, env: Dict[str, str]) -> Dict[str, Any]:
        """Fail fast before touching the cluster: no blank required vars + the stack
        renders. Catches the env-quoting / interpolation / bad-image-ref bugs that
        otherwise only surface as crash-loops mid-deploy."""
        required = ["REGISTRY", "VERSION", "DROP_PATH", "INTEL_IMAGE"]
        if spec.sim:
            required += ["ENGINE_IMAGE", "SIM_CMD"]
        blank = sorted({k for k in required if not str(env.get(k, "")).strip()})
        if blank:
            return {"ok": False, "msg": f"blank required env: {', '.join(blank)}"}
        # render (best-effort — needs docker). Catches YAML/interp errors + bad refs.
        r = self._run(["docker", "stack", "config", "-c", spec.stack_file],
                      env=env, check=False, capture=True)
        if r is not None and r.returncode not in (0, 127, None):  # 127 = docker absent, skip
            return {"ok": False, "msg": f"stack render failed: {(r.stderr or '').strip()[:300]}"}
        warnings = []
        if str(env.get("VERSION", "")).strip() in ("", "latest"):
            warnings.append("deploying a mutable ':latest' image tag — services may NOT roll "
                            "on code change + stale-image risk; pin a SHA/content tag")
        return {"ok": True, "msg": "ok", "warnings": warnings,
                "rendered": (r.stdout if r else "") or ""}

    def _wait_for_convergence(self, stack: str, timeout: int) -> Dict[str, Any]:
        """Poll until every service reaches its desired replicas, else timeout. A service
        stuck below desired (crash-looping) => UNHEALTHY, with the laggards' last logs."""
        deadline = time.time() + timeout
        last: Dict[str, tuple] = {}
        while time.time() < deadline:
            r = self._run(self._dk() + ["stack", "services", stack,
                           "--format", "{{.Name}}\t{{.Replicas}}"], check=False, capture=True)
            rows = [ln for ln in ((r.stdout if r else "") or "").splitlines() if ln.strip()]
            last, all_ok = {}, True
            for ln in rows:
                name, _, rep = ln.partition("\t")
                run_s, _, des_s = rep.strip().partition("/")           # "2/2", "0/1"
                run = int("".join(c for c in run_s if c.isdigit()) or 0)
                des = int("".join(c for c in des_s if c.isdigit()) or 0)
                last[name.strip()] = (run, des)
                if des > 0 and run < des:
                    all_ok = False
            if rows and all_ok:
                active = sum(1 for v in last.values() if v[1] > 0)
                return {"ok": True, "summary": f"{active} active services healthy",
                        "services": last}
            time.sleep(3)
        bad = {n: f"{run}/{des}" for n, (run, des) in last.items() if des > 0 and run < des}
        logs = {}
        for n in list(bad)[:4]:
            lg = self._run(self._dk() + ["service", "logs", "--tail", "4", n],
                           check=False, capture=True)
            logs[n] = (((lg.stderr or "") + (lg.stdout or "")) if lg else "")[-400:]
        return {"ok": False, "summary": f"unhealthy after {timeout}s: {bad or 'no services'}",
                "unhealthy": bad, "logs": logs, "services": last}

    def _advertise_addr(self) -> str:
        """Swarm-init advertise addr — tailscale IP if present, else loopback. Avoids the
        multi-NIC 'could not choose an address to advertise' failure seen on NODE-5."""
        ts = self._run(["tailscale", "ip", "-4"], check=False, capture=True)
        if ts and ts.returncode == 0 and (ts.stdout or "").strip():
            return (ts.stdout or "").strip().splitlines()[0].strip()
        return "127.0.0.1"

    # ---- image sideload (no ECR/registry/R2 — the k8s effort's approach) ----
    def _sideload_images(self, env: Dict[str, str], inventory: str) -> None:
        """Ship locally-built images to every node's docker over SSH — no registry, ECR,
        or R2 (the ~10 GB of images would eat the R2 budget). Adapts sideload-image.sh for
        Swarm: `docker save <imgs> | ssh node docker load`, streamed (no multi-GB temp tar).
        Images must exist LOCALLY under the exact names the stack references; pairs with
        `--resolve-image=never` at deploy so swarm uses the loaded copy, not a pull."""
        refs = []
        for k in ("INTEL_IMAGE", "ENGINE_IMAGE", "BACKEND_IMAGE"):
            v = env.get(k)
            if v:
                refs.append(self._resolve(v, env))
        refs = [r for r in dict.fromkeys(refs) if r]     # dedup, drop blanks
        if not refs:
            return
        for row in self._read_inventory(inventory):
            # stream one tar of all images straight into the node's docker load
            save = subprocess.Popen(["docker", "save", *refs], stdout=subprocess.PIPE)
            load = subprocess.Popen(
                ["ssh", *self._SSH_OPTS, row["ssh"], "docker load"],
                stdin=save.stdout)
            save.stdout.close()
            load.communicate()
            if save.wait() != 0 or load.returncode != 0:
                raise RuntimeError(f"sideload to {row['fqdn']} failed (are the images built locally?)")

    @staticmethod
    def _resolve(s: str, env: Dict[str, str]) -> str:
        """Expand ${VAR}/$VAR from env in a string — the deployer needs concrete image
        names for `docker save`, since docker's own interpolation happens later at deploy."""
        import re
        return re.sub(r"\$\{([A-Za-z_]\w*)\}|\$([A-Za-z_]\w*)",
                      lambda m: env.get(m.group(1) or m.group(2), m.group(0)), s)

    # ---- remote deploy targeting (the manager is the EC2 head, not this host) ----
    def _remote_context(self, inventory: str) -> Optional[str]:
        """Docker context pointing at the swarm's HEAD node so `stack deploy` targets the
        remote MANAGER (ec2/mini-net), not the deployer's local docker. This is the swarm
        analog of the k8s sibling's fetched-kubeconfig remote targeting."""
        head = next((r for r in self._read_inventory(inventory) if r["role"] == "head"), None)
        if not head:
            return None
        name = "swarm-fleet-head"
        self._run(["docker", "context", "rm", "-f", name], check=False)
        self._run(["docker", "context", "create", name,
                   "--docker", f"host=ssh://{head['ssh']}"], check=False)
        return name

    def _dk(self) -> List[str]:
        """`docker` prefix, routed to the remote head context when deploying to a remote
        swarm (set by deploy_fleet). Local/single-host -> plain `docker`."""
        c = getattr(self, "_deploy_ctx", None)
        return ["docker"] + (["--context", c] if c else [])

    def teardown(self, spec: FleetSpec, destroy_infra: bool = False,
                 yes: bool = False, deep: bool = False) -> DeploymentResult:
        """Tear down. Safe-by-default, with a verified clean slate:

        - default: `docker stack rm` only — removes the *workload*, keeps the fleet,
          swarm, and shared store (samples + checkpoints) intact. Reversible.
        - `--deep`: also remove the stack's residue — dangling volumes/network + the
          local registry container. Does NOT touch the shared store or leave the swarm.
        - `--destroy` (ec2 only): also `terraform destroy` the fleet. Gated behind
          `--yes` (destroying EFS = all samples + checkpoints); without it, PREVIEWS only.
        Every path ends with a RESIDUE CHECK that verifies a clean slate (the parallel
        k8s effort's 'residue sweep must show clean' rule, applied to swarm).
        """
        # 1. always: remove the running stack (data on EFS/NFS untouched)
        self._run(["docker", "stack", "rm", spec.stack_name], check=False)

        if not destroy_infra or spec.fleet != "ec2":
            if deep:
                self._deep_clean(spec)
            residue = self._residue_check(spec.stack_name)
            note = "stack removed" + (" + deep-cleaned" if deep else "")
            if spec.fleet != "single":
                note += "; fleet + shared store retained"
            note += f"; {residue['summary']}"
            return self._create_deployment_result(
                residue["clean"], f"{spec.stack_name}: {note}", metadata=residue)

        # 2. ec2 + --destroy: tear the provisioned fleet down via terraform
        env = self._compose_env(spec)
        tfdir = env.get("TF_DIR", spec.tf_dir)
        varflag = ([f"-var-file={env['TF_VARS']}"] if env.get("TF_VARS") else [])
        base = ["terraform", f"-chdir={tfdir}"]
        self._run(base + ["init", "-input=false"], check=False)
        if not yes:
            # never destroy infra (and EFS data) without an explicit ack
            self._run(base + ["plan", "-destroy", "-input=false"] + varflag, check=False)
            return self._create_deployment_result(
                True,
                f"{spec.stack_name}: PREVIEW only — re-run with --yes to destroy. "
                f"WARNING: destroys EFS (all samples + trained checkpoints); copy "
                f"anything you need off {env.get('DROP_PATH')} first.",
            )
        # HARVEST the trained weights off the shared store BEFORE destroy wipes it —
        # so a --destroy never silently loses a run's output. Best-effort; logged.
        harvested = self._harvest_weights(spec, env)
        self._run(base + ["destroy", "-auto-approve", "-input=false"] + varflag, check=True)
        residue = self._residue_check(spec.stack_name)
        hnote = f"; weights harvested -> {harvested}" if harvested else "; no weights to harvest"
        return self._create_deployment_result(
            True, f"{spec.stack_name}: fleet destroyed (instances + EFS gone){hnote}; {residue['summary']}",
            metadata={**residue, "harvested": harvested})

    def _harvest_weights(self, spec: FleetSpec, env: Dict[str, str]) -> Optional[str]:
        """Copy trained weights (FedAvg merged output + RUNTIME certified ckpts) off the
        head's shared store to a LOCAL dir before teardown destroys it. Best-effort — never
        blocks/raises into teardown. Returns the local tarball path, or None if nothing."""
        inv = env.get("INVENTORY") or os.path.join(env.get("TF_DIR", spec.tf_dir), "fleet.inventory")
        if not (inv and os.path.exists(inv)):
            return None
        try:
            head = next((r for r in self._read_inventory(inv) if r["role"] == "head"), None)
        except Exception:
            head = None
        if not head:
            return None
        drop = env.get("DROP_PATH", "/opt/swarm/data")
        dest = os.path.join(self.intel_root, "harvest", spec.project)
        os.makedirs(dest, exist_ok=True)
        out = os.path.join(dest, f"{head['fqdn'].split('.')[0]}.weights.tgz")
        # tar just the weights dirs (merged FedAvg output + RUNTIME) if present; stream to us
        remote = (f"cd {shlex.quote(drop)} 2>/dev/null && d=$(ls -d _fedavg RUNTIME 2>/dev/null) "
                  f"&& [ -n \"$d\" ] && tar czf - $d 2>/dev/null || true")
        try:
            with open(out, "wb") as fh:
                subprocess.run(["ssh", *self._SSH_OPTS, head["ssh"], remote],
                               stdout=fh, stderr=subprocess.DEVNULL, check=False)
            if os.path.getsize(out) > 64:      # non-empty tar
                return out
            os.remove(out)
        except Exception:
            pass
        return None

    def _stage_host_assets(self, spec: FleetSpec, env: Dict[str, str],
                           inventory: Optional[str]) -> None:
        """Stage the stack's host-mounted assets onto remote nodes — a fresh cloud node
        lacks the repo, so the crafts/etc bind-mounts (`INTEL_CRAFTS_PATH`/`INTEL_ETC_PATH`,
        default relative paths that resolve to the deploy host) and the sim config (which
        `SIM_CMD` reads from the shared store) don't exist there. crafts is ~86 MB, etc tiny.
        Repoints INTEL_CRAFTS_PATH/INTEL_ETC_PATH at the on-node copies. Single-host keeps
        its local repo paths (no inventory → no-op)."""
        if spec.fleet == "single" or not inventory:
            return
        try:
            rows = self._read_inventory(inventory)
        except Exception:
            return
        crafts = os.path.join(self.intel_root, "crafts")
        etc = os.path.join(self.intel_root, "etc")
        sim_cfg = os.path.join(self.intel_root, "deploy", "fleet", "assets",
                               f"{spec.project}-sim.toml")
        drop = env.get("DROP_PATH", "/opt/swarm/data")
        for r in rows:
            tgt = r["ssh"]
            for src, dest in ((crafts, "/opt/swarm/crafts"), (etc, "/opt/swarm/etc")):
                if os.path.isdir(src):
                    tar = subprocess.Popen(["tar", "czf", "-", "-C", src, "."],
                                           stdout=subprocess.PIPE)
                    subprocess.run(["ssh", *self._SSH_OPTS, tgt,
                                    f"mkdir -p {shlex.quote(dest)} && tar xzf - -C {shlex.quote(dest)}"],
                                   stdin=tar.stdout, check=False, capture_output=True)
                    if tar.stdout:
                        tar.stdout.close()
                    tar.wait()
            if os.path.isfile(sim_cfg):     # SIM_CMD reads /data/<proj>/<proj>-sim.toml == drop/<proj>-sim.toml
                subprocess.run(["scp", *self._SSH_OPTS, sim_cfg,
                                f"{tgt}:{drop}/{spec.project}-sim.toml"],
                               check=False, capture_output=True)
        env["INTEL_CRAFTS_PATH"] = "/opt/swarm/crafts"
        env["INTEL_ETC_PATH"] = "/opt/swarm/etc"

    def _stage_r2_script(self, spec: FleetSpec, env: Dict[str, str],
                         inventory: Optional[str]) -> None:
        """scp the R2 sync script onto the head so the archive sidecar can bind-mount it
        (fresh EC2 nodes don't have the repo). Sets R2_SYNC_SCRIPT to the staged path.
        No-op unless R2 archiving is on (R2_ENDPOINT + R2_SYNC_WORKERS>0)."""
        if not (env.get("R2_ENDPOINT") and int(env.get("R2_SYNC_WORKERS", "0") or 0) > 0 and inventory):
            return
        local = os.path.join(self.intel_root, "deploy", "fleet", "lib", "r2-sync.sh")
        if not os.path.exists(local):
            return
        staged = "/tmp/r2-sync.sh"
        try:
            for r in self._read_inventory(inventory):     # every node that might run the sidecar
                subprocess.run(["scp", *self._SSH_OPTS, local, f"{r['ssh']}:{staged}"],
                               check=False, capture_output=True, text=True)
            env["R2_SYNC_SCRIPT"] = staged
        except Exception:
            pass

    def _restore_weights(self, spec: FleetSpec, env: Dict[str, str],
                         inventory: Optional[str]) -> None:
        """Pull prior weights from R2 into the head's shared store (…/_fedavg, …/RUNTIME)
        so warm-start resumes from them. No-op unless R2 is configured. Best-effort — runs
        the aws-cli image on the head; creds come from R2_CREDS_FILE (parsed on the deploy
        host, passed as env — never left on the node). EFS fleets persist weights natively."""
        ep = env.get("R2_ENDPOINT")
        if not (ep and inventory):
            return
        try:
            head = next((r for r in self._read_inventory(inventory) if r["role"] == "head"), None)
        except Exception:
            head = None
        if not head:
            return
        ak, sk = self._read_r2_creds(env.get("R2_CREDS_FILE", ""))
        if not (ak and sk):
            return
        drop = env.get("DROP_PATH", "/opt/swarm/data")
        bucket = env.get("R2_BUCKET", "swarm-training-data")
        base = f"{env.get('R2_PREFIX', 'fleet/')}{spec.project}/weights"
        rg = env.get("R2_REGION", "auto")
        for sub in ("_fedavg", "RUNTIME"):
            cmd = (f"docker run --rm -e AWS_ACCESS_KEY_ID={shlex.quote(ak)} "
                   f"-e AWS_SECRET_ACCESS_KEY={shlex.quote(sk)} "
                   f"-v {shlex.quote(drop)}:/data amazon/aws-cli:latest "
                   f"--endpoint-url {shlex.quote(ep)} --region {shlex.quote(rg)} "
                   f"s3 sync s3://{bucket}/{base}/{sub} /data/{sub} --only-show-errors")
            self._ssh(head["ssh"], cmd, check=False)

    @staticmethod
    def _read_r2_creds(path: str):
        """(access_key, secret_key) from an AWS-credentials-format file, or (None, None)."""
        ak = sk = None
        try:
            if path and os.path.exists(path):
                for line in open(path):
                    s = line.strip()
                    if s.startswith("aws_access_key_id"):
                        ak = s.split("=", 1)[1].strip()
                    elif s.startswith("aws_secret_access_key"):
                        sk = s.split("=", 1)[1].strip()
        except Exception:
            pass
        return ak, sk

    def harvest(self, spec: FleetSpec) -> DeploymentResult:
        """Standalone harvest (no teardown): pull weights off the live fleet's head."""
        env = self._compose_env(spec)
        if env.get("PROVISION") == "terraform":
            env.setdefault("INVENTORY", os.path.join(env.get("TF_DIR", spec.tf_dir), "fleet.inventory"))
        path = self._harvest_weights(spec, env)
        return self._create_deployment_result(
            bool(path), f"harvested weights -> {path}" if path else "no weights found to harvest",
            metadata={"harvested": path})

    def _deep_clean(self, spec: FleetSpec) -> None:
        """Remove this stack's residue: its overlay network, its named volumes, and the
        local registry container. Never touches the shared store or leaves the swarm."""
        self._run(["docker", "network", "rm", "swarm-net"], check=False)
        vols = self._run(["docker", "volume", "ls", "-q"], check=False, capture=True)
        for v in ((vols.stdout if vols else "") or "").split():
            if "swarm" in v or spec.project in v:
                self._run(["docker", "volume", "rm", v], check=False)
        self._run(["docker", "rm", "-f", "registry"], check=False)   # local registry:2

    def _residue_check(self, stack: str) -> Dict[str, Any]:
        """Verify a clean slate: no services/network/volumes left for the stack. Returns
        {clean, summary, leftovers} — a failed clean is surfaced, not silently ignored."""
        left = {}
        svc = self._run(["docker", "stack", "services", "-q", stack], check=False, capture=True)
        s = [x for x in ((svc.stdout if svc else "") or "").split() if x]
        if s:
            left["services"] = len(s)
        net = self._run(["docker", "network", "ls", "--filter", "name=swarm-net", "-q"],
                        check=False, capture=True)
        if ((net.stdout if net else "") or "").strip():
            left["network"] = "swarm-net"
        clean = not left
        return {"clean": clean,
                "summary": "clean slate ✓" if clean else f"RESIDUE remains: {left}",
                "leftovers": left}

    def test(self, spec: FleetSpec, hold_seconds: int = 60,
             destroy_infra: Optional[bool] = None) -> DeploymentResult:
        """Deploy, hold briefly, then GUARANTEE teardown — the safe way to run a
        short test without leaving anything billing. Teardown runs in `finally`,
        so it happens even if deploy or the hold raises. For ec2 it destroys the
        fleet by default (stops billing); single/mini-net just remove the stack.
        Note: this is the process-level guarantee; the cloud-init TTL backstop
        (ttl_minutes) covers the case where THIS process itself dies mid-test."""
        if destroy_infra is None:
            destroy_infra = (spec.fleet == "ec2")
        deploy_res = None
        try:
            deploy_res = self.deploy_fleet(spec, dry_run=False)
            if hold_seconds > 0:
                time.sleep(hold_seconds)
            status = self.get_deployment_status(spec.project)
            return self._create_deployment_result(
                True,
                f"test OK: deployed {spec.stack_name}, held {hold_seconds}s, torn down",
                metadata={"deploy": bool(deploy_res and deploy_res.success), "status": status},
            )
        finally:
            # ALWAYS tear down — the whole point of `test`. yes=True because the
            # caller opted into a self-cleaning run.
            self.teardown(spec, destroy_infra=destroy_infra, yes=True)

    # ---- env composition (the swarm<->sega contract) ----------------------
    def _compose_env(self, spec: FleetSpec) -> Dict[str, str]:
        """Layer: process env -> fleet env (sega) -> project env (swarm) ->
        resolved workload replica counts. Mirrors swarm-up's ordering so the
        stack file's ${VAR}s all resolve. Fleet first so REGISTRY/VERSION exist
        when the project env references them."""
        env = dict(os.environ)
        env.update(self._read_env_file(spec.fleet_env))     # sega: where/registry
        env.update(self._read_env_file(spec.project_env))   # swarm: workload
        env.update(spec.extra_env)

        env["VERSION"] = spec.version or env.get("VERSION", "latest")
        env["SIM_WORKERS"] = str(
            (spec.sim_workers if spec.sim_workers is not None
             else int(env.get("SIM_WORKERS_DEFAULT", "8"))) if spec.sim else 0
        )
        env["TRAIN_WORKERS"] = str(
            (spec.train_workers if spec.train_workers is not None
             else int(env.get("TRAIN_WORKERS_DEFAULT", "2"))) if spec.train else 0
        )
        env["EXTERNAL_WORKERS"] = str(1 if spec.external else 0)

        # Expand nested ${VAR} references in env VALUES to a fixpoint. The env files carry
        # composed values like BACKEND_IMAGE=${REGISTRY}/hermes-backend:${VERSION}; our file
        # parser reads them literally (shell `source`/swarm-up would expand them). Docker
        # compose interpolation is SINGLE-PASS — it substitutes ${BACKEND_IMAGE} but does
        # NOT then expand the ${REGISTRY} that came in from that value, so `stack deploy`
        # errors 'invalid reference format'. Resolve here so image refs are concrete.
        # _resolve only substitutes vars PRESENT in env, so runtime shell payloads in
        # SIM_CMD ($(date), ${HOSTNAME}, $$) are left intact.
        for _ in range(6):
            nxt = {}
            for k, v in env.items():
                # leave runtime shell payloads (e.g. SIM_CMD's $(date)/${HOSTNAME}/$$) for the
                # container shell to evaluate at start — expanding them here would bake in the
                # deploy host's values (or mangle the subshell).
                nxt[k] = v if "$(" in v else self._resolve(v, env)
            if nxt == env:
                break
            env = nxt
        return env

    # ---- provisioning (terraform) -----------------------------------------
    def _provision_ec2(self, spec: FleetSpec, env: Dict[str, str]) -> str:
        """terraform apply the flat-network fleet, then emit an inventory file in
        the format _ensure_swarm expects (role ssh-target fqdn label)."""
        tfdir = env.get("TF_DIR", spec.tf_dir)
        tfvars = env.get("TF_VARS", "")
        self._run(["terraform", f"-chdir={tfdir}", "init", "-input=false"], check=True)
        apply = ["terraform", f"-chdir={tfdir}", "apply", "-input=false", "-auto-approve"]
        if tfvars:
            apply.append(f"-var-file={tfvars}")
        if spec.nodes:
            apply.append(f"-var=worker_count={spec.nodes}")
        self._run(apply, check=True)
        inv = os.path.join(tfdir, "fleet.inventory")
        out = self._run(
            ["terraform", f"-chdir={tfdir}", "output", "-raw", "inventory"],
            check=True, capture=True,
        )
        with open(inv, "w") as fh:
            fh.write(out.stdout if out else "")
        return inv

    # ---- swarm formation (ported from swarm/deploy/fleet/lib/swarm.sh) ------
    def _ensure_swarm(self, fleet: str, inventory: str, drop_path: str) -> None:
        # single host: one-node swarm on the local engine + local registry
        if fleet == "single" or not inventory:
            # explicit advertise-addr: multi-NIC hosts (tailscale+eth+wifi) otherwise
            # fail 'could not choose an address' and the node isn't a manager.
            self._run(["docker", "swarm", "init", "--advertise-addr", self._advertise_addr()],
                      check=False)
            os.makedirs(drop_path, exist_ok=True)
            self._ensure_local_registry(ssh=None)
            return

        rows = self._read_inventory(inventory)
        head = next((r for r in rows if r["role"] == "head"), None)
        if not head:
            raise ValueError(f"inventory {inventory} has no head node")

        # nodes boot async AFTER terraform apply returns — wait for cloud-init to finish
        # (docker installed, drop_path created, tailnet up) before touching the swarm, else
        # `test -d drop_path` / `docker swarm init` race the node's runcmd and fail.
        self._wait_for_nodes_ready(rows, drop_path)

        # swarm advertise-addr must be an IP, not a hostname/FQDN — use the head's
        # tailscale IP (resolved on the node) so workers join over the tailnet.
        head_ip = self._ssh(head["ssh"], "tailscale ip -4 | head -1",
                            check=True, capture=True).stdout.strip()

        # init on head, verify shared mount, label + registry
        self._ssh(head["ssh"], f"docker swarm init --advertise-addr {head_ip}", check=False)
        self._ssh(head["ssh"], f"test -d {shlex.quote(drop_path)}", check=True,
                  err=f"{head['fqdn']}: shared store {drop_path} not mounted")
        self._ssh(head["ssh"],
                  f"docker node update --label-add {head['label']} "
                  f"$(docker info -f '{{{{.Swarm.NodeID}}}}')", check=False)
        self._ensure_local_registry(ssh=head["ssh"])

        token = self._ssh(head["ssh"], "docker swarm join-token -q worker",
                          check=True, capture=True).stdout.strip()
        for r in rows:
            if r["role"] == "head":
                continue
            self._ssh(r["ssh"], f"test -d {shlex.quote(drop_path)}", check=True,
                      err=f"{r['fqdn']}: shared store {drop_path} not mounted")
            self._ssh(r["ssh"],
                      f"docker swarm join --token {token} {head_ip}:2377",
                      check=False)
            if r.get("label"):
                self._ssh(r["ssh"],
                          f"docker node update --label-add {r['label']} "
                          f"$(docker info -f '{{{{.Swarm.NodeID}}}}')", check=False)

    def _wait_for_nodes_ready(self, rows: List[Dict[str, str]], drop_path: str,
                              timeout: int = 480) -> None:
        """Block until every node finished cloud-init before the swarm is formed.
        terraform apply returns as soon as the instances exist; their cloud-init
        runcmd (docker install → mkdir drop_path → tailscale up) is still running.
        For each node: wait for SSH reachability (tailnet coming up), block on
        `cloud-init status --wait`, then confirm docker + drop_path. Raises on timeout."""
        deadline = time.time() + timeout
        for r in rows:
            target = r["ssh"]
            # 1. SSH reachability — tailnet/sshd may be seconds behind the API
            while time.time() < deadline:
                res = subprocess.run(
                    ["ssh", *self._SSH_OPTS, target, "true"],
                    check=False, capture_output=True, text=True)
                if res.returncode == 0:
                    break
                time.sleep(5)
            # 2. block until cloud-init completes (installs docker, makes drop_path)
            remaining = max(30, int(deadline - time.time()))
            subprocess.run(["ssh", *self._SSH_OPTS, target,
                            "command -v cloud-init >/dev/null && sudo cloud-init status --wait || true"],
                           check=False, capture_output=True, text=True, timeout=remaining)
            # 3. confirm the two things the swarm step needs: docker up + drop_path exists
            ready = False
            while time.time() < deadline:
                res = subprocess.run(
                    ["ssh", *self._SSH_OPTS, target,
                     f"docker info >/dev/null 2>&1 && test -d {shlex.quote(drop_path)}"],
                    check=False, capture_output=True, text=True)
                if res.returncode == 0:
                    ready = True
                    break
                time.sleep(5)
            if not ready:
                raise RuntimeError(
                    f"{r['fqdn']}: not ready (cloud-init/docker/{drop_path}) within {timeout}s")

    def _ensure_local_registry(self, ssh: Optional[str]) -> None:
        cmd = ("docker inspect registry >/dev/null 2>&1 || "
               "docker run -d --restart=always -p 5000:5000 --name registry registry:2")
        if ssh:
            self._ssh(ssh, cmd, check=False)
        else:
            self._run(["bash", "-lc", cmd], check=False)

    # ---- helpers -----------------------------------------------------------
    def _spec_from_kwargs(self, target: str, image_tag: str, kw: Dict[str, Any]) -> FleetSpec:
        project = kw.get("project")
        if not project:
            raise ValueError("swarm deploy requires --project")
        return FleetSpec(
            project=project,
            fleet=kw.get("fleet", target),
            sim=bool(kw.get("sim", False)),
            train=bool(kw.get("train", False)),
            external=bool(kw.get("external", False)),
            sim_workers=kw.get("sim_workers"),
            train_workers=kw.get("train_workers"),
            version=kw.get("version", image_tag or "latest"),
            nodes=kw.get("nodes"),
            intel_root=kw.get("intel_root", self.intel_root),
        )

    @staticmethod
    def _read_env_file(path: str) -> Dict[str, str]:
        env: Dict[str, str] = {}
        if not os.path.exists(path):
            return env
        with open(path) as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                v = v.strip()
                q = None
                if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
                    q = v[0]; v = v[1:-1]           # fully-quoted value: strip surrounding quotes
                elif v and v[0] in ("'", '"'):
                    q = v[0]                        # quoted value + trailing inline comment
                    end = v.find(q, 1)
                    v = v[1:end] if end != -1 else v[1:]
                else:
                    # unquoted: drop an inline `# comment` (shell `source` semantics), so
                    # e.g. `SIM_MEM=1g   # measured ...` yields `1g`, not the whole line.
                    h = v.find(" #")
                    if h == -1:
                        h = v.find("\t#")
                    if h != -1:
                        v = v[:h].strip()
                if q == '"':
                    # shell double-quote UNESCAPING (\$ \" \` \\): these files are written for
                    # `source`, which unescapes them. Without this, SIM_CMD's `\$(date +%s)`
                    # reaches the container shell with a literal backslash and dash errors
                    # 'Syntax error: "(" unexpected'. Single-quoted values are literal → skip.
                    out, i = [], 0
                    while i < len(v):
                        if v[i] == "\\" and i + 1 < len(v) and v[i + 1] in '$`"\\':
                            out.append(v[i + 1]); i += 2
                        else:
                            out.append(v[i]); i += 1
                    v = "".join(out)
                env[k.strip()] = v
        return env

    @staticmethod
    def _read_inventory(path: str) -> List[Dict[str, str]]:
        rows: List[Dict[str, str]] = []
        with open(path) as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                if len(parts) < 3:
                    continue
                rows.append({
                    "role": parts[0], "ssh": parts[1], "fqdn": parts[2],
                    "label": parts[3] if len(parts) > 3 else "",
                })
        return rows

    def _run(self, cmd: List[str], env: Optional[Dict[str, str]] = None,
             check: bool = True, capture: bool = False):
        try:
            return subprocess.run(
                cmd, env=env, check=check,
                capture_output=capture, text=True,
            )
        except FileNotFoundError as e:
            if check:
                raise
            # missing binary (docker/tailscale/terraform not on PATH) -> synthetic
            # failed result so check=False callers (preflight/health/advertise) degrade.
            return subprocess.CompletedProcess(cmd, 127, stdout="", stderr=str(e))

    # fresh cloud nodes have unknown host keys; accept-new adds them without an
    # interactive prompt (bare ssh would fail host-key verification), BatchMode keeps
    # everything non-interactive. Ephemeral tailnet nodes reached by name/IP.
    _SSH_OPTS = ["-o", "ConnectTimeout=10", "-o", "StrictHostKeyChecking=accept-new",
                 "-o", "BatchMode=yes"]

    def _ssh(self, target: str, remote_cmd: str, check: bool = True,
             capture: bool = False, err: Optional[str] = None):
        res = subprocess.run(
            ["ssh", *self._SSH_OPTS, target, remote_cmd],
            check=False, capture_output=True, text=True,
        )
        if check and res.returncode != 0:
            raise RuntimeError(err or f"ssh {target} failed: {res.stderr.strip()}")
        return res
