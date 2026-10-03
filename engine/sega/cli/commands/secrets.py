#!/usr/bin/env python3
# Copyright 2025 SEGA
#
# SEGA Secrets Management Command
# Handles GitLab CI/CD variable integration for the FLEET ecosystem

import os
import json
import yaml
import click
import requests
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass
from ...utils.paths import get_fleet_root


@dataclass
class SecretConfig:
    """Configuration for secret management"""
    gitlab_url: str = "https://gitlab.com"
    project_id: str = ""
    gitlab_token: str = ""
    
    @classmethod
    def from_env(cls):
        """Load config from environment"""
        return cls(
            gitlab_url=os.getenv("GITLAB_URL", "https://gitlab.com"),
            project_id=os.getenv("CI_PROJECT_ID", ""),
            gitlab_token=os.getenv("GITLAB_TOKEN", "")
        )


class SecretsManager:
    """Manages secrets between GitLab and FLEET projects"""
    
    # Standard secret mappings
    STANDARD_SECRETS = {
        # Auth0
        "AUTH0_DOMAIN": "AUTH0_DOMAIN",
        "AUTH0_CLIENT_ID": "AUTH0_CLIENT_ID", 
        "AUTH0_CLIENT_SECRET": "AUTH0_CLIENT_SECRET",
        "AUTH0_AUDIENCE": "AUTH0_AUDIENCE",
        
        # Sentry
        "SENTRY_DSN": "SENTRY_DSN",
        "SENTRY_AUTH_TOKEN": "SENTRY_AUTH_TOKEN",
        "SENTRY_ORG": "SENTRY_ORG",
        "SENTRY_PROJECT": "SENTRY_PROJECT",
        "SENTRY_ENVIRONMENT": "SENTRY_ENVIRONMENT",
        
        # Mailgun
        "MAILGUN_API_KEY": "MAILGUN_API_KEY",
        "MAILGUN_DOMAIN": "MAILGUN_DOMAIN",
        "MAILGUN_WEBHOOK_KEY": "MAILGUN_WEBHOOK_SIGNING_KEY",
        "MAILGUN_FROM_EMAIL": "MAILGUN_FROM_EMAIL",
        "MAILGUN_FROM_NAME": "MAILGUN_FROM_NAME",
        
        # Database
        "DATABASE_PASSWORD": "DATABASE_PASSWORD",
        "POSTGRES_PASSWORD": "POSTGRES_PASSWORD",
        "REDIS_PASSWORD": "REDIS_PASSWORD",
        "TIMESCALE_PASSWORD": "TIMESCALE_PASSWORD",
        
        # AApplication
        "JWT_SECRET_KEY": "JWT_SECRET_KEY",
        "SECRET_KEY": "SECRET_KEY",
        "ENCRYPTION_KEY": "ENCRYPTION_KEY",

        # Telemetry Integration
        "TIFFANY_API_KEY": "TIFFANY_API_KEY",
    }
    
    def __init__(self, config: SecretConfig):
        self.config = config
        self.fleet_root = get_fleet_root()
        
    def pull_from_gitlab(self, environment: str = "production") -> Dict[str, str]:
        """Pull secrets from GitLab CI/CD variables"""
        secrets = {}
        
        # First try environment variables (when running in GitLab CI)
        for gitlab_key in self.STANDARD_SECRETS.keys():
            value = os.getenv(gitlab_key)
            if value:
                secrets[gitlab_key] = value
                
        # If not in CI, try GitLab API
        if not secrets and self.config.gitlab_token and self.config.project_id:
            headers = {"PRIVATE-TOKEN": self.config.gitlab_token}
            url = f"{self.config.gitlab_url}/api/v4/projects/{self.config.project_id}/variables"
            
            try:
                response = requests.get(url, headers=headers)
                if response.status_code == 200:
                    for var in response.json():
                        if var.get("environment_scope") in [environment, "*"]:
                            secrets[var["key"]] = var["value"]
            except Exception as e:
                click.echo(f"Error fetching from GitLab API: {e}", err=True)
                
        return secrets
    
    def apply_to_project(self, project: str, secrets: Dict[str, str], env: str = "production"):
        """Apply secrets to a project's .env file"""
        project_path = self.fleet_root / project
        
        if not project_path.exists():
            click.echo(f"Project {project} not found", err=True)
            return False
            
        # Determine env file name
        env_file = project_path / f".env.{env}" if env != "development" else project_path / ".env"
        
        # Start with .env.example if it exists
        example_file = project_path / ".env.example"
        if example_file.exists():
            content = example_file.read_text()
        else:
            content = ""
            
        # Append secrets
        content += "\n\n# === Secrets from GitLab ===\n"
        
        for gitlab_key, env_key in self.STANDARD_SECRETS.items():
            if gitlab_key in secrets:
                content += f"{env_key}={secrets[gitlab_key]}\n"
                
        # Add environment
        content += f"ENVIRONMENT={env}\n"
        
        # Write file
        env_file.write_text(content)
        click.echo(f" Applied secrets to {env_file}")
        return True
    
    def import_from_file(self, file_path: str, environment: str = "production"):
        """Import secrets from YAML file to GitLab"""
        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)
            
        if environment not in data:
            click.echo(f"Environment {environment} not found in file", err=True)
            return False
            
        secrets = data[environment]
        
        if not self.config.gitlab_token or not self.config.project_id:
            click.echo("GitLab token and project ID required for import", err=True)
            return False
            
        headers = {"PRIVATE-TOKEN": self.config.gitlab_token}
        base_url = f"{self.config.gitlab_url}/api/v4/projects/{self.config.project_id}/variables"
        
        for key, value in secrets.items():
            # Check if variable exists
            check_url = f"{base_url}/{key}"
            exists = requests.get(check_url, headers=headers).status_code == 200
            
            data = {
                "key": key,
                "value": value,
                "protected": True,
                "masked": self._can_mask(value),
                "environment_scope": environment
            }
            
            if exists:
                # Update existing
                response = requests.put(check_url, headers=headers, json=data)
            else:
                # Create new
                response = requests.post(base_url, headers=headers, json=data)
                
            if response.status_code in [200, 201]:
                click.echo(f" {'Updated' if exists else 'Created'} {key}")
            else:
                click.echo(f" Failed to set {key}: {response.text}", err=True)
                
        return True
    
    def _can_mask(self, value: str) -> bool:
        """Check if value can be masked in GitLab (alphanumeric + some chars, 8+ length)"""
        import re
        # GitLab masking requirements
        if len(value) < 8:
            return False
        # Must match GitLab's regex for maskable variables
        pattern = r'^[a-zA-Z0-9+/=\-_]+$'
        return bool(re.match(pattern, value))
    
    def validate(self, environment: str = "production") -> Dict[str, bool]:
        """Validate that all required secrets are present"""
        secrets = self.pull_from_gitlab(environment)
        results = {}
        
        # Check required secrets
        required = [
            "DATABASE_PASSWORD", "REDIS_PASSWORD", "JWT_SECRET_KEY"
        ]
        
        for key in self.STANDARD_SECRETS.keys():
            if key in required:
                results[key] = key in secrets and bool(secrets[key])
            else:
                results[key] = key in secrets
                
        return results
    
    def test_service(self, service: str, secrets: Optional[Dict[str, str]] = None) -> bool:
        """Test connection to external service with secrets"""
        if not secrets:
            secrets = self.pull_from_gitlab()
            
        if service == "auth0":
            domain = secrets.get("AUTH0_DOMAIN")
            if domain:
                try:
                    response = requests.get(f"https://{domain}/.well-known/jwks.json")
                    return response.status_code == 200
                except:
                    return False
                    
        elif service == "sentry":
            dsn = secrets.get("SENTRY_DSN")
            if dsn:
                # Parse DSN and test
                # Format: https://key@org.ingest.sentry.io/project
                return dsn.startswith("https://") and "@" in dsn
                
        elif service == "mailgun":
            api_key = secrets.get("MAILGUN_API_KEY")
            if api_key:
                try:
                    response = requests.get(
                        "https://api.mailgun.net/v3/domains",
                        auth=("api", api_key)
                    )
                    return response.status_code == 200
                except:
                    return False
                    
        return False


@click.group()
def secrets():
    """Manage secrets integration with GitLab CI/CD"""
    pass


@secrets.command()
@click.option('--project', '-p', help='Project name')
@click.option('--env', '-e', default='production', help='Environment')
@click.option('--key', '-k', help='Specific secret key to pull')
def pull(project, env, key):
    """Pull secrets from GitLab CI/CD variables"""
    config = SecretConfig.from_env()
    manager = SecretsManager(config)
    
    secrets = manager.pull_from_gitlab(env)
    
    if key:
        if key in secrets:
            click.echo(f"{key}={secrets[key]}")
        else:
            click.echo(f"Secret {key} not found", err=True)
    else:
        click.echo(f"Pulled {len(secrets)} secrets from GitLab")
        for k in sorted(secrets.keys()):
            masked = "***" if "SECRET" in k or "PASSWORD" in k or "KEY" in k else secrets[k][:20]
            click.echo(f"  {k}: {masked}...")


@secrets.command()
@click.option('--project', '-p', required=True, help='Project name or "all"')
@click.option('--env', '-e', default='production', help='Environment')
def apply(project, env):
    """Apply secrets to project .env files"""
    config = SecretConfig.from_env()
    manager = SecretsManager(config)
    
    secrets = manager.pull_from_gitlab(env)
    
    if not secrets:
        click.echo("No secrets found. Are you in GitLab CI or have GITLAB_TOKEN set?", err=True)
        return
    
    if project == "all":
        # Apply to all application projects (the curated `[fleet] app_projects`
        # config list; ships empty for new installs).
        from ...core.config import get_config
        projects = list(get_config().fleet.app_projects)
        for proj in projects:
            manager.apply_to_project(proj, secrets, env)
    else:
        manager.apply_to_project(project, secrets, env)


@secrets.command()
@click.option('--file', '-f', required=True, help='YAML file with secrets')
@click.option('--env', '-e', default='production', help='Environment')
def import_secrets(file, env):
    """Import secrets from YAML file to GitLab"""
    config = SecretConfig.from_env()
    
    if not config.gitlab_token:
        click.echo("GITLAB_TOKEN environment variable required", err=True)
        return
        
    if not config.project_id:
        click.echo("CI_PROJECT_ID environment variable required", err=True)
        return
        
    manager = SecretsManager(config)
    manager.import_from_file(file, env)


@secrets.command()
@click.option('--env', '-e', default='production', help='Environment')
def validate(env):
    """Validate that required secrets are configured"""
    config = SecretConfig.from_env()
    manager = SecretsManager(config)
    
    results = manager.validate(env)
    
    click.echo(f"Secret validation for {env}:")
    for key, present in results.items():
        status = "" if present else ""
        required = key in ["DATABASE_PASSWORD", "REDIS_PASSWORD", "JWT_SECRET_KEY"]
        req_marker = " (REQUIRED)" if required else ""
        click.echo(f"  {status} {key}{req_marker}")


@secrets.command()
@click.option('--service', '-s', help='Service to test (auth0, sentry, mailgun)')
@click.option('--all', 'test_all', is_flag=True, help='Test all services')
def test(service, test_all):
    """Test service connections with configured secrets"""
    config = SecretConfig.from_env()
    manager = SecretsManager(config)
    
    services = ["auth0", "sentry", "mailgun"] if test_all else [service]
    
    for svc in services:
        if svc:
            result = manager.test_service(svc)
            status = "" if result else ""
            click.echo(f"{status} {svc.upper()} connection")


@secrets.command()
@click.option('--project', '-p', required=True, help='Project to verify')
def verify(project):
    """Verify project has required secrets in .env file"""
    fleet_root = get_fleet_root()
    project_path = fleet_root / project
    
    env_files = [
        project_path / ".env.production",
        project_path / ".env"
    ]
    
    for env_file in env_files:
        if env_file.exists():
            content = env_file.read_text()
            click.echo(f"Checking {env_file}:")
            
            required = ["DATABASE_PASSWORD", "REDIS_PASSWORD", "JWT_SECRET_KEY"]
            for key in required:
                if key in content:
                    click.echo(f"   {key} present")
                else:
                    click.echo(f"   {key} missing")
            break
    else:
        click.echo(f"No .env file found for {project}", err=True)