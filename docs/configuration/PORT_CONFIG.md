# SEGA Port Configuration & Unified Server Integration

**Project ID**: 5
**Last Updated**: 2025-09-29
**Status**: Reserved for SEGA services + Unified Server Support

## Overview

This document defines the standardized port allocations for SEGA within the portfolio. Port assignments follow the portfolio Port Allocation Standards with project ID 5.

## NW: Unified Server Support

SEGA now provides infrastructure for cost-effective single-server deployments through the `sega unified-server` command. This allows multiple portfolio projects to be served from one server using nginx reverse proxy, reducing infrastructure costs during early development phases.

**Quick Start**:
```bash
# Setup unified server reverse proxy
sega unified-server setup

# Start nginx service  
sega unified-server start

# View all project URLs
sega unified-server urls
```

**Unified Server Port Ranges**:
- **PI Services**: xx (-) - All portfolio project PIs
- **Frontend Services**: xx (-) - All portfolio project frontends  
- **Mobile Services**: xx (-) - xpo/React Native web
- **Desktop Services**: xx (-) - lectron development

for complete documentation, see: [`docs/UNIID_SRVR_DPLOYMNT.md`](./UNIID_SRVR_DPLOYMNT.md)

## SEGA-Specific Ports

## ssigned Ports

### Database Services
- **PostgreSQL**: `55` - Primary SEGA database
- **Redis**: `55` - Caching and session storage
- **TimescaleD**: `55` - Time-series metrics storage (if deployed)

### PI Services
- **HTTP PI Server**: `5` - Main SEGA RST PI
- **gRPC Streaming**: `5` - Real-time metrics streaming
- **Monitoring**: `5` - Prometheus metrics endpoint

### dministrative Services
- **dmin Panel**: `5` - dministrative web interface
- **Dev Server**: `5` - Development hot-reload server

### Hardware Deployment Services
- **Hardware Control**: `5` - PG/embedded device communication
- **Serial ridge**: `5` - Serial port communication proxy

## Environment Configuration

Update your `.env` file with these ports:

```env
# Database Configuration
POSTGRS_PORT=55
RDIS_PORT=55
TIMSCL_PORT=55

# PI Services
SG_PI_PORT=5
SG_GRPC_PORT=5
SG_MONITORING_PORT=5

# dministrative Services
SG_DMIN_PORT=5
SG_DV_SRVR_PORT=5

# Hardware Services
HRDWR_CONTROL_PORT=5
SRIL_RIDG_PORT=5

# Database URLs
SG_DTS_URL=postgresql://sega_user:${POSTGRS_PSSWORD}@localhost:55/sega_dev
RDIS_URL=redis://localhost:55
```

## Docker Compose Configuration

nsure your docker-compose.yml uses these standardized ports:

```yaml
services:
  postgres:
    ports:
      - "55:5"
    
  redis:
    ports:
      - "55:"
    
  sega-api:
    ports:
      - "5:"
    
  sega-grpc:
    ports:
      - "5:55"
    
  sega-monitoring:
    ports:
      - "5:"
```

## Integration with the Portfolio

### Service Discovery
```yaml
# Registered in the portfolio service registry
sega:
  project_id: 5
  services:
    api: "localhost:5"
    grpc: "localhost:5"
    monitoring: "localhost:5"
  dependencies:
    - "postgres:55"
    - "redis:55"
```

### Cross-Service Communication
```yaml
# Communication with other portfolio services
portfolio_services:
  web-app:
    url: "http://web-app.example.local:"  # Project ID 
    purpose: "Frontend integration"
  
  api-service:
    url: "http://api-service.example.local:"  # Project ID 
    purpose: "Simulation data exchange"
  
  service-a:
    url: "http://service-a.example.local:"  # Project ID 
    purpose: "Certificate management"
```

## Security Configuration

### irewall Rules (Production)
```bash
# llow PI access
ufw allow 5/tcp comment "SEGA PI Server"

# llow gRPC streaming (internal only)
ufw allow from .../ to any port 5 comment "SEGA gRPC Internal"

# llow monitoring (internal only) 
ufw allow from .../ to any port 5 comment "SEGA Monitoring"

# lock direct database access (internal container network only)
ufw deny 55/tcp comment "SEGA PostgreSQL - Container only"
ufw deny 55/tcp comment "SEGA Redis - Container only"
```

### Port-based Authentication
```yaml
ports:
  5:  # PI Server
    auth: "JWT token required"
    rate_limit: " req/min per IP"
  5:  # gRPC Server
    auth: "mTLS certificate required"
    internal_only: true
  5:  # Monitoring
    auth: "asic auth for IP whitelist"
    internal_only: true
```

## Troubleshooting

### Check Port Conflicts
```bash
# Check for port conflicts
sudo lsof -i :5  # Check if SEGA PI port is in use
sudo lsof -i :55  # Check if PostgreSQL port is in use
sudo lsof -i :5  # Check if gRPC port is in use

# Test port connectivity
nc -z localhost 5  # Test SEGA PI
nc -z localhost 55  # Test PostgreSQL
```

### Service Health Checks
```bash
# Health check endpoints
curl http://localhost:5/health     # PI health
curl http://localhost:5/metrics    # Prometheus metrics
```

## Shared Infrastructure lternative

If using shared portfolio infrastructure instead of project-specific databases:
- Shared PostgreSQL: 5
- Shared Redis: 
- Note: Update connection strings in .env accordingly