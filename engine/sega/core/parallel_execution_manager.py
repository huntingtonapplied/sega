#!/usr/bin/env python3
# Copyright 2025 SEGA
"""
Parallel Execution Manager
==========================
Optimizes testing, deployment, and operations across multiple FLEET projects simultaneously.
"""

import asyncio
import time
import logging
from typing import Dict, List, Any, Optional, Callable, Set
from dataclasses import dataclass, field
from enum import Enum


class TaskStatus(Enum):
    """Status of parallel tasks."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ParallelTask:
    """Represents a task in the parallel execution system."""
    task_id: str
    project: str
    operation: str
    dependencies: Set[str] = field(default_factory=set)
    priority: int = 1  # Higher number = higher priority
    timeout: Optional[float] = None
    retry_count: int = 0
    max_retries: int = 3
    status: TaskStatus = TaskStatus.PENDING
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    result: Optional[Any] = None
    error: Optional[str] = None


@dataclass
class ExecutionResult:
    """Result of parallel execution."""
    total_tasks: int
    completed: int
    failed: int
    cancelled: int
    total_duration: float
    task_results: Dict[str, Any] = field(default_factory=dict)
    dependency_graph: Dict[str, Set[str]] = field(default_factory=dict)
    execution_order: List[str] = field(default_factory=list)


class DependencyResolver:
    """Resolves task dependencies for optimal execution order."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def build_dependency_graph(self, tasks: List[ParallelTask]) -> Dict[str, Set[str]]:
        """Build dependency graph from tasks."""
        graph = {}
        for task in tasks:
            graph[task.task_id] = task.dependencies.copy()
        
        # Validate that all dependencies exist
        all_task_ids = set(task.task_id for task in tasks)
        for task_id, deps in graph.items():
            invalid_deps = deps - all_task_ids
            if invalid_deps:
                self.logger.warning(f"Task {task_id} has invalid dependencies: {invalid_deps}")
                deps -= invalid_deps
        
        return graph
    
    def topological_sort(self, graph: Dict[str, Set[str]]) -> List[str]:
        """Perform topological sort to determine execution order."""
        in_degree = {node: 0 for node in graph}
        
        # Calculate in-degrees
        for node, deps in graph.items():
            for dep in deps:
                if dep in in_degree:
                    in_degree[node] += 1
        
        # Find nodes with no dependencies
        queue = [node for node, degree in in_degree.items() if degree == 0]
        result = []
        
        while queue:
            # Sort by priority if available (assuming we can access task priorities)
            queue.sort()
            node = queue.pop(0)
            result.append(node)
            
            # Update in-degrees for dependent nodes
            for other_node, deps in graph.items():
                if node in deps:
                    in_degree[other_node] -= 1
                    if in_degree[other_node] == 0:
                        queue.append(other_node)
        
        # Check for circular dependencies
        if len(result) != len(graph):
            remaining = set(graph.keys()) - set(result)
            raise ValueError(f"Circular dependency detected involving: {remaining}")
        
        return result
    
    def get_execution_batches(self, tasks: List[ParallelTask]) -> List[List[str]]:
        """Group tasks into batches that can be executed in parallel."""
        graph = self.build_dependency_graph(tasks)
        sorted_tasks = self.topological_sort(graph)
        
        # Create batches
        batches = []
        processed = set()
        
        while processed != set(sorted_tasks):
            current_batch = []
            
            for task_id in sorted_tasks:
                if task_id in processed:
                    continue
                
                # Check if all dependencies are satisfied
                deps = graph.get(task_id, set())
                if deps.issubset(processed):
                    current_batch.append(task_id)
            
            if not current_batch:
                # Should not happen if topological sort worked
                remaining = set(sorted_tasks) - processed
                raise ValueError(f"Unable to resolve dependencies for: {remaining}")
            
            batches.append(current_batch)
            processed.update(current_batch)
        
        return batches


class ResourceManager:
    """Manages resource allocation for parallel execution."""
    
    def __init__(self, max_concurrent_tasks: int = 4, memory_limit_mb: int = 2048):
        self.max_concurrent_tasks = max_concurrent_tasks
        self.memory_limit_mb = memory_limit_mb
        self.active_tasks: Dict[str, ParallelTask] = {}
        self.resource_usage: Dict[str, float] = {
            'cpu_cores': 0,
            'memory_mb': 0,
            'network_connections': 0
        }
        self.logger = logging.getLogger(__name__)
    
    def can_execute_task(self, task: ParallelTask) -> bool:
        """Check if task can be executed given current resource constraints."""
        if len(self.active_tasks) >= self.max_concurrent_tasks:
            return False
        
        # Estimate resource requirements based on operation type
        estimated_memory = self._estimate_memory_usage(task)
        if self.resource_usage['memory_mb'] + estimated_memory > self.memory_limit_mb:
            return False
        
        return True
    
    def allocate_resources(self, task: ParallelTask):
        """Allocate resources for task execution."""
        self.active_tasks[task.task_id] = task
        estimated_memory = self._estimate_memory_usage(task)
        self.resource_usage['memory_mb'] += estimated_memory
        self.resource_usage['cpu_cores'] += 1
    
    def releBase_resources(self, task_id: str):
        """ReleBase resources after task completion."""
        if task_id in self.active_tasks:
            task = self.active_tasks[task_id]
            estimated_memory = self._estimate_memory_usage(task)
            self.resource_usage['memory_mb'] -= estimated_memory
            self.resource_usage['cpu_cores'] -= 1
            del self.active_tasks[task_id]
    
    def _estimate_memory_usage(self, task: ParallelTask) -> float:
        """Estimate memory usage based on task type."""
        memory_estimates = {
            'test': 512,      # MB
            'build': 1024,    # MB
            'deploy': 256,    # MB
            'scan': 128,      # MB
            'browser_test': 768,  # MB for browser automation
        }
        return memory_estimates.get(task.operation, 256)
    
    def get_resource_status(self) -> Dict[str, Any]:
        """Get current resource utilization."""
        return {
            'active_tasks': len(self.active_tasks),
            'max_concurrent': self.max_concurrent_tasks,
            'memory_usage_mb': self.resource_usage['memory_mb'],
            'memory_limit_mb': self.memory_limit_mb,
            'cpu_cores_used': self.resource_usage['cpu_cores'],
            'utilization_percent': len(self.active_tasks) / self.max_concurrent_tasks * 100
        }


class ParallelExecutionManager:
    """Manages parallel execution of tasks across multiple FLEET projects."""
    
    def __init__(self, max_workers: int = 4, memory_limit_mb: int = 2048):
        self.max_workers = max_workers
        self.dependency_resolver = DependencyResolver()
        self.resource_manager = ResourceManager(max_workers, memory_limit_mb)
        self.logger = logging.getLogger(__name__)
        self.task_registry: Dict[str, Callable] = {}
        
        # Register common task types
        self._register_default_tasks()
    
    def _register_default_tasks(self):
        """Register default task handlers."""
        self.task_registry.update({
            'test': self._execute_test_task,
            'build': self._execute_build_task,
            'deploy': self._execute_deploy_task,
            'scan': self._execute_scan_task,
            'browser_test': self._execute_browser_test_task,
            'local_up': self._execute_local_up_task,
            'local_down': self._execute_local_down_task,
        })
    
    def register_task_handler(self, operation: str, handler: Callable):
        """Register custom task handler."""
        self.task_registry[operation] = handler
    
    async def execute_parallel(self, tasks: List[ParallelTask]) -> ExecutionResult:
        """Execute tasks in parallel with dependency resolution."""
        start_time = time.time()
        
        self.logger.info(f"Starting parallel execution of {len(tasks)} tasks")
        
        # Build dependency graph and execution order
        dependency_graph = self.dependency_resolver.build_dependency_graph(tasks)
        execution_batches = self.dependency_resolver.get_execution_batches(tasks)
        
        # Create task lookup
        task_lookup = {task.task_id: task for task in tasks}
        
        # Results tracking
        results = ExecutionResult(
            total_tasks=len(tasks),
            completed=0,
            failed=0,
            cancelled=0,
            total_duration=0,
            dependency_graph=dependency_graph,
            execution_order=[task_id for batch in execution_batches for task_id in batch]
        )
        
        # Execute batches
        for batch_idx, batch in enumerate(execution_batches):
            self.logger.info(f"Executing batch {batch_idx + 1}/{len(execution_batches)}: {batch}")
            
            # Execute batch in parallel
            batch_results = await self._execute_batch(
                [task_lookup[task_id] for task_id in batch]
            )
            
            # Update results
            for task_id, task_result in batch_results.items():
                results.task_results[task_id] = task_result
                task = task_lookup[task_id]
                
                if task.status == TaskStatus.COMPLETED:
                    results.completed += 1
                elif task.status == TaskStatus.FAILED:
                    results.failed += 1
                elif task.status == TaskStatus.CANCELLED:
                    results.cancelled += 1
                
                # Stop execution if critical task failed
                if task.status == TaskStatus.FAILED and task.priority >= 10:
                    self.logger.error(f"Critical task {task_id} failed, stopping execution")
                    await self._cancel_remaining_tasks(tasks)
                    break
        
        results.total_duration = time.time() - start_time
        
        self.logger.info(f"Parallel execution completed: {results.completed} completed, "
                        f"{results.failed} failed, {results.cancelled} cancelled")
        
        return results
    
    async def _execute_batch(self, batch_tasks: List[ParallelTask]) -> Dict[str, Any]:
        """Execute a batch of tasks in parallel."""
        batch_results = {}
        
        # Create semaphore to limit concurrent execution
        semaphore = asyncio.Semaphore(self.max_workers)
        
        async def execute_with_semaphore(task: ParallelTask):
            async with semaphore:
                if not self.resource_manager.can_execute_task(task):
                    # Wait for resources to become available
                    while not self.resource_manager.can_execute_task(task):
                        await asyncio.sleep(0.1)
                
                self.resource_manager.allocate_resources(task)
                try:
                    result = await self._execute_single_task(task)
                    batch_results[task.task_id] = result
                finally:
                    self.resource_manager.releBase_resources(task.task_id)
        
        # Execute all tasks in batch concurrently
        await asyncio.gather(*[execute_with_semaphore(task) for task in batch_tasks])
        
        return batch_results
    
    async def _execute_single_task(self, task: ParallelTask) -> Dict[str, Any]:
        """Execute a single task with timeout and retry logic."""
        task.status = TaskStatus.RUNNING
        task.start_time = time.time()
        
        for attempt in range(task.max_retries + 1):
            try:
                self.logger.info(f"Executing task {task.task_id} (attempt {attempt + 1})")
                
                # Get task handler
                handler = self.task_registry.get(task.operation)
                if not handler:
                    raise ValueError(f"No handler registered for operation: {task.operation}")
                
                # Execute with timeout
                if task.timeout:
                    result = await asyncio.wait_for(
                        handler(task),
                        timeout=task.timeout
                    )
                else:
                    result = await handler(task)
                
                # Task completed successfully
                task.status = TaskStatus.COMPLETED
                task.result = result
                task.end_time = time.time()
                
                return {
                    'status': 'completed',
                    'result': result,
                    'duration': task.end_time - task.start_time,
                    'attempts': attempt + 1
                }
            
            except asyncio.TimeoutError:
                error_msg = f"Task {task.task_id} timed out after {task.timeout}s"
                self.logger.warning(error_msg)
                task.error = error_msg
                
                if attempt < task.max_retries:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    continue
            
            except Exception as e:
                error_msg = f"Task {task.task_id} failed: {str(e)}"
                self.logger.error(error_msg)
                task.error = error_msg
                
                if attempt < task.max_retries:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    continue
        
        # Task failed after all retries
        task.status = TaskStatus.FAILED
        task.end_time = time.time()
        
        return {
            'status': 'failed',
            'error': task.error,
            'duration': task.end_time - task.start_time,
            'attempts': task.max_retries + 1
        }
    
    async def _cancel_remaining_tasks(self, tasks: List[ParallelTask]):
        """Cancel remaining tasks."""
        for task in tasks:
            if task.status == TaskStatus.PENDING:
                task.status = TaskStatus.CANCELLED
    
    # Default task handlers
    
    async def _execute_test_task(self, task: ParallelTask) -> Dict[str, Any]:
        """Execute test task."""
        # Simulate test execution
        await asyncio.sleep(0.5)  # Simulate test time
        
        return {
            'project': task.project,
            'operation': 'test',
            'tests_run': 50,
            'tests_passed': 48,
            'tests_failed': 2,
            'coverage': 85.5
        }
    
    async def _execute_build_task(self, task: ParallelTask) -> Dict[str, Any]:
        """Execute build task."""
        await asyncio.sleep(1.0)  # Simulate build time
        
        return {
            'project': task.project,
            'operation': 'build',
            'build_time': 45.2,
            'artifacts': ['dist/', 'build/'],
            'success': True
        }
    
    async def _execute_deploy_task(self, task: ParallelTask) -> Dict[str, Any]:
        """Execute deploy task."""
        await asyncio.sleep(2.0)  # Simulate deployment time
        
        return {
            'project': task.project,
            'operation': 'deploy',
            'deployment_id': f"deploy-{task.project}-{int(time.time())}",
            'status': 'deployed',
            'url': f"https://{task.project}.fleet-dev.example.com"
        }
    
    async def _execute_scan_task(self, task: ParallelTask) -> Dict[str, Any]:
        """Execute security scan task."""
        await asyncio.sleep(0.3)  # Simulate scan time
        
        return {
            'project': task.project,
            'operation': 'scan',
            'vulnerabilities_found': 2,
            'critical': 0,
            'high': 1,
            'medium': 1,
            'low': 0
        }
    
    async def _execute_browser_test_task(self, task: ParallelTask) -> Dict[str, Any]:
        """Execute browser test task."""
        await asyncio.sleep(3.0)  # Simulate browser test time
        
        return {
            'project': task.project,
            'operation': 'browser_test',
            'tests_run': 25,
            'tests_passed': 23,
            'tests_failed': 2,
            'screenshots': ['test1.png', 'test2.png'],
            'validation_tiers': ['static', 'dynamic', 'integration']
        }
    
    async def _execute_local_up_task(self, task: ParallelTask) -> Dict[str, Any]:
        """Execute local service startup task."""
        await asyncio.sleep(1.5)  # Simulate service startup
        
        return {
            'project': task.project,
            'operation': 'local_up',
            'services_started': ['postgres', 'redis', 'api'],
            'ports': [5001, 6001, 3001],
            'status': 'running'
        }
    
    async def _execute_local_down_task(self, task: ParallelTask) -> Dict[str, Any]:
        """Execute local service shutdown task."""
        await asyncio.sleep(0.5)  # Simulate service shutdown
        
        return {
            'project': task.project,
            'operation': 'local_down',
            'services_stopped': ['api', 'redis', 'postgres'],
            'status': 'stopped'
        }
    
    def create_task_from_project_operation(self, project: str, operation: str, 
                                         dependencies: Optional[List[str]] = None,
                                         priority: int = 1, timeout: Optional[float] = None) -> ParallelTask:
        """Create a parallel task from project and operation."""
        task_id = f"{project}-{operation}-{int(time.time() * 1000)}"
        
        return ParallelTask(
            task_id=task_id,
            project=project,
            operation=operation,
            dependencies=set(dependencies or []),
            priority=priority,
            timeout=timeout
        )
    
    def get_execution_stats(self) -> Dict[str, Any]:
        """Get execution statistics."""
        resource_status = self.resource_manager.get_resource_status()
        
        return {
            'resource_utilization': resource_status,
            'registered_operations': list(self.task_registry.keys()),
            'max_workers': self.max_workers
        }