# CLI Reference

This document covers CLI command usage. For implementation locations and codebase structure, see the **[Feature Map](FEATURE_MAP.md)**.

---

## SEGA + GitLab CI/CD Integration

SEGA commands can be run manually (local development) or automated via GitLab CI/CD pipelines.

**Relationship**:
- **GitLab CI/CD**: Orchestrates WHEN pipelines run (triggers, stages, environments)
- **SEGA commands**: Execute WHAT runs (build, test, deploy logic)
- **Runners**: Install SEGA and execute commands in pipeline jobs

**Usage Contexts**:

| Context | Example | Trigger |
|---------|---------|---------|
| Local development | `sega local up -p my-project` | Manual |
| Local testing | `sega probe run --type unit` | Manual |
| CI validation | `sega probe run` (in `.gitlab-ci.yml`) | Push/MR |
| CI deployment | `sega ship deploy --target staging` | Main branch |
| CI release | `sega forge release --platform desktop` | Git tag |

**CI/CD Templates**: See [Feature Map - Templates Architecture](FEATURE_MAP.md#gitlab-cicd-templates-architecture) for composable pipeline templates.

---

## Commands

### `sega local`
Manage local development deployments for workspace projects.

#### `sega local up`
Start local development services.

```bash
sega local up [options]
```

**Options:**
- `-p, --project` - Specific project(s) to deploy
- `--all` - Deploy all projects
- `--no-infra` - Skip shared infrastructure (PostgreSQL, Redis)
- `--with-tools` - Start management tools (PgAdmin, Redis Commander)
- `--shared [COMPONENT...]` - Use shared environments instead of Docker
- `--project-env [COMPONENT...]` - Use project-local environments instead of Docker
- `--backend-runtime` - Backend runtime: `python` or `rust` (native only)
- `--engine-runtime` - Engine runtime: `python` or `rust` (native only)
- `--port-offset INT` - Offset to add to all ports (for running multiple instances)
- `--agent-id` - Agent ID for concurrent testing (auto-generated if not provided)
- `--no-ledger` - Skip project reservation ledger (for single-agent use)

**Component values:** `backend`, `engine`, `frontend`, `ide`, `all`

**Environment Modes:**

| Command | Backend | Engine | Frontend |
|---------|---------|--------|----------|
| `sega local up` | Docker | Docker | Docker |
| `sega local up --shared` | Shared | Shared | Shared |
| `sega local up --shared backend` | Shared | Docker | Docker |
| `sega local up --shared backend engine` | Shared | Shared | Docker |
| `sega local up --project` | Project | Project | Project |
| `sega local up --project frontend` | Docker | Docker | Project |
| `sega local up --shared backend --project frontend` | Shared | Docker | Project |

**Environment Locations:**

| Environment | Type | Path |
|-------------|------|------|
| Shared `backend_venv` | Python venv | `~/portfolio/environments/backend_venv` |
| Shared `engine_venv` | Python venv | `~/portfolio/environments/engine_venv` |
| Shared `node_modules` | Node.js | `~/portfolio/environments/node_modules` |
| Project backend | Python venv | `./backend/venv` or `./venv` |
| Project engine | Python venv | `./engine/venv` |
| Project frontend | Node.js | `./frontend/node_modules` or `./node_modules` |

**Examples:**
```bash
# All Docker (default)
sega local up -p my-project

# All components use shared environments
sega local up -p my-project --shared

# Only backend and engine use shared, frontend uses Docker
sega local up -p my-project --shared backend engine

# Backend uses shared, frontend uses project-local
sega local up -p my-project --shared backend --project-env frontend
```

**Port Offset (Running Multiple Instances):**

Use `--port-offset` to run multiple instances of the same project simultaneously without port conflicts. The offset is added to all service ports.

| Instance | Command | API Port | Frontend Port |
|----------|---------|----------|---------------|
| Primary | `sega local up -p my-project` | 8010 | 3010 |
| Secondary | `sega local up -p my-project --port-offset 100` | 8110 | 3110 |
| Tertiary | `sega local up -p my-project --port-offset 200` | 8210 | 3210 |

```bash
# Run Docker instance on standard ports
sega local up -p my-project

# Run shared environment instance with offset (in another terminal)
sega local up -p my-project --shared all --port-offset 100

# Multiple test instances with different offsets
sega local up -p my-project --port-offset 100 --agent-id test-1
sega local up -p my-project --port-offset 200 --agent-id test-2
```

**Environment Variables Set:**
- `SEGA_PORT_OFFSET` - The raw offset value (e.g., `100`)
- `PORT_OFFSET` - Same as above (alternative name for docker-compose)
- `PORT` - Computed port with offset (for frontend/native components)
- `API_PORT` - Computed API port with offset (for native components)

#### `sega local down`
Stop local development services.

```bash
sega local down [options]
```

**Options:**
- `-p, --project` - Specific project(s) to stop
- `--all` - Stop all projects
- `--keep-infra` - Keep shared infrastructure running

#### `sega local status`
Show status of local development services.

```bash
sega local status [options]
```

**Options:**
- `--format` - Output format: table, json, simple
- `--infra` - Show infrastructure details

#### `sega local logs`
View logs for a project.

```bash
sega local logs <project> [options]
```

**Options:**
- `-f, --follow` - Follow log output (default: true)
- `-n, --tail` - Number of lines to show (default: 100)
- `-s, --service` - Show logs for specific service only

#### `sega local open`
Open project URLs in browser. Supports production domains, dev domains, and local development.

```bash
sega local open [options]
```

**Options:**
- `-p, --project` - Specific project(s) to open (can specify multiple)
- `-t, --target` - Target to open: `web` (default), `api`, `ide`, `mobile`, `metrics`, `docs`, `all`
- `-e, --env` - Environment: `prod` (default), `dev`, `local`
- `-r, --remote` - Open on remote EC2 instance (1, 2, group1, group2, or IP)
- `--list` - List URLs without opening browser
- `--port-offset` - Port offset for test environments
- `--ping` - Check URL reachability before opening (only opens reachable URLs)
- `--ping-only` - Only check reachability, do not open browser
- `--timeout FLOAT` - Timeout in seconds for ping checks (default: 3.0)
- `--scan` - Auto-select all projects for the instance/environment

**Environments:**
| Environment | URL Format | Example |
|-------------|------------|---------|
| `prod` | Production domains | `https://my-project.app` |
| `dev` | Staging domains (staging.{production-domain}) | `https://staging.my-project.app` |
| `local` | localhost:port | `http://localhost:3009` |

**Targets:**
| Target | Description | Local Port | Production URL |
|--------|-------------|------------|----------------|
| `web` | Web frontend | 3XXX | `https://{domain}` |
| `api` | API documentation | 8XXX | `https://api.{domain}/docs` |
| `ide` | IDE dev server / web page | 33XX | `https://ide.{domain}` |
| `mobile` | Mobile app | 19XXX | `https://app.{domain}` |
| `metrics` | Metrics endpoint | 9XXX | N/A (local only) |
| `docs` | Alias for api | - | - |

**Examples:**
```bash
# Open my-project production site
sega local open -p my-project

# Open multiple projects (Group 1)
sega local open -p service-a -p service-b -p my-project -p service-c -p service-d -p service-e -p service-f -p service-g

# Open dev environment
sega local open -p my-project -e dev

# Open local development (localhost:port)
sega local open -p my-project -e local

# Open API docs
sega local open -p my-project -t api

# Open IDE dev server locally
sega local open -p my-project -t ide -e local

# Open on EC2 Instance 1 (uses IP:port)
sega local open -p my-project --remote 1

# List URLs without opening
sega local open -p my-project -t all --list

# Check reachability and only open reachable URLs
sega local open --ping -p my-project

# Check reachability only (no browser)
sega local open --ping-only -p my-project -t all

# Check local services reachability with 5s timeout
sega local open --ping-only -p my-project -e local --timeout 5

# Check all projects in a group for reachability
sega local open --ping-only -e local -p service-a -p service-b -p my-project

# Scan entire EC2 instance for running services
sega local open --scan --ping-only --remote 1        # Scan Instance 1 (8 projects)
sega local open --scan --ping-only --remote 2        # Scan Instance 2 (8 projects)
sega local open --scan --ping-only --remote 1 -t api # Scan Instance 1 APIs

# Scan all local services
sega local open --scan --ping-only -e local          # Scan all local web frontends
sega local open --scan --ping-only -e local -t api   # Scan all local APIs

# Scan and open only reachable services
sega local open --scan --ping --remote 2             # Open reachable on Instance 2
```

**Project Groups:**
- **Group 1 (Instance 1)**: service-a, service-b, service-c, service-d, service-e, service-f, service-g, service-h
- **Group 2 (Instance 2)**: service-i, service-j, service-k, service-l, service-m, service-n, service-o, web-app

**Note:** Utility projects (backend-only or CLI tools) are automatically skipped as they have no web frontend.

#### `sega local launch`
Launch local application binaries. Executes packaged desktop apps or IDE binaries.

```bash
sega local launch [options]
```

**Options:**
- `-p, --project` - Project to launch (auto-detected if not specified)
- `-t, --target` - Target type: `desktop` (default), `ide`
- `--path` - Path to application binary/bundle (required unless --dev)
- `--dev` - Run in development mode (npm run electron:dev)

**Targets:**
| Target | Description | Dev Command |
|--------|-------------|-------------|
| `desktop` | Electron-based desktop app | `npm run electron:dev` |
| `ide` | VS Code fork IDE | `npm run watch` |

**Examples:**
```bash
# Launch a packaged desktop app
sega local launch -t desktop --path ./dist/MyApp.app

# Launch a packaged IDE
sega local launch -t ide --path ~/apps/MyProjectIDE.app

# Run desktop app in dev mode
sega local launch -t desktop --dev -p my-project

# Run IDE in dev mode (auto-detect project)
sega local launch -t ide --dev
```

**Platform Support:**
- **macOS**: Uses `open` command for .app bundles
- **Linux**: Direct execution of binary
- **Windows**: Uses `os.startfile()` for .exe files

---

### `sega deploy`
Deploy projects to target environments.

```bash
sega deploy --target <environment> [options]
```

**Options:**
- `--target` - Target environment (staging, prod)
- `--strategy` - Deployment strategy (rolling, blue-green)
- `--dry-run` - Preview changes without deploying

### `sega status`
Check deployment status.

```bash
sega status [--watch]
```

**Options:**
- `--watch` - Continuously monitor status

### `sega logs`
View application logs.

```bash
sega logs [--follow] [--target <env>]
```

**Options:**
- `--follow` - Stream logs in real-time
- `--target` - Filter by environment

### `sega init`
Initialize a new project with SEGA configuration.

```bash
sega init [--type <project-type>]
```

### `sega detect`
Auto-detect project type from current directory.

```bash
sega detect
```

---

## System Utilities

### `sega sysmon`
System monitoring for local and EC2 instances.

#### `sega sysmon status`
Quick system status check.

```bash
sega sysmon status [options]
```

**Options:**
- `-i, --instance` - Specific instance (1 or 2)
- `--all` - Check all instances (local + both EC2)
- `-q, --quick` - Skip slow operations

#### `sega sysmon analyze`
Deep disk analysis with cleanup recommendations.

```bash
sega sysmon analyze [options]
```

**Options:**
- `-i, --instance` - Analyze specific EC2 instance
- `--with-cpu` - Include CPU/memory/process metrics
- `-o, --output` - Save report to file

#### `sega sysmon dashboard`
Multi-instance overview dashboard.

```bash
sega sysmon dashboard [options]
```

**Options:**
- `-q, --quick` - Skip database volume sizing
- `--animate` - Enable live auto-updating
- `-n, --interval` - Refresh interval in seconds (default: 3)
- `--debug` - Enable debug logging

**Dashboard Pages (animated mode):**

| Key | Page | Content |
|-----|------|---------|
| 1 | Overview | Instance panels with disk/memory/CPU |
| 2 | Storage | node_modules, venvs, build dirs, caches |
| 3 | Docker | Container stats, database volumes |
| 4 | CPU | Detailed process list and CPU metrics |
| 5 | Graphs | CPU/memory/disk history time series |
| 6 | Services | Non-Docker services (Node.js frontends, Python backends) |

**Animated Mode Controls:**
- `q`, `Esc` - Quit dashboard
- `1-6` - Jump to specific page
- `F1-F6` - Alternative page navigation
- `↑`/`↓` - Previous/next page
- `r`, `Space` - Refresh now
- `h`, `?` - Show help overlay

#### `sega sysmon projects`
Project-based metrics dashboard.

```bash
sega sysmon projects [options]
```

**Options:**
- `-i, --instance` - Filter by instance
- `-p, --project` - Detailed view of single project
- `-q, --quick` - Skip DB volume sizing

#### `sega sysmon cleanup docker`
Clean up Docker resources.

```bash
sega sysmon cleanup docker [options]
```

**Options:**
- `-y, --yes` - Skip confirmation prompts
- `--aggressive` - Full cleanup including unused images/volumes
- `--dry-run` - Preview without executing

#### `sega sysmon cleanup builds`
Clean up build artifacts.

```bash
sega sysmon cleanup builds [options]
```

**Options:**
- `-y, --yes` - Skip confirmation prompts
- `--include-node-modules` - Also remove node_modules
- `--path` - Custom base path (default: ~/portfolio)
- `--dry-run` - Preview without executing

#### `sega sysmon report`
Generate structured reports.

```bash
sega sysmon report [options]
```

**Options:**
- `-f, --format` - Output format (markdown, json)
- `-o, --output` - Save to file
- `-i, --instance` - Single instance report
- `--all` - Include all instances

---

### `sega sysnc`
Multi-system git synchronization across the fleet.

#### `sega sysnc inspect`
Inspect changes across all 3 systems.

```bash
sega sysnc inspect [options]
```

**Options:**
- `-e, --enhanced` - Use enhanced inspection with lane validation

#### `sega sysnc analyze`
Analyze 3-way conflicts before consolidation.

```bash
sega sysnc analyze
```

Detects files modified on multiple systems and categorizes by priority.

#### `sega sysnc run`
Execute consolidation workflow.

```bash
sega sysnc run [options]
```

**Options:**
- `--dry-run` - Preview without executing
- `--phase` - Execute specific phase (1=I2, 2=I1, 3=Local, all)
- `-y, --yes` - Skip confirmation prompt

**Phase Order:**
1. Instance 2 pushes first
2. Instance 1 pulls I2, then pushes
3. Local pulls all, then pushes

#### `sega sysnc bulk`
Run bulk stash-pull-pop-push on current system.

```bash
sega sysnc bulk [options]
```

**Options:**
- `--dry-run` - Preview without executing
- `-c, --commit-number` - Specific commit number (e.g., cc54)

#### `sega sysnc settings`
Sync Claude settings to EC2 instances.

```bash
sega sysnc settings --push
```

**Options:**
- `--push` - Push settings to EC2 instances

---

## Consolidated Command Groups (Implemented)

**Status**: Implemented | 2025-12-15
**Core Principle**: Actions are commands, platforms are options.

### `sega forge`
Build, package, and distribute artifacts.

#### `sega forge build`
Build project for target platform.

```bash
sega forge build --platform <platform> [options]
```

**Options:**
- `--platform` - Target platform: `desktop`, `mobile`, `web`, `api`
- `--output` - Output directory

**Examples:**
```bash
sega forge build --platform desktop    # Electron build
sega forge build --platform mobile     # Expo/React Native build
sega forge build --platform web        # Next.js/frontend build
sega forge build --platform api        # Backend build
```

#### `sega forge dev`
Start development server for platform.

```bash
sega forge dev --platform <platform> [options]
```

**Options:**
- `--platform` - Target platform: `desktop`, `mobile`, `web`
- `--port` - Custom port

**Examples:**
```bash
sega forge dev --platform desktop      # Electron dev mode
sega forge dev --platform mobile       # Expo dev server
sega forge dev --platform web          # Next.js dev server
```

#### `sega forge compile`
Compile source to protected binaries.

```bash
sega forge compile --lang <language> [options]
```

**Options:**
- `--lang` - Source language: `python`, `node`, `js`, `rust`
- `--output` - Output directory

**Examples:**
```bash
sega forge compile --lang python       # Nuitka compilation
sega forge compile --lang node         # Bytenode compilation
sega forge compile --lang js           # javascript-obfuscator
sega forge compile --lang rust         # cargo build --release
```

#### `sega forge package`
Package application for distribution.

```bash
sega forge package --platform <platform> [options]
```

**Options:**
- `--platform` - Target: `desktop`, `mobile`, `cli`, `extension`
- `--os` - Operating system (for desktop): `mac`, `windows`, `linux`

**Examples:**
```bash
sega forge package --platform desktop --os mac     # .dmg
sega forge package --platform desktop --os windows # .exe
sega forge package --platform mobile               # .ipa, .apk
sega forge package --platform cli                  # standalone binary
sega forge package --platform extension            # .vsix
```

#### `sega forge sign`
Code signing for distribution.

```bash
sega forge sign --os <os> [options]
```

**Options:**
- `--os` - Operating system: `mac`, `windows`, `linux`
- `--identity` - Signing identity (macOS)
- `--cert` - Certificate path (Windows)

**Examples:**
```bash
sega forge sign --os mac               # codesign + notarize
sega forge sign --os windows           # signtool / osslsigncode
sega forge sign --os linux             # GPG signing
```

#### `sega forge publish`
Distribute artifacts to targets.

```bash
sega forge publish --target <target> [options]
```

**Options:**
- `--target` - Destination: `instance`, `s3`, `github`, `appstore`, `playstore`, `registry`
- `--version` - Version tag

**Examples:**
```bash
sega forge publish --target instance   # SCP to EC2 download server
sega forge publish --target s3         # Upload to S3 bucket
sega forge publish --target github     # GitHub Releases
sega forge publish --target appstore   # iOS App Store
sega forge publish --target playstore  # Google Play Store
sega forge publish --target registry   # Container/package registry (GitLab)
```

#### `sega forge release`
Full workflow: build → compile → package → sign → publish.

```bash
sega forge release --platform <platform> --target <target> [options]
```

**Examples:**
```bash
sega forge release --platform desktop --target github
sega forge release --platform mobile --target appstore
sega forge release --platform api --target registry
```

---

### `sega ship`
Deployment lifecycle management.

#### `sega ship deploy`
Deploy services to target environment.

```bash
sega ship deploy --platform <platform> --target <env> [options]
```

**Options:**
- `--platform` - Service type: `api`, `web`
- `--target` - Environment: `staging`, `production`
- `--strategy` - Deployment strategy: `rolling`, `blue-green`, `canary`
- `--dry-run` - Preview changes

**Examples:**
```bash
sega ship deploy --platform api --target production
sega ship deploy --platform web --target staging
sega ship deploy --platform api --strategy blue-green
```

#### `sega ship rollback`
Rollback to previous version.

```bash
sega ship rollback [options]
```

**Options:**
- `--version` - Specific version/tag to rollback to
- `--steps` - Number of versions to rollback

**Examples:**
```bash
sega ship rollback --steps 1           # Rollback one version
sega ship rollback --version v1.2.3    # Rollback to specific version
```

#### `sega ship status`
Check deployment status.

```bash
sega ship status [options]
```

**Options:**
- `--watch` - Continuously monitor

#### `sega ship promote`
Promote staging to production.

```bash
sega ship promote [options]
```

#### `sega ship validate`
Run health checks on deployment.

```bash
sega ship validate [options]
```

---

### `sega probe`
Test orchestration and execution.

> **Full Testing Procedure**: See [TESTING_PROCEDURE.md](TESTING_PROCEDURE.md) for sequential testing from simple to complex (8 levels).

#### `sega probe run`
Run tests with auto-detection.

```bash
sega probe run [options]
```

**Options:**
- `--platform` - Target: `desktop`, `mobile`, `web`, `api`
- `--type` - Test type: `unit`, `integration`, `e2e`
- `-H, --host` - Remote host/IP for API testing
- `--port-offset` - Port offset for testing offset deployments
- `--parallel` - Run in parallel
- `--coverage` - Generate coverage report

**Examples:**
```bash
sega probe run                                  # Auto-detect and run
sega probe run --platform web --type e2e        # Web E2E tests
sega probe run --platform mobile --type unit    # Mobile unit tests
sega probe run --host 203.0.113.10              # Test against remote host
sega probe run --port-offset 100                # Test offset deployment
```

#### `sega probe unit`
Run unit tests only.

```bash
sega probe unit [options]
```

#### `sega probe integration`
Run integration tests only.

```bash
sega probe integration [options]
```

#### `sega probe e2e`
Run end-to-end tests.

```bash
sega probe e2e [options]
```

#### `sega probe api`
API and OpenAPI validation.

```bash
sega probe api [options]
```

**Options:**
- `--spec` - OpenAPI specification file
- `--base-url` - Base URL for API testing (e.g., http://localhost:8010)
- `-H, --host` - Remote host/IP (combined with project port)
- `-p, --project` - Project name (for port lookup)
- `--port-offset` - Port offset for testing offset deployments
- `--https` - Use HTTPS instead of HTTP

**Remote API Testing:**

```bash
# Test local project
sega probe api --project my-project

# Test remote API
sega probe api --project my-project --host 203.0.113.10

# Test with HTTPS
sega probe api --project my-project --host api.example.com --https

# Test offset deployment
sega probe api --project my-project --port-offset 100

# Direct base URL
sega probe api --base-url http://192.168.1.100:8010
```

#### `sega probe browser`
Browser testing with Playwright.

```bash
sega probe browser [options]
```

**Options:**
- `--visual` - Visual regression testing
- `--a11y` - Accessibility testing
- `--perf` - Performance testing

#### `sega probe coverage`
Generate coverage report.

```bash
sega probe coverage [options]
```

#### `sega probe benchmark`
Run performance benchmarks.

```bash
sega probe benchmark [options]
```

#### `sega probe domain`
Test production and internal dev domain URLs for your projects.

```bash
sega probe domain [options]
```

**Options:**
- `-p, --project` - Specific project(s) to test (can be repeated)
- `--domain` - Domain type: `production`, `internal`, `both` (default: both)
- `--type` - Endpoint type: `landing`, `product_app`, `api`, `all` (default: all)
- `--instance` - Filter to projects on EC2 instance (`1` or `2`)
- `--timeout` - Request timeout in seconds (default: 30)
- `--no-ssl` - Disable SSL verification
- `--json-output` - Output results as JSON
- `-v, --verbose` - Verbose output

**Examples:**
```bash
# Test all production and internal domains
sega probe domain

# Test specific project
sega probe domain -p my-project --domain production

# Test only landing pages on Instance 1
sega probe domain --instance 1 --type landing

# Test internal dev domains with JSON output
sega probe domain --domain internal --json-output

# Test multiple projects
sega probe domain -p my-project -p service-b -p service-c
```

**Domain Configuration:**
Domain mappings are defined in `config/domain_registry.yaml`. Each project has:
- Production domain (e.g., `my-project.app`)
- Staging domain (e.g., `staging.my-project.app`)
- Endpoint configurations (landing, product_app, api)

#### `sega probe scan`
Scan pages for console errors and HTTP status.

```bash
sega probe scan [options]
```

**Two Modes:**

1. **Dashboard** (`--dashboard`): Fast HTTP checks, no browser (2-3 seconds)
2. **Report** (`--report`): Deep Playwright scan with console logs (60-90 seconds)

**Options:**
- `--all` - Scan all projects in the portfolio
- `-p, --project` - Specific project(s) to scan (can be repeated)
- `--domain-type` - Domain type: `production` or `internal` (default: production)
- `--endpoint-type` - Endpoint types: `landing`, `product_app`, `both` (default: both)
- `--instance` - Filter to projects on EC2 instance (`1`, `2`, or `3`)
- `--dashboard` - Show lightweight status dashboard (HTTP checks only)
- `--report` - Generate detailed console error report (Playwright scan)
- `--detail` - Report detail level: `minimal`, `summary`, `full` (default: summary)
- `--json` - Output results as JSON
- `--compact` - Show compact summary table
- `--headed` - Show browser during scan (for debugging)
- `--screenshot-errors` - Capture screenshots of pages with errors (default: true)
- `--timeout` - Page load timeout in seconds (default: 30)
- `-o, --output` - Output directory for reports (default: docs/reports/console_scans)
- `-v, --verbose` - Verbose output

**Dashboard Mode Examples:**
```bash
# Quick HTTP status check for all projects
sega probe scan --dashboard --all

# Check specific instance
sega probe scan --dashboard --instance 1

# Check internal dev domains
sega probe scan --dashboard --all --domain-type internal

# Compact view
sega probe scan --dashboard --all --compact

# Check only product apps
sega probe scan --dashboard --all --endpoint-type product_app
```

**Report Mode Examples:**
```bash
# Full console scan with detailed report
sega probe scan --all --report

# Scan specific projects
sega probe scan -p my-project -p service-b --report

# Minimal detail report
sega probe scan --all --report --detail minimal

# Full detail with stack traces
sega probe scan -p service-c --report --detail full

# JSON export for automation
sega probe scan --all --report --json > scan_results.json

# Scan with visible browser (debugging)
sega probe scan -p service-d --report --headed
```

**Console Message Processing:**
- Truncates verbose stack traces to first line + location
- Deduplicates identical errors (shows count)
- Extracts file:line from stack traces
- Filters common noise (HMR, DevTools, etc.)
- Sorts by severity (errors > warnings > info)

**Report Output:**
Reports are written to `docs/reports/console_scans/` with format:
- Markdown: `CONSOLE_SCAN_YYYYMMDD_HHMMSS.md`
- JSON: `console_scan_YYYYMMDD_HHMMSS.json`

**Use Cases:**
- **Daily health checks**: Quick dashboard to see which projects are up
- **Pre-deployment validation**: Deep scan before pushing to production
- **Error monitoring**: Track console errors across all projects
- **Cross-project analysis**: Identify systemic issues (Auth0, CORS, etc.)

> **Full Documentation**: See [CONSOLE_SCAN_GUIDE.md](../operations/CONSOLE_SCAN_GUIDE.md) for complete usage guide, architecture, and workflows

---

### `sega doctor`
Diagnostics and repair (expanded from existing).

#### `sega doctor check`
Quick health check.

```bash
sega doctor check [options]
```

#### `sega doctor diagnose`
Full diagnostics.

```bash
sega doctor diagnose [options]
```

**Options:**
- `--deps` - Check dependencies
- `--config` - Check configuration
- `--network` - Check network connectivity

#### `sega doctor repair`
Auto-fix detected issues.

```bash
sega doctor repair [options]
```

#### `sega doctor optimize`
Performance optimization.

```bash
sega doctor optimize [options]
```

**Options:**
- `--analyze` - Analysis only, no changes

#### `sega doctor scan`
Security and code scanning.

```bash
sega doctor scan [options]
```

**Options:**
- `--type` - Scan type: `deps`, `secrets`, `code`

#### `sega doctor report`
Generate health report.

```bash
sega doctor report [options]
```

---

### `sega validate`
Validate Dockerfile and deployment configurations for SEGA compatibility.

```bash
sega validate [options]
```

**Options:**
- `-d, --dockerfile PATH` - Path to Dockerfile to validate
- `-t, --project-type` - Expected project type: web_app, api, engine, worker, mobile, desktop
- `-c, --compose PATH` - Path to docker-compose.yml to validate
- `--config PATH` - Path to SEGA config file (.sega.yml)
- `--strict` - Fail on warnings (not just errors)
- `--json-output` - Output results as JSON

**Checks performed:**
- Required health check endpoints
- Non-root user configuration
- Port standards compliance
- Environment variable compatibility
- Security best practices

**Examples:**
```bash
# Validate a Dockerfile
sega validate --dockerfile Dockerfile

# Validate with project type context
sega validate --dockerfile Dockerfile --project-type web_app

# Validate docker-compose configuration
sega validate --compose docker-compose.yml

# Strict mode (fail on warnings)
sega validate --dockerfile Dockerfile --strict
```

---

### `sega health`
Check health endpoints for deployed services.

```bash
sega health [options]
```

**Options:**
- `-p, --project TEXT` - Project name (uses standard ports)
- `-u, --url TEXT` - Direct URL to health endpoint
- `-H, --host TEXT` - Custom host/IP address (e.g., 203.0.113.10, api.example.com)
- `-e, --environment` - Deployment environment: local, staging, production
- `--port INTEGER` - Override port number
- `--port-offset INTEGER` - Port offset (added to standard port)
- `--https` - Use HTTPS instead of HTTP
- `-t, --timeout INTEGER` - Timeout in seconds (default: 30)
- `-i, --interval INTEGER` - Check interval in seconds (default: 5)
- `-w, --wait` - Wait for service to become healthy
- `--all-services` - Check all project services
- `--json-output` - Output results as JSON
- `-v, --verbose` - Show detailed output

**Remote Testing:**

Test services running on remote hosts (EC2 instances, staging servers, production):

```bash
# Check project on remote IP
sega health --project my-project --host 203.0.113.10

# Check with HTTPS
sega health --project my-project --host api.example.com --https

# Check offset deployment
sega health --project my-project --port-offset 100

# Check all services on remote host
sega health --all-services --host 203.0.113.10
```

**Examples:**
```bash
# Check specific project health
sega health --project service-b

# Check project in staging environment
sega health --project service-b --environment staging

# Direct URL health check
sega health --url http://localhost:8003/health

# Wait for service to become healthy (useful in CI/CD)
sega health --project service-b --wait --timeout 60

# Check all services
sega health --all-services
```

---

## Command Migration Quick Reference

| Old Command | New Command |
|-------------|-------------|
| `sega desktop build` | `sega forge build --platform desktop` |
| `sega mobile build` | `sega forge build --platform mobile` |
| `sega frontend build` | `sega forge build --platform web` |
| `sega compile` | `sega forge compile` |
| `sega package` | `sega forge package` |
| `sega sign` | `sega forge sign` |
| `sega deploy` | `sega ship deploy` |
| `sega rollback` | `sega ship rollback` |
| `sega test` | `sega probe run` |
| `sega test_api` | `sega probe api` |
| `sega test_browser` | `sega probe browser` |
| `sega doctor` | `sega doctor check` |
| `sega optimize` | `sega doctor optimize` |
| `sega scan` | `sega doctor scan` |
