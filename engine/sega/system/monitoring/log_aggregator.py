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
SEGA MULTI-INFRASTRUCTURE LOG AGGREGATOR
==============================================================================
File: src/sega/monitoring/log_aggregator.py
Project: SEGA (Scalable Engineering & Growth Automation)
Copyright: 2022-2025 FLEET
License: Apache-2.0

SEGA MODULE: Monitoring/LogAggregation
COMPONENT: Cross-Infrastructure Log Collection Engine
PURPOSE: Aggregate logs from Kubernetes, Ansible nodes, and FPGA hardware
DEPENDENCIES: subprocess, json, dataclasses, datetime
USAGE: aggregator = LogAggregator(); logs = aggregator.get_recent_logs()

This aggregator provides unified log collection across heterogeneous infrastructure
with real-time streaming, filtering, and structured log entry management.
==============================================================================
"""

import subprocess
import json
import logging
from dataclasses import dataclass
from typing import List, Optional, Iterator
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class LogEntry:
    timestamp: datetime
    source: str
    level: str
    message: str
    metadata: dict


class LogAggregator:
    """Aggregate logs from Kubernetes, Ansible nodes, and hardware."""

    def __init__(self):
        self.sources = {
            "kubernetes": self._get_k8s_logs,
            "ansible": self._get_ansible_logs,
            "fpga": self._get_fpga_logs,
        }

    def get_recent_logs(
        self,
        target_filter: Optional[str] = None,
        service_filter: Optional[str] = None,
        limit: int = 100,
    ) -> List[LogEntry]:
        """Get recent logs from all sources."""
        all_logs = []

        for source_type, log_func in self.sources.items():
            try:
                logs = log_func(target_filter, service_filter, limit)
                all_logs.extend(logs)
            except (
                subprocess.SubprocessError,
                subprocess.TimeoutExpired,
            ) as e:
                # Add error log entry but continue
                error_log = LogEntry(
                    timestamp=datetime.now(),
                    source=f"{source_type}-error",
                    level="ERROR",
                    message=f"Subprocess error retrieving {source_type} logs: {str(e)}",
                    metadata={"error_type": "subprocess"},
                )
                all_logs.append(error_log)
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                # Add error log entry but continue
                error_log = LogEntry(
                    timestamp=datetime.now(),
                    source=f"{source_type}-error",
                    level="ERROR",
                    message=f"Data parsing error retrieving {source_type} logs: {str(e)}",
                    metadata={"error_type": "parsing"},
                )
                all_logs.append(error_log)
            except (FileNotFoundError, PermissionError) as e:
                # Add error log entry but continue
                error_log = LogEntry(
                    timestamp=datetime.now(),
                    source=f"{source_type}-error",
                    level="ERROR",
                    message=f"File system error retrieving {source_type} logs: {str(e)}",
                    metadata={"error_type": "filesystem"},
                )
                all_logs.append(error_log)
            except (KeyError, ValueError, OSError) as e:
                # Add error log entry but continue
                error_log = LogEntry(
                    timestamp=datetime.now(),
                    source=f"{source_type}-error",
                    level="ERROR",
                    message=f"Unexpected error retrieving {source_type} logs: {str(e)}",
                    metadata={"error_type": "unexpected"},
                )
                all_logs.append(error_log)

        # Sort by timestamp and limit
        all_logs.sort(key=lambda x: x.timestamp, reverse=True)
        return all_logs[:limit]

    def stream_logs(
        self,
        target_filter: Optional[str] = None,
        service_filter: Optional[str] = None,
    ) -> Iterator[LogEntry]:
        """Stream logs in real-time from all sources."""
        # For demonstration - in reality would use async streaming
        while True:
            recent_logs = self.get_recent_logs(
                target_filter, service_filter, 10
            )
            for log in recent_logs:
                yield log

    def _get_k8s_logs(
        self,
        target_filter: Optional[str],
        service_filter: Optional[str],
        limit: int,
    ) -> List[LogEntry]:
        """Get logs from Kubernetes deployments."""
        try:
            # Get pod logs from sega namespace
            cmd = [
                "kubectl",
                "logs",
                "--namespace",
                "sega-deployments",
                "--all-containers=true",
                "--timestamps=true",
                f"--tail={limit}",
            ]

            if service_filter:
                cmd.extend(["-l", f"app={service_filter}"])

            from ..utils.resource_manager import safe_subprocess

            result = safe_subprocess(cmd, timeout=30)

            if result.returncode != 0:
                return []

            logs = []
            for line in result.stdout.split("\n"):
                if line.strip():
                    # Parse kubectl log format: timestamp pod_name message
                    parts = line.split(" ", 2)
                    if len(parts) >= 3:
                        timestamp_str = parts[0]
                        pod_name = parts[1]
                        message = parts[2]

                        try:
                            timestamp = datetime.fromisoformat(
                                timestamp_str.replace("Z", "+00:00")
                            )
                        except (ValueError, TypeError) as e:
                            logger.warning(
                                f"Invalid timestamp format in Kubernetes log, using current time: {e}"
                            )
                            timestamp = datetime.now()

                        log_entry = LogEntry(
                            timestamp=timestamp,
                            source=f"k8s-{pod_name}",
                            level="INFO",
                            message=message,
                            metadata={
                                "pod": pod_name,
                                "namespace": "sega-deployments",
                            },
                        )
                        logs.append(log_entry)

            return logs

        except (subprocess.SubprocessError, subprocess.TimeoutExpired) as e:
            logger.error(f"Subprocess error retrieving Kubernetes logs: {e}")
            return []
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Data parsing error in Kubernetes logs: {e}")
            return []
        except (AttributeError, TypeError) as e:
            logger.error(f"Data structure error in Kubernetes logs: {e}")
            return []
        except (ConnectionError, TimeoutError, OSError) as e:
            logger.error(f"Connection error retrieving Kubernetes logs: {e}")
            return []
        except (
            subprocess.SubprocessError,
            ValueError,
            json.JSONDecodeError,
        ) as e:
            logger.error(f"Error processing Kubernetes logs: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error retrieving Kubernetes logs: {e}")
            logger.debug(
                f"Full exception details: {e.__class__.__name__}: {str(e)}"
            )
            return []

    def _get_ansible_logs(
        self,
        target_filter: Optional[str],
        service_filter: Optional[str],
        limit: int,
    ) -> List[LogEntry]:
        """Get logs from Ansible-managed nodes."""
        try:
            # Get systemd journal logs from managed hosts
            ansible_cmd = [
                "ansible",
                "all",
                "-i",
                "./_internal/tooling/_internal/tooling/infrastructure/ansible/host.ini",
                "-m",
                "shell",
                "-a",
                f"journalctl -u sega-* --lines {limit} --output json",
            ]

            if target_filter:
                ansible_cmd[1] = target_filter

            from ..utils.resource_manager import safe_subprocess

            result = safe_subprocess(ansible_cmd, timeout=60)

            if result.returncode != 0:
                return []

            logs = []
            for line in result.stdout.split("\n"):
                if "SUCCESS" in line and "{" in line:
                    # Extract JSON from ansible output
                    json_start = line.find("{")
                    if json_start != -1:
                        try:
                            log_data = json.loads(line[json_start:])

                            log_entry = LogEntry(
                                timestamp=datetime.fromtimestamp(
                                    int(
                                        log_data.get("__REALTIME_TIMESTAMP", 0)
                                    )
                                    / 1000000
                                ),
                                source=f"ansible-{log_data.get('_HOSTNAME', 'unknown')}",
                                level=log_data.get("PRIORITY", "INFO"),
                                message=log_data.get("MESSAGE", ""),
                                metadata={
                                    "unit": log_data.get("_SYSTEMD_UNIT", "")
                                },
                            )
                            logs.append(log_entry)
                        except (
                            json.JSONDecodeError,
                            KeyError,
                            ValueError,
                            TypeError,
                        ) as e:
                            logger.warning(
                                f"Skipping malformed Ansible log entry: {e}"
                            )
                            continue

            return logs

        except (subprocess.SubprocessError, subprocess.TimeoutExpired) as e:
            logger.error(f"Subprocess error retrieving Ansible logs: {e}")
            return []
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"JSON parsing error in Ansible logs: {e}")
            return []
        except (IndexError, AttributeError) as e:
            logger.error(f"Data structure error in Ansible logs: {e}")
            return []
        except (IOError, OSError, RuntimeError) as e:
            logger.error(f"I/O error retrieving Ansible logs: {e}")
            return []
        except (
            subprocess.SubprocessError,
            ValueError,
            json.JSONDecodeError,
        ) as e:
            logger.error(f"Error processing Ansible logs: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error retrieving Ansible logs: {e}")
            logger.debug(
                f"Full exception details: {e.__class__.__name__}: {str(e)}"
            )
            return []

    def _get_fpga_logs(
        self,
        target_filter: Optional[str],
        service_filter: Optional[str],
        limit: int,
    ) -> List[LogEntry]:
        """Get logs from FPGA devices."""
        try:
            # FPGA devices typically log through UART or custom protocols
            # Hardware-specific log retrieval requires device drivers/interfaces
            logs = []

            # Hardware-specific interface implementation framework
            # Check for available interfaces
            import os
            
            # 1. Check for UART/Serial communication
            uart_device = os.environ.get('FPGA_UART_DEVICE', '/dev/ttyUSB0')
            if os.path.exists(uart_device):
                try:
                    import serial
                    with serial.Serial(uart_device, 115200, timeout=1) as ser:
                        if ser.in_waiting:
                            uart_data = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
                            for line in uart_data.splitlines():
                                if line.strip():
                                    logs.append(LogEntry(
                                        timestamp=datetime.now(),
                                        source="fpga-uart",
                                        level="DEBUG",
                                        message=line.strip(),
                                        metadata={"interface": "uart", "device": uart_device}
                                    ))
                except ImportError:
                    pass  # pyserial not installed
                except Exception as e:
                    self.logger.debug(f"UART read failed: {e}")
            
            # 2. Check for telemetry data via shared memory or IPC
            telemetry_path = os.environ.get('FPGA_TELEMETRY_PATH', '/tmp/fpga_telemetry')
            if os.path.exists(telemetry_path):
                try:
                    with open(telemetry_path, 'r') as f:
                        telemetry_data = f.read()
                        if telemetry_data:
                            logs.append(LogEntry(
                                timestamp=datetime.now(),
                                source="fpga-telemetry",
                                level="INFO",
                                message="FPGA telemetry data available",
                                metadata={"data": telemetry_data[:500]}  # Limit size
                            ))
                except Exception as e:
                    self.logger.debug(f"Telemetry read failed: {e}")
            
            # 3. Hardware abstraction layer placeholder
            hal_driver = os.environ.get('FPGA_HAL_DRIVER')
            if hal_driver:
                # This would load vendor-specific drivers dynamically
                logs.append(LogEntry(
                    timestamp=datetime.now(),
                    source="fpga-hal",
                    level="INFO",
                    message=f"HAL driver configured: {hal_driver}",
                    metadata={"driver": hal_driver}
                ))
            
            # 4. Ring buffer for high-frequency data (using circular buffer concept)
            if not logs:
                # Fallback message if no hardware interfaces are available
                log_entry = LogEntry(
                    timestamp=datetime.now(),
                    source="fpga-system",
                    level="INFO",
                    message="FPGA hardware interfaces not configured - set FPGA_UART_DEVICE or FPGA_TELEMETRY_PATH",
                    metadata={
                        "type": "hardware_interface_info",
                        "interfaces_checked": ["uart", "telemetry", "hal"],
                    },
            )
            logs.append(log_entry)

            return logs

        except (OSError, IOError) as e:
            logger.error(
                f"Hardware communication error retrieving FPGA logs: {e}"
            )
            return []
        except (ValueError, TypeError) as e:
            logger.error(f"Data processing error in FPGA logs: {e}")
            return []
        except (IOError, OSError, RuntimeError) as e:
            logger.error(f"I/O error retrieving FPGA logs: {e}")
            return []
        except (
            subprocess.SubprocessError,
            ValueError,
            UnicodeDecodeError,
        ) as e:
            logger.error(f"Error processing FPGA logs: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error retrieving FPGA logs: {e}")
            logger.debug(
                f"Full exception details: {e.__class__.__name__}: {str(e)}"
            )
            return []
