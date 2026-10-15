#!/usr/bin/env python3
# Copyright 2025 SEGA
#
# SEGA Social Secrets Management Command
# Handles social platform and sensitive API keys with three-tier security

import os
import json
import yaml
import click
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import getpass
import requests


@dataclass
class SecretCategory:
    """Categorization for different security levels"""
    INFRASTRUCTURE = "infrastructure"  # GitLab CI/CD (Auth0, databases, Sentry)
    SOCIAL = "social"  # Encrypted local (Twitter, TikTok, Instagram)
    SENSITIVE = "sensitive"  # Ultra-sensitive (blockchain keys, payment)
    HSM = "hsm"  # Future HSM integration


@dataclass
class SecretMapping:
    """Maps secrets to projects and categories"""
    key: str
    value: str
    category: str
    projects: List[str]
    description: str = ""
    rotation_days: int = 90
    last_rotated: Optional[datetime] = None


def _social_project_mappings() -> Dict[str, List[str]]:
    """Project-to-secret mapping from the `[secrets.social_project_mappings]`
    config table (operator data; ships empty for new installs)."""
    from sega.core.config import get_config
    return {
        project: list(keys)
        for project, keys in get_config().secrets.social_project_mappings.items()
    }


class SocialSecretsManager:
    """Manages social platform and sensitive secrets with encryption"""

    # Project to secret mapping (config-sourced).
    PROJECT_MAPPINGS = _social_project_mappings()
    
    # Category classification patterns
    CATEGORY_PATTERNS = {
        SecretCategory.INFRASTRUCTURE: [
            "AUTH0", "DATABASE", "POSTGRES", "REDIS", "MONGO",
            "SENTRY", "MAILGUN", "SENDGRID", "SMTP",
            "AWS_RDS", "AZURE_SQL", "GCP_SQL"
        ],
        SecretCategory.SOCIAL: [
            "TWITTER", "FACEBOOK", "INSTAGRAM", "TIKTOK", "LINKEDIN",
            "YOUTUBE", "PINTEREST", "SNAPCHAT", "REDDIT", "DISCORD",
            "TELEGRAM", "WHATSAPP", "WECHAT", "MEDIUM", "TWITCH"
        ],
        SecretCategory.SENSITIVE: [
            "PRIVATE_KEY", "MNEMONIC", "SEED", "WALLET",
            "STRIPE", "PAYPAL", "SQUARE", "COINBASE",
            "POLYMARKET", "PREDICTIT", "BLOCKCHAIN", "CRYPTO"
        ],
        SecretCategory.HSM: [
            "HSM_", "MASTER_KEY", "ROOT_KEY", "SIGNING_KEY"
        ]
    }
    
    def __init__(self, config_dir: Path = None):
        """Initialize the social secrets manager"""
        self.config_dir = config_dir or Path.home() / ".sega" / "secrets"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        self.encrypted_file = self.config_dir / "social_secrets.enc"
        self.metadata_file = self.config_dir / "secrets_metadata.json"
        self.audit_log = self.config_dir / "audit.log"
        
    def categorize_secret(self, key: str) -> str:
        """Automatically categorize a secret based on its name"""
        key_upper = key.upper()
        
        # Check patterns for each category
        for category, patterns in self.CATEGORY_PATTERNS.items():
            for pattern in patterns:
                if pattern in key_upper:
                    return category
                    
        # Default to infrastructure if no pattern matches
        return SecretCategory.INFRASTRUCTURE
        
    def get_projects_for_secret(self, key: str) -> List[str]:
        """Determine which projects need a given secret"""
        projects = []
        key_upper = key.upper()
        
        for project, secrets in self.PROJECT_MAPPINGS.items():
            for secret_pattern in secrets:
                if secret_pattern in key_upper or key_upper in secret_pattern:
                    projects.append(project)
                    break
                    
        return projects if projects else ["all"]
        
    def derive_key_from_password(self, password: str, salt: bytes = None) -> bytes:
        """Derive encryption key from password using PBKDF2"""
        if salt is None:
            salt = os.urandom(16)
            
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key, salt
        
    def encrypt_secrets(self, secrets: Dict[str, Any], password: str) -> bytes:
        """Encrypt secrets with password-derived key"""
        key, salt = self.derive_key_from_password(password)
        fernet = Fernet(key)
        
        # Serialize secrets
        secrets_json = json.dumps(secrets, indent=2)
        encrypted = fernet.encrypt(secrets_json.encode())
        
        # Combine salt and encrypted data
        return salt + encrypted
        
    def decrypt_secrets(self, encrypted_data: bytes, password: str) -> Dict[str, Any]:
        """Decrypt secrets with password"""
        # Extract salt (first 16 bytes)
        salt = encrypted_data[:16]
        encrypted = encrypted_data[16:]
        
        # Derive key from password and salt
        key, _ = self.derive_key_from_password(password, salt)
        fernet = Fernet(key)
        
        # Decrypt
        decrypted = fernet.decrypt(encrypted)
        return json.loads(decrypted.decode())
        
    def import_from_excel(self, excel_path: Path, sheet_name: str = None) -> Dict[str, List[SecretMapping]]:
        """Import secrets from Excel file and categorize them"""
        try:
            import pandas as pd  # optional: pip install 'sega[data]'
        except ImportError:
            raise click.ClickException("Excel import needs pandas: pip install 'sega[data]'")
        # Read Excel file
        if sheet_name:
            df = pd.read_excel(excel_path, sheet_name=sheet_name)
        else:
            df = pd.read_excel(excel_path)
            
        # Expected columns: KEY, VALUE, DESCRIPTION (optional), PROJECTS (optional)
        if 'KEY' not in df.columns or 'VALUE' not in df.columns:
            raise ValueError("Excel must have KEY and VALUE columns")
            
        categorized = {
            SecretCategory.INFRASTRUCTURE: [],
            SecretCategory.SOCIAL: [],
            SecretCategory.SENSITIVE: [],
            SecretCategory.HSM: []
        }
        
        for _, row in df.iterrows():
            key = str(row['KEY']).strip()
            value = str(row['VALUE']).strip()
            description = str(row.get('DESCRIPTION', '')).strip()
            
            # Categorize the secret
            category = self.categorize_secret(key)
            
            # Determine projects
            if 'PROJECTS' in row and pd.notna(row['PROJECTS']):
                projects = [p.strip() for p in str(row['PROJECTS']).split(',')]
            else:
                projects = self.get_projects_for_secret(key)
                
            mapping = SecretMapping(
                key=key,
                value=value,
                category=category,
                projects=projects,
                description=description
            )
            
            categorized[category].append(mapping)
            
        return categorized
        
    def save_encrypted_secrets(self, secrets: Dict[str, List[SecretMapping]], password: str):
        """Save categorized secrets with encryption"""
        # Separate by category
        social_sensitive = {}
        infrastructure = {}
        
        for category, mappings in secrets.items():
            for mapping in mappings:
                if category in [SecretCategory.SOCIAL, SecretCategory.SENSITIVE, SecretCategory.HSM]:
                    social_sensitive[mapping.key] = {
                        'value': mapping.value,
                        'category': mapping.category,
                        'projects': mapping.projects,
                        'description': mapping.description,
                        'last_updated': datetime.now().isoformat()
                    }
                else:
                    infrastructure[mapping.key] = mapping.value
                    
        # Encrypt social/sensitive secrets
        if social_sensitive:
            encrypted = self.encrypt_secrets(social_sensitive, password)
            with open(self.encrypted_file, 'wb') as f:
                f.write(encrypted)
                
        # Save metadata (without values)
        metadata = {
            'last_import': datetime.now().isoformat(),
            'categories': {
                category: len(mappings) for category, mappings in secrets.items()
            },
            'total_secrets': sum(len(m) for m in secrets.values()),
            'projects_configured': list(set(
                project for mappings in secrets.values() 
                for mapping in mappings 
                for project in mapping.projects
            ))
        }
        
        with open(self.metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
            
        return infrastructure, social_sensitive
        
    def load_encrypted_secrets(self, password: str) -> Dict[str, Any]:
        """Load and decrypt social/sensitive secrets"""
        if not self.encrypted_file.exists():
            raise FileNotFoundError("No encrypted secrets file found")
            
        with open(self.encrypted_file, 'rb') as f:
            encrypted_data = f.read()
            
        return self.decrypt_secrets(encrypted_data, password)
        
    def apply_to_project(self, project: str, env: str = 'production', password: str = None):
        """Apply secrets to a specific project"""
        project_path = Path.cwd().parent / project
        if not project_path.exists():
            raise FileNotFoundError(f"Project {project} not found at {project_path}")
            
        # Load encrypted secrets if password provided
        social_secrets = {}
        if password:
            try:
                all_secrets = self.load_encrypted_secrets(password)
                # Filter for this project
                social_secrets = {
                    key: data['value'] 
                    for key, data in all_secrets.items()
                    if project in data['projects'] or 'all' in data['projects']
                }
            except FileNotFoundError:
                click.echo("No encrypted social secrets found")
                
        # Write to .env.social file (gitignored)
        if social_secrets:
            env_file = project_path / f".env.social.{env}"
            with open(env_file, 'w') as f:
                f.write(f"# Social platform secrets for {project}\n")
                f.write(f"# Generated by SEGA Social Secrets Manager\n")
                f.write(f"# Last updated: {datetime.now().isoformat()}\n\n")
                
                for key, value in sorted(social_secrets.items()):
                    f.write(f"{key}={value}\n")
                    
            # Update .gitignore to exclude social env files
            gitignore = project_path / '.gitignore'
            if gitignore.exists():
                with open(gitignore, 'r') as f:
                    content = f.read()
                if '.env.social' not in content:
                    with open(gitignore, 'a') as f:
                        f.write('\n# Social secrets (encrypted locally)\n')
                        f.write('.env.social.*\n')
                        
            return len(social_secrets)
            
        return 0
        
    def validate_project_secrets(self, project: str, password: str = None) -> Dict[str, bool]:
        """Validate that a project has all required secrets"""
        required = self.PROJECT_MAPPINGS.get(project, [])
        if not required:
            return {}
            
        found = {}
        missing = {}
        
        # Check encrypted secrets
        if password:
            try:
                secrets = self.load_encrypted_secrets(password)
                for key in required:
                    # Check if any secret matches the pattern
                    found[key] = any(
                        key in secret_key or secret_key in key
                        for secret_key in secrets.keys()
                    )
            except FileNotFoundError:
                for key in required:
                    found[key] = False
        else:
            for key in required:
                found[key] = False
                
        return found
        
    def rotate_secret(self, key: str, new_value: str, password: str):
        """Rotate a specific secret with audit trail"""
        # Load existing secrets
        secrets = self.load_encrypted_secrets(password)
        
        if key not in secrets:
            raise KeyError(f"Secret {key} not found")
            
        # Update with audit trail
        old_value_hash = hashlib.sha256(secrets[key]['value'].encode()).hexdigest()[:8]
        secrets[key]['value'] = new_value
        secrets[key]['last_rotated'] = datetime.now().isoformat()
        secrets[key]['previous_hash'] = old_value_hash
        
        # Save updated secrets
        encrypted = self.encrypt_secrets(secrets, password)
        with open(self.encrypted_file, 'wb') as f:
            f.write(encrypted)
            
        # Log rotation
        with open(self.audit_log, 'a') as f:
            f.write(json.dumps({
                'action': 'rotate',
                'key': key,
                'timestamp': datetime.now().isoformat(),
                'old_hash': old_value_hash
            }) + '\n')
            
    def export_to_gitlab(self, infrastructure_secrets: Dict[str, str]):
        """Export infrastructure secrets to GitLab CI/CD variables"""
        gitlab_url = os.getenv("GITLAB_URL", "https://gitlab.com")
        project_id = os.getenv("CI_PROJECT_ID", "")
        token = os.getenv("GITLAB_TOKEN", "")
        
        if not project_id or not token:
            raise ValueError("GITLAB_TOKEN and CI_PROJECT_ID must be set")
            
        headers = {"PRIVATE-TOKEN": token}
        base_url = f"{gitlab_url}/api/v4/projects/{project_id}/variables"
        
        created = 0
        updated = 0
        
        for key, value in infrastructure_secrets.items():
            # Try to create variable
            response = requests.post(
                base_url,
                headers=headers,
                json={
                    "key": key,
                    "value": value,
                    "protected": True,
                    "masked": True,
                    "environment_scope": "*"
                }
            )
            
            if response.status_code == 201:
                created += 1
            elif response.status_code == 400:
                # Variable exists, update it
                response = requests.put(
                    f"{base_url}/{key}",
                    headers=headers,
                    json={
                        "value": value,
                        "protected": True,
                        "masked": True
                    }
                )
                if response.status_code == 200:
                    updated += 1
                    
        return created, updated


@click.group()
def social():
    """Manage social platform and sensitive secrets"""
    pass


@social.command()
@click.option('--excel', '-e', type=click.Path(exists=True), required=True, help='Excel file with secrets')
@click.option('--sheet', '-s', help='Sheet name to import from')
@click.option('--password', '-p', help='Password for encryption (will prompt if not provided)')
@click.option('--push-infra/--no-push-infra', default=True, help='Push infrastructure secrets to GitLab')
def import_excel(excel, sheet, password, push_infra):
    """Import secrets from Excel and categorize by security level"""
    manager = SocialSecretsManager()
    
    # Get password if not provided
    if not password:
        password = getpass.getpass("Enter encryption password: ")
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            click.echo("Passwords don't match")
            raise click.Abort()
            
    click.echo(f"Importing secrets from {excel}...")
    
    # Import and categorize
    categorized = manager.import_from_excel(Path(excel), sheet)
    
    # Show categorization summary
    click.echo("\n Categorization Summary:")
    click.echo("=" * 50)
    for category, mappings in categorized.items():
        click.echo(f"{category}: {len(mappings)} secrets")
        if mappings and len(mappings) <= 5:
            for m in mappings[:5]:
                click.echo(f"  - {m.key} → {', '.join(m.projects)}")
                
    # Save encrypted secrets
    infrastructure, social_sensitive = manager.save_encrypted_secrets(categorized, password)
    
    click.echo(f"\n Encrypted {len(social_sensitive)} social/sensitive secrets")
    click.echo(f" Identified {len(infrastructure)} infrastructure secrets")
    
    # Push infrastructure to GitLab if requested
    if push_infra and infrastructure:
        click.echo("\n Pushing infrastructure secrets to GitLab...")
        try:
            created, updated = manager.export_to_gitlab(infrastructure)
            click.echo(f" GitLab: {created} created, {updated} updated")
        except Exception as e:
            click.echo(f"️ GitLab push failed: {e}")
            
    click.echo("\n Import complete!")
    click.echo("Next steps:")
    click.echo("1. Run 'sega social apply' to distribute secrets to projects")
    click.echo("2. Run 'sega social validate' to check completeness")


@social.command()
@click.option('--project', '-p', help='Project to apply secrets to (or "all")')
@click.option('--env', '-e', default='production', help='Environment')
@click.option('--password', '-p', help='Decryption password')
def apply(project, env, password):
    """Apply social/sensitive secrets to projects"""
    manager = SocialSecretsManager()
    
    if not password:
        password = getpass.getpass("Enter decryption password: ")
        
    projects = []
    if project == 'all':
        # Apply to all projects
        projects = list(manager.PROJECT_MAPPINGS.keys())
    elif project:
        projects = [project]
    else:
        # Interactive selection
        click.echo("Select projects to apply secrets to:")
        for i, p in enumerate(manager.PROJECT_MAPPINGS.keys(), 1):
            click.echo(f"{i}. {p}")
        selection = click.prompt("Enter numbers (comma-separated) or 'all'")
        
        if selection.lower() == 'all':
            projects = list(manager.PROJECT_MAPPINGS.keys())
        else:
            indices = [int(x.strip()) - 1 for x in selection.split(',')]
            all_projects = list(manager.PROJECT_MAPPINGS.keys())
            projects = [all_projects[i] for i in indices]
            
    # Apply to each project
    for proj in projects:
        click.echo(f"\n Applying secrets to {proj}...")
        try:
            count = manager.apply_to_project(proj, env, password)
            if count > 0:
                click.echo(f" Applied {count} secrets to {proj}/.env.social.{env}")
            else:
                click.echo(f"️ No secrets found for {proj}")
        except Exception as e:
            click.echo(f" Failed for {proj}: {e}")
            
    click.echo("\n AApplication complete!")


@social.command()
@click.option('--project', '-p', required=True, help='Project to validate')
@click.option('--password', help='Decryption password')
def validate(project, password):
    """Validate that a project has all required secrets"""
    manager = SocialSecretsManager()
    
    if not password:
        password = getpass.getpass("Enter decryption password: ")
        
    click.echo(f"Validating secrets for {project}...")
    
    found = manager.validate_project_secrets(project, password)
    
    if not found:
        click.echo(f"No required secrets defined for {project}")
        return
        
    # Display results
    missing = [key for key, exists in found.items() if not exists]
    present = [key for key, exists in found.items() if exists]
    
    if present:
        click.echo(f"\n Present ({len(present)}):")
        for key in present[:10]:  # Show first 10
            click.echo(f"  - {key}")
            
    if missing:
        click.echo(f"\n Missing ({len(missing)}):")
        for key in missing[:10]:  # Show first 10
            click.echo(f"  - {key}")
            
    if not missing:
        click.echo(f"\n All required secrets present for {project}!")
    else:
        click.echo(f"\n️ {len(missing)} secrets missing for {project}")


@social.command()
@click.option('--key', '-k', required=True, help='Secret key to rotate')
@click.option('--value', '-v', required=True, help='New value')
@click.option('--password', help='Decryption password')
def rotate(key, value, password):
    """Rotate a specific secret with audit trail"""
    manager = SocialSecretsManager()
    
    if not password:
        password = getpass.getpass("Enter decryption password: ")
        
    try:
        manager.rotate_secret(key, value, password)
        click.echo(f" Rotated secret: {key}")
        click.echo("Audit trail updated")
    except Exception as e:
        click.echo(f" Rotation failed: {e}")


@social.command()
def status():
    """Show social secrets system status"""
    manager = SocialSecretsManager()
    
    # Check if encrypted file exists
    if manager.encrypted_file.exists():
        click.echo(" Encrypted secrets: CONFIGURED")
        
        # Load metadata
        if manager.metadata_file.exists():
            with open(manager.metadata_file, 'r') as f:
                metadata = json.load(f)
                
            click.echo(f" Last import: {metadata['last_import']}")
            click.echo(f" Total secrets: {metadata['total_secrets']}")
            click.echo("\nCategories:")
            for category, count in metadata['categories'].items():
                click.echo(f"  - {category}: {count}")
                
            if metadata['projects_configured']:
                click.echo(f"\n Projects configured: {', '.join(metadata['projects_configured'])}")
    else:
        click.echo(" No encrypted secrets found")
        click.echo("Run 'sega social import-excel' to get started")
        
    # Check audit log
    if manager.audit_log.exists():
        with open(manager.audit_log, 'r') as f:
            lines = f.readlines()
        click.echo(f"\n Audit log: {len(lines)} entries")
        if lines:
            last_entry = json.loads(lines[-1])
            click.echo(f"Last action: {last_entry['action']} on {last_entry['timestamp']}")


if __name__ == "__main__":
    social()