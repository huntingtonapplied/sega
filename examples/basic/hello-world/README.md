# Hello World - Basic SEGA Example

This is the simplest possible example demonstrating core SEGA platform features.

## Features Demonstrated

- **Containerized Deployment**: Docker-based application packaging
- **Health Monitoring**: Built-in health check endpoints
- **Auto-scaling**: Configuration for automatic scaling based on CPU usage
- **Security Scanning**: Dependency and container vulnerability scanning
- **Multi-environment**: Development, staging, and production configurations
- **Blue-green Deployment**: Zero-downtime production deployments

## Prerequisites

- Node.js 20+
- Docker
- SEGA CLI installed

## Quick Start

1. **Clone this example**:
   ```bash
   cp -r examples/basic/hello-world ./my-hello-world
   cd my-hello-world
   ```

2. **Install dependencies**:
   ```bash
   npm install
   ```

3. **Run locally**:
   ```bash
   npm run dev
   ```

4. **Test the application**:
   ```bash
   # View the app
   curl http://localhost:3000

   # Check health
   curl http://localhost:3000/health

   # View detailed status
   curl http://localhost:3000/status
   ```

5. **Run tests**:
   ```bash
   npm test
   ```

6. **Deploy with SEGA**:
   ```bash
   # Initialize SEGA project
   sega init

   # Deploy to development
   sega deploy --target development

   # Deploy to staging
   sega deploy --target staging

   # Deploy to production (requires approval)
   sega deploy --target production
   ```

## Application Endpoints

- `GET /` - Main hello world endpoint
- `GET /health` - Health check (required by SEGA)
- `GET /status` - Detailed application status and SEGA features

## SEGA Configuration

The `sega.yaml` file demonstrates:

- **Project metadata**: Name, type, team, criticality
- **Build configuration**: Docker containerization with multi-stage builds
- **Deployment targets**: Local, staging, and production environments
- **Infrastructure requirements**: CPU, memory, networking, scaling
- **Testing**: Unit, integration, and security tests
- **Security policies**: Vulnerability scanning and compliance
- **Monitoring**: Metrics collection and alerting

## Testing Integration

This example includes comprehensive tests that serve as both:

1. **Unit tests**: Test application functionality
2. **Integration tests**: Validate SEGA platform integration
3. **Security tests**: Verify security scanning capabilities

Tests are automatically run as part of SEGA's CI/CD pipeline.

## Docker Usage

```bash
# Build image
docker build -t sega-hello-world .

# Run container
docker run -p 3000:3000 sega-hello-world

# Run with environment variables
docker run -p 3000:3000 -e NODE_ENV=production sega-hello-world
```

## Environment Variables

- `NODE_ENV`: Application environment (development, staging, production)
- `PORT`: Server port (default: 3000)
- `DEPLOYMENT_STRATEGY`: Deployment strategy used by SEGA
- `AUTO_SCALING`: Auto-scaling status
- `MONITORING`: Monitoring status

## Expected Outputs

### GET /
```json
{
  "message": "Hello World from SEGA Platform!",
  "timestamp": "2026-01-01T00:00:00.000Z",
  "environment": "development",
  "features": [
    "Containerized deployment",
    "Health monitoring",
    "Auto-scaling",
    "Security scanning",
    "Intelligence insights"
  ]
}
```

### GET /health
```json
{
  "status": "healthy",
  "timestamp": "2026-01-01T00:00:00.000Z",
  "version": "1.0.0"
}
```

## Next Steps

After exploring this basic example:

1. Try the `web-app/` examples for more complex applications
2. Explore `ml-pipeline/` examples for AI/ML workflows
3. Check `enterprise/` examples for production-scale deployments
4. Review `hybrid-system/` examples for multi-component projects

## Troubleshooting

### Common Issues

1. **Port already in use**: Change the PORT environment variable
2. **Docker build fails**: Ensure Docker is running and you have internet access
3. **Tests fail**: Run `npm install` to ensure all dependencies are installed
4. **SEGA deployment fails**: Check AWS credentials and cluster configuration

### Getting Help

- Check the main SEGA documentation
- Review the SEGA troubleshooting guide
- Open an issue in the SEGA repository
