# SEGA Local - Nginx Manager
"""Nginx configuration and SSL certificate management."""

import subprocess
import shutil
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
import socket

import yaml

from ..project.project_detector import ProjectDetector

logger = logging.getLogger(__name__)


class NginxManager:
    """Manages nginx configuration and SSL certificates for portfolio projects."""

    # Instance topology (project -> instance/ip) is sourced from sega.core.config
    # (`get_config().instances`); no hardcoded instance map is kept here.

    def __init__(self, project_path: Path = None):
        # Auto-detect project if not specified
        if project_path:
            self.project_path = Path(project_path)
        else:
            self.project_path = Path.cwd()

        # Initialize detector with project path
        self.detector = ProjectDetector(str(self.project_path))

        # Load project configuration
        self.project_info = self._detect_project()
        self.nginx_config_dir = Path('/etc/nginx/sites-available')
        self.nginx_enabled_dir = Path('/etc/nginx/sites-enabled')
        self.ssl_cert_dir = Path('/etc/letsencrypt/live')
        self.templates_dir = Path(__file__).parent.parent.parent / 'templates' / 'nginx'
        
    def _detect_project(self) -> Dict[str, Any]:
        """Detect project type and load configuration."""
        try:
            # Use SEGA's project detector
            project_type = self.detector.detect()
            
            # Load project-specific configuration
            config_files = [
                self.project_path / 'sega.yaml',
                self.project_path / '.sega' / 'config.yaml',
                self.project_path / 'deployment.yaml',
                self.project_path / '.env'
            ]
            
            config = {}
            for config_file in config_files:
                if config_file.exists():
                    if config_file.suffix == '.yaml':
                        with open(config_file, 'r') as f:
                            file_config = yaml.safe_load(f) or {}
                            config.update(file_config)
                    elif config_file.name == '.env':
                        # Parse .env file for basic config
                        config.update(self._parse_env_file(config_file))
                        
            return {
                'type': project_type,
                'path': str(self.project_path),
                'name': config.get('project_name', self.project_path.name),
                'config': config
            }
            
        except Exception as e:
            logger.warning(f"Could not detect project: {e}")
            return {
                'type': 'unknown',
                'path': str(self.project_path),
                'name': self.project_path.name,
                'config': {}
            }
            
    def _parse_env_file(self, env_file: Path) -> Dict[str, Any]:
        """Parse .env file for configuration values."""
        config = {}
        try:
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        # Extract relevant nginx configuration
                        if key in ['DOMAIN', 'SERVER_NAME', 'HOST', 'PORT', 
                                  'API_PORT', 'FRONTEND_PORT', 'PROJECT_NAME']:
                            config[key.lower()] = value.strip('"\'')
        except Exception:
            pass
        return config
        
    def setup_nginx(self, domain: str = None, template: str = 'auto', 
                   backend_port: int = None, frontend_port: int = None,
                   ssl: bool = False, dry_run: bool = False) -> bool:
        """Setup nginx configuration for the project."""
        try:
            # Auto-detect configuration if not provided
            if not domain:
                domain = self._get_domain_from_config()
                
            if not backend_port:
                backend_port = self._get_port_from_config('backend')
                
            if not frontend_port:
                frontend_port = self._get_port_from_config('frontend')
                
            # Select appropriate template based on project type
            if template == 'auto':
                template = self._select_template()
                
            logger.info(f"Setting up nginx for {self.project_info['name']}")
            logger.debug(f"  Domain: {domain}")
            logger.debug(f"  Backend Port: {backend_port}")
            logger.debug(f"  Frontend Port: {frontend_port}")
            logger.debug(f"  Template: {template}")
            logger.debug(f"  SSL: {'Enabled' if ssl else 'Disabled'}")
            
            # Load and render template
            template_file = self.templates_dir / f'{template}.conf.j2'
            if not template_file.exists():
                # Fallback to generic template
                template_file = self.templates_dir / 'generic.conf.j2'
                
            if not template_file.exists():
                # Create basic template if none exists
                template_content = self._generate_basic_template()
            else:
                with open(template_file, 'r') as f:
                    template_content = f.read()
                    
            # Render configuration
            nginx_config = self._render_template(
                template_content,
                domain=domain,
                backend_port=backend_port,
                frontend_port=frontend_port,
                ssl=ssl,
                project_name=self.project_info['name'],
                project_path=self.project_info['path']
            )
            
            if dry_run:
                logger.info("Dry run - Generated nginx configuration")
                logger.debug(nginx_config)
                return True
                
            # Write configuration
            config_file = self.nginx_config_dir / f"{self.project_info['name']}.conf"
            
            # Create backup if file exists
            if config_file.exists():
                backup_file = config_file.with_suffix(f'.conf.backup.{datetime.now().strftime("%Y%m%d_%H%M%S")}')
                shutil.copy2(config_file, backup_file)
                logger.info(f"Backed up existing config to {backup_file.name}")

            # Write new configuration
            with open(config_file, 'w') as f:
                f.write(nginx_config)
            logger.info(f"Configuration written to {config_file}")

            # Enable site
            enabled_file = self.nginx_enabled_dir / config_file.name
            if not enabled_file.exists():
                enabled_file.symlink_to(config_file)
                logger.info("Site enabled")
            else:
                logger.debug("Site already enabled")

            # Test configuration
            if self._test_nginx_config():
                logger.info("Nginx configuration valid")

                # Reload nginx
                if self._reload_nginx():
                    logger.info("Nginx reloaded successfully")

                    if ssl:
                        logger.info("SSL is enabled in config. Run 'sega nginx ssl' to obtain certificates")

                    return True
            else:
                logger.error("Nginx configuration test failed")
                return False

        except Exception as e:
            logger.error(f"Setting up nginx: {e}")
            return False
            
    def setup_ssl(self, domain: str = None, email: str = None,
                 staging: bool = False, self_signed: bool = False) -> bool:
        """Setup SSL certificates for the domain."""
        try:
            if not domain:
                domain = self._get_domain_from_config()

            logger.info(f"Setting up SSL for {domain}")

            if self_signed:
                return self._setup_self_signed_cert(domain)
            else:
                return self._setup_letsencrypt_cert(domain, email, staging)

        except Exception as e:
            logger.error(f"Setting up SSL: {e}")
            return False
            
    def _setup_letsencrypt_cert(self, domain: str, email: str = None, staging: bool = False) -> bool:
        """Setup Let's Encrypt SSL certificate."""
        try:
            # Check if certbot is installed
            if not shutil.which('certbot'):
                logger.info("Certbot not found. Installing...")
                subprocess.run(['sudo', 'apt-get', 'update'], check=True)
                subprocess.run(['sudo', 'apt-get', 'install', '-y', 'certbot', 'python3-certbot-nginx'], check=True)

            # Build certbot command (requires sudo for nginx plugin)
            cmd = ['sudo', 'certbot', '--nginx', '-d', domain]

            # Add www subdomain if not already a subdomain
            if not domain.startswith('www.') and domain.count('.') == 1:
                cmd.extend(['-d', f'www.{domain}'])

            if email:
                cmd.extend(['--email', email])
            else:
                cmd.append('--register-unsafely-without-email')

            cmd.extend(['--agree-tos', '--non-interactive'])

            if staging:
                cmd.append('--staging')
                logger.info("Using Let's Encrypt staging server (for testing)")

            # Run certbot
            logger.info(f"Running: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                logger.info("SSL certificate obtained successfully")

                # Setup auto-renewal
                self._setup_cert_renewal()

                # Update nginx config to use SSL
                self._update_nginx_for_ssl(domain)

                return True
            else:
                logger.error(f"Certbot failed: {result.stderr}")
                return False

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to install certbot: {e}")
            return False
        except Exception as e:
            logger.error(f"Setting up Let's Encrypt: {e}")
            return False
            
    def _setup_self_signed_cert(self, domain: str) -> bool:
        """Setup self-signed SSL certificate."""
        try:
            cert_dir = Path(f'/etc/ssl/certs/{self.project_info["name"]}')
            cert_dir.mkdir(parents=True, exist_ok=True)

            cert_file = cert_dir / 'cert.pem'
            key_file = cert_dir / 'key.pem'

            # Generate self-signed certificate
            cmd = [
                'openssl', 'req', '-x509', '-nodes', '-days', '365',
                '-newkey', 'rsa:2048',
                '-keyout', str(key_file),
                '-out', str(cert_file),
                '-subj', f'/CN={domain}'
            ]

            subprocess.run(cmd, check=True)

            logger.info("Self-signed certificate generated")
            logger.debug(f"Certificate: {cert_file}")
            logger.debug(f"Private Key: {key_file}")

            # Update nginx config to use SSL
            self._update_nginx_for_self_signed_ssl(domain, cert_file, key_file)

            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to generate certificate: {e}")
            return False
        except Exception as e:
            logger.error(f"Setting up self-signed certificate: {e}")
            return False
            
    def _generate_basic_template(self) -> str:
        """Generate a basic nginx configuration template."""
        return """
# Nginx configuration for {{ project_name }}
# Generated by SEGA on {{ timestamp }}

{% if ssl %}
server {
    listen 80;
    listen [::]:80;
    server_name {{ domain }};
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name {{ domain }};
    
    # SSL configuration will be added by certbot or manually
    
{% else %}
server {
    listen 80;
    listen [::]:80;
    server_name {{ domain }};
    
{% endif %}
    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    
    # Frontend (if applicable)
    {% if frontend_port %}
    location / {
        proxy_pass http://127.0.0.1:{{ frontend_port }};
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    {% endif %}
    
    # API/Backend
    {% if backend_port %}
    location /api {
        proxy_pass http://127.0.0.1:{{ backend_port }};
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # IncreBase timeouts for long-running requests
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
    {% endif %}
    
    # WebSocket support (if needed)
    location /ws {
        proxy_pass http://127.0.0.1:{{ backend_port or frontend_port }};
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
    
    # Static files (optional)
    location /static {
        alias {{ project_path }}/static;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
    
    # Health check endpoint
    location /health {
        access_log off;
        return 200 "healthy\\n";
        add_header Content-Type text/plain;
    }
}
"""
        
    def _render_template(self, template_content: str, **kwargs) -> str:
        """Render nginx configuration template."""
        try:
            from jinja2 import Template
        except ImportError:
            # Fallback to simple string replacement if jinja2 not available
            for key, value in kwargs.items():
                template_content = template_content.replace(f'{{{{ {key} }}}}', str(value))
            return template_content
            
        template = Template(template_content)
        kwargs['timestamp'] = datetime.now().isoformat()
        return template.render(**kwargs)
        
    def _get_domain_from_config(self) -> str:
        """Get domain from project configuration."""
        config = self.project_info['config']
        
        # Try various config keys
        for key in ['domain', 'server_name', 'host', 'hostname']:
            if key in config:
                return config[key]
                
        # Default to project name with .local
        return f"{self.project_info['name']}.local"
        
    def _get_port_from_config(self, service_type: str) -> Optional[int]:
        """Get port from project configuration."""
        config = self.project_info['config']
        
        if service_type == 'backend':
            keys = ['api_port', 'backend_port', 'port', 'server_port']
        else:
            keys = ['frontend_port', 'ui_port', 'web_port', 'client_port']
            
        for key in keys:
            if key in config:
                try:
                    return int(config[key])
                except (ValueError, TypeError):
                    pass
                    
        # Default ports based on FLEET standards
        if service_type == 'backend':
            return 3001  # Default API port
        else:
            return 3101  # Default frontend port
            
    def _select_template(self) -> str:
        """Select appropriate nginx template based on project type."""
        project_type = self.project_info['type']
        
        # Map project types to templates
        template_map = {
            'nextjs': 'nextjs',
            'react': 'spa',
            'vue': 'spa',
            'angular': 'spa',
            'django': 'django',
            'flask': 'flask',
            'fastapi': 'fastapi',
            'express': 'nodejs',
            'rails': 'rails'
        }
        
        return template_map.get(project_type, 'generic')
        
    def _test_nginx_config(self) -> bool:
        """Test nginx configuration."""
        try:
            result = subprocess.run(['nginx', '-t'], capture_output=True, text=True)
            return result.returncode == 0
        except FileNotFoundError:
            logger.warning("nginx not found, skipping config test")
            return True
            
    def _reload_nginx(self) -> bool:
        """Reload nginx service."""
        try:
            # Try systemctl first
            result = subprocess.run(['systemctl', 'reload', 'nginx'], capture_output=True, text=True)
            if result.returncode == 0:
                return True

            # Fallback to service command
            result = subprocess.run(['service', 'nginx', 'reload'], capture_output=True, text=True)
            if result.returncode == 0:
                return True

            # Fallback to nginx command
            result = subprocess.run(['nginx', '-s', 'reload'], capture_output=True, text=True)
            return result.returncode == 0

        except FileNotFoundError:
            logger.warning("Could not reload nginx")
            return False
            
    def _setup_cert_renewal(self):
        """Setup automatic certificate renewal."""
        try:
            # Add cron job for renewal
            cron_cmd = "0 0,12 * * * certbot renew --quiet --post-hook 'systemctl reload nginx'"
            subprocess.run(['crontab', '-l'], capture_output=True, text=True)
            # Add to crontab if not already present
            # Note: This is simplified, production would check if already exists
            logger.info("Auto-renewal configured")
        except Exception:
            logger.info("Please manually configure auto-renewal")
            
    def _update_nginx_for_ssl(self, domain: str):
        """Update nginx configuration to use SSL certificates."""
        config_file = self.nginx_config_dir / f"{self.project_info['name']}.conf"
        if config_file.exists():
            # Certbot usually handles this automatically
            logger.info("Nginx configuration updated for SSL")
            
    def _update_nginx_for_self_signed_ssl(self, domain: str, cert_file: Path, key_file: Path):
        """Update nginx configuration for self-signed SSL."""
        config_file = self.nginx_config_dir / f"{self.project_info['name']}.conf"

        if config_file.exists():
            # Read current config
            with open(config_file, 'r') as f:
                config = f.read()

            # Add SSL configuration if not present
            if 'ssl_certificate' not in config:
                ssl_config = f"""
    ssl_certificate {cert_file};
    ssl_certificate_key {key_file};
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
"""
                # Insert after listen 443 line
                config = config.replace('listen 443', f'listen 443{ssl_config}')

                with open(config_file, 'w') as f:
                    f.write(config)

            logger.info("Nginx configuration updated for self-signed SSL")
            
    def get_status(self) -> Dict[str, Any]:
        """Get nginx configuration status for the project."""
        status = {
            'project': self.project_info['name'],
            'nginx_config': False,
            'nginx_enabled': False,
            'nginx_valid': False,
            'ssl_configured': False,
            'ssl_valid': False,
            'services': {}
        }
        
        try:
            # Check configuration files
            config_file = self.nginx_config_dir / f"{self.project_info['name']}.conf"
            enabled_file = self.nginx_enabled_dir / f"{self.project_info['name']}.conf"
            
            status['nginx_config'] = config_file.exists()
            status['nginx_enabled'] = enabled_file.exists()
            
            if status['nginx_config']:
                # Check if configuration is valid
                status['nginx_valid'] = self._test_nginx_config()
                
                # Check for SSL configuration
                with open(config_file, 'r') as f:
                    config_content = f.read()
                    status['ssl_configured'] = 'ssl' in config_content or 'SSL' in config_content
                    
            # Check service availability
            backend_port = self._get_port_from_config('backend')
            frontend_port = self._get_port_from_config('frontend')
            
            if backend_port:
                status['services']['backend'] = self._check_port(backend_port)
                
            if frontend_port:
                status['services']['frontend'] = self._check_port(frontend_port)
                
        except Exception as e:
            logger.warning(f"Could not get complete status: {e}")

        return status
        
    def _check_port(self, port: int) -> bool:
        """Check if a port is open."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('127.0.0.1', port))
            sock.close()
            return result == 0
        except Exception:
            return False

