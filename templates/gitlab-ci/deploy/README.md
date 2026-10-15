# Deploy Templates

Service deployment templates for continuous delivery (branch-triggered).

## Templates

| Template | Status | Purpose |
|----------|--------|---------|
| `docker-registry.yml` | **Active** | Build + push Docker images to GitLab Registry |
| `kubernetes.yml` | Planned | K8s/Helm deployment |
| `ec2-ansible.yml` | Planned | EC2 deployment via Ansible |

## Triggers

Deploy templates run on:
- Main branch pushes (staging: auto, production: manual)
- Tags (staging + production available)

## Usage

```yaml
include:
  - project: 'example/sega'
    file:
      - '/templates/gitlab-ci/deploy/docker-registry.yml'

variables:
  PROJECT_NAME: "my-project"
  DEPLOY_ENVIRONMENT: "staging"
```

## SEGA Commands Used

- `sega forge build --platform api` - Build backend
- `sega ship deploy --target staging` - Deploy to staging
- `sega ship deploy --target production` - Deploy to production
- `sega ship rollback` - Rollback deployment
