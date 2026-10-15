<div align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset=".readme/logo-dark-mode.png">
    <img src=".readme/logo.png" alt="SEGA" width="360">
  </picture>
  <br><br>

[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![Status](https://img.shields.io/badge/status-source--available-success.svg)](#what-it-does)

**Fleet orchestration for the software you ship.**

[Website](https://segaapp.com) · [Install](#install) · [Quick start](#quick-start) · [Docs](#documentation) · [Support SEGA](#support)

</div>

-----------------

SEGA is a command-line tool for teams that run many sibling services instead of one monolith. It boots your shared local stack, builds and signs your artifacts, ships across mixed targets, **monitors capacity across every host**, syncs work between machines, and reaches past software into embedded/FPGA hardware and ML-model distribution. One grammar, one config, for your whole fleet.

It's less "a task runner" and more **an internal developer platform, as a CLI**: the operational backbone a lab runs its whole fleet from. SEGA is opinionated toward the *fleet* shape: many services, shared infrastructure, one way to operate them. If that's your situation, it collapses a pile of per-project, per-machine tribal knowledge into one grammar. If you run a single app, simpler tools (`docker compose`, `mise`, Taskfile) will serve you better.

> **Origin & support.** SEGA is the internal utility Huntington Applied built to run its own multi-service fleet, cleaned up and shared under Apache-2.0. We develop it in the open but maintain it primarily for our own use; treat it as *source-available and useful*, not a supported product. Issues and PRs are welcome; response times are best-effort.

---

## What it does

| Area | What it does | Command | Status |
|---|---|---|---|
| **Boot** | shared local infra (Postgres/Redis) + every service, one command | `sega local up` / `status` / `down` | **stable** |
| **Operate** | capacity monitoring: disk/CPU/memory/Docker across **all hosts**, with cleanup recommendations | `sega sysmon status --all` · `sega sysmon analyze` | **stable** |
| **Watch** | live status/console scan + status dashboard across the fleet | `sega probe scan --dashboard` · `sega sysmon dashboard` | **stable** |
| **Build** | compile, package, code-sign (desktop/web/mobile), compiled CLIs | `sega forge build` / `sign` · `sega desktop` · `sega binaries` | **stable** (desktop signing verified) |
| **Sync** | cross-machine git integration that never loses work (commit, never stash; abort on conflict) | `sega sysnc run` · `sega fleet` | **stable** |
| **Secrets** | sync CI/CD variables | `sega secrets pull` / `apply` | **stable** *(GitLab provider today)* |
| **Diagnose** | health checks, dependency repair, project-type detection | `sega doctor` · `sega health` · `sega detect` | **stable** |
| **Ship** | deploy lifecycle + nginx/SSL, systemd services, VPN, unified server | `sega ship deploy` · `sega services` · `sega infrastructure` | **beta** (verify against your infra) |
| **Beyond software** | firmware/FPGA/embedded programming, ML weight-bundle publishing, pipeline data extraction | `sega flash` · `sega program` · `sega models` · `sega data` | **experimental** (domain-specific) |

*One config file (`config/sega.toml`) describes your projects, hosts, and domains; every command reads it. Nothing about your fleet is hardcoded, and adding a service is a few config lines (or `sega fleet add`), not a new toolchain.*

We label maturity honestly. The `stable` core is what we run daily; `beta`/`experimental` areas are real code but not broadly hardened; don't build critical paths on them yet.

## Why SEGA

The pain it targets is specific: **a portfolio of heterogeneous services becomes a portfolio problem.** Each project grows its own boot script, its own deploy steps, its own health check. SEGA gives them one grammar (detect the project type, route to the right behavior), so `sega local up` boots the whole stack and `sega probe scan` tells you what's broken across all of them.

It **wraps, doesn't replace** the tools underneath: Docker, Kubernetes, Terraform, Ansible, and (for hardware) `openFPGALoader`. It is not a build system (no dependency graph or caching; use Nx or Bazel for that) and not a GitOps controller (use Argo). It's the opinionated glue above them.

One design principle worth calling out: **the sync layer never discards work.** `sega sysnc` commits work-in-progress as a real commit (never a stash), pushes first, and on a genuine conflict aborts and reports rather than auto-resolving. A commit survives; a stash can strand.

## Install

```bash
pip install "git+https://github.com/huntingtonapplied/sega.git#subdirectory=engine"

sega doctor                 # check/repair host dependencies (Docker, etc.)
```

Or from a clone (the package lives in `engine/`):

```bash
git clone https://github.com/huntingtonapplied/sega.git
cd sega
pip install ./engine        # optional extras: ./engine[dashboard,data,grpc]
```

Requires Python 3.10+. Optional external tools (Docker, kubectl, helm, ansible, terraform) are only needed for the features that use them.

## Quick start

Go from nothing to a running fleet without hand-editing config:

```bash
sega fleet init                 # scaffold config/sega.toml (one starter service)
sega fleet add api -d api.example.com   # allocate id + ports, add to the fleet
sega fleet ls                   # see the whole fleet at a glance
sega local up                   # boot shared Postgres/Redis + every service
sega probe scan                 # HTTP + console health across the fleet
```

Prefer to start from a fuller template? `cp config/sega.toml.example config/sega.toml` and edit it by hand. Enable tab-completion with `sega completion zsh` (or `bash`/`fish`).

Ports are derived from each project's `id` (api = 8000+id, frontend = 3000+id, …), so you allocate ids once and the whole port map follows, with no collisions.

See [`examples/`](examples/) for runnable sample configurations.

## Configuration

Everything SEGA needs is in `config/sega.toml`: projects, instances (deploy hosts), domains, build manifest. Nothing about your fleet is hardcoded in the source; SEGA reads it all from config. Override the config path with `SEGA_CONFIG_PATH`, and the workspace root with `SEGA_FLEET_ROOT`.

```toml
[projects.web-app]
id = 0
deployment_target = "prod-01"   # an instance name, or "local"
has_frontend = true

[instances.prod-01]
ip = "203.0.113.11"
ssh_user = "ubuntu"
ssh_key_path = "~/.ssh/id_rsa"

[domains]
web-app = { prod = "example.com", dev = "staging.example.com" }
```

## Documentation

- [Whitepaper](docs/WHITEPAPER.md): the design, and what runs today vs. roadmap
- [CLI reference](docs/reference/cli-reference.md)
- [Architecture](docs/architecture/)
- [Contributing](docs/CONTRIBUTING.md) · [Security policy](docs/SECURITY.md)

## Support

SEGA is free under Apache-2.0. If it saves your team time, you can [support its development](https://buy.stripe.com/dRmcN50e0dA19aV0Rl6g800) (any amount, via Stripe). Payments go to Huntington Applied LLC and are not tax-deductible. Bug reports and pull requests help just as much.

## License

Apache License 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
Copyright © Huntington Applied.
