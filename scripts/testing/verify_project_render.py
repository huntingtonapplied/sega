#!/usr/bin/env python3
"""
SEGA Project Render Verification Script
Verifies deployed projects are accessible via their configured endpoints
Uses laboratory_config.yaml for project type and endpoint expectations
"""

import sys
import yaml
import requests
from pathlib import Path
from typing import Dict, List, Tuple, Optional

def load_laboratory_config(project_path: Path) -> Optional[Dict]:
    """Load laboratory configuration for a project."""
    config_path = project_path / ".sega" / "laboratory_config.yaml"
    if not config_path.exists():
        return None

    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def get_project_config(lab_config: Dict, project_name: str) -> Optional[Dict]:
    """Get configuration for a specific project."""
    projects = lab_config.get('projects', {})
    return projects.get(project_name)

def get_project_type_endpoints(lab_config: Dict, project_type: str) -> List[Dict]:
    """Get expected endpoints for a project type."""
    project_types = lab_config.get('project_types', {})
    type_config = project_types.get(project_type, {})
    return type_config.get('endpoints', [])

def verify_endpoint(base_url: str, endpoint_config: Dict) -> Tuple[bool, int, str]:
    """
    Verify a single endpoint.

    Returns:
        (success, status_code, message)
    """
    path = endpoint_config.get('path', '')
    method = endpoint_config.get('method', 'GET')
    expected_statuses = endpoint_config.get('expected_status', [200])
    description = endpoint_config.get('description', path)

    url = f"{base_url}{path}"

    try:
        if method == 'GET':
            response = requests.get(url, timeout=5)
        elif method == 'POST':
            response = requests.post(url, timeout=5)
        else:
            return False, 0, f"Unsupported method: {method}"

        status_code = response.status_code

        if status_code in expected_statuses:
            return True, status_code, f"✅ {description}: {status_code}"
        else:
            return False, status_code, f"❌ {description}: {status_code} (expected {expected_statuses})"

    except requests.exceptions.ConnectionError:
        return False, 0, f"❌ {description}: Connection refused"
    except requests.exceptions.Timeout:
        return False, 0, f"❌ {description}: Timeout"
    except Exception as e:
        return False, 0, f"❌ {description}: {str(e)}"

def verify_project(fleet_root: Path, project_name: str) -> Dict:
    """
    Verify a project's deployment.

    Returns:
        Verification results dictionary
    """
    project_path = fleet_root / project_name

    # Load laboratory config
    lab_config = load_laboratory_config(fleet_root)
    if not lab_config:
        return {
            'project': project_name,
            'status': 'error',
            'message': 'Laboratory config not found'
        }

    # Get project configuration
    project_config = get_project_config(lab_config, project_name)
    if not project_config:
        return {
            'project': project_name,
            'status': 'error',
            'message': f'Project {project_name} not in laboratory config'
        }

    # Build base URL
    api_port = project_config.get('api')
    if not api_port:
        return {
            'project': project_name,
            'status': 'error',
            'message': 'No API port configured'
        }

    base_url = f"http://localhost:{api_port}"

    # Get project type and endpoints
    project_type = project_config.get('type', 'infrastructure')
    endpoints = get_project_type_endpoints(lab_config, project_type)

    if not endpoints:
        return {
            'project': project_name,
            'status': 'warning',
            'message': f'No endpoints defined for type: {project_type}'
        }

    # Verify each endpoint
    results = []
    success_count = 0

    for endpoint_config in endpoints:
        success, status_code, message = verify_endpoint(base_url, endpoint_config)
        results.append({
            'endpoint': endpoint_config.get('path'),
            'success': success,
            'status_code': status_code,
            'message': message
        })
        if success:
            success_count += 1

    # Determine overall status
    if success_count == len(endpoints):
        overall_status = 'success'
    elif success_count > 0:
        overall_status = 'partial'
    else:
        overall_status = 'failed'

    return {
        'project': project_name,
        'status': overall_status,
        'project_type': project_type,
        'api_port': api_port,
        'base_url': base_url,
        'total_endpoints': len(endpoints),
        'successful_endpoints': success_count,
        'results': results
    }

def main():
    """Main verification function."""
    if len(sys.argv) < 2:
        print("Usage: verify_project_render.py <project_name> [workspace_root]")
        sys.exit(1)

    project_name = sys.argv[1]
    fleet_root = Path(sys.argv[2]) if len(sys.argv) > 2 else Path.home() / "workspace"

    print(f"\n🔍 Verifying render for project: {project_name}")
    print(f"📁 Workspace Root: {fleet_root}")
    print("=" * 60)

    result = verify_project(fleet_root, project_name)

    print(f"\n📦 Project: {result['project']}")
    if result['status'] == 'error':
        print(f"❌ Error: {result['message']}")
        sys.exit(1)

    if result['status'] == 'warning':
        print(f"⚠️  Warning: {result['message']}")
        sys.exit(0)

    print(f"🏷️  Type: {result['project_type']}")
    print(f"🌐 Base URL: {result['base_url']}")
    print(f"📊 Status: {result['status'].upper()}")
    print(f"✅ Successful: {result['successful_endpoints']}/{result['total_endpoints']}")
    print("\n📋 Endpoint Results:")
    print("-" * 60)

    for endpoint_result in result['results']:
        print(endpoint_result['message'])

    print("=" * 60)

    if result['status'] == 'success':
        print("✅ All endpoints verified successfully")
        sys.exit(0)
    elif result['status'] == 'partial':
        print("⚠️  Some endpoints failed verification")
        sys.exit(1)
    else:
        print("❌ All endpoints failed verification")
        sys.exit(1)

if __name__ == "__main__":
    main()
