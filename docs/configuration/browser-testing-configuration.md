# SEGA Browser Testing - Configuration Guide

> **Testing Procedure**: See [TESTING_PROCEDURE.md](../reference/TESTING_PROCEDURE.md#level-6-browser-tests) for browser testing commands.

## Overview

The SEGA Browser Testing framework uses a flexible, project-agnostic configuration system that supports:
- Environment variable expansion
- Project-specific defaults
- Multiple configuration sources
- Runtime overrides

## Configuration Loading Priority

1. **Environment Variables** (highest priority)
2. **Project-specific config.json**
3. **Template defaults**
4. **Built-in defaults** (lowest priority)

## Configuration File Structure

### Basic Configuration (config.json)

```json
{
  "services": {
    "start": "make dev-shared",
    "healthCheck": "http://localhost:3102/api/auth0/health",
    "stop": "make down"
  },
  "testData": {
    "strategy": "api_creation_ui_validation",
    "apiBaseUrl": "http://localhost:3102/api"
  },
  "validation": {
    "tiers": ["static", "dynamic", "integration"],
    "routes": {
      "core": ["/", "/dashboard"],
      "api": ["/api/health"]
    }
  }
}
```

### Environment Variable Expansion

The configuration supports two syntaxes for environment variables:

1. **Simple substitution**: `${VAR_NAME}`
2. **With default value**: `${VAR_NAME:-default_value}`

Example:
```json
{
  "services": {
    "healthCheck": "${HEALTH_URL:-http://localhost:${PORT:-3001}/health}"
  }
}
```

## Project-Specific Defaults

The framework includes built-in defaults for all portfolio projects:

### Port Mappings

| Project | Frontend | Backend | Additional |
|---------|----------|---------|------------|
| web-app | 3102 | 3001 | tcp: 3308 |
| service-a | 3114 | 3001 | - |
| service-b | 3104 | 3001 | - |
| service-c | 3107 | 3001 | - |
| service-d | 3101 | 3001 | - |
| service-e | 3103 | 3001 | - |
| service-f | 3105 | 3001 | - |
| api-service | 3106 | 3001 | - |
| service-g | 3108 | 3001 | - |
| service-h | 3109 | 3001 | - |
| service-i | 3110 | 3001 | - |
| service-j | 3111 | 3001 | - |
| service-k | 3112 | 3001 | - |
| service-l | 3113 | 3001 | - |

### Health Check Paths

Projects can use different health check patterns:
- Default: `/health`
- Auth0: `/api/auth0/health`
- Metrics: `/api/metrics/health`
- Monitoring: `/api/monitoring/health`

## Configuration Sections

### Services Configuration

Controls how the aApplication is started and monitored:

```json
{
  "services": {
    "start": "make dev-shared",
    "healthCheck": "http://localhost:3102/health",
    "stop": "make down",
    "waitForReady": {
      "timeout": 120000,
      "checkInterval": 2000
    }
  }
}
```

### Test Data Configuration

Defines how test data is managed:

```json
{
  "testData": {
    "strategy": "api_creation_ui_validation",
    "resetCommand": "curl -X DELETE http://localhost:3102/api/test-data",
    "seedCommand": "curl -X POST http://localhost:3102/api/test-data/seed",
    "apiBaseUrl": "http://localhost:3102/api",
    "testEntities": {
      "endpoint": "/entities",
      "fields": {
        "name": "name",
        "description": "description"
      }
    }
  }
}
```

### Validation Configuration

Controls the 3-tier validation process:

```json
{
  "validation": {
    "tiers": ["static", "dynamic", "integration"],
    "successCriteria": "database_write_then_ui_read",
    "routes": {
      "core": ["/", "/dashboard", "/metrics"],
      "api": ["/api/health", "/api/metrics"]
    },
    "skipTiers": [],
    "continueOnFailure": false
  }
}
```

### Selectors Configuration

Defines how to find elements in the UI:

```json
{
  "selectors": {
    "usernameField": "input[type='email'], input[name='username']",
    "passwordField": "input[type='password']",
    "loginButton": "button[type='submit']",
    "dashboardLink": "a[href*='dashboard']",
    "dataTable": "table, [role='table']",
    "errorMessage": ".error, .alert-danger",
    "loadingIndicator": ".loading, .spinner"
  }
}
```

### Authentication Configuration

For projects requiring authentication:

```json
{
  "authentication": {
    "enabled": true,
    "provider": "auth0",
    "testUser": {
      "email": "test@example.com",
      "password": "testpassword123"
    },
    "loginUrl": "/login",
    "logoutUrl": "/logout",
    "dashboardUrl": "/dashboard"
  }
}
```

### Browser Configuration

Controls Playwright browser settings:

```json
{
  "browser": {
    "headless": true,
    "slowMo": 0,
    "viewport": {
      "width": 1280,
      "height": 720
    },
    "timeout": 30000,
    "screenshot": {
      "enabled": true,
      "onFailure": true,
      "fullPage": false
    },
    "video": {
      "enabled": false,
      "onFailure": true
    }
  }
}
```

## Using Environment Variables

### Option 1: .env File

Create a `.env` file in your project'as test directory:

```bash
# Project Configuration
PROJECT_NAME=web-app
FRONTEND_PORT=3102
BBACKEND_PORT=3001

# Test Settings
HEADLESS=false
SLOW_MO=100
DEFAULT_TIMEOUT=60000

# Authentication
AUTH_ENABLED=true
TEST_USER_EMAIL=test@web-app.local
```

### Option 2: Export Variables

```bash
export FRONTEND_PORT=3102
export HEALTH_CHECK_URL=http://localhost:3102/api/auth0/health
export HEADLESS=false

sega test browser --project web-app --type validation
```

### Option 3: Inline Variables

```bash
HEADLESS=false SLOW_MO=100 sega test browser --project web-app --debug
```

## Configuration Validation

The framework validates configuration automatically:

```python
from sega.testing.config_handler import BrowserTestConfig

config = BrowserTestConfig('web-app')
validation = config.validate()

if not validation['valid']:
    for issue in validation['issues']:
        print(f"Config issue: {issue}")
```

## Customization Examples

### Example 1: Custom Health Check

```json
{
  "services": {
    "healthCheck": "http://localhost:3102/api/custom/health"
  }
}
```

### Example 2: Custom Test Data Strategy

```json
{
  "testData": {
    "strategy": "ui_only",
    "resetCommand": "make reset-test-db",
    "testEntities": {
      "endpoint": "/api/v2/resources",
      "fields": {
        "title": "title",
        "content": "body",
        "id": "uuid"
      }
    }
  }
}
```

### Example 3: Skip Certain Validation Tiers

```json
{
  "validation": {
    "skipTiers": ["integration"],
    "continueOnFailure": true
  }
}
```

### Example 4: Custom Selectors for Specific UI

```json
{
  "selectors": {
    "usernameField": "#email-input",
    "passwordField": "#password-input",
    "loginButton": ".login-submit-btn",
    "dashboardLink": ".nav-dashboard",
    "metricsPanel": "[data-testid='metrics-widget']"
  }
}
```

## Best Practices

1. **Use Environment Variables for Secrets**
   - Never commit passwords for API keys to config.json
   - Use `.env` files (git-ignored) for sensitive data

2. **Project-Specific Overrides**
   - Start with template defaults
   - Override only what'as different for your project

3. **Consistent Naming**
   - Use uppercase for environment variables
   - Use camelCase in JSON configuration

4. **Validation Routes**
   - Include all critical routes in validation.routes
   - Test both UI routes and API endpoints

5. **Selector Strategy**
   - Prefer data-testid attributes for reliability
   - Provide multiple fallback selectors

## Troubleshooting

### Issue: Configuration not loading

Check file locations in order:
1. `{project}/tests/browser/config.json`
2. `{project}/browser.config.json`
3. `/path/to/sega/templates/browser/config.json`

### Issue: Environment variables not expanding

Ensure proper syntax:
-  `${VAR_NAME}`
-  `${VAR_NAME:-default}`
-  `$VAR_NAME`
-  `$(VAR_NAME)`

### Issue: Wrong ports being used

Check PROJECT_PORTS mapping in:
```
/path/to/sega/engine/sega/probe/config_handler.py
```

### Issue: Health check failing

1. Verify the actual health endpoint:
   ```bash
   curl http://localhost:3102/health
   curl http://localhost:3102/api/health
   curl http://localhost:3102/api/auth0/health
   ```

2. Update config.json:
   ```json
   {
     "services": {
       "healthCheck": "http://localhost:3102/actual/health/path"
     }
   }
   ```

## Migration Guide

### From Hardcoded Configuration

Before:
```json
{
  "services": {
    "healthCheck": "http://localhost:3001/health"
  }
}
```

After:
```json
{
  "services": {
    "healthCheck": "${HEALTH_URL:-http://localhost:${FRONTEND_PORT:-3001}/health}"
  }
}
```

### From Project-Specific Tests

1. Extract project-specific values to config.json
2. Replace hardcoded selectors with configuration
3. Use environment variables for flexibility
4. Test with multiple projects to ensure portability