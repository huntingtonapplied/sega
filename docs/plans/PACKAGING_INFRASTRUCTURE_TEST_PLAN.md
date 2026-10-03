# SEGA Packaging Infrastructure Test Plan

**Created**: 2025-12-16
**Status**: READY FOR EXECUTION
**Owner**: Operations / Healer Division
**Task ID**: SEGA-PKG-TEST-001
**Prerequisites**: SEGA-PKG-001 (Implementation) - Pending

---

## Objective

Validate SEGA packaging infrastructure across all distribution types defined in the PROJECT_DISTRIBUTION_MATRIX. This test plan covers build, compile, package, sign, publish, and registry operations with comprehensive verification procedures.

**Reference Documents**:
- **[SEGA_COMPILE_PACKAGING_DIRECTIVE.md](SEGA_COMPILE_PACKAGING_DIRECTIVE.md)** - Implementation specification
- **[PROJECT_DISTRIBUTION_MATRIX.md](/docs/standards/deployment/PROJECT_DISTRIBUTION_MATRIX.md)** - Per-project distribution breakdown
- **[cli-reference.md](/sega/docs/reference/cli-reference.md)** - Command documentation

---

## 1. Test Matrix Overview

### 1.1 Distribution Types to Test

| Type | Representative Project | Protection | Output Format |
|------|----------------------|------------|---------------|
| **Simulation Engine (Docker)** | my-project | None (internal) | Engine + Server images |
| **Full Local Desktop (desktop/)** | api-service | Nuitka + V8 Byte | .dmg/.exe/.AppImage |
| **Scientific IDE (ide/)** | my-project | V8 Byte + Obfusc | .dmg/.exe/.AppImage |
| **Remote Backend Desktop** | web-app | V8 Byte + Obfusc | .dmg/.exe/.AppImage |
| **CLI Tool (Rust)** | rust-cli | Native binary | Binary executables |
| **CLI Tool (Python)** | cli-tool | Nuitka | Binary executables |
| **Web Frontend** | my-project | Obfusc | Static bundle |
| **GitLab Registry** | my-project | N/A | Docker image tags |

### 1.2 Test Projects Selection

| Project | Type | Folder | Rationale |
|---------|------|--------|-----------|
| **my-project** | Simulation + IDE | `ide/` | Full stack: engine + backend + frontend + docker + IDE |
| **api-service** | Full Local Desktop | `desktop/` | Backend + native engine + frontend (Electron) |
| **web-app** | Remote Desktop | `desktop/` | Frontend-only desktop with mobile support |
| **rust-cli** | Rust CLI | `desktop/` | Native Rust binary + Electron wrapper |
| **cli-tool** | Python CLI | N/A | Nuitka Python compilation |

### 1.3 Desktop vs IDE Architecture

**Key Distinction**: Projects may have `desktop/` (Electron app) and/or `ide/` (VS Code fork)

| Folder | Build System | Output | Projects |
|--------|--------------|--------|----------|
| `desktop/` | electron-builder | Standard Electron app | api-service, web-app, rust-cli, most projects |
| `ide/` | gulp + electron-builder | VS Code fork with extensions | your simulation/compute services |

**IDE-enabled projects** (8 simulation engines) will have both:
- `desktop/` - Traditional Electron app for non-IDE use cases
- `ide/` - Scientific IDE (VS Code fork) for development workflows

---

## 2. Test Scenarios

### 2.1 Docker Image Build & Registry Upload

**Scope**: Infrastructure distribution (GitLab Container Registry)

#### Test 2.1.1: Build Docker Images
```bash
# Test project: my-project
cd ~/projects/my-project

# Build server image
sega forge build --platform api --verbose

# Expected output:
# - Docker image built: my-project-server:latest
# - Build completes without errors
# - Image size logged
```

**Verification Steps**:
1. Check image exists: `docker images | grep my-project`
2. Verify image layers: `docker inspect my-project-server:latest`
3. Test image runs: `docker run --rm my-project-server:latest --version`
4. Check health endpoint: `docker run -d -p 8001:8001 my-project-server:latest && curl localhost:8001/health`

#### Test 2.1.2: Push to GitLab Container Registry
```bash
# Login to registry
docker login registry.gitlab.com

# Tag for registry
docker tag my-project-server:latest registry.gitlab.com/my-org/my-project:test-$(date +%Y%m%d)

# Push to registry
sega forge publish --target registry --dry-run  # Preview first
sega forge publish --target registry

# Expected output:
# - Image pushed successfully
# - Tag visible in registry
# - Manifest generated
```

**Verification Steps**:
1. Confirm push success from CLI output
2. Pull image back: `docker pull registry.gitlab.com/my-org/my-project:test-YYYYMMDD`
3. Verify pulled image matches: `docker inspect --format='{{.Id}}'`
4. Check registry UI shows new tag
5. Verify deployment manifest artifact

#### Test 2.1.3: Multi-Tag Release
```bash
# Simulate tagged release
sega forge publish --target registry --version v1.0.0-test

# Expected tags created:
# - registry.gitlab.com/my-org/my-project:v1.0.0-test
# - registry.gitlab.com/my-org/my-project:latest
# - registry.gitlab.com/my-org/my-project:<commit-sha>
```

**Verification Steps**:
1. List registry tags via GitLab API or UI
2. Verify all three tags present
3. Confirm all tags point to same image ID

---

### 2.2 Desktop Application Packaging

**Scope**: Consumer distribution (Electron apps)

#### Test 2.2.1: Web Build (Frontend)
```bash
# Test project: web-app (remote backend - simpler)
cd ~/projects/web-app

# Build frontend
sega forge build --platform web --verbose

# Expected output:
# - Next.js/React build completes
# - dist/ or .next/ directory created
# - No build errors
```

**Verification Steps**:
1. Check build directory exists and has content
2. Verify bundle size is reasonable (< 10MB compressed)
3. Check no source maps in production build
4. Verify critical files present (index.html, main.js, etc.)

#### Test 2.2.2: Desktop Package Build
```bash
# Test project: web-app
cd ~/projects/web-app

# Build desktop package for current OS
sega forge build --platform desktop

# Package for distribution
sega forge package --platform desktop --os mac    # On macOS
sega forge package --platform desktop --os linux  # On Linux

# Expected output:
# - Electron app packaged
# - .dmg (macOS) or .AppImage (Linux) created
# - Package size logged
```

**Verification Steps**:
1. Locate output file in `desktop/dist/` or `dist/`
2. Check file size is reasonable (50-200MB depending on project)
3. Verify package metadata:
   ```bash
   # macOS - Check DMG contents
   hdiutil attach web-app-1.0.0.dmg
   ls /Volumes/Web-App/

   # Linux - Check AppImage
   ./web-app-1.0.0.AppImage --appimage-extract
   ls squashfs-root/
   ```
4. Verify application icon and name

#### Test 2.2.3: Install and Run Package
```bash
# macOS
open web-app-1.0.0.dmg
# Drag to Applications, launch

# Linux
chmod +x web-app-1.0.0.AppImage
./web-app-1.0.0.AppImage

# Expected behavior:
# - Application launches without errors
# - Splash screen or main window appears
# - No security warnings (unsigned)
```

**Verification Steps**:
1. Application window opens successfully
2. Check application logs (~/Library/Logs or ~/.config/web-app/logs)
3. Verify expected log messages:
   - "Application started"
   - "Config loaded"
   - Connection attempts (for remote backend apps)
4. Test basic functionality (navigation, UI responsiveness)
5. Clean exit on close

#### Test 2.2.4: Full Local Desktop (with Backend)
```bash
# Test project: api-service (has local backend + engine)
cd ~/projects/api-service

# Build all components
sega forge build --platform desktop --production

# Expected:
# - Backend compiled (if Nuitka available)
# - Frontend built
# - Electron packaged with embedded backend
```

**Verification Steps**:
1. Package includes backend binary or script
2. Application starts local backend on launch
3. Health check passes internally
4. Database initializes (SQLite or embedded)

---

### 2.2B Scientific IDE Packaging (VS Code Fork)

**Scope**: IDE distribution for simulation projects (a representative engine and others)

**Note**: The `ide/` folder will be present in simulation projects once IDE-EXEC-001 is underway. These tests validate the IDE build pipeline separate from the standard `desktop/` Electron builds.

#### Test 2.2B.1: IDE Build (gulp)
```bash
# Test project: my-project (when ide/ folder exists)
cd ~/projects/my-project/ide

# Build VS Code fork
sega forge build --platform ide --verbose

# Or manual build
npm install
npm run compile  # TypeScript compilation
gulp vscode-darwin-x64  # macOS build (or vscode-linux-x64, vscode-win32-x64)

# Expected output:
# - VS Code fork compiles successfully
# - Build artifacts in out/ directory
# - Electron app structure created
```

**Verification Steps**:
1. Build completes without TypeScript errors
2. Output directory contains VS Code structure:
   ```
   out/
   ├── vs/
   ├── main.js
   └── [workbench files]
   ```
3. Extensions bundle correctly
4. Build time is reasonable (5-15 minutes typical for full build)

#### Test 2.2B.2: IDE Package Build
```bash
# Package IDE for distribution
cd ~/projects/my-project/ide

# Package using electron-builder (same as desktop)
sega forge package --platform ide --os mac
sega forge package --platform ide --os linux

# Expected output:
# - My-Project IDE.dmg (macOS)
# - My-Project IDE.AppImage (Linux)
# - Application properly branded
```

**Verification Steps**:
1. Package file created in `ide/dist/` or similar
2. File size appropriate for IDE (200-400MB typical)
3. Check branding:
   ```bash
   # macOS - verify app name and icon
   ls "/Volumes/My-Project IDE/"

   # Verify Info.plist has correct bundle ID
   plutil -p "/Volumes/My-Project IDE/My-Project IDE.app/Contents/Info.plist" | grep CFBundle
   ```
4. Icon is project-specific (not default VS Code icon)

#### Test 2.2B.3: IDE Launch and Functionality
```bash
# Launch IDE
open "/Applications/My-Project IDE.app"  # macOS
./my-project-ide.AppImage                 # Linux

# Expected behavior:
# - IDE launches with My-Project branding
# - Welcome page shows project-specific content
# - Simulation extensions are pre-installed
# - Backend connection establishes (if applicable)
```

**Verification Steps**:
1. IDE window opens with correct branding (title bar, about dialog)
2. Check Extensions panel:
   - Simulation control extension installed
   - Three.js visualization extension installed
   - ECharts/Cesium panels available
3. Verify backend integration:
   - Status bar shows connection status
   - Simulation commands available in Command Palette
4. Check logs: `~/.config/my-project-ide/logs/`
5. Verify custom panels:
   - 3D visualization panel opens
   - Results panel functional
   - Parameter editor works

#### Test 2.2B.4: IDE vs Desktop Differentiation
```bash
# Verify both builds can coexist
# Desktop (standard Electron app)
cd ~/projects/my-project/desktop
sega forge build --platform desktop

# IDE (VS Code fork)
cd ~/projects/my-project/ide
sega forge build --platform ide

# Both should build independently
```

**Verification Steps**:
1. Both builds complete without conflict
2. Output directories are separate:
   - `desktop/dist/` - Standard Electron app
   - `ide/dist/` - VS Code fork IDE
3. Both applications can be installed simultaneously
4. Each has distinct:
   - Application name (My-Project vs My-Project IDE)
   - Bundle identifier
   - Icon
   - User data directory

---

### 2.3 Code Protection / Compilation

**Scope**: IP protection for consumer distribution

#### Test 2.3.1: Python Compilation (Nuitka)
```bash
# Test project: cli-tool
cd ~/projects/cli-tool

# Compile Python to binary
sega forge compile --lang python --standalone

# Expected output:
# - Nuitka compilation starts
# - Progress indicators shown
# - Binary created in dist/ or build/
```

**Verification Steps**:
1. Binary file exists and is executable
2. File size is reasonable (20-100MB typical)
3. Run compiled binary:
   ```bash
   ./dist/cli-tool --version
   ./dist/cli-tool --help
   ```
4. Verify no Python source visible:
   ```bash
   strings dist/cli-tool | grep -i "def " | head -5  # Should be minimal
   ```
5. Compare functionality with source version

#### Test 2.3.2: Node.js Compilation (Bytenode)
```bash
# Test project: web-app (frontend)
cd ~/projects/web-app/frontend

# Compile to V8 bytecode
sega forge compile --lang node

# Expected output:
# - .jsc files created
# - Original .js files can be removed
```

**Verification Steps**:
1. .jsc bytecode files created in output directory
2. .jsc files are binary (not readable text)
3. Application still runs with bytecode:
   ```bash
   node -e "require('./dist/main.jsc')"
   ```
4. Compare bytecode size to original JS

#### Test 2.3.3: JavaScript Obfuscation
```bash
# Test project: func-lib (JS engine)
cd ~/projects/func-lib

# Obfuscate JavaScript
sega forge compile --lang js

# Expected output:
# - Obfuscated .js files created
# - Self-defending code enabled
```

**Verification Steps**:
1. Obfuscated files are larger than originals
2. Code is unreadable:
   ```bash
   head -1 dist/engine.js  # Should be obfuscated
   ```
3. Functionality preserved:
   ```bash
   node -e "const engine = require('./dist/engine.js'); console.log(typeof engine.scan)"
   ```

#### Test 2.3.4: Rust Compilation
```bash
# Test project: rust-cli
cd ~/projects/rust-cli

# Build release binary
sega forge compile --lang rust

# Expected output:
# - cargo build --release runs
# - Binary in target/release/
```

**Verification Steps**:
1. Binary exists: `ls -la target/release/rust-cli`
2. Binary is stripped and optimized (smaller than debug)
3. Run binary:
   ```bash
   ./target/release/rust-cli --version
   ./target/release/rust-cli --help
   ```
4. Check no debug symbols: `file target/release/rust-cli`

---

### 2.4 Code Signing

**Scope**: Distribution trust and security

#### Test 2.4.1: macOS Code Signing (If Certs Available)
```bash
# Test project: web-app
cd ~/projects/web-app

# Sign application (requires Developer ID)
sega forge sign --os mac --identity "Developer ID Application: Your Organization"

# Expected output:
# - codesign runs successfully
# - Signature attached to .app bundle
```

**Verification Steps**:
1. Verify signature:
   ```bash
   codesign --verify --deep --strict web-app.app
   codesign -dv --verbose=4 web-app.app
   ```
2. Check signature details:
   ```bash
   spctl --assess --verbose web-app.app
   ```
3. No "unidentified developer" warning on launch

#### Test 2.4.2: macOS Notarization (If Certs Available)
```bash
# Notarize for distribution outside App Store
sega forge sign --os mac --notarize

# Expected output:
# - Notarization request submitted
# - UUID returned
# - Stapling completed
```

**Verification Steps**:
1. Check notarization status:
   ```bash
   xcrun notarytool history --keychain-profile "default"
   ```
2. Verify stapling:
   ```bash
   xcrun stapler validate web-app.dmg
   ```
3. App launches on fresh macOS without warnings

#### Test 2.4.3: Linux GPG Signing
```bash
# Sign AppImage
sega forge sign --os linux

# Expected output:
# - GPG signature created
# - .sig file alongside AppImage
```

**Verification Steps**:
1. Signature file exists: `ls web-app-1.0.0.AppImage.sig`
2. Verify signature:
   ```bash
   gpg --verify web-app-1.0.0.AppImage.sig web-app-1.0.0.AppImage
   ```

---

### 2.5 Full Release Workflow

**Scope**: End-to-end release pipeline

#### Test 2.5.1: Dry Run Release
```bash
# Test project: web-app
cd ~/projects/web-app

# Preview full workflow
sega forge release --platform desktop --target github --dry-run

# Expected output:
# - Lists all steps that would execute
# - No actual changes made
# - Shows version tag
```

**Verification Steps**:
1. All 5 steps listed (build, compile, package, sign, publish)
2. No files created or modified
3. Correct platform and target shown

#### Test 2.5.2: Execute Release to S3
```bash
# Full release to S3 (requires AWS credentials)
sega forge release --platform desktop --target s3 --version v0.0.1-test

# Expected workflow:
# 1. Build frontend
# 2. Compile/protect code
# 3. Package Electron
# 4. Sign (if certs available)
# 5. Upload to S3
```

**Verification Steps**:
1. Build artifacts created
2. Package file generated
3. S3 upload successful:
   ```bash
   aws s3 ls s3://my-org-releases/web-app/v0.0.1-test/
   ```
4. Download from S3 and verify:
   ```bash
   aws s3 cp s3://my-org-releases/web-app/v0.0.1-test/web-app-1.0.0.dmg ./
   # Install and run
   ```

---

## 3. GitLab CI/CD Integration Tests

### 3.1 Pipeline Template Validation

#### Test 3.1.1: Validate docker-registry.yml Template
```bash
# Lint pipeline configuration
cd ~/projects/sega/templates/gitlab-ci/deploy

# GitLab CI lint (if available)
gitlab-ci-lint docker-registry.yml

# Or use GitLab API
curl --request POST \
  --header "PRIVATE-TOKEN: $GITLAB_TOKEN" \
  --header "Content-Type: application/json" \
  --data '{"content": "'"$(cat docker-registry.yml)"'"}' \
  "https://gitlab.com/api/v4/ci/lint"
```

**Verification Steps**:
1. YAML syntax is valid
2. All stage references are correct
3. Variable substitutions are properly formatted
4. No deprecated features used

#### Test 3.1.2: Pipeline Stage Simulation
```yaml
# Create test project with template
include:
  - local: 'templates/gitlab-ci/deploy/docker-registry.yml'

variables:
  PROJECT_NAME: "test-project"
  DEPLOY_ENVIRONMENT: "staging"
```

**Verification Steps**:
1. Pipeline triggers on push
2. Build stage creates image
3. Package stage pushes to registry
4. Deploy stage (manual) functions correctly

---

## 4. Verification Checklist

### 4.1 Build Verification Matrix

| Command | Input | Folder | Expected Output | Verification |
|---------|-------|--------|-----------------|--------------|
| `forge build --platform web` | React/Next.js source | `frontend/` | dist/ with bundles | Size check, no errors |
| `forge build --platform desktop` | Electron project | `desktop/` | Packaged app | Opens, has icon |
| `forge build --platform ide` | VS Code fork | `ide/` | IDE package | Opens with branding |
| `forge build --platform api` | Python/FastAPI | `backend/` | Container ready | Health endpoint |
| `forge compile --lang python` | Python source | `backend/` or `engine/` | Nuitka binary | Runs, no .py visible |
| `forge compile --lang node` | Node.js source | `frontend/` | .jsc bytecode | Runs, binary content |
| `forge compile --lang rust` | Rust source | `engine/` | Release binary | Runs, optimized size |
| `forge package --platform desktop` | Built app | `desktop/` | .dmg/.exe/.AppImage | Installs correctly |
| `forge package --platform ide` | Built IDE | `ide/` | .dmg/.exe/.AppImage | IDE installs correctly |
| `forge publish --target registry` | Docker image | N/A | Registry tags | Pull succeeds |

**Folder Distinction**:
- `desktop/` → Standard Electron app (electron-builder)
- `ide/` → VS Code fork (gulp + electron-builder)

### 4.2 Log Verification Patterns

**Success Indicators**:
```
[BUILD] Build completed successfully
[COMPILE] Compilation finished: output_binary
[PACKAGE] Package created: project-1.0.0.dmg
[SIGN] Code signing complete
[PUBLISH] Published to registry: tag_name
```

**Error Patterns to Watch**:
```
[ERROR] Build failed: missing dependency
[ERROR] Compilation failed: Nuitka error
[ERROR] Package failed: electron-builder error
[ERROR] Sign failed: Certificate not found
[ERROR] Publish failed: Registry authentication failed
```

### 4.3 Package Metadata Verification

For each packaged application, verify:

| Field | Location | Expected Value |
|-------|----------|----------------|
| **App Name** | Info.plist / package.json | Project name |
| **Version** | Info.plist / package.json | Semantic version |
| **Bundle ID** | Info.plist | com.example.{project} |
| **Icon** | Resources/ | Custom icon present |
| **Copyright** | Info.plist | "2025 Your Organization" |
| **Signature** | codesign -dv | Valid Developer ID |

---

## 5. Test Environment Requirements

### 5.1 Local Development Machine

| Requirement | Purpose |
|-------------|---------|
| Docker | Container builds and registry tests |
| Node.js 18+ | Frontend builds, Bytenode |
| Python 3.10+ | Backend builds, Nuitka |
| Rust toolchain | rust-cli CLI compilation |
| Electron | Desktop app packaging |
| electron-builder | Cross-platform packaging |

### 5.2 Optional (Full Testing)

| Requirement | Purpose |
|-------------|---------|
| Apple Developer ID | macOS code signing |
| Apple Notarization credentials | App Store distribution |
| Windows code signing cert | Windows distribution |
| GPG key | Linux signing |
| AWS credentials | S3 distribution |
| GitLab token | Registry push/pull |

### 5.3 Tool Installation Verification

```bash
# Verify all tools available
sega doctor check --deps

# Expected output:
# ✓ docker: 24.x
# ✓ node: 18.x
# ✓ python: 3.10+
# ✓ cargo: 1.x
# ✓ electron-builder: installed
# ✓ nuitka: installed (optional)
# ✓ bytenode: installed (optional)
```

---

## 6. Test Execution Order

### Phase 1: Foundation (Prerequisites)
1. Verify SEGA installation and CLI access
2. Run `sega doctor check` to confirm dependencies
3. Verify GitLab registry access
4. Confirm test projects are available

### Phase 2: Build Tests (Core Functionality)
1. Test 2.1.1: Docker image build (my-project)
2. Test 2.2.1: Web build (my-project)
3. Test 2.2.2: Desktop package build - `desktop/` folder (web-app)
4. Test 2.2.4: Full Local Desktop with backend - `desktop/` folder (api-service)
5. Test 2.2B.1-4: IDE build - `ide/` folder (my-project, when available)
6. Test 2.3.4: Rust compilation (rust-cli)

### Phase 3: Protection Tests (IP Security)
1. Test 2.3.1: Python/Nuitka compilation
2. Test 2.3.2: Node.js/Bytenode compilation
3. Test 2.3.3: JavaScript obfuscation

### Phase 4: Distribution Tests (Registry/Publishing)
1. Test 2.1.2: GitLab registry push
2. Test 2.1.3: Multi-tag release
3. Test 2.5.2: Full release to S3 (if credentials available)

### Phase 5: Signing Tests (Optional - Requires Certs)
1. Test 2.4.1: macOS code signing
2. Test 2.4.2: macOS notarization
3. Test 2.4.3: Linux GPG signing

### Phase 6: CI/CD Integration
1. Test 3.1.1: Pipeline template validation
2. Test 3.1.2: Pipeline stage simulation

---

## 7. Success Criteria

### Minimum Viable (Phase 2 Complete)
- [ ] Docker images build successfully for simulation projects
- [ ] Desktop packages build from `desktop/` folder (web-app - remote backend)
- [ ] Desktop packages build from `desktop/` folder (api-service - full local backend)
- [ ] IDE packages build from `ide/` folder (my-project - when available)
- [ ] Rust binaries compile for CLI tools (rust-cli)
- [ ] Web frontends build with obfuscation

### Full Compliance (All Phases Complete)
- [ ] All 6 distribution types tested and verified (including IDE)
- [ ] Desktop vs IDE builds differentiated and coexist
- [ ] Code protection verified (no visible source)
- [ ] Registry push/pull cycle verified
- [ ] Package installation and execution verified
- [ ] Logs match expected patterns
- [ ] Metadata correctly set in packages (both desktop and IDE)

### Production Ready
- [ ] Code signing verified (if certs available)
- [ ] Notarization verified (macOS)
- [ ] CI/CD pipelines validated
- [ ] Full release workflow executes end-to-end
- [ ] Rollback procedures tested

---

## 8. Known Limitations

1. **Code Signing**: Requires actual certificates; skip in environments without them
2. **Notarization**: Requires Apple Developer account; skip if unavailable
3. **Mobile Builds**: Expo EAS requires account setup; defer to separate test
4. **Windows Testing**: Requires Windows machine or VM for .exe verification
5. **IDE Builds**: VS Code fork builds are complex; defer to specialized test

---

## 9. Reporting

### Test Report Template

```markdown
## SEGA Packaging Test Report - YYYY-MM-DD

### Environment
- OS: [macOS/Linux/Windows]
- SEGA Version: [x.x.x]
- Docker Version: [x.x.x]
- Node Version: [x.x.x]

### Results Summary
| Phase | Tests | Passed | Failed | Skipped |
|-------|-------|--------|--------|---------|
| Build | X | X | X | X |
| Protection | X | X | X | X |
| Distribution | X | X | X | X |
| Signing | X | X | X | X |
| CI/CD | X | X | X | X |

### Detailed Results
[Per-test results with logs]

### Issues Found
[List of issues with severity]

### Recommendations
[Next steps]
```

---

## Related Documents

- **[SEGA_COMPILE_PACKAGING_DIRECTIVE.md](SEGA_COMPILE_PACKAGING_DIRECTIVE.md)** - Implementation spec
- **[PROJECT_DISTRIBUTION_MATRIX.md](/docs/standards/deployment/PROJECT_DISTRIBUTION_MATRIX.md)** - Project breakdown
- **Task tracking** - Your project tracker

---

*This test plan implements SEGA-PKG-TEST-001 from the Operational Ledger Wave 5.*
