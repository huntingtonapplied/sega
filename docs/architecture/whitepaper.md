# A cross-domain control plane for deploying software and hardware from one interface

*How SEGA presents a single command surface over container, cloud, bare-metal, and FPGA deployment, orchestrates fleet-wide testing, and integrates work-in-progress across many machines without ever discarding it.*

## Abstract

SEGA is the orchestration layer that a portfolio of engineering projects shares instead of each project carrying its own deployment scripts, test runners, and synchronization habits. It targets the case where the things being shipped do not all run the same way: a web frontend deploys to a hosting platform, a backend service deploys to a container cluster, a device deploys firmware over a serial link, and a programmable chip deploys a bitstream. SEGA routes each of these through a detected project type to the matching deployer, so one command surface covers targets that normally require separate toolchains. Alongside deployment, it runs test orchestration across a project fleet, collecting console errors and HTTP status from live sites, and it carries a git synchronization toolkit built around a strict rule that no work is ever thrown away to make a merge succeed. This article describes the deployment router, the fleet test and synchronization layers that are built and used today, and the model distribution path that extends the same publishing machinery to trained weights. It separates the parts that run now from the intelligence and autoscaling features that the platform is designed toward.

## Background

Continuous integration and continuous delivery describe the practice of turning a code change into a running deployment automatically, with tests gating each step. The tooling for this is mature when the target is uniform. A team that ships only containers can standardize on one pipeline. Version control provides the substrate: Git tracks every change as a content-addressed commit, which makes history reconstructable and merges well defined [1]. Container orchestration platforms such as Kubernetes schedule and scale services across machines [2]. Infrastructure as code tools such as Terraform describe cloud resources declaratively so they can be created and destroyed reproducibly [3]. Configuration management tools such as Ansible push state onto machines over SSH without an agent [4].

Hardware targets sit outside this uniform picture. Firmware for an embedded device is flashed over a physical link. A field-programmable gate array, a chip whose logic is reconfigured after manufacture, is loaded with a bitstream using a dedicated programmer such as openFPGALoader [5]. These operations do not fit the container pipeline, and the teams that perform them often maintain a parallel set of scripts that share nothing with the software side.

The gap SEGA addresses is the seam between these worlds. A portfolio that contains both web services and hardware artifacts ends up with two deployment cultures, two sets of credentials, and two mental models. The cost includes duplicated tooling and, more significantly, the coordination overhead of remembering which command applies to which target.

## The problem

Three constraints make a shared control plane hard to build.

The first is heterogeneity of targets. A single deploy command has to reach a container registry, a cloud hosting provider, a bare-metal host, and a hardware programmer, each with its own protocol and failure mode. Hiding that variety behind one interface requires detecting what a project is before deciding how to ship it, and routing to the correct deployer once the type is known.

The second is fleet scale. When many projects share infrastructure, testing and deployment become portfolio problems rather than per-project ones. A status check that means anything has to reach every project's live surface, and a synchronization pass has to touch every repository in a fleet of submodules rather than only the one in front of the operator.

The third constraint is the safety of live work. Synchronizing many repositories across several machines invites the temptation to stash or discard local changes to force a clean merge. That temptation is where work is lost. A stash that is never restored strands an operator's changes; an automatic conflict resolution silently drops one side. Any tool that moves code between machines has to treat uncommitted work as sacred.

## The approach

SEGA is a command-line platform written in Python, organized into action-oriented command groups where the action is the command and the platform is an option. The core of the deployment path is a router that maps a detected project to a deployer.

**Project detection and deployment routing.** Before deploying, SEGA inspects a project to determine its type, then selects the deployer that matches. The deployer set is concrete and covers both software and hardware. Container and cloud targets are handled by deployers for Kubernetes, container services, and hosted platforms including Vercel, Amplify, Firebase, Render, and Supabase. Bare-metal and firmware targets are handled by an Ansible deployer that pushes state over SSH. Programmable-chip targets are handled by an FPGA deployer that drives a bitstream loader. A router in front of these deployers dispatches to the right one, and a base deployer defines the shared contract, so adding a new target means implementing one interface rather than threading a new path through the whole system. This is the mechanism behind the claim that one interface spans software and hardware: the variety lives in the deployers, and the operator sees a single deploy command.

**Fleet test orchestration.** SEGA runs tests across a portfolio rather than a single project. A test orchestrator selects runners by project type, covering unit and integration suites, browser-based end-to-end tests driven through a browser automation layer, and API validation against an OpenAPI specification. A separate probe path performs a lighter check that scales to the whole fleet at once: it visits each project's live surface, records HTTP status, and scans the browser console for errors, then aggregates the results into a report. The distinction matters in practice. A full test suite is expensive and runs per project; a console-and-status scan is cheap and answers the portfolio-wide question of what is currently broken.

**Git synchronization with a preservation invariant.** SEGA carries a synchronization toolkit for keeping many repositories aligned across several machines. Its design is shaped by one rule stated in the tooling itself: never discard work to unblock a merge, and never auto-resolve a conflict. The primary integration script commits each repository's work-in-progress as a real commit rather than stashing it, attempts a push first, and only falls through to fetch and merge when the push is rejected. When a genuine same-line conflict appears, the script aborts the merge, leaves the committed work intact, and reports the conflicted files for deliberate manual resolution. A companion pull script performs the reverse direction without stashing, so any local change that overlaps incoming work surfaces as a conflict rather than being masked. The reasoning recorded in the scripts is that a commit is a first-class object that survives an abort and can always be recovered, while a stash that is never popped hides work and can strand it.

## Architecture at a glance

The platform is a Click-based command-line interface over a set of engine modules organized by domain. A local module manages shared development infrastructure, standing up the PostgreSQL, Redis, and time-series database services that portfolio projects share so that a project does not run its own copy of each. A forge module handles build, compilation, packaging, code signing, and publishing of artifacts. A ship module holds the deployers and deployment strategies. A probe module holds the test runners and the fleet scan. A system module holds the synchronization and monitoring utilities. Configuration is expressed in YAML, with a per-project descriptor declaring the project type and deployment targets, which is the input the detection and routing logic reads.

The same publishing machinery that ships CLI and desktop artifacts also ships trained models. A models command takes weight bundles staged by an upstream producer, verifies their checksums, publishes them under a downloads path alongside the other artifacts, and builds a catalog that links to them. Reusing the artifact-distribution path for weights keeps model release inside the same infrastructure rather than introducing a separate one.

## Current status and limitations

The deployment router, the deployer set, the fleet test and scan paths, the git synchronization toolkit, the local shared-infrastructure manager, and the model publishing command are built and in use across the portfolio. These are the parts an operator runs today.

Several capabilities described in the broader platform design are targets rather than shipped behavior and should not be read as operational. The design references AI-driven deployment strategy selection with a high success-prediction accuracy and machine-learning-powered cost optimization; these are roadmap items, and the deployment routing that runs today is rule-based on detected project type, not model-driven. The design document's headline figures for deployment success rate, time reduction, and return on investment are illustrative targets from that document, not measured results from a live fleet, and they are not reported here as outcomes. The Kubernetes autoscaling infrastructure for simulation jobs, based on an event-driven autoscaler over cloud GPU node groups, is specified in Terraform modules; its provisioning is described as infrastructure the platform provides rather than a continuously exercised production deployment. The synchronization scripts include a note that some hosts need IPv4-forced SSH because an IPv6 route to the git remote can fail silently, which is a reminder that fleet operations across real machines encounter conditions that a uniform description omits.

## Related work

SEGA sits on top of established tools rather than replacing them. It orchestrates Terraform for cloud resources [3], Ansible for bare-metal and firmware [4], Kubernetes for container scheduling [2], and openFPGALoader for bitstream programming [5], and it builds on Git for the version-control substrate that its synchronization layer manipulates [1]. Its browser end-to-end testing is driven through a browser automation layer of the kind that Playwright provides for cross-browser control [6]. The contribution is not a new deployment engine for any one of these domains. It is the routing and fleet layer that lets one interface reach all of them and one synchronization discipline hold across all of a portfolio's repositories.

## Outlook

The near-term direction follows from the gap between what runs and what the design describes. The routing layer is the natural place to add the deployment-strategy intelligence the design anticipates, because the detection step already produces the signal a model would consume, and the deployer contract already isolates where a chosen strategy would take effect. The fleet scan is the natural place to accumulate the history that would make failure prediction meaningful, since it already visits every project's live surface on a schedule. The simulation autoscaling modules point toward exercising the GPU-node autoscaling path against real simulation load rather than holding it as provisioned infrastructure.

The contribution of SEGA is a working control plane that presents container, cloud, bare-metal, and FPGA deployment behind one command surface, orchestrates testing and status across a project fleet, and integrates work across machines under a rule that keeps every change recoverable. The cross-domain deployment and the preservation-first synchronization are real today. The predictive and autoscaling intelligence is the direction the platform is built to grow.

## References

[1] S. Chacon and B. Straub. Pro Git. Apress, 2nd edition, 2014. https://git-scm.com/book/en/v2

[2] B. Burns, B. Grant, D. Oppenheimer, E. Brewer, and J. Wilkes. Borg, Omega, and Kubernetes. ACM Queue, 2016. https://dl.acm.org/doi/10.1145/2898442.2898444

[3] HashiCorp. Terraform documentation. https://developer.hashicorp.com/terraform/docs

[4] Red Hat. Ansible documentation. https://docs.ansible.com/

[5] openFPGALoader: a universal utility for programming FPGAs. https://github.com/trabucayre/openFPGALoader

[6] Microsoft. Playwright documentation. https://playwright.dev/docs/intro
