# Core Templates

Shared validation and testing templates included by all projects.

## Templates

| Template | Status | Purpose |
|----------|--------|---------|
| `validate.yml` | Planned | Lint, type check, static analysis |
| `test.yml` | Planned | Unit, integration, e2e test patterns |

## Triggers

Core templates run on:
- Every push (validation)
- Merge requests (validation + tests)
- Main branch pushes (validation + tests)
- Tags (validation + tests)

## Usage

```yaml
include:
  - project: 'example/sega'
    file:
      - '/templates/gitlab-ci/core/validate.yml'
      - '/templates/gitlab-ci/core/test.yml'
```

## SEGA Commands Used

- `sega doctor check` - Dependency and config validation
- `sega probe run --type unit` - Unit tests
- `sega probe run --type integration` - Integration tests
