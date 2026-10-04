"""
SEGA Sign Command

Signs binaries and packages for distribution using:
- macOS: codesign + notarization
- Windows: signtool or osslsigncode
- Linux: GPG signatures

Configuration is read from config/sega.toml.

Usage:
    sega sign <path> --platform <mac|windows|linux>
    sega sign <directory> --all
"""

import logging
import os
import platform as plt
from pathlib import Path
from typing import Optional

import click

from ...core.config import get_config, SegaConfig
from ...forge.signing import MacSigner, WindowsSigner, LinuxSigner
from ...forge.signing.mac import MacSigningConfig
from ...forge.signing.windows import WindowsSigningConfig
from ...forge.signing.linux import LinuxSigningConfig

logger = logging.getLogger(__name__)


def _detect_platform(target: Path) -> str:
    """Auto-detect signing platform based on file type and current OS."""
    suffix = target.suffix.lower()
    name = target.name.lower()

    # macOS indicators
    if suffix in [".app", ".dmg", ".pkg"]:
        return "mac"

    # Windows indicators
    if suffix in [".exe", ".dll", ".msi", ".msix"]:
        return "windows"

    # Linux indicators
    if suffix in [".deb", ".rpm", ".appimage", ".tar.gz", ".tar.xz"]:
        return "linux"
    if name.endswith(".tar.gz") or name.endswith(".tar.xz"):
        return "linux"

    # Fall back to current OS
    system = plt.system().lower()
    if system == "darwin":
        return "mac"
    elif system == "windows":
        return "windows"
    else:
        return "linux"


def _handle_mac(
    target: Path,
    config: SegaConfig,
    identity: Optional[str],
    notarize: bool,
    output_dir: Optional[Path],
    dry_run: bool,
    verify: bool,
) -> dict:
    """Handle macOS signing using TOML config."""
    signing_env = config.signing.mac

    # Get identity from env or arg
    resolved_identity = identity
    if not resolved_identity:
        resolved_identity = os.environ.get(signing_env.identity_env)

    mac_config = MacSigningConfig(
        identity=resolved_identity or "",
        notarize=notarize,
        apple_id=os.environ.get(signing_env.apple_id_env, ""),
        app_specific_password=os.environ.get(signing_env.apple_password_env, ""),
        team_id=os.environ.get(signing_env.team_id_env, ""),
    )

    signer = MacSigner(mac_config)

    if not signer.is_available():
        return {
            "success": False,
            "error": "codesign not available (not on macOS?)",
        }

    click.echo(f"Identity: {resolved_identity or '(not set)'}")
    click.echo(f"Notarize: {notarize}")

    if verify:
        result = signer.verify(target)
        return {
            "success": result.success,
            "error": result.error_message,
            "output": result.stdout,
        }

    if mac_config.notarize:
        result = signer.sign_and_notarize(target, dry_run=dry_run)
    else:
        result = signer.sign(target, dry_run=dry_run)

    return {
        "success": result.success,
        "output": str(result.signed_path) if result.signed_path else None,
        "error": result.error_message,
        "command": result.command,
        "notarization_status": result.notarization_status,
    }


def _handle_windows(
    target: Path,
    config: SegaConfig,
    certificate: Optional[str],
    output_dir: Optional[Path],
    dry_run: bool,
    verify: bool,
) -> dict:
    """Handle Windows signing using TOML config."""
    signing_env = config.signing.win

    # Get certificate from env or arg
    cert_path = certificate
    if not cert_path:
        cert_path = os.environ.get(signing_env.cert_path_env)

    win_config = WindowsSigningConfig(
        certificate_path=cert_path or "",
        certificate_password=os.environ.get(signing_env.cert_password_env, ""),
    )

    signer = WindowsSigner(win_config)

    if not signer.is_available():
        return {
            "success": False,
            "error": "No signing tool available. Install signtool (Windows SDK) or osslsigncode.",
        }

    click.echo(f"Certificate: {cert_path or '(not set)'}")

    if verify:
        result = signer.verify(target)
        return {
            "success": result.success,
            "error": result.error_message,
            "output": result.stdout,
        }

    output_path = None
    if output_dir:
        output_path = output_dir / target.name

    result = signer.sign(target, output_path, dry_run=dry_run)

    return {
        "success": result.success,
        "output": str(result.signed_path) if result.signed_path else None,
        "error": result.error_message,
        "command": result.command,
    }


def _handle_linux(
    target: Path,
    config: SegaConfig,
    key_id: Optional[str],
    output_dir: Optional[Path],
    dry_run: bool,
    verify: bool,
) -> dict:
    """Handle Linux GPG signing using TOML config."""
    signing_env = config.signing.linux

    # Get key from env or arg
    resolved_key_id = key_id
    if not resolved_key_id:
        resolved_key_id = os.environ.get(signing_env.gpg_key_env)

    linux_config = LinuxSigningConfig(
        key_id=resolved_key_id or "",
        passphrase=os.environ.get(signing_env.gpg_passphrase_env, ""),
    )

    signer = LinuxSigner(linux_config)

    if not signer.is_available():
        return {
            "success": False,
            "error": "GPG not available. Install gnupg.",
        }

    click.echo(f"Key ID: {resolved_key_id or '(not set)'}")

    if verify:
        result = signer.verify(target)
        return {
            "success": result.success,
            "error": result.error_message,
            "output": result.stdout,
        }

    # Directory signing
    if target.is_dir():
        click.echo("Signing all files in directory...")
        results = signer.sign_directory(target, dry_run=dry_run)

        success_count = sum(1 for r in results.values() if r.success)
        total = len(results)

        if success_count == total:
            return {
                "success": True,
                "output": f"Signed {success_count}/{total} files",
                "signature": [str(r.signature_path) for r in results.values() if r.signature_path],
            }
        else:
            errors = [f"{p}: {r.error_message}" for p, r in results.items() if not r.success]
            return {
                "success": False,
                "error": "; ".join(errors),
            }

    # Single file signing
    output_path = None
    if output_dir:
        if linux_config.armor:
            output_path = output_dir / f"{target.name}.asc"
        else:
            output_path = output_dir / f"{target.name}.sig"

    result = signer.sign(target, output_path, dry_run=dry_run)

    # Also create checksums
    if result.success and not dry_run:
        click.echo("Creating checksums...")
        checksum_file = signer.write_checksum_file(target)
        if checksum_file:
            click.echo(f"Checksum file: {checksum_file}")

    return {
        "success": result.success,
        "output": str(target),
        "signature": str(result.signature_path) if result.signature_path else None,
        "error": result.error_message,
        "command": result.command,
    }


@click.command()
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "--platform", "-p",
    type=click.Choice(["mac", "windows", "linux", "auto"]),
    default="auto",
    help="Signing platform",
)
@click.option("--identity", "-i", default=None, help="Signing identity (macOS) or certificate (Windows)")
@click.option("--notarize", is_flag=True, help="Notarize after signing (macOS only)")
@click.option("--key-id", default=None, help="GPG key ID (Linux only)")
@click.option("--output", "-o", type=click.Path(), default=None, help="Output directory")
@click.option("--dry-run", is_flag=True, help="Show commands without executing")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.option("--verify", is_flag=True, help="Verify signature instead of signing")
def sign(
    path: str,
    platform: str,
    identity: Optional[str],
    notarize: bool,
    key_id: Optional[str],
    output: Optional[str],
    dry_run: bool,
    verbose: bool,
    verify: bool,
):
    """
    Sign binaries and packages for distribution.

    Configuration is read from config/sega.toml.

    Examples:
        sega sign dist/MyApp.app --platform mac
        sega sign dist/MyApp.app --platform mac --notarize
        sega sign dist/MyApp.exe --platform windows
        sega sign dist/myapp.tar.gz --platform linux
        sega sign dist/MyApp.exe --verify
    """
    if verbose:
        logging.basicConfig(level=logging.DEBUG)

    # Load central TOML config
    config = get_config()

    target = Path(path)

    # Auto-detect platform
    if platform == "auto":
        platform = _detect_platform(target)
        click.echo(f"Auto-detected platform: {platform}")

    click.echo(f"Config: {config.meta.config_path}")
    click.echo(f"Target: {target}")
    click.echo(f"Platform: {platform}")
    click.echo(f"Mode: {'Verify' if verify else 'Sign'}")

    output_dir = Path(output) if output else None

    if platform == "mac":
        result = _handle_mac(target, config, identity, notarize, output_dir, dry_run, verify)
    elif platform == "windows":
        result = _handle_windows(target, config, identity, output_dir, dry_run, verify)
    elif platform == "linux":
        result = _handle_linux(target, config, key_id, output_dir, dry_run, verify)
    else:
        click.secho(f"Unsupported platform: {platform}", fg="red")
        raise SystemExit(1)

    # Display results
    click.echo(f"\n{'='*60}")
    if verify:
        click.echo("Verification Result")
    else:
        click.echo("Signing Result")
    click.echo("="*60)

    if result.get("success"):
        click.secho("SUCCESS", fg="green")
        if result.get("output"):
            click.echo(f"Output: {result['output']}")
        if result.get("signature"):
            click.echo(f"Signature: {result['signature']}")
        if result.get("notarization_status"):
            click.echo(f"Notarization: {result['notarization_status']}")
    else:
        click.secho("FAILED", fg="red")
        if result.get("error"):
            click.echo(f"Error: {result['error']}")
        raise SystemExit(1)


@click.command("sign-list")
@click.option("--platform", "-p", type=click.Choice(["mac", "windows", "linux"]), default=None)
def sign_list(platform: Optional[str]):
    """
    List available signing identities/keys.

    Examples:
        sega sign-list
        sega sign-list --platform mac
    """
    if platform is None:
        system = plt.system().lower()
        if system == "darwin":
            platform = "mac"
        elif system == "windows":
            platform = "windows"
        else:
            platform = "linux"

    click.echo(f"Available signing identities ({platform}):\n")

    if platform == "mac":
        signer = MacSigner()
        identities = signer.list_identities()
        if identities:
            for i, identity in enumerate(identities, 1):
                click.echo(f"  {i}. {identity}")
        else:
            click.echo("  No signing identities found")

    elif platform == "windows":
        signer = WindowsSigner()
        if signer.signtool_path:
            click.echo(f"  signtool: {signer.signtool_path}")
        if signer.osslsigncode_path:
            click.echo(f"  osslsigncode: {signer.osslsigncode_path}")
        click.echo("\n  Use --identity with certificate path (.pfx/.p12) or thumbprint")

    elif platform == "linux":
        signer = LinuxSigner()
        version = signer.get_version()
        if version:
            click.echo(f"  {version}\n")
        keys = signer.list_keys()
        if keys:
            for key in keys:
                click.echo(f"  {key['id']}")
                if key.get("uid"):
                    click.echo(f"    {key['uid']}")
        else:
            click.echo("  No GPG keys found")
