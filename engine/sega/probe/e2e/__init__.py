#!/usr/bin/env python3
# Copyright 2025 SEGA
"""
SEGA E2E Testing Package
========================
Configuration-driven end-to-end testing framework.

Projects define test flows in {project}/tests/e2e/flows.yaml
SEGA provides the runner, evaluation, and reporting infrastructure.
"""

from .flow_schema import TestAction, TestFlow, FlowConfig
from .flow_runner import FlowRunner, FlowResult, ActionResult
from .success_criteria import SuccessCriteria, CriteriaEvaluation, CriterionResult
from .criteria_evaluator import CriteriaEvaluator

__all__ = [
    "TestAction",
    "TestFlow",
    "FlowConfig",
    "FlowRunner",
    "FlowResult",
    "ActionResult",
    "SuccessCriteria",
    "CriteriaEvaluation",
    "CriterionResult",
    "CriteriaEvaluator",
]
