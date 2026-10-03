# 06: Product Launch

Deploy consumer packages to distribution channels.

## Desktop Launch

```bash
# 1. Build and package
sega forge build --platform desktop
sega forge package --platform desktop

# 2. Sign for distribution
sega forge sign --os mac
sega forge sign --os win

# 3. Publish to channels
sega forge publish --target github      # GitHub Releases
sega forge publish --target s3          # Direct download

# 4. Verify downloads
curl -I https://releases.example.com/<project>/latest
```

## Mobile Launch

```bash
# 1. Build for stores
sega forge build --platform mobile --profile production

# 2. Submit to stores
sega forge publish --target appstore    # iOS App Store
sega forge publish --target playstore   # Google Play

# 3. OTA updates (Expo)
sega forge publish --target expo --channel production
```

## Web Launch

```bash
# 1. Build optimized bundle
sega forge build --platform web --optimize

# 2. Deploy to CDN/hosting
sega ship deploy --platform web --target production

# 3. Verify deployment
curl -I https://<domain>
```

## Launch Checklist

```bash
# Pre-launch
sega probe run --full              # All tests pass
sega doctor scan --type secrets    # No exposed secrets

# Launch
sega forge release --platform <platform> --target <channel>

# Post-launch
sega sysmon status --all           # Monitor health
sega ship status --watch           # Watch for issues
```
