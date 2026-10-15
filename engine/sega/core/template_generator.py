#!/usr/bin/env python
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

# ===============================================================
# SEGA MODULE - Infrastructure Template Generator
# ===============================================================
# File: src/sega/core/template_generator.py
# Purpose: Generates infrastructure templates based on project types
#
# Description: Provides template generation capabilities for different
# project types including web aApps, ML pipelines, firmware, and FPGA projects.
# Creates standardized infrastructure configurations and deployment scripts.
#
# Dependencies:
# - External: pathlib, typing
# - Internal: None
#
# Used by: Project initialization, infrastructure setup commands
#

from pathlib import Path
from typing import Dict


class TemplateGenerator:
    """Generates infrastructure templates based on project type."""

    def __init__(self, project_type: str):
        self.project_type = project_type
        self.templates = {
            "web_app": self._generate_web_templates,
            "ml_pipeline": self._generate_ml_templates,
            "firmware_edge": self._generate_firmware_templates,
            "native_app": self._generate_native_templates,
            "hdl_fpga": self._generate_hdl_templates,
        }

    def generate_all(
        self, project_name: str = "sega-app", domain: str = "yourdomain.com"
    ) -> Dict[str, str]:
        """Generate all infrastructure templates."""
        generator = self.templates.get(
            self.project_type, self._generate_generic_templates
        )
        return generator(project_name, domain)

    def _generate_web_templates(
        self, project_name: str, domain: str = "yourdomain.com"
    ) -> Dict[str, str]:
        """Generate templates for web aApplications."""
        templates = {}

        # Dockerfile
        templates[
            "Dockerfile"
        ] = """FROM node:18-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --only=production

# Copy source code
COPY . .

# Build aApplication
RUN npm run build

# Expose port
EXPOSE 3000

# Start aApplication
CMD ["npm", "start"]
"""

        # Helm Chart.yaml
        templates[
            "_internal/tooling/_internal/tooling/infrastructure/helm/sega-app/Chart.yaml"
        ] = f"""apiVersion: v2
name: {project_name}
description: SEGA Web AApplication
type: aApplication
version: 0.1.0
appVersion: "latest"
"""

        # Helm values.yaml
        templates[
            "_internal/tooling/_internal/tooling/infrastructure/helm/sega-app/values.yaml"
        ] = f"""replicaCount: 2

image:
  repository: {project_name}
  tag: latest
  pullPolicy: IfNotPresent

service:
  type: ClusterIP
  port: 80
  targetPort: 3000

ingress:
  enabled: true
  className: "nginx"
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/force-ssl-redirect: "true"
    nginx.ingress.kubernetes.io/server-snippet: |
      add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
      add_header X-Frame-Options "SAMEORIGIN" always;
      add_header X-Content-Type-Options "nosniff" always;
      add_header X-XSS-Protection "1; mode=block" always;
      add_header Referrer-Policy "strict-origin-when-cross-origin" always;
  hosts:
    - host: {project_name}.{domain}
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: {project_name}-tls
      hosts:
        - {project_name}.{domain}

resources:
  limits:
    cpu: 500m
    memory: 512Mi
  requests:
    cpu: 250m
    memory: 256Mi

autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 10
  targetCPUUtilizationPercentage: 80
"""

        # Kubernetes deployment
        templates[
            "_internal/tooling/_internal/tooling/infrastructure/helm/sega-app/templates/deployment.yaml"
        ] = """apiVersion: aApps/v1
kind: Deployment
metadata:
  name: {{ include "sega-app.fullname" . }}
  labels:
    {{- include "sega-app.labels" . | nindent 4 }}
spec:
  {{- if not .Values.autoscaling.enabled }}
  replicas: {{ .Values.replicaCount }}
  {{- end }}
  selector:
    matchLabels:
      {{- include "sega-app.selectorLabels" . | nindent 6 }}
  template:
    metadata:
      labels:
        {{- include "sega-app.selectorLabels" . | nindent 8 }}
    spec:
      containers:
        - name: {{ .Chart.Name }}
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
          imagePullPolicy: {{ .Values.image.pullPolicy }}
          ports:
            - name: http
              containerPort: {{ .Values.service.targetPort }}
              protocol: TCP
          livenessProbe:
            httpGet:
              path: /health
              port: http
            initialDelaySeconds: 30
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: /ready
              port: http
            initialDelaySeconds: 5
            periodSeconds: 5
          resources:
            {{- toYaml .Values.resources | nindent 12 }}
"""

        return templates

    def _generate_ml_templates(
        self, project_name: str, domain: str = "yourdomain.com"
    ) -> Dict[str, str]:
        """Generate templates for ML pipelines."""
        templates = {}

        # GPU-enabled Dockerfile
        templates[
            "Dockerfile"
        ] = """FROM pytorch/pytorch:latest

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    git \\
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Set environment variables
ENV PYTHONPATH=/app

# Expose port for model serving
EXPOSE 8000

# Start model server
CMD ["python", "serve.py"]
"""

        # Helm values for ML workloads
        templates[
            "_internal/tooling/_internal/tooling/infrastructure/helm/sega-app/values.yaml"
        ] = f"""replicaCount: 1

image:
  repository: {project_name}
  tag: latest
  pullPolicy: IfNotPresent

service:
  type: ClusterIP
  port: 80
  targetPort: 8000

resources:
  limits:
    cpu: 4
    memory: 8Gi
    nvidia.com/gpu: 1
  requests:
    cpu: 2
    memory: 4Gi
    nvidia.com/gpu: 1

nodeSelector:
  accelerator: nvidia-tesla-k80

tolerations:
  - key: nvidia.com/gpu
    operator: Exists
    effect: NoSchedule
"""

        return templates

    def _generate_firmware_templates(
        self, project_name: str, domain: str = "yourdomain.com"
    ) -> Dict[str, str]:
        """Generate templates for firmware projects."""
        templates = {}

        # CMakeLists.txt
        templates[
            "CMakeLists.txt"
        ] = f"""cmake_minimum_required(VERSION 3.10)

project({project_name} C CXX)

set(CMAKE_C_STANDARD 99)
set(CMAKE_CXX_STANDARD 17)

# Set output directories
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${{CMAKE_BINARY_DIR}}/bin)

# Include directories
include_directories(include)

# Source files
file(GLOB_RECURSE SOURCES "src/*.c" "src/*.cpp")
file(GLOB_RECURSE HEADERS "include/*.h" "include/*.hpp")

# Create executable
add_executable(${{PROJECT_NAME}} ${{SOURCES}} ${{HEADERS}})

# Compiler flags
target_compile_options(${{PROJECT_NAME}} PRIVATE
    -Wall -Wextra -Werror
    $<$<CONFIG:Debug>:-g -O0>
    $<$<CONFIG:ReleBase>:-O3 -DNDEBUG>
)

# Link libraries (add as needed)
# target_link_libraries(${{PROJECT_NAME}} pthread)
"""

        # Ansible deployment playbook
        templates[
            "_internal/tooling/_internal/tooling/infrastructure/ansible/deploy-firmware.yml"
        ] = f"""---
- name: Deploy {project_name} firmware
  hosts: firmware_targets
  become: yes
  
  vars:
    firmware_binary: "{project_name}.elf"
    backup_location: "/opt/firmware/backup"
    
  tasks:
    - name: Create backup directory
      file:
        path: "{{{{ backup_location }}}}"
        state: directory
        mode: '0755'
    
    - name: Backup current firmware
      copy:
        src: "/opt/firmware/current.elf"
        dest: "{{{{ backup_location }}}}/{{{{ ansible_date_time.epoch }}}}.elf"
        remote_src: yes
      ignore_errors: yes
    
    - name: Copy new firmware
      copy:
        src: "build/{{{{ firmware_binary }}}}"
        dest: "/opt/firmware/{{{{ firmware_binary }}}}"
        mode: '0755'
    
    - name: Flash firmware to device
      command: |
        openocd -f interface/stlink.cfg -f target/stm32f4x.cfg \\
        -c "program /opt/firmware/{{{{ firmware_binary }}}} verify reset exit"
      register: flash_result
    
    - name: Verify firmware flash
      debug:
        msg: "Firmware flashed successfully"
      when: flash_result.rc == 0
    
    - name: Create current firmware symlink
      file:
        src: "/opt/firmware/{{{{ firmware_binary }}}}"
        dest: "/opt/firmware/current.elf"
        state: link
        force: yes
"""

        return templates

    def _generate_native_templates(
        self, project_name: str, domain: str = "yourdomain.com"
    ) -> Dict[str, str]:
        """Generate templates for native aApplications."""
        templates = {}

        # Dockerfile for native aApps
        templates[
            "Dockerfile"
        ] = f"""FROM rust:1.70 as builder

WORKDIR /usr/src/{project_name}

# Copy manifest files
COPY Cargo.toml Cargo.lock ./

# Copy source code
COPY src ./src

# Build aApplication
RUN cargo build --releBase

# Runtime image
FROM debian:bookworm-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \\
    ca-certificates \\
    && rm -rf /var/lib/apt/lists/*

# Copy binary from builder stage
COPY --from=builder /usr/src/{project_name}/target/releBase/{project_name} /usr/local/bin/{project_name}

# Create non-root user
RUN useradd -r -s /bin/false {project_name}
USER {project_name}

# Expose port
EXPOSE 8080

# Start aApplication
CMD ["{project_name}"]
"""

        # Systemd service file
        templates[
            "_internal/tooling/_internal/tooling/infrastructure/ansible/files/sega-app.service"
        ] = f"""[Unit]
Description={project_name} Service
After=network.target

[Service]
Type=simple
User=sega
Group=sega
WorkingDirectory=/opt/sega
ExecStart=/opt/sega/bin/{project_name}
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/sega/data

[Install]
WantedBy=multi-user.target
"""

        return templates

    def _generate_hdl_templates(
        self, project_name: str, domain: str = "yourdomain.com"
    ) -> Dict[str, str]:
        """Generate templates for HDL/FPGA projects."""
        templates = {}

        # Makefile for HDL synthesis
        templates[
            "Makefile"
        ] = f"""PROJECT = {project_name}
TOP_MODULE = top
SOURCES = src/$(TOP_MODULE).v
CONSTRAINTS = constraints/$(PROJECT).xdc

# FPGA device (adjust as needed)
PART = xc7a35tcpg236-1

# Synthesis and implementation
$(PROJECT).bit: $(SOURCES) $(CONSTRAINTS)
\techo "Starting synthesis for $(PROJECT)"
\tvivado -mode batch -source scripts/build.tcl \\
\t\t-tclargs $(PROJECT) $(TOP_MODULE) $(PART)

# Program FPGA
program: $(PROJECT).bit
\topenFPGALoader -b arty $(PROJECT).bit

# Clean build artifacts
clean:
\trm -rf work *.bit *.jou *.log *.str
\trm -rf .Xil vivado*

# Simulation
sim: $(SOURCES)
\tiverilog -o sim $(SOURCES) testbench/tb_$(TOP_MODULE).v
\tvvp sim
\tgtkwave sim.vcd &

.PHONY: program clean sim
"""

        return templates

    def _generate_generic_templates(
        self, project_name: str, domain: str = "yourdomain.com"
    ) -> Dict[str, str]:
        """Generate generic templates for unknown project types."""
        templates = {}

        templates[
            "Dockerfile"
        ] = """FROM ubuntu:22.04

WORKDIR /app

# Install basic dependencies
RUN apt-get update && apt-get install -y \\
    build-essential \\
    && rm -rf /var/lib/apt/lists/*

# Copy aApplication
COPY . .

# Build placeholder
RUN echo "Configure your build process here"

# Start placeholder
CMD ["echo", "Configure your start command here"]
"""

        return templates

    def write_templates(self, templates: Dict[str, str], base_path: str = "."):
        """Write templates to filesystem."""
        base = Path(base_path)

        for file_path, content in templates.items():
            full_path = base / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)

            # Don't overwrite existing files
            if full_path.exists():
                print(f"Skipping existing file: {file_path}")
                continue

            full_path.write_text(content)
            print(f"Created: {file_path}")
