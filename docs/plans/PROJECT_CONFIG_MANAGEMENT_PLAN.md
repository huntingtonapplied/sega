# SEGA Project Configuration Management - Development Plan

**Document Status**: Active Planning Document  
**Created**: 2026-02-21  
**Owner**: SEGA Infrastructure Team  
**Priority**: High  
**Estimated Duration**: 4 weeks  

---

## Executive Summary

Develop a comprehensive configuration management module within SEGA to programmatically control and manage project configurations stored in `projects.json`. This module will provide CLI commands, Python API, and ecosystem integrations for safe, validated configuration updates across all your projects.

**Key Objectives**:
- Enable programmatic project configuration management
- Provide safe write operations with rollback capability
- Integrate with the metrics service (metrics) and the observability dashboard (observatory)
- Maintain `projects.json` as single source of truth

---

## Background & Motivation

### Current State
- **Configuration Storage**: Project metadata stored in `projects.json` (your projects)
- **Manual Editing**: Currently requires hand-editing JSON file
- **No Validation**: Risk of syntax errors, port conflicts, invalid values
- **No Audit Trail**: Changes not logged or tracked
- **Integration Gap**: the metrics service and the observability dashboard don't consume configuration programmatically

### Target State
- **Programmatic Control**: CLI and Python API for configuration management
- **Automated Validation**: Port conflict detection, schema validation, constraint checking
- **Safety Mechanisms**: Backups, rollback, dry-run, atomic updates
- **Ecosystem Integration**: the metrics service metrics updates, the observability dashboard observatory feeds
- **Audit Trail**: Complete history of all configuration changes

### Why SEGA?
SEGA is the infrastructure orchestrator across the portfolio and the natural owner of deployment-related configuration:
- **Infrastructure Ownership**: SEGA manages ports, domains, deployment targets
- **Deployment Integration**: Configuration drives `sega local`, `sega deploy`, `sega ship`
- **Clear Separation**: the metrics service owns metrics, the observability dashboard owns visibility, SEGA owns infrastructure config

---

## Scope

### In Scope
- Read operations for project configuration
- Write operations with validation and safety checks
- Port conflict detection and resolution
- Bulk operations and templating
- Python API for programmatic access
- CLI commands for user interaction
- Integration with existing SEGA config system
- Audit logging and change tracking
- Backup and rollback mechanisms

### Out of Scope (Future Phases)
- REST API for external access (Phase 5+)
- Web-based configuration UI (the observability dashboard integration - future)
- Real-time configuration synchronization across instances
- Configuration versioning with git integration (potential future enhancement)
- Multi-file configuration management (projects.json only for now)

---

## Architecture Overview

### Module Structure
```
sega/
├── engine/sega/config/
│   ├── __init__.py                 # Existing
│   ├── loader.py                   # Existing SEGA config loader
│   ├── schema.py                   # Existing schemas
│   ├── project_config.py           # NEW: projects.json management
│   ├── validators.py               # NEW: Validation rules
│   └── operations.py               # NEW: CRUD operations
├── src/sega/commands/
│   └── config.py                   # NEW: CLI implementation
└── docs/
    ├── plans/PROJECT_CONFIG_MANAGEMENT_PLAN.md  # This document
    └── reference/CONFIG_MANAGEMENT_REFERENCE.md # NEW: User documentation
```

### Data Flow
```
┌─────────────────────┐
│ projects.json   │ ← Single source of truth
│ (the observability dashboard shared) │
└──────────┬──────────┘
           │
           ▼
┌──────────────────────────────────┐
│ SEGA Config Module               │
│ - Parse & validate               │
│ - CRUD operations                │
│ - Backup & rollback              │
└────┬─────────────────┬──────────┘
     │                 │
     ▼                 ▼
┌─────────────┐   ┌──────────────────┐
│ CLI         │   │ Python API       │
│ sega config │   │ ProjectConfig()  │
└─────────────┘   └──────────────────┘
     │                 │
     └────────┬────────┘
              │
              ▼
     ┌────────────────────┐
     │ Ecosystem          │
     │ - the metrics service          │
     │ - the observability dashboard       │
     │ - SEGA deployment  │
     └────────────────────┘
```

### Technology Stack
- **Language**: Python 3.10+
- **CLI Framework**: Click (existing SEGA dependency)
- **Validation**: Pydantic for schema validation
- **File Operations**: Atomic writes with tempfile
- **Locking**: filelock for concurrent access prevention
- **Backup**: JSON snapshots with timestamp rotation
- **Logging**: Python logging with structured audit trail

---

## Phase-by-Phase Implementation Plan

## Phase 1: Foundation & Read Operations (Week 1)

### Objectives
- Establish configuration module architecture
- Implement safe read operations
- Build comprehensive validation system
- Create CLI read commands

### Tasks

#### 1.1 Module Setup (Day 1)
- [ ] Create `engine/sega/config/project_config.py`
- [ ] Create `engine/sega/config/validators.py`
- [ ] Define Pydantic schemas for `projects.json` structure
- [ ] Set up unit test structure

**Files**:
- `engine/sega/config/project_config.py` (new)
- `engine/sega/config/validators.py` (new)
- `tests/unit/config/test_project_config.py` (new)

#### 1.2 Configuration Parser (Day 2)
- [ ] Implement JSON parser with error handling
- [ ] Create ProjectConfig class with read methods
- [ ] Add support for reading from custom paths
- [ ] Handle malformed JSON gracefully

**Key Methods**:
```python
class ProjectConfigManager:
    def __init__(self, config_path: Optional[Path] = None)
    def load_config() -> Dict[str, ProjectMetadata]
    def get_project(slug: str) -> Optional[ProjectMetadata]
    def get_all_projects() -> List[ProjectMetadata]
    def find_projects(filter_fn: Callable) -> List[ProjectMetadata]
```

#### 1.3 Validation System (Day 3)
- [ ] Port conflict detection across all projects
- [ ] Required field validation
- [ ] Status value constraints (demo/development/stealth)
- [ ] Domain format validation
- [ ] Port range validation (per PORT_ALLOCATION_STANDARDS.md)

**Validation Rules**:
- Port uniqueness per service type
- Valid status values
- Domain format (primary_domain, secondary_domain)
- Required fields: id, slug, name, status
- Port ranges: API (8000-8099), Frontend (3000-3099), etc.

#### 1.4 CLI Read Commands (Day 4)
- [ ] Create `src/sega/commands/config.py`
- [ ] Implement `sega config list`
- [ ] Implement `sega config show <project>`
- [ ] Implement `sega config validate`
- [ ] Implement `sega config check-ports`

**CLI Specifications**:
```bash
# List all projects
sega config list
sega config list --status demo
sega config list --format json|table|yaml

# Show specific project
sega config show my-project
sega config show my-project --format json

# Validate configuration
sega config validate
sega config validate --verbose

# Check for port conflicts
sega config check-ports
sega config check-ports --show-conflicts
```

#### 1.5 Testing & Documentation (Day 5)
- [ ] Unit tests for parser
- [ ] Unit tests for validators
- [ ] Integration tests for CLI commands
- [ ] User documentation for read operations
- [ ] Code review and refinement

**Test Coverage Target**: 90%+

### Deliverables
- ✅ Functional read-only configuration module
- ✅ CLI commands for inspection and validation
- ✅ Comprehensive validation system
- ✅ Documentation for Phase 1 features

### Success Criteria
- Can parse `projects.json` without errors
- Port conflicts automatically detected
- All validation rules passing
- CLI commands functional and documented

---

## Phase 2: Safe Write Operations (Week 2)

### Objectives
- Enable controlled configuration updates
- Implement backup and rollback system
- Add safety mechanisms (dry-run, confirmation)
- Support single-field updates

### Tasks

#### 2.1 Backup System (Day 1)
- [ ] Create `engine/sega/config/backup.py`
- [ ] Implement automatic backup before writes
- [ ] Add timestamp-based backup naming
- [ ] Implement backup rotation (keep last 10)
- [ ] Create rollback functionality

**Backup Strategy**:
- Location: `~/.sega/config/backups/`
- Format: `projects.{timestamp}.json`
- Retention: Last 10 backups automatically kept
- Metadata: `.backup_metadata.json` with change info

#### 2.2 Atomic Write Operations (Day 2)
- [ ] Create `engine/sega/config/operations.py`
- [ ] Implement atomic file write (tempfile + rename)
- [ ] Add file locking for concurrent access prevention
- [ ] Create transaction-like update mechanism
- [ ] Add validation before commit

**Write Process**:
1. Acquire file lock
2. Create backup of current config
3. Validate proposed changes
4. Write to temporary file
5. Validate temporary file
6. Atomic rename (temp → actual)
7. Release lock
8. Log change to audit trail

#### 2.3 Update Methods (Day 3)
- [ ] Implement `update_field()` method
- [ ] Implement `update_status()` specialized method
- [ ] Implement `update_ports()` with conflict check
- [ ] Implement `update_visibility()` for home page flags
- [ ] Add dry-run mode for all operations

**Update API**:
```python
class ProjectConfigManager:
    def update_field(slug: str, field: str, value: Any, dry_run: bool = False)
    def update_status(slug: str, status: str, dry_run: bool = False)
    def update_ports(slug: str, ports: Dict[str, int], dry_run: bool = False)
    def update_visibility(slug: str, visibility: Dict[str, bool], dry_run: bool = False)
    def rollback_to_backup(backup_file: str)
```

#### 2.4 CLI Write Commands (Day 4)
- [ ] Implement `sega config set`
- [ ] Implement `sega config rollback`
- [ ] Add confirmation prompts for destructive operations
- [ ] Add `--dry-run` flag for all write commands
- [ ] Add `--force` flag to skip confirmations

**CLI Specifications**:
```bash
# Update single field
sega config set my-project --status demo
sega config set cli-tool --port-api 8017
sega config set my-project --home-featured true
sega config set <project> --field value

# Dry run mode
sega config set my-project --status demo --dry-run

# Rollback
sega config rollback
sega config rollback --to-backup projects.20260221_143022.json
sega config list-backups
```

#### 2.5 Audit Logging & Testing (Day 5)
- [ ] Implement audit log system
- [ ] Log all configuration changes
- [ ] Create `sega config audit-log` command
- [ ] Unit tests for write operations
- [ ] Integration tests for rollback
- [ ] Safety mechanism tests

**Audit Log Format**:
```json
{
  "timestamp": "2026-02-21T14:30:22Z",
  "user": "ubuntu",
  "operation": "update_status",
  "project": "my-project",
  "changes": {
    "status": {"old": "development", "new": "demo"}
  },
  "backup_file": "projects.20260221_143022.json"
}
```

### Deliverables
- ✅ Safe write operations with validation
- ✅ Backup and rollback system
- ✅ CLI commands for updates
- ✅ Audit trail of all changes

### Success Criteria
- Can update individual project fields safely
- Rollback works correctly
- Dry-run mode prevents actual changes
- All writes are atomic and validated
- Audit log captures all changes

---

## Phase 3: Bulk Operations & Templates (Week 3)

### Objectives
- Enable bulk configuration updates
- Support import/export workflows
- Implement configuration diffing
- Create project templates

### Tasks

#### 3.1 Bulk Update System (Day 1-2)
- [ ] Implement bulk update with filtering
- [ ] Add batch validation
- [ ] Support multi-field updates
- [ ] Implement progress reporting for bulk ops

**Bulk Operations API**:
```python
class ProjectConfigManager:
    def bulk_update(filter_fn: Callable, updates: Dict[str, Any], dry_run: bool = False)
    def batch_update(updates: List[Dict], dry_run: bool = False)
```

**CLI Specifications**:
```bash
# Bulk updates with filtering
sega config bulk-set --filter 'status==stealth' --home-featured false
sega config bulk-set --filter 'category==Simulation Engine' --lab-assignment "Example Research Lab"

# Batch updates from file
sega config batch-update ./batch-updates.json --dry-run
```

#### 3.2 Import/Export (Day 2-3)
- [ ] Implement configuration export
- [ ] Implement configuration import with validation
- [ ] Support multiple formats (JSON, YAML)
- [ ] Add merge strategies (replace, update, append)

**CLI Specifications**:
```bash
# Export
sega config export > backup.json
sega config export --format yaml > backup.yaml
sega config export --projects my-project,cli-tool > subset.json

# Import
sega config import ./new-config.json --validate
sega config import ./new-config.json --merge update
sega config import ./new-config.json --dry-run
```

#### 3.3 Configuration Diff (Day 3)
- [ ] Implement diff algorithm
- [ ] Create visual diff output
- [ ] Support comparing files or live config
- [ ] Add summary statistics

**CLI Specifications**:
```bash
# Diff configurations
sega config diff backup.json projects.json
sega config diff backup.json --live
sega config diff --show-all  # Show unchanged fields too
```

#### 3.4 Template System (Day 4)
- [ ] Create project templates directory
- [ ] Implement template application
- [ ] Add preset configurations (stealth→demo, demo→production)
- [ ] Support custom templates

**Template Structure**:
```yaml
# templates/stealth-to-demo.yaml
changes:
  status: demo
  home_carousel: true
  home_featured: true
  
validation:
  require_official_website: true
  require_primary_domain: true
```

**CLI Specifications**:
```bash
# Apply template
sega config apply-template stealth-to-demo --project my-project
sega config apply-template ./custom-template.yaml --project cli-tool
```

#### 3.5 Advanced Queries & Testing (Day 5)
- [ ] Implement advanced filtering/querying
- [ ] Add statistics and reporting
- [ ] Comprehensive test suite for bulk operations
- [ ] Performance testing with all 19+ projects

**CLI Specifications**:
```bash
# Advanced queries
sega config query --status demo --has-desktop
sega config stats
sega config report --format markdown
```

### Deliverables
- ✅ Bulk update capabilities
- ✅ Import/export functionality
- ✅ Configuration diffing
- ✅ Template system

### Success Criteria
- Can update multiple projects in one operation
- Import/export works with validation
- Diff shows clear comparison
- Templates apply correctly

---

## Phase 4: Integration & API (Week 4)

### Objectives
- Finalize Python API
- Integrate with SEGA deployment commands
- Add the metrics service integration hooks
- Prepare the observability dashboard integration
- Production hardening

### Tasks

#### 4.1 Python API Finalization (Day 1)
- [ ] Clean up public API surface
- [ ] Add comprehensive docstrings
- [ ] Create API usage examples
- [ ] Generate API documentation

**Public API**:
```python
from sega.config import ProjectConfigManager

# Initialize
config = ProjectConfigManager()

# Read operations
project = config.get_project('my-project')
all_projects = config.get_all_projects()
demo_projects = config.find_projects(lambda p: p.status == 'demo')

# Write operations
config.update_status('cli-tool', 'demo')
config.update_ports('my-project', {'api': 8009, 'frontend': 3009})
config.bulk_update(lambda p: p.status == 'stealth', {'home_featured': False})

# Utilities
config.validate()
config.check_port_conflicts()
config.export_config('/tmp/backup.json')
config.rollback()
```

#### 4.2 SEGA Integration (Day 2)
- [ ] Integrate with `sega local` (read project config)
- [ ] Integrate with `sega deploy` (deployment target)
- [ ] Integrate with `sega ship` (port allocation)
- [ ] Update project detection to use config

**Integration Points**:
- `sega local up -p my-project` reads ports from config
- `sega deploy` reads deployment_target from config
- `sega ship` validates domains from config

#### 4.3 the metrics service Integration Hooks (Day 3)
- [ ] Add webhook/callback system for config changes
- [ ] Create the metrics service notification on status changes
- [ ] Add metrics update trigger
- [ ] Document the metrics service integration pattern

**Integration Pattern**:
```python
# When project status changes demo → production
# Trigger: Notify the metrics service to update project visibility metrics
# Trigger: Update the observability dashboard observatory display
```

#### 4.4 the observability dashboard Integration Prep (Day 3-4)
- [ ] Define the observability dashboard read-only API endpoints
- [ ] Create project metadata feed
- [ ] Add change notification system
- [ ] Document the observability dashboard integration

**the observability dashboard Integration**:
- the observability dashboard reads `projects.json` directly
- SEGA config changes trigger the observability dashboard refresh
- Admin panel (future) uses SEGA config API

#### 4.5 Production Hardening (Day 4-5)
- [ ] Performance optimization
- [ ] Error handling review
- [ ] Security audit
- [ ] Load testing
- [ ] Documentation polish
- [ ] Final code review

**Production Checklist**:
- [ ] All validation rules enforced
- [ ] File locking prevents corruption
- [ ] Backups working reliably
- [ ] Audit log complete
- [ ] Error messages clear and actionable
- [ ] Performance acceptable (< 100ms for reads)

### Deliverables
- ✅ Stable Python API
- ✅ SEGA deployment integration
- ✅ the metrics service integration hooks
- ✅ the observability dashboard integration prep
- ✅ Production-ready module

### Success Criteria
- Python API documented and stable
- SEGA commands use config module
- the metrics service receives change notifications
- Performance benchmarks met
- Security review passed

---

## Testing Strategy

### Unit Tests
- **Config Parser**: Validate JSON parsing, error handling
- **Validators**: All validation rules tested individually
- **Operations**: CRUD operations, backup/rollback
- **CLI Commands**: All commands with various flags

**Target Coverage**: 90%+

### Integration Tests
- **File System**: Actual file operations, atomic writes
- **CLI Execution**: End-to-end command execution
- **SEGA Integration**: Config used by deployment commands
- **Multi-Project**: Operations across all 19+ projects

### Safety Tests
- **Rollback**: Verify rollback after failed update
- **Atomic Transactions**: Ensure all-or-nothing updates
- **Concurrent Access**: File locking under concurrent writes
- **Data Corruption**: Recovery from invalid JSON

### Performance Tests
- **Read Performance**: < 50ms for single project read
- **Write Performance**: < 200ms for single update
- **Bulk Operations**: < 2s for bulk update of all projects
- **Validation**: < 100ms for full config validation

---

## Risk Management

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Configuration corruption | High | Low | Automatic backups, atomic writes, validation |
| Port conflicts | Medium | Medium | Pre-flight validation, conflict detection |
| Concurrent access issues | Medium | Low | File locking, atomic operations |
| Performance degradation | Low | Low | Performance testing, optimization |
| Integration breaking changes | Medium | Low | Versioned API, deprecation warnings |
| Data loss | High | Very Low | Multiple backup layers, audit trail |

---

## Dependencies

### Internal Dependencies
- SEGA config system (`engine/sega/core/config/`)
- SEGA CLI framework (`src/sega/commands/`)
- Port Allocation Standards (`/docs/standards/infrastructure/PORT_ALLOCATION_STANDARDS.md`)

### External Dependencies
- **Pydantic**: Schema validation
- **filelock**: Concurrent access prevention
- **Click**: CLI framework (existing)
- **tabulate**: Table formatting for CLI output

### Ecosystem Dependencies
- **projects.json**: Must exist at `~/projects/shared/projects.json`
- **the metrics service**: Optional integration for metrics updates
- **the observability dashboard**: Optional integration for observatory feeds

---

## Success Metrics

### Technical Metrics
- **Test Coverage**: > 90%
- **Performance**: Read < 50ms, Write < 200ms
- **Reliability**: Zero data corruption incidents
- **Validation**: 100% of invalid configs caught

### User Metrics
- **Adoption**: All SEGA deployment commands use config module
- **Efficiency**: Configuration updates take < 30 seconds (vs 5+ min manual)
- **Safety**: Zero rollback failures
- **Usability**: Clear error messages, helpful CLI help text

### Ecosystem Metrics
- **Integration**: the metrics service and the observability dashboard consuming config
- **Consistency**: Single source of truth for all project metadata
- **Auditability**: Complete change history for compliance

---

## Timeline

| Week | Phase | Key Milestones |
|------|-------|----------------|
| Week 1 | Foundation | Read operations, validation system, CLI read commands |
| Week 2 | Write Operations | Backup system, atomic writes, CLI write commands, audit log |
| Week 3 | Bulk Operations | Import/export, diffing, templates, advanced queries |
| Week 4 | Integration | Python API, SEGA integration, the metrics service hooks, production hardening |

**Total Duration**: 4 weeks (20 working days)

---

## Resources Required

### Development Team
- **Primary Developer**: 1 full-time (4 weeks)
- **Reviewer**: 1 part-time (code review, testing)
- **Integration Lead**: 1 part-time (the metrics service/the observability dashboard integration)

### Infrastructure
- Development environment with SEGA installed
- Access to `projects.json`
- Test projects for validation

### Documentation
- User documentation for CLI commands
- Python API reference documentation
- Integration guides for the metrics service/the observability dashboard

---

## Post-Implementation

### Maintenance Plan
- Monitor audit logs for unusual patterns
- Review backup rotation and cleanup
- Performance monitoring and optimization
- User feedback collection and iteration

### Future Enhancements (Phase 5+)
- **REST API**: External programmatic access with authentication
- **Web UI**: Integration with the observability dashboard admin panel
- **Git Integration**: Track config changes in version control
- **Advanced Analytics**: Configuration trend analysis
- **Multi-Instance Sync**: Synchronize config across EC2 instances
- **Validation Plugins**: Custom validation rules per project type

---

## Appendix

### A. Configuration Schema

```python
# Pydantic schema for projects.json
class ProjectMetadata(BaseModel):
    id: int
    slug: str
    name: str
    title: str
    lab_assignment: str
    category: str
    description: str
    tagline: str
    image: str
    status: Literal["demo", "development", "stealth"]
    official_website: Optional[str]
    primary_domain: Optional[str]
    secondary_domain: Optional[str]
    whitepaper: Optional[str]
    home_carousel: bool
    home_highlight: Optional[Dict[str, str]]
    home_featured: bool
    port_api: Optional[int]
    port_frontend: Optional[int]
    port_desktop: Optional[int]
    port_mobile: Optional[int]
    port_database: Optional[int]
    port_redis: Optional[int]
    port_metrics: Optional[int]

class ProjectsConfig(BaseModel):
    projects: List[ProjectMetadata]
```

### B. CLI Command Reference

```bash
# Read Operations
sega config list [--status STATUS] [--format json|table|yaml]
sega config show PROJECT [--format json]
sega config validate [--verbose]
sega config check-ports [--show-conflicts]

# Write Operations
sega config set PROJECT --FIELD VALUE [--dry-run] [--force]
sega config rollback [--to-backup BACKUP_FILE]
sega config list-backups

# Bulk Operations
sega config bulk-set --filter EXPRESSION --FIELD VALUE [--dry-run]
sega config batch-update FILE [--dry-run]
sega config export [--format json|yaml] [--projects PROJECT_LIST]
sega config import FILE [--validate] [--merge replace|update] [--dry-run]
sega config diff FILE1 [FILE2|--live] [--show-all]

# Templates
sega config apply-template TEMPLATE --project PROJECT [--dry-run]
sega config list-templates

# Utilities
sega config query --FILTER [--FILTER ...]
sega config stats
sega config report [--format markdown|json]
sega config audit-log [--limit N] [--project PROJECT]
```

### C. References

- **Port Allocation Standards**: `/docs/standards/infrastructure/PORT_ALLOCATION_STANDARDS.md`
- **Project Overview**: `/docs/references/PROJECT_OVERVIEW.md`
- **SEGA CLI Reference**: `~/sega/docs/reference/cli-reference.md`
- **Metrics Integration Architecture**: `~/projects/docs/architecture/METRICS_INTEGRATION.md`

---

**Document Version**: 1.0  
**Last Updated**: 2026-02-21  
**Next Review**: After Phase 1 completion
