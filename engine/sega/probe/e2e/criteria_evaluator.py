#!/usr/bin/env python3
# Copyright 2025 SEGA
"""
E2E Criteria Evaluator
======================
Evaluates E2E test results against success criteria.
"""

from typing import List, Optional
from .flow_runner import FlowResult, E2ETestReport
from .success_criteria import (
    SuccessCriteria,
    CriteriaEvaluation,
    CriterionResult,
    get_profile,
)


class CriteriaEvaluator:
    """
    Evaluates E2E test results against success criteria.

    Usage:
        evaluator = CriteriaEvaluator(profile="standard")
        evaluation = evaluator.evaluate_report(report)
    """

    def __init__(self, profile: str = "standard", criteria: Optional[SuccessCriteria] = None):
        """
        Initialize evaluator with a profile or custom criteria.

        Args:
            profile: Profile name ("strict", "standard", "lenient")
            criteria: Optional custom criteria (overrides profile)
        """
        self.criteria = criteria or get_profile(profile)
        self.profile = profile

    def evaluate_flow(self, result: FlowResult) -> CriteriaEvaluation:
        """
        Evaluate a single flow result against criteria.

        Args:
            result: FlowResult from flow execution

        Returns:
            CriteriaEvaluation with detailed results
        """
        evaluation = CriteriaEvaluation(passed=True)

        # Check actions completed
        if result.skipped:
            evaluation.add_result(CriterionResult(
                name="Flow Execution",
                passed=False,
                expected="executed",
                actual="skipped",
                message=f"Flow skipped: {result.skip_reason}",
            ))
            return evaluation

        if not result.passed:
            evaluation.add_result(CriterionResult(
                name="Actions Completed",
                passed=False,
                expected=result.actions_total,
                actual=result.actions_completed,
                message=f"Only {result.actions_completed}/{result.actions_total} actions completed",
            ))
        else:
            evaluation.add_result(CriterionResult(
                name="Actions Completed",
                passed=True,
                expected=result.actions_total,
                actual=result.actions_completed,
                message=f"All {result.actions_completed} actions completed",
            ))

        # Check duration
        duration_passed = result.duration_ms <= self.criteria.max_load_time_ms
        evaluation.add_result(CriterionResult(
            name="Duration",
            passed=duration_passed,
            expected=f"<= {self.criteria.max_load_time_ms}ms",
            actual=f"{result.duration_ms:.0f}ms",
            message=f"Duration: {result.duration_ms:.0f}ms (max: {self.criteria.max_load_time_ms}ms)",
        ))

        # Check console errors (filtering allowed patterns)
        filtered_errors = [
            e for e in result.console_errors
            if not self.criteria.is_console_error_allowed(e)
        ]
        console_passed = len(filtered_errors) <= self.criteria.max_console_errors
        evaluation.add_result(CriterionResult(
            name="Console Errors",
            passed=console_passed,
            expected=f"<= {self.criteria.max_console_errors}",
            actual=len(filtered_errors),
            message=f"Console errors: {len(filtered_errors)} (max: {self.criteria.max_console_errors})",
        ))

        # Check network failures
        network_passed = len(result.network_failures) <= self.criteria.max_failed_requests
        evaluation.add_result(CriterionResult(
            name="Network Failures",
            passed=network_passed,
            expected=f"<= {self.criteria.max_failed_requests}",
            actual=len(result.network_failures),
            message=f"Network failures: {len(result.network_failures)} (max: {self.criteria.max_failed_requests})",
        ))

        return evaluation

    def evaluate_report(self, report: E2ETestReport) -> CriteriaEvaluation:
        """
        Evaluate an entire E2E test report against criteria.

        Args:
            report: E2ETestReport from test run

        Returns:
            CriteriaEvaluation with overall results
        """
        evaluation = CriteriaEvaluation(passed=True)

        # Aggregate results
        total_actions = sum(r.actions_total for r in report.flow_results)
        completed_actions = sum(r.actions_completed for r in report.flow_results)
        total_console_errors = sum(
            len([e for e in r.console_errors if not self.criteria.is_console_error_allowed(e)])
            for r in report.flow_results
        )
        total_network_failures = sum(len(r.network_failures) for r in report.flow_results)

        # Check flows passed
        flows_passed = report.flows_passed == report.flows_total - report.flows_skipped
        evaluation.add_result(CriterionResult(
            name="Flows Passed",
            passed=flows_passed,
            expected=report.flows_total - report.flows_skipped,
            actual=report.flows_passed,
            message=f"Flows: {report.flows_passed}/{report.flows_total - report.flows_skipped} passed",
        ))

        # Check actions completed
        actions_passed = completed_actions == total_actions
        evaluation.add_result(CriterionResult(
            name="Actions Completed",
            passed=actions_passed,
            expected=total_actions,
            actual=completed_actions,
            message=f"Actions: {completed_actions}/{total_actions} completed",
        ))

        # Check duration
        duration_passed = report.duration_ms <= self.criteria.max_load_time_ms * report.flows_total
        max_expected = self.criteria.max_load_time_ms * report.flows_total
        evaluation.add_result(CriterionResult(
            name="Total Duration",
            passed=duration_passed,
            expected=f"<= {max_expected}ms",
            actual=f"{report.duration_ms:.0f}ms",
            message=f"Total duration: {report.duration_ms:.0f}ms",
        ))

        # Check console errors
        console_passed = total_console_errors <= self.criteria.max_console_errors
        evaluation.add_result(CriterionResult(
            name="Console Errors",
            passed=console_passed,
            expected=f"<= {self.criteria.max_console_errors}",
            actual=total_console_errors,
            message=f"Console errors: {total_console_errors} (max: {self.criteria.max_console_errors})",
        ))

        # Check network failures
        network_passed = total_network_failures <= self.criteria.max_failed_requests
        evaluation.add_result(CriterionResult(
            name="Network Failures",
            passed=network_passed,
            expected=f"<= {self.criteria.max_failed_requests}",
            actual=total_network_failures,
            message=f"Network failures: {total_network_failures} (max: {self.criteria.max_failed_requests})",
        ))

        return evaluation

    def explain_failure(self, evaluation: CriteriaEvaluation) -> str:
        """
        Generate human-readable explanation of failures.

        Args:
            evaluation: CriteriaEvaluation to explain

        Returns:
            Formatted failure explanation
        """
        if evaluation.passed:
            return "All criteria passed."

        lines = ["FAILURE EXPLANATION:", ""]

        for i, failure in enumerate(evaluation.blocking_failures, 1):
            lines.append(f"  {i}. {failure}")

        if evaluation.warnings:
            lines.append("")
            lines.append("WARNINGS:")
            for warning in evaluation.warnings:
                lines.append(f"  - {warning}")

        return "\n".join(lines)
