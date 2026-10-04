#!/usr/bin/env python
# -*- coding: utf-8 -*-
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

# ===============================================================
# SEGA MODULE - ENTERPRISE ORCHESTRATOR
# ===============================================================
# File: src/sega/core/enterprise_orchestrator.py
# Purpose: Enterprise-scale deployment orchestration for FLEET projects
#
# Description: Manages parallel deployment execution across multiple projects
# with support for dependency resolution, retry mechanisms, and real-time
# monitoring. Coordinates complex deployment workflows for enterprise environments.
#
# Dependencies:
# - External: concurrent.futures, dataclasses, enum, pathlib
# - Internal: workspace_manager, deployment_result
#
# Used by: deployment_service, API endpoints for enterprise deployments
#

"""Enterprise-scale deployment orchestration for FLEET projects."""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from enum import Enum
import time

from .workspace_manager import WorkspaceManager
from .deployment_result import DeploymentResult


class DeploymentStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ROLLED_BACK = "rolled_back"


@dataclass
class DeploymentTask:
    """Represents a deployment task for a single project."""

    project_key: str
    target: str
    strategy: str
    dependencies: List[str]
    priority: int = 0
    status: DeploymentStatus = DeploymentStatus.PENDING
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    result: Optional[DeploymentResult] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3


class EnterpriseOrchestrator:
    """Enterprise-scale deployment orchestration with parallel execution, retries, and monitoring."""

    def __init__(
        self, workspace_manager: WorkspaceManager, max_workers: int = 10
    ):
        self.workspace_manager = workspace_manager
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.logger = logging.getLogger(__name__)

        # Deployment state
        self.active_deployments: Dict[str, DeploymentTask] = {}
        self.deployment_history: List[DeploymentTask] = []
        self.resource_locks: Dict[
            str, Set[str]
        ] = {}  # resource -> projects using it

        # Configuration
        self.config = {
            "max_parallel_per_team": 3,
            "max_parallel_per_type": 5,
            "default_timeout": 1800,  # 30 minutes
            "retry_delay": 60,  # 1 minute
            "health_check_interval": 30,
        }

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        self.shutdown()

    def shutdown(self):
        """Shutdown orchestrator and cleanup resources."""
        self.logger.info("Shutting down enterprise orchestrator")

        # Cancel any active deployments
        for deployment_id, task in self.active_deployments.items():
            self.logger.warning(
                f"Cancelling active deployment: {deployment_id}"
            )
            # Cancel task if it has a future
            if hasattr(task, "future") and task.future:
                task.future.cancel()

        # Shutdown executor
        self.executor.shutdown(wait=True, timeout=30)
        self.logger.info("Enterprise orchestrator shutdown complete")

    def create_deployment_plan(
        self, projects: List[str], target: str, strategy: str = "coordinated"
    ) -> List[DeploymentTask]:
        """Create optimized deployment plan with parallel execution groups."""

        # Get dependency order
        dependency_order = self.workspace_manager.get_deployment_order(
            projects
        )

        # Create deployment tasks
        tasks = []
        for i, project_key in enumerate(dependency_order):
            dependencies = self.workspace_manager.get_project_dependencies(
                project_key
            )

            # Filter dependencies to only include projects in this deployment
            filtered_deps = [dep for dep in dependencies if dep in projects]

            task = DeploymentTask(
                project_key=project_key,
                target=target,
                strategy=strategy,
                dependencies=filtered_deps,
                priority=i,  # Later in dependency order = higher priority
            )
            tasks.append(task)

        # Optimize for parallel execution
        if strategy == "parallel":
            tasks = self._optimize_parallel_execution(tasks)

        return tasks

    def _optimize_parallel_execution(
        self, tasks: List[DeploymentTask]
    ) -> List[DeploymentTask]:
        """Optimize task priorities for maximum parallelism."""

        # Group tasks by team and type for resource management
        team_counts = {}
        type_counts = {}

        for task in tasks:
            project = self.workspace_manager.projects[task.project_key]
            team = project["team"]
            project_type = project["detector"].detect()

            # Track resource usage
            team_counts[team] = team_counts.get(team, 0) + 1
            type_counts[project_type] = type_counts.get(project_type, 0) + 1

            # Adjust priority based on resource constraints
            if team_counts[team] > self.config["max_parallel_per_team"]:
                task.priority += 100  # Delay high-resource teams

            if (
                type_counts[project_type]
                > self.config["max_parallel_per_type"]
            ):
                task.priority += 50  # Delay high-resource types

        return sorted(tasks, key=lambda t: t.priority)

    def execute_deployment_plan(
        self,
        tasks: List[DeploymentTask],
        monitor_callback: Optional[callable] = None,
    ) -> Dict[str, DeploymentResult]:
        """Execute deployment plan with parallel execution and monitoring."""

        self.active_deployments = {task.project_key: task for task in tasks}
        results = {}

        # Start monitoring thread
        monitor_future = self.executor.submit(
            self._monitor_deployments, monitor_callback
        )

        try:
            # Execute tasks in parallel with dependency respect
            futures = {}

            while self.active_deployments or futures:
                # Start new tasks that are ready
                ready_tasks = self._get_ready_tasks()

                for task in ready_tasks:
                    if len(futures) < self.max_workers:
                        future = self.executor.submit(
                            self._execute_single_deployment, task
                        )
                        futures[future] = task
                        task.status = DeploymentStatus.IN_PROGRESS
                        task.started_at = time.time()

                # Wait for completions
                if futures:
                    for future in as_completed(futures, timeout=1.0):
                        task = futures[future]

                        try:
                            result = future.result()
                            task.result = result
                            task.status = DeploymentStatus.COMPLETED
                            task.completed_at = time.time()

                            results[task.project_key] = result

                            # Remove from active deployments
                            if task.project_key in self.active_deployments:
                                del self.active_deployments[task.project_key]

                            # ReleBase resources
                            self._releBase_resources(task)

                        except Exception as e:
                            task.error = str(e)
                            task.status = DeploymentStatus.FAILED
                            task.completed_at = time.time()

                            # Handle retry logic
                            if task.retry_count < task.max_retries:
                                task.retry_count += 1
                                task.status = DeploymentStatus.PENDING
                                self.logger.warning(
                                    f"Retrying {task.project_key} (attempt {task.retry_count})"
                                )
                                time.sleep(self.config["retry_delay"])
                            else:
                                # Mark as failed
                                results[task.project_key] = DeploymentResult(
                                    success=False, error=task.error
                                )

                                # Remove from active deployments
                                if task.project_key in self.active_deployments:
                                    del self.active_deployments[
                                        task.project_key
                                    ]

                        finally:
                            # Clean up future
                            if future in futures:
                                del futures[future]

                # Brief pause to avoid busy waiting
                time.sleep(0.1)

        finally:
            # Stop monitoring
            monitor_future.cancel()

        return results

    def _get_ready_tasks(self) -> List[DeploymentTask]:
        """Get tasks that are ready to execute (dependencies satisfied)."""
        ready_tasks = []

        for task in self.active_deployments.values():
            if task.status != DeploymentStatus.PENDING:
                continue

            # Check if dependencies are satisfied
            dependencies_satisfied = True
            for dep in task.dependencies:
                if dep in self.active_deployments:
                    dependencies_satisfied = False
                    break

            if dependencies_satisfied:
                # Check resource constraints
                if self._check_resource_constraints(task):
                    ready_tasks.append(task)

        return ready_tasks

    def _check_resource_constraints(self, task: DeploymentTask) -> bool:
        """Check if task can run given current resource constraints."""
        project = self.workspace_manager.projects[task.project_key]
        team = project["team"]
        project_type = project["detector"].detect()

        # Count current active deployments by team and type
        team_active = sum(
            1
            for t in self.active_deployments.values()
            if t.status == DeploymentStatus.IN_PROGRESS
            and self.workspace_manager.projects[t.project_key]["team"] == team
        )

        type_active = sum(
            1
            for t in self.active_deployments.values()
            if t.status == DeploymentStatus.IN_PROGRESS
            and self.workspace_manager.projects[t.project_key][
                "detector"
            ].detect()
            == project_type
        )

        # Check constraints
        if team_active >= self.config["max_parallel_per_team"]:
            return False

        if type_active >= self.config["max_parallel_per_type"]:
            return False

        # Check shared resource locks
        shared_resources = self.workspace_manager.get_shared_resources()
        for resource, projects in shared_resources.items():
            if task.project_key in projects:
                if (
                    resource in self.resource_locks
                    and self.resource_locks[resource]
                ):
                    return False

        return True

    def _acquire_resources(self, task: DeploymentTask):
        """Acquire resources for a deployment task."""
        shared_resources = self.workspace_manager.get_shared_resources()

        for resource, projects in shared_resources.items():
            if task.project_key in projects:
                if resource not in self.resource_locks:
                    self.resource_locks[resource] = set()
                self.resource_locks[resource].add(task.project_key)

    def _releBase_resources(self, task: DeploymentTask):
        """ReleBase resources for a deployment task."""
        shared_resources = self.workspace_manager.get_shared_resources()

        for resource, projects in shared_resources.items():
            if task.project_key in projects:
                if resource in self.resource_locks:
                    self.resource_locks[resource].discard(task.project_key)
                    if not self.resource_locks[resource]:
                        del self.resource_locks[resource]

    def _execute_single_deployment(
        self, task: DeploymentTask
    ) -> DeploymentResult:
        """Execute deployment for a single project."""
        try:
            # Acquire resources
            self._acquire_resources(task)

            # Get project info
            project = self.workspace_manager.projects[task.project_key]
            project_path = str(project["path"])

            # Import deployment logic
            from ..ship.deployers.deployment_router import DeploymentRouter

            # Create router and execute deployment
            router = DeploymentRouter()
            result = router.deploy(
                project_path=project_path,
                target=task.target,
                strategy=task.strategy,
                dry_run=False,
            )

            self.logger.info(
                f"Deployment completed for {task.project_key}: {result.success}"
            )
            return result

        except Exception as e:
            self.logger.error(
                f"Deployment failed for {task.project_key}: {str(e)}"
            )
            return DeploymentResult(
                success=False, error=f"Deployment failed: {str(e)}"
            )

    def _monitor_deployments(self, callback: Optional[callable] = None):
        """Monitor active deployments and provide status updates."""
        while self.active_deployments:
            try:
                # Collect status information
                status_info = {
                    "active_count": len(
                        [
                            t
                            for t in self.active_deployments.values()
                            if t.status == DeploymentStatus.IN_PROGRESS
                        ]
                    ),
                    "pending_count": len(
                        [
                            t
                            for t in self.active_deployments.values()
                            if t.status == DeploymentStatus.PENDING
                        ]
                    ),
                    "completed_count": len(
                        [
                            t
                            for t in self.active_deployments.values()
                            if t.status == DeploymentStatus.COMPLETED
                        ]
                    ),
                    "failed_count": len(
                        [
                            t
                            for t in self.active_deployments.values()
                            if t.status == DeploymentStatus.FAILED
                        ]
                    ),
                    "tasks": {
                        task.project_key: {
                            "status": task.status.value,
                            "started_at": task.started_at,
                            "retry_count": task.retry_count,
                        }
                        for task in self.active_deployments.values()
                    },
                }

                # Call callback if provided
                if callback:
                    callback(status_info)

                # Check for timeouts
                current_time = time.time()
                for task in self.active_deployments.values():
                    if (
                        task.status == DeploymentStatus.IN_PROGRESS
                        and task.started_at
                        and current_time - task.started_at
                        > self.config["default_timeout"]
                    ):
                        self.logger.warning(
                            f"Deployment timeout for {task.project_key}"
                        )
                        task.status = DeploymentStatus.FAILED
                        task.error = "Deployment timeout"

                time.sleep(self.config["health_check_interval"])

            except Exception as e:
                self.logger.error(f"Monitoring error: {str(e)}")
                time.sleep(5)  # Brief pause before retry

    def get_deployment_status(self) -> Dict:
        """Get current deployment status."""
        return {
            "active_deployments": len(self.active_deployments),
            "resource_locks": {
                k: list(v) for k, v in self.resource_locks.items()
            },
            "tasks": {
                task.project_key: {
                    "status": task.status.value,
                    "started_at": task.started_at,
                    "completed_at": task.completed_at,
                    "retry_count": task.retry_count,
                    "error": task.error,
                }
                for task in self.active_deployments.values()
            },
        }

    def cancel_deployment(self, project_key: str = None):
        """Cancel active deployment(s)."""
        if project_key:
            # Cancel specific project
            if project_key in self.active_deployments:
                task = self.active_deployments[project_key]
                task.status = DeploymentStatus.CANCELLED
                self._releBase_resources(task)
                del self.active_deployments[project_key]
        else:
            # Cancel all active deployments
            for task in list(self.active_deployments.values()):
                task.status = DeploymentStatus.CANCELLED
                self._releBase_resources(task)

            self.active_deployments.clear()

    def get_deployment_metrics(self) -> Dict:
        """Get deployment metrics and statistics."""
        all_tasks = (
            list(self.active_deployments.values()) + self.deployment_history
        )

        if not all_tasks:
            return {"total_deployments": 0}

        completed_tasks = [
            t for t in all_tasks if t.status == DeploymentStatus.COMPLETED
        ]
        failed_tasks = [
            t for t in all_tasks if t.status == DeploymentStatus.FAILED
        ]

        # Calculate metrics
        total_deployments = len(all_tasks)
        success_rate = (
            len(completed_tasks) / total_deployments
            if total_deployments > 0
            else 0
        )

        # Average deployment time
        avg_deployment_time = 0
        if completed_tasks:
            deployment_times = [
                t.completed_at - t.started_at
                for t in completed_tasks
                if t.started_at and t.completed_at
            ]
            if deployment_times:
                avg_deployment_time = sum(deployment_times) / len(
                    deployment_times
                )

        return {
            "total_deployments": total_deployments,
            "successful_deployments": len(completed_tasks),
            "failed_deployments": len(failed_tasks),
            "success_rate": success_rate,
            "average_deployment_time": avg_deployment_time,
            "active_deployments": len(self.active_deployments),
            "resource_utilization": len(self.resource_locks),
        }

    def cleanup(self):
        """Clean up resources and shutdown executor."""
        self.cancel_deployment()  # Cancel all active deployments
        self.executor.shutdown(wait=True)
        self.resource_locks.clear()
