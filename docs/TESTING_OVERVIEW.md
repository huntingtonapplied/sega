# SEGA Testing Overview

Quick reference for testing with SEGA.

**Related Documentation**:
- [TESTING_PROCEDURE.md](reference/TESTING_PROCEDURE.md) - Full sequential procedure (8 levels)
- [SEGA_TESTING_FRAMEWORK.md](development/SEGA_TESTING_FRAMEWORK.md) - Framework architecture
- [Playbook 03: Local Testing](playbooks/03-local-testing.md) - Workflow guide
- [Playbook 07: Production Testing](playbooks/07-production-testing.md) - Production validation

## Quick Start

```bash
# Run all tests (auto-detect)
sega probe run

# Run specific test types
sega probe unit           # Unit tests
sega probe integration    # Integration tests
sega probe e2e            # End-to-end tests

# Browser testing
sega probe browser        # Functional tests
sega probe browser --visual   # Visual regression
sega probe browser --a11y     # Accessibility

# Coverage
sega probe coverage
```

## Test Types

| Type | Command | Purpose |
|------|---------|---------|
| Unit | `sega probe unit` | Fast, isolated tests |
| Integration | `sega probe integration` | Service integration |
| E2E | `sega probe e2e` | Full workflow tests |
| Browser | `sega probe browser` | UI testing |
| API | `sega probe api` | API validation |

## Test Detection

SEGA automatically detects test infrastructure:

1. `docker-compose.test.yml` - Docker-based tests (highest priority)
2. Makefile `test` targets - Make-based tests
3. `pytest.ini` / `tests/` - Python tests
4. `package.json` test scripts - JavaScript tests
5. `go.mod` / `Cargo.toml` - Go/Rust native tests

## Coverage Requirements

| Scope | Target |
|-------|--------|
| Critical paths | 85%+ |
| Business logic | 80%+ |
| Overall project | 70%+ |

## CI/CD Integration

```yaml
# GitLab CI example
test:
  script:
    - sega probe run --output junit
  artifacts:
    reports:
      junit: test-results.xml
```

## Troubleshooting

```bash
# Check what SEGA detects
sega probe run --dry-run

# Debug output
SEGA_DEBUG=1 sega probe run

# View test infrastructure status
sega probe status
```
