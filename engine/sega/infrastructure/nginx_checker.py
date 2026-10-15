#!/usr/bin/env python3
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

"""
SEGA Nginx Infrastructure Checker
==============================================================================
File: engine/sega/infrastructure/nginx_checker.py
Purpose: Comprehensive nginx and SSL validation for EC2 instances
==============================================================================

Provides automated checking of:
- Nginx service status and configuration validity
- SSL certificate presence, expiry, and coverage
- SSL block configuration (port 443 listening)
- Certbot auto-renewal configuration
- Configured domains and server blocks
- Issue detection and reporting
- FLEET SSL Standard compliance enforcement

FLEET SSL STANDARD (ENFORCED):
    SSL on origin is the FLEET standard. All production instances MUST:
    - Have SSL certificates via Let's Encrypt/certbot
    - Configure nginx to listen on port 443 with SSL
    - Use Cloudflare "Full (Strict)" mode (NOT "Flexible")
    
    This checker detects violations and reports them as CRITICAL issues.
"""

import subprocess
import json
import re
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
from datetime import datetime
from pathlib import Path


@dataclass
class SSLCertificate:
    """SSL certificate information."""

    name: str
    domains: List[str]
    expiry_date: str
    days_remaining: int
    status: str  # VALID, EXPIRING_SOON, EXPIRED


@dataclass
class NginxStatus:
    """Nginx service status."""

    service_active: bool
    config_valid: bool
    uptime: str
    last_reload: str
    error_message: Optional[str] = None


@dataclass
class CertbotStatus:
    """Certbot auto-renewal status."""

    installed: bool
    timer_active: bool
    next_renewal: Optional[str] = None


@dataclass
class InstanceCheckResult:
    """Complete check result for an instance."""

    instance_num: str
    instance_ip: str
    instance_name: str
    projects: List[str]
    nginx: NginxStatus
    ssl_certs: List[SSLCertificate]
    ssl_blocks_count: int  # Number of "listen 443" blocks in nginx config
    certbot: CertbotStatus
    domains: List[str]
    issues: List[str]


class NginxChecker:
    """Nginx infrastructure checker for EC2 instances."""

    def __init__(self, ssh_key_path: Path, ssh_options: List[str]):
        """
        Initialize nginx checker.

        Args:
            ssh_key_path: Path to SSH private key
            ssh_options: List of SSH options (e.g., ["-o", "ConnectTimeout=5"])
        """
        self.ssh_key = ssh_key_path
        self.ssh_opts = ssh_options

    def check_instance(
        self,
        instance,
        instance_num: str,
        check_ssl: bool = True,
        check_certbot: bool = True,
        check_domains: bool = True,
    ) -> InstanceCheckResult:
        """
        Run comprehensive check on an instance.

        Args:
            instance: EC2Instance object
            instance_num: Instance number (e.g., "1", "2", "3")
            check_ssl: Check SSL certificates
            check_certbot: Check certbot auto-renewal
            check_domains: Extract configured domains

        Returns:
            InstanceCheckResult with all collected data
        """
        # Initialize result
        result = InstanceCheckResult(
            instance_num=instance_num,
            instance_ip=instance.ip,
            instance_name=instance.name,
            projects=instance.projects,
            nginx=NginxStatus(False, False, "unknown", "unknown"),
            ssl_certs=[],
            ssl_blocks_count=0,
            certbot=CertbotStatus(False, False),
            domains=[],
            issues=[],
        )

        # Check nginx status
        result.nginx = self._check_nginx_status(instance)

        # Check SSL certificates
        if check_ssl:
            result.ssl_certs = self._check_ssl_certificates(instance)
            result.ssl_blocks_count = self._check_ssl_blocks(instance)

        # Check certbot
        if check_certbot:
            result.certbot = self._check_certbot_timer(instance)

        # Check domains
        if check_domains:
            result.domains = self._check_domains(instance)

        # Detect issues
        result.issues = self._detect_issues(result)

        return result

    def _run_ssh_command(self, instance, command: str) -> tuple[int, str, str]:
        """
        Execute SSH command on instance.

        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        cmd = ["ssh", "-i", str(self.ssh_key), *self.ssh_opts, instance.ssh_host, command]

        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode, result.stdout, result.stderr

    def _check_nginx_status(self, instance) -> NginxStatus:
        """Check nginx service status and configuration validity."""
        # Check service status and config test
        returncode, stdout, stderr = self._run_ssh_command(
            instance, "sudo nginx -t 2>&1 && echo '---' && sudo systemctl status nginx --no-pager"
        )

        if returncode != 0:
            return NginxStatus(
                service_active=False,
                config_valid=False,
                uptime="unknown",
                last_reload="unknown",
                error_message=stderr.strip() if stderr else "Connection failed",
            )

        # Parse output
        config_valid = "test is successful" in stdout
        service_active = "active (running)" in stdout

        # Extract uptime
        uptime = "unknown"
        uptime_match = re.search(r"Active: active \(running\) since .+?; (.+?) ago", stdout)
        if uptime_match:
            uptime = uptime_match.group(1)

        # Extract last reload
        last_reload = "unknown"
        reload_lines = [line for line in stdout.split("\n") if "Reloaded" in line or "reload" in line.lower()]
        if reload_lines:
            # Get most recent reload timestamp
            reload_match = re.search(r"(\w{3} \d{2} \d{2}:\d{2}:\d{2})", reload_lines[-1])
            if reload_match:
                last_reload = reload_match.group(1)

        return NginxStatus(
            service_active=service_active, config_valid=config_valid, uptime=uptime, last_reload=last_reload
        )

    def _check_ssl_certificates(self, instance) -> List[SSLCertificate]:
        """Check SSL certificates via certbot."""
        returncode, stdout, stderr = self._run_ssh_command(instance, "sudo certbot certificates 2>/dev/null")

        if returncode != 0 or not stdout.strip():
            return []

        # Parse certbot output
        certs = []
        current_cert = None

        for line in stdout.split("\n"):
            line = line.strip()

            # Certificate Name line
            if line.startswith("Certificate Name:"):
                if current_cert:
                    certs.append(current_cert)
                cert_name = line.split(":", 1)[1].strip()
                current_cert = {"name": cert_name, "domains": [], "expiry": "", "days": 0}

            # Domains line
            elif line.startswith("Domains:") and current_cert:
                domains_str = line.split(":", 1)[1].strip()
                current_cert["domains"] = [d.strip() for d in domains_str.split()]

            # Expiry Date line
            elif line.startswith("Expiry Date:") and current_cert:
                expiry_match = re.search(
                    r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\+\d{2}:\d{2}).*\(VALID: (\d+) days?\)", line
                )
                if expiry_match:
                    current_cert["expiry"] = expiry_match.group(1)
                    current_cert["days"] = int(expiry_match.group(2))

        # Add last cert
        if current_cert:
            certs.append(current_cert)

        # Convert to SSLCertificate objects
        ssl_certs = []
        for cert in certs:
            days = cert["days"]
            if days < 0:
                status = "EXPIRED"
            elif days < 30:
                status = "EXPIRING_SOON"
            else:
                status = "VALID"

            ssl_certs.append(
                SSLCertificate(
                    name=cert["name"],
                    domains=cert["domains"],
                    expiry_date=cert["expiry"],
                    days_remaining=days,
                    status=status,
                )
            )

        return ssl_certs

    def _check_certbot_timer(self, instance) -> CertbotStatus:
        """Check certbot auto-renewal configuration."""
        # Check if certbot is installed
        returncode, stdout, stderr = self._run_ssh_command(instance, "which certbot 2>/dev/null")

        if returncode != 0 or not stdout.strip():
            return CertbotStatus(installed=False, timer_active=False)

        # Check timer status
        returncode, stdout, stderr = self._run_ssh_command(
            instance, "sudo systemctl status certbot.timer --no-pager 2>&1"
        )

        timer_active = returncode == 0 and "active (waiting)" in stdout

        # Extract next renewal time
        next_renewal = None
        trigger_match = re.search(r"Trigger: (.+?)(?:\n|$)", stdout)
        if trigger_match:
            next_renewal = trigger_match.group(1).strip()

        return CertbotStatus(installed=True, timer_active=timer_active, next_renewal=next_renewal)

    def _check_domains(self, instance) -> List[str]:
        """Extract configured domains from nginx config."""
        returncode, stdout, stderr = self._run_ssh_command(
            instance, "sudo grep 'server_name' /etc/nginx/sites-enabled/fleet.conf 2>/dev/null"
        )

        if returncode != 0 or not stdout.strip():
            return []

        # Parse server_name lines
        domains = []
        for line in stdout.split("\n"):
            line = line.strip()
            if "server_name" in line:
                # Extract domains from "server_name domain1 domain2 domain3;"
                match = re.search(r"server_name\s+(.+?);", line)
                if match:
                    domain_list = match.group(1).strip().split()
                    domains.extend(domain_list)

        # Remove duplicates while preserving order
        seen = set()
        unique_domains = []
        for domain in domains:
            if domain not in seen:
                seen.add(domain)
                unique_domains.append(domain)

        return unique_domains

    def _check_ssl_blocks(self, instance) -> int:
        """Check for SSL blocks (listen 443) in running nginx config."""
        returncode, stdout, stderr = self._run_ssh_command(
            instance, "sudo nginx -T 2>/dev/null | grep -c 'listen.*443' || echo '0'"
        )
        
        if returncode != 0:
            return 0
        
        try:
            return int(stdout.strip())
        except ValueError:
            return 0

    def _detect_issues(self, result: InstanceCheckResult) -> List[str]:
        """
        Detect common nginx/SSL issues.
        
        Enforces FLEET SSL Standard: SSL on origin is required for all production instances.
        """
        issues = []

        # Check 1: Nginx service down
        if not result.nginx.service_active:
            issues.append("❌ CRITICAL: Nginx service not running")

        # Check 2: Invalid nginx config
        if not result.nginx.config_valid:
            issues.append("❌ CRITICAL: Nginx configuration invalid")
            if result.nginx.error_message:
                issues.append(f"   Error: {result.nginx.error_message}")

        # Check 3: FLEET SSL STANDARD - SSL on origin required
        if not result.ssl_certs:
            issues.append("❌ CRITICAL: No SSL certificates found - VIOLATES FLEET SSL STANDARD")
            issues.append("   FLEET requires SSL on origin (Cloudflare 'Flexible' mode prohibited)")
            issues.append("   Action: Run certbot to obtain certificates and configure nginx")
        else:
            # Check if certificates exist but nginx not configured to use them
            ssl_blocks = self._check_ssl_blocks_count(result)
            if ssl_blocks == 0:
                issues.append("❌ CRITICAL: SSL certificates exist but nginx not listening on port 443")
                issues.append("   Certificates found but not configured - VIOLATES FLEET SSL STANDARD")
                issues.append(f"   Action: Run 'sudo certbot install --nginx --cert-name <cert>' for each certificate")

        # Check 4: Expiring certificates (< 30 days)
        for cert in result.ssl_certs:
            if cert.status == "EXPIRED":
                issues.append(f"❌ CRITICAL: {cert.name} has EXPIRED")
            elif cert.status == "EXPIRING_SOON":
                issues.append(f"⚠️  WARNING: {cert.name} expires in {cert.days_remaining} days")

        # Check 5: Certbot not installed (but SSL certs present)
        if result.ssl_certs and not result.certbot.installed:
            issues.append("⚠️  WARNING: SSL certificates present but certbot not installed")

        # Check 6: Certbot installed but timer disabled
        if result.certbot.installed and not result.certbot.timer_active:
            issues.append("⚠️  WARNING: Certbot installed but auto-renewal timer not active")
            issues.append("   Action: sudo systemctl enable --now certbot.timer")

        return issues

    def _check_ssl_blocks_count(self, result: InstanceCheckResult) -> int:
        """Get SSL block count from stored check."""
        return result.ssl_blocks_count

    def format_results(
        self, results: List[InstanceCheckResult], format_type: str = "table", detailed: bool = False
    ) -> str:
        """
        Format results for output.

        Args:
            results: List of InstanceCheckResult objects
            format_type: Output format (table, json, markdown)
            detailed: Include detailed information

        Returns:
            Formatted string
        """
        if format_type == "json":
            return self._format_json(results)
        elif format_type == "markdown":
            return self._format_markdown(results, detailed)
        else:
            return self._format_table(results, detailed)

    def _format_json(self, results: List[InstanceCheckResult]) -> str:
        """Format as JSON."""
        data = {"timestamp": datetime.utcnow().isoformat() + "Z", "instances": []}

        for result in results:
            instance_data = {
                "instance_num": result.instance_num,
                "instance_ip": result.instance_ip,
                "instance_name": result.instance_name,
                "projects": result.projects,
                "nginx": asdict(result.nginx),
                "ssl_certificates": [asdict(cert) for cert in result.ssl_certs],
                "ssl_blocks_count": result.ssl_blocks_count,
                "ssl_standard_compliance": result.ssl_blocks_count > 0 if result.ssl_certs else False,
                "certbot": asdict(result.certbot),
                "domains": result.domains,
                "issues": result.issues,
                "status": "healthy" if not result.issues else "issues_detected",
            }
            data["instances"].append(instance_data)

        return json.dumps(data, indent=2)

    def _format_table(self, results: List[InstanceCheckResult], detailed: bool) -> str:
        """Format as table (console output)."""
        output = []

        for result in results:
            output.append("=" * 80)
            output.append(f"Instance {result.instance_num} ({result.instance_ip}) - {result.instance_name}")
            output.append(f"Projects: {', '.join(result.projects[:5])}{'...' if len(result.projects) > 5 else ''}")
            output.append("=" * 80)

            # Nginx status
            active_icon = "✅" if result.nginx.service_active else "❌"
            valid_icon = "✅" if result.nginx.config_valid else "❌"

            output.append(
                f"\nNginx Service:   {active_icon} {'Active' if result.nginx.service_active else 'Inactive'} ({result.nginx.uptime} uptime)"
            )
            output.append(f"Config Valid:    {valid_icon} {'OK' if result.nginx.config_valid else 'INVALID'}")
            output.append(f"Last Reload:     {result.nginx.last_reload}")

            # SSL certificates and blocks
            if result.ssl_certs:
                ssl_blocks_icon = "✅" if result.ssl_blocks_count > 0 else "❌"
                output.append(f"\nSSL Certificates: {len(result.ssl_certs)} certificate(s)")
                output.append(f"SSL Blocks (443): {ssl_blocks_icon} {result.ssl_blocks_count} configured")
                
                # FLEET SSL STANDARD compliance check
                if result.ssl_certs and result.ssl_blocks_count == 0:
                    output.append("  ⚠️  SSL certificates exist but nginx not configured to use them")
                    output.append("  ⚠️  VIOLATES FLEET SSL STANDARD (SSL on origin required)")
                
                for cert in result.ssl_certs[: 10 if not detailed else None]:
                    status_icon = "✅" if cert.status == "VALID" else ("⚠️ " if cert.status == "EXPIRING_SOON" else "❌")
                    output.append(
                        f"  {status_icon} {cert.name:30s} Expires: {cert.expiry_date} ({cert.days_remaining} days)"
                    )
                    if detailed and len(cert.domains) > 1:
                        output.append(f"      Domains: {', '.join(cert.domains)}")

                if len(result.ssl_certs) > 10 and not detailed:
                    output.append(f"  ... and {len(result.ssl_certs) - 10} more (use --detailed to see all)")
            else:
                output.append(f"\nSSL Certificates: ❌ None found")
                output.append("  ❌ VIOLATES FLEET SSL STANDARD (SSL on origin required)")

            # Certbot status
            if result.certbot.installed:
                timer_icon = "✅" if result.certbot.timer_active else "⚠️ "
                output.append(
                    f"\nCertbot Auto-Renewal:  {timer_icon} {'Active' if result.certbot.timer_active else 'Inactive'}"
                )
                if result.certbot.next_renewal:
                    output.append(f"  Next Check: {result.certbot.next_renewal}")
            else:
                output.append(f"\nCertbot Auto-Renewal:  ❌ Not installed")

            # Domains
            if result.domains:
                output.append(f"\nDomains Configured: {len(result.domains)} domain(s)")
                if detailed:
                    for domain in result.domains:
                        output.append(f"  • {domain}")
                else:
                    # Show first 5 domains
                    sample = result.domains[:5]
                    output.append(f"  • {', '.join(sample)}")
                    if len(result.domains) > 5:
                        output.append(f"  ... and {len(result.domains) - 5} more (use --detailed to see all)")

            # Issues
            if result.issues:
                output.append(f"\nIssues Detected: {len(result.issues)}")
                for issue in result.issues:
                    output.append(f"  {issue}")
            else:
                output.append(f"\nIssues: ✅ None")

            output.append("")

        # Summary
        output.append("=" * 80)
        output.append(f"Summary: {len(results)} instance(s) checked")
        output.append("=" * 80)

        healthy = sum(1 for r in results if not r.issues)
        issues = len(results) - healthy

        output.append(f"✅ Healthy: {healthy}")
        if issues > 0:
            output.append(f"⚠️  Issues Detected: {issues}")
            output.append("\nRecommendations:")
            for result in results:
                if result.issues:
                    if any("No SSL certificates" in issue for issue in result.issues):
                        output.append(
                            f"  • Instance {result.instance_num}: Install certbot and obtain SSL certificates"
                        )
                    if any("auto-renewal" in issue.lower() for issue in result.issues):
                        output.append(f"  • Instance {result.instance_num}: Enable certbot.timer for auto-renewal")

        return "\n".join(output)

    def _format_markdown(self, results: List[InstanceCheckResult], detailed: bool) -> str:
        """Format as markdown."""
        output = []

        output.append("# Nginx Infrastructure Check Report")
        output.append(f"\n**Generated**: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
        output.append(f"**Instances Checked**: {len(results)}\n")

        for result in results:
            output.append(f"## Instance {result.instance_num} - {result.instance_name}")
            output.append(f"\n**IP**: {result.instance_ip}")
            output.append(f"**Projects**: {', '.join(result.projects)}\n")

            # Status table
            output.append("### Nginx Status\n")
            output.append("| Component | Status | Details |")
            output.append("|-----------|--------|---------|")
            output.append(
                f"| Service | {'✅ Active' if result.nginx.service_active else '❌ Inactive'} | Uptime: {result.nginx.uptime} |"
            )
            output.append(
                f"| Configuration | {'✅ Valid' if result.nginx.config_valid else '❌ Invalid'} | Last reload: {result.nginx.last_reload} |"
            )

            # SSL certificates and compliance
            output.append("\n### SSL Certificates\n")
            if result.ssl_certs:
                output.append(f"**Total**: {len(result.ssl_certs)} certificate(s)")
                ssl_compliance = "✅ COMPLIANT" if result.ssl_blocks_count > 0 else "❌ NON-COMPLIANT"
                output.append(f"**SSL Blocks (port 443)**: {result.ssl_blocks_count} configured")
                output.append(f"**FLEET SSL Standard**: {ssl_compliance}\n")
                
                if result.ssl_blocks_count == 0:
                    output.append("⚠️ **WARNING**: SSL certificates exist but nginx not listening on port 443")
                    output.append("⚠️ **VIOLATES FLEET SSL STANDARD** - SSL on origin required\n")
                
                output.append("| Certificate | Domains | Expiry | Days Remaining | Status |")
                output.append("|-------------|---------|--------|----------------|--------|")
                for cert in result.ssl_certs:
                    status_icon = "✅" if cert.status == "VALID" else ("⚠️" if cert.status == "EXPIRING_SOON" else "❌")
                    domains_str = ", ".join(cert.domains[:3])
                    if len(cert.domains) > 3:
                        domains_str += f" (+{len(cert.domains) - 3} more)"
                    output.append(
                        f"| {cert.name} | {domains_str} | {cert.expiry_date} | {cert.days_remaining} | {status_icon} {cert.status} |"
                    )
            else:
                output.append("❌ No SSL certificates found")
                output.append("❌ **VIOLATES FLEET SSL STANDARD** - SSL on origin required\n")

            # Certbot
            output.append("\n### Certbot Auto-Renewal\n")
            if result.certbot.installed:
                output.append(f"- **Installed**: ✅ Yes")
                output.append(f"- **Timer Active**: {'✅ Yes' if result.certbot.timer_active else '⚠️ No'}")
                if result.certbot.next_renewal:
                    output.append(f"- **Next Check**: {result.certbot.next_renewal}")
            else:
                output.append("❌ Certbot not installed\n")

            # Issues
            if result.issues:
                output.append("\n### Issues\n")
                for issue in result.issues:
                    output.append(f"- {issue}")
            else:
                output.append("\n### Issues\n\n✅ No issues detected\n")

            output.append("\n---\n")

        return "\n".join(output)
