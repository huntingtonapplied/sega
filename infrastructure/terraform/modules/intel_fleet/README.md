# intel_fleet (Terraform)

Provisions a **flat-network EC2 pool** for the distributed swarm swarm, so EC2
behaves like the local LAN. Invoked by sega's `SwarmDeployer` when
`--fleet ec2` (`PROVISION=terraform`); not used for single/mini-net.

Creates:
- one **cluster placement group** (single-AZ, low-latency node↔node)
- a **self-referencing security group** (all intra-cluster ports open node↔node,
  SSH only from the tailscale CGNAT range, egress out) — closed to the world
- **EFS** as the shared sample store, mounted at `drop_path` on every node
- `1 + worker_count` instances (index 0 = head), each with cloud-init that
  installs docker, joins the **tailnet** (pre-auth key), and mounts EFS

It deliberately does **not** init/join the swarm — sega's `SwarmDeployer` does
that over SSH after apply, consuming `output "inventory"` (same code path and
format as the mini-net inventory). Keeps the token dance out of Terraform.

## Contract
- Reuses an **existing** `vpc_id` + one private `subnet_id` (pass via
  `config/fleets/ec2.tfvars`). All nodes land in that single subnet.
- `output "inventory"` → `role ssh-target fqdn label` lines the deployer parses.

## Cost / arch knobs
- `cpu_arch` — `x86_64` (m7i/c7i/t3) or `arm64` (m7g/c7g/**t4g**, ~20% cheaper and matches
  images built on the M4 minis — no cross-compile). Switches the Ubuntu AMI automatically.
- `use_spot` — one-time spot request (60–90% off; no auto-replace on interruption — fine for
  the stateless sim pool and all testing).
- `use_placement_group` — cluster PG for low latency (prod). **Set false for t-series** —
  burstable types don't support cluster PGs.
- `worker_count = 0` — single node (head only): the cheapest provisioning smoke.

**Cheapest test:** `config/fleets/ec2-test.tfvars` (t4g.small, arm64, spot, 1 node, no PG) —
a few-cents run that still exercises the real provision → cloud-init → swarm path. Burstable
is fine for *testing* (bursty, not sustained); the t-series throttle caveat only bites
sustained production sim.

## Usage (normally via `sega ship swarm --fleet ec2`)
```
terraform -chdir=. apply -var-file=<repo>/config/fleets/ec2.tfvars \
  -var worker_count=6
terraform output -raw inventory      # what SwarmDeployer materializes
```

Built on the same primitives as sega's `vpc`/`devops` modules; kept as a
dedicated module because the flat-net + placement-group + EFS shape is specific
to the fleet. Validated with `terraform validate`.
