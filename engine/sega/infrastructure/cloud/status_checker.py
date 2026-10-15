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
# SEGA MODULE - INFRASTRUCTURE STATUS CHECKER
# ===============================================================
# File: src/sega/core/_internal/tooling/_internal/tooling/infrastructure/status_checker.py
# Purpose: Infrastructure status checking and monitoring
#
# Description: Monitors AWS infrastructure health by checking status of
# VPCs, EKS clusters, ECS services, RDS databases, and other components.
# Provides comprehensive status reports for deployed infrastructure.
#
# Dependencies:
# - External: boto3, click, botocore
# - Internal: None (uses AWS SDK directly)
#
# Used by: infrastructure_manager, CLI status command, monitoring services
#

"""Infrastructure status checking and monitoring."""

import boto3
from typing import Dict, Optional
from botocore.exceptions import ClientError


class InfrastructureStatusChecker:
    """Checks status of provisioned infrastructure."""

    def __init__(self, aws_session: Optional[boto3.Session] = None):
        self.session = aws_session or boto3.Session()

    def check_status(self, config: Dict) -> Dict:
        """Check status of all infrastructure components."""
        status = {"overall": "healthy", "components": {}, "aApplications": {}}

        # Check each enabled component
        components = config.get("components", {})

        if components.get("networking", {}).get("enabled"):
            status["components"]["networking"] = self._check_networking_status(
                config
            )

        if components.get("compute", {}).get("enabled"):
            status["components"]["compute"] = self._check_compute_status(
                components["compute"], config
            )

        if components.get("storage", {}).get("enabled"):
            status["components"]["storage"] = self._check_storage_status(
                components["storage"]
            )

        if components.get("monitoring", {}).get("enabled"):
            status["components"][
                "monitoring"
            ] = self._check_monitoring_status()

        # Check aApplications
        for app in config.get("aApplications", []):
            status["aApplications"][
                app["name"]
            ] = self._check_aApplication_status(
                app, components.get("compute", {})
            )

        # Determine overall status
        all_statuses = []
        for comp_status in status["components"].values():
            all_statuses.append(comp_status.get("status", "unknown"))
        for app_status in status["aApplications"].values():
            all_statuses.append(app_status.get("status", "unknown"))

        if "error" in all_statuses or "unhealthy" in all_statuses:
            status["overall"] = "unhealthy"
        elif "warning" in all_statuses:
            status["overall"] = "warning"
        elif all(s == "healthy" for s in all_statuses):
            status["overall"] = "healthy"
        else:
            status["overall"] = "unknown"

        return status

    def _check_networking_status(self, config: Dict) -> Dict:
        """Check VPC and networking status."""
        try:
            ec2 = self.session.client("ec2")

            # Check for VPCs
            vpcs = ec2.describe_vpcs(
                Filters=[{"Name": "tag:ManagedBy", "Values": ["SEGA"]}]
            )

            if vpcs["Vpcs"]:
                vpc = vpcs["Vpcs"][0]
                return {
                    "status": "healthy",
                    "vpc_id": vpc["VpcId"],
                    "cidr": vpc["CidrBlock"],
                    "state": vpc["State"],
                }
            else:
                return {
                    "status": "not_found",
                    "message": "No SEGA-managed VPC found",
                }

        except ClientError as e:
            return {"status": "error", "message": str(e)}

    def _check_compute_status(
        self, compute_config: Dict, infra_config: Dict
    ) -> Dict:
        """Check compute resource status."""
        compute_type = compute_config.get("type", "ecs")

        if compute_type == "ecs":
            return self._check_ecs_status(infra_config)
        elif compute_type == "kubernetes":
            return self._check_eks_status(infra_config)
        elif compute_type == "ec2":
            return self._check_ec2_status(infra_config)

        return {
            "status": "unknown",
            "message": f"Unknown compute type: {compute_type}",
        }

    def _check_ecs_status(self, config: Dict) -> Dict:
        """Check ECS cluster status."""
        try:
            ecs = self.session.client("ecs")
            cluster_name = f"sega-{config.get('project_name', 'default')}"

            response = ecs.describe_clusters(clusters=[cluster_name])

            if response["clusters"]:
                cluster = response["clusters"][0]
                return {
                    "status": "healthy"
                    if cluster["status"] == "ACTIVE"
                    else "unhealthy",
                    "cluster_name": cluster["clusterName"],
                    "running_tasks": cluster["runningTasksCount"],
                    "active_services": cluster["activeServicesCount"],
                    "registered_instances": cluster[
                        "registeredContainerInstancesCount"
                    ],
                }
            else:
                return {
                    "status": "not_found",
                    "message": f"ECS cluster '{cluster_name}' not found",
                }

        except ClientError as e:
            return {"status": "error", "message": str(e)}

    def _check_eks_status(self, config: Dict) -> Dict:
        """Check EKS cluster status."""
        try:
            eks = self.session.client("eks")
            cluster_name = f"sega-{config.get('project_name', 'default')}"

            response = eks.describe_cluster(name=cluster_name)
            cluster = response["cluster"]

            return {
                "status": "healthy"
                if cluster["status"] == "ACTIVE"
                else "unhealthy",
                "cluster_name": cluster["name"],
                "version": cluster["version"],
                "endpoint": cluster["endpoint"],
                "cluster_status": cluster["status"],
            }

        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                return {
                    "status": "not_found",
                    "message": f"EKS cluster '{cluster_name}' not found",
                }
            return {"status": "error", "message": str(e)}

    def _check_ec2_status(self, config: Dict) -> Dict:
        """Check EC2 instance status."""
        try:
            ec2 = self.session.client("ec2")

            instances = ec2.describe_instances(
                Filters=[
                    {"Name": "tag:ManagedBy", "Values": ["SEGA"]},
                    {
                        "Name": "tag:Project",
                        "Values": [config.get("project_name", "default")],
                    },
                    {
                        "Name": "instance-state-name",
                        "Values": ["running", "pending"],
                    },
                ]
            )

            instance_count = sum(
                len(r["Instances"]) for r in instances["Reservations"]
            )

            return {
                "status": "healthy" if instance_count > 0 else "not_found",
                "instance_count": instance_count,
            }

        except ClientError as e:
            return {"status": "error", "message": str(e)}

    def _check_storage_status(self, storage_config: Dict) -> Dict:
        """Check S3 bucket status."""
        try:
            s3 = self.session.client("s3")

            bucket_statuses = {}
            for bucket_name in storage_config.get("s3_buckets", []):
                full_bucket_name = f"sega-{bucket_name}".replace(
                    "_", "-"
                ).lower()
                try:
                    s3.head_bucket(Bucket=full_bucket_name)
                    bucket_statuses[bucket_name] = "exists"
                except ClientError as e:
                    if e.response["Error"]["Code"] == "404":
                        bucket_statuses[bucket_name] = "not_found"
                    else:
                        bucket_statuses[bucket_name] = "error"

            all_exist = all(
                status == "exists" for status in bucket_statuses.values()
            )

            return {
                "status": "healthy" if all_exist else "warning",
                "buckets": bucket_statuses,
            }

        except ClientError as e:
            return {"status": "error", "message": str(e)}

    def _check_monitoring_status(self) -> Dict:
        """Check CloudWatch status."""
        try:
            logs = self.session.client("logs")

            # Check for SEGA log groups
            response = logs.describe_log_groups(logGroupNamePrefix="/sega/")

            log_group_count = len(response.get("logGroups", []))

            return {
                "status": "healthy"
                if log_group_count > 0
                else "not_configured",
                "log_groups": log_group_count,
            }

        except ClientError as e:
            return {"status": "error", "message": str(e)}

    def _check_aApplication_status(
        self, app: Dict, compute_config: Dict
    ) -> Dict:
        """Check aApplication deployment status."""
        compute_type = compute_config.get("type", "ecs")

        if compute_type == "ecs":
            return self._check_ecs_service_status(app["name"])
        elif compute_type == "kubernetes":
            return self._check_k8s_deployment_status(app["name"])

        return {
            "status": "unknown",
            "message": "Cannot check aApplication status",
        }

    def _check_ecs_service_status(self, service_name: str) -> Dict:
        """Check ECS service status."""
        try:
            import boto3

            ecs = boto3.client("ecs")

            # Get cluster name from service name (assuming service-cluster format)
            cluster_name = f"{service_name}-cluster"

            response = ecs.describe_services(
                cluster=cluster_name, services=[service_name]
            )

            if not response["services"]:
                return {
                    "status": "not_found",
                    "message": f"ECS service {service_name} not found",
                }

            service = response["services"][0]
            running_count = service["runningCount"]
            desired_count = service["desiredCount"]

            if running_count == desired_count and running_count > 0:
                status = "healthy"
            elif running_count > 0:
                status = "degraded"
            else:
                status = "unhealthy"

            return {
                "status": status,
                "running_count": running_count,
                "desired_count": desired_count,
                "message": f"ECS service {service_name}: {running_count}/{desired_count} running",
            }

        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to check ECS service status: {str(e)}",
            }

    def _check_k8s_deployment_status(self, deployment_name: str) -> Dict:
        """Check Kubernetes deployment status."""
        try:
            from kubernetes import client, config

            # Try to load kubeconfig
            try:
                config.load_kube_config()
            except Exception:
                config.load_incluster_config()

            aApps_v1 = client.AppsV1Api()

            # Get deployment status
            deployment = aApps_v1.read_namespaced_deployment(
                name=deployment_name, namespace="default"
            )

            ready_replicas = deployment.status.ready_replicas or 0
            desired_replicas = deployment.spec.replicas or 0

            if ready_replicas == desired_replicas and ready_replicas > 0:
                status = "healthy"
            elif ready_replicas > 0:
                status = "degraded"
            else:
                status = "unhealthy"

            return {
                "status": status,
                "ready_replicas": ready_replicas,
                "desired_replicas": desired_replicas,
                "message": f"K8s deployment {deployment_name}: {ready_replicas}/{desired_replicas} ready",
            }

        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to check Kubernetes deployment status: {str(e)}",
            }
