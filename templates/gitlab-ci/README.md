# GitLab CI/CD Templates

Composable, modular pipeline templates for projects.

## Architecture

**Design Principle**: GitLab CI orchestrates WHEN things run; SEGA commands execute WHAT runs.

```
templates/gitlab-ci/
├── core/                  # Shared across all projects
│   ├── validate.yml       # Lint, type check, static analysis
│   └── test.yml           # Unit, integration, e2e patterns
│
├── deploy/                # Service deployment (continuous, branch-triggered)
│   ├── docker-registry.yml  # Build + push Docker image to GitLab Registry
│   ├── kubernetes.yml     # K8s/Helm deployment (planned)
│   └── ec2-ansible.yml    # EC2 via Ansible (planned)
│
└── release/               # Artifact releases (discrete, tag-triggered)
    ├── _base.yml          # Common: version tagging, changelog (planned)
    ├── api.yml            # API container release (planned)
    ├── desktop.yml        # Electron releases (planned)
    ├── cli.yml            # CLI binary releases (planned)
    ├── mobile-ios.yml     # iOS releases (planned)
    └── mobile-android.yml # Android releases (planned)
```

## Usage

Projects compose pipelines by including only the templates they need:

```yaml
# Example: project/.gitlab-ci.yml
include:
  - project: 'example/sega'
    file:
      - '/templates/gitlab-ci/core/validate.yml'
      - '/templates/gitlab-ci/core/test.yml'
      - '/templates/gitlab-ci/deploy/docker-registry.yml'

variables:
  PROJECT_NAME: "my-project"
```

## Event-Based Activation

Each template contains rules for when it runs:

| Event | core/* | deploy/* | release/* |
|-------|--------|----------|-----------|
| Push to feature branch | validate | - | - |
| Merge request | validate, test | - | - |
| Push to main branch | validate, test | staging (auto) | - |
| Git tag (v*.*.*) | validate, test | staging, prod (manual) | manual |

## SEGA Integration

Templates call SEGA commands for actual work:

```yaml
# Inside template
script:
  - curl -sSL https://install.huntingtonapplied.com/fleet_install | bash
  - sega forge build --platform web
  - sega ship deploy --target staging
```

## Related Documentation

- [Feature Map - Templates Architecture](/docs/reference/FEATURE_MAP.md#gitlab-cicd-templates-architecture)
- [CLI Reference - CI/CD Integration](/docs/reference/cli-reference.md#sega--gitlab-cicd-integration)
