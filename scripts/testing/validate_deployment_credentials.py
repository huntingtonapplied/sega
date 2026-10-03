#!/usr/bin/env python3
"""
SEGA Deployment Engine Credential Validation Script

This script validates that all required credentials are properly configured
for each deployment engine in the SEGA platform.

Usage:
    python scripts/validate_deployment_credentials.py
    python scripts/validate_deployment_credentials.py --engine ecs
    python scripts/validate_deployment_credentials.py --verbose
"""

import os
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import subprocess
import json

# Add SEGA source to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

class DeploymentCredentialValidator:
    """Validates deployment engine credentials and configuration."""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.issues = []
        
    def validate_all_engines(self) -> bool:
        """Validate credentials for all deployment engines."""
        print(" SEGA Deployment Engine Credential Validation")
        print("=" * 50)
        
        engines = [
            ("Security Variables", self._validate_security_credentials),
            ("ECS", self._validate_ecs_credentials),
            ("Kubernetes", self._validate_k8s_credentials),
            ("Ansible", self._validate_ansible_credentials),
            ("FPGA", self._validate_fpga_credentials),
            ("SSH", self._validate_ssh_credentials),
            ("Docker Registry", self._validate_docker_credentials)
        ]
        
        all_valid = True
        for engine_name, validator in engines:
            print(f"\\n Validating {engine_name} credentials...")
            
            try:
                is_valid = validator()
                status = " VALID" if is_valid else " INVALID"
                print(f"   {status}")
                
                if not is_valid:
                    all_valid = False
                    
            except Exception as e:
                print(f"    ERROR: {e}")
                all_valid = False
        
        print(f"\\n{'=' * 50}")
        if all_valid:
            print(" All deployment engine credentials are properly configured!")
        else:
            print(" Some deployment engines have credential issues:")
            for issue in self.issues:
                print(f"   • {issue}")
                
        return all_valid
    
    def validate_engine(self, engine_name: str) -> bool:
        """Validate credentials for a specific engine."""
        validators = {
            "security": self._validate_security_credentials,
            "ecs": self._validate_ecs_credentials,
            "k8s": self._validate_k8s_credentials,
            "kubernetes": self._validate_k8s_credentials,
            "ansible": self._validate_ansible_credentials,
            "fpga": self._validate_fpga_credentials,
            "ssh": self._validate_ssh_credentials,
            "docker": self._validate_docker_credentials
        }
        
        validator = validators.get(engine_name.lower())
        if not validator:
            print(f" Unknown engine: {engine_name}")
            return False
            
        print(f" Validating {engine_name.upper()} credentials...")
        try:
            is_valid = validator()
            print(" VALID" if is_valid else " INVALID")
            return is_valid
        except Exception as e:
            print(f" ERROR: {e}")
            return False
    
    def _validate_security_credentials(self) -> bool:
        """Validate SEGA security environment variables."""
        required_security_vars = [
            "SEGA_JWT_SECRET_KEY",
            "SEGA_API_KEY",
            "SEGA_SESSION_SECRET",
            "SEGA_ENCRYPTION_KEY",
            "SEGA_CSRF_SECRET",
            "DEPLOYMENT_ENGINE_SECRET",
            "HARDWARE_ACCESS_SECRET"
        ]
        
        missing = []
        weak = []
        
        for var in required_security_vars:
            value = os.getenv(var)
            if not value:
                missing.append(var)
            elif len(value) < 32:
                weak.append(var)
                
        if missing:
            self.issues.append(f"Security: Missing required variables: {', '.join(missing)}")
            if self.verbose:
                print(f"     Missing: {', '.join(missing)}")
                print("     Generate with: openssl rand -hex 32")
            return False
            
        if weak:
            self.issues.append(f"Security: Weak secrets (< 32 chars): {', '.join(weak)}")
            if self.verbose:
                print(f"     Weak secrets: {', '.join(weak)}")
                print("     Use stronger secrets: openssl rand -hex 32")
            return False
            
        if self.verbose:
            print("     All security variables properly configured")
            
        return True
    
    def _validate_ecs_credentials(self) -> bool:
        """Validate AWS ECS deployment credentials."""
        required_vars = [
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "AWS_REGION"
        ]
        
        missing = []
        for var in required_vars:
            if not os.getenv(var):
                missing.append(var)
                
        if missing:
            self.issues.append(f"ECS: Missing environment variables: {', '.join(missing)}")
            if self.verbose:
                print(f"     Missing: {', '.join(missing)}")
            return False
            
        # Test AWS connection if boto3 is available
        try:
            import boto3
            from botocore.exceptions import ClientError, NoCredentialsError
            
            ecs_client = boto3.client('ecs', region_name=os.getenv('AWS_REGION'))
            ecs_client.list_clusters(maxResults=1)
            
            if self.verbose:
                print("     AWS credentials tested successfully")
                
        except ImportError:
            if self.verbose:
                print("     boto3 not available, skipping connection test")
        except NoCredentialsError:
            self.issues.append("ECS: AWS credentials not configured properly")
            return False
        except ClientError as e:
            if e.response['Error']['Code'] == 'UnauthorizedOperation':
                if self.verbose:
                    print("     AWS credentials valid but missing ECS permissions")
            else:
                self.issues.append(f"ECS: AWS connection error: {e}")
                return False
        except Exception as e:
            self.issues.append(f"ECS: Connection test failed: {e}")
            return False
            
        return True
    
    def _validate_k8s_credentials(self) -> bool:
        """Validate Kubernetes deployment credentials."""
        # Check for kubeconfig file
        kubeconfig_path = os.getenv('KUBERNETES_CONFIG') or os.path.expanduser('~/.kube/config')
        
        if not Path(kubeconfig_path).exists():
            self.issues.append(f"Kubernetes: kubeconfig file not found at {kubeconfig_path}")
            return False
            
        # Test kubectl connection if available
        try:
            result = subprocess.run(
                ['kubectl', 'cluster-info', '--request-timeout=5s'],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode != 0:
                self.issues.append(f"Kubernetes: kubectl connection failed: {result.stderr}")
                return False
                
            if self.verbose:
                print("     kubectl connection tested successfully")
                
        except FileNotFoundError:
            if self.verbose:
                print("     kubectl not available, skipping connection test")
        except subprocess.TimeoutExpired:
            self.issues.append("Kubernetes: kubectl connection timeout")
            return False
        except Exception as e:
            self.issues.append(f"Kubernetes: Connection test failed: {e}")
            return False
            
        return True
    
    def _validate_ansible_credentials(self) -> bool:
        """Validate Ansible deployment credentials."""
        # Check for required environment variables
        ansible_vars = [
            "ANSIBLE_PRIVATE_KEY_FILE",
            "ANSIBLE_REMOTE_USER"
        ]
        
        missing = []
        for var in ansible_vars:
            if not os.getenv(var):
                missing.append(var)
                
        # Check for private key file
        private_key_path = os.getenv('ANSIBLE_PRIVATE_KEY_FILE')
        if private_key_path and not Path(private_key_path).exists():
            self.issues.append(f"Ansible: Private key file not found: {private_key_path}")
            return False
            
        # Check for inventory file
        inventory_path = Path("infrastructure/ansible/host.ini")
        if not inventory_path.exists():
            self.issues.append("Ansible: Inventory file not found at infrastructure/ansible/host.ini")
            return False
            
        # Test ansible command if available
        try:
            result = subprocess.run(
                ['ansible', '--version'],
                capture_output=True, text=True, timeout=5
            )
            
            if result.returncode != 0:
                self.issues.append("Ansible: ansible command not working")
                return False
                
            if self.verbose:
                print("     Ansible installation verified")
                
        except FileNotFoundError:
            self.issues.append("Ansible: ansible command not found")
            return False
        except Exception as e:
            self.issues.append(f"Ansible: Validation failed: {e}")
            return False
            
        return True
    
    def _validate_fpga_credentials(self) -> bool:
        """Validate FPGA deployment credentials."""
        # Check for openFPGALoader
        openfpgaloader_path = os.getenv('OPENFPGALOADER_PATH', '/usr/local/bin/openFPGALoader')
        
        if not Path(openfpgaloader_path).exists():
            self.issues.append(f"FPGA: openFPGALoader not found at {openfpgaloader_path}")
            return False
            
        # Check for FPGA programmer key
        fpga_key = os.getenv('FPGA_PROGRAMMER_KEY')
        if not fpga_key:
            if self.verbose:
                print("     FPGA_PROGRAMMER_KEY not set (may be optional)")
                
        # Test openFPGALoader if available
        try:
            result = subprocess.run(
                [openfpgaloader_path, '--help'],
                capture_output=True, text=True, timeout=5
            )
            
            if result.returncode not in [0, 1]:  # --help often returns 1
                self.issues.append("FPGA: openFPGALoader not working properly")
                return False
                
            if self.verbose:
                print("     openFPGALoader installation verified")
                
        except Exception as e:
            self.issues.append(f"FPGA: openFPGALoader test failed: {e}")
            return False
            
        return True
    
    def _validate_ssh_credentials(self) -> bool:
        """Validate SSH access credentials."""
        # Check for SSH private key
        ssh_key_path = os.getenv('SSH_PRIVATE_KEY')
        if not ssh_key_path:
            self.issues.append("SSH: SSH_PRIVATE_KEY environment variable not set")
            return False
            
        if not Path(ssh_key_path).exists():
            self.issues.append(f"SSH: Private key file not found: {ssh_key_path}")
            return False
            
        # Check key permissions
        key_stat = Path(ssh_key_path).stat()
        if key_stat.st_mode & 0o077:
            self.issues.append(f"SSH: Private key has insecure permissions: {oct(key_stat.st_mode)}")
            if self.verbose:
                print(f"     Fix with: chmod 600 {ssh_key_path}")
            return False
            
        if self.verbose:
            print("     SSH private key found with secure permissions")
            
        return True
    
    def _validate_docker_credentials(self) -> bool:
        """Validate Docker registry credentials."""
        # Check if Docker is installed
        try:
            result = subprocess.run(
                ['docker', '--version'],
                capture_output=True, text=True, timeout=5
            )
            
            if result.returncode != 0:
                self.issues.append("Docker: docker command not working")
                return False
                
        except FileNotFoundError:
            self.issues.append("Docker: docker command not found")
            return False
        except Exception as e:
            self.issues.append(f"Docker: Installation check failed: {e}")
            return False
            
        # Check for registry credentials (optional)
        registry_user = os.getenv('DOCKER_REGISTRY_USER')
        registry_pass = os.getenv('DOCKER_REGISTRY_PASS')
        
        if registry_user and not registry_pass:
            self.issues.append("Docker: DOCKER_REGISTRY_USER set but DOCKER_REGISTRY_PASS missing")
            return False
            
        if registry_pass and not registry_user:
            self.issues.append("Docker: DOCKER_REGISTRY_PASS set but DOCKER_REGISTRY_USER missing")
            return False
            
        if self.verbose:
            if registry_user:
                print("     Docker registry credentials configured")
            else:
                print("     Docker registry credentials not configured (using public registries)")
                
        return True


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validate SEGA deployment engine credentials"
    )
    parser.add_argument(
        '--engine', '-e',
        help="Validate specific engine only (ecs, k8s, ansible, fpga, ssh, docker)"
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help="Show verbose output"
    )
    
    args = parser.parse_args()
    
    validator = DeploymentCredentialValidator(verbose=args.verbose)
    
    if args.engine:
        success = validator.validate_engine(args.engine)
    else:
        success = validator.validate_all_engines()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()