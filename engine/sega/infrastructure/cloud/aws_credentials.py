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
# SEGA MODULE - AWS CREDENTIAL MANAGER
# ===============================================================
# File: src/sega/core/_internal/tooling/_internal/tooling/infrastructure/aws_credentials.py
# Purpose: AWS credential management and validation
#
# Description: Manages AWS authentication methods including profiles and
# access keys. Validates credentials, retrieves AWS account information,
# and provides secure session management for AWS service interactions.
#
# Dependencies:
# - External: boto3, click, botocore
# - Internal: None (provides AWS authentication foundation)
#
# Used by: infrastructure_manager, setup_wizard, status_checker
#

"""AWS credential management and validation."""

import os
import re
import boto3
import click
from pathlib import Path
from typing import List, Optional, Tuple
from botocore.exceptions import (
    ClientError,
    NoCredentialsError,
    ProfileNotFound,
)


class AWSCredentialManager:
    """Manages AWS credentials and authentication."""

    def __init__(self):
        self.aws_session = None

    def _validate_profile_choice(self, value: int, max_choice: int) -> int:
        """Validate AWS profile choice."""
        if not (1 <= value <= max_choice):
            raise click.BadParameter(
                f"Choice must be between 1 and {max_choice}"
            )
        return value

    def _validate_access_key(self, value: str) -> str:
        """Validate AWS Access Key ID format."""
        if not value:
            raise click.BadParameter("AWS Access Key ID cannot be empty")

        # AWS Access Key ID format: AKIA followed by 16 alphanumeric characters
        if not re.match(r"^AKIA[A-Z0-9]{16}$", value.strip().upper()):
            raise click.BadParameter(
                "Invalid AWS Access Key ID format (should start with AKIA followed by 16 characters)"
            )

        return value.strip().upper()

    def _validate_secret_key(self, value: str) -> str:
        """Validate AWS Secret Access Key format."""
        if not value:
            raise click.BadParameter("AWS Secret Access Key cannot be empty")

        # AWS Secret Access Key: 40 characters, bBase64-like
        if len(value.strip()) != 40:
            raise click.BadParameter(
                "AWS Secret Access Key must be exactly 40 characters"
            )

        # Check for basic bBase64-like characters
        if not re.match(r"^[A-Za-z0-9+/]+$", value.strip()):
            raise click.BadParameter(
                "AWS Secret Access Key contains invalid characters"
            )

        return value.strip()

    def _validate_profile_name(self, value: str) -> str:
        """Validate AWS profile name."""
        if not value:
            raise click.BadParameter("Profile name cannot be empty")

        # AWS profile names: alphanumeric, hyphens, underscores
        if not re.match(r"^[a-zA-Z0-9_-]+$", value):
            raise click.BadParameter(
                "Profile name can only contain letters, numbers, hyphens, and underscores"
            )

        if len(value) > 64:
            raise click.BadParameter(
                "Profile name must be 64 characters or less"
            )

        return value.strip()

    def get_profiles(self) -> List[str]:
        """Get list of available AWS profiles."""
        profiles = []
        try:
            session = boto3.Session()
            profiles = session.available_profiles
        except Exception:
            pass
        return profiles

    def test_credentials(
        self,
        profile: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
    ) -> bool:
        """Test AWS credentials by attempting to call STS GetCallerIdentity."""
        try:
            if access_key and secret_key:
                session = boto3.Session(
                    aws_access_key_id=access_key,
                    aws_secret_access_key=secret_key,
                )
            elif profile:
                session = boto3.Session(profile_name=profile)
            else:
                session = boto3.Session()

            sts = session.client("sts")
            response = sts.get_caller_identity()

            click.echo(
                f" AWS credentials valid. Account: {response['Account']}"
            )
            self.aws_session = session
            return True

        except (NoCredentialsError, ClientError, ProfileNotFound) as e:
            click.echo(f" AWS credential test failed: {str(e)}")
            return False

    def configure_interactive(
        self,
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Interactive AWS credential configuration."""
        click.echo("\n AWS Credentials Configuration")
        click.echo("-" * 30)

        # Security recommendations
        click.echo("\n Security Recommendations:")
        click.echo("  1. Use IAM roles when running on EC2/ECS/Lambda")
        click.echo("  2. Use AWS SSO for long-term access")
        click.echo("  3. Use temporary credentials when possible")
        click.echo("  4. Avoid hardcoding credentials in code/config")

        # Check for IAM role/metadata first
        if self._check_iam_role_available():
            click.echo("\n IAM role detected - using instance credentials")
            if self.test_credentials():
                return None, None, None

        # Check for existing profiles
        profiles = self.get_profiles()

        if profiles:
            click.echo("\nAvailable AWS profiles:")
            for i, profile in enumerate(profiles):
                click.echo(f"  {i+1}. {profile}")
            click.echo(
                f"  {len(profiles)+1}. Enter credentials manually (NOT RECOMMENDED)"
            )

            choice = click.prompt(
                "Select option",
                type=int,
                default=1,
                value_proc=lambda x: self._validate_profile_choice(
                    x, len(profiles) + 1
                ),
            )

            if 1 <= choice <= len(profiles):
                profile = profiles[choice - 1]
                if self.test_credentials(profile=profile):
                    return profile, None, None

        # Manual credential entry with warnings
        click.echo(
            "\n  WARNING: Manual credential entry is not recommended for production"
        )
        click.echo(
            "   Consider using IAM roles, AWS SSO, or temporary credentials instead"
        )

        if not click.confirm("\nProceed with manual credential entry?"):
            click.echo("Credential configuration cancelled")
            return None, None, None

        click.echo("\nEnter AWS credentials manually:")
        access_key = click.prompt(
            "AWS Access Key ID",
            hide_input=True,
            value_proc=self._validate_access_key,
        )
        secret_key = click.prompt(
            "AWS Secret Access Key",
            hide_input=True,
            value_proc=self._validate_secret_key,
        )

        if self.test_credentials(access_key=access_key, secret_key=secret_key):
            # Save to profile if desired
            if click.confirm("\nSave these credentials to a profile?"):
                profile_name = click.prompt(
                    "Profile name",
                    default="sega",
                    value_proc=self._validate_profile_name,
                )
                self._save_to_profile(profile_name, access_key, secret_key)
                return profile_name, None, None

            return None, access_key, secret_key

        return None, None, None

    def _check_iam_role_available(self) -> bool:
        """Check if IAM role credentials are available (EC2 instance metadata)."""
        try:
            import requests

            # Try to access EC2 instance metadata service
            response = requests.get(
                "http://169.254.169.254/latest/meta-data/iam/security-credentials/",
                timeout=2,
            )
            return response.status_code == 200
        except Exception:
            # Not running on EC2 or metadata service unavailable
            return False

    def _save_to_profile(
        self, profile_name: str, access_key: str, secret_key: str
    ):
        """Save credentials to AWS profile using AWS CLI configuration."""
        import configparser

        aws_dir = Path.home() / ".aws"
        aws_dir.mkdir(
            mode=0o700, exist_ok=True
        )  # Secure directory permissions

        credentials_file = aws_dir / "credentials"

        # Use configparser for safe credential handling
        config = configparser.ConfigParser()

        # Read existing credentials if file exists
        if credentials_file.exists():
            config.read(credentials_file)

        # Add new profile section
        if not config.has_section(profile_name):
            config.add_section(profile_name)

        config.set(profile_name, "aws_access_key_id", access_key)
        config.set(profile_name, "aws_secret_access_key", secret_key)

        # Write with secure file permissions (600 - owner read/write only)
        with open(credentials_file, "w") as f:
            config.write(f)

        # Set secure file permissions
        os.chmod(credentials_file, 0o600)

        click.echo(
            f" Credentials saved to profile '{profile_name}' with secure permissions"
        )
        click.echo(
            "ℹ  Consider using IAM roles or AWS SSO for enhanced security"
        )
