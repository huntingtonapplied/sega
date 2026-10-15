# Changelog

All notable changes to SEGA are recorded here. This project follows
[Semantic Versioning](https://semver.org/).

## [0.1.0]

First source-available release: fleet orchestration for a portfolio of services.

### Added
- One CLI over the fleet: `local` (shared dev infrastructure), `forge` (build,
  sign, package), `ship` (mixed-target deployers), `probe` (test + status scan),
  `system` (cross-machine sync), and a live `dashboard`.
- Config-driven behavior: project lists, ports, hosts, and deploy targets live in
  `config/sega.toml`, never in the source. See `config/sega.toml.example`.
- `sega fleet` commands to grow and inspect the fleet: `init`, `add`, `ls`
  (`--json`), and `remove`.
- Graceful first run: with no config present the CLI still starts and points you
  at `sega fleet init`.
- Shell tab-completion via `sega completion <shell>`.
- Preservation-first git sync: work is committed, never stashed or discarded, and
  conflicts are never auto-resolved.

[0.1.0]: https://github.com/huntingtonapplied/sega/releases/tag/v0.1.0
