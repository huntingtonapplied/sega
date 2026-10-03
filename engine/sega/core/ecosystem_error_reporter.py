#!/usr/bin/env python3
# Copyright 2025 SEGA
"""
Ecosystem Error Reporter
========================
Provides comprehensive error analysis and reporting across all 17 FLEET projects.
"""

import json
import time
import traceback
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
import logging
import yaml
import requests
from ..utils.paths import get_fleet_root


class ErrorSeverity(Enum):
    """Error severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories for classification."""
    DEPENDENCY = "dependency"
    CONFIGURATION = "configuration"
    NETWORK = "network"
    AUTHENTICATION = "authentication"
    DATABASE = "database"
    BUILD = "build"
    DEPLOYMENT = "deployment"
    TESTING = "testing"
    PERFORMANCE = "performance"
    SECURITY = "security"
    INFRASTRUCTURE = "infrastructure"
    DOM_INTERACTION = "dom_interaction"  # E2E browser testing DOM errors
    UNKNOWN = "unknown"


@dataclass
class ErrorContext:
    """Context information for errors."""
    project: str
    operation: str
    environment: str
    timestamp: str
    user: str
    command: str
    working_directory: str
    git_branch: Optional[str] = None
    git_commit: Optional[str] = None
    system_info: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EcosystemError:
    """Comprehensive error representation."""
    error_id: str
    severity: ErrorSeverity
    category: ErrorCategory
    title: str
    description: str
    context: ErrorContext
    stack_trace: Optional[str] = None
    log_excerpt: Optional[str] = None
    related_services: List[str] = field(default_factory=list)
    suggested_fixes: List[str] = field(default_factory=list)
    documentation_links: List[str] = field(default_factory=list)
    similar_errors: List[str] = field(default_factory=list)
    resolution_status: str = "unresolved"
    resolution_notes: Optional[str] = None


@dataclass
class ServiceHealthStatus:
    """Health status of ecosystem services."""
    service_name: str
    status: str  # healthy, degraded, unhealthy, unknown
    last_check: str
    response_time_ms: Optional[float] = None
    error_rate: Optional[float] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EcosystemHealthReport:
    """Comprehensive health report of FLEET ecosystem."""
    timestamp: str
    overall_status: str
    total_projects: int
    healthy_projects: int
    degraded_projects: int
    unhealthy_projects: int
    service_statuses: List[ServiceHealthStatus] = field(default_factory=list)
    recent_errors: List[EcosystemError] = field(default_factory=list)
    performance_metrics: Dict[str, Any] = field(default_factory=dict)


class ErrorPatternAnalyzer:
    """Analyzes error patterns and provides intelligent suggestions."""
    
    def __init__(self):
        self.error_patterns = self._load_error_patterns()
        self.common_fixes = self._load_common_fixes()
    
    def _load_error_patterns(self) -> Dict[str, Dict[str, Any]]:
        """Load known error patterns from configuration."""
        return {
            'protobuf_descriptor_error': {
                'pattern': r'Descriptors cannot be created directly',
                'category': ErrorCategory.DEPENDENCY,
                'severity': ErrorSeverity.ERROR,
                'fixes': [
                    'Set PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python',
                    'Update protobuf version to >=3.19.0,<5.0.0',
                    'Regenerate protobuf files with protoc'
                ],
                'documentation': [
                    'https://developers.google.com/protocol-buffers/docs/news/2022-05-06#python-updates'
                ]
            },
            'module_not_found': {
                'pattern': r'ModuleNotFoundError: No module named \'(.+)\'',
                'category': ErrorCategory.DEPENDENCY,
                'severity': ErrorSeverity.ERROR,
                'fixes': [
                    'Install missing dependency: pip install {module}',
                    'Add dependency to pyproject.toml',
                    'Check virtual environment activation'
                ]
            },
            'port_already_in_use': {
                'pattern': r'Address already in use.*:(\d+)',
                'category': ErrorCategory.INFRASTRUCTURE,
                'severity': ErrorSeverity.WARNING,
                'fixes': [
                    'Kill process using port: lsof -ti:{port} | xargs kill',
                    'Use different port in configuration',
                    'Check for existing service instances'
                ]
            },
            'database_connection_failed': {
                'pattern': r'(could not connect to server|Connection refused).*postgres',
                'category': ErrorCategory.DATABASE,
                'severity': ErrorSeverity.ERROR,
                'fixes': [
                    'Start PostgreSQL service: sega local up',
                    'Check database configuration in .env',
                    'Verify database credentials'
                ]
            },
            'docker_not_running': {
                'pattern': r'Cannot connect to the Docker daemon',
                'category': ErrorCategory.INFRASTRUCTURE,
                'severity': ErrorSeverity.ERROR,
                'fixes': [
                    'Start Docker service: sudo systemctl start docker',
                    'Check Docker installation',
                    'Add user to docker group'
                ]
            },
            'npm_permission_denied': {
                'pattern': r'EACCES.*permission denied.*npm',
                'category': ErrorCategory.CONFIGURATION,
                'severity': ErrorSeverity.WARNING,
                'fixes': [
                    'Use npm with --user flag',
                    'Fix npm permissions: npm config set prefix ~/.npm-global',
                    'Use Node Version Manager (nvm)'
                ]
            },
            'test_timeout': {
                'pattern': r'Test timeout.*exceeded',
                'category': ErrorCategory.TESTING,
                'severity': ErrorSeverity.WARNING,
                'fixes': [
                    'Increase test timeout in configuration',
                    'Check for hanging processes',
                    'Review test performance bottlenecks'
                ]
            },
            # E2E Browser Testing - DOM Interaction Patterns
            'element_not_found': {
                'pattern': r'(Element not found|No element matches selector|waiting for selector)',
                'category': ErrorCategory.DOM_INTERACTION,
                'severity': ErrorSeverity.ERROR,
                'fixes': [
                    'Verify selector is correct: {selector}',
                    'Add data-testid attribute to element for stable selection',
                    'Use more specific selector (avoid generic class names)',
                    'Check if element is rendered conditionally'
                ]
            },
            'element_not_visible': {
                'pattern': r'(Element is not visible|Element is hidden|not visible)',
                'category': ErrorCategory.DOM_INTERACTION,
                'severity': ErrorSeverity.ERROR,
                'fixes': [
                    'Wait for visibility: await page.waitForSelector(selector, {state: "visible"})',
                    'Check CSS display/visibility properties',
                    'Scroll element into view: await element.scrollIntoViewIfNeeded()',
                    'Check if element is inside collapsed accordion or tab'
                ]
            },
            'click_intercepted': {
                'pattern': r'(click intercepted|other element would receive|Element is covered)',
                'category': ErrorCategory.DOM_INTERACTION,
                'severity': ErrorSeverity.ERROR,
                'fixes': [
                    'Close modal or overlay before clicking',
                    'Wait for overlay to disappear: await page.waitForSelector(".overlay", {state: "hidden"})',
                    'Scroll target element into view',
                    'Use force click if appropriate: await element.click({force: true})'
                ]
            },
            'navigation_timeout': {
                'pattern': r'(Navigation timeout|Timeout.*navigation|page\.goto)',
                'category': ErrorCategory.DOM_INTERACTION,
                'severity': ErrorSeverity.ERROR,
                'fixes': [
                    'Check if backend/API is running',
                    'Increase navigation timeout',
                    'Verify base URL is correct',
                    'Check network connectivity to target host'
                ]
            }
        }
    
    def _load_common_fixes(self) -> Dict[str, List[str]]:
        """Load common fixes for different error categories."""
        return {
            ErrorCategory.DEPENDENCY.value: [
                'Check pyproject.toml dependencies',
                'Verify virtual environment activation',
                'Run pip install --user -e .',
                'Clear pip cache: pip cache purge'
            ],
            ErrorCategory.CONFIGURATION.value: [
                'Check .env.example for required variables',
                'Verify file permissions',
                'Review configuration file syntax',
                'Compare with working project configuration'
            ],
            ErrorCategory.INFRASTRUCTURE.value: [
                'Check service status: sega local status',
                'Restart services: sega local down && sega local up',
                'Verify port availability',
                'Check Docker service status'
            ],
            ErrorCategory.DATABASE.value: [
                'Check database connection: sega local status',
                'Review database credentials in .env',
                'Verify database service is running',
                'Check database migration status'
            ],
            ErrorCategory.DOM_INTERACTION.value: [
                'Use data-testid attributes for stable element selection',
                'Wait for element visibility before interaction',
                'Check for overlays/modals that may intercept clicks',
                'Verify frontend is running: sega local status',
                'Run tests in headed mode to debug: sega probe e2e -p PROJECT --headed --debug'
            ]
        }
    
    def analyze_error(self, error_text: str, context: ErrorContext) -> Tuple[ErrorCategory, List[str], List[str]]:
        """Analyze error text and provide category, fixes, and documentation."""
        import re
        
        category = ErrorCategory.UNKNOWN
        suggested_fixes = []
        documentation_links = []
        
        # Check against known patterns
        for pattern_name, pattern_info in self.error_patterns.items():
            if re.search(pattern_info['pattern'], error_text, re.IGNORECASE):
                category = pattern_info['category']
                suggested_fixes.extend(pattern_info.get('fixes', []))
                documentation_links.extend(pattern_info.get('documentation', []))
                break
        
        # Add category-specific common fixes
        if category != ErrorCategory.UNKNOWN:
            common_fixes = self.common_fixes.get(category.value, [])
            suggested_fixes.extend([fix for fix in common_fixes if fix not in suggested_fixes])
        
        # Format fixes with context-specific information
        formatted_fixes = []
        for fix in suggested_fixes:
            formatted_fix = fix.format(
                project=context.project,
                module=self._extract_module_name(error_text),
                port=self._extract_port_number(error_text)
            )
            formatted_fixes.append(formatted_fix)
        
        return category, formatted_fixes, documentation_links
    
    def _extract_module_name(self, error_text: str) -> str:
        """Extract module name from ModuleNotFoundError."""
        import re
        match = re.search(r'No module named \'(.+?)\'', error_text)
        return match.group(1) if match else 'unknown_module'
    
    def _extract_port_number(self, error_text: str) -> str:
        """Extract port number from port-related errors."""
        import re
        match = re.search(r':(\d+)', error_text)
        return match.group(1) if match else 'unknown_port'


class ServiceHealthChecker:
    """Checks health of ecosystem services."""
    
    def __init__(self, fleet_root: Path):
        self.fleet_root = fleet_root
        self.logger = logging.getLogger(__name__)
        
        # Project port mappings (frontend ports for health checks). The project
        # set is the curated `[fleet] app_projects` config list; port VALUES
        # come from config (frontend = 3000 + id).
        # AUTHORITATIVE: /docs/standards/infrastructure/PORT_ALLOCATION_STANDARDS.md
        from sega.core.config import get_config
        _cfg = get_config()
        self.project_ports = {}
        for _name in _cfg.fleet.app_projects:
            _proj = _cfg.get_project(_name)
            if _proj is not None:
                self.project_ports[_name] = _proj.ports.frontend

        # Infrastructure services (+ the telemetry project's TCP protobuf port,
        # if the fleet has one configured)
        self.infrastructure_services = {
            'postgresql': 5432,
            'redis': 6379,
        }
        if _cfg.fleet.telemetry_project:
            self.infrastructure_services[f"{_cfg.fleet.telemetry_project}_tcp"] = (
                _cfg.telemetry.tcp_protobuf_port
            )
    
    async def check_project_health(self, project: str) -> ServiceHealthStatus:
        """Check health of a specific project."""
        start_time = time.time()
        
        try:
            port = self.project_ports.get(project, 3000)
            health_url = f"http://localhost:{port}/health"
            
            response = requests.get(health_url, timeout=5)
            response_time = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                status = "healthy"
                details = response.json() if response.headers.get('content-type', '').startswith('aApplication/json') else {}
            elif response.status_code in [404, 405]:
                # Service is running but no health endpoint
                status = "degraded"
                details = {"note": "Service running but no health endpoint"}
            else:
                status = "unhealthy"
                details = {"http_status": response.status_code}
            
            return ServiceHealthStatus(
                service_name=project,
                status=status,
                last_check=datetime.now().isoformat(),
                response_time_ms=response_time,
                details=details
            )
        
        except requests.exceptions.ConnectionError:
            return ServiceHealthStatus(
                service_name=project,
                status="unhealthy",
                last_check=datetime.now().isoformat(),
                details={"error": "Connection refused - service not running"}
            )
        except requests.exceptions.Timeout:
            return ServiceHealthStatus(
                service_name=project,
                status="degraded",
                last_check=datetime.now().isoformat(),
                response_time_ms=5000,
                details={"error": "Request timeout"}
            )
        except Exception as e:
            return ServiceHealthStatus(
                service_name=project,
                status="unknown",
                last_check=datetime.now().isoformat(),
                details={"error": str(e)}
            )
    
    async def check_infrastructure_health(self) -> List[ServiceHealthStatus]:
        """Check health of infrastructure services."""
        health_statuses = []
        
        for service, port in self.infrastructure_services.items():
            try:
                # Simple port connectivity check
                import socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                result = sock.connect_ex(('localhost', port))
                sock.close()
                
                if result == 0:
                    status = "healthy"
                    details = {"port_accessible": True}
                else:
                    status = "unhealthy"
                    details = {"port_accessible": False, "port": port}
                
                health_statuses.append(ServiceHealthStatus(
                    service_name=service,
                    status=status,
                    last_check=datetime.now().isoformat(),
                    details=details
                ))
            
            except Exception as e:
                health_statuses.append(ServiceHealthStatus(
                    service_name=service,
                    status="unknown",
                    last_check=datetime.now().isoformat(),
                    details={"error": str(e)}
                ))
        
        return health_statuses


class EcosystemErrorReporter:
    """Comprehensive error reporter for the FLEET ecosystem."""
    
    def __init__(self, fleet_root: Optional[str] = None):
        self.fleet_root = Path(fleet_root) if fleet_root else get_fleet_root()
        self.error_analyzer = ErrorPatternAnalyzer()
        self.health_checker = ServiceHealthChecker(self.fleet_root)
        self.logger = logging.getLogger(__name__)
        
        # Error storage
        self.error_history: List[EcosystemError] = []
        self.error_storage_file = self.fleet_root / "sega" / ".sega" / "error_history.json"
        self.error_storage_file.parent.mkdir(exist_ok=True, parents=True)
        
        # Load existing error history
        self._load_error_history()
    
    def report_error(self, exception: Exception, context: ErrorContext) -> EcosystemError:
        """Report an error with full ecosystem context."""
        error_id = self._generate_error_id(exception, context)
        
        # Get stack trace
        stack_trace = traceback.format_exc()
        
        # Analyze error
        category, suggested_fixes, documentation_links = self.error_analyzer.analyze_error(
            str(exception), context
        )
        
        # Determine severity
        severity = self._determine_severity(exception, context)
        
        # Find related services
        related_services = self._find_related_services(exception, context)
        
        # Create error object
        error = EcosystemError(
            error_id=error_id,
            severity=severity,
            category=category,
            title=f"{context.operation} failed in {context.project}",
            description=str(exception),
            context=context,
            stack_trace=stack_trace,
            related_services=related_services,
            suggested_fixes=suggested_fixes,
            documentation_links=documentation_links,
            similar_errors=self._find_similar_errors(exception, context)
        )
        
        # Store error
        self.error_history.append(error)
        self._save_error_history()
        
        self.logger.error(f"Error reported: {error_id}")
        
        return error
    
    async def generate_comprehensive_report(self, project: str = None) -> EcosystemHealthReport:
        """Generate comprehensive health report for the ecosystem."""
        timestamp = datetime.now().isoformat()
        
        # Check health of all projects (or specific project)
        projects_to_check = [project] if project else list(self.health_checker.project_ports.keys())
        service_statuses = []
        
        for proj in projects_to_check:
            health_status = await self.health_checker.check_project_health(proj)
            service_statuses.append(health_status)
        
        # Check infrastructure health
        infra_statuses = await self.health_checker.check_infrastructure_health()
        service_statuses.extend(infra_statuses)
        
        # Calculate overall health metrics
        healthy_count = sum(1 for s in service_statuses if s.status == "healthy")
        degraded_count = sum(1 for s in service_statuses if s.status == "degraded")
        unhealthy_count = sum(1 for s in service_statuses if s.status == "unhealthy")
        
        # Determine overall status
        if unhealthy_count > 0:
            overall_status = "unhealthy"
        elif degraded_count > 0:
            overall_status = "degraded"
        else:
            overall_status = "healthy"
        
        # Get recent errors
        recent_errors = self._get_recent_errors(hours=24)
        
        # Generate performance metrics
        performance_metrics = self._calculate_performance_metrics(service_statuses)
        
        return EcosystemHealthReport(
            timestamp=timestamp,
            overall_status=overall_status,
            total_projects=len(projects_to_check),
            healthy_projects=healthy_count,
            degraded_projects=degraded_count,
            unhealthy_projects=unhealthy_count,
            service_statuses=service_statuses,
            recent_errors=recent_errors,
            performance_metrics=performance_metrics
        )
    
    def get_error_trends(self, days: int = 7) -> Dict[str, Any]:
        """Get error trends over specified time period."""
        cutoff_time = time.time() - (days * 24 * 60 * 60)
        recent_errors = [
            error for error in self.error_history
            if datetime.fromisoformat(error.context.timestamp).timestamp() > cutoff_time
        ]
        
        # Category breakdown
        category_counts = {}
        for error in recent_errors:
            category = error.category.value
            category_counts[category] = category_counts.get(category, 0) + 1
        
        # Project breakdown
        project_counts = {}
        for error in recent_errors:
            project = error.context.project
            project_counts[project] = project_counts.get(project, 0) + 1
        
        # Severity breakdown
        severity_counts = {}
        for error in recent_errors:
            severity = error.severity.value
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        
        return {
            'total_errors': len(recent_errors),
            'time_period_days': days,
            'category_breakdown': category_counts,
            'project_breakdown': project_counts,
            'severity_breakdown': severity_counts,
            'average_errors_per_day': len(recent_errors) / days
        }
    
    def _generate_error_id(self, exception: Exception, context: ErrorContext) -> str:
        """Generate unique error ID."""
        import hashlib
        error_content = f"{context.project}:{context.operation}:{type(exception).__name__}:{str(exception)[:100]}"
        return hashlib.md5(error_content.encode()).hexdigest()[:8]
    
    def _determine_severity(self, exception: Exception, context: ErrorContext) -> ErrorSeverity:
        """Determine error severity based on exception type and context."""
        critical_operations = ['deploy', 'build']
        from .config import get_config
        critical_projects = get_config().critical_projects  # core infrastructure (config-driven)
        
        if isinstance(exception, (SystemExit, KeyboardInterrupt)):
            return ErrorSeverity.CRITICAL
        
        if context.operation in critical_operations:
            return ErrorSeverity.ERROR
        
        if context.project in critical_projects:
            return ErrorSeverity.ERROR
        
        if isinstance(exception, (ImportError, ModuleNotFoundError)):
            return ErrorSeverity.ERROR
        
        if isinstance(exception, (ConnectionError, TimeoutError)):
            return ErrorSeverity.WARNING
        
        return ErrorSeverity.INFO
    
    def _find_related_services(self, exception: Exception, context: ErrorContext) -> List[str]:
        """Find services related to the error."""
        related = []
        
        error_text = str(exception).lower()
        
        if 'postgres' in error_text or 'database' in error_text:
            related.append('postgresql')
        
        if 'redis' in error_text:
            related.append('redis')
        
        # Telemetry/metrics backend (config-named project), if configured
        from sega.core.config import get_config
        _telemetry = get_config().fleet.telemetry_project
        if _telemetry and (_telemetry in error_text or 'metrics' in error_text):
            related.append(_telemetry)


        if 'docker' in error_text:
            related.append('docker')
        
        return related
    
    def _find_similar_errors(self, exception: Exception, context: ErrorContext) -> List[str]:
        """Find similar errors in history."""
        similar = []
        
        for past_error in self.error_history[-10:]:  # Check last 10 errors
            if (past_error.category == context.operation and 
                past_error.context.project == context.project):
                similar.append(past_error.error_id)
        
        return similar
    
    def _get_recent_errors(self, hours: int = 24) -> List[EcosystemError]:
        """Get recent errors within specified hours."""
        cutoff_time = time.time() - (hours * 60 * 60)
        return [
            error for error in self.error_history
            if datetime.fromisoformat(error.context.timestamp).timestamp() > cutoff_time
        ]
    
    def _calculate_performance_metrics(self, service_statuses: List[ServiceHealthStatus]) -> Dict[str, Any]:
        """Calculate performance metrics from service statuses."""
        response_times = [s.response_time_ms for s in service_statuses if s.response_time_ms]
        
        if response_times:
            avg_response_time = sum(response_times) / len(response_times)
            max_response_time = max(response_times)
        else:
            avg_response_time = None
            max_response_time = None
        
        return {
            'average_response_time_ms': avg_response_time,
            'max_response_time_ms': max_response_time,
            'services_checked': len(service_statuses),
            'responsive_services': len([s for s in service_statuses if s.response_time_ms and s.response_time_ms < 1000])
        }
    
    def _load_error_history(self):
        """Load error history from disk."""
        try:
            if self.error_storage_file.exists():
                with open(self.error_storage_file, 'r') as f:
                    data = json.load(f)
                
                # Convert to EcosystemError objects
                for error_data in data:
                    # Convert nested objects
                    error_data['severity'] = ErrorSeverity(error_data['severity'])
                    error_data['category'] = ErrorCategory(error_data['category'])
                    error_data['context'] = ErrorContext(**error_data['context'])
                    
                    self.error_history.append(EcosystemError(**error_data))
        
        except Exception as e:
            self.logger.warning(f"Failed to load error history: {e}")
    
    def _save_error_history(self):
        """Save error history to disk."""
        try:
            # Keep only last 100 errors
            recent_errors = self.error_history[-100:]
            
            # Convert to serializable format
            data = []
            for error in recent_errors:
                error_dict = asdict(error)
                error_dict['severity'] = error.severity.value
                error_dict['category'] = error.category.value
                data.append(error_dict)
            
            with open(self.error_storage_file, 'w') as f:
                json.dump(data, f, indent=2)
        
        except Exception as e:
            self.logger.warning(f"Failed to save error history: {e}")
    
    def export_health_report(self, report: EcosystemHealthReport, format: str = 'json') -> str:
        """Export health report in specified format."""
        if format == 'json':
            return json.dumps(asdict(report), indent=2, default=str)
        
        elif format == 'yaml':
            return yaml.dump(asdict(report), default_flow_style=False)
        
        elif format == 'html':
            return self._generate_html_report(report)
        
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def _generate_html_report(self, report: EcosystemHealthReport) -> str:
        """Generate HTML health report."""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>FLEET Ecosystem Health Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .healthy {{ color: green; }}
                .degraded {{ color: orange; }}
                .unhealthy {{ color: red; }}
                .summary {{ background: #f5f5f5; padding: 15px; border-radius: 5px; }}
                .service {{ margin: 10px 0; padding: 10px; border: 1px solid #ddd; }}
                .error {{ background: #ffebee; padding: 10px; margin: 5px 0; }}
            </style>
        </head>
        <body>
            <h1>FLEET Ecosystem Health Report</h1>
            <div class="summary">
                <h2>Summary</h2>
                <p><strong>Overall Status:</strong> <span class="{report.overall_status}">{report.overall_status.upper()}</span></p>
                <p><strong>Timestamp:</strong> {report.timestamp}</p>
                <p><strong>Projects:</strong> {report.healthy_projects} healthy, {report.degraded_projects} degraded, {report.unhealthy_projects} unhealthy</p>
            </div>
            
            <h2>Service Status</h2>
        """
        
        for service in report.service_statuses:
            html += f"""
            <div class="service">
                <h3>{service.service_name} - <span class="{service.status}">{service.status.upper()}</span></h3>
                <p><strong>Last Check:</strong> {service.last_check}</p>
                {f'<p><strong>Response Time:</strong> {service.response_time_ms}ms</p>' if service.response_time_ms else ''}
                {f'<p><strong>Details:</strong> {service.details}</p>' if service.details else ''}
            </div>
            """
        
        if report.recent_errors:
            html += "<h2>Recent Errors</h2>"
            for error in report.recent_errors[:10]:  # Show last 10 errors
                html += f"""
                <div class="error">
                    <h4>{error.title}</h4>
                    <p><strong>Project:</strong> {error.context.project}</p>
                    <p><strong>Severity:</strong> {error.severity.value}</p>
                    <p><strong>Category:</strong> {error.category.value}</p>
                    <p>{error.description}</p>
                </div>
                """
        
        html += """
        </body>
        </html>
        """
        
        return html