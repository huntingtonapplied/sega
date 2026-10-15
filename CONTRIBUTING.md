# Contributing to SEGA

Thanks for your interest. SEGA is the internal utility Huntington Applied uses to
run its own multi-service fleet, shared under Apache-2.0. We develop it in the
open but maintain it **primarily for our own use**, so please set expectations
accordingly: issues and pull requests are welcome and read, but reviews and
releases happen on a **best-effort** cadence, and we may decline changes that
don't fit how we run our fleet.

## Ground rules

- **Keep it fleet-shaped.** SEGA is opinionated toward many-sibling-services with
  shared infrastructure and config-driven behavior. Changes that generalize *that*
  are welcome; changes that turn SEGA into a different kind of tool probably aren't.
- **Config over hardcoding.** Anything project-, host-, or org-specific belongs in
  `config/sega.toml`, never in the source. See `config/sega.toml.example`.
- **Be honest about maturity.** Don't advertise a command as `stable` in docs
  unless it's verified. Mark new/rough areas `beta`/`experimental`.

## Development

```bash
pip install -e engine        # installs the `sega` CLI
pip install ruff pytest
ruff check engine/sega
PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python pytest tests/ -m "not integration and not slow"
```

- Match the surrounding code style; keep changes focused.
- Add or update tests for behavior changes (see `tests/`).
- The CLI must import cleanly: `python -c "from sega.cli.main import cli"`.

## Sign-off (DCO)

We use the [Developer Certificate of Origin](https://developercertificate.org/).
Sign each commit with `git commit -s`, which adds:

```
Signed-off-by: Your Name <you@example.com>
```

By signing off you certify you wrote the change (or have the right to submit it)
under the project's Apache-2.0 license. No separate CLA is required.

## Reporting security issues

Do **not** open a public issue for anything exploitable, see [SECURITY.md](SECURITY.md).
