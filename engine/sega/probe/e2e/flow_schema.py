#!/usr/bin/env python3
# Copyright 2025 SEGA
"""
E2E Test Flow Schema
====================
Data models for configuration-driven E2E test flows.

Projects define flows at: {project}/tests/e2e/flows.yaml
Template available at: sega/templates/e2e/flows.yaml.template
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


class ActionType(Enum):
    """Supported test action types."""
    NAVIGATE = "navigate"      # Navigate to URL path
    CLICK = "click"            # Click element
    FILL = "fill"              # Fill input with value
    VERIFY = "verify"          # Wait for element to be visible
    WAIT = "wait"              # Wait for milliseconds
    SCREENSHOT = "screenshot"  # Capture screenshot


@dataclass
class TestAction:
    """
    A single action in a test flow.

    Attributes:
        action: Action type (navigate, click, fill, verify, wait, screenshot)
        selector: CSS selector, data-testid, or path for navigate
        value: Value for fill actions, supports {{ENV_VAR}} interpolation
        timeout_ms: Action timeout in milliseconds
        screenshot: Whether to capture screenshot before/after this action
    """
    action: str
    selector: str
    value: Optional[str] = None
    timeout_ms: int = 5000
    screenshot: bool = False

    def __post_init__(self):
        # Validate action type
        valid_actions = {e.value for e in ActionType}
        if self.action not in valid_actions:
            raise ValueError(
                f"Invalid action '{self.action}'. "
                f"Valid actions: {', '.join(valid_actions)}"
            )

    @property
    def action_type(self) -> ActionType:
        """Get the ActionType enum value."""
        return ActionType(self.action)


@dataclass
class TestFlow:
    """
    A test flow consisting of multiple actions.

    Attributes:
        name: Flow identifier (e.g., "login", "create_entity")
        description: Human-readable description
        actions: List of actions to execute in order
        preconditions: List of flow names that must pass first
        success_criteria: Per-flow criteria overrides
    """
    name: str
    description: str
    actions: List[TestAction]
    preconditions: List[str] = field(default_factory=list)
    success_criteria: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, name: str, data: Dict[str, Any]) -> "TestFlow":
        """Create TestFlow from YAML dictionary."""
        actions = [
            TestAction(
                action=a["action"],
                selector=a["selector"],
                value=a.get("value"),
                timeout_ms=a.get("timeout_ms", 5000),
                screenshot=a.get("screenshot", False),
            )
            for a in data.get("actions", [])
        ]

        return cls(
            name=name,
            description=data.get("description", ""),
            actions=actions,
            preconditions=data.get("preconditions", []),
            success_criteria=data.get("success_criteria", {}),
        )


@dataclass
class FlowDefaults:
    """
    Default settings applied to all flows unless overridden.

    Attributes:
        timeout_ms: Default action timeout
        max_console_errors: Maximum allowed console errors
        max_failed_requests: Maximum allowed network failures
        allowed_console_patterns: Regex patterns to ignore in console
    """
    timeout_ms: int = 5000
    max_console_errors: int = 0
    max_failed_requests: int = 0
    allowed_console_patterns: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FlowDefaults":
        """Create FlowDefaults from YAML dictionary."""
        return cls(
            timeout_ms=data.get("timeout_ms", 5000),
            max_console_errors=data.get("max_console_errors", 0),
            max_failed_requests=data.get("max_failed_requests", 0),
            allowed_console_patterns=data.get("allowed_console_patterns", []),
        )


@dataclass
class FlowConfig:
    """
    Complete E2E test configuration for a project.

    Loaded from: {project}/tests/e2e/flows.yaml

    Attributes:
        project: Project name
        base_url: Base URL for the frontend (supports {{ENV_VAR}})
        defaults: Default settings for all flows
        flows: Dictionary of flow name -> TestFlow
    """
    project: str
    base_url: str
    defaults: FlowDefaults
    flows: Dict[str, TestFlow]

    @classmethod
    def from_yaml(cls, data: Dict[str, Any]) -> "FlowConfig":
        """Create FlowConfig from parsed YAML data."""
        defaults = FlowDefaults.from_dict(data.get("defaults", {}))

        flows = {}
        for flow_name, flow_data in data.get("flows", {}).items():
            flows[flow_name] = TestFlow.from_dict(flow_name, flow_data)

        return cls(
            project=data.get("project", "unknown"),
            base_url=data.get("base_url", "http://localhost:3000"),
            defaults=defaults,
            flows=flows,
        )

    def get_flow(self, name: str) -> Optional[TestFlow]:
        """Get a flow by name."""
        return self.flows.get(name)

    def get_execution_order(self) -> List[str]:
        """
        Get flows in dependency order (topological sort).

        Flows with preconditions are executed after their dependencies.
        """
        # Build dependency graph
        visited = set()
        order = []

        def visit(flow_name: str):
            if flow_name in visited:
                return
            visited.add(flow_name)

            flow = self.flows.get(flow_name)
            if flow:
                for dep in flow.preconditions:
                    visit(dep)
                order.append(flow_name)

        for flow_name in self.flows:
            visit(flow_name)

        return order
