#!/usr/bin/env python3
# Copyright 2025 SEGA
"""
E2E Success Criteria
====================
Data models for explicit pass/fail success criteria.

Profiles defined at: sega/config/e2e_success_profiles.yaml
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional


@dataclass
class SuccessCriteria:
    """
    Explicit success/failure criteria for E2E tests.

    Attributes:
        max_load_time_ms: Maximum page load time in milliseconds
        max_console_errors: Maximum allowed console errors
        max_failed_requests: Maximum allowed network failures
        allowed_console_patterns: Regex patterns to ignore in console
        required_elements: CSS selectors that must exist after flow
        forbidden_elements: Error indicators that must NOT exist
    """
    max_load_time_ms: int = 5000
    max_console_errors: int = 0
    max_failed_requests: int = 0
    allowed_console_patterns: List[str] = field(default_factory=list)
    required_elements: List[str] = field(default_factory=list)
    forbidden_elements: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SuccessCriteria":
        """Create SuccessCriteria from dictionary."""
        return cls(
            max_load_time_ms=data.get("max_load_time_ms", 5000),
            max_console_errors=data.get("max_console_errors", 0),
            max_failed_requests=data.get("max_failed_requests", 0),
            allowed_console_patterns=data.get("allowed_console_patterns", []),
            required_elements=data.get("required_elements", []),
            forbidden_elements=data.get("forbidden_elements", []),
        )

    def is_console_error_allowed(self, error_message: str) -> bool:
        """Check if a console error matches an allowed pattern."""
        for pattern in self.allowed_console_patterns:
            if re.search(pattern, error_message, re.IGNORECASE):
                return True
        return False


@dataclass
class CriterionResult:
    """Result of evaluating a single criterion."""
    name: str
    passed: bool
    expected: Any
    actual: Any
    message: str

    def __str__(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return f"{self.name}: {status} - {self.message}"


@dataclass
class CriteriaEvaluation:
    """
    Result of evaluating all criteria for a flow or test run.

    Attributes:
        passed: Whether all criteria passed
        criteria_results: Individual criterion results
        overall_score: Percentage of criteria passed (0.0 to 1.0)
        blocking_failures: List of failure messages for blocking issues
        warnings: List of warning messages (non-blocking)
    """
    passed: bool
    criteria_results: Dict[str, CriterionResult] = field(default_factory=dict)
    overall_score: float = 0.0
    blocking_failures: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def add_result(self, result: CriterionResult):
        """Add a criterion result."""
        self.criteria_results[result.name] = result
        if not result.passed:
            self.blocking_failures.append(result.message)
        self._recalculate_score()

    def _recalculate_score(self):
        """Recalculate overall score and passed status."""
        if not self.criteria_results:
            self.overall_score = 1.0
            self.passed = True
            return

        passed_count = sum(1 for r in self.criteria_results.values() if r.passed)
        self.overall_score = passed_count / len(self.criteria_results)
        self.passed = all(r.passed for r in self.criteria_results.values())

    def format_summary(self) -> str:
        """Format a summary of the evaluation."""
        lines = []
        for name, result in self.criteria_results.items():
            status = "PASS" if result.passed else "FAIL"
            lines.append(f"  {name:30} {status:6} {result.actual}")
        return "\n".join(lines)


# Standard profiles
PROFILES = {
    "strict": SuccessCriteria(
        max_load_time_ms=3000,
        max_console_errors=0,
        max_failed_requests=0,
        allowed_console_patterns=[],
    ),
    "standard": SuccessCriteria(
        max_load_time_ms=5000,
        max_console_errors=3,
        max_failed_requests=0,
        allowed_console_patterns=[
            r".*deprecation.*",
            r".*DevTools.*",
            r".*favicon.*",
        ],
    ),
    "lenient": SuccessCriteria(
        max_load_time_ms=10000,
        max_console_errors=10,
        max_failed_requests=2,
        allowed_console_patterns=[
            r".*deprecation.*",
            r".*DevTools.*",
            r".*favicon.*",
            r".*warning.*",
        ],
    ),
}


def get_profile(name: str) -> SuccessCriteria:
    """Get a success criteria profile by name."""
    if name not in PROFILES:
        raise ValueError(f"Unknown profile '{name}'. Available: {', '.join(PROFILES.keys())}")
    return PROFILES[name]
