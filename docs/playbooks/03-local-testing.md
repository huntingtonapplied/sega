# 03: Local Testing

Two-phase testing: shared mode first (fast), then docker (full isolation).

> **Detailed Procedure**: See [TESTING_PROCEDURE.md](../reference/TESTING_PROCEDURE.md) for all 8 testing levels with full command options.

## Phase 1: Shared Mode Testing (No Docker)

Fast iteration without container overhead.

```bash
# 1. Ensure shared infrastructure is up
sega local up

# 2. Run unit tests
sega probe unit

# 3. Run integration tests
sega probe integration

# 4. Check coverage
sega probe coverage
```

## Phase 2: Docker Testing (Full Isolation)

Production-like environment with full isolation.

```bash
# 1. Start project in docker mode
sega local up -p <project> --docker

# 2. Run full test suite
sega probe run

# 3. Run E2E tests
sega probe e2e

# 4. Browser testing (web projects)
sega probe browser
sega probe browser --visual    # Visual regression
sega probe browser --a11y      # Accessibility
```

## API Testing

```bash
# Validate against OpenAPI spec
sega probe api --spec openapi.yaml

# Test specific endpoints
sega probe api --base-url http://localhost:8000
```

## Pre-Commit Testing Sequence

```bash
sega probe unit              # Fast feedback
sega probe integration       # Service integration
sega probe e2e               # Full workflows
sega probe coverage          # Verify coverage threshold
```
