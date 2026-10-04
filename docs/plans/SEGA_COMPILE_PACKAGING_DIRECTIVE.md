# SEGA Compile & Packaging Implementation Directive

**Created**: 2025-12-14
**Updated**: 2025-12-14
**Status**: PENDING IMPLEMENTATION
**Owner**: Operations / Healer Division
**Task ID**: SEGA-PKG-001

---

## Objective

Configure SEGA to implement compile, protection, signing, and packaging features for all distribution targets as defined in the consolidated deployment documentation.

**Reference Documents**:
- **[DISTRIBUTION_STRATEGY.md](/docs/standards/deployment/DISTRIBUTION_STRATEGY.md)** - Distribution categories and protection requirements
- **[PROJECT_DISTRIBUTION_MATRIX.md](/docs/standards/deployment/PROJECT_DISTRIBUTION_MATRIX.md)** - Per-project distribution breakdown
- **[CICD_PIPELINE_STANDARDS.md](/docs/standards/deployment/CICD_PIPELINE_STANDARDS.md)** - CI/CD pipeline integration
- **[FEATURE_MAP.md](/sega/docs/reference/FEATURE_MAP.md)** - SEGA codebase structure reference

---

## 1. SEGA Command Structure

### 1.1 New Commands to Implement

```bash
# Code Protection Commands
sega compile <project> --target <python|node|js|rust>   # Compile source to protected binary
sega compile <project> --all                            # Compile all components

# Packaging Commands
sega package <project> --platform <desktop|mobile|ide|extension|cli>
sega package <project> --platform desktop --os <mac|win|linux|all>
sega package <project> --platform mobile --os <ios|android|all>
sega package <project> --platform ide --os <mac|win|linux|all>
sega package <project> --platform extension             # VS Code extension (.vsix)

# Signing Commands
sega sign <project> --platform <mac|win|linux>          # Sign built artifacts
sega sign <project> --notarize                          # macOS notarization

# Distribution Commands
sega distribute <project> --target <s3|registry|store>  # Upload to distribution channel
sega distribute <project> --publish                     # Publish release

# Combined Workflow
sega release <project> --platform <desktop|mobile|ide|extension|cli>
```

### 1.2 Command Configuration

Each command reads from `sega.yaml` in project root:

```yaml
# sega.yaml - Distribution Configuration Section
distribution:
  # Build Mode: 'standalone' for desktop/CLI, 'cloud' for infrastructure
  mode: standalone

  # Feature Exclusions (applied when mode=standalone)
  # These features are compile-time excluded from packaged builds
  exclusions:
    telemetry_reporter: true    # Exclude telemetry metrics client (no central metrics in offline mode)
    cloud_telemetry: true       # Exclude cloud telemetry endpoints
    remote_job_client: false    # Keep for sync functionality (set true for fully offline)

  # Code Protection
  protection:
    python:
      enabled: true
      tool: nuitka
      options: "--standalone --onefile"
      # Environment vars set during standalone builds
      standalone_env:
        SEGA_STANDALONE_BUILD: "true"
        SEGA_TELEMETRY_ENABLED: "false"
    node:
      enabled: true
      tool: bytenode  # V8 bytecode compilation
      options: "--compress"
      # Webpack defines for standalone builds
      standalone_defines:
        STANDALONE_BUILD: "true"
        TELEMETRY_ENABLED: "false"
    js:
      enabled: false
      tool: javascript-obfuscator  # For function libraries
      options: "--compact true --self-defending true"
    rust:
      enabled: true  # Native binary, no additional protection needed
      # Cargo feature flags for standalone builds
      standalone_features: ["standalone"]
      exclude_default_features: true  # Excludes telemetry-reporter from default

  # Desktop Packaging (Electron)
  desktop:
    enabled: true
    electron_builder: true
    template: "docs/templates/desktop/electron_base"
    platforms: [mac, win, linux]
    signing:
      mac:
        identity: "Developer ID Application: Your Organization"
        notarize: true
      win:
        certificate: "${WINDOWS_CERT_PATH}"
        timestamp: "http://timestamp.digicert.com"
      linux:
        gpg_key: "${GPG_KEY_ID}"

  # Mobile Packaging (Expo)
  mobile:
    enabled: true
    expo: true
    template: "docs/templates/mobile"
    platforms: [ios, android]
    signing:
      ios:
        provisioning: "${IOS_PROVISIONING_PROFILE}"
        certificate: "${IOS_DISTRIBUTION_CERT}"
      android:
        keystore: "${ANDROID_KEYSTORE_PATH}"
        key_alias: "${ANDROID_KEY_ALIAS}"

  # IDE Packaging (VS Code Fork)
  ide:
    enabled: false
    template: "docs/templates/IDE/vscode"
    build_system: gulp
    platforms: [mac, win, linux]

  # VS Code Extension Packaging
  extension:
    enabled: false
    tool: vsce
    output: ".vsix"

  # CLI Distribution
  cli:
    enabled: false  # Only for CLI utilities
    formats: [binary, cargo, pip]
    platforms: [mac, win, linux]
```

---

## 2. Project-Specific Configuration

### 2.1 Simulation Engines (Full Local Backend)

**Projects**: your simulation/compute services with a full local backend

| Component | Protection | Tool | Output |
|-----------|------------|------|--------|
| Engine (Python) | Compiled | Nuitka | Single binary |
| Backend (Python) | Compiled | Nuitka | Single binary |
| Frontend (Node) | Bytecode | Bytenode | .jsc files |
| Desktop | Packaged | electron-builder | .dmg/.exe/.AppImage |
| Mobile | Packaged | Expo EAS | .ipa/.apk |

**SEGA Commands**:
```bash
# Full desktop release for my-project
sega release my-project --platform desktop --os all

# Equivalent to:
sega compile my-project --target python    # Nuitka compile engine + backend
sega compile my-project --target node      # Bytenode compile frontend
sega package my-project --platform desktop --os all
sega sign my-project --platform mac --notarize
sega sign my-project --platform win
sega sign my-project --platform linux
sega distribute my-project --target s3
```

### 2.2 Remote Backend Projects (Thin Clients)

**Projects**: your thin-client apps that talk to a remote backend

| Component | Protection | Tool | Output |
|-----------|------------|------|--------|
| Frontend (Node) | Bytecode | Bytenode | .jsc files |
| Desktop | Packaged | electron-builder | .dmg/.exe/.AppImage |
| Mobile | Packaged | Expo EAS | .ipa/.apk |

**SEGA Commands**:
```bash
# Desktop release for a thin client (no engine/backend to compile)
sega release web-app --platform desktop --os all

# Mobile release
sega release web-app --platform mobile --os all
```

### 2.3 Utility Binaries

**Projects**: your CLI utilities (Rust or Python)

| Project | Language | Protection | Distribution |
|---------|----------|------------|--------------|
| cli-tool | Rust | Native binary | Direct download, cargo |
| monitor-tool | Python | Nuitka | Direct download, pip |
| sega | Python | Nuitka | Direct download, pip |

**SEGA Commands**:
```bash
# CLI release for cli-tool
sega release cli-tool --platform cli

# Equivalent to:
sega compile cli-tool --target rust           # cargo build --release
sega package cli-tool --platform cli --os all # Create platform binaries
sega sign cli-tool --platform all
sega distribute cli-tool --target s3
sega distribute cli-tool --target cargo       # Optional: publish to crates.io
```

### 2.4 Function Library

**Projects**: your function-library projects

| Component | Protection | Tool |
|-----------|------------|------|
| JS Functions | Obfuscation | javascript-obfuscator |
| Python Functions | Compiled | Nuitka |

**SEGA Commands**:
```bash
# Compile function library
sega compile func-lib --target js      # javascript-obfuscator
sega compile func-lib --target python  # Nuitka
sega compile func-lib --all            # Both
```

### 2.5 IDE Distribution (VS Code Fork)

**Projects**: your IDE fork (if applicable)

| Component | Build System | Tool | Output |
|-----------|--------------|------|--------|
| Full IDE | gulp | VS Code build | Custom IDE distribution |
| Extensions | vsce | VS Code Extension | .vsix files |

**Template**: `docs/templates/IDE/vscode/`

**SEGA Commands**:
```bash
# Build full IDE
sega package ide-fork --platform ide --os all

# Build VS Code extension
sega package my-extension --platform extension
```

---

## 3. Implementation Phases

### Phase 1: Core Commands (Priority)

| Command | Description | Complexity |
|---------|-------------|------------|
| `sega compile` | Nuitka/Bytenode/JS-Obfuscator compilation | Medium |
| `sega package desktop` | electron-builder integration | Medium |
| `sega sign` | Code signing (mac/win/linux) | High |

**Deliverables** (in `src/sega/`):

```
src/sega/
├── commands/
│   ├── compile.py                    # Compile command
│   ├── package.py                    # Package command
│   └── sign.py                       # Sign command
├── protection/
│   ├── __init__.py
│   ├── nuitka.py                     # Python → binary
│   ├── bytenode.py                   # Node.js → V8 bytecode
│   └── jsobfuscator.py               # JS obfuscation
├── packaging/
│   ├── __init__.py
│   ├── electron.py                   # electron-builder integration
│   ├── vscode_ide.py                 # VS Code fork builds
│   └── vscode_extension.py           # vsce integration
└── signing/
    ├── __init__.py
    ├── mac.py                        # macOS signing + notarization
    ├── windows.py                    # Authenticode signing
    └── linux.py                      # GPG signing
```

**Checklist**:
- [ ] `src/sega/commands/compile.py` - Compile command implementation
- [ ] `src/sega/commands/package.py` - Package command implementation
- [ ] `src/sega/commands/sign.py` - Sign command implementation
- [ ] `src/sega/protection/__init__.py` - Protection module init
- [ ] `src/sega/protection/nuitka.py` - Nuitka integration
- [ ] `src/sega/protection/bytenode.py` - Bytenode integration
- [ ] `src/sega/protection/jsobfuscator.py` - JS obfuscator integration
- [ ] `src/sega/packaging/__init__.py` - Packaging module init
- [ ] `src/sega/packaging/electron.py` - Electron-builder integration
- [ ] `src/sega/packaging/vscode_ide.py` - VS Code IDE build integration
- [ ] `src/sega/packaging/vscode_extension.py` - vsce integration
- [ ] `src/sega/signing/__init__.py` - Signing module init
- [ ] `src/sega/signing/mac.py` - macOS signing
- [ ] `src/sega/signing/windows.py` - Windows signing
- [ ] `src/sega/signing/linux.py` - Linux signing

### Phase 2: Mobile & Distribution

| Command | Description | Complexity |
|---------|-------------|------------|
| `sega package mobile` | Expo EAS integration | Medium |
| `sega distribute` | S3/registry upload | Medium |
| `sega release` | Combined workflow | Low (orchestration) |

**Deliverables**:

```
src/sega/
├── commands/
│   ├── distribute.py                 # Distribute command
│   └── release.py                    # Release orchestration
├── packaging/
│   └── expo.py                       # Expo EAS integration
└── distribution/
    ├── __init__.py
    ├── s3.py                         # AWS S3 upload
    └── registry.py                   # Container/package registry
```

**Checklist**:
- [ ] `src/sega/packaging/expo.py` - Expo EAS integration
- [ ] `src/sega/distribution/__init__.py` - Distribution module init
- [ ] `src/sega/distribution/s3.py` - S3 upload module
- [ ] `src/sega/distribution/registry.py` - Container registry module
- [ ] `src/sega/commands/distribute.py` - Distribute command
- [ ] `src/sega/commands/release.py` - Release command (orchestrates others)

### Phase 3: CI/CD Integration

| Feature | Description |
|---------|-------------|
| GitLab CI Templates | Pre-built `.gitlab-ci.yml` templates for each distribution type |
| GitHub Actions | Alternative CI/CD templates |
| Auto-versioning | Semantic version bumping |

**Deliverables**:
- [ ] `templates/ci/gitlab-desktop-release.yml`
- [ ] `templates/ci/gitlab-mobile-release.yml`
- [ ] `templates/ci/gitlab-cli-release.yml`
- [ ] `templates/ci/gitlab-ide-release.yml`
- [ ] `templates/ci/gitlab-extension-release.yml`

---

## 4. Template References

### 4.1 Project Templates

| Platform | Template Location | Build Tool |
|----------|-------------------|------------|
| Desktop (Electron) | `docs/templates/desktop/electron_base/` | electron-builder |
| IDE (VS Code Fork) | `docs/templates/IDE/vscode/` | gulp |
| Mobile (Expo) | `docs/templates/mobile/` | Expo EAS |

### 4.2 SEGA Internal Templates

| Platform | Template Location | Purpose |
|----------|-------------------|---------|
| Browser Testing | `sega/templates/browser/` | Playwright configs |
| Desktop | `sega/templates/desktop/` | Electron scaffolding |
| GitLab CI | `sega/templates/gitlab-ci/` | CI/CD pipelines |

---

## 5. Configuration Requirements

### 5.1 Environment Variables

```bash
# Code Signing - macOS
APPLE_ID="developer@example.com"
APPLE_APP_SPECIFIC_PASSWORD="xxxx-xxxx-xxxx-xxxx"
APPLE_TEAM_ID="XXXXXXXXXX"
MAC_SIGNING_IDENTITY="Developer ID Application: Your Organization (XXXXXXXXXX)"

# Code Signing - Windows
WINDOWS_CERT_PATH="/path/to/certificate.p12"
WINDOWS_CERT_PASSWORD="xxxxx"

# Code Signing - Linux
GPG_KEY_ID="XXXXXXXX"
GPG_PASSPHRASE="xxxxx"

# Mobile - iOS
IOS_PROVISIONING_PROFILE="/path/to/profile.mobileprovision"
IOS_DISTRIBUTION_CERT="/path/to/distribution.p12"

# Mobile - Android
ANDROID_KEYSTORE_PATH="/path/to/keystore.jks"
ANDROID_KEY_ALIAS="upload"
ANDROID_KEYSTORE_PASSWORD="xxxxx"
ANDROID_KEY_PASSWORD="xxxxx"

# Distribution
AWS_ACCESS_KEY_ID="xxxxx"
AWS_SECRET_ACCESS_KEY="xxxxx"
S3_BUCKET_RELEASES="my-org-releases"

# VS Code Extension
VSCE_PAT="xxxxx"  # Personal Access Token for VS Code Marketplace
```

### 5.2 Project Structure Requirements

Projects using these features must have:

```
project/
├── sega.yaml                    # Distribution config
├── desktop/
│   ├── electron-builder.yml     # Electron config
│   ├── build/
│   │   ├── entitlements.mac.plist
│   │   └── icon.icns / icon.ico / icon.png
│   └── scripts/
│       └── build.sh
├── mobile/  # or expo/
│   ├── app.json                 # Expo config
│   └── eas.json                 # EAS Build config
├── extension/  # For VS Code extensions
│   ├── package.json             # Extension manifest
│   └── .vscodeignore
└── engine/  # If applicable
    └── pyproject.toml           # Nuitka config
```

---

## 6. Protection Tools Summary

| Tool | Target | Use Case | Output |
|------|--------|----------|--------|
| **Nuitka** | Python | Engines, backends, CLI utilities | Standalone binary |
| **Bytenode** | Node.js | Frontend apps (Electron renderer) | .jsc bytecode |
| **javascript-obfuscator** | JavaScript | Function libraries | Obfuscated .js |
| **Rust (cargo)** | Rust | Native CLI tools (cli-tool) | Native binary |

---

## 7. Compile-Time Feature Exclusions

Packaged desktop and CLI builds exclude features that are only relevant for cloud/infrastructure deployments. SEGA handles this automatically based on `sega.yaml` configuration.

### 7.1 Excluded Features

| Feature | Reason for Exclusion | Projects Affected |
|---------|---------------------|-------------------|
| **Telemetry Reporter** | No central metrics collection in offline/local mode | All standalone builds |
| **Cloud Telemetry** | Local-only operation, no phone-home | All standalone builds |
| **Remote Job Client** | Optional - local engine execution preferred | Simulation projects |

### 7.2 How SEGA Applies Exclusions

When `distribution.mode: standalone` and exclusions are enabled:

**Python (Nuitka)**:
```bash
# SEGA sets environment variables before Nuitka compilation
SEGA_STANDALONE_BUILD=true SEGA_TELEMETRY_ENABLED=false \
  nuitka --standalone --onefile backend/main.py
```

**Node.js (Bytenode/Webpack)**:
```bash
# SEGA injects defines into webpack config
STANDALONE_BUILD=true TELEMETRY_ENABLED=false \
  npm run build:desktop
```

**Rust (Cargo)**:
```bash
# SEGA uses feature flags
cargo build --release --no-default-features --features standalone
```

### 7.3 Verification

SEGA provides verification commands to confirm exclusions:

```bash
# Verify the telemetry reporter is excluded from compiled binary
sega verify-exclusions my-project --check telemetry_reporter

# Outputs:
# ✓ telemetry_reporter: EXCLUDED (no symbols found)
# ✓ cloud_telemetry: EXCLUDED (no endpoints found)
# ✓ Binary size: 45MB (12MB smaller than cloud build)
```

Manual verification:
```bash
# Rust - check symbols
nm target/release/backend | grep -i telemetry
# Should return nothing

# Python/Nuitka - check strings
strings backend.bin | grep -i telemetry
# Should return nothing

# Node - check bundle
grep -r "telemetry" dist/
# Should return nothing
```

### 7.4 Reference Documentation

For full details on compile-time exclusions:
- **[DISTRIBUTION_STRATEGY.md](/docs/standards/deployment/DISTRIBUTION_STRATEGY.md)** - Section: "Compile-Time Feature Exclusions"
- **[SUBSCRIPTION_SESSION_MANAGEMENT.md](/docs/architecture/desktop/SUBSCRIPTION_SESSION_MANAGEMENT.md)** - Section: "Build Configuration: Telemetry Reporter"

---

## 8. Testing & Validation

### 8.1 Test Matrix

| Project | Desktop | Mobile | IDE | Extension | CLI | Priority |
|---------|---------|--------|-----|-----------|-----|----------|
| my-project | ✓ | ✓ | - | - | - | High |
| cli-tool | ✓ | - | - | - | ✓ | High |
| monitor-tool | ✓ | - | - | - | ✓ | High |
| web-app | ✓ | ✓ | - | - | - | Medium |
| api-service | ✓ | ✓ | - | - | - | Medium |
| func-lib | - | - | - | - | - | Medium |
| ide-fork | - | - | ✓ | ✓ | - | Low |

### 8.2 Validation Commands

```bash
# Test compile without packaging
sega compile my-project --target python --dry-run

# Test full release workflow
sega release my-project --platform desktop --os mac --dry-run

# Verify signing
sega sign --verify my-project --platform mac

# Test IDE build
sega package ide-fork --platform ide --dry-run

# Test extension packaging
sega package my-extension --platform extension --dry-run
```

---

## 9. Success Criteria

- [ ] All 8 simulation engines can produce signed desktop binaries
- [ ] All mobile-enabled projects can produce signed iOS/Android builds
- [ ] CLI utilities can produce cross-platform CLI binaries
- [ ] Function libraries can be obfuscated with javascript-obfuscator
- [ ] IDE builds can be produced from VS Code fork template
- [ ] VS Code extensions can be packaged as .vsix
- [ ] CI/CD templates integrated with GitLab pipelines
- [ ] Documentation updated in `sega/docs/reference/FEATURE_MAP.md`

---

## Related Tasks

- **PKG-DOWNLOAD-001**: Download serving infrastructure (depends on this)
- **BUILD-VERIFY-001**: Build verification (can run in parallel)

---

*This directive implements the compile and packaging features described in the consolidated deployment documentation.*
