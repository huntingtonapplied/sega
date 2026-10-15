# SEGA Enhanced Shared Infrastructure Implementation Plan

**Objective**: Enhance `sega local up --shared all` to support full-stack native testing with graceful service orchestration, including database services and proper npm process management.

## Current State Analysis

### Existing Capabilities
- ✅ Native environment detection (`~/projects/environments/`)
- ✅ Mixed deployment modes (`--shared backend`, `--project-env frontend`)
- ✅ Basic process management (PID tracking for native processes)
- ✅ Port allocation system (API: 8009, Frontend: 3009, DB: 5009, Redis: 6009)
- ✅ Docker-based shared infrastructure (PostgreSQL, Redis, TimescaleDB)

### Critical Gaps
- ❌ Native database service management
- ❌ Service orchestration for mixed deployments
- ❌ Port offset handling for native services
- ❌ Comprehensive service lifecycle management
- ❌ Seed data management for testing

## Critical Integration Gaps Identified

### CLI Command Structure Integration
- **Missing Commands**: No dedicated CLI commands for shared infrastructure management
- **Command Inconsistency**: Current `--shared` flag lacks integration with shared infrastructure scripts
- **Help System**: CLI reference needs comprehensive updates for new capabilities

### Configuration Management Integration
- **Schema Extension**: `sega.toml` requires schema updates for native database configuration
- **Path Validation**: No validation that shared environment paths exist and are accessible
- **Environment Persistence**: No mechanism to persist preferred deployment modes

### Testing Framework Integration
- **Missing Test Coverage**: No tests for native deployment modes or database management
- **Integration Testing**: Lacks tests for mixed native/Docker deployment scenarios
- **Performance Testing**: No benchmarks for native vs Docker deployment speeds

### Error Handling and Logging Patterns
- **Dependency Resolution**: No specific error handling for database service conflicts
- **Graceful Degradation**: Missing fallback mechanisms when native services fail
- **Health Monitoring**: No comprehensive health check system for native services

### Documentation Updates Required
- **CLI Reference**: Must document new shared infrastructure commands
- **Feature Map**: Needs native deployment capabilities documentation
- **Architecture Documentation**: Requires updates for mixed deployment patterns
- **Troubleshooting**: New section for native deployment issues

## Implementation Architecture

### Phase 1: Native Database Infrastructure (HIGH PRIORITY)

#### 1.1 Native Database Manager
**File**: `engine/sega/local/native_database_manager.py`

**Core Responsibilities**:
- PostgreSQL/TimescaleDB process management via `pg_ctl`
- Redis process management via `redis-server`
- Data directory initialization and migration
- Configuration file generation with port offsets
- Health checks and status monitoring

**Key Methods**:
```python
class NativeDatabaseManager:
    def start_postgresql(self, port: int, data_dir: Path) -> bool
    def start_redis(self, port: int, config_dir: Path) -> bool
    def initialize_database(self, project: str) -> bool
    def stop_database(self, db_type: str) -> bool
    def get_database_status(self) -> Dict[str, ServiceStatus]
```

#### 1.2 Service Process Registry
**File**: `engine/sega/local/service_registry.py`

**Purpose**: Centralized PID and port tracking for all services

**Data Structure**:
```python
@dataclass
class ServiceInfo:
    name: str
    pid: Optional[int]
    port: int
    status: str  # running, stopped, error
    type: str    # native, docker, process
    start_time: datetime
    command: List[str]
```

### Phase 2: Enhanced Service Orchestration (HIGH PRIORITY)

#### 2.1 Mixed Deployment Orchestrator
**File**: `engine/sega/local/mixed_orchestrator.py`

**Responsibilities**:
- Startup order coordination (databases → backend → frontend → engine)
- Dependency management and health checks
- Mixed native/Docker environment handling
- Graceful shutdown with proper cleanup

**Orchestration Flow**:
1. Check for existing services
2. Start databases (native or Docker based on flag)
3. Wait for database health checks
4. Start backend services (shared or project-local)
5. Start frontend processes (npm start)
6. Start engine services (if applicable)
7. Register all services in process registry

#### 2.2 Enhanced Local Manager
**Modification**: `engine/sega/local/manager.py`

**Enhancement Points**:
- Integrate `NativeDatabaseManager`
- Add `MixedOrchestrator` for deployment coordination
- Enhance `--shared all` to include database services
- Add graceful error handling and rollback

### Phase 3: Port Management and Conflict Resolution (MEDIUM PRIORITY)

#### 3.1 Port Allocation Service
**File**: `engine/sega/local/port_manager.py`

**Features**:
- Dynamic port allocation with offset support
- Port conflict detection and resolution
- Service-to-port mapping persistence
- Environment-specific port configurations

#### 3.2 Configuration Generation
**Enhancement**: Update database configuration generation to use dynamic ports

### Phase 4: Frontend Process Management (MEDIUM PRIORITY)

#### 4.1 NPM Process Manager
**File**: `engine/sega/local/npm_manager.py`

**Capabilities**:
- Detect `landing` and `product` app structures
- Manage multiple `npm start` processes simultaneously
- Handle different frontend frameworks (Next.js, React, etc.)
- Monitor build status and hot-reload functionality

#### 4.2 Frontend Service Registry Integration
- Integrate frontend processes into central service registry
- Handle port conflicts for multiple frontend apps
- Provide unified status reporting

### Phase 5: Seed Data Management (MEDIUM PRIORITY)

#### 5.1 Seed Data Manager
**File**: `engine/sega/local/seed_data_manager.py`

**Features**:
- Project-specific seed data detection
- Automated database population
- Test data isolation between projects
- Cleanup and reset capabilities

## Implementation Steps

### Step 1: Native Database Infrastructure (Week 1)
1. Create `NativeDatabaseManager` class
2. Implement PostgreSQL process management
3. Implement Redis process management
4. Add basic configuration file generation
5. Create unit tests for database manager

### Step 2: Service Registry and PID Management (Week 1-2)
1. Implement `ServiceRegistry` with persistent storage
2. Add service status tracking and health checks
3. Create service discovery mechanisms
4. Integrate with existing process management

### Step 3: Mixed Orchestration Implementation (Week 2-3)
1. Create `MixedOrchestrator` class
2. Implement dependency-based startup sequence
3. Add health check coordination
4. Implement graceful shutdown procedures
5. Add error handling and rollback mechanisms

### Step 4: Enhanced Local Manager Integration (Week 3)
1. Modify `manager.py` to use new components
2. Enhance `--shared all` command handling
3. Add native database flags (`--native-db`)
4. Update command-line help and documentation

### Step 5: Port Management Enhancement (Week 4)
1. Implement `PortManager` with conflict resolution
2. Add dynamic port allocation with offsets
3. Update configuration generation for dynamic ports
4. Add port persistence and recovery

### Step 6: Frontend Process Management (Week 4-5)
1. Create `NPMManager` for frontend processes
2. Detect and manage multiple frontend apps
3. Integrate with service registry
4. Add framework-specific handling

### Step 7: Seed Data Implementation (Week 5)
1. Create `SeedDataManager` class
2. Implement project-specific seed data detection
3. Add automated population capabilities
4. Create cleanup and reset procedures

### Step 8: CLI Integration and Command Structure (Week 5-6)
1. **Add Shared Infrastructure Commands**:
   ```bash
   sega shared deps install      # Install shared dependencies
   sega shared deps update       # Update shared dependencies  
   sega shared deps verify       # Verify dependency integrity
   sega shared env status        # Show shared environment status
   sega shared env reset         # Reset shared environments
   ```

2. **Enhance Local Command Integration**:
   - Add `--native-db` flag to `sega local up`
   - Integrate with existing `--shared all` flag
   - Update help documentation and examples

3. **Configuration Schema Updates**:
   ```toml
   [infrastructure.shared_dependencies]
   enabled = true
   native_databases = true
   auto_sync = true
   conflict_resolution = "highest_version"
   health_check_interval = 3600
   
   [infrastructure.native_databases]
   postgresql_enabled = true
   redis_enabled = true
   timescale_enabled = true
   data_directory = "${WORKSPACE_ROOT}/environments/data"
   ```

4. **Create Comprehensive Integration Tests**:
   - Test CLI command integration with native services
   - Test with a representative project and others
   - Performance testing and optimization
   - Documentation integration testing

## Technical Specifications

### Database Configuration Templates

#### PostgreSQL Configuration
```bash
# postgresql.conf template
port = {port}
data_directory = '{data_dir}'
listen_addresses = 'localhost'
max_connections = 100
shared_buffers = 128MB
```

#### Redis Configuration
```bash
# redis.conf template
port {port}
bind 127.0.0.1
appendonly yes
appendfilename "appendonly.aof"
```

### Service Registry Schema
```python
services = {
    'my-project': {
        'backend': ServiceInfo(...),
        'frontend': ServiceInfo(...),
        'engine': ServiceInfo(...),
        'postgres': ServiceInfo(...),
        'redis': ServiceInfo(...),
    }
}
```

### Port Allocation Matrix
```
Base Ports:    DB: 5000, Redis: 6000, API: 8000, Frontend: 3000
Offset 100:    DB: 5100, Redis: 6100, API: 8100, Frontend: 3100
Offset 200:    DB: 5200, Redis: 6200, API: 8200, Frontend: 3200
```

## Success Criteria

### Functional Requirements
- ✅ `sega local up --shared all` starts complete stack without Docker
- ✅ New CLI commands `sega shared deps install/update/verify` work properly
- ✅ Port offsets work for multiple concurrent environments
- ✅ Graceful shutdown stops all services cleanly
- ✅ Service health checks pass for all components
- ✅ Both landing and product apps start correctly
- ✅ Mixed native/Docker deployments work seamlessly

### CLI Integration Requirements
- ✅ All new commands integrate with existing CLI structure
- ✅ Help system updated with comprehensive documentation
- ✅ Command flags work consistently across all `sega` commands
- ✅ Configuration validation in `sega.toml` works properly
- ✅ Error messages follow SEGA's established patterns

### Performance Requirements
- ✅ Full stack startup time < 5 seconds (vs 20+ seconds Docker)
- ✅ Memory usage < 1GB for complete stack
- ✅ Support 3+ concurrent development environments
- ✅ CLI command response time < 1 second

### Testing Requirements
- ✅ 95% code coverage for all new components
- ✅ Integration tests cover mixed deployment scenarios
- ✅ Performance benchmarks show 60-80% improvement over Docker
- ✅ Error handling tested for all failure modes

### Documentation Requirements
- ✅ CLI reference updated with all new commands
- ✅ Feature Map includes native deployment capabilities
- ✅ Architecture documentation updated for mixed deployments
- ✅ Troubleshooting guide covers native deployment issues
- ✅ Configuration schema documented with examples

### Reliability Requirements
- ✅ 99% service start success rate
- ✅ Proper cleanup on process termination
- ✅ Port conflict resolution works reliably
- ✅ Error recovery and rollback mechanisms
- ✅ Graceful degradation when native services unavailable

## Risk Assessment

### High Risk
- **Database corruption**: Improper native database shutdown
  **Mitigation**: Implement graceful shutdown procedures and data backups

### Medium Risk
- **Port conflicts**: Complex port management across multiple services
  **Mitigation**: Comprehensive conflict detection and dynamic allocation

### Low Risk
- **Process management complexity**: Managing many native processes
  **Mitigation**: Centralized service registry with robust PID tracking

## Testing Strategy

### Unit Tests
- Database manager process control
- Service registry operations
- Port allocation logic
- Configuration file generation

### Integration Tests
- Full stack deployment with native databases
- Port offset scenarios
- Mixed deployment configurations
- Error handling and recovery

### Performance Tests
- Startup time benchmarks
- Memory usage profiling
- Concurrent environment testing

## File Structure Changes

### Core Implementation Files
```
engine/sega/local/
├── manager.py                    # Enhanced with native support
├── native_database_manager.py    # NEW: Database process management
├── service_registry.py          # NEW: Centralized service tracking
├── mixed_orchestrator.py        # NEW: Mixed deployment orchestration
├── port_manager.py              # NEW: Port allocation and conflicts
├── npm_manager.py              # NEW: Frontend process management
└── seed_data_manager.py        # NEW: Test data management
```

### CLI Command Integration
```
engine/sega/cli/commands/
├── local.py                     # Enhanced with native flags
├── shared.py                    # NEW: Shared infrastructure commands
└── infrastructure.py            # Enhanced for native database support
```

### Configuration and Templates
```
config/
├── sega.toml                   # Enhanced schema for native databases
└── database_configs/           # NEW: Database configuration templates
    ├── postgresql.conf.j2
    └── redis.conf.j2

templates/
└── shared_infrastructure/      # NEW: Configuration templates
    ├── native_database.yaml.j2
    └── service_registry.yaml.j2
```

### Testing Infrastructure
```
tests/
├── unit/
│   ├── test_native_database_manager.py
│   ├── test_service_registry.py
│   ├── test_mixed_orchestrator.py
│   └── test_port_manager.py
├── integration/
│   ├── test_native_deployment.py
│   ├── test_cli_integration.py
│   └── test_mixed_environments.py
└── performance/
    └── test_native_vs_docker.py
```

## Implementation Timeline

**Week 1**: Native Database Infrastructure + Service Registry
**Week 2**: Mixed Orchestration + Local Manager Integration  
**Week 3**: Port Management + Frontend Process Management
**Week 4**: Seed Data Management + Testing
**Week 5**: Integration Testing + Performance Optimization
**Week 6**: Documentation + Final Testing

## Additional Critical Areas Identified

### SEGA Architecture Integration Points
1. **Workspace Manager Integration**: Must integrate with existing workspace configuration detection
2. **Project Detector Enhancement**: Needs to detect native database requirements
3. **Telemetry Reporter Integration**: Service status reporting must include native services
4. **Resource Manager Integration**: Native database processes must be tracked for resource limits

### Environment Variable Management
1. **WORKSPACE_ROOT Integration**: Must respect existing WORKSPACE_ROOT environment variable
2. **Shared Environment Paths**: Integration with existing `~/projects/environments/` structure
3. **Port Standardization**: Must follow the port allocation standards (API: 8015, DB: 5015, Redis: 6015)
4. **Configuration Expansion**: Environment variable expansion in configuration files

### Security and Permissions
1. **Database Permissions**: Native databases require proper user permissions
2. **Port Access**: Some ports may require elevated privileges
3. **Data Directory Security**: Database data directories need proper permissions
4. **Process Isolation**: Native services need proper isolation from system processes

### Backward Compatibility
1. **Docker Fallback**: Must gracefully fallback to Docker when native fails
2. **Configuration Migration**: Existing configurations must continue working
3. **CLI Compatibility**: Existing commands and flags must remain functional
4. **API Stability**: Internal APIs must maintain backward compatibility

### Monitoring and Observability
1. **Health Check Integration**: Must integrate with existing `sega sysmon` system
2. **Log Aggregation**: Native service logs must integrate with SEGA logging
3. **Metrics Collection**: Performance metrics for native vs Docker deployments
4. **Status Reporting**: Unified status reporting across deployment modes

**Revised Total Implementation Time**: 8 weeks (increased due to integration requirements)

---

**Next Action**: Begin Phase 1 implementation with `NativeDatabaseManager` class creation, ensuring proper integration with existing SEGA architecture patterns.