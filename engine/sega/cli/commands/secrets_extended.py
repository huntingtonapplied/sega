#!/usr/bin/env python3
"""
Extended Secrets Management for FLEET Ecosystem
Handles social platform API keys and other sensitive credentials
with password-protected storage
"""

import os
import json
import yaml
import click
import hashlib
import base64
from pathlib import Path
from typing import Dict, List, Optional, Any
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
import getpass
from ...utils.paths import get_fleet_root


def _config_key_groups() -> Dict[str, str]:
    """Operator-curated secret-key groups from `[secrets.key_groups]` config."""
    from ...core.config import get_config
    return dict(get_config().secrets.key_groups)


def _config_project_required() -> Dict[str, List[str]]:
    """Per-project required keys from `[secrets.project_required]` config."""
    from ...core.config import get_config
    return {
        project: list(keys)
        for project, keys in get_config().secrets.project_required.items()
    }


class SocialSecretsManager:
    """Manages social platform and sensitive API keys with encryption"""
    
    # Social platform secret mappings
    SOCIAL_SECRETS = {
        # Twitter/X
        "TWITTER_API_KEY": "twitter",
        "TWITTER_API_SECRET": "twitter",
        "TWITTER_BEARER_TOKEN": "twitter",
        "TWITTER_ACCESS_TOKEN": "twitter",
        "TWITTER_ACCESS_TOKEN_SECRET": "twitter",
        
        # Facebook/Meta
        "FACEBOOK_APP_ID": "facebook",
        "FACEBOOK_APP_SECRET": "facebook",
        "FACEBOOK_PAGE_ACCESS_TOKEN": "facebook",
        "INSTAGRAM_BUSINESS_ID": "instagram",
        "INSTAGRAM_ACCESS_TOKEN": "instagram",
        
        # LinkedIn
        "LINKEDIN_CLIENT_ID": "linkedin",
        "LINKEDIN_CLIENT_SECRET": "linkedin",
        "LINKEDIN_ACCESS_TOKEN": "linkedin",
        
        # TikTok
        "TIKTOK_CLIENT_KEY": "tiktok",
        "TIKTOK_CLIENT_SECRET": "tiktok",
        "TIKTOK_ACCESS_TOKEN": "tiktok",
        
        # YouTube
        "YOUTUBE_API_KEY": "youtube",
        "GOOGLE_CLIENT_ID": "google",
        "GOOGLE_CLIENT_SECRET": "google",

        # OpenAI/Anthropic
        "OPENAI_API_KEY": "ai",
        "ANTHROPIC_API_KEY": "ai",
        "COHERE_API_KEY": "ai",
        
        # Blockchain
        "ETHEREUM_PRIVATE_KEY": "blockchain",
        "POLYGON_PRIVATE_KEY": "blockchain",
        "SOLANA_PRIVATE_KEY": "blockchain",
        "INFURA_PROJECT_ID": "blockchain",
        "ALCHEMY_API_KEY": "blockchain",
        
        # Payment Processing
        "STRIPE_SECRET_KEY": "payment",
        "STRIPE_PUBLISHABLE_KEY": "payment",
        "STRIPE_WEBHOOK_SECRET": "payment",
        "PAYPAL_CLIENT_ID": "payment",
        "PAYPAL_CLIENT_SECRET": "payment",
        
        # Analytics
        "GOOGLE_ANALYTICS_ID": "Analytics",
        "MIXPANEL_TOKEN": "Analytics",
        "SEGMENT_WRITE_KEY": "Analytics",
        "AMPLITUDE_API_KEY": "Analytics",
        
        # Cloud Services
        "AWS_ACCESS_KEY_ID": "aws",
        "AWS_SECRET_ACCESS_KEY": "aws",
        "GCP_SERVICE_ACCOUNT_KEY": "gcp",
        "AZURE_SUBSCRIPTION_ID": "azure",
        
        # Communication
        "TWILIO_ACCOUNT_SID": "communication",
        "TWILIO_AUTH_TOKEN": "communication",
        "SENDGRID_API_KEY": "communication",
        "DISCORD_BOT_TOKEN": "communication",
        "SLACK_BOT_TOKEN": "communication",
        "TELEGRAM_BOT_TOKEN": "communication",
    }
    # Extra operator-curated {SECRET_KEY: group} entries (e.g. project-specific
    # market keys) merged over the generic platform map above, from the
    # `[secrets.key_groups]` config table (ships empty for new installs).
    SOCIAL_SECRETS.update(_config_key_groups())

    # Project-specific secret requirements, from the
    # `[secrets.project_required]` config table (ships empty for new installs).
    PROJECT_SECRETS = _config_project_required()


    def __init__(self, password: Optional[str] = None):
        self.fleet_root = get_fleet_root()
        self.secrets_dir = self.fleet_root / ".secrets"
        self.secrets_dir.mkdir(exist_ok=True)
        
        # Set up encryption
        if password:
            self.cipher = self._get_cipher(password)
        else:
            self.cipher = None
    
    def _get_cipher(self, password: str) -> Fernet:
        """Create cipher from password"""
        password_bytes = password.encode()
        salt = b'fleet_secrets_salt_2025'  # In production, use random salt stored separately
        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password_bytes))
        return Fernet(key)
    
    def encrypt_file(self, input_path: str, output_path: str, password: str):
        """Encrypt a YAML file containing secrets"""
        with open(input_path, 'r') as f:
            data = f.read()
        
        cipher = self._get_cipher(password)
        encrypted = cipher.encrypt(data.encode())
        
        with open(output_path, 'wb') as f:
            f.write(encrypted)
        
        click.echo(f" Encrypted secrets saved to {output_path}")
    
    def decrypt_file(self, input_path: str, password: str) -> Dict[str, Any]:
        """Decrypt and load secrets file"""
        with open(input_path, 'rb') as f:
            encrypted = f.read()
        
        cipher = self._get_cipher(password)
        decrypted = cipher.decrypt(encrypted)
        
        return yaml.safe_load(decrypted.decode())
    
    def import_from_excel(self, excel_path: str, password: str):
        """Import secrets from Excel sheet to encrypted storage"""
        try:
            import pandas as pd
        except ImportError:
            click.echo("pandas required: pip install pandas openpyxl", err=True)
            return False
        
        # Read Excel
        df = pd.read_excel(excel_path)
        
        # Expected columns: Project, Key, Value, Environment, Category
        secrets_data = {
            "production": {},
            "staging": {},
            "development": {}
        }
        
        for _, row in df.iterrows():
            env = row.get('Environment', 'production')
            key = row.get('Key')
            value = row.get('Value')
            
            if key and value and env in secrets_data:
                secrets_data[env][key] = value
        
        # Save encrypted
        output_path = self.secrets_dir / "social_secrets.enc"
        temp_yaml = self.secrets_dir / "temp.yaml"
        
        with open(temp_yaml, 'w') as f:
            yaml.dump(secrets_data, f)
        
        self.encrypt_file(str(temp_yaml), str(output_path), password)
        temp_yaml.unlink()  # Delete temp file
        
        click.echo(f" Imported {sum(len(env) for env in secrets_data.values())} secrets")
        return True
    
    def apply_social_secrets(self, project: str, environment: str = "production"):
        """Apply social/sensitive secrets to a project"""
        if not self.cipher:
            password = getpass.getpass("Enter secrets password: ")
            self.cipher = self._get_cipher(password)
        
        # Load encrypted secrets
        secrets_file = self.secrets_dir / "social_secrets.enc"
        if not secrets_file.exists():
            click.echo("No encrypted secrets file found", err=True)
            return False
        
        try:
            secrets_data = self.decrypt_file(str(secrets_file), password)
        except Exception as e:
            click.echo(f"Failed to decrypt: {e}", err=True)
            return False
        
        env_secrets = secrets_data.get(environment, {})
        
        # Get project-specific secrets
        required_keys = self.PROJECT_SECRETS.get(project, [])
        project_secrets = {k: v for k, v in env_secrets.items() 
                          if k in required_keys}
        
        if not project_secrets:
            click.echo(f"No social secrets found for {project}", err=True)
            return False
        
        # Write to project's .env.social file (separate from main .env)
        project_path = self.fleet_root / project
        social_env_file = project_path / f".env.social.{environment}"
        
        content = "# Social Platform and Sensitive API Keys\n"
        content += "# This file is managed by SEGA secrets management\n"
        content += "# DO NOT COMMIT TO GIT\n\n"
        
        for key, value in sorted(project_secrets.items()):
            # Mask sensitive parts in output
            masked = value[:4] + "..." + value[-4:] if len(value) > 8 else "***"
            click.echo(f"  Adding {key}: {masked}")
            content += f"{key}={value}\n"
        
        social_env_file.write_text(content)
        
        # Update .gitignore
        gitignore = project_path / ".gitignore"
        if gitignore.exists():
            gitignore_content = gitignore.read_text()
            if ".env.social*" not in gitignore_content:
                gitignore_content += "\n# Social secrets\n.env.social*\n"
                gitignore.write_text(gitignore_content)
        
        click.echo(f" Applied {len(project_secrets)} social secrets to {project}")
        return True
    
    def validate_social_secrets(self, environment: str = "production") -> Dict[str, bool]:
        """Validate all social secrets are present"""
        password = getpass.getpass("Enter secrets password: ")
        
        secrets_file = self.secrets_dir / "social_secrets.enc"
        if not secrets_file.exists():
            click.echo("No encrypted secrets file found", err=True)
            return {}
        
        try:
            secrets_data = self.decrypt_file(str(secrets_file), password)
        except Exception:
            click.echo("Failed to decrypt secrets", err=True)
            return {}
        
        env_secrets = secrets_data.get(environment, {})
        validation = {}
        
        # Check each project's requirements
        for project, required_keys in self.PROJECT_SECRETS.items():
            project_valid = True
            for key in required_keys:
                if key not in env_secrets:
                    validation[f"{project}:{key}"] = False
                    project_valid = False
                else:
                    validation[f"{project}:{key}"] = True
            
            validation[f"{project}:COMPLETE"] = project_valid
        
        return validation
    
    def rotate_key(self, key_name: str, new_value: str, environment: str = "production"):
        """Rotate a specific API key"""
        password = getpass.getpass("Enter secrets password: ")
        
        secrets_file = self.secrets_dir / "social_secrets.enc"
        if not secrets_file.exists():
            click.echo("No encrypted secrets file found", err=True)
            return False
        
        try:
            secrets_data = self.decrypt_file(str(secrets_file), password)
        except Exception:
            click.echo("Failed to decrypt secrets", err=True)
            return False
        
        # Update the key
        if environment in secrets_data:
            old_value = secrets_data[environment].get(key_name, "NOT_SET")
            secrets_data[environment][key_name] = new_value
            
            # Re-encrypt and save
            temp_yaml = self.secrets_dir / "temp.yaml"
            with open(temp_yaml, 'w') as f:
                yaml.dump(secrets_data, f)
            
            self.encrypt_file(str(temp_yaml), str(secrets_file), password)
            temp_yaml.unlink()
            
            # Log rotation (audit trail)
            audit_log = self.secrets_dir / "rotation_audit.log"
            with open(audit_log, 'a') as f:
                from datetime import datetime
                f.write(f"{datetime.now().isoformat()} - Rotated {key_name} in {environment}\n")
            
            click.echo(f" Rotated {key_name} successfully")
            return True
        
        return False


# CLI Commands Extension
@click.group()
def social():
    """Manage social platform and sensitive API keys"""
    pass


@social.command()
@click.option('--excel', '-e', required=True, help='Excel file with secrets')
@click.option('--password', '-p', help='Password for encryption (will prompt if not provided)')
def import_excel(excel, password):
    """Import secrets from Excel spreadsheet"""
    if not password:
        password = getpass.getpass("Enter password for encryption: ")
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            click.echo("Passwords don't match", err=True)
            return
    
    manager = SocialSecretsManager(password)
    manager.import_from_excel(excel, password)


@social.command()
@click.option('--project', '-p', required=True, help='Project name')
@click.option('--env', '-e', default='production', help='Environment')
def apply(project, env):
    """Apply social secrets to a project"""
    manager = SocialSecretsManager()
    manager.apply_social_secrets(project, env)


@social.command()
@click.option('--env', '-e', default='production', help='Environment')
def validate(env):
    """Validate all social secrets are configured"""
    manager = SocialSecretsManager()
    results = manager.validate_social_secrets(env)
    
    click.echo(f"\nSocial secrets validation for {env}:")
    
    # Group by project
    projects = {}
    for key, valid in results.items():
        project = key.split(':')[0]
        if project not in projects:
            projects[project] = []
        projects[project].append((key, valid))
    
    for project in sorted(projects.keys()):
        complete = results.get(f"{project}:COMPLETE", False)
        status = "" if complete else ""
        click.echo(f"\n{status} {project}")
        
        for key, valid in projects[project]:
            if ":COMPLETE" not in key:
                status = "" if valid else ""
                secret_name = key.split(':')[1]
                click.echo(f"    {status} {secret_name}")


@social.command()
@click.option('--key', '-k', required=True, help='Key name to rotate')
@click.option('--value', '-v', required=True, help='New value')
@click.option('--env', '-e', default='production', help='Environment')
def rotate(key, value, env):
    """Rotate a specific API key"""
    manager = SocialSecretsManager()
    manager.rotate_key(key, value, env)


@social.command()
@click.option('--input', '-i', required=True, help='Plain YAML file to encrypt')
@click.option('--output', '-o', help='Output file (default: social_secrets.enc)')
def encrypt(input, output):
    """Encrypt a YAML secrets file"""
    password = getpass.getpass("Enter password for encryption: ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        click.echo("Passwords don't match", err=True)
        return
    
    manager = SocialSecretsManager(password)
    output = output or str(manager.secrets_dir / "social_secrets.enc")
    manager.encrypt_file(input, output, password)


if __name__ == "__main__":
    social()