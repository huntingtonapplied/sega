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
SEGA: Enterprise Deployment Framework
=====================================================
File: examples/test-integration/conftest.py
Purpose: Provides pytest configuration and fixtures for example integration testing
Dependencies: pytest, tempfile
Authors: FLEET Development Team
Copyright: 2022-2025 FLEET. All rights reserved.
License: Apache-2.0
Last Modified: 2025-07-25
"""

import pytest
import tempfile
import shutil
from pathlib import Path
import os
import sys

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

@pytest.fixture(scope="session")
def examples_dir():
    """Return the examples directory path"""
    return Path(__file__).parent.parent

@pytest.fixture(scope="function")
def temp_dir():
    """Create a temporary directory for tests"""
    temp_path = tempfile.mkdtemp(prefix="sega_test_")
    yield Path(temp_path)
    shutil.rmtree(temp_path)

@pytest.fixture(scope="session")
def sample_sega_config():
    """Return a sample SEGA configuration"""
    return {
        "version": "2.1",
        "project": {
            "name": "test-project",
            "type": "web_app",
            "domain": "test",
            "team": "test-team",
            "description": "Test project"
        },
        "build": {
            "strategy": "containerized",
            "commands": {
                "development": "npm run dev",
                "staging": "npm run build",
                "production": "npm run build"
            },
            "docker": {
                "dockerfile": "Dockerfile",
                "context": "."
            }
        },
        "deployment": {
            "targets": {
                "development": {
                    "type": "local",
                    "auto_deploy": True
                }
            },
            "infrastructure": {
                "compute": {
                    "cpu": 256,
                    "memory": 512
                },
                "networking": {
                    "port": 3000,
                    "health_check_path": "/health"
                }
            }
        },
        "testing": {
            "types": ["unit", "integration"],
            "commands": {
                "unit": "npm test",
                "integration": "npm run test:integration"
            }
        },
        "security": {
            "vulnerability_scanning": {
                "enabled": True,
                "scanners": ["dependency", "static"]
            }
        },
        "monitoring": {
            "metrics": {
                "enabled": True,
                "collector": "prometheus"
            },
            "logging": {
                "level": "info",
                "format": "json"
            }
        }
    }

@pytest.fixture(scope="function")
def mock_environment(monkeypatch):
    """Set up mock environment variables"""
    test_env = {
        "DEPLOYMENT_ENV": "test",
        "DATABASE_URL": "postgresql://test:test@localhost:5432/test",
        "REDIS_URL": "redis://localhost:6379",
        "JWT_SECRET": "test-secret-key",
        "AWS_REGION": "us-east-1"
    }
    
    for key, value in test_env.items():
        monkeypatch.setenv(key, value)
    
    return test_env