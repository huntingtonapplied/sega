#!/usr/bin/env python3
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

"""
SEGA SERVICES MODULE
==============================================
File: engine/sega/services/__init__.py
Purpose: Reporting module for SEGA platform metrics and telemetry

Description: Provides reporting capabilities for security scans,
deployment metrics, infrastructure status, and platform health
to external monitoring and dashboard systems.

Components:
- TelemetryReporter: TCP protobuf reporting to the telemetry backend
- Metric collection and aggregation utilities

Used by: All SEGA platform components for telemetry
"""

# The concrete TCP/protobuf telemetry backend adapter (``telemetry_reporter``)
# is an OPTIONAL, PRIVATE plug-in: public/standalone builds may exclude it.
# When it is absent, degrade gracefully to no-op stubs so that
# ``from sega.services import ...`` keeps working and callers never crash.
try:
    from .telemetry_reporter import (
        TelemetryReporter,
        get_telemetry_reporter,
        report_security_scan,
        report_deployment,
        report_platform_health,
    )
except ImportError:
    # No telemetry plug-in shipped in this build: provide inert stubs.
    class TelemetryReporter:  # type: ignore[no-redef]
        """No-op telemetry reporter (concrete plug-in excluded from this build)."""

        def __init__(self, *args, **kwargs):
            pass

        def start(self):
            pass

        def stop(self):
            pass

        def __getattr__(self, name):
            # Any send_*/report_* method call is a silent no-op.
            def _noop(*args, **kwargs):
                return None

            return _noop

    def get_telemetry_reporter():  # type: ignore[no-redef]
        """Return the global telemetry reporter (None when plug-in excluded)."""
        return None

    def report_security_scan(*args, **kwargs):  # type: ignore[no-redef]
        """No-op: telemetry plug-in excluded from this build."""
        return None

    def report_deployment(*args, **kwargs):  # type: ignore[no-redef]
        """No-op: telemetry plug-in excluded from this build."""
        return None

    def report_platform_health(*args, **kwargs):  # type: ignore[no-redef]
        """No-op: telemetry plug-in excluded from this build."""
        return None

__all__ = [
    "TelemetryReporter",
    "get_telemetry_reporter",
    "report_security_scan",
    "report_deployment",
    "report_platform_health",
]
