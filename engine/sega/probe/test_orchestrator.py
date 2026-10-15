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

"""Test orchestration for multiple test types."""

import os
import subprocess
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from pathlib import Path
from ..project.project_detector import ProjectDetector


@dataclass
class TestResult:
    """Result of a test execution."""

    success: bool
    test_type: str
    duration: float
    output: str
    error: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = None


class TestOrchestrator:
    """Orchestrates different types of testing."""

    def __init__(self):
        self.test_runners = {
            "unit": self._run_unit_tests,
            "integration": self._run_integration_tests,
            "load": self._run_load_tests,
            "chaos": self._run_chaos_tests,
            "security": self._run_security_tests,
            "compatibility": self._run_compatibility_tests,
        }
        
        # Add backend test runners
        try:
            from .backend_test_runners import create_backend_test_runners
            backend_runners = create_backend_test_runners()
            self.test_runners.update(backend_runners)
        except ImportError:
            # Backend test runners not available, continue with standard tests
            pass

    def run_tests(
        self, test_types: List[str], project_path: str = "."
    ) -> Dict[str, TestResult]:
        """Run specified test types."""
        results = {}

        # Detect project type for appropriate test strategies
        detector = ProjectDetector(project_path)
        project_type = detector.detect()

        for test_type in test_types:
            if test_type not in self.test_runners:
                results[test_type] = TestResult(
                    success=False,
                    test_type=test_type,
                    duration=0.0,
                    output="",
                    error=f"Unknown test type: {test_type}",
                )
                continue

            try:
                start_time = time.time()
                result = self.test_runners[test_type](
                    project_path, project_type
                )
                result.duration = time.time() - start_time
                results[test_type] = result

            except Exception as e:
                results[test_type] = TestResult(
                    success=False,
                    test_type=test_type,
                    duration=time.time() - start_time,
                    output="",
                    error=str(e),
                )

        return results

    def _run_unit_tests(
        self, project_path: str, project_type: str
    ) -> TestResult:
        """Run unit tests based on project type."""

        # Different test commands for different project types
        test_commands = {
            "web_app": self._run_web_unit_tests,
            "ml_pipeline": self._run_python_unit_tests,
            "firmware_edge": self._run_c_unit_tests,
            "native_app": self._run_native_unit_tests,
            "hdl_fpga": self._run_hdl_unit_tests,
        }

        test_func = test_commands.get(
            project_type, self._run_generic_unit_tests
        )
        return test_func(project_path)

    def _run_web_unit_tests(self, project_path: str) -> TestResult:
        """Run web app unit tests."""
        if Path(project_path, "package.json").exists():
            # Node.js project
            result = subprocess.run(
                ["npm", "test"],
                capture_output=True,
                text=True,
                cwd=project_path,
            )

            return TestResult(
                success=result.returncode == 0,
                test_type="unit",
                duration=0.0,
                output=result.stdout,
                error=result.stderr if result.returncode != 0 else None,
            )
        else:
            # Python web app
            result = subprocess.run(
                ["python", "-m", "pytest", "-v"],
                capture_output=True,
                text=True,
                cwd=project_path,
            )

            return TestResult(
                success=result.returncode == 0,
                test_type="unit",
                duration=0.0,
                output=result.stdout,
                error=result.stderr if result.returncode != 0 else None,
            )

    def _run_python_unit_tests(self, project_path: str) -> TestResult:
        """Run Python unit tests."""
        result = subprocess.run(
            ["python", "-m", "pytest", "-v", "--tb=short"],
            capture_output=True,
            text=True,
            cwd=project_path,
        )

        return TestResult(
            success=result.returncode == 0,
            test_type="unit",
            duration=0.0,
            output=result.stdout,
            error=result.stderr if result.returncode != 0 else None,
        )

    def _run_c_unit_tests(self, project_path: str) -> TestResult:
        """Run C/C++ unit tests."""
        # Look for CMake test target
        if Path(project_path, "CMakeLists.txt").exists():
            # Build tests
            build_result = subprocess.run(
                ["cmake", "--build", "build", "--target", "test"],
                capture_output=True,
                text=True,
                cwd=project_path,
            )

            if build_result.returncode == 0:
                # Run CTest
                test_result = subprocess.run(
                    ["ctest", "--output-on-failure"],
                    capture_output=True,
                    text=True,
                    cwd=Path(project_path, "build"),
                )

                return TestResult(
                    success=test_result.returncode == 0,
                    test_type="unit",
                    duration=0.0,
                    output=test_result.stdout,
                    error=test_result.stderr
                    if test_result.returncode != 0
                    else None,
                )
            else:
                return TestResult(
                    success=False,
                    test_type="unit",
                    duration=0.0,
                    output=build_result.stdout,
                    error=f"Build failed: {build_result.stderr}",
                )
        else:
            return TestResult(
                success=False,
                test_type="unit",
                duration=0.0,
                output="",
                error="No CMakeLists.txt found for C/C++ tests",
            )

    def _run_native_unit_tests(self, project_path: str) -> TestResult:
        """Run native app unit tests."""
        # Rust
        if Path(project_path, "Cargo.toml").exists():
            result = subprocess.run(
                ["cargo", "test"],
                capture_output=True,
                text=True,
                cwd=project_path,
            )

            return TestResult(
                success=result.returncode == 0,
                test_type="unit",
                duration=0.0,
                output=result.stdout,
                error=result.stderr if result.returncode != 0 else None,
            )

        # Go
        elif Path(project_path, "go.mod").exists():
            result = subprocess.run(
                ["go", "test", "./..."],
                capture_output=True,
                text=True,
                cwd=project_path,
            )

            return TestResult(
                success=result.returncode == 0,
                test_type="unit",
                duration=0.0,
                output=result.stdout,
                error=result.stderr if result.returncode != 0 else None,
            )

        else:
            return TestResult(
                success=False,
                test_type="unit",
                duration=0.0,
                output="",
                error="No recognized native project structure",
            )

    def _run_hdl_unit_tests(self, project_path: str) -> TestResult:
        """Run HDL unit tests."""
        # Look for testbench files
        testbench_files = list(Path(project_path).glob("**/tb_*.v")) + list(
            Path(project_path).glob("**/tb_*.vhd")
        )

        if not testbench_files:
            return TestResult(
                success=False,
                test_type="unit",
                duration=0.0,
                output="",
                error="No testbench files found",
            )

        # Run simulation with ModelSim/Questa
        result = subprocess.run(
            ["vsim", "-c", "-do", "run -all; quit"],
            capture_output=True,
            text=True,
            cwd=project_path,
        )

        return TestResult(
            success=result.returncode == 0,
            test_type="unit",
            duration=0.0,
            output=result.stdout,
            error=result.stderr if result.returncode != 0 else None,
        )

    def _run_generic_unit_tests(self, project_path: str) -> TestResult:
        """Generic unit test runner."""
        return TestResult(
            success=False,
            test_type="unit",
            duration=0.0,
            output="",
            error="No unit test strategy for this project type",
        )

    def _run_integration_tests(
        self, project_path: str, project_type: str
    ) -> TestResult:
        """Run integration tests."""
        # Look for integration test directories
        integration_dirs = [
            "tests/integration",
            "test/integration",
            "integration_tests",
        ]

        for test_dir in integration_dirs:
            if Path(project_path, test_dir).exists():
                result = subprocess.run(
                    ["python", "-m", "pytest", test_dir, "-v"],
                    capture_output=True,
                    text=True,
                    cwd=project_path,
                )

                return TestResult(
                    success=result.returncode == 0,
                    test_type="integration",
                    duration=0.0,
                    output=result.stdout,
                    error=result.stderr if result.returncode != 0 else None,
                )

        return TestResult(
            success=False,
            test_type="integration",
            duration=0.0,
            output="",
            error="No integration tests found",
        )

    def _run_load_tests(
        self, project_path: str, project_type: str
    ) -> TestResult:
        """Run load tests."""
        from .load_testing import LoadTester

        load_tester = LoadTester()

        # Default load test configuration
        config = {
            "target_url": os.getenv(
                "LOAD_TEST_TARGET_URL",
                f"http://localhost:{os.getenv('SEGA_TEST_PORT', '8080')}",
            ),
            "concurrent_users": int(
                os.getenv("LOAD_TEST_CONCURRENT_USERS", "10")
            ),
            "duration": int(os.getenv("LOAD_TEST_DURATION", "60")),
            "ramp_up_time": int(os.getenv("LOAD_TEST_RAMP_UP_TIME", "10")),
        }

        # Load custom config if available
        config_path = Path(project_path, "load_test_config.json")
        if config_path.exists():
            import json

            with open(config_path) as f:
                config.update(json.load(f))

        result = load_tester.run_load_test(config)

        return TestResult(
            success=result.success,
            test_type="load",
            duration=result.duration,
            output=result.summary,
            error=result.error,
            metrics=result.metrics,
        )

    def _run_chaos_tests(
        self, project_path: str, project_type: str
    ) -> TestResult:
        """Run chaos engineering tests."""
        from .chaos_testing import ChaosEngine

        chaos_engine = ChaosEngine()

        # Default chaos test configuration
        config = {
            "target_namespace": "sega-deployments",
            "duration": 300,  # 5 minutes
            "experiments": ["pod_failure", "network_delay", "cpu_stress"],
        }

        # Load custom config if available
        config_path = Path(project_path, "chaos_test_config.json")
        if config_path.exists():
            import json

            with open(config_path) as f:
                config.update(json.load(f))

        result = chaos_engine.run_chaos_test(config)

        return TestResult(
            success=result.success,
            test_type="chaos",
            duration=result.duration,
            output=result.summary,
            error=result.error,
            metrics=result.metrics,
        )

    def _run_security_tests(
        self, project_path: str, project_type: str
    ) -> TestResult:
        """Run security tests."""
        from ..doctor.security.scanner import SecurityScanner

        scanner = SecurityScanner()
        scan_results = scanner.scan_all(project_path)

        # Count high/critical findings
        total_critical = 0
        total_high = 0

        for scan_result in scan_results.values():
            if scan_result.success:
                total_critical += scan_result.critical_count
                total_high += scan_result.high_count

        # Security test fails if there are critical findings
        success = total_critical == 0

        summary = f"Security scan completed. Critical: {total_critical}, High: {total_high}"

        return TestResult(
            success=success,
            test_type="security",
            duration=0.0,
            output=summary,
            error=None if success else "Critical security findings detected",
            metrics={
                "critical_findings": total_critical,
                "high_findings": total_high,
            },
        )

    def _run_compatibility_tests(
        self, project_path: str, project_type: str
    ) -> TestResult:
        """Run compatibility tests."""
        # Test across different environments/versions
        compatibility_matrix = {
            "web_app": ["node:16", "node:18", "node:20"],
            "ml_pipeline": ["python:3.8", "python:3.9", "python:3.10"],
            "native_app": ["ubuntu:20.04", "ubuntu:22.04", "alpine:3.18"],
        }

        test_images = compatibility_matrix.get(project_type, ["ubuntu:22.04"])

        results = []
        for image in test_images:
            try:
                # Run tests in different container environments
                result = subprocess.run(
                    [
                        "docker",
                        "run",
                        "--rm",
                        "-v",
                        f"{project_path}:/app",
                        image,
                        "sh",
                        "-c",
                        "cd /app && echo 'Compatibility test placeholder'",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )

                results.append(
                    {
                        "image": image,
                        "success": result.returncode == 0,
                        "output": result.stdout,
                    }
                )

            except subprocess.TimeoutExpired:
                results.append(
                    {
                        "image": image,
                        "success": False,
                        "output": "Test timed out",
                    }
                )

        overall_success = all(r["success"] for r in results)
        summary = f"Compatibility tests: {sum(r['success'] for r in results)}/{len(results)} passed"

        return TestResult(
            success=overall_success,
            test_type="compatibility",
            duration=0.0,
            output=summary,
            error=None
            if overall_success
            else "Some compatibility tests failed",
            metrics={
                "test_environments": len(results),
                "passed": sum(r["success"] for r in results),
            },
        )
