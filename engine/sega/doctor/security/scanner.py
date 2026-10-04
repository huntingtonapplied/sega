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
SEGA SECURITY VULNERABILITY SCANNER
==============================================================================
File: src/sega/security/scanner.py
Project: SEGA (Scalable Engineering & Growth Automation)
Copyright: 2022-2025 FLEET
License: Apache-2.0

SEGA MODULE: Security/VulnerabilityScanning
COMPONENT: Multi-Type Security Scanner Engine
PURPOSE: Execute comprehensive security scans across multiple vulnerability types
DEPENDENCIES: subprocess, json, os, shlex, dataclasses, pathlib, tempfile, re
USAGE: scanner = SecurityScanner(); results = scanner.scan(scan_types, severity)

This scanner executes dependency, static analysis, container, infrastructure, and
secrets scanning with configurable severity levels and output formats.
==============================================================================
"""

import subprocess
import json
import os
from dataclasses import dataclass
from typing import List, Dict, Optional
from pathlib import Path
import tempfile
import re


@dataclass
class SecurityFinding:
    """Security finding from scan."""

    severity: str
    title: str
    description: str
    file_path: str
    line_number: int
    cve_id: Optional[str] = None
    fix_suggestion: Optional[str] = None


@dataclass
class SecurityScanResult:
    """Result of security scan."""

    success: bool
    findings: List[SecurityFinding]
    scan_type: str
    error: Optional[str] = None

    @property
    def critical_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "critical")

    @property
    def high_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "high")

    @property
    def medium_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "medium")

    @property
    def low_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "low")


class SecurityScanner:
    """Multi-tool security scanner."""

    # Severity level constants
    SEVERITY_CRITICAL = "critical"
    SEVERITY_HIGH = "high"
    SEVERITY_MEDIUM = "medium"
    SEVERITY_LOW = "low"
    SEVERITY_INFO = "info"

    def __init__(self):
        self.scanners = {
            "dependency": self._scan_dependencies,
            "static": self._scan_static_analysis,
            "container": self._scan_container,
            "infrastructure": self._scan_infrastructure,
            "secrets": self._scan_secrets,
        }

    def _safe_get_cve_id(self, vuln_data: dict) -> str:
        """Safely extract CVE ID from vulnerability data with type validation."""
        cve_data = vuln_data.get("cve")
        if not cve_data:
            return None

        # Handle different CVE data formats
        if isinstance(cve_data, list):
            return cve_data[0] if cve_data else None
        elif isinstance(cve_data, str):
            return cve_data
        else:
            # Log unexpected format for debugging
            print(f"Warning: Unexpected CVE data format: {type(cve_data)}")
            return None

    def _safe_rglob(self, base_path: Path, pattern: str):
        """Safe recursive globbing that prevents symlink traversal and cycle detection."""
        base_resolved = base_path.resolve()
        visited = set()

        def _recursive_glob(current_path):
            # Resolve current path to detect cycles
            try:
                resolved_path = current_path.resolve()
            except OSError:
                # Path doesn't exist or can't be resolved
                return

            # Check for cycles
            if resolved_path in visited:
                return
            visited.add(resolved_path)

            # Ensure we're still within the base directory
            try:
                resolved_path.relative_to(base_resolved)
            except ValueError:
                # Path is outside base directory
                return

            # Skip symlinks to prevent traversal
            if current_path.is_symlink():
                return

            try:
                if current_path.is_file() and current_path.match(pattern):
                    yield current_path
                elif current_path.is_dir():
                    for child in current_path.iterdir():
                        yield from _recursive_glob(child)
            except (OSError, PermissionError):
                # Skip inaccessible directories
                pass

        return _recursive_glob(base_path)

    def _validate_path(self, path: str) -> Path:
        """Validate and sanitize file path to prevent directory traversal."""
        try:
            # Get current working directory
            cwd = Path.cwd().resolve()
            
            # First validate the raw path string before any resolution
            # This prevents bypassing validation with symlinks or other tricks
            if '..' in path or path.startswith('/'):
                # For absolute paths, check if they're within the working directory
                if path.startswith('/'):
                    test_path = Path(path).resolve()
                    try:
                        test_path.relative_to(cwd)
                    except ValueError:
                        raise ValueError("Absolute path outside working directory not allowed")
                else:
                    # Reject any path with parent directory references
                    raise ValueError("Path traversal attempts not allowed")

            # Now check if the path exists and is a symlink
            path_obj = Path(path)
            if path_obj.exists() and path_obj.is_symlink():
                # Check the symlink target
                target = Path(os.readlink(path_obj)).resolve()
                try:
                    target.relative_to(cwd)
                except ValueError:
                    raise ValueError(
                        "Symlink target outside working directory not allowed"
                    )

            # Resolve the input path to handle symlinks and relative paths
            clean_path = path_obj.resolve()

            # Check if the resolved path is within the current working directory
            try:
                clean_path.relative_to(cwd)
            except ValueError:
                raise ValueError("Path outside working directory not allowed")

            # Additional validation to prevent path traversal attacks
            # Check for suspicious path components in the resolved path
            path_str = str(clean_path)
            if any(component in path_str for component in ['..', './', '\\']):
                # These should have been resolved, if they're still present it's suspicious
                raise ValueError("Suspicious path components detected")

            return clean_path
        except (OSError, ValueError) as e:
            raise ValueError(f"Invalid path: {e}")

    def _safe_subprocess_run(
        self, cmd: List[str], **kwargs
    ) -> subprocess.CompletedProcess:
        """Safely execute subprocess with input validation."""
        # Validate command components
        if not cmd or not isinstance(cmd, list):
            raise ValueError("Command must be a non-empty list")

        # Ensure first element is a known safe command
        safe_commands = {
            "npm",
            "safety",
            "bandit",
            "cargo",
            "govulncheck",
            "docker",
            "trivy",
            "tfsec",
            "kubesec",
            "kube-score",
            "trufflehog",
        }

        base_cmd = cmd[0]
        if base_cmd not in safe_commands:
            raise ValueError(f"Command '{base_cmd}' not in allowlist")

        # Define allowed argument patterns for each command
        allowed_args = {
            "npm": {"audit", "--json", "install", "test", "run", "ci"},
            "safety": {"check", "--json", "--continue-on-error"},
            "bandit": {"-r", "--format", "json", "-l", "-ll", "-lll"},
            "cargo": {"audit", "--json"},
            "govulncheck": {"--json"},
            "docker": {"build", "scan", "--file", "-f", "-t", ".", "--severity"},
            "trivy": {"image", "--format", "json", "--severity", "HIGH,CRITICAL"},
            "tfsec": {"--format", "json", ".", "--no-color"},
            "kubesec": {"scan"},
            "kube-score": {"score", "--output-format", "json"},
            "trufflehog": {"filesystem", "--json", "--no-update"},
        }

        # Validate command arguments to prevent injection
        dangerous_chars = {
            "&",
            "|",
            ";",
            "$",
            "`",
            "\n",
            "\r",
            "(",
            ")",
            "{",
            "}",
            "<",
            ">",
            "\\",
        }

        # Get allowed args for this command
        cmd_allowed_args = allowed_args.get(base_cmd, set())
        
        for i, arg in enumerate(cmd[1:], 1):
            if not isinstance(arg, str):
                raise ValueError(
                    f"Command argument must be string, got {type(arg)}"
                )
            
            # Check for dangerous characters
            if any(char in arg for char in dangerous_chars):
                raise ValueError(
                    f"Dangerous character in command argument: {arg}"
                )
            
            # For file paths and similar arguments, validate they don't escape
            if arg.startswith("/") or ".." in arg:
                # Allow specific safe paths
                if arg not in [".", "./", "--json"] and not arg.startswith("--"):
                    raise ValueError(f"Absolute or parent directory paths not allowed: {arg}")
            
            # Check if argument is in allowed list (unless it's a file path after a flag)
            prev_arg = cmd[i-1] if i > 1 else ""
            if prev_arg not in ["--file", "-f", "-r"] and not arg.startswith("--"):
                if arg not in cmd_allowed_args and not Path(arg).exists():
                    raise ValueError(f"Argument '{arg}' not in allowlist for {base_cmd}")

        # Remove shell=True to prevent shell injection
        kwargs.pop("shell", None)

        # Set secure defaults
        kwargs.setdefault("capture_output", True)
        kwargs.setdefault("text", True)

        # Make timeout configurable via environment variable
        try:
            default_timeout = int(
                os.getenv("SEGA_SECURITY_SCAN_TIMEOUT", "300")
            )
            if default_timeout < 1:
                raise ValueError("Timeout must be at least 1 second")
        except (ValueError, TypeError):
            default_timeout = 300  # 5 minute fallback
        kwargs.setdefault("timeout", default_timeout)

        try:
            return subprocess.run(cmd, **kwargs)
        except subprocess.TimeoutExpired:
            raise ValueError("Command timed out")
        except FileNotFoundError:
            raise ValueError(f"Command '{base_cmd}' not found")

    def scan_all(
        self, project_path: str = "."
    ) -> Dict[str, SecurityScanResult]:
        """Run all security scans."""
        results = {}

        try:
            # Validate the project path
            validated_path = self._validate_path(project_path)
        except ValueError as e:
            # Return error for all scanners if path is invalid
            for scan_type in self.scanners.keys():
                results[scan_type] = SecurityScanResult(
                    success=False,
                    findings=[],
                    scan_type=scan_type,
                    error=f"Invalid project path: {e}",
                )
            return results

        for scan_type, scanner_func in self.scanners.items():
            try:
                result = scanner_func(str(validated_path))
                results[scan_type] = result
            except Exception as e:
                results[scan_type] = SecurityScanResult(
                    success=False,
                    findings=[],
                    scan_type=scan_type,
                    error=str(e),
                )

        return results

    def _scan_dependencies(self, project_path: str) -> SecurityScanResult:
        """Scan dependencies for known vulnerabilities."""
        findings = []

        # Check for different dependency files
        dependency_files = [
            ("package.json", self._scan_npm_deps),
            ("requirements.txt", self._scan_pip_deps),
            ("Cargo.toml", self._scan_cargo_deps),
            ("go.mod", self._scan_go_deps),
        ]

        success = True
        error_message = None

        for dep_file, scanner_func in dependency_files:
            file_path = Path(project_path) / dep_file
            if file_path.exists():
                try:
                    dep_findings = scanner_func(file_path)
                    findings.extend(dep_findings)
                except ValueError as e:
                    if "timed out" in str(e).lower():
                        success = False
                        error_message = f"Scan timeout occurred: {str(e)}"
                    findings.append(
                        SecurityFinding(
                            severity=self.SEVERITY_MEDIUM,
                            title=f"Dependency scan error for {dep_file}",
                            description=str(e),
                            file_path=str(file_path),
                            line_number=1,
                        )
                    )
                except Exception as e:
                    success = False
                    error_message = (
                        f"Unexpected error during dependency scan: {str(e)}"
                    )
                    findings.append(
                        SecurityFinding(
                            severity=self.SEVERITY_MEDIUM,
                            title=f"Dependency scan error for {dep_file}",
                            description=str(e),
                            file_path=str(file_path),
                            line_number=1,
                        )
                    )

        return SecurityScanResult(
            success=success,
            findings=findings,
            scan_type="dependency",
            error=error_message,
        )

    def _scan_npm_deps(self, package_json_path: Path) -> List[SecurityFinding]:
        """Scan npm dependencies."""
        findings = []

        try:
            # Run npm audit with safe subprocess
            result = self._safe_subprocess_run(
                ["npm", "audit", "--json"], cwd=str(package_json_path.parent)
            )

            if result.returncode != 0 and result.stdout:
                audit_data = json.loads(result.stdout)

                for vuln_id, vuln_data in audit_data.get(
                    "vulnerabilities", {}
                ).items():
                    severity = vuln_data.get("severity", "unknown")
                    title = vuln_data.get("title", "Unknown vulnerability")

                    finding = SecurityFinding(
                        severity=severity,
                        title=f"npm: {title}",
                        description=vuln_data.get(
                            "overview", "No description"
                        ),
                        file_path=str(package_json_path),
                        line_number=1,
                        cve_id=self._safe_get_cve_id(vuln_data),
                        fix_suggestion=f"Update to {vuln_data.get('patched_versions', 'latest')}",
                    )
                    findings.append(finding)

        except ValueError:
            # Re-raise ValueError to allow timeout detection in calling method
            raise
        except subprocess.SubprocessError as e:
            # Log subprocess errors for debugging
            print(f"Warning: Subprocess error in dependency scan: {e}")
        except json.JSONDecodeError as e:
            # Log JSON parsing errors for debugging
            print(f"Warning: Failed to parse dependency scan output: {e}")

        return findings

    def _scan_pip_deps(self, requirements_path: Path) -> List[SecurityFinding]:
        """Scan pip dependencies."""
        findings = []

        try:
            # Use safety to scan Python dependencies
            result = self._safe_subprocess_run(
                ["safety", "check", "--json", "-r", str(requirements_path)]
            )

            if result.returncode != 0 and result.stdout:
                safety_data = json.loads(result.stdout)

                for vuln in safety_data:
                    finding = SecurityFinding(
                        severity=self.SEVERITY_HIGH,  # Safety typically reports high severity
                        title=f"pip: {vuln.get('advisory', 'Vulnerability')}",
                        description=vuln.get("advisory", "No description"),
                        file_path=str(requirements_path),
                        line_number=1,
                        cve_id=vuln.get("id"),
                        fix_suggestion=f"Update {vuln.get('package_name')} to {vuln.get('analyzed_version')}",
                    )
                    findings.append(finding)

        except ValueError:
            # Re-raise ValueError to allow timeout detection in calling method
            raise
        except subprocess.SubprocessError as e:
            # Log subprocess errors for debugging
            print(f"Warning: Subprocess error in dependency scan: {e}")
        except json.JSONDecodeError as e:
            # Log JSON parsing errors for debugging
            print(f"Warning: Failed to parse dependency scan output: {e}")

        return findings

    def _scan_cargo_deps(self, cargo_path: Path) -> List[SecurityFinding]:
        """Scan Rust dependencies."""
        findings = []

        try:
            # Use cargo-audit
            result = self._safe_subprocess_run(
                ["cargo", "audit", "--json"], cwd=str(cargo_path.parent)
            )

            if result.returncode != 0 and result.stdout:
                audit_data = json.loads(result.stdout)

                for vuln in audit_data.get("vulnerabilities", {}).get(
                    "list", []
                ):
                    finding = SecurityFinding(
                        severity=self.SEVERITY_HIGH,
                        title=f"cargo: {vuln.get('advisory', {}).get('title', 'Vulnerability')}",
                        description=vuln.get("advisory", {}).get(
                            "description", "No description"
                        ),
                        file_path=str(cargo_path),
                        line_number=1,
                        cve_id=vuln.get("advisory", {}).get("id"),
                        fix_suggestion="Update dependency version",
                    )
                    findings.append(finding)

        except ValueError:
            # Re-raise ValueError to allow timeout detection in calling method
            raise
        except subprocess.SubprocessError as e:
            # Log subprocess errors for debugging
            print(f"Warning: Subprocess error in dependency scan: {e}")
        except json.JSONDecodeError as e:
            # Log JSON parsing errors for debugging
            print(f"Warning: Failed to parse dependency scan output: {e}")

        return findings

    def _scan_go_deps(self, go_mod_path: Path) -> List[SecurityFinding]:
        """Scan Go dependencies."""
        findings = []

        try:
            # Use govulncheck
            result = self._safe_subprocess_run(
                ["govulncheck", "-json", "./..."], cwd=str(go_mod_path.parent)
            )

            if result.returncode != 0 and result.stdout:
                for line in result.stdout.split("\n"):
                    if line.strip():
                        vuln_data = json.loads(line)
                        if vuln_data.get("finding"):
                            finding = SecurityFinding(
                                severity=self.SEVERITY_HIGH,
                                title=f"go: {vuln_data.get('finding', {}).get('title', 'Vulnerability')}",
                                description=vuln_data.get("finding", {}).get(
                                    "description", "No description"
                                ),
                                file_path=str(go_mod_path),
                                line_number=1,
                                fix_suggestion="Update dependency version",
                            )
                            findings.append(finding)

        except ValueError:
            # Re-raise ValueError to allow timeout detection in calling method
            raise
        except subprocess.SubprocessError as e:
            # Log subprocess errors for debugging
            print(f"Warning: Subprocess error in dependency scan: {e}")
        except json.JSONDecodeError as e:
            # Log JSON parsing errors for debugging
            print(f"Warning: Failed to parse dependency scan output: {e}")

        return findings

    def _scan_static_analysis(self, project_path: str) -> SecurityScanResult:
        """Static code analysis for security issues."""
        findings = []

        # Scan for common security patterns
        security_patterns = [
            (
                r"password\s*=\s*['\"][^'\"]*['\"]",
                "hardcoded_password",
                "Hardcoded password detected",
            ),
            (
                r"api_key\s*=\s*['\"][^'\"]*['\"]",
                "hardcoded_api_key",
                "Hardcoded API key detected",
            ),
            (
                r"secret\s*=\s*['\"][^'\"]*['\"]",
                "hardcoded_secret",
                "Hardcoded secret detected",
            ),
            (
                r"eval\s*\(",
                "code_injection",
                "Potential code injection with eval()",
            ),
            (
                r"exec\s*\(",
                "code_injection",
                "Potential code injection with exec()",
            ),
            (
                r"os\.system\s*\(",
                "command_injection",
                "Potential command injection",
            ),
            (
                r"subprocess\.(call|run|Popen)\s*\([^)]{0,200}shell\s*=\s*True",
                "shell_injection",
                "Shell injection risk",
            ),
        ]


        # Use followlinks=False to prevent symlink traversal attacks
        for root, _, files in os.walk(project_path, followlinks=False):
            # Additional security check: ensure we're still within project directory
            root_path = Path(root).resolve()
            try:
                root_path.relative_to(Path(project_path).resolve())
            except ValueError:
                # Skip directories outside project path
                continue

            for file in files:
                if file.endswith(
                    (".py", ".js", ".ts", ".java", ".c", ".cpp", ".go", ".rs")
                ):
                    file_path = Path(root) / file

                    # Skip symlinks to prevent traversal
                    if file_path.is_symlink():
                        continue
                    try:
                        content = file_path.read_text(encoding="utf-8")
                        lines = content.split("\n")

                        for line_num, line in enumerate(lines, 1):
                            for (
                                pattern,
                                vuln_type,
                                description,
                            ) in security_patterns:
                                if re.search(pattern, line, re.IGNORECASE):
                                    finding = SecurityFinding(
                                        severity=self.SEVERITY_HIGH
                                        if "injection" in vuln_type
                                        else "medium",
                                        title=f"Static analysis: {vuln_type}",
                                        description=description,
                                        file_path=str(file_path),
                                        line_number=line_num,
                                        fix_suggestion="Review and remediate security issue",
                                    )
                                    findings.append(finding)
                    except (UnicodeDecodeError, PermissionError):
                        continue

        return SecurityScanResult(
            success=True, findings=findings, scan_type="static"
        )

    def _scan_container(self, project_path: str) -> SecurityScanResult:
        """Scan container images for vulnerabilities."""
        findings = []

        # Look for Dockerfile
        dockerfile_path = Path(project_path) / "Dockerfile"
        if not dockerfile_path.exists():
            return SecurityScanResult(
                success=True, findings=[], scan_type="container"
            )

        tmp_file_path = None
        # Generate unique Docker tag to prevent race conditions
        import uuid

        docker_tag = f"sega-scan:{uuid.uuid4().hex[:8]}"

        try:
            # Build image for scanning
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".tar", delete=False
            ) as tmp_file:
                tmp_file_path = tmp_file.name
                build_result = self._safe_subprocess_run(
                    ["docker", "build", "-t", docker_tag, "."],
                    cwd=project_path,
                )

                if build_result.returncode != 0:
                    return SecurityScanResult(
                        success=False,
                        findings=[],
                        scan_type="container",
                        error=f"Docker build failed: {build_result.stderr}",
                    )

                # Use trivy for container scanning
                scan_result = self._safe_subprocess_run(
                    ["trivy", "image", "--format", "json", docker_tag]
                )

                if scan_result.returncode == 0 and scan_result.stdout:
                    trivy_data = json.loads(scan_result.stdout)

                    for result in trivy_data.get("Results", []):
                        for vuln in result.get("Vulnerabilities", []):
                            finding = SecurityFinding(
                                severity=vuln.get(
                                    "Severity", "unknown"
                                ).lower(),
                                title=f"Container: {vuln.get('VulnerabilityID', 'Unknown')}",
                                description=vuln.get(
                                    "Description", "No description"
                                ),
                                file_path=str(dockerfile_path),
                                line_number=1,
                                cve_id=vuln.get("VulnerabilityID"),
                                fix_suggestion=f"Update {vuln.get('PkgName', 'package')} to {vuln.get('FixedVersion', 'latest')}",
                            )
                            findings.append(finding)

        except Exception as e:
            return SecurityScanResult(
                success=False, findings=[], scan_type="container", error=str(e)
            )
        finally:
            # Clean up temporary file and Docker image
            if tmp_file_path and os.path.exists(tmp_file_path):
                try:
                    os.unlink(tmp_file_path)
                except OSError:
                    pass  # File might have been cleaned up already

            # Clean up Docker image
            try:
                self._safe_subprocess_run(["docker", "rmi", docker_tag])
            except (subprocess.CalledProcessError, FileNotFoundError, OSError):
                pass  # Image might not exist or Docker might not be available

        return SecurityScanResult(
            success=True, findings=findings, scan_type="container"
        )

    def _scan_infrastructure(self, project_path: str) -> SecurityScanResult:
        """Scan infrastructure as code for security issues."""
        findings = []

        # Scan Terraform files
        terraform_path = Path(project_path) / "infrastructure" / "terraform"
        if terraform_path.exists():
            findings.extend(self._scan_terraform(terraform_path))

        # Scan Kubernetes manifests
        k8s_path = Path(project_path) / "infrastructure" / "helm"
        if k8s_path.exists():
            findings.extend(self._scan_kubernetes(k8s_path))

        return SecurityScanResult(
            success=True, findings=findings, scan_type="infrastructure"
        )

    def _scan_terraform(self, terraform_path: Path) -> List[SecurityFinding]:
        """Scan Terraform files."""
        findings = []

        try:
            # Use tfsec for Terraform scanning
            result = self._safe_subprocess_run(
                ["tfsec", "--format", "json", str(terraform_path)]
            )

            if result.returncode != 0 and result.stdout:
                tfsec_data = json.loads(result.stdout)

                for finding_data in tfsec_data.get("results", []):
                    finding = SecurityFinding(
                        severity=finding_data.get(
                            "severity", "unknown"
                        ).lower(),
                        title=f"Terraform: {finding_data.get('rule_id', 'Security issue')}",
                        description=finding_data.get(
                            "description", "No description"
                        ),
                        file_path=finding_data.get("location", {}).get(
                            "filename", "unknown"
                        ),
                        line_number=finding_data.get("location", {}).get(
                            "start_line", 1
                        ),
                        fix_suggestion="Review Terraform configuration",
                    )
                    findings.append(finding)

        except ValueError:
            # Re-raise ValueError to allow timeout detection in calling method
            raise
        except subprocess.SubprocessError as e:
            # Log subprocess errors for debugging
            print(f"Warning: Subprocess error in dependency scan: {e}")
        except json.JSONDecodeError as e:
            # Log JSON parsing errors for debugging
            print(f"Warning: Failed to parse dependency scan output: {e}")

        return findings

    def _scan_kubernetes(self, k8s_path: Path) -> List[SecurityFinding]:
        """Scan Kubernetes manifests."""
        findings = []

        try:
            # Use kubesec for Kubernetes scanning (with symlink protection)
            for yaml_file in self._safe_rglob(k8s_path, "*.yaml"):
                result = self._safe_subprocess_run(
                    ["kubesec", "scan", str(yaml_file)]
                )

                if result.returncode == 0 and result.stdout:
                    kubesec_data = json.loads(result.stdout)

                    for scan_result in kubesec_data:
                        for advisory in scan_result.get("scoring", {}).get(
                            "advise", []
                        ):
                            finding = SecurityFinding(
                                severity=self.SEVERITY_MEDIUM,
                                title=f"Kubernetes: {advisory.get('selector', 'Security issue')}",
                                description=advisory.get(
                                    "reason", "No description"
                                ),
                                file_path=str(yaml_file),
                                line_number=1,
                                fix_suggestion="Review Kubernetes configuration",
                            )
                            findings.append(finding)

        except ValueError:
            # Re-raise ValueError to allow timeout detection in calling method
            raise
        except subprocess.SubprocessError as e:
            # Log subprocess errors for debugging
            print(f"Warning: Subprocess error in dependency scan: {e}")
        except json.JSONDecodeError as e:
            # Log JSON parsing errors for debugging
            print(f"Warning: Failed to parse dependency scan output: {e}")

        return findings

    def _scan_secrets(self, project_path: str) -> SecurityScanResult:
        """Scan for exposed secrets."""
        findings = []

        try:
            # Use truffleHog for secret scanning
            result = self._safe_subprocess_run(
                ["trufflehog", "filesystem", "--json", project_path]
            )

            if result.returncode == 0 and result.stdout:
                for line in result.stdout.split("\n"):
                    if line.strip():
                        secret_data = json.loads(line)

                        finding = SecurityFinding(
                            severity=self.SEVERITY_CRITICAL,
                            title=f"Secret: {secret_data.get('DetectorName', 'Unknown')}",
                            description="Exposed secret detected",
                            file_path=secret_data.get("SourceMetadata", {})
                            .get("Data", {})
                            .get("Filesystem", {})
                            .get("file", "unknown"),
                            line_number=secret_data.get("SourceMetadata", {})
                            .get("Data", {})
                            .get("Filesystem", {})
                            .get("line", 1),
                            fix_suggestion="Remove or encrypt secret",
                        )
                        findings.append(finding)

        except ValueError:
            # Re-raise ValueError to allow timeout detection in calling method
            raise
        except subprocess.SubprocessError as e:
            # Log subprocess errors for debugging
            print(f"Warning: Subprocess error in dependency scan: {e}")
        except json.JSONDecodeError as e:
            # Log JSON parsing errors for debugging
            print(f"Warning: Failed to parse dependency scan output: {e}")

        return SecurityScanResult(
            success=True, findings=findings, scan_type="secrets"
        )
