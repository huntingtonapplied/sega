# 05: Production Deploy

Deploy production infrastructure and services.

## Pre-Deployment

```bash
# 1. Sync all systems
sega sysnc run

# 2. Check system health
sega sysmon status --all
sega doctor check

# 3. Pull latest secrets
sega secrets pull --env production

# 4. Validate configuration
sega ship deploy --target production --dry-run
```

## Deploy to Staging

```bash
# 1. Deploy to staging
sega ship deploy --target staging

# 2. Verify deployment
sega ship status --target staging

# 3. Run smoke tests
sega probe run --target staging
```

## Deploy to Production

```bash
# 1. Deploy with rolling strategy
sega ship deploy --target production --strategy rolling

# 2. Monitor deployment
sega ship status --watch

# 3. Verify health
curl https://<domain>/health
```

## Rollback (if needed)

```bash
# Rollback one version
sega ship rollback --steps 1

# Rollback to specific version
sega ship rollback --version v1.2.3
```

## Post-Deployment

```bash
# 1. Verify all services
sega ship status --target production

# 2. Check metrics
sega sysmon status --all

# 3. Apply secrets if needed
sega secrets apply --env production
```

## Promotion Flow

```bash
# Promote staging to production
sega ship promote
```
