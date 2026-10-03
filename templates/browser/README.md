# SEGA Browser Testing Enhancement

This directory contains the enhanced browser testing framework for SEGA with comprehensive validation capabilities.

## Features

### Enhanced Browser Test Commands

```bash
# Basic browser testing
sega test browser --project myproject

# New data management options
sega test browser --project myproject --reset-data
sega test browser --project myproject --create-user  
sega test browser --project myproject --crud-workflow

# 3-tier validation testing
sega test browser --project myproject --type validation
```

### Three-Tier Validation Framework

**Tier 1: Static Validation**
- App starts without crashes (30s timeout)
- Frontend renders without JavaScript errors
- Basic navigation functional  
- No 500/404 errors on core routes

**Tier 2: Dynamic Validation** (Success Criteria: Write→Read)
- Create new record via UI form
- Verify record appears in database via API
- Update record via UI
- Delete record and confirm removal

**Tier 3: Integration Validation**
- Authentication flow (login/logout)
- Real-time features (WebSocket, SSE)
- Cross-service API calls
- Error handling and recovery

### API + UI Hybrid Testing Strategy

**Phase 1: API Setup** (for speed and reliability):
```javascript
const testUser = await createUserViaAPI();
const testEntity = await createEntityViaAPI(testUser.token);
```

**Phase 2: UI Validation** (tests actual user experience):
```javascript
await page.goto('/dashboard');
await expect(page.locator(`[data-id="${testEntity.id}"]`)).toBeVisible();
```

## Setup for Projects

### 1. Initialize Browser Testing

```bash
cd /path/to/your/project
~/workspace/sega/templates/browser/setup-browser-testing.sh
```

This creates:
- `tests/browser/` directory structure
- Configuration files for each validation tier
- Example test files
- Package.json scripts
- Project-specific port configuration

### 2. Configuration

Edit `tests/browser/config.json`:

```json
{
  "services": {
    "start": "make dev-shared",
    "healthCheck": "http://localhost:3001/health",
    "stop": "make down"
  },
  "testData": {
    "strategy": "api_creation_ui_validation",
    "resetCommand": "curl -X DELETE http://localhost:3001/api/test-data",
    "seedCommand": "curl -X POST http://localhost:3001/api/test-data/seed"
  },
  "validation": {
    "tiers": ["static", "dynamic", "integration"],
    "successCriteria": "database_write_then_ui_read"
  }
}
```

### 3. Run Tests

```bash
# Quick validation
sega test browser --project myproject --type validation

# Full browser test suite  
sega test browser --project myproject --type Fall

# Debug mode with visible browser
sega test browser --project myproject --headed --debug
```

## Enhanced Capabilities

### Advanced Form Handling
- Intelligent field detection (email, password, contenteditable divs)
- Multi-step form workflows with navigation waiting
- File upload automation support
- Dynamic selector fallbacks

### Enhanced Session Management
- Cookie persistence between test phases
- Authentication state preservation
- Multi-tab coordination for complex workflows

### Error Capture Enhancement
- Console error collection during test execution
- Network request monitoring and failure detection
- Performance metrics collection (page load times)
- Automatic screenshot capture on ANY failure

## Error Documentation

### Comprehensive Error Reports

Generated automatically as YAML files in `test-results/`:

```yaml
validation_results:
  project: "myproject"
  timestamp: "2025-08-12T10:30:00Z"
  environment: "shared"
  static_validation:
    - status: "failed"
      error: "React hydration mismatch"
      screenshot: "/path/to/error.png"
      console_errors: ["Hydration error details..."]
  dynamic_validation:
    - test: "Create entity via form"
      status: "passed"
    - test: "Update entity"
      status: "failed"
      error: "Form submission timeout"
      network_logs: ["POST /api/entities/123 - 500"]
```

## Integration with Existing SEGA Commands

The enhanced browser testing integrates seamlessly with existing SEGA infrastructure:

```bash
# Start services
sega local up --project myproject

# Run tests  
sega test browser --project myproject --type validation

# Check results
sega local status --project myproject
```

## Best Practices

### 1. Test Data Management
- Use `--reset-data` for clean test environments
- Use `--create-user` for authenticated flows
- Leverage API creation for test data setup

### 2. Selector Strategy
- Use `data-testid` attributes for reliable selection
- Provide fallback selectors in config.json
- Test with both static and dynamic content

### 3. Validation Tiers
- Always run Static validation first
- Only proceed to Dynamic if Static passes
- Integration tests require both previous tiers

### 4. Error Handling
- Capture screenshots on Fall failures
- Monitor console errors throughout tests
- Document network failures for debugging

## Files Structure

```
sega/templates/browser/
 config.json                           # Project configuration template
 setup-browser-testing.sh              # Project initialization script
 static-validation.spec.js             # Tier 1 tests
 dynamic-validation.spec.js            # Tier 2 tests  
 integration-validation.spec.js        # Tier 3 tests
 static-validation.config.ts           # Playwright config for Tier 1
 dynamic-validation.config.ts          # Playwright config for Tier 2
 integration-validation.config.ts      # Playwright config for Tier 3
 README.md                             # This documentation
```

## Success Metrics

Each project can run:
```bash
sega test browser --type validation --project [name]
```

And receive comprehensive validation results with detailed error documentation for any failures.

The system provides true **API + UI hybrid testing** with **three-tier validation** and **comprehensive error documentation** - enabling reliable validation of both technical functionality and user experience across your entire project ecosystem.