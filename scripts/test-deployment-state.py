#!/usr/bin/env python3
"""
Test deployment state scanner directly
This tests the scanner modules without requiring full SEGA CLI installation
"""

import sys
from pathlib import Path

# Add SEGA to path
sega_root = Path(__file__).parent.parent
sys.path.insert(0, str(sega_root / "engine"))

from sega.services.deployment_state import scan_instance_state, load_deployment_config
from sega.services.conflict_detector import detect_conflicts, get_conflicts_by_severity, get_conflicts_by_project


def print_deployment_overview(instance_id: str):
    """Print deployment overview for an instance"""

    print(f"\n{'=' * 80}")
    print(f"DEPLOYMENT STATE OVERVIEW - Instance {instance_id}")
    print(f"{'=' * 80}\n")

    # Scan instance
    print(f"📡 Scanning instance {instance_id}...")
    try:
        state = scan_instance_state(instance_id)
    except Exception as e:
        print(f"❌ Error scanning instance: {e}")
        return

    # Load expected config
    expected_config = load_deployment_config()

    # Detect conflicts
    conflicts = detect_conflicts(state, expected_config)

    print(f"✅ Scan complete - {state.timestamp}\n")
    print(f"Instance: {state.instance_name} ({state.ip})")
    print(f"Services found: {len(state.services)}")
    print(f"Port bindings: {len(state.port_bindings)}")
    print(f"\n{'-' * 80}\n")

    # Group services by project and deployment mode
    services_by_project = {}
    for service in state.services:
        if service.project not in services_by_project:
            services_by_project[service.project] = []
        services_by_project[service.project].append(service)

    # Classify by deployment mode
    docker_isolated = []
    hybrid = []
    native_dev = []
    shared_landing = []
    static_nginx = []
    unknown = []

    for project, services in services_by_project.items():
        methods = {s.method for s in services if s.status == "running"}
        service_types = {s.service_type for s in services if s.status == "running"}

        # Classification logic
        if methods == {"docker"}:
            # All Docker
            if "database" in service_types:
                docker_isolated.append((project, services))
            else:
                shared_landing.append((project, services))
        elif "native" in methods and "systemd" in methods:
            native_dev.append((project, services))
        elif methods == {"docker", "systemd"}:
            hybrid.append((project, services))
        elif methods == {"nginx"}:
            static_nginx.append((project, services))
        else:
            unknown.append((project, services))

    # Print deployment mode summary
    print("📊 DEPLOYMENT MODE SUMMARY\n")

    if docker_isolated:
        print(f"🐳 DOCKER ISOLATED ({len(docker_isolated)} projects):")
        for project, services in docker_isolated:
            running = len([s for s in services if s.status == "running"])
            total = len(services)
            print(f"  ✓ {project}: {running}/{total} services running")
        print()

    if hybrid:
        print(f"🔄 HYBRID (Docker + Systemd) ({len(hybrid)} projects):")
        for project, services in hybrid:
            docker_svcs = [s for s in services if s.method == "docker" and s.status == "running"]
            systemd_svcs = [s for s in services if s.method == "systemd" and s.status == "running"]
            print(f"  ✓ {project}: {len(docker_svcs)} Docker + {len(systemd_svcs)} systemd")
        print()

    if native_dev:
        print(f"💻 NATIVE DEV ({len(native_dev)} projects):")
        for project, services in native_dev:
            native_svcs = [s for s in services if s.method == "native" and s.status == "running"]
            systemd_svcs = [s for s in services if s.method == "systemd" and s.status == "running"]
            print(f"  ✓ {project}: {len(native_svcs)} native + {len(systemd_svcs)} systemd")
        print()

    if shared_landing:
        print(f"🌐 SHARED LANDING DOCKER ({len(shared_landing)} projects):")
        for project, services in shared_landing:
            running = len([s for s in services if s.status == "running"])
            print(f"  ✓ {project}: {running} services")
        print()

    if static_nginx:
        print(f"📄 STATIC NGINX ({len(static_nginx)} projects):")
        for project, services in static_nginx:
            print(f"  ✓ {project}: nginx serving")
        print()

    # Print conflicts
    if conflicts:
        print(f"\n⚠️  CONFLICTS DETECTED ({len(conflicts)})\n")

        conflicts_by_severity = get_conflicts_by_severity(conflicts)

        if conflicts_by_severity.get("ERROR"):
            print(f"❌ ERRORS ({len(conflicts_by_severity['ERROR'])}):")
            for conflict in conflicts_by_severity["ERROR"]:
                print(f"  • {conflict.project}: {conflict.description}")
                if conflict.fix_description:
                    print(f"    Fix: {conflict.fix_description}")
            print()

        if conflicts_by_severity.get("WARNING"):
            print(f"⚠️  WARNINGS ({len(conflicts_by_severity['WARNING'])}):")
            for conflict in conflicts_by_severity["WARNING"]:
                print(f"  • {conflict.project}: {conflict.description}")
            print()

    # Print summary
    print(f"{'-' * 80}")
    print(f"SUMMARY:")
    print(f"  Docker Isolated:     {len(docker_isolated)}")
    print(f"  Hybrid:              {len(hybrid)}")
    print(f"  Native Dev:          {len(native_dev)}")
    print(f"  Shared Landing:      {len(shared_landing)}")
    print(f"  Static Nginx:        {len(static_nginx)}")
    print(f"  Total Projects:      {len(services_by_project)}")
    print(f"  Total Services:      {len(state.services)}")
    print(f"  Running Services:    {len([s for s in state.services if s.status == 'running'])}")
    print(f"  Conflicts:           {len(conflicts)}")
    print(f"{'=' * 80}\n")


if __name__ == "__main__":
    instance_id = sys.argv[1] if len(sys.argv) > 1 else "1"
    print_deployment_overview(instance_id)
