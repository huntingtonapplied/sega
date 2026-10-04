"""
Chained Test Runner
===================
Execute test chains with context passing between steps.
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from .chain_builder import TestChain, TestStep
from .extractors import TestContext


@dataclass
class StepResult:
    """Result of executing a single test step."""

    step_name: str
    endpoint: str
    method: str
    status_code: int
    success: bool
    duration_ms: float
    expected_status: List[int]
    response_data: Optional[Any] = None
    extracted_values: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class ChainResult:
    """Result of executing a test chain."""

    chain_name: str
    resource: str
    success: bool
    steps_executed: int
    steps_passed: int
    steps_failed: int
    step_results: List[StepResult] = field(default_factory=list)
    duration_seconds: float = 0.0
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class ChainedTestRunner:
    """Executes test chains with context passing."""

    def __init__(
        self,
        timeout: float = 30.0,
        auth_token: Optional[str] = None,
    ):
        self.timeout = timeout
        self.auth_token = auth_token

    async def run_chain(
        self,
        chain: TestChain,
        base_url: str,
        context: Optional[TestContext] = None,
        stop_on_failure: bool = True,
    ) -> ChainResult:
        """
        Execute a test chain with context passing between steps.

        Args:
            chain: TestChain to execute
            base_url: Base URL of the API
            context: Optional pre-populated context
            stop_on_failure: Stop chain on first failure (default True)

        Returns:
            ChainResult with all step results
        """
        context = context or TestContext()
        step_results: List[StepResult] = []
        start_time = time.perf_counter()

        for step in chain.steps:
            result = await self._run_step(step, base_url, context)
            step_results.append(result)

            # Extract values on success
            if result.success and step.extractors and result.response_data:
                try:
                    extracted = context.extract_and_store(
                        result.response_data, step.extractors
                    )
                    result.extracted_values = extracted
                except ValueError as e:
                    result.error = str(e)

            # Stop on failure if configured
            if not result.success and stop_on_failure:
                break

        duration = time.perf_counter() - start_time
        passed = sum(1 for r in step_results if r.success)
        failed = len(step_results) - passed

        return ChainResult(
            chain_name=chain.name,
            resource=chain.resource,
            success=failed == 0,
            steps_executed=len(step_results),
            steps_passed=passed,
            steps_failed=failed,
            step_results=step_results,
            duration_seconds=duration,
        )

    async def run_chains(
        self,
        chains: List[TestChain],
        base_url: str,
        parallel: bool = False,
    ) -> List[ChainResult]:
        """
        Execute multiple test chains.

        Args:
            chains: List of TestChains to execute
            base_url: Base URL of the API
            parallel: Run chains in parallel (default False for sequential)

        Returns:
            List of ChainResults
        """
        if parallel:
            tasks = [self.run_chain(chain, base_url) for chain in chains]
            return await asyncio.gather(*tasks)
        else:
            results = []
            for chain in chains:
                result = await self.run_chain(chain, base_url)
                results.append(result)
            return results

    async def _run_step(
        self,
        step: TestStep,
        base_url: str,
        context: TestContext,
    ) -> StepResult:
        """Execute a single test step."""
        # Substitute variables in endpoint
        endpoint = context.substitute(step.endpoint)
        url = f"{base_url}{endpoint}"

        # Substitute variables in body
        body = None
        if step.body:
            body = context.substitute_dict(step.body)

        # Build headers
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if step.headers:
            headers.update(step.headers)
        if step.requires_auth and self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        start_time = time.perf_counter()

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                if step.method == "GET":
                    response = await client.get(url, headers=headers)
                elif step.method == "POST":
                    response = await client.post(url, json=body, headers=headers)
                elif step.method == "PUT":
                    response = await client.put(url, json=body, headers=headers)
                elif step.method == "PATCH":
                    response = await client.patch(url, json=body, headers=headers)
                elif step.method == "DELETE":
                    response = await client.delete(url, headers=headers)
                else:
                    raise ValueError(f"Unsupported method: {step.method}")

                duration_ms = (time.perf_counter() - start_time) * 1000

                # Parse response
                try:
                    response_data = response.json()
                except Exception:
                    response_data = response.text[:500] if response.text else None

                success = response.status_code in step.expected_status

                return StepResult(
                    step_name=step.name,
                    endpoint=endpoint,
                    method=step.method,
                    status_code=response.status_code,
                    success=success,
                    duration_ms=duration_ms,
                    expected_status=step.expected_status,
                    response_data=response_data,
                )

        except httpx.ConnectError as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            return StepResult(
                step_name=step.name,
                endpoint=endpoint,
                method=step.method,
                status_code=0,
                success=False,
                duration_ms=duration_ms,
                expected_status=step.expected_status,
                error=f"Connection failed: {e}",
            )
        except httpx.TimeoutException:
            duration_ms = (time.perf_counter() - start_time) * 1000
            return StepResult(
                step_name=step.name,
                endpoint=endpoint,
                method=step.method,
                status_code=0,
                success=False,
                duration_ms=duration_ms,
                expected_status=step.expected_status,
                error=f"Timeout after {self.timeout}s",
            )
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            return StepResult(
                step_name=step.name,
                endpoint=endpoint,
                method=step.method,
                status_code=0,
                success=False,
                duration_ms=duration_ms,
                expected_status=step.expected_status,
                error=str(e),
            )


def print_chain_results(results: List[ChainResult]) -> None:
    """Pretty print chain execution results."""
    print("\n" + "=" * 70)
    print("TEST CHAIN RESULTS")
    print("=" * 70)

    total_passed = 0
    total_failed = 0

    for result in results:
        status = "PASSED" if result.success else "FAILED"
        status_color = "" if result.success else ""

        print(f"\nChain: {result.chain_name} [{status}]")
        print("-" * 50)

        for step_result in result.step_results:
            step_status = "" if step_result.success else ""
            extracted = ""
            if step_result.extracted_values:
                vals = ", ".join(
                    f"{k}={v}" for k, v in step_result.extracted_values.items()
                )
                extracted = f" (extracted: {vals})"

            if step_result.error:
                print(
                    f"  {step_status} {step_result.method} {step_result.endpoint} "
                    f"-> ERROR: {step_result.error}"
                )
            else:
                print(
                    f"  {step_status} {step_result.method} {step_result.endpoint} "
                    f"-> {step_result.status_code} ({step_result.duration_ms:.0f}ms){extracted}"
                )

        print(
            f"  Result: {result.steps_passed}/{result.steps_executed} steps passed "
            f"({result.duration_seconds:.2f}s)"
        )

        if result.success:
            total_passed += 1
        else:
            total_failed += 1

    print("\n" + "=" * 70)
    print(f"SUMMARY: {total_passed} chains passed, {total_failed} chains failed")
    print("=" * 70)
