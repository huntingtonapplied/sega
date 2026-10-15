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
SEGA INFRASTRUCTURE MODULE
=============================================================================
Provides unified infrastructure provisioning and management capabilities.
"""

from .vpn_manager import VPNManager, VPNConfig
from .engine_deployer import EngineDeployer
from .runner_manager import RunnerManager
from .network_orchestrator import NetworkOrchestrator
from .ec2_config import (
    EC2Instance,
    DistributionConfig,
    INSTANCE1,
    INSTANCE2,
    INSTANCE3,
    INSTANCE4,
    EC2_INSTANCES,
    ALL_INSTANCES,
    SSH_KEY_PATH,
    THRESHOLDS,
    get_instance,
    get_instance_by_project,
    get_ssh_key_path,
    get_ssh_options,
    build_ssh_command,
    get_distribution_config,
)

__all__ = [
    "VPNManager",
    "VPNConfig",
    "EngineDeployer",
    "RunnerManager",
    "NetworkOrchestrator",
    # EC2 Configuration
    "EC2Instance",
    "DistributionConfig",
    "INSTANCE1",
    "INSTANCE2",
    "INSTANCE3",
    "INSTANCE4",
    "EC2_INSTANCES",
    "ALL_INSTANCES",
    "SSH_KEY_PATH",
    "THRESHOLDS",
    "get_instance",
    "get_instance_by_project",
    "get_ssh_key_path",
    "get_ssh_options",
    "build_ssh_command",
    "get_distribution_config",
]
