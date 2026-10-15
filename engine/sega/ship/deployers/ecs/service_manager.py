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
File: src/sega/deployers/ecs/service_manager.py
Purpose: Provides utility functions for ECS service management and deployment
Dependencies: boto3, botocore
Authors: FLEET Development Team
Copyright: 2022-2026 Huntington Applied
License: Apache-2.0
Last Modified: 2025-07-25
"""

import boto3
import time
from typing import Dict, Any, List
from botocore.exceptions import ClientError


class ECServiceManager:
    """Manages ECS services."""

    def __init__(self, ecs_client: boto3.client, ec2_client: boto3.client):
        self.ecs = ecs_client
        self.ec2 = ec2_client

    def create_or_update_service(
        self, config: Dict[str, Any], task_def_arn: str, force: bool = False
    ) -> str:
        """Create or update ECS service."""
        service_name = config["service_name"]
        cluster_name = config["cluster_name"]

        # Check if service exists
        try:
            response = self.ecs.describe_services(
                cluster=cluster_name, services=[service_name]
            )

            if (
                response["services"]
                and response["services"][0]["status"] != "INACTIVE"
            ):
                # Update existing service
                return self._update_service(config, task_def_arn, force)
            else:
                # Create new service
                return self._create_service(config, task_def_arn)

        except ClientError:
            # Service doesn't exist, create it
            return self._create_service(config, task_def_arn)

    def _create_service(
        self, config: Dict[str, Any], task_def_arn: str
    ) -> str:
        """Create new ECS service."""
        service_def = {
            "cluster": config["cluster_name"],
            "serviceName": config["service_name"],
            "taskDefinition": task_def_arn,
            "desiredCount": config.get("desired_count", 1),
            "launchType": "FARGATE",
            "networkConfiguration": {
                "awsvpconfiguration": {
                    "subnets": self._get_subnet_ids(),
                    "securityGroups": [
                        self._get_security_group_id(config["cluster_name"])
                    ],
                    "assignPublicIp": "ENABLED",
                }
            },
            "deploymentConfiguration": {
                "maximumPercent": 200,
                "minimumHealthyPercent": 100,
            },
        }

        # Add load balancer if specified
        if config.get("load_balancer"):
            service_def["loadBalancers"] = [
                {
                    "targetGroupArn": config["load_balancer"][
                        "target_group_arn"
                    ],
                    "containerName": config.get(
                        "container_name", config["service_name"]
                    ),
                    "containerPort": config["port"],
                }
            ]

            service_def["healthCheckGracePeriodSeconds"] = 60

        response = self.ecs.create_service(**service_def)
        return response["service"]["serviceArn"]

    def _update_service(
        self, config: Dict[str, Any], task_def_arn: str, force: bool
    ) -> str:
        """Update existing ECS service."""
        update_params = {
            "cluster": config["cluster_name"],
            "service": config["service_name"],
            "taskDefinition": task_def_arn,
            "desiredCount": config.get("desired_count", 1),
            "forceNewDeployment": force,
        }

        response = self.ecs.update_service(**update_params)
        return response["service"]["serviceArn"]

    def wait_for_deployment(
        self, cluster_name: str, service_name: str, timeout: int = 600
    ) -> bool:
        """Wait for service deployment to complete."""
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                response = self.ecs.describe_services(
                    cluster=cluster_name, services=[service_name]
                )

                if not response["services"]:
                    return False

                service = response["services"][0]
                deployments = service.get("deployments", [])

                # Check if there's only one deployment (the new one)
                if (
                    len(deployments) == 1
                    and deployments[0]["status"] == "PRIMARY"
                ):
                    if (
                        deployments[0]["runningCount"]
                        == deployments[0]["desiredCount"]
                    ):
                        return True

                time.sleep(10)

            except ClientError:
                return False

        return False

    def get_service_info(
        self, cluster_name: str, service_name: str
    ) -> Dict[str, Any]:
        """Get service deployment information."""
        try:
            response = self.ecs.describe_services(
                cluster=cluster_name, services=[service_name]
            )

            if response["services"]:
                service = response["services"][0]
                return {
                    "status": service["status"],
                    "running_count": service["runningCount"],
                    "desired_count": service["desiredCount"],
                    "deployments": len(service.get("deployments", [])),
                    "task_definition": service.get("taskDefinition", ""),
                }

        except ClientError:
            pass

        return {}

    def stop_service(self, cluster_name: str, service_name: str):
        """Stop a service by setting desired count to 0."""
        try:
            self.ecs.update_service(
                cluster=cluster_name, service=service_name, desiredCount=0
            )
        except ClientError:
            pass

    def delete_service(self, cluster_name: str, service_name: str):
        """Delete a service."""
        try:
            # First stop the service
            self.stop_service(cluster_name, service_name)

            # Wait for tasks to stop
            time.sleep(30)

            # Delete the service
            self.ecs.delete_service(
                cluster=cluster_name, service=service_name, force=True
            )
        except ClientError:
            pass

    def _get_subnet_ids(self) -> List[str]:
        """Get subnet IDs for the default VPC."""
        response = self.ec2.describe_subnets(
            Filters=[{"Name": "default-for-az", "Values": ["true"]}]
        )
        return [subnet["SubnetId"] for subnet in response["Subnets"]]

    def _get_security_group_id(self, cluster_name: str) -> str:
        """Get or create security group for ECS cluster."""
        # Look for existing security group
        try:
            response = self.ec2.describe_security_groups(
                Filters=[
                    {
                        "Name": "group-name",
                        "Values": [f"ecs-{cluster_name}-sg"],
                    }
                ]
            )

            if response["SecurityGroups"]:
                return response["SecurityGroups"][0]["GroupId"]
        except ClientError:
            pass

        # Create new security group
        vpc_response = self.ec2.describe_vpcs(
            Filters=[{"Name": "isDefault", "Values": ["true"]}]
        )
        vpc_id = vpc_response["Vpcs"][0]["VpcId"]

        sg_response = self.ec2.create_security_group(
            GroupName=f"ecs-{cluster_name}-sg",
            Description=f"Security group for ECS cluster {cluster_name}",
            VpcId=vpc_id,
        )

        sg_id = sg_response["GroupId"]

        # Add ingress rules with restricted access
        ingress_rules = self._get_security_group_rules()
        self.ec2.authorize_security_group_ingress(
            GroupId=sg_id, IpPermissions=ingress_rules
        )

        return sg_id

    def _get_security_group_rules(self) -> List[Dict]:
        """Get security group ingress rules with least-privilege access."""
        import os

        # Default to more restrictive access - only common web traffic
        # These can be overridden by environment variables for specific deployments
        allowed_cidrs = (
            os.getenv("SEGA_ALLOWED_CIDRS", "").split(",")
            if os.getenv("SEGA_ALLOWED_CIDRS")
            else []
        )

        # If no specific CIDRs are configured, use more restrictive defaults
        if not allowed_cidrs:
            # Only allow common web traffic from Internet, but log this decision
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(
                "No SEGA_ALLOWED_CIDRS configured, using default web access (0.0.0.0/0 for HTTP/HTTPS). "
                "Consider setting SEGA_ALLOWED_CIDRS environment variable for more restrictive access."
            )
            allowed_cidrs = ["0.0.0.0/0"]

        # Clean up CIDR list
        allowed_cidrs = [
            cidr.strip() for cidr in allowed_cidrs if cidr.strip()
        ]

        # Validate CIDR blocks
        validated_cidrs = []
        for cidr in allowed_cidrs:
            try:
                import ipaddress

                ipaddress.IPv4Network(cidr, strict=False)
                validated_cidrs.append(cidr)
            except ipaddress.AddressValueError:
                import logging

                logger = logging.getLogger(__name__)
                logger.error(
                    f"Invalid CIDR block in SEGA_ALLOWED_CIDRS: {cidr}, skipping"
                )

        if not validated_cidrs:
            # Fallback to localhost only if all CIDRs are invalid
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(
                "No valid CIDRs found, falling back to localhost access only"
            )
            validated_cidrs = ["127.0.0.1/32"]

        # Build ingress rules for HTTP and HTTPS
        ingress_rules = []

        # HTTP (port 80) - only if explicitly needed
        if os.getenv("SEGA_ALLOW_HTTP", "false").lower() == "true":
            ingress_rules.append(
                {
                    "IpProtocol": "tcp",
                    "FromPort": 80,
                    "ToPort": 80,
                    "IpRanges": [
                        {
                            "CidrIp": cidr,
                            "Description": f"HTTP access from {cidr}",
                        }
                        for cidr in validated_cidrs
                    ],
                }
            )

        # HTTPS (port 443) - default enabled
        ingress_rules.append(
            {
                "IpProtocol": "tcp",
                "FromPort": 443,
                "ToPort": 443,
                "IpRanges": [
                    {
                        "CidrIp": cidr,
                        "Description": f"HTTPS access from {cidr}",
                    }
                    for cidr in validated_cidrs
                ],
            }
        )

        # Allow custom ports if specified
        custom_ports = os.getenv("SEGA_CUSTOM_PORTS", "")
        if custom_ports:
            for port_spec in custom_ports.split(","):
                port_spec = port_spec.strip()
                if "-" in port_spec:
                    # Port range
                    try:
                        from_port, to_port = map(int, port_spec.split("-"))
                        if 1 <= from_port <= to_port <= 65535:
                            ingress_rules.append(
                                {
                                    "IpProtocol": "tcp",
                                    "FromPort": from_port,
                                    "ToPort": to_port,
                                    "IpRanges": [
                                        {
                                            "CidrIp": cidr,
                                            "Description": f"Custom port range {port_spec} from {cidr}",
                                        }
                                        for cidr in validated_cidrs
                                    ],
                                }
                            )
                    except ValueError:
                        pass
                else:
                    # Single port
                    try:
                        port = int(port_spec)
                        if 1 <= port <= 65535:
                            ingress_rules.append(
                                {
                                    "IpProtocol": "tcp",
                                    "FromPort": port,
                                    "ToPort": port,
                                    "IpRanges": [
                                        {
                                            "CidrIp": cidr,
                                            "Description": f"Custom port {port} from {cidr}",
                                        }
                                        for cidr in validated_cidrs
                                    ],
                                }
                            )
                    except ValueError:
                        pass

        return ingress_rules
