#!/usr/bin/env python3
# Copyright 2025 SEGA
"""
Optimized Resource Manager
==========================
Advanced resource management for FLEET ecosystem shared infrastructure.
"""

import os
import json
import time
import psutil
import threading
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging
import yaml
from ..utils.paths import get_fleet_root


class ResourceType(Enum):
    """Types of resources managed by SEGA."""
    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    NETWORK = "network"
    DATABASE_CONNECTIONS = "database_connections"
    DOCKER_CONTAINERS = "docker_containers"
    PORT = "port"


class ResourceStatus(Enum):
    """Status of resource allocation."""
    AVAILABLE = "available"
    ALLOCATED = "allocated"
    RESERVED = "reserved"
    OVERCOMMITTED = "overcommitted"
    EXHAUSTED = "exhausted"


@dataclass
class ResourceAllocation:
    """Represents a resource allocation."""
    allocation_id: str
    project: str
    resource_type: ResourceType
    amount: float
    allocated_at: datetime
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ResourceQuota:
    """Resource quota for projects."""
    project: str
    cpu_cores: float = 2.0
    memory_mb: float = 1024.0
    disk_mb: float = 5120.0
    max_containers: int = 5
    max_ports: int = 10
    max_db_connections: int = 20


@dataclass
class SystemResourceSnapshot:
    """Snapshot of system resources."""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_available_mb: float
    disk_usage_percent: float
    disk_free_mb: float
    load_average: Tuple[float, float, float]
    active_connections: int
    docker_stats: Dict[str, Any] = field(default_factory=dict)


class ResourceMonitor:
    """Monitors system resource usage in real-time."""
    
    def __init__(self, update_interval: float = 5.0):
        self.update_interval = update_interval
        self.current_snapshot: Optional[SystemResourceSnapshot] = None
        self.snapshots_history: List[SystemResourceSnapshot] = []
        self.max_history = 288  # 24 hours at 5-minute intervals
        self.monitor_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.logger = logging.getLogger(__name__)
    
    def start_monitoring(self):
        """Start resource monitoring in background thread."""
        if self.monitor_thread and self.monitor_thread.is_alive():
            return
        
        self.stop_event.clear()
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        self.logger.info("Resource monitoring started")
    
    def stop_monitoring(self):
        """Stop resource monitoring."""
        self.stop_event.set()
        if self.monitor_thread:
            self.monitor_thread.join(timeout=10)
        self.logger.info("Resource monitoring stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop."""
        while not self.stop_event.wait(self.update_interval):
            try:
                snapshot = self._take_snapshot()
                self.current_snapshot = snapshot
                
                # Add to history
                self.snapshots_history.append(snapshot)
                
                # Trim history
                if len(self.snapshots_history) > self.max_history:
                    self.snapshots_history = self.snapshots_history[-self.max_history:]
                
            except Exception as e:
                self.logger.error(f"Error taking resource snapshot: {e}")
    
    def _take_snapshot(self) -> SystemResourceSnapshot:
        """Take a snapshot of current system resources."""
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # Memory usage
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        memory_available_mb = memory.available / 1024 / 1024
        
        # Disk usage
        disk = psutil.disk_usage('/')
        disk_usage_percent = (disk.used / disk.total) * 100
        disk_free_mb = disk.free / 1024 / 1024
        
        # Load average
        load_average = os.getloadavg()
        
        # Network connections
        active_connections = len(psutil.net_connections())
        
        # Docker stats
        docker_stats = self._get_docker_stats()
        
        return SystemResourceSnapshot(
            timestamp=datetime.now(),
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            memory_available_mb=memory_available_mb,
            disk_usage_percent=disk_usage_percent,
            disk_free_mb=disk_free_mb,
            load_average=load_average,
            active_connections=active_connections,
            docker_stats=docker_stats
        )
    
    def _get_docker_stats(self) -> Dict[str, Any]:
        """Get Docker container statistics."""
        try:
            # Get running containers
            result = subprocess.run(
                ['docker', 'stats', '--no-stream', '--format', 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}'],
                capture_output=True, text=True, timeout=5
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')[1:]  # Skip header
                containers = []
                
                for line in lines:
                    if line.strip():
                        parts = line.split('\t')
                        if len(parts) >= 4:
                            containers.append({
                                'name': parts[0],
                                'cpu_percent': parts[1],
                                'memory_usage': parts[2],
                                'network_io': parts[3]
                            })
                
                return {
                    'running_containers': len(containers),
                    'containers': containers
                }
        
        except Exception as e:
            self.logger.debug(f"Could not get Docker stats: {e}")
        
        return {'running_containers': 0, 'containers': []}
    
    def get_resource_trends(self, hours: int = 1) -> Dict[str, Any]:
        """Get resource usage trends over specified hours."""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_snapshots = [
            s for s in self.snapshots_history
            if s.timestamp >= cutoff_time
        ]
        
        if not recent_snapshots:
            return {}
        
        cpu_values = [s.cpu_percent for s in recent_snapshots]
        memory_values = [s.memory_percent for s in recent_snapshots]
        
        return {
            'time_period_hours': hours,
            'snapshots_count': len(recent_snapshots),
            'cpu': {
                'average': sum(cpu_values) / len(cpu_values),
                'max': max(cpu_values),
                'min': min(cpu_values),
                'current': recent_snapshots[-1].cpu_percent
            },
            'memory': {
                'average': sum(memory_values) / len(memory_values),
                'max': max(memory_values),
                'min': min(memory_values),
                'current': recent_snapshots[-1].memory_percent
            }
        }


class PortManager:
    """Manages port allocations for FLEET projects."""
    
    def __init__(self):
        self.allocated_ports: Dict[int, str] = {}
        self.project_ports: Dict[str, List[int]] = {}
        self.port_ranges = {
            'api': (3001, 3099),
            'frontend': (3101, 3199),
            'expo_web': (3201, 3299),
            'desktop_dev': (3301, 3399),
            'database': (5001, 5099),
            'redis': (6001, 6099),
            'monitoring': (8001, 8099),
            'custom': (9001, 9999)
        }
        self.logger = logging.getLogger(__name__)
    
    def allocate_port(self, project: str, port_type: str = 'custom', 
                     preferred_port: Optional[int] = None) -> Optional[int]:
        """Allocate a port for a project."""
        if port_type not in self.port_ranges:
            raise ValueError(f"Unknown port type: {port_type}")
        
        start_port, end_port = self.port_ranges[port_type]
        
        # Try preferred port first
        if preferred_port and start_port <= preferred_port <= end_port:
            if self._is_port_available(preferred_port):
                self._allocate_port_to_project(project, preferred_port)
                return preferred_port
        
        # Find next available port in range
        for port in range(start_port, end_port + 1):
            if self._is_port_available(port):
                self._allocate_port_to_project(project, port)
                return port
        
        return None
    
    def releBase_port(self, port: int):
        """ReleBase a port allocation."""
        if port in self.allocated_ports:
            project = self.allocated_ports[port]
            del self.allocated_ports[port]
            
            if project in self.project_ports:
                self.project_ports[project].remove(port)
                if not self.project_ports[project]:
                    del self.project_ports[project]
            
            self.logger.info(f"ReleBased port {port} from project {project}")
    
    def releBase_project_ports(self, project: str):
        """ReleBase all ports allocated to a project."""
        if project in self.project_ports:
            ports_to_releBase = self.project_ports[project].copy()
            for port in ports_to_releBase:
                self.releBase_port(port)
    
    def _is_port_available(self, port: int) -> bool:
        """Check if port is available."""
        if port in self.allocated_ports:
            return False
        
        # Check if port is actually free on the system
        import socket
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(('localhost', port))
            sock.close()
            return True
        except OSError:
            return False
    
    def _allocate_port_to_project(self, project: str, port: int):
        """Allocate port to project."""
        self.allocated_ports[port] = project
        
        if project not in self.project_ports:
            self.project_ports[project] = []
        
        self.project_ports[project].append(port)
        self.logger.info(f"Allocated port {port} to project {project}")
    
    def get_port_status(self) -> Dict[str, Any]:
        """Get port allocation status."""
        return {
            'allocated_ports': len(self.allocated_ports),
            'project_count': len(self.project_ports),
            'port_ranges': self.port_ranges,
            'allocations': dict(self.allocated_ports),
            'project_ports': dict(self.project_ports)
        }


class DatabaseConnectionPool:
    """Manages database connection pools for projects."""
    
    def __init__(self, max_total_connections: int = 100):
        self.max_total_connections = max_total_connections
        self.project_pools: Dict[str, Dict[str, Any]] = {}
        self.total_allocated = 0
        self.logger = logging.getLogger(__name__)
    
    def allocate_pool(self, project: str, db_type: str = 'postgresql', 
                     max_connections: int = 10) -> bool:
        """Allocate connection pool for project."""
        if self.total_allocated + max_connections > self.max_total_connections:
            self.logger.warning(f"Cannot allocate {max_connections} connections for {project} "
                              f"(would exceed limit of {self.max_total_connections})")
            return False
        
        pool_key = f"{project}_{db_type}"
        self.project_pools[pool_key] = {
            'project': project,
            'db_type': db_type,
            'max_connections': max_connections,
            'allocated_at': datetime.now(),
            'active_connections': 0
        }
        
        self.total_allocated += max_connections
        self.logger.info(f"Allocated {max_connections} {db_type} connections for {project}")
        return True
    
    def releBase_pool(self, project: str, db_type: str = 'postgresql'):
        """ReleBase connection pool for project."""
        pool_key = f"{project}_{db_type}"
        
        if pool_key in self.project_pools:
            pool_info = self.project_pools[pool_key]
            self.total_allocated -= pool_info['max_connections']
            del self.project_pools[pool_key]
            
            self.logger.info(f"ReleBased {db_type} connection pool for {project}")
    
    def get_pool_status(self) -> Dict[str, Any]:
        """Get connection pool status."""
        return {
            'total_allocated': self.total_allocated,
            'max_total_connections': self.max_total_connections,
            'utilization_percent': (self.total_allocated / self.max_total_connections) * 100,
            'active_pools': len(self.project_pools),
            'pools': dict(self.project_pools)
        }


class OptimizedResourceManager:
    """Advanced resource manager for FLEET ecosystem."""
    
    def __init__(self, fleet_root: Optional[str] = None):
        self.fleet_root = Path(fleet_root) if fleet_root else get_fleet_root()
        self.monitor = ResourceMonitor(update_interval=5.0)
        self.port_manager = PortManager()
        self.db_pool_manager = DatabaseConnectionPool(max_total_connections=200)
        self.logger = logging.getLogger(__name__)
        
        # Resource allocation tracking
        self.allocations: Dict[str, ResourceAllocation] = {}
        self.project_quotas: Dict[str, ResourceQuota] = {}
        
        # Load project configurations and quotas
        self._load_project_quotas()
        
        # Start monitoring
        self.monitor.start_monitoring()
    
    def _load_project_quotas(self):
        """Load resource quotas for fleet projects."""
        # Default quotas for all quota-managed projects (the curated
        # `[fleet] probe_fallback_projects` config list — the application set
        # plus the CLI-only projects; ships empty for new installs).
        from sega.core.config import get_config
        _cfg = get_config()
        projects = list(_cfg.fleet.probe_fallback_projects)

        for project in projects:
            # Set higher quotas for infrastructure projects (config-driven
            # `critical_projects` list)
            if project in _cfg.critical_projects:
                quota = ResourceQuota(
                    project=project,
                    cpu_cores=4.0,
                    memory_mb=2048.0,
                    disk_mb=10240.0,
                    max_containers=10,
                    max_ports=20,
                    max_db_connections=50
                )
            else:
                quota = ResourceQuota(
                    project=project,
                    cpu_cores=2.0,
                    memory_mb=1024.0,
                    disk_mb=5120.0,
                    max_containers=5,
                    max_ports=10,
                    max_db_connections=20
                )
            
            self.project_quotas[project] = quota
    
    def allocate_resources(self, project: str, operation: str, 
                          resource_requirements: Dict[str, float]) -> Dict[str, bool]:
        """Allocate resources for a project operation."""
        allocation_results = {}
        allocated_resources = []
        
        try:
            # Check if project is known
            if project not in self.project_quotas:
                self.logger.warning(f"Unknown project: {project}")
                return {'error': False, 'message': f'Unknown project: {project}'}
            
            quota = self.project_quotas[project]
            
            # Check each resource requirement
            for resource_type_str, amount in resource_requirements.items():
                try:
                    resource_type = ResourceType(resource_type_str)
                except ValueError:
                    self.logger.warning(f"Unknown resource type: {resource_type_str}")
                    continue
                
                # Check if allocation is possible
                can_allocate = self._can_allocate_resource(project, resource_type, amount, quota)
                
                if can_allocate:
                    allocation_id = f"{project}_{operation}_{resource_type_str}_{int(time.time())}"
                    allocation = ResourceAllocation(
                        allocation_id=allocation_id,
                        project=project,
                        resource_type=resource_type,
                        amount=amount,
                        allocated_at=datetime.now(),
                        metadata={'operation': operation}
                    )
                    
                    self.allocations[allocation_id] = allocation
                    allocated_resources.append(allocation_id)
                    allocation_results[resource_type_str] = True
                    
                    self.logger.info(f"Allocated {amount} {resource_type_str} for {project}/{operation}")
                
                else:
                    allocation_results[resource_type_str] = False
                    self.logger.warning(f"Cannot allocate {amount} {resource_type_str} for {project}")
                    
                    # Rollback previous allocations
                    for alloc_id in allocated_resources:
                        self.releBase_allocation(alloc_id)
                    
                    return allocation_results
            
            return allocation_results
        
        except Exception as e:
            self.logger.error(f"Error allocating resources for {project}: {e}")
            
            # Rollback any successful allocations
            for alloc_id in allocated_resources:
                self.releBase_allocation(alloc_id)
            
            return {'error': True, 'message': str(e)}
    
    def _can_allocate_resource(self, project: str, resource_type: ResourceType, 
                              amount: float, quota: ResourceQuota) -> bool:
        """Check if resource can be allocated."""
        if not self.monitor.current_snapshot:
            return True  # Optimistic allocation if no monitoring data
        
        snapshot = self.monitor.current_snapshot
        
        if resource_type == ResourceType.CPU:
            # Check system CPU availability
            if snapshot.cpu_percent > 80:
                return False
            
            # Check project quota
            current_cpu = self._get_project_resource_usage(project, ResourceType.CPU)
            return (current_cpu + amount) <= quota.cpu_cores
        
        elif resource_type == ResourceType.MEMORY:
            # Check system memory availability
            if snapshot.memory_available_mb < amount:
                return False
            
            # Check project quota
            current_memory = self._get_project_resource_usage(project, ResourceType.MEMORY)
            return (current_memory + amount) <= quota.memory_mb
        
        elif resource_type == ResourceType.DISK:
            # Check system disk availability
            if snapshot.disk_free_mb < amount:
                return False
            
            # Check project quota
            current_disk = self._get_project_resource_usage(project, ResourceType.DISK)
            return (current_disk + amount) <= quota.disk_mb
        
        elif resource_type == ResourceType.PORT:
            # Use port manager
            return len(self.port_manager.project_ports.get(project, [])) < quota.max_ports
        
        elif resource_type == ResourceType.DATABASE_CONNECTIONS:
            # Check database connection pool availability
            return self.db_pool_manager.total_allocated + amount <= self.db_pool_manager.max_total_connections
        
        return True
    
    def _get_project_resource_usage(self, project: str, resource_type: ResourceType) -> float:
        """Get current resource usage for a project."""
        total_usage = 0.0
        
        for allocation in self.allocations.values():
            if allocation.project == project and allocation.resource_type == resource_type:
                total_usage += allocation.amount
        
        return total_usage
    
    def releBase_allocation(self, allocation_id: str):
        """ReleBase a resource allocation."""
        if allocation_id in self.allocations:
            allocation = self.allocations[allocation_id]
            del self.allocations[allocation_id]
            
            self.logger.info(f"ReleBased {allocation.amount} {allocation.resource_type.value} "
                           f"from {allocation.project}")
    
    def releBase_project_resources(self, project: str):
        """ReleBase all resources allocated to a project."""
        project_allocations = [
            alloc_id for alloc_id, allocation in self.allocations.items()
            if allocation.project == project
        ]
        
        for alloc_id in project_allocations:
            self.releBase_allocation(alloc_id)
        
        # ReleBase port allocations
        self.port_manager.releBase_project_ports(project)
        
        self.logger.info(f"ReleBased all resources for project: {project}")
    
    def get_resource_summary(self) -> Dict[str, Any]:
        """Get comprehensive resource summary."""
        current_snapshot = self.monitor.current_snapshot
        
        # Project resource usage
        project_usage = {}
        for project in self.project_quotas:
            project_usage[project] = {
                'cpu': self._get_project_resource_usage(project, ResourceType.CPU),
                'memory': self._get_project_resource_usage(project, ResourceType.MEMORY),
                'disk': self._get_project_resource_usage(project, ResourceType.DISK),
                'ports': len(self.port_manager.project_ports.get(project, []))
            }
        
        return {
            'timestamp': datetime.now().isoformat(),
            'system_resources': {
                'cpu_percent': current_snapshot.cpu_percent if current_snapshot else None,
                'memory_percent': current_snapshot.memory_percent if current_snapshot else None,
                'memory_available_mb': current_snapshot.memory_available_mb if current_snapshot else None,
                'disk_free_mb': current_snapshot.disk_free_mb if current_snapshot else None,
                'load_average': current_snapshot.load_average if current_snapshot else None
            },
            'allocations': {
                'total_active': len(self.allocations),
                'by_project': len(set(alloc.project for alloc in self.allocations.values())),
                'by_type': {}
            },
            'project_usage': project_usage,
            'port_status': self.port_manager.get_port_status(),
            'db_pool_status': self.db_pool_manager.get_pool_status()
        }
    
    def optimize_resource_allocation(self) -> Dict[str, Any]:
        """Optimize resource allocation across projects."""
        optimization_results = {
            'timestamp': datetime.now().isoformat(),
            'optimizations_applied': [],
            'recommendations': []
        }
        
        # Get resource trends
        trends = self.monitor.get_resource_trends(hours=2)
        
        if trends:
            # CPU optimization
            if trends['cpu']['average'] > 70:
                optimization_results['recommendations'].append({
                    'type': 'cpu_overload',
                    'message': 'High CPU usage detected. Consider scaling or load balancing.',
                    'priority': 'high'
                })
            
            # Memory optimization
            if trends['memory']['average'] > 80:
                optimization_results['recommendations'].append({
                    'type': 'memory_pressure',
                    'message': 'High memory usage detected. Review memory-intensive processes.',
                    'priority': 'high'
                })
        
        # Port optimization
        port_status = self.port_manager.get_port_status()
        total_port_ranges = sum(end - start for start, end in self.port_manager.port_ranges.values())
        port_utilization = (port_status['allocated_ports'] / total_port_ranges) * 100
        
        if port_utilization > 70:
            optimization_results['recommendations'].append({
                'type': 'port_exhaustion',
                'message': f'Port utilization at {port_utilization:.1f}%. Consider expanding port ranges.',
                'priority': 'medium'
            })
        
        # Database connection optimization
        db_status = self.db_pool_manager.get_pool_status()
        if db_status['utilization_percent'] > 80:
            optimization_results['recommendations'].append({
                'type': 'db_connection_pressure',
                'message': f'Database connection utilization at {db_status["utilization_percent"]:.1f}%.',
                'priority': 'high'
            })
        
        return optimization_results
    
    def export_metrics(self, format: str = 'json') -> str:
        """Export resource metrics in specified format."""
        summary = self.get_resource_summary()
        
        if format == 'json':
            return json.dumps(summary, indent=2, default=str)
        elif format == 'yaml':
            return yaml.dump(summary, default_flow_style=False)
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def cleanup(self):
        """Clean up resource manager."""
        self.monitor.stop_monitoring()
        self.logger.info("Resource manager cleanup completed")