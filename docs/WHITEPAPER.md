# SEGA: fleet orchestration

*How a single CLI boots, builds, ships, tests, and watches every project in a portfolio, routing heterogeneous targets through one interface and integrating work across many machines without ever discarding it.*

> **Positioning in one line:** SEGA is the *fleet CLI*, the orchestration layer a portfolio of engineering projects shares, instead of each project carrying its own deployment scripts, test runners, and sync habits. It is deliberately opinionated toward the fleet shape; that opinion is the point.

---

## Abstract

Most CI/CD tooling assumes a *uniform* target: a team that ships only containers standardizes on one pipeline. SEGA addresses the opposite case, a **portfolio of services that do not all run the same way**: a web frontend deploys to a hosting platform, a backend to a container cluster, a desktop app is built and signed, a device is flashed over a serial link, a programmable chip is loaded with a bitstream. SEGA routes each of these through a *detected project type* to the matching deployer, so one command surface covers targets that normally require separate toolchains and separate mental models.

Around deployment it adds the things a *fleet* needs that a single-project tool never has to: shared local infrastructure that every project uses instead of each running its own copy; test and status orchestration that answers portfolio-wide questions ("what is broken right now?"); and a git-synchronization discipline built on a single rule, **no work is ever discarded to make a merge succeed.**

This paper describes the parts that run today, separates them plainly from the intelligence and autoscaling the platform is *designed toward*, and states the design principles, opinionated defaults, config-driven behavior, preservation-first sync, and backend integrations kept as private plug-ins behind generic interfaces.

---

## The problem: a portfolio is not a project

Three constraints make a shared control plane for a portfolio hard to build, and they are the constraints SEGA is organized around.

**1. Heterogeneity of targets.** A single `deploy` has to be able to reach a container registry, a cloud host, a bare-metal box, a desktop-signing pipeline, and a hardware programmer, each with its own protocol and failure mode. Hiding that variety behind one verb requires *detecting what a project is* before deciding *how to ship it*.

**2. Fleet scale.** When many projects share infrastructure, testing, status, and synchronization become *portfolio* problems, not per-project ones. A status check that means anything has to reach every project's live surface; a sync pass has to touch every repository in a fleet, not just the one in front of the operator.

**3. Safety of live work.** Synchronizing many repositories across several machines invites the temptation to stash or discard local changes to force a clean merge, and that is exactly where work is lost. A stash that is never restored strands an operator's changes; an automatic conflict resolution silently drops one side. Any tool that moves code between machines has to treat uncommitted work as sacred.

Existing tools solve *slices* of this. Build systems (Nx, Turborepo, Bazel) own the dependency graph and caching for a monorepo. GitOps controllers (Argo) own declarative Kubernetes delivery. IaC (Terraform, Ansible) owns provisioning. Developer portals (Backstage) own the catalog and UI. None of them own *"one CLI that boots my local stack, builds and signs my desktop app, ships my services across mixed targets, and shows me what's broken across the whole fleet."* That seam, above task runners, below build systems and portals, wrapping (not replacing) IaC, is where SEGA sits.

---

## The approach

SEGA is a command-line platform in Python, organized into **action-oriented command groups where the action is the command and the platform is an option** (`sega ship deploy --platform api`, `sega forge build --platform desktop`). Four load-bearing mechanisms:

### Project detection → deployment routing
Before deploying, SEGA inspects a project to determine its type, then dispatches to the deployer that matches. The deployer set is concrete and spans software and hardware: Kubernetes and container-service deployers, hosted-platform deployers, an Ansible deployer that pushes state over SSH for bare-metal and firmware, and an FPGA deployer that drives a bitstream loader. A **router** sits in front of a shared **base-deployer contract**, so the variety lives in the deployers and the operator sees one `deploy`. Adding a target means implementing one interface, not threading a new path through the whole system.

### Shared local infrastructure
`sega local up` stands up the databases and caches (PostgreSQL, Redis, a time-series store) that portfolio projects *share*, so a project does not run its own copy of each. This is the honest wedge, the immediately demoable win: one command boots the entire multi-service stack, no per-project `docker-compose` sprawl. Ports are computed from a project identifier by a fixed formula, so the fleet never collides.

### Fleet test + status orchestration
Two distinct paths, because a portfolio needs both. A **test orchestrator** selects runners by project type, unit/integration suites, browser end-to-end tests, API validation against an OpenAPI spec. A lighter **probe/scan** path scales to the whole fleet at once: it visits each project's live surface, records HTTP status, scans the browser console for errors, and aggregates a report. A full suite is expensive and runs per project; a console-and-status scan is cheap and answers the portfolio-wide question of what is currently broken.

### Git synchronization with a preservation invariant
SEGA carries a sync toolkit for keeping many repositories aligned across several machines, shaped by one rule stated in the tooling itself: **never discard work to unblock a merge, and never auto-resolve a conflict.** The integration path *commits* each repository's work-in-progress as a real commit (never a stash), tries to push first, and only falls through to fetch-and-merge when the push is rejected. A genuine same-line conflict aborts the merge, leaves the committed work intact, and reports the conflicted files for deliberate resolution. The reasoning, recorded in the scripts: a commit is a first-class object that survives an abort and is always recoverable; a stash that is never popped hides work and can strand it.

---

## Architecture at a glance

A Click-based CLI over engine modules organized by domain:

| Group | Responsibility |
|---|---|
| `local` | shared dev infrastructure (Postgres/Redis/time-series) for the fleet |
| `forge` | build, compile, package, code-sign, publish artifacts (web / desktop / mobile) |
| `ship` | deployers + deployment strategies across mixed targets |
| `probe` | test runners + the fleet console/status scan |
| `system` | cross-machine synchronization + host monitoring |
| `dashboard` | live portfolio status/config web view |

Behavior is **config-driven**: a per-project descriptor declares the project's type, ports, and deployment target, and the deployment topology (which hosts exist, where a project runs) is resolved from configuration rather than hardcoded, the platform supports any number of instances named in config, not a fixed set.

**Backend integrations are private plug-ins behind generic interfaces.** Where SEGA reports telemetry to an external observability backend, the *interface* is generic and ships as a no-op by default; the concrete transport implementation is an optional, privately-supplied plug-in. The open-source core carries the extension point, not any particular organization's backend. This is the seam throughout: the control-plane logic is public and agnostic; site-specific adapters and registries are configuration and plug-ins layered on top.

---

## What runs today vs. what it is designed toward

Honesty about maturity is a feature, not a caveat. **Running and used today:** the deployment router and deployer set; the shared local-infrastructure manager; the fleet test and console/status scan; the git-synchronization toolkit; artifact build/sign/package (notably desktop code-signing, a genuinely painful problem); and the live status dashboard.

**Roadmap, not shipped behavior, do not read as operational:** AI-driven deployment-strategy selection and cost optimization (today's routing is *rule-based* on detected project type, not model-driven); any headline figures for deployment success rate or ROI that appear in internal design documents are illustrative targets, not measured fleet results, and are not reported here as outcomes; and the Kubernetes/GPU autoscaling for simulation workloads exists as infrastructure modules rather than a continuously exercised production path. The command surface deliberately labels experimental areas so an operator is never surprised by an unfinished path.

---

## Design principles

1. **Opinionated toward the fleet shape.** SEGA assumes many sibling services and optimizes hard for that. It says no to single-app teams and pure-single-stack shops on purpose, a sharp tool earns adoption by nailing a shape, not by being generic.
2. **Config over code.** Project lists, ports, hosts, domains, and deployment targets live in configuration. The engine reads them; it does not embed them. A new organization populates config, not source.
3. **Preservation-first.** No sync path discards uncommitted work or auto-resolves a conflict. Ever.
4. **Adapters stay private.** Organization-specific backends, registries, and credentials are plug-ins and configuration behind generic public interfaces, never baked into the shipped core.
5. **Wrap, don't replace.** SEGA orchestrates Terraform, Ansible, Kubernetes, and bitstream loaders; it is the routing-and-fleet layer over them, not a new engine for any one domain.

---

## Related work

SEGA sits *on top of* established tools rather than replacing them: Terraform for cloud resources, Ansible for bare-metal and firmware, Kubernetes for container scheduling, `openFPGALoader` for bitstream programming, Git for the version-control substrate its sync layer manipulates, and a browser-automation layer for end-to-end testing. Its contribution is not a new deployment engine for any of these, it is the **routing and fleet layer** that lets one interface reach all of them, plus the synchronization discipline that holds across every repository in a portfolio.

Against adjacent categories: it is *not* a build system (no dependency graph, no content-addressed caching, use Nx/Bazel for that), *not* a GitOps controller (Argo is declarative and K8s-native), and *not* a portal (Backstage is a UI + catalog). It is the opinionated, code-first control plane a portfolio runs *from*.

---

## Outlook

The near-term direction follows from the gap between what runs and what the design anticipates. The routing layer is the natural place to add deployment-strategy intelligence, because detection already produces the signal a model would consume and the deployer contract already isolates where a chosen strategy takes effect. The fleet scan is the natural place to accumulate the history that would make failure prediction meaningful, since it already visits every project's live surface on a schedule. And the autoscaling modules point toward exercising GPU-node autoscaling against real load rather than holding it as provisioned infrastructure.

The contribution of SEGA is a working control plane that presents container, cloud, bare-metal, desktop, and FPGA delivery behind one command surface, orchestrates testing and status across a project fleet, and integrates work across machines under a rule that keeps every change recoverable. The cross-domain routing and the preservation-first synchronization are real today. The predictive and autoscaling intelligence is the direction the platform is built to grow.

---

*SEGA is a plain product name (not an acronym). This document describes the open-source core; organization-specific configuration, registries, and backend adapters are layered on top and are not part of the public distribution.*
