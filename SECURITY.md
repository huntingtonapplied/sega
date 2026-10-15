# Security Policy

## Reporting a vulnerability

If you find a security issue in SEGA, please report it privately, **do not open a
public issue for anything exploitable.**

- Use GitHub's **[Report a vulnerability](https://github.com/huntingtonapplied/sega/security/advisories/new)**
  (Security → Advisories) on this repository, or
- email **security@huntingtonapplied.com** with a description and, if possible, a
  minimal reproduction.

We aim to acknowledge reports within a few business days. As a source-available
project maintained primarily for our own use, we handle fixes on a best-effort
basis and will credit reporters who want it.

## Scope

SEGA orchestrates builds, deployments, secrets synchronization, and (optionally)
hardware programming. Please pay particular attention to:

- the secrets commands (`sega secrets …`) and any credential handling,
- the deployment/SSH paths (`sega ship`, `sega sysnc`),
- the license/JWT utilities and any auth code,
- command-injection or path-traversal in commands that shell out.

## What is *not* a vulnerability

- Findings that require an already-compromised host or the operator's own
  credentials/SSH keys (SEGA runs with the privileges you give it).
- The presence of an "authorized penetration testing" helper, it is a wrapper
  around tools you must be authorized to run; misuse is out of scope.

## Supported versions

We support the latest released version. Fixes land on `main` and in the next
release; we do not backport to older tags.
