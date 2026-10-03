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
SEGA Ship Deployers
=====================================================
File: engine/sega/ship/deployers/__init__.py
Purpose: Package initialization for deployment engine modules
Dependencies: None
Authors: FLEET Development Team
Copyright: 2022-2026 Huntington Applied
License: Apache-2.0
Last Modified: 2025-12-15

Supported Platforms:
- AWS ECS (containerized applications)
- Kubernetes/Helm (web apps, ML pipelines)
- Vercel (Next.js, static sites)
- Firebase (hosting, functions, Firestore)
- Supabase (database, auth, storage, edge functions)
- Render (web services, workers)
- AWS Amplify (frontend hosting, CI/CD)
- Ansible (firmware, native apps)
- FPGA (hardware)
- Mobile (iOS, Android)
- Desktop (Electron, Tauri)
"""

from .base_deployer import BaseDeployer, ContainerBaseDeployer, ServerlessBaseDeployer
from .deployment_router import DeploymentRouter
from .ecs_deployer import ECSDeployer
from .k8s_deployer import K8sDeployer
from .ansible_deployer import AnsibleDeployer
from .fpga_deployer import FPGADeployer
from .mobile_deployer import MobileDeployer
from .desktop_deployer import DesktopDeployer
from .multi_region_deployer import MultiRegionDeployer

# Platform deployers (Vercel, Firebase, Supabase, Render, Amplify)
from .vercel_deployer import VercelDeployer
from .firebase_deployer import FirebaseDeployer
from .supabase_deployer import SupabaseDeployer
from .render_deployer import RenderDeployer
from .amplify_deployer import AmplifyDeployer

__all__ = [
    # Base classes
    "BaseDeployer",
    "ContainerBaseDeployer",
    "ServerlessBaseDeployer",
    # Router
    "DeploymentRouter",
    # Infrastructure deployers
    "ECSDeployer",
    "K8sDeployer",
    "AnsibleDeployer",
    "FPGADeployer",
    "MobileDeployer",
    "DesktopDeployer",
    "MultiRegionDeployer",
    # Platform deployers
    "VercelDeployer",
    "FirebaseDeployer",
    "SupabaseDeployer",
    "RenderDeployer",
    "AmplifyDeployer",
]
