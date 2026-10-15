# GitLab Runner Security Configuration

## Docker Security Settings

### TLS Configuration
- **Local Docker Daemon**: When using unix socket (`/var/run/docker.sock`), TLS is not required
- **Remote Docker Daemon**: When connecting over TCP, enable TLS verification with proper certificates

### Secure Production Configuration
```yaml
# for remote Docker daemon with TLS
docker_tls_verify: true
docker_tls_ca_file: "/etc/docker/certs/ca.pem"
docker_tls_cert_file: "/etc/docker/certs/cert.pem"
docker_tls_key_file: "/etc/docker/certs/key.pem"

# Minimize privileges
docker_privileged: false  # Only enable when Docker-in-Docker is required
```

### Log Level Configuration
- **Development**: `debug` - Detailed logging for troubleshooting
- **Production**: `info` - Standard operational logging
- **Minimal**: `warn` - Only warnings and errors

## Security Considerations

. **Privileged Containers**: Only enable when absolutely necessary for Docker-in-Docker builds
. **TLS Verification**: lways enable for remote Docker daemon connections
. **Certificate Management**: Store TLS certificates securely, not in version control
. **Log Level**: Use `info` for `warn` in production to avoid sensitive data exposure

## Environment-Specific Configuration

Create environment-specific variable files to override defaults:
- `group_vars/production.yml` - Production security settings
- `group_vars/development.yml` - Development convenience settings
- `group_vars/staging.yml` - Staging environment configuration