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
SEGA Docker Utilities
=====================
Docker-related utility functions
"""

import subprocess


def ensure_docker_running() -> bool:
    """Ensure Docker daemon is running."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode != 0:
            print("Docker is not running. Please start Docker first.")
            return False
            
        return True
        
    except subprocess.TimeoutExpired:
        print("Docker command timed out. Please check Docker installation.")
        return False
        
    except FileNotFoundError:
        print("Docker is not installed. Please install Docker first.")
        return False
        
    except Exception as e:
        print(f"Error checking Docker status: {e}")
        return False


def check_docker_compose() -> bool:
    """Check if docker-compose is available."""
    try:
        # Try docker compose (v2)
        result = subprocess.run(
            ["docker", "compose", "version"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            return True
            
        # Try docker-compose (v1)
        result = subprocess.run(
            ["docker-compose", "version"],
            capture_output=True,
            text=True
        )
        
        return result.returncode == 0
        
    except FileNotFoundError:
        return False
        
    except Exception:
        return False