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
# SEGA MODULE - K8s Fleet Deployer (Plane 1 — product serving)
# ===============================================================
# File: src/sega/ship/deployers/k8s_fleet.py
# Purpose: Provision a multi-node k3s cluster on EC2 (tailnet-only, no inbound),
#          form it with tailscale-join, and deploy a project's serving stack via
#          the fleet-standard fleet-project Helm chart. The Plane-1 (Kubernetes)
#          analogue of swarm_deployer.py (Plane-2, Docker Swarm).
#
# DRAFT (2026-07-31): NOT yet test-run — mirrors two PROVEN references:
#   - swarm_deployer.py (the sibling contract: provision -> form -> deploy,
#     safe-by-default teardown with --destroy gated by --yes), and
#   - lab/orchestration/k8s/setup/{control-up,node-launch,install_k3s_*,
#     fetch-kubeconfig}.sh (the k3s+tailscale bootstrap proven in Phase-1).
#   The bootstrap scripts below are ported VERBATIM from those lab scripts so
#   sega owns the logic self-contained (no sega->lab dependency), exactly as
#   swarm_deployer ported swarm.sh. Verify with `deploy(..., dry_run=True)` then
#   a real run on an idle host before adoption.
#
# Ownership boundary (mirrors the swarm contract):
#   - the PROJECT owns its image (built by forge from backend/Dockerfile.slim)
#     and its Helm values (infrastructure/helm/fleet-project/values-<project>.yaml).
#   - sega OWNS getting a cluster onto infrastructure and running the stack:
#     account scaffolding, node provisioning, tailscale-join, cluster formation,
#     kubeconfig, KEDA, helm deploy, and teardown.
#
# Two axes, same shape as swarm:
#   workload -> --sim-nodes N (KEDA still scales worker pods 0..N within the pool)
#   fleet    -> ec2-k3s (now) | eks (later, via terraform modules/eks)
# ===============================================================

import os
import subprocess
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List

from ...core.deployment_result import DeploymentResult
from .base_deployer import BaseDeployer

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
# sega/infrastructure/helm/fleet-project — the fleet-standard chart (values-<proj>.yaml)
DEFAULT_HELM_CHART = os.path.abspath(
    os.path.join(_THIS_DIR, "..", "..", "..", "..",
                 "infrastructure", "helm", "fleet-project")
)
DEFAULT_KEYS_DIR = os.path.expanduser(os.environ.get("FLEET_KEYS_DIR", "~/fleet/keys"))

# --- ported bootstrap: k3s control-plane (from install_k3s_server.sh) ----------
# Prepended env header supplies TS_AUTHKEY / K3S_TOKEN / NODE_NAME.
BOOTSTRAP_SERVER = r"""
set -euxo pipefail
if ! command -v tailscale >/dev/null 2>&1; then
  curl -fsSL https://tailscale.com/install.sh | sh
fi
if ! tailscale status >/dev/null 2>&1; then
  tailscale up --authkey="${TS_AUTHKEY}" --hostname="${NODE_NAME}"
fi
TS_IP=$(tailscale ip -4 | head -1)
if ! systemctl is-active --quiet k3s 2>/dev/null; then
  curl -sfL https://get.k3s.io | K3S_TOKEN="${K3S_TOKEN}" sh -s - server \
    --node-name "${NODE_NAME}" --node-ip "${TS_IP}" --advertise-address "${TS_IP}" \
    --flannel-iface tailscale0 --tls-san "${NODE_NAME}" --tls-san "${TS_IP}" \
    --node-taint "node-role.fleet/control=true:NoSchedule" --write-kubeconfig-mode 644
fi
for i in $(seq 1 60); do k3s kubectl get --raw /readyz >/dev/null 2>&1 && break; sleep 5; done
"""

# --- ported bootstrap: k3s sim node / agent (from install_k3s_agent.sh) ---------
# Prepended env header supplies TS_AUTHKEY / K3S_TOKEN / K3S_URL / NODE_NAME.
BOOTSTRAP_AGENT = r"""
set -euxo pipefail
# clear any inherited tailscale identity (a baked-AMI clone would otherwise reuse the
# source node's node key and collide) then join fresh under this node's hostname.
systemctl stop tailscaled 2>/dev/null || true
rm -f /var/lib/tailscale/tailscaled.state 2>/dev/null || true
if ! command -v tailscale >/dev/null 2>&1; then
  curl -fsSL https://tailscale.com/install.sh | sh
fi
systemctl start tailscaled 2>/dev/null || true
sleep 2
tailscale up --authkey="${TS_AUTHKEY}" --hostname="${NODE_NAME}"
TS_IP=$(tailscale ip -4 | head -1)
# clear inherited k3s cluster-join identity (a baked-AMI clone carries the build
# cluster's node password + CA and can't join the new control) — but KEEP the
# containerd image store (the whole point of the bake).
systemctl stop k3s-agent 2>/dev/null || true
find /var/lib/rancher/k3s/agent -mindepth 1 -maxdepth 1 ! -name containerd -exec rm -rf {} + 2>/dev/null || true
rm -rf /etc/rancher/node 2>/dev/null || true
if ! systemctl is-active --quiet k3s-agent 2>/dev/null; then
  curl -sfL https://get.k3s.io | K3S_URL="${K3S_URL}" K3S_TOKEN="${K3S_TOKEN}" sh -s - agent \
    --node-name "${NODE_NAME}" --node-ip "${TS_IP}" --flannel-iface tailscale0 \
    --node-label "node-role.fleet/sim=true"
fi
"""

# Build node = a sim agent + docker/git/rsync + buildx, for the in-region build+bake.
BOOTSTRAP_BUILD_SIM = BOOTSTRAP_AGENT + r"""
export DEBIAN_FRONTEND=noninteractive
apt-get update -y && apt-get install -y docker.io git rsync
systemctl enable --now docker
usermod -aG docker ubuntu || true
# buildx plugin — Ubuntu's docker.io ships no buildx, but Dockerfile.slim needs
# BuildKit (`--mount=type=cache`); docker 29 requires the buildx CLI for BuildKit.
mkdir -p /usr/libexec/docker/cli-plugins
curl -fsSL https://github.com/docker/buildx/releases/download/v0.18.0/buildx-v0.18.0.linux-amd64 \
  -o /usr/libexec/docker/cli-plugins/docker-buildx && chmod +x /usr/libexec/docker/cli-plugins/docker-buildx
"""


@dataclass
class K8sFleetSpec:
    """One deploy request: which project, how many sim nodes, which fleet."""

    project: str
    fleet: str = "ec2-k3s"                 # ec2-k3s (now) | eks (later)
    region: str = os.environ.get("AWS_REGION", "us-east-1")
    sim_nodes: int = 2
    # arch selects BOTH the Ubuntu AMI and (when the types below are left None) the
    # default instance family. arm64/t4g is the default/prod target (cheaper, 1 vCPU
    # = 1 physical core); amd64/t3 is for images built on an x86_64 host (e.g. node-5).
    # All overridable — nothing here is a one-way door.
    arch: str = "arm64"                    # arm64 | amd64
    control_type: Optional[str] = None     # None => per-arch default (_ARCH_TYPES)
    # sim nodes also host the in-cluster DB tier (TimescaleDB + backend + redis) for
    # the test, since control is tainted — so the default is a ~4 GB size. Prod
    # separates baseline vs compute node groups; the brief k3s test packs one size.
    sim_type: Optional[str] = None         # None => per-arch default
    root_vol_gb: int = 16
    version: str = "latest"
    ttl_minutes: int = 90   # TTL self-terminate backstop (Plane-2 pattern): nodes
                            # self-halt -> terminate after N min even if teardown is
                            # forgotten or the orchestrator dies. 0 = disable.
    spot: bool = False      # spot for the sim pool (Plane-2 test convention). Default
                            # OFF here: the brief-test topology packs the in-cluster DB
                            # onto sim nodes, and a spot reclaim would kill it. Safe to
                            # enable once the DB has its own on-demand baseline node.
    use_ebs: bool = True    # False => skip node IAM profile + EBS CSI, use k3s local-path
    # image delivery: 'sideload' streams the image to each node (slow over a home
    # uplink, one-time per cluster); 'baked-ami' launches nodes from an AMI that
    # already carries tailscale+k3s+the image -> ~90s time-to-serving, no sideload
    # (the responsive-scaling path). Bake once with bake_ami(), then reuse.
    image_delivery: str = "sideload"       # sideload | baked-ami
    builder_type: str = "c6i.xlarge"       # in-region build/bake host (4 vCPU, fast)
    keys_dir: str = DEFAULT_KEYS_DIR
    helm_chart: str = DEFAULT_HELM_CHART
    extra_values_files: List[str] = field(default_factory=list)  # extra helm `-f` overlays
    helm_set: Dict[str, str] = field(default_factory=dict)        # extra helm `--set k=v`
    sideload_images: List[str] = field(default_factory=list)      # local images -> ctr-import to sim nodes
    extra_env: Dict[str, str] = field(default_factory=dict)

    # Per-project resource names so multiple project fleets never collide, and
    # so sega's teardown can never touch the lab's fleet-k8s-test resources.
    # per-arch default instance families (control ~2 GB; sim ~4 GB for the DB tier)
    _ARCH_TYPES = {"arm64": ("t4g.small", "t4g.medium"),
                   "amd64": ("t3.small", "t3.medium")}

    @property
    def control_instance(self) -> str:
        return self.control_type or self._ARCH_TYPES[self.arch][0]

    @property
    def sim_instance(self) -> str:
        return self.sim_type or self._ARCH_TYPES[self.arch][1]

    @property
    def tag(self) -> str: return f"sega-k8s-{self.project}"
    @property
    def control_name(self) -> str: return f"{self.tag}-control"
    @property
    def sim_prefix(self) -> str: return f"{self.tag}-sim"
    @property
    def key_name(self) -> str: return self.tag
    @property
    def sg_name(self) -> str: return f"{self.tag}-sg"
    @property
    def role_name(self) -> str: return f"{self.tag}-node-role"
    @property
    def profile_name(self) -> str: return f"{self.tag}-node-profile"
    @property
    def baked_ami_name(self) -> str: return f"{self.tag}-baked-{self.arch}"

    @property
    def kube_context(self) -> str: return f"sega-{self.project}"
    @property
    def namespace(self) -> str: return self.project
    @property
    def ts_authkey_file(self) -> str: return os.path.join(self.keys_dir, "tailscale-authkey")
    @property
    def k3s_token_file(self) -> str: return os.path.join(self.keys_dir, f"{self.tag}-k3s-token")
    @property
    def ssh_key_file(self) -> str: return os.path.join(self.keys_dir, f"{self.key_name}.pem")
    @property
    def values_file(self) -> str:
        return os.path.join(self.helm_chart, f"values-{self.project}.yaml")


class K8sFleetDeployer(BaseDeployer):
    """Provision + tailscale-join + form a k3s fleet, then helm-deploy the
    project. Plane-1 sibling of SwarmDeployer."""

    def __init__(self):
        super().__init__()

    # ---- BaseDeployer interface -------------------------------------------
    def deploy(self, target: str, strategy: str = "rolling", image_tag: str = "latest",
               force: bool = False, dry_run: bool = False, **kwargs: Any) -> DeploymentResult:
        """`target` doubles as the fleet name; project + sizing arrive via kwargs
        so the generic router can drive this without a bespoke signature."""
        try:
            spec = self._spec_from_kwargs(target, image_tag, kwargs)
        except ValueError as e:
            return self._create_deployment_result(False, str(e), error=str(e))
        return self.deploy_fleet(spec, dry_run=dry_run)

    def get_deployment_status(self, target: str) -> Dict[str, Any]:
        spec = K8sFleetSpec(project=target)
        out = self._run(["kubectl", "--context", spec.kube_context, "-n", spec.namespace,
                         "get", "pods", "-o", "wide"], check=False, capture=True)
        return {"context": spec.kube_context, "pods": out.stdout if out else ""}

    def rollback(self, target: str, to_version: Optional[str] = None) -> DeploymentResult:
        spec = K8sFleetSpec(project=target)
        self._run(["helm", "--kube-context", spec.kube_context, "-n", spec.namespace,
                   "rollback", spec.project], check=False)
        return self._create_deployment_result(True, f"helm rollback {spec.project}")

    # ---- fleet orchestration (mirrors SwarmDeployer.deploy_fleet) ----------
    def deploy_fleet(self, spec: K8sFleetSpec, dry_run: bool = False) -> DeploymentResult:
        """provision -> tailscale-join/form -> kubeconfig -> KEDA -> helm deploy."""
        if spec.fleet == "eks":
            return self._create_deployment_result(
                False, "fleet=eks not wired yet — use terraform modules/eks then "
                "point --context at it; this deployer handles fleet=ec2-k3s.",
                error="eks path pending")

        for p in (spec.ts_authkey_file,):
            if not os.path.exists(p):
                msg = f"missing tailscale auth key: {p} (put the admin-console key there)"
                return self._create_deployment_result(False, msg, error=msg)
        if not os.path.exists(spec.values_file):
            msg = f"missing helm values for project: {spec.values_file}"
            return self._create_deployment_result(False, msg, error=msg)

        if dry_run:
            plan = self._plan(spec)
            return self._create_deployment_result(True, "dry-run: provisioning plan",
                                                   metadata={"plan": plan})

        self._preflight(spec)                            # 0. fail fast BEFORE any EC2 spend
        control_ip = self.provision_fleet(spec)          # 1. nodes + tailscale-join + k3s
        self.fetch_kubeconfig(spec, control_ip)          # 2. kubeconfig -> local context
        self._sideload_images(spec)                      # 3. ctr-import local images (no ECR)
        if spec.use_ebs:
            self._install_ebs_csi(spec)                  # 4. EBS CSI + gp3 SC (D4 TimescaleDB PVs)
        self._install_keda(spec)                         # 5. KEDA (queue-depth autoscaler)
        return self._deploy_app(spec)                    # 6. helm upgrade --install

    def deploy_test(self, spec: K8sFleetSpec, hold_seconds: int = 600,
                    keep: bool = False) -> DeploymentResult:
        """Automated smoke: provision+deploy -> hold -> teardown in a `finally`
        (Plane-2 `swarm-test` pattern), so the fleet is torn down even if deploy or
        hold raises. The TTL self-terminate (spec.ttl_minutes) is the second
        backstop — survives the orchestrator/laptop dying. `--keep` leaves it up and
        relies on the TTL alone. Exposed as `sega ship k8s-test` (cf. swarm-test)."""
        try:
            result = self.deploy_fleet(spec)
            self._run(["sleep", str(hold_seconds)], check=False)  # hold only on success
            return result
        finally:
            if not keep:
                self.teardown(spec, destroy_infra=True, yes=True)

    # ---- provisioning (ported from control-up.sh + node-launch.sh) ---------
    def provision_fleet(self, spec: K8sFleetSpec) -> str:
        """Create account scaffolding, launch the control node + N sim nodes, each
        joining the tailnet at boot. Returns the control node's tailnet IP.
        Idempotent: existing nodes/scaffolding are reused."""
        self._ensure_token(spec)
        sg_id = self._ensure_scaffolding(spec)
        if not self._instance_id(spec, spec.control_name):
            self._launch_control(spec, sg_id)
        control_ip = self._wait_api(spec)
        existing = self._sim_count(spec)
        for i in range(existing, spec.sim_nodes):
            self._launch_sim(spec, sg_id, control_ip, i)
        return control_ip

    def teardown(self, spec: K8sFleetSpec, destroy_infra: bool = False,
                 yes: bool = False) -> DeploymentResult:
        """Safe-by-default, mirroring SwarmDeployer.teardown:

        - default: `helm uninstall` only — removes the WORKLOAD, keeps the
          cluster + nodes so a re-deploy is instant. Reversible.
        - `--destroy`: also terminate every instance tagged Project=<spec.tag>
          and delete the SG/keypair/IAM. Gated behind `--yes`; without it we only
          LIST what would be terminated so nothing dies by accident.
        """
        self._run(["helm", "--kube-context", spec.kube_context, "-n", spec.namespace,
                   "uninstall", spec.project], check=False)
        if not destroy_infra:
            return self._create_deployment_result(True, f"{spec.project}: workload removed; cluster retained")

        iids = self._instances_by_tag(spec)
        if not yes:
            return self._create_deployment_result(
                True, f"{spec.project}: PREVIEW only — re-run with --yes to terminate "
                f"{len(iids)} instance(s): {' '.join(iids) or '(none)'}. Nothing destroyed.")
        if iids:
            self._aws(spec, ["ec2", "terminate-instances", "--instance-ids", *iids])
            self._aws(spec, ["ec2", "wait", "instance-terminated", "--instance-ids", *iids])
        self._delete_scaffolding(spec)
        leak = self._residue_sweep(spec)
        return self._create_deployment_result(
            not leak, f"{spec.project}: fleet destroyed" + (" (RESIDUE FOUND)" if leak else ""))

    def decommission_idle(self, spec: K8sFleetSpec, min_keep: int = 0,
                          dry_run: bool = False) -> DeploymentResult:
        """Node-level scale-DOWN — the decommission half of dynamic management.

        KEDA drains worker pods to 0 in seconds once the Redis ZSET (pending-sim
        depth) empties; the NODES that carried them must then follow so idle
        capacity stops billing. For each sim node running zero application pods:
        cordon → drain (daemonsets tolerated) → delete the k8s node → terminate
        the EC2 instance. Keeps `min_keep` warmest sim nodes so a fresh burst
        still lands on warm capacity. dry_run only reports what would go."""
        sim_ids = self._instances_by_tag(spec, role="sim-node")
        idle: List[tuple] = []
        for iid in sim_ids:
            name = self._aws(spec, ["ec2", "describe-instances", "--instance-ids", iid,
                                    "--query", "Reservations[].Instances[].Tags[?Key=='Name']|[0][0].Value",
                                    "--output", "text"], check=False, capture=True).stdout.strip()
            # count non-terminating app pods bound to this node in the app namespace
            pods = self._run(["kubectl", "--context", spec.kube_context, "-n", spec.namespace,
                              "get", "pods", "--field-selector",
                              f"spec.nodeName={name},status.phase!=Succeeded,status.phase!=Failed",
                              "--no-headers"], check=False, capture=True).stdout.strip()
            n = len([ln for ln in pods.splitlines() if ln.strip()])
            if n == 0:
                idle.append((iid, name))
        keep = idle[:min_keep]
        kill = idle[min_keep:]
        if dry_run or not kill:
            return self._create_deployment_result(
                True, f"{spec.project}: idle sim nodes={len(idle)} keep={len(keep)} "
                f"would-decommission={[n for _, n in kill] or '(none)'}")
        for iid, name in kill:
            self._run(["kubectl", "--context", spec.kube_context, "cordon", name], check=False)
            self._run(["kubectl", "--context", spec.kube_context, "drain", name,
                       "--ignore-daemonsets", "--delete-emptydir-data", "--force",
                       "--timeout=60s"], check=False)
            self._run(["kubectl", "--context", spec.kube_context, "delete", "node", name], check=False)
            self._aws(spec, ["ec2", "terminate-instances", "--instance-ids", iid])
        return self._create_deployment_result(
            True, f"{spec.project}: decommissioned {len(kill)} idle sim node(s): "
            f"{[n for _, n in kill]}; {len(keep)} kept warm")

    # ---- steps -------------------------------------------------------------
    def _ensure_token(self, spec: K8sFleetSpec) -> None:
        os.makedirs(spec.keys_dir, exist_ok=True)
        if not os.path.exists(spec.k3s_token_file):
            tok = self._run(["openssl", "rand", "-hex", "24"], capture=True).stdout.strip()
            with open(spec.k3s_token_file, "w") as fh:
                fh.write(tok)
            os.chmod(spec.k3s_token_file, 0o600)

    def _ensure_scaffolding(self, spec: K8sFleetSpec) -> str:
        """keypair + zero-inbound SG + IAM role/profile (ECR pull + SSM break-glass)."""
        if self._aws(spec, ["ec2", "describe-key-pairs", "--key-names", spec.key_name],
                     check=False).returncode != 0:
            out = self._aws(spec, [
                "ec2", "create-key-pair", "--key-name", spec.key_name,
                "--tag-specifications", self._tagspec(spec, "key-pair"),
                "--query", "KeyMaterial", "--output", "text"], capture=True)
            with open(spec.ssh_key_file, "w") as fh:
                fh.write(out.stdout)
            os.chmod(spec.ssh_key_file, 0o600)

        sg_id = self._aws(spec, [
            "ec2", "describe-security-groups", "--filters", f"Name=group-name,Values={spec.sg_name}",
            "--query", "SecurityGroups[0].GroupId", "--output", "text"], check=False, capture=True).stdout.strip()
        if sg_id in ("", "None"):
            vpc = self._aws(spec, ["ec2", "describe-vpcs", "--filters", "Name=is-default,Values=true",
                                   "--query", "Vpcs[0].VpcId", "--output", "text"], capture=True).stdout.strip()
            sg_id = self._aws(spec, [
                "ec2", "create-security-group", "--group-name", spec.sg_name,
                "--description", "sega k8s fleet - no inbound, tailnet only", "--vpc-id", vpc,
                "--tag-specifications", self._tagspec(spec, "security-group"),
                "--query", "GroupId", "--output", "text"], capture=True).stdout.strip()

        # The node IAM role/instance-profile exists ONLY to give the EBS CSI driver
        # node creds (D4). We sideload images (no ECR) and SSM is optional, so when
        # EBS is off we skip it — which also sidesteps needing iam:CreateRole.
        if spec.use_ebs:
            if self._aws(spec, ["iam", "get-role", "--role-name", spec.role_name], check=False).returncode != 0:
                trust = ('{"Version":"2012-10-17","Statement":[{"Effect":"Allow",'
                         '"Principal":{"Service":"ec2.amazonaws.com"},"Action":"sts:AssumeRole"}]}')
                self._aws(spec, ["iam", "create-role", "--role-name", spec.role_name,
                                 "--assume-role-policy-document", trust])
                for arn in ("arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly",
                            "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore",
                            "arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy"):
                    self._aws(spec, ["iam", "attach-role-policy", "--role-name", spec.role_name,
                                     "--policy-arn", arn])
            if self._aws(spec, ["iam", "get-instance-profile", "--instance-profile-name", spec.profile_name],
                         check=False).returncode != 0:
                self._aws(spec, ["iam", "create-instance-profile", "--instance-profile-name", spec.profile_name])
                self._aws(spec, ["iam", "add-role-to-instance-profile",
                                 "--instance-profile-name", spec.profile_name, "--role-name", spec.role_name])
                self._run(["sleep", "10"], check=False)  # IAM propagation before run-instances
        return sg_id

    def _launch_control(self, spec: K8sFleetSpec, sg_id: str) -> None:
        header = {"TS_AUTHKEY": self._read(spec.ts_authkey_file),
                  "K3S_TOKEN": self._read(spec.k3s_token_file),
                  "NODE_NAME": spec.control_name}
        self._run_instance(spec, sg_id, spec.control_name, "control",
                           spec.control_instance,
                           self._user_data(header, BOOTSTRAP_SERVER, spec.ttl_minutes))

    def _launch_sim(self, spec: K8sFleetSpec, sg_id: str, control_ip: str, idx: int) -> None:
        name = f"{spec.sim_prefix}-{idx}"
        header = {"TS_AUTHKEY": self._read(spec.ts_authkey_file),
                  "K3S_TOKEN": self._read(spec.k3s_token_file),
                  "K3S_URL": f"https://{control_ip}:6443",
                  "NODE_NAME": name}
        self._run_instance(spec, sg_id, name, "sim-node",
                           spec.sim_instance,
                           self._user_data(header, BOOTSTRAP_AGENT, spec.ttl_minutes))

    def _run_instance(self, spec: K8sFleetSpec, sg_id: str, name: str, role: str,
                      itype: str, user_data: str) -> None:
        ami = self._resolve_ami(spec, role)
        tags = (f"ResourceType=instance,Tags=[{{Key=Name,Value={name}}},"
                f"{{Key=Project,Value={spec.tag}}},{{Key=Role,Value={role}}}]")
        args = [
            "ec2", "run-instances", "--image-id", ami, "--instance-type", itype,
            "--key-name", spec.key_name, "--security-group-ids", sg_id,
            "--user-data", user_data,
            # halt (from the user-data TTL) TERMINATES rather than stops -> no stray EBS.
            "--instance-initiated-shutdown-behavior", "terminate",
            "--tag-specifications", tags,
        ]
        # A baked AMI carries its own (larger) root volume — don't override the
        # block-device-mapping (can't shrink below the AMI snapshot size). Stock AMI
        # nodes get an explicit gp3 root.
        baked = spec.image_delivery == "baked-ami" and role != "control"
        if not baked:
            args += ["--block-device-mappings",
                     f'[{{"DeviceName":"/dev/sda1","Ebs":{{"VolumeSize":{spec.root_vol_gb},'
                     f'"VolumeType":"gp3","DeleteOnTermination":true}}}}]']
        if spec.use_ebs:                                 # instance profile = EBS CSI node creds
            args += ["--iam-instance-profile", f"Name={spec.profile_name}"]
        # Spot only for the stateless sim pool, only when opted in — never control,
        # and unsafe while the DB shares a sim node (see spec.spot).
        if spec.spot and role == "sim-node":
            args += ["--instance-market-options", "MarketType=spot"]
        args += ["--query", "Instances[0].InstanceId", "--output", "text"]
        self._aws(spec, args, capture=True)

    def fetch_kubeconfig(self, spec: K8sFleetSpec, control_ip: str) -> None:
        """Pull the k3s kubeconfig, rewrite 127.0.0.1 -> tailnet IP and the
        context name, merge into ~/.kube/config. (Python string-replace instead
        of `sed -i ''` so it's not macOS-specific.)"""
        raw = self._ssh(spec, control_ip, "sudo cat /etc/rancher/k3s/k3s.yaml", capture=True).stdout
        raw = raw.replace("https://127.0.0.1:6443", f"https://{control_ip}:6443")
        raw = raw.replace(": default", f": {spec.kube_context}")
        kube = os.path.expanduser("~/.kube/config")
        os.makedirs(os.path.dirname(kube), exist_ok=True)
        tmp = kube + f".{spec.project}.tmp"
        with open(tmp, "w") as fh:
            fh.write(raw)
        if os.path.exists(kube):
            # NEW config first so a fresh control IP overrides a stale same-named
            # context (kubectl merge: first file wins on key conflicts).
            merged = self._run(["kubectl", "config", "view", "--flatten"], capture=True,
                               env={**os.environ, "KUBECONFIG": f"{tmp}:{kube}"}).stdout
            with open(kube, "w") as fh:
                fh.write(merged)
            os.remove(tmp)
        else:
            os.replace(tmp, kube)
        os.chmod(kube, 0o600)
        self._run(["kubectl", "config", "use-context", spec.kube_context], check=False)

    def _sideload_images(self, spec: K8sFleetSpec) -> None:
        """`docker save` the local images and stream them into each sim node's k3s
        containerd (no registry — the ECR-push-of-2.6GB path that died in Phase-1).
        Only sim nodes: control is tainted, app pods never land there."""
        if spec.image_delivery == "baked-ami":
            return  # image already on disk (in the AMI) — nothing to stream
        if not spec.sideload_images:
            return
        tar = f"/tmp/sideload-{spec.tag}.tar"
        self._run(["docker", "save", *spec.sideload_images, "-o", tar], check=True)
        probe = spec.sideload_images[0].split(":")[0]
        for i in range(spec.sim_nodes):
            # WAIT for the sim node to be on the tailnet + ssh-reachable before
            # streaming. provision_fleet launches sims but does NOT block on their
            # boot, so a one-shot _ts_ip here races the node's tailscale-join and
            # silently skips it — leaving the node imageless → ImagePullBackOff.
            ip = self._wait_ssh(spec, f"{spec.sim_prefix}-{i}")
            # WAIT for k3s containerd to be up before touching `k3s ctr`. _wait_ssh
            # only proves the node is SSH-reachable, NOT that the k3s agent started
            # containerd. Importing before the socket exists fails with "cannot access
            # socket /run/k3s/containerd/containerd.sock" and — because the import ran
            # with check=False — was silently swallowed, leaving the node imageless →
            # every app pod ImagePullBackOff → helm --wait times out (2026-08-01).
            # Mirror the baked path's readiness gate (see _user_data, ~line 728).
            self._ssh(spec, ip,
                      "for _ in $(seq 1 60); do sudo k3s ctr version >/dev/null 2>&1 && exit 0; sleep 5; done; exit 1",
                      check=False)
            # skip nodes that already have it — redeploys shouldn't re-stream ~1 GB.
            have = self._ssh(spec, ip,
                             f"sudo k3s ctr -n k8s.io images ls -q 2>/dev/null | grep -c {probe} || true",
                             check=False, capture=True).stdout.strip()
            if have not in ("", "0"):
                continue
            with open(tar, "rb") as fh:
                # -n k8s.io: the containerd namespace kubelet reads (NOT the default ns).
                subprocess.run(
                    ["ssh", "-i", spec.ssh_key_file, "-o", "StrictHostKeyChecking=accept-new",
                     "-o", "ConnectTimeout=20", f"ubuntu@{ip}", "sudo k3s ctr -n k8s.io images import -"],
                    stdin=fh, check=False)
            # VERIFY the import landed — the stream ran check=False, so a socket race
            # or truncated stream would otherwise surface only later as ImagePullBackOff.
            got = self._ssh(spec, ip,
                            f"sudo k3s ctr -n k8s.io images ls -q 2>/dev/null | grep -c {probe} || true",
                            check=False, capture=True).stdout.strip()
            if got in ("", "0"):
                raise RuntimeError(
                    f"sideload FAILED: '{probe}' not in containerd on {spec.sim_prefix}-{i} "
                    "after import (k3s containerd not ready, or stream truncated)")

    def _install_ebs_csi(self, spec: K8sFleetSpec) -> None:
        """Install the AWS EBS CSI driver + a `gp3` StorageClass so the D4
        TimescaleDB StatefulSet gets a real gp3 PV (k3s ships only local-path).
        The driver authenticates via the node instance-profile (EBS policy
        attached in _ensure_scaffolding)."""
        self._run(["helm", "repo", "add", "aws-ebs-csi-driver",
                   "https://kubernetes-sigs.github.io/aws-ebs-csi-driver"], check=False)
        self._run(["helm", "repo", "update"], check=False)
        self._run(["helm", "--kube-context", spec.kube_context, "upgrade", "--install",
                   "aws-ebs-csi-driver", "aws-ebs-csi-driver/aws-ebs-csi-driver",
                   "--namespace", "kube-system"], check=False)
        gp3 = ("apiVersion: storage.k8s.io/v1\nkind: StorageClass\n"
               "metadata:\n  name: gp3\nprovisioner: ebs.csi.aws.com\n"
               "volumeBindingMode: WaitForFirstConsumer\nparameters:\n  type: gp3\n")
        subprocess.run(["kubectl", "--context", spec.kube_context, "apply", "-f", "-"],
                       input=gp3, text=True, check=False)

    def _install_keda(self, spec: K8sFleetSpec) -> None:
        # KEDA must tolerate the control taint (lab F1): it's the scale-from-zero
        # controller, so it can't live on elastic sim nodes.
        #
        # RETRY the whole install: the chart download from kedacore.github.io fetches
        # over IPv6 and intermittently `connection reset by peer` (same class as the
        # gitlab-IPv6 flake). It ran check=False, so a reset silently left KEDA
        # UNINSTALLED → the app chart's ScaledObject apply then failed ("helm deploy
        # failed") with no obvious cause (2026-08-03). Retry until the release is
        # actually deployed; only then return. (Future: pre-bake the chart into the AMI
        # so no network fetch happens at deploy — noted in lab k8s STATUS.)
        self._run(["helm", "repo", "add", "kedacore", "https://kedacore.github.io/charts"], check=False)
        last = None
        for attempt in range(1, 5):                       # up to 4 tries
            self._run(["helm", "repo", "update", "kedacore"], check=False)
            r = self._run(["helm", "--kube-context", spec.kube_context, "upgrade", "--install",
                           "keda", "kedacore/keda", "--namespace", "keda", "--create-namespace",
                           "--wait", "--timeout", "5m",
                           "--set", "tolerations[0].key=node-role.fleet/control",
                           "--set", "tolerations[0].operator=Exists",
                           "--set", "tolerations[0].effect=NoSchedule"],
                          check=False, capture=True)
            if r.returncode == 0:
                return
            last = (r.stderr or r.stdout or "")[-300:]
            print(f"KEDA install attempt {attempt}/4 failed (retrying): {last}")
            self._run(["sleep", str(10 * attempt)], check=False)   # backoff: 10s,20s,30s
        # Exhausted retries — surface it instead of limping into a confusing
        # ScaledObject-apply failure downstream.
        raise RuntimeError(f"KEDA install failed after 4 attempts: {last}")

    def _deploy_app(self, spec: K8sFleetSpec) -> DeploymentResult:
        """helm upgrade --install against the fleet-standard fleet-project chart with
        the project's values file. (This is the chart k8s_deployer.py should also
        target — it currently points at the stale `sega-app` path; converge there.)"""
        # shared value flags for both the render-check and the real upgrade
        vals = ["-f", spec.values_file]
        for f in spec.extra_values_files:                # test overlay layers on top
            vals += ["-f", f]
        vals += ["--set", f"image.tag={spec.version}"]
        for k, v in spec.helm_set.items():               # secret data etc. (not in files)
            vals += ["--set", f"{k}={v}"]

        # GATE: validate the chart RENDERS before applying — catches template bugs
        # (ternary-on-string, replicas 0->1, command-vs-args, doc-separator) at zero
        # cost instead of mid-cluster. Every bug this run hit would've tripped here.
        chk = self._run(["helm", "template", spec.project, spec.helm_chart, *vals],
                        check=False, capture=True)
        if chk.returncode != 0:
            return self._create_deployment_result(False, "chart render failed (nothing applied)",
                                                  error=(chk.stderr or "")[:2000])

        # RECOVERY: a prior aborted deploy can leave the release pending/failed, which
        # makes `upgrade` error. Uninstall a wedged release first so re-runs are clean.
        st = self._run(["helm", "--kube-context", spec.kube_context, "-n", spec.namespace,
                        "status", spec.project], check=False, capture=True)
        if st.returncode == 0 and any(s in (st.stdout or "") for s in ("pending-", "failed")):
            self._run(["helm", "--kube-context", spec.kube_context, "-n", spec.namespace,
                       "uninstall", spec.project], check=False)

        cmd = ["helm", "--kube-context", spec.kube_context, "upgrade", "--install",
               spec.project, spec.helm_chart, *vals,
               "--namespace", spec.namespace, "--create-namespace",
               "--wait", "--timeout=10m"]
        r = self._run(cmd, check=False, capture=True)
        if r.returncode != 0:
            return self._create_deployment_result(False, "helm deploy failed",
                                                  error=(r.stderr or "")[:2000])
        return self._create_deployment_result(
            True, f"deployed {spec.project} on {spec.fleet} ({spec.sim_nodes} sim nodes)",
            metadata=self.get_deployment_status(spec.project))

    # ---- waits + queries ---------------------------------------------------
    def _wait_api(self, spec: K8sFleetSpec, tries: int = 60) -> str:
        self._aws(spec, ["ec2", "wait", "instance-running", "--instance-ids",
                         *self._instances_by_tag(spec, role="control")], check=False)
        for _ in range(tries):
            ip = self._ts_ip(spec.control_name)
            if ip and self._port_open(ip, 6443):
                return ip
            self._run(["sleep", "10"], check=False)
        raise RuntimeError(f"control node {spec.control_name} never reached API on the tailnet")

    @staticmethod
    def _port_open(ip: str, port: int, timeout: float = 3.0) -> bool:
        # portable (nc's -G/-w flags differ across BSD/Linux; sockets don't)
        import socket
        try:
            with socket.create_connection((ip, int(port)), timeout=timeout):
                return True
        except OSError:
            return False

    def _sim_count(self, spec: K8sFleetSpec) -> int:
        return len(self._instances_by_tag(spec, role="sim-node"))

    def _instance_id(self, spec: K8sFleetSpec, name: str) -> str:
        return self._aws(spec, [
            "ec2", "describe-instances",
            "--filters", f"Name=tag:Name,Values={name}",
            "Name=instance-state-name,Values=pending,running",
            "--query", "Reservations[].Instances[].InstanceId", "--output", "text"],
            check=False, capture=True).stdout.strip()

    def _instances_by_tag(self, spec: K8sFleetSpec, role: Optional[str] = None) -> List[str]:
        filters = [f"Name=tag:Project,Values={spec.tag}",
                   "Name=instance-state-name,Values=pending,running,stopping,stopped"]
        if role:
            filters.append(f"Name=tag:Role,Values={role}")
        out = self._aws(spec, ["ec2", "describe-instances", "--filters", *filters,
                               "--query", "Reservations[].Instances[].InstanceId", "--output", "text"],
                        check=False, capture=True).stdout.split()
        return [i for i in out if i]

    def _delete_scaffolding(self, spec: K8sFleetSpec) -> None:
        sg = self._aws(spec, ["ec2", "describe-security-groups", "--filters",
                              f"Name=group-name,Values={spec.sg_name}",
                              "--query", "SecurityGroups[0].GroupId", "--output", "text"],
                       check=False, capture=True).stdout.strip()
        if sg not in ("", "None"):
            self._aws(spec, ["ec2", "delete-security-group", "--group-id", sg], check=False)
        self._aws(spec, ["ec2", "delete-key-pair", "--key-name", spec.key_name], check=False)
        self._aws(spec, ["iam", "remove-role-from-instance-profile",
                         "--instance-profile-name", spec.profile_name, "--role-name", spec.role_name], check=False)
        self._aws(spec, ["iam", "delete-instance-profile", "--instance-profile-name", spec.profile_name], check=False)
        for arn in ("arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly",
                    "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore",
                    "arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy"):
            self._aws(spec, ["iam", "detach-role-policy", "--role-name", spec.role_name, "--policy-arn", arn], check=False)
        self._aws(spec, ["iam", "delete-role", "--role-name", spec.role_name], check=False)

    def _residue_sweep(self, spec: K8sFleetSpec) -> bool:
        remaining = self._instances_by_tag(spec)
        return len(remaining) > 0

    def build_and_bake(self, spec: K8sFleetSpec) -> str:
        """OPTIMAL delivery: provision a control + one beefy build node, build the
        image IN-REGION on it (base layers pull from Docker Hub over AWS's pipe — only
        the source crosses the operator uplink), import into k3s containerd, then
        snapshot to a baked AMI. Nodes launched with --image-delivery baked-ami boot
        with the image on disk (~90s, no sideload). Tears the build cluster down and
        keeps the AMI. Returns the AMI id."""
        spec.use_ebs = False        # build node needs no EBS/IAM (avoids iam:CreateRole)
        self._preflight(spec)
        self._ensure_token(spec)
        sg_id = self._ensure_scaffolding(spec)
        if not self._instance_id(spec, spec.control_name):
            self._launch_control(spec, sg_id)
        control_ip = self._wait_api(spec)                # k3s server up
        bname = f"{spec.sim_prefix}-build"
        # the build needs disk headroom (base layers + BuildKit cache + the ~1 GB
        # image + export temp); 16 GB fills up on export. Control already launched.
        spec.root_vol_gb = max(spec.root_vol_gb, 48)
        header = {"TS_AUTHKEY": self._read(spec.ts_authkey_file),
                  "K3S_TOKEN": self._read(spec.k3s_token_file),
                  "K3S_URL": f"https://{control_ip}:6443", "NODE_NAME": bname}
        self._run_instance(spec, sg_id, bname, "sim-node", spec.builder_type,
                           self._user_data(header, BOOTSTRAP_BUILD_SIM, spec.ttl_minutes))
        bip = self._wait_ssh(spec, bname)
        self._rsync_source(spec, bip)                    # source only (small vs 1 GB image)
        # run the build DETACHED + poll: a ~12-min blocking ssh is fragile even with
        # keepalive; detaching means a dropped connection can't strand the build.
        # bash, not sh: the build script uses `set -o pipefail` (a bash builtin). Under
        # Ubuntu's /bin/sh (dash) that dies "Illegal option -o pipefail" on line 1, so the
        # build never ran and /tmp/build.done never appeared → the poll below timed out
        # with no image (2026-08-03). bash is present on the build AMI.
        self._ssh(spec, bip,
                  f"nohup bash -c '{self._build_script(spec)}; touch /tmp/build.done' "
                  ">/tmp/build.log 2>&1 &", check=False)
        for _ in range(90):                              # up to ~30 min
            if self._ssh(spec, bip, "test -f /tmp/build.done && echo yes || echo no",
                         check=False, capture=True).stdout.strip() == "yes":
                break
            self._run(["sleep", "20"], check=False)
        else:
            raise RuntimeError("in-region build timed out")
        ami = self.bake_ami(spec, bname)                 # snapshot -> baked AMI
        for n in (bname, spec.control_name):             # tear the build cluster down
            iid = self._instance_id(spec, n)
            if iid:
                self._aws(spec, ["ec2", "terminate-instances", "--instance-ids", iid], check=False)
        return ami

    def _wait_ssh(self, spec: K8sFleetSpec, name: str, tries: int = 60) -> str:
        for _ in range(tries):
            ip = self._ts_ip(name)
            if ip and self._port_open(ip, 22):
                return ip
            self._run(["sleep", "10"], check=False)
        raise RuntimeError(f"{name} never reachable via ssh on the tailnet")

    def _rsync_source(self, spec: K8sFleetSpec, ip: str) -> None:
        src = os.path.expanduser(f"~/fleet/{spec.project}/")
        self._run(["rsync", "-az", "--delete",
                   "-e", f"ssh -i {spec.ssh_key_file} -o StrictHostKeyChecking=accept-new -o ConnectTimeout=15",
                   "--exclude", ".git", "--exclude", "node_modules", "--exclude", "ide/",
                   "--exclude", "environments/", "--exclude", "*.tar", "--exclude", "*.dmg",
                   src, f"ubuntu@{ip}:/home/ubuntu/{spec.project}/"], check=True)

    def _build_script(self, spec: K8sFleetSpec) -> str:
        p = spec.project
        return ("set -euxo pipefail; "
                "until command -v docker >/dev/null 2>&1 && sudo docker info >/dev/null 2>&1; do sleep 5; done; "
                f"cd ~/{p}; "
                # skip the build-only, UI-only library-asset pre-render (fragile,
                # not needed for the engine/worker run).
                f"sudo docker buildx build --load --build-arg SKIP_LIBRARY_ASSETS=true "
                f"-f backend/Dockerfile.slim -t {p}/api:latest -t {p}/worker:latest . ; "
                f"sudo docker save {p}/api:latest {p}/worker:latest -o /tmp/img.tar ; "
                "until sudo k3s ctr version >/dev/null 2>&1; do sleep 5; done; "
                "sudo k3s ctr -n k8s.io images import /tmp/img.tar ; sudo rm -f /tmp/img.tar")

    def _find_baked_ami(self, spec: K8sFleetSpec) -> str:
        out = self._aws(spec, [
            "ec2", "describe-images", "--owners", "self",
            "--filters", f"Name=name,Values={spec.baked_ami_name}", "Name=state,Values=available",
            "--query", "reverse(sort_by(Images,&CreationDate))[0].ImageId", "--output", "text"],
            check=False, capture=True).stdout.strip()
        return "" if out in ("None", "") else out

    def bake_ami(self, spec: K8sFleetSpec, node_name: str) -> str:
        """Snapshot a node that already carries tailscale+k3s+the image into a baked
        AMI (spec.baked_ami_name). Wipes per-node identity first so clones re-register
        cleanly; nodes launched from it boot with the image ON DISK (~90s, no
        sideload) — the responsive-scaling delivery. Returns the AMI id."""
        # cloud-init clean so CLONES re-run their user-data (the #1 baked-AMI gotcha:
        # without this, the bootstrap never executes on a clone -> unconfigured node,
        # not on the tailnet, never joins k3s). Safe over ssh (doesn't drop the link,
        # unlike stopping tailscaled). Per-node identity is cleared at clone boot.
        ip = self._ts_ip(node_name)
        if ip:
            self._ssh(spec, ip, "sudo cloud-init clean --logs 2>/dev/null || true", check=False)
        iid = self._instance_id(spec, node_name)
        old = self._find_baked_ami(spec)          # create-image rejects a dup name
        if old:
            self._aws(spec, ["ec2", "deregister-image", "--image-id", old], check=False)
        ami = self._aws(spec, [
            "ec2", "create-image", "--instance-id", iid, "--no-reboot",
            "--name", spec.baked_ami_name,
            "--description", f"{spec.project} baked engine node (tailscale+k3s+image)",
            "--tag-specifications", self._tagspec(spec, "image"), self._tagspec(spec, "snapshot"),
            "--query", "ImageId", "--output", "text"], capture=True).stdout.strip()
        self._aws(spec, ["ec2", "wait", "image-available", "--image-ids", ami], check=False)
        return ami

    def _resolve_ami(self, spec: K8sFleetSpec, role: str = "sim-node") -> str:
        # baked-ami mode: only engine nodes launch from the pre-baked image (image on
        # disk -> no sideload). Control is tainted (no app pods) -> always stock Ubuntu.
        if spec.image_delivery == "baked-ami" and role != "control":
            baked = self._find_baked_ami(spec)
            if baked:
                return baked
        # describe-images (not SSM): the terraform user has ec2:DescribeImages but
        # not ssm:GetParameters for Canonical's public parameters. Owner
        # 099720109477 = Canonical; newest available jammy image for the arch.
        name = f"ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-{spec.arch}-server-*"
        return self._aws(spec, [
            "ec2", "describe-images", "--owners", "099720109477",
            "--filters", f"Name=name,Values={name}", "Name=state,Values=available",
            "--query", "reverse(sort_by(Images,&CreationDate))[0].ImageId",
            "--output", "text"], capture=True).stdout.strip()

    # ---- helpers -----------------------------------------------------------
    def _preflight(self, spec: K8sFleetSpec) -> None:
        """Fail fast BEFORE provisioning (no partial spend): required tools, live AWS
        creds, and the tailscale auth key must be present. Raises one actionable
        message listing everything missing."""
        missing = []
        for tool in ("aws", "helm", "kubectl", "docker", "tailscale"):
            if self._run(["bash", "-lc", f"command -v {tool}"], check=False, capture=True).returncode != 0:
                missing.append(f"missing tool: {tool}")
        if self._aws(spec, ["sts", "get-caller-identity"], check=False, capture=True).returncode != 0:
            missing.append("AWS credentials invalid (aws sts get-caller-identity failed)")
        if not os.path.exists(spec.ts_authkey_file):
            missing.append(f"tailscale auth key absent: {spec.ts_authkey_file}")
        if missing:
            raise RuntimeError("preflight failed (nothing provisioned) — " + "; ".join(missing))

    def _plan(self, spec: K8sFleetSpec) -> Dict[str, Any]:
        return {"fleet": spec.fleet, "region": spec.region, "arch": spec.arch,
                "control": spec.control_instance, "sim_nodes": spec.sim_nodes,
                "sim_type": spec.sim_instance, "tag": spec.tag, "chart": spec.helm_chart,
                "values": spec.values_file, "context": spec.kube_context,
                "inbound_rules": "none (tailnet-only)"}

    def _spec_from_kwargs(self, target: str, image_tag: str, kw: Dict[str, Any]) -> K8sFleetSpec:
        project = kw.get("project")
        if not project:
            raise ValueError("k8s fleet deploy requires --project")
        return K8sFleetSpec(
            project=project,
            fleet=kw.get("fleet", target if target in ("ec2-k3s", "eks") else "ec2-k3s"),
            sim_nodes=int(kw.get("sim_nodes", 2)),
            arch=kw.get("arch", "arm64"),
            control_type=kw.get("control_type"),   # None => per-arch default
            sim_type=kw.get("sim_type"),
            version=kw.get("version", image_tag or "latest"),
            ttl_minutes=int(kw.get("ttl_minutes", 90)),
            spot=bool(kw.get("spot", False)),
        )

    @staticmethod
    def _tagspec(spec: K8sFleetSpec, rtype: str) -> str:
        return f"ResourceType={rtype},Tags=[{{Key=Project,Value={spec.tag}}}]"

    @staticmethod
    def _user_data(header: Dict[str, str], body: str, ttl_minutes: int = 0) -> str:
        lines = ["#!/bin/bash"] + [f"export {k}='{v}'" for k, v in header.items()]
        if ttl_minutes and ttl_minutes > 0:
            # TTL backstop: halt N min from boot. With run-instances'
            # instance-initiated-shutdown-behavior=terminate, halt => terminate,
            # so a forgotten/failed teardown still can't leave a node billing.
            lines.append(f"shutdown -h +{ttl_minutes} || true")
        lines.append(body)
        return "\n".join(lines)

    @staticmethod
    def _read(path: str) -> str:
        with open(path) as fh:
            return fh.read().strip()

    def _ts_ip(self, name: str) -> str:
        # Resolve via `tailscale status`, preferring an ONLINE node. A terminated node
        # leaves a stale OFFLINE entry with the same hostname, and the re-joined node
        # gets a `-N` suffix — so `tailscale ip <name>` returns the stale one. Pick the
        # online exact match, else the online suffixed match, else the offline fallback.
        out = self._run(["tailscale", "status"], check=False, capture=True).stdout or ""
        exact_off = suffix_on = ""
        for line in out.splitlines():
            p = line.split()
            if len(p) < 2:
                continue
            ip, host = p[0], p[1]
            online = "offline" not in line
            if host == name:
                if online:
                    return ip
                exact_off = exact_off or ip
            elif host.startswith(name + "-") and online:
                suffix_on = suffix_on or ip
        return suffix_on or exact_off

    def _aws(self, spec: K8sFleetSpec, args: List[str], check: bool = True, capture: bool = False):
        return self._run(["aws", "--region", spec.region, *args], check=check, capture=capture)

    def _ssh(self, spec: K8sFleetSpec, ip: str, remote_cmd: str, check: bool = True, capture: bool = False):
        # keepalive so a long remote command (e.g. a 12-min in-region build) doesn't
        # hang on a half-open connection — tolerates up to ~10min of output silence.
        return self._run(["ssh", "-i", spec.ssh_key_file, "-o", "StrictHostKeyChecking=accept-new",
                          "-o", "ConnectTimeout=10", "-o", "ServerAliveInterval=30",
                          "-o", "ServerAliveCountMax=20", f"ubuntu@{ip}", remote_cmd],
                         check=check, capture=capture)

    def _run(self, cmd: List[str], env: Optional[Dict[str, str]] = None,
             check: bool = True, capture: bool = False):
        return subprocess.run(cmd, env=env, check=check, capture_output=capture, text=True)
