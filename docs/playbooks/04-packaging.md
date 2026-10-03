# 04: Packaging

Build and package products for distribution.

## Build for Platform

```bash
# Web frontend
sega forge build --platform web

# API/Backend
sega forge build --platform api

# Desktop (Electron)
sega forge build --platform desktop

# Mobile (Expo)
sega forge build --platform mobile
```

## Code Protection (Optional)

```bash
# Python (Nuitka)
sega forge compile --lang python

# Node.js (Bytenode)
sega forge compile --lang node

# JavaScript (Obfuscation)
sega forge compile --lang js
```

## Package for Distribution

```bash
# Desktop packages
sega forge package --platform desktop    # .dmg, .exe, .AppImage

# Mobile packages
sega forge package --platform mobile     # .ipa, .apk
```

## Code Signing

```bash
# macOS
sega forge sign --os mac

# Windows
sega forge sign --os win

# Linux
sega forge sign --os linux
```

## Publish to Registry

```bash
# Docker registry (GitLab)
sega forge publish --target registry

# GitHub Releases
sega forge publish --target github

# S3
sega forge publish --target s3
```

## Full Release Workflow

```bash
# All-in-one: build → package → sign → publish
sega forge release --platform desktop --target github
sega forge release --platform api --target registry
```
