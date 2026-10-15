# Ansible Role Mapping and Repurposing Strategy

## Overview
SEGA already contains comprehensive Ansible roles for system installation and configuration. Rather than creating new installation scripts, we should repurpose and extend these existing roles to support the full portfolio.

## Existing Ansible Role Analysis

### Current Roles in `/infrastructure/ansible/roles/`

#### Platform/Cloud Service Roles
- **`install_legacy_cloud`** - Complete platform deployment with Docker Compose
- **`install_fleet_engine`** - Engine-only deployment with minimal services (formerly the sensor-net engine role)
- **`openvpn_server`** - VPN server installation and configuration
- **`openvpn_client`** - VPN client installation and connection
- **`openvpn_client_configs`** - VPN client certificate distribution

#### System Configuration Roles
- **`add_data_volume`** - Disk mounting and /data partition setup
- **`add_repositories`** - Package repository configuration
- **`add_ssh_keys`** - SSH key management and access
- **`configure_aws`** - AWS CLI and credentials setup
- **`install_packages`** - System package installation
- **`install_devops_packages`** - Development and operations tools

#### Specialized Roles
- **`configure_debug_node`** - Development environment setup
- **`configure_x310`** - Hardware-specific configuration
- **`install_gitlab_runner`** - CI/CD runner setup
- **`install_aws`** - AWS-specific tooling

## Role Repurposing Strategy

### 1. Rename and Generalize Existing Roles

#### From Legacy Project-Specific to Generic Roles
```bash
# Current role structure
install_legacy_cloud/ → install_platform/
 templates/docker-compose.yml.j2 (update image names)  
 files/nexus.toml → files/engine.toml
 tasks/main.yml (update references)

install_fleet_engine/ (formerly sensor-net engine role) → install_engine/
 files/docker-compose.yml (update image names)
 files/engine/ (generalize configuration)
 tasks/main.yml (make project-agnostic)
```

#### Generalize Image References
**Current**: `<account-id>.dkr.ecr.us-east-1.amazonaws.com/my-org/engine:<tag>`
**New**: Template-based with project detection
```yaml
# In docker-compose.yml.j2
engine:
  image: "{{ sega_registry }}/{{ project_name }}/{{ component }}:{{ version }}"
```

### 2. Create System Type Role Mapping

#### `server-jellyfish` Role Combination
```yaml
# Combines multiple existing roles
- role: install_packages
- role: add_data_volume  
- role: install_platform  # (repurposed install_legacy_cloud)
- role: openvpn_server
- role: configure_monitoring  # (new role based on existing patterns)
```

#### `engine-jellyfish` Role Combination  
```yaml
# Minimal engine deployment
- role: install_packages
  vars:
    package_profile: minimal
- role: add_data_volume
- role: install_engine  # (repurposed install_fleet_engine, formerly sensor-net)
- role: openvpn_client
```

#### `platform-jellyfish` Role Combination
```yaml
# Platform without VPN server
- role: install_packages
- role: install_platform  # (repurposed install_legacy_cloud)
- role: openvpn_client
```

### 3. Project-Agnostic Configuration Templates

#### Docker Compose Template Structure
```yaml
# templates/docker-compose.yml.j2
services:
  {% for service in sega_services %}
  {{ service.name }}:
    image: "{{ sega_registry }}/{{ sega_project }}/{{ service.image }}:{{ service.version }}"
    {% if service.type == 'engine' %}
    command: {{ service.command | default(['-c', '/' + service.name + '/etc/' + service.name + '.toml']) }}
    {% endif %}
    restart: always
    {% if service.network_mode %}
    network_mode: {{ service.network_mode }}
    {% endif %}
    volumes:
      - /var/run/dbus:/var/run/dbus
      - /var/run/avahi-daemon/socket:/var/run/avahi-daemon/socket
      {% for volume in service.volumes | default([]) %}
      - {{ volume }}
      {% endfor %}
    {% if service.ports %}
    ports:
      {% for port in service.ports %}
      - "{{ port }}"
      {% endfor %}
    {% endif %}
  {% endfor %}
```

#### Configuration File Templates
```toml
# templates/engine.toml.j2 (generalized from nexus.toml)
[engine]
name = "{{ sega_project }}_{{ ansible_hostname }}"
project = "{{ sega_project }}"

[network]
{% if sega_vpn_enabled %}
bind_address = "{{ ansible_tun0.ipv4.address | default('0.0.0.0') }}"
{% else %}
bind_address = "0.0.0.0"
{% endif %}

{% for section, config in sega_engine_config.items() %}
[{{ section }}]
{% for key, value in config.items() %}
{{ key }} = {{ value | to_json }}
{% endfor %}
{% endfor %}
```

### 4. SEGA Integration with Ansible Roles

#### Role Execution via SEGA
```python
# engine/sega/installation/ansible_installer.py
class AnsibleInstaller:
    def install_system_type(self, system_type: str, target_host: str):
        """Execute Ansible playbook for system type installation"""
        
        playbook_map = {
            'server-jellyfish': 'install_server_jellyfish.yml',
            'engine-jellyfish': 'install_engine_jellyfish.yml', 
            'platform-jellyfish': 'install_platform_jellyfish.yml',
            # ... other mappings
        }
        
        # Detect project requirements
        project_requirements = self.detect_project_requirements()
        
        # Execute Ansible playbook with detected variables
        self.run_ansible_playbook(
            playbook=playbook_map[system_type],
            host=target_host,
            extra_vars={
                'sega_project': project_requirements.primary_project,
                'sega_services': project_requirements.services,
                'sega_engine_config': project_requirements.engine_config,
                # ... other project-specific variables
            }
        )
```

#### Project Detection Integration
```python
# Extension of existing ProjectDetector
class ProjectDetector:
    def get_ansible_variables(self) -> Dict[str, Any]:
        """Generate Ansible variables based on detected project requirements"""
        
        variables = {
            'sega_project': self.detect_primary_project(),
            'sega_services': self.get_required_services(),
            'sega_registry': self.get_container_registry(),
            'sega_engine_config': self.get_engine_configuration(),
        }
        
        # Add technology-specific variables
        if self._has_rust_projects():
            variables['rust_enabled'] = True
            variables['rust_services'] = self.get_rust_services()
            
        if self._has_hardware_projects():
            variables['hardware_enabled'] = True
            variables['hardware_devices'] = self.get_hardware_devices()
            
        return variables
```

### 5. New System-Type Playbooks

#### Master System Type Playbooks
```yaml
# playbooks/install_server_jellyfish.yml
---
- hosts: all
  become: yes
  vars:
    system_type: server-jellyfish
    
  roles:
    - role: install_packages
      vars:
        package_profile: production
    - role: add_data_volume
    - role: install_platform
    - role: openvpn_server
    - role: configure_monitoring
    - role: configure_firewall
      vars:
        firewall_profile: server

# playbooks/install_engine_jellyfish.yml  
---
- hosts: all
  become: yes
  vars:
    system_type: engine-jellyfish
    
  roles:
    - role: install_packages
      vars:
        package_profile: minimal
    - role: add_data_volume
    - role: install_engine
    - role: openvpn_client
    - role: configure_monitoring
      vars:
        monitoring_profile: engine
```

### 6. Migration Path from Existing Roles

#### Phase 1: Create Generalized Variants
1. Copy existing roles with new names
2. Update templates to use generic variables
3. Generalize Docker image references
4. Create project-agnostic configuration templates

#### Phase 2: Test and Validate  
1. Test new roles against existing systems
2. Validate functional parity
3. Test project detection and variable generation
4. Validate VPN connectivity

#### Phase 3: Integration with SEGA
1. Integrate Ansible execution with SEGA install commands
2. Add project detection to variable generation
3. Create system type to playbook mapping
4. Test end-to-end installation flow

#### Phase 4: Deprecate Old Roles
1. Update all deployment references
2. Remove old role directories
3. Update documentation

## Implementation Benefits

### Reuse Existing Infrastructure
- **Proven Roles**: Leverage existing, tested Ansible roles
- **Docker Compose Patterns**: Reuse existing service orchestration patterns
- **VPN Integration**: Existing OpenVPN roles work immediately
- **System Configuration**: Disk mounting, SSH, AWS setup already implemented

### Project-Agnostic Approach
- **Template-Driven**: Single role supports multiple portfolio projects
- **Variable-Driven**: Project detection drives configuration generation
- **Scalable**: Easy to add new projects without new roles
- **Maintainable**: Single codebase for all system installations

### SEGA Integration Benefits
- **Unified Interface**: `sega install --target <type>` for all installations
- **Cross-Domain Deployment**: Leverages SEGA'as existing deployment capabilities
- **Project Detection**: Uses SEGA'as existing project analysis
- **Monitoring Integration**: SEGA can monitor Ansible-deployed services

This approach transforms the existing collection of installation scripts into a unified, SEGA-orchestrated system that reuses proven Ansible roles while adding project-agnostic capabilities and centralized management.