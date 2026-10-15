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
SEGA Engine Test Runner
=======================
Orchestrates low-level engine testing for Rust, C++, and Python engines
"""

import os
import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass
from ..utils.paths import get_fleet_root

@dataclass
class EngineTestResult:
    """Result of engine test execution."""
    project: str
    engine_type: str
    passed: int
    failed: int
    duration: float
    benchmarks: Dict[str, float]
    memory_usage: Optional[int]
    coverage: Optional[float]

class EngineTestRunner:
    """Orchestrates low-level engine testing across FLEET projects."""
    
    def __init__(self, fleet_root: Optional[str] = None):
        self.fleet_root = Path(fleet_root) if fleet_root else get_fleet_root()
        self.test_env_path = self.fleet_root / "test-environments" / "engine"
        
    def run_engine_tests(self, project: str, engine_type: str, 
                        options: Dict[str, Any] = None) -> EngineTestResult:
        """Run engine tests for a specific project."""
        options = options or {}
        
        runners = {
            'rust': self.run_rust_engine_tests,
            'cpp': self.run_cpp_engine_tests,
            'python': self.run_python_engine_tests,
            'cuda': self.run_cuda_tests,
        }
        
        if engine_type not in runners:
            raise ValueError(f"Unknown engine type: {engine_type}")
            
        return runners[engine_type](project, options)
    
    def run_rust_engine_tests(self, project: str, options: Dict[str, Any]) -> EngineTestResult:
        """Run Rust engine tests using cargo."""
        project_path = self.fleet_root / project / "engine"
        
        if not (project_path / "Cargo.toml").exists():
            print(f"No Rust engine found for {project}")
            return self._empty_result(project, "rust")
        
        env = os.environ.copy()
        env['RUST_BACKTRACE'] = '1'
        env['RUST_TEST_THREADS'] = str(options.get('threads', 1))
        
        # Run tests
        cmd = ["cargo", "test"]
        if options.get('releBase', True):
            cmd.append('--releBase')
        if options.get('verbose', False):
            cmd.append('--verbose')
            
        result = subprocess.run(
            cmd, 
            cwd=project_path, 
            env=env, 
            capture_output=True, 
            text=True
        )
        
        # Parse test results
        test_result = self._parse_cargo_test_output(result.stdout)
        
        # Run benchmarks if requested
        benchmarks = {}
        if options.get('benchmark', False):
            bench_result = subprocess.run(
                ["cargo", "bench", "--no-fail-fast"],
                cwd=project_path,
                env=env,
                capture_output=True,
                text=True
            )
            benchmarks = self._parse_cargo_bench_output(bench_result.stdout)
        
        # Get memory usage if available
        memory_usage = None
        if options.get('memory_profile', False):
            memory_usage = self._profile_rust_memory(project_path)
        
        # Get coverage if tarpaulin is available
        coverage = None
        if options.get('coverage', False):
            coverage = self._get_rust_coverage(project_path)
        
        return EngineTestResult(
            project=project,
            engine_type="rust",
            passed=test_result.get('passed', 0),
            failed=test_result.get('failed', 0),
            duration=test_result.get('duration', 0.0),
            benchmarks=benchmarks,
            memory_usage=memory_usage,
            coverage=coverage
        )
    
    def run_cpp_engine_tests(self, project: str, options: Dict[str, Any]) -> EngineTestResult:
        """Run C++ engine tests using CMake/CTest."""
        project_path = self.fleet_root / project / "engine"
        build_path = project_path / "build"
        
        if not (project_path / "CMakeLists.txt").exists():
            print(f"No C++ engine found for {project}")
            return self._empty_result(project, "cpp")
        
        # Build if needed
        if not build_path.exists() or options.get('rebuild', False):
            build_path.mkdir(exist_ok=True)
            subprocess.run(
                ["cmake", "..", "-DCMAKE_BUILD_TYPE=ReleBase"],
                cwd=build_path,
                check=True
            )
            subprocess.run(
                ["make", "-j", str(os.cpu_count())],
                cwd=build_path,
                check=True
            )
        
        # Run tests
        result = subprocess.run(
            ["ctest", "--output-on-failure", "--output-junit", "test-results.xml"],
            cwd=build_path,
            capture_output=True,
            text=True
        )
        
        # Parse CTest results
        test_results = self._parse_ctest_xml(build_path / "test-results.xml")
        
        # Run benchmarks with Google Benchmark if available
        benchmarks = {}
        if options.get('benchmark', False):
            bench_exe = build_path / "benchmark" / "engine_benchmark"
            if bench_exe.exists():
                bench_result = subprocess.run(
                    [str(bench_exe), "--benchmark_format=json"],
                    capture_output=True,
                    text=True
                )
                benchmarks = self._parse_google_benchmark_json(bench_result.stdout)
        
        return EngineTestResult(
            project=project,
            engine_type="cpp",
            passed=test_results.get('passed', 0),
            failed=test_results.get('failed', 0),
            duration=test_results.get('duration', 0.0),
            benchmarks=benchmarks,
            memory_usage=None,
            coverage=None
        )
    
    def run_python_engine_tests(self, project: str, options: Dict[str, Any]) -> EngineTestResult:
        """Run Python engine tests using pytest."""
        project_path = self.fleet_root / project
        engine_path = project_path / "engine"
        
        if not engine_path.exists():
            engine_path = project_path / "backend" / "engine"
        
        if not engine_path.exists():
            print(f"No Python engine found for {project}")
            return self._empty_result(project, "python")
        
        # Run pytest with engine marker
        cmd = [
            "pytest",
            "-m", "engine",
            "--json-report",
            "--json-report-file=/tmp/engine-test-report.json"
        ]
        
        if options.get('verbose', False):
            cmd.append('-v')
        if options.get('coverage', False):
            cmd.extend(['--cov=engine', '--cov-report=json'])
            
        result = subprocess.run(
            cmd,
            cwd=project_path,
            capture_output=True,
            text=True
        )
        
        # Parse pytest results
        test_results = self._parse_pytest_json("/tmp/engine-test-report.json")
        
        # Run benchmarks with pytest-benchmark
        benchmarks = {}
        if options.get('benchmark', False):
            bench_result = subprocess.run(
                ["pytest", "-m", "benchmark", "--benchmark-json=/tmp/benchmark.json"],
                cwd=project_path,
                capture_output=True,
                text=True
            )
            benchmarks = self._parse_pytest_benchmark_json("/tmp/benchmark.json")
        
        # Get memory profiling if requested
        memory_usage = None
        if options.get('memory_profile', False):
            memory_usage = self._profile_python_memory(engine_path)
        
        return EngineTestResult(
            project=project,
            engine_type="python",
            passed=test_results.get('passed', 0),
            failed=test_results.get('failed', 0),
            duration=test_results.get('duration', 0.0),
            benchmarks=benchmarks,
            memory_usage=memory_usage,
            coverage=test_results.get('coverage', None)
        )
    
    def run_cuda_tests(self, project: str, options: Dict[str, Any]) -> EngineTestResult:
        """Run CUDA engine tests."""
        # Placeholder for CUDA testing
        print(f"CUDA testing for {project} not yet implemented")
        return self._empty_result(project, "cuda")
    
    def _parse_cargo_test_output(self, output: str) -> Dict[str, Any]:
        """Parse cargo test output."""
        lines = output.split('\n')
        passed = failed = 0
        duration = 0.0
        
        for line in lines:
            if 'test result:' in line:
                parts = line.split()
                for i, part in enumerate(parts):
                    if part == 'passed;' and i > 0:
                        passed = int(parts[i-1])
                    elif part == 'failed;' and i > 0:
                        failed = int(parts[i-1])
            elif 'finished in' in line:
                # Extract duration
                import re
                match = re.search(r'(\d+\.\d+)s', line)
                if match:
                    duration = float(match.group(1))
                    
        return {'passed': passed, 'failed': failed, 'duration': duration}
    
    def _parse_cargo_bench_output(self, output: str) -> Dict[str, float]:
        """Parse cargo bench output."""
        benchmarks = {}
        lines = output.split('\n')
        
        for line in lines:
            if 'bench:' in line:
                parts = line.split()
                if len(parts) >= 3:
                    name = parts[0].replace('test', '').strip()
                    # Extract time value
                    for part in parts:
                        if 'ns/iter' in part:
                            value = float(part.replace('ns/iter', '').replace(',', ''))
                            benchmarks[name] = value / 1_000_000  # Convert to ms
                            
        return benchmarks
    
    def _parse_ctest_xml(self, xml_path: Path) -> Dict[str, Any]:
        """Parse CTest XML output."""
        if not xml_path.exists():
            return {'passed': 0, 'failed': 0, 'duration': 0.0}
            
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        tests = root.findall('.//Test')
        passed = sum(1 for t in tests if t.get('Status') == 'passed')
        failed = sum(1 for t in tests if t.get('Status') == 'failed')
        
        # Calculate total duration
        duration = 0.0
        for t in tests:
            time_elem = t.find('Time')
            if time_elem is not None:
                duration += float(time_elem.text)
                
        return {'passed': passed, 'failed': failed, 'duration': duration}
    
    def _parse_pytest_json(self, json_path: str) -> Dict[str, Any]:
        """Parse pytest JSON report."""
        if not Path(json_path).exists():
            return {'passed': 0, 'failed': 0, 'duration': 0.0}
            
        with open(json_path, 'r') as f:
            report = json.load(f)
            
        summary = report.get('summary', {})
        return {
            'passed': summary.get('passed', 0),
            'failed': summary.get('failed', 0),
            'duration': report.get('duration', 0.0),
            'coverage': summary.get('coverage', None)
        }
    
    def _empty_result(self, project: str, engine_type: str) -> EngineTestResult:
        """Return empty test result."""
        return EngineTestResult(
            project=project,
            engine_type=engine_type,
            passed=0,
            failed=0,
            duration=0.0,
            benchmarks={},
            memory_usage=None,
            coverage=None
        )
    
    def _profile_rust_memory(self, project_path: Path) -> Optional[int]:
        """Profile Rust memory usage using valgrind or heaptrack."""
        # Placeholder - would integrate memory profiling tools
        return None
    
    def _get_rust_coverage(self, project_path: Path) -> Optional[float]:
        """Get Rust code coverage using tarpaulin."""
        # Placeholder - would integrate cargo-tarpaulin
        return None
    
    def _profile_python_memory(self, engine_path: Path) -> Optional[int]:
        """Profile Python memory usage using memory_profiler."""
        # Placeholder - would integrate memory_profiler
        return None
    
    def _parse_google_benchmark_json(self, output: str) -> Dict[str, float]:
        """Parse Google Benchmark JSON output."""
        try:
            data = json.loads(output)
            benchmarks = {}
            for bench in data.get('benchmarks', []):
                name = bench['name']
                time = bench['real_time'] / 1_000_000  # Convert ns to ms
                benchmarks[name] = time
            return benchmarks
        except:
            return {}
    
    def _parse_pytest_benchmark_json(self, json_path: str) -> Dict[str, float]:
        """Parse pytest-benchmark JSON output."""
        if not Path(json_path).exists():
            return {}
            
        with open(json_path, 'r') as f:
            data = json.load(f)
            
        benchmarks = {}
        for bench in data.get('benchmarks', []):
            name = bench['name']
            time = bench['stats']['mean'] * 1000  # Convert to ms
            benchmarks[name] = time
            
        return benchmarks