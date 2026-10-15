#!/usr/bin/env python3
# Copyright 2022-2026 Huntington Applied
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
SEGA Backend Testing Framework
==============================================================================
File: src/sega/testing/backend_test_runners.py
Project: SEGA (Scalable Engineering & Growth Automation)
Copyright: 2022-2025 SEGA
License: Apache-2.0

SEGA MODULE: Testing/Backend Functionality
COMPONENT: Laboratory Backend Test Runners
PURPOSE: Comprehensive backend testing for laboratory projects
DEPENDENCIES: requests, psycopg2, redis, docker
USAGE: Integrated with SEGA TestOrchestrator

Configurable backend testing framework that can work with any laboratory
ecosystem through configuration files rather than hardcoded values.
==============================================================================
"""

import asyncio
import json
import os
import time
import socket
import yaml
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from pathlib import Path
import logging

try:
    import requests
    import psycopg2
    import redis
    import docker
except ImportError as e:
    logging.warning(f"Optional dependency not available: {e}")

from .test_orchestrator import TestResult


@dataclass
class ProjectConfig:
    """Laboratory project configuration for testing"""
    name: str
    project_type: str  # financial, ml, bi, infrastructure, custom
    api_port: int
    db_port: int
    redis_port: int
    db_name: str
    db_user: str
    bBase_path: str
    docker_compose_file: str = "docker-compose.yml"
    custom_endpoints: Optional[List[Dict]] = None
    health_checks: Optional[Dict] = None


@dataclass
class TestMetrics:
    """Enhanced test metrics for backend testing"""
    response_times: Dict[str, float]
    success_rates: Dict[str, float]
    resource_usage: Dict[str, Any]
    error_counts: Dict[str, int]
    performance_benchmarks: Dict[str, float]


class LaboratoryProjectDetector:
    """Detects laboratory project configuration from configuration files"""
    
    def __init__(self, config_path: str = None):
        """Initialize with optional config path"""
        self.config_path = config_path or self._find_config_file()
        self.project_configs = self._load_project_configs()
    
    def _find_config_file(self) -> str:
        """Find the laboratory configuration file"""
        possible_paths = [
            os.path.join(os.getcwd(), "sega_laboratory_config.yaml"),
            os.path.join(os.getcwd(), ".sega", "laboratory_config.yaml"),
            os.path.expanduser("~/.sega/laboratory_config.yaml"),
            "/etc/sega/laboratory_config.yaml",
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        
        # If no config found, create a default fleet config for backward compatibility
        return self._create_default_fleet_config()

    def _build_default_projects(self) -> Dict[str, Dict[str, Any]]:
        """Build the default projects map from central config.

        Membership is the curated `[fleet] probe_fallback_projects` config
        list; ids/ports come from the standard formulas (api = 8000 + id,
        db = 5000 + id, redis = 6000 + id); categories come from the
        `[fleet.project_categories]` map (default "infrastructure").
        AUTHORITATIVE: /docs/standards/infrastructure/PORT_ALLOCATION_STANDARDS.md
        """
        from ..core.config import get_config
        cfg = get_config()
        projects: Dict[str, Dict[str, Any]] = {}
        for name in cfg.fleet.probe_fallback_projects:
            proj = cfg.get_project(name)
            if proj is None:
                continue
            projects[name] = {
                "id": f"{proj.id:02d}",
                "type": cfg.fleet.project_categories.get(name, "infrastructure"),
                "api": proj.ports.api,
                "db": proj.ports.database,
                "redis": proj.ports.redis,
            }
        return projects

    def _create_default_fleet_config(self) -> str:
        """Create a default fleet configuration for backward compatibility"""
        default_config = {
            "laboratory": {
                "name": "FLEET",
                "description": "Huntington Applied",
                "default_project_type": "infrastructure"
            },
            "projects": self._build_default_projects(),
            "project_types": {
                "financial": {
                    "endpoints": [
                        {"path": "/api/v1/payments", "method": "GET", "expected_status": [200, 405], "description": "Payment endpoints"},
                        {"path": "/api/v1/transactions", "method": "GET", "expected_status": [200, 405], "description": "Transaction endpoints"},
                        {"path": "/api/v1/market-data", "method": "GET", "expected_status": [200, 405], "description": "Market data endpoints"}
                    ],
                    "health_checks": {
                        "payment_system": True,
                        "audit_logging": True,
                        "market_data": True
                    }
                },
                "ml": {
                    "endpoints": [
                        {"path": "/api/v1/generate", "method": "GET", "expected_status": [200, 405], "description": "Content generation"},
                        {"path": "/api/v1/models", "method": "GET", "expected_status": [200, 405], "description": "Model endpoints"},
                        {"path": "/api/v1/predictions", "method": "GET", "expected_status": [200, 405], "description": "Prediction endpoints"}
                    ],
                    "health_checks": {
                        "model_loading": True,
                        "inference_pipeline": True,
                        "token_tracking": True
                    }
                },
                "bi": {
                    "endpoints": [
                        {"path": "/api/v1/Analytics", "method": "GET", "expected_status": [200, 405], "description": "Analytics endpoints"},
                        {"path": "/api/v1/reports", "method": "GET", "expected_status": [200, 405], "description": "Report endpoints"},
                        {"path": "/api/v1/dashboards", "method": "GET", "expected_status": [200, 405], "description": "Dashboard endpoints"}
                    ],
                    "health_checks": {
                        "timescaledb": True,
                        "dashboard_data": True,
                        "report_generation": True
                    }
                },
                "infrastructure": {
                    "endpoints": [
                        {"path": "/api/v1/status", "method": "GET", "expected_status": [200, 405], "description": "Status endpoints"},
                        {"path": "/api/v1/metrics", "method": "GET", "expected_status": [200, 405], "description": "Metrics endpoints"}
                    ],
                    "health_checks": {
                        "service_discovery": True,
                        "monitoring": True
                    }
                }
            }
        }
        
        # Create config directory if it doesn't exist
        config_dir = os.path.join(os.getcwd(), ".sega")
        os.makedirs(config_dir, exist_ok=True)
        
        config_file = os.path.join(config_dir, "laboratory_config.yaml")
        with open(config_file, 'w') as f:
            yaml.dump(default_config, f, default_flow_style=False, indent=2)
        
        return config_file
    
    def _load_project_configs(self) -> Dict:
        """Load project configurations from file"""
        try:
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logging.error(f"Failed to load laboratory config from {self.config_path}: {e}")
            return {}
    
    def detect_project_config(self, project_path: str) -> Optional[ProjectConfig]:
        """Detect project configuration from path and config"""
        project_name = Path(project_path).name.lower()
        
        projects = self.project_configs.get("projects", {})
        if project_name not in projects:
            return None
        
        config = projects[project_name]
        project_types = self.project_configs.get("project_types", {})
        
        return ProjectConfig(
            name=project_name,
            project_type=config.get("type", "infrastructure"),
            api_port=config.get("api", 3000),
            db_port=config.get("db", 5432),
            redis_port=config.get("redis", 6379),
            db_name=project_name,
            db_user=f"{project_name}_user",
            bBase_path=project_path,
            custom_endpoints=project_types.get(config.get("type", "infrastructure"), {}).get("endpoints", []),
            health_checks=project_types.get(config.get("type", "infrastructure"), {}).get("health_checks", {})
        )
    
    def get_laboratory_info(self) -> Dict:
        """Get laboratory information"""
        return self.project_configs.get("laboratory", {
            "name": "Unknown Laboratory",
            "description": "Laboratory configuration not found"
        })


class RobustTestExecution:
    """Robust test execution with retry logic and error handling"""
    
    def __init__(self, max_retries: int = 3, backoff_factor: float = 2.0):
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.logger = logging.getLogger(__name__)
    
    async def execute_with_retry(self, test_func, *args, **kwargs) -> Any:
        """Execute test function with exponential backoff retry"""
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                return await test_func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    delay = self.backoff_factor ** attempt
                    self.logger.warning(f"Test attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                else:
                    self.logger.error(f"All {self.max_retries} attempts failed. Last error: {e}")
        
        raise last_exception
    
    def is_service_available(self, host: str, port: int, timeout: float = 5.0) -> bool:
        """Check if service is available on host:port"""
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except (socket.error, socket.timeout):
            return False


class APIEndpointValidator:
    """Validates API endpoints with comprehensive testing"""
    
    def __init__(self, project_config: ProjectConfig):
        self.config = project_config
        self.base_url = f"http://localhost:{project_config.api_port}"
        self.session = requests.Session()
        self.session.timeout = 10.0
        
    async def validate_core_endpoints(self) -> Dict[str, Any]:
        """Validate core API endpoints"""
        results = {}
        
        core_endpoints = [
            ("/health", "GET", 200, "Health endpoint"),
            ("/docs", "GET", 200, "API documentation"),
            ("/openapi.json", "GET", 200, "OpenAPI schema"),
        ]
        
        for endpoint, method, expected_status, description in core_endpoints:
            try:
                start_time = time.time()
                response = self.session.request(method, f"{self.base_url}{endpoint}")
                response_time = (time.time() - start_time) * 1000
                
                results[endpoint] = {
                    "success": response.status_code == expected_status,
                    "status_code": response.status_code,
                    "response_time_ms": response_time,
                    "description": description,
                    "content_type": response.headers.get("content-type", ""),
                }
                
                # Additional validation for health endpoint
                if endpoint == "/health" and response.status_code == 200:
                    try:
                        health_data = response.json()
                        results[endpoint]["health_data"] = health_data
                        results[endpoint]["has_status"] = "status" in health_data
                    except json.JSONDecodeError:
                        results[endpoint]["health_data_error"] = "Invalid JSON response"
                        
            except requests.RequestException as e:
                results[endpoint] = {
                    "success": False,
                    "error": str(e),
                    "description": description,
                }
        
        return results
    
    async def validate_project_specific_endpoints(self) -> Dict[str, Any]:
        """Validate project-specific endpoints based on configuration"""
        results = {}
        
        if not self.config.custom_endpoints:
            return results
        
        for endpoint_config in self.config.custom_endpoints:
            endpoint = endpoint_config.get("path", "")
            method = endpoint_config.get("method", "GET")
            expected_statuses = endpoint_config.get("expected_status", [200])
            description = endpoint_config.get("description", f"{method} {endpoint}")
            
            try:
                start_time = time.time()
                response = self.session.request(method, f"{self.base_url}{endpoint}")
                response_time = (time.time() - start_time) * 1000
                
                success = response.status_code in expected_statuses
                results[endpoint] = {
                    "success": success,
                    "status_code": response.status_code,
                    "response_time_ms": response_time,
                    "description": description,
                }
                
            except requests.RequestException as e:
                results[endpoint] = {
                    "success": False,
                    "error": str(e),
                    "description": description,
                }
        
        return results


class DatabaseValidator:
    """Validates database connectivity and operations"""
    
    def __init__(self, project_config: ProjectConfig):
        self.config = project_config
        
    async def validate_database_connectivity(self) -> Dict[str, Any]:
        """Validate database connectivity and basic operations"""
        results = {}
        
        try:
            # Test PostgreSQL connectivity
            conn_string = f"host=localhost port={self.config.db_port} dbname={self.config.db_name} user={self.config.db_user} password={self.config.db_name}_password"
            
            start_time = time.time()
            conn = psycopg2.connect(conn_string)
            connection_time = (time.time() - start_time) * 1000
            
            cursor = conn.cursor()
            
            # Test basic query
            start_time = time.time()
            cursor.execute("SELECT 1 as test_query")
            result = cursor.fetchone()
            query_time = (time.time() - start_time) * 1000
            
            results["connectivity"] = {
                "success": True,
                "connection_time_ms": connection_time,
                "basic_query_time_ms": query_time,
                "test_result": result[0] if result else None,
            }
            
            # Test schema validation
            cursor.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'")
            table_count = cursor.fetchone()[0]
            
            results["schema"] = {
                "success": True,
                "table_count": table_count,
                "has_tables": table_count > 0,
            }
            
            # Test for TimescaleDB extension (for BI platforms)
            if self.config.project_type == "bi" or self.config.health_checks.get("timescaledb", False):
                try:
                    cursor.execute("SELECT extname FROM pg_extension WHERE extname = 'timescaledb'")
                    timescaledb_result = cursor.fetchone()
                    results["timescaledb"] = {
                        "success": True,
                        "extension_installed": timescaledb_result is not None,
                    }
                except:
                    results["timescaledb"] = {
                        "success": False,
                        "extension_installed": False,
                    }
            
            cursor.close()
            conn.close()
            
        except Exception as e:
            results["connectivity"] = {
                "success": False,
                "error": str(e),
            }
        
        return results


class CacheValidator:
    """Validates Redis cache operations"""
    
    def __init__(self, project_config: ProjectConfig):
        self.config = project_config
        
    async def validate_cache_operations(self) -> Dict[str, Any]:
        """Validate Redis cache connectivity and operations"""
        results = {}
        
        try:
            # Connect to Redis
            r = redis.Redis(host='localhost', port=self.config.redis_port, decode_responses=True)
            
            # Test connectivity
            start_time = time.time()
            ping_result = r.ping()
            ping_time = (time.time() - start_time) * 1000
            
            results["connectivity"] = {
                "success": ping_result,
                "ping_time_ms": ping_time,
            }
            
            if ping_result:
                # Test basic operations
                test_key = f"test_{int(time.time())}"
                test_value = f"test_value_{int(time.time())}"
                
                # Test SET operation
                start_time = time.time()
                set_result = r.set(test_key, test_value, ex=60)
                set_time = (time.time() - start_time) * 1000
                
                # Test GET operation
                start_time = time.time()
                get_result = r.get(test_key)
                get_time = (time.time() - start_time) * 1000
                
                # Test TTL operation
                ttl_result = r.ttl(test_key)
                
                results["operations"] = {
                    "success": set_result and get_result == test_value,
                    "set_time_ms": set_time,
                    "get_time_ms": get_time,
                    "ttl_valid": 50 <= ttl_result <= 60,
                }
                
                # Test memory info
                memory_info = r.info("memory")
                results["memory"] = {
                    "success": True,
                    "used_memory": memory_info.get("used_memory", 0),
                    "used_memory_human": memory_info.get("used_memory_human", "N/A"),
                    "connected_clients": r.info("clients").get("connected_clients", 0),
                }
                
                # Cleanup test key
                r.delete(test_key)
            
        except Exception as e:
            results["connectivity"] = {
                "success": False,
                "error": str(e),
            }
        
        return results


class ServiceHealthValidator:
    """Validates service health and container status"""
    
    def __init__(self, project_config: ProjectConfig):
        self.config = project_config
        
    async def validate_service_health(self) -> Dict[str, Any]:
        """Validate overall service health"""
        results = {}
        
        try:
            # Docker client for container inspection
            client = docker.from_env()
            
            # Check container status
            containers = client.containers.list(filters={"name": self.config.name})
            
            container_status = {}
            for container in containers:
                container_name = container.name
                container_status[container_name] = {
                    "status": container.status,
                    "health": getattr(container.attrs.get("State", {}), "Health", {}).get("Status", "unknown"),
                    "running": container.status == "running",
                }
                
                # Get container stats
                try:
                    stats = container.stats(stream=False)
                    cpu_percent = self._calculate_cpu_percentage(stats)
                    memory_usage = stats["memory_stats"].get("usage", 0)
                    memory_limit = stats["memory_stats"].get("limit", 1)
                    memory_percent = (memory_usage / memory_limit) * 100
                    
                    container_status[container_name].update({
                        "cpu_percent": cpu_percent,
                        "memory_percent": memory_percent,
                        "memory_usage_mb": memory_usage / (1024 * 1024),
                    })
                except:
                    container_status[container_name]["stats_error"] = "Could not retrieve stats"
            
            results["containers"] = {
                "success": len(containers) > 0,
                "container_count": len(containers),
                "details": container_status,
            }
            
            # Check port accessibility
            ports_to_check = [
                ("api", self.config.api_port),
                ("database", self.config.db_port),
                ("redis", self.config.redis_port),
            ]
            
            port_status = {}
            for service_name, port in ports_to_check:
                is_accessible = self._check_port_accessibility("localhost", port)
                port_status[service_name] = {
                    "port": port,
                    "accessible": is_accessible,
                }
            
            results["ports"] = {
                "success": all(status["accessible"] for status in port_status.values()),
                "details": port_status,
            }
            
        except Exception as e:
            results["containers"] = {
                "success": False,
                "error": str(e),
            }
        
        return results
    
    def _calculate_cpu_percentage(self, stats: Dict) -> float:
        """Calculate CPU percentage from Docker stats"""
        try:
            cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - stats["precpu_stats"]["cpu_usage"]["total_usage"]
            system_delta = stats["cpu_stats"]["system_cpu_usage"] - stats["precpu_stats"]["system_cpu_usage"]
            cpu_count = len(stats["cpu_stats"]["cpu_usage"]["percpu_usage"])
            
            if system_delta > 0 and cpu_delta > 0:
                return (cpu_delta / system_delta) * cpu_count * 100.0
        except (KeyError, ZeroDivisionError):
            pass
        return 0.0
    
    def _check_port_accessibility(self, host: str, port: int, timeout: float = 2.0) -> bool:
        """Check if port is accessible"""
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except (socket.error, socket.timeout):
            return False


class BackendTestRunner:
    """Main backend test runner that integrates with SEGA"""
    
    def __init__(self, config_path: str = None):
        self.detector = LaboratoryProjectDetector(config_path)
        self.robust_executor = RobustTestExecution()
        self.logger = logging.getLogger(__name__)
    
    async def run_backend_functionality_tests(self, project_path: str, project_type: str) -> TestResult:
        """Run comprehensive backend functionality tests"""
        start_time = time.time()
        
        # Get laboratory info
        lab_info = self.detector.get_laboratory_info()
        lab_name = lab_info.get("name", "Laboratory")
        
        # Detect project configuration
        project_config = self.detector.detect_project_config(project_path)
        if not project_config:
            return TestResult(
                success=False,
                test_type="backend-functionality",
                duration=0.0,
                output="",
                error=f"Unknown {lab_name} project in path: {project_path}",
            )
        
        # Execute all backend functionality tests
        all_results = {}
        overall_success = True
        
        try:
            # API endpoint validation
            api_validator = APIEndpointValidator(project_config)
            api_results = await self.robust_executor.execute_with_retry(
                api_validator.validate_core_endpoints
            )
            api_specific_results = await self.robust_executor.execute_with_retry(
                api_validator.validate_project_specific_endpoints
            )
            all_results["api_endpoints"] = {**api_results, **api_specific_results}
            
            # Database validation
            db_validator = DatabaseValidator(project_config)
            db_results = await self.robust_executor.execute_with_retry(
                db_validator.validate_database_connectivity
            )
            all_results["database"] = db_results
            
            # Cache validation
            cache_validator = CacheValidator(project_config)
            cache_results = await self.robust_executor.execute_with_retry(
                cache_validator.validate_cache_operations
            )
            all_results["cache"] = cache_results
            
            # Service health validation
            health_validator = ServiceHealthValidator(project_config)
            health_results = await self.robust_executor.execute_with_retry(
                health_validator.validate_service_health
            )
            all_results["service_health"] = health_results
            
            # Determine overall success
            overall_success = self._evaluate_overall_success(all_results)
            
        except Exception as e:
            self.logger.exception(f"Backend functionality tests failed for {project_config.name}")
            overall_success = False
            all_results["error"] = str(e)
        
        duration = time.time() - start_time
        
        # Generate summary
        summary = self._generate_test_summary(project_config, all_results, overall_success, lab_name)
        
        # Calculate metrics
        metrics = self._calculate_test_metrics(all_results)
        
        return TestResult(
            success=overall_success,
            test_type="backend-functionality",
            duration=duration,
            output=summary,
            error=None if overall_success else "Some backend functionality tests failed",
            metrics=metrics,
        )
    
    def _evaluate_overall_success(self, results: Dict[str, Any]) -> bool:
        """Evaluate overall test success from individual results"""
        critical_tests = ["api_endpoints", "database", "service_health"]
        
        for test_category in critical_tests:
            if test_category not in results:
                return False
            
            category_results = results[test_category]
            if isinstance(category_results, dict):
                # Check if any critical endpoints/operations failed
                if test_category == "api_endpoints":
                    critical_endpoints = ["/health", "/docs"]
                    for endpoint in critical_endpoints:
                        if endpoint in category_results and not category_results[endpoint].get("success", False):
                            return False
                elif test_category == "database":
                    if not category_results.get("connectivity", {}).get("success", False):
                        return False
                elif test_category == "service_health":
                    if not category_results.get("containers", {}).get("success", False):
                        return False
        
        return True
    
    def _generate_test_summary(self, config: ProjectConfig, results: Dict[str, Any], success: bool, lab_name: str) -> str:
        """Generate human-readable test summary"""
        lines = [
            f"{lab_name} Backend Functionality Test Results for {config.name.upper()}",
            f"Project Type: {config.project_type}",
            f"Overall Status: {' PASS' if success else ' FAIL'}",
            "",
        ]
        
        # API endpoints summary
        if "api_endpoints" in results:
            api_results = results["api_endpoints"]
            successful_endpoints = sum(1 for r in api_results.values() if r.get("success", False))
            total_endpoints = len(api_results)
            lines.append(f"API Endpoints: {successful_endpoints}/{total_endpoints} successful")
            
            for endpoint, result in api_results.items():
                status = "" if result.get("success", False) else ""
                response_time = result.get("response_time_ms", 0)
                lines.append(f"  {status} {endpoint} ({response_time:.1f}ms)")
        
        # Database summary
        if "database" in results:
            db_results = results["database"]
            db_success = db_results.get("connectivity", {}).get("success", False)
            lines.append(f"Database: {' Connected' if db_success else ' Failed'}")
            
            if db_success:
                conn_time = db_results.get("connectivity", {}).get("connection_time_ms", 0)
                table_count = db_results.get("schema", {}).get("table_count", 0)
                lines.append(f"  Connection time: {conn_time:.1f}ms")
                lines.append(f"  Tables found: {table_count}")
        
        # Cache summary
        if "cache" in results:
            cache_results = results["cache"]
            cache_success = cache_results.get("connectivity", {}).get("success", False)
            lines.append(f"Cache: {' Connected' if cache_success else ' Failed'}")
            
            if cache_success:
                ping_time = cache_results.get("connectivity", {}).get("ping_time_ms", 0)
                lines.append(f"  Ping time: {ping_time:.1f}ms")
        
        # Service health summary
        if "service_health" in results:
            health_results = results["service_health"]
            container_count = health_results.get("containers", {}).get("container_count", 0)
            lines.append(f"Containers: {container_count} running")
        
        return "\n".join(lines)
    
    def _calculate_test_metrics(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate test metrics from results"""
        metrics = {
            "endpoints_tested": 0,
            "endpoints_successful": 0,
            "avg_response_time_ms": 0.0,
            "database_connected": False,
            "cache_connected": False,
            "containers_running": 0,
        }
        
        # API metrics
        if "api_endpoints" in results:
            api_results = results["api_endpoints"]
            metrics["endpoints_tested"] = len(api_results)
            metrics["endpoints_successful"] = sum(1 for r in api_results.values() if r.get("success", False))
            
            response_times = [r.get("response_time_ms", 0) for r in api_results.values() if "response_time_ms" in r]
            if response_times:
                metrics["avg_response_time_ms"] = sum(response_times) / len(response_times)
        
        # Database metrics
        if "database" in results:
            metrics["database_connected"] = results["database"].get("connectivity", {}).get("success", False)
        
        # Cache metrics
        if "cache" in results:
            metrics["cache_connected"] = results["cache"].get("connectivity", {}).get("success", False)
        
        # Container metrics
        if "service_health" in results:
            metrics["containers_running"] = results["service_health"].get("containers", {}).get("container_count", 0)
        
        return metrics


# Integration function for SEGA TestOrchestrator
def create_backend_test_runners(config_path: str = None) -> Dict[str, callable]:
    """Create backend test runners for integration with SEGA TestOrchestrator"""
    runner = BackendTestRunner(config_path)
    
    return {
        "backend-functionality": lambda project_path, project_type: asyncio.run(
            runner.run_backend_functionality_tests(project_path, project_type)
        ),
        "health-validation": lambda project_path, project_type: asyncio.run(
            runner.run_backend_functionality_tests(project_path, project_type)
        ),
        "service-integration": lambda project_path, project_type: asyncio.run(
            runner.run_backend_functionality_tests(project_path, project_type)
        ),
    }