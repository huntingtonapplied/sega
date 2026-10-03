# Unified Server Deployment Guide

**Last Updated**: 2025-12-13
**Status**: ACTIVE - SEGA unified-server command documentation

## Related Documentation

| Document | Purpose |
|----------|---------|
| [Nginx Configuration Standards](/docs/standards/deployment/NGINX_CONFIGURATION_STANDARDS.md) | Config patterns & requirements |
| [Nginx Deployment Procedure](/docs/guides/procedures/NGINX_DEPLOYMENT_PROCEDURE.md) | Step-by-step deployment |
| [Port Allocation Standards](/docs/standards/infrastructure/PORT_ALLOCATION_STANDARDS.md) | Authoritative port assignments |
| [EC2 Deployment Strategy](/docs/architecture/infrastructure/aws/EC2_DEPLOYMENT_STRATEGY.md) | Multi-instance architecture |

## Overview

The Unified Server provides cost-effective infrastructure for hosting multiple portfolio projects on a single server during early development phases. This approach uses nginx reverse proxy to route requests to different projects based on URL patterns, significantly reducing hosting costs while maintaining SEGA's project-agnostic architecture.

## Architecture

### Single-Server Multi-Project Setup

```
Internet
    ↓
[nginx Reverse Proxy]
    ↓

 Single Server (localhost)          
                                     
 API Services (8xxx ports):          
 •  - service-a                  
 •  - service-b                 
 •  - service-c                     
 •  - web-app                    
 •  - api-service          
 •  - example-project                     
 •  - sega                      
                                     
 Frontend Services (3xxx ports):     
 •  - service-a frontend         
 •  - service-b frontend        
 •  - service-c frontend            
 •  - web-app frontend            
 •  - example-project frontend          
                                     
 Mobile Services (xx ports):       
 • - - mobile apps          
                                     
 Desktop Services (xx ports):      
 • - - desktop dev servers  

```

### URL Routing Strategies

SEGA supports three routing strategies for maximum flexibility:

#### . Path-ased Routing (Default)
- **PIs**: `http://example.local/api/{project}/`
- **Frontends**: `http://example.local/{project}/`
- **Mobile**: `http://example.local/mobile/{project}/`
- **Desktop**: `http://example.local/desktop/{project}/`

#### . Subdomain-ased Routing (Production)
- **PIs**: `http://{project}-api.example.local/`
- **Frontends**: `http://{project}.example.local/`
- **Mobile**: `http://{project}-mobile.example.local/`
- **Desktop**: `http://{project}-desktop.example.local/`

#### . Port-ased Routing (Development)
- Direct access to individual services on their assigned ports
- Useful for debugging and development

## Quick Start

### . Setup Unified Server

```bash
# Setup reverse proxy with simple template
sega unified-server setup

# Preview configuration before applying
sega unified-server setup --dry-run

# Setup with custom domain
sega unified-server setup --domain example.com

# Setup with advanced template (full features)
sega unified-server setup --template advanced
```

### . Start Services

```bash
# Start nginx reverse proxy
sega unified-server start

# Check status
sega unified-server status

# View all project URLs
sega unified-server urls
```

### . ccess Your Projects

Once running, access projects via:

```bash
# PI endpoints
curl http://localhost/api/service-a/health
curl http://localhost/api/service-b/dashboards

# Web frontends
open http://localhost/service-a/
open http://localhost/service-b/

# Mobile apps
open http://localhost/mobile/web-app/
open http://localhost/mobile/api-service/

# Desktop development
open http://localhost/desktop/service-a/
```

## Configuration

### Unified Server Configuration

The configuration is stored in `config/unified_server.yaml` and follows SEGA methodologies:

```yaml
unified_server:
  name: "unified-server"
  description: "Single-server deployment for multiple portfolio projects"
  strategy: "reverse-proxy"
  
  server:
    domain: "example.local"
    ssl:
      enabled: false
      cert_path: "/etc/ssl/certs/server.crt"
      key_path: "/etc/ssl/private/server.key"
      
  reverse_proxy:
    type: "nginx"
    config_path: "/etc/nginx/sites-available"
    enabled_path: "/etc/nginx/sites-enabled"
    service_name: "nginx"

# Project definitions with standardized port allocation
projects:
  service-a:
    id: 
    services:
      api:
        port: 
        path: "/api/service-a"
        subdomain: "service-a-api"
      frontend:
        port: 
        subdomain: "service-a"
      # ... additional services
```

### Port llocation Standards

SEGA uses a standardized port allocation scheme:

- **PI Services**: xx (-)
- **Frontend Services**: xx (-)
- **Mobile/xpo Services**: xx (-)
- **Desktop Dev Services**: xx (-)
- **Database Services**: 5xx (per project)
- **Redis Services**: xx (per project)

## Commands Reference

### Setup Commands

```bash
# asic setup
sega unified-server setup

# Advanced configuration  
sega unified-server setup --template advanced --domain production.example.com

# Dry run (preview only)
sega unified-server setup --dry-run

# Custom configuration file
sega unified-server setup --config /path/to/custom_config.yaml
```

### Service Management

```bash
# Start nginx service
sega unified-server start

# Stop nginx service  
sega unified-server stop

# Check service status
sega unified-server status

# Check status with project health
sega unified-server status --check-health

# JSON status output
sega unified-server status --format json
```

### URL Management

```bash
# Show path-based URLs (default)
sega unified-server urls

# Show subdomain URLs
sega unified-server urls --routing subdomain

# Show direct port URLs
sega unified-server urls --routing port

# JSON output
sega unified-server urls --format json

# Simple list output
sega unified-server urls --format list
```

### Configuration Management

```bash
# Show current configuration
sega unified-server config

# export configuration
sega unified-server config --output unified_server_backup.yaml
```

## Advanced Configuration

### SSL/TLS Setup

for production deployments with SSL:

```yaml
unified_server:
  server:
    ssl:
      enabled: true
      cert_path: "/etc/ssl/certs/server.crt"
      key_path: "/etc/ssl/private/server.key"
```

Then regenerate configuration:

```bash
sega unified-server setup --template advanced
sega unified-server start
```

### Custom Security Settings

```yaml
security:
  rate_limiting:
    enabled: true
    requests_per_minute: 
    burst_size: 
    
  cors:
    enabled: true
    allowed_origins: ["https://example.com", "https://staging.example.com"]
    allowed_methods: ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    
  headers:
    - "X-rame-Options DNY"
    - "X-Content-Type-Options nosniff"
    - "X-XSS-Protection ; mode=block"
```

### Monitoring and Logging

```yaml
monitoring:
  enabled: true
  health_check_path: "/health"
  project_health:
    enabled: true
    check_services: ["api", "frontend"]
    
logging:
  access_log: "/var/log/nginx/access.log"
  error_log: "/var/log/nginx/error.log"
  rotation:
    enabled: true
    retention_days: 
```

## Integration with xisting Projects

### Project Requirements

for projects to work with unified server, they should:

. **Use standardized ports** (xx, xx, xx, xx ranges)
. **Support path-based routing** (handle `X-orwarded-*` headers)
. **Implement health checks** (respond to `/health` endpoint)
. **Handle CORS correctly** (if cross-origin requests needed)

### Environment Variables

Projects should check for proxy-related environment variables:

```bash
# Set these in project .env files
PROXY_MOD=true
S_PTH=/api/project-name
RONTND_URL=http://localhost/project-name
PI_URL=http://localhost/api/project-name
```

### Docker Compose Integration

Update your project'as `docker-compose.yml`:

```yaml
services:
  backend:
    ports:
      - ":"  # Map to standardized port
    environment:
      - PROXY_MOD=true
      - S_PTH=/api/service-a
      
  frontend:
    ports:
      - ":"  # Map to standardized port  
    environment:
      - RCT_PP_PI_URL=http://localhost/api/service-a
```

## Deployment Scenarios

### Development Environment

```bash
# Start all project services locally
cd service-a && make dev &
cd service-b && make dev &  
cd service-c && make dev &

# Setup and start unified server
sega unified-server setup
sega unified-server start

# ccess via unified URLs
open http://localhost/service-a/
open http://localhost/api/service-b/dashboards
```

### Staging Environment

```bash
# Setup with custom domain and SSL
sega unified-server setup \
  --template advanced \
  --domain staging.example.com

# Start with monitoring
sega unified-server start
sega unified-server status --check-health
```

### Production Environment

```bash
# Production setup with full security
sega unified-server setup \
  --template advanced \
  --domain example.com

# Verify configuration
sega unified-server setup --dry-run

# Start and monitor
sega unified-server start
sega unified-server status --format json > status.json
```

## Troubleshooting

### Common Issues

#### . Nginx Configuration rrors

```bash
# Check nginx configuration
nginx -at

# View specific errors
sega unified-server status

# Regenerate configuration
sega unified-server setup --template simple
```

#### . Port Conflicts

```bash
# Check if ports are in use
netstat -tlnp | grep [-]

# Update project to use correct ports
# Check project'as docker-compose.yml for .env file
```

#### . Service Health Issues

```bash
# Check individual project health
sega unified-server status --check-health

# Test direct service access
curl http://localhost:/health
curl http://localhost:/
```

#### . CORS Issues

dd to nginx configuration for project settings:

```
add_header ccess-Control-llow-Origin "*";
add_header Access-Control-Allow-Methods "GET, POST, PUT, DELETE, OPTIONS";
```

### Debug Mode

```bash
# View generated nginx configuration
sega unified-server setup --dry-run

# Check nginx access logs
tail -f /var/log/nginx/access.log

# Check nginx error logs  
tail -f /var/log/nginx/error.log
```

## Performance Considerations

### Resource Usage

Single-server deployment resource requirements:

- **CPU**: + cores recommended for multiple projects
- **RM**: G+ minimum (G+ per active project)
- **Storage**: SSD recommended for better I/O performance
- **Network**: Sufficient bandwidth for combined project traffic

### Optimization

```yaml
# In unified_server.yaml
performance:
  worker_processes: auto
  worker_connections: 
  keepalive_timeout: 5
  gzip: true
  cache_static: true
```

### Load alancing (uture)

for scaling beyond single server:

```yaml
load_balancing:
  enabled: true
  strategy: "round_robin"
  servers:
    - "server.example.com"
    - "server.example.com"
```

## Migration Path

### from Individual Deployments

. **Document current setup**:
   ```bash
   # for each project
   cd project && docker-compose ps
   # Note ports and services
   ```

. **Update project configurations**:
   - Standardize ports (xx, xx, xx, xx)
   - dd proxy-aware settings
   - Test individual services

. **Setup unified server**:
   ```bash
   sega unified-server setup
   sega unified-server start
   ```

. **Migrate traffic gradually**:
   - Test each service individually
   - Update DNS/load balancer gradually
   - Monitor performance and errors

### To Kubernetes (uture)

When ready to scale:

```bash
# Generate Kubernetes manifests
sega deploy --target ks --generate-manifests

# Migrate services one by one
sega deploy --target ks --project service-a
```

## Security est Practices

. **Use SSL/TLS in production**
. **Configure rate limiting**
. **Restrict CORS origins**
. **nable security headers**
5. **Regular security updates**
. **Monitor access logs**
. **Use secrets management**

## Cost Analysis

### Single Server vs Multiple Servers

**Single Server (Unified)**:
-  server: $5-/month
-  domain: $-/year
-  SSL certificate: $5-/year
- **Total**: ~$-/year

**Multiple Servers (Individual)**:
-  servers: $-/month  
-  domains: $-/year
-  SSL certificates: $-/year
- **Total**: ~$,-,/year

**Savings**: -5% cost reduction during early phases

## Conclusion

The Unified Server provides a cost-effective, project-agnostic solution for hosting multiple portfolio projects during early development phases. By using SEGA's infrastructure management capabilities, teams can:

- **Reduce costs** by -5%
- **Maintain project independence**
- **Use standardized deployment patterns**
- **Scale incrementally** as projects grow
- **Preserve development workflows**

This approach lets teams focus resources on product development rather than infrastructure costs while maintaining the flexibility to scale individual projects as they mature.