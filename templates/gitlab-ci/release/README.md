# Release Templates

Artifact release templates for discrete releases (tag-triggered).

## Templates

| Template | Status | Purpose | Output |
|----------|--------|---------|--------|
| `_base.yml` | Planned | Common patterns (versioning, changelog) | - |
| `api.yml` | Planned | API container releases | Docker image |
| `desktop.yml` | Planned | Electron desktop apps | .dmg, .exe, .AppImage |
| `cli.yml` | Planned | CLI binary tools | Standalone binaries |
| `mobile-ios.yml` | Planned | iOS app releases | .ipa → App Store |
| `mobile-android.yml` | Planned | Android app releases | .apk/.aab → Play Store |

## Triggers

Release templates run on:
- Git tags matching `v*.*.*` pattern
- All release jobs are **manual** (require approval)

## Why Separate Templates Per Platform

| Concern | Desktop | CLI | Mobile iOS | Mobile Android |
|---------|---------|-----|------------|----------------|
| Build tool | electron-builder | Nuitka/cargo | Xcode/EAS | Gradle/EAS |
| Runner | macOS | Linux | macOS | Linux |
| Signing | Apple + Windows | GPG | Apple Developer | Play signing key |
| Publish | GitHub/S3 | PyPI/GitHub | App Store | Play Store |

## Usage

```yaml
include:
  - project: 'example/sega'
    file:
      - '/templates/gitlab-ci/release/desktop.yml'

variables:
  PROJECT_NAME: "atlas"
  PUBLISH_TARGET: "github"
```

## SEGA Commands Used

- `sega forge build --platform desktop` - Build Electron app
- `sega forge compile --lang python` - Compile to binary (CLI)
- `sega forge package --platform desktop` - Package for distribution
- `sega forge sign --os mac` - Code signing
- `sega forge publish --target github` - Publish release
- `sega forge release --platform desktop --target github` - Full workflow
