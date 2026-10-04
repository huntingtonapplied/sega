# SEGA CLI Main
"""Main CLI entry point with command registration and logging setup."""

# Suppress cryptography deprecation warnings from paramiko
import warnings
from cryptography.utils import CryptographyDeprecationWarning

warnings.filterwarnings("ignore", category=CryptographyDeprecationWarning)

import os
import logging
import structlog
import colorlog
import click

from ..core.dependency_injection import setup_default_dependencies


def setup_standardized_logging():
    """Configure standardized logging for SEGA CLI operations."""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    is_production = os.getenv("ENVIRONMENT", "development") == "production"

    if is_production:
        # Production: Structured JSON logging
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.JSONRenderer(),
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )

        logging.basicConfig(
            level=getattr(logging, log_level, logging.INFO),
            format="%(message)s",
        )
    else:
        # Development: Colored terminal output
        handler = colorlog.StreamHandler()
        handler.setFormatter(
            colorlog.ColoredFormatter(
                "%(log_color)s%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
                log_colors={
                    "DEBUG": "cyan",
                    "INFO": "green",
                    "WARNING": "yellow",
                    "ERROR": "red",
                    "CRITICAL": "red,bg_white",
                },
            )
        )

        logging.basicConfig(
            level=getattr(logging, log_level, logging.INFO),
            handlers=[handler],
        )

    # Configure root logger
    logger = logging.getLogger("sega")
    logger.debug(f"SEGA logging initialized - level: {log_level}, production: {is_production}")


@click.group()
@click.version_option(version="0.1.0", package_name="sega")
def cli():
    """SEGA - Unified CI/CD platform for multi-domain projects."""
    # Configure standardized logging
    setup_standardized_logging()

    # Setup dependency injection on CLI startup
    setup_default_dependencies()


@cli.command()
@click.argument("shell", type=click.Choice(["bash", "zsh", "fish"]), required=False)
def completion(shell):
    """Show how to enable shell tab-completion for `sega`.

    Example: `sega completion zsh` then follow the printed one-liner.
    """
    shell = shell or "zsh"
    src = {"bash": "bash_source", "zsh": "zsh_source", "fish": "fish_source"}[shell]
    rc = {"bash": "~/.bashrc", "zsh": "~/.zshrc", "fish": "~/.config/fish/completions/sega.fish"}[shell]
    click.echo(f"# Enable `sega` tab-completion for {shell}:")
    if shell == "fish":
        click.echo(f'_SEGA_COMPLETE={src} sega > {rc}')
    else:
        click.echo(f'echo \'eval "$(_SEGA_COMPLETE={src} sega)"\' >> {rc}')
        click.echo(f"# then restart your shell (or: source {rc})")


def register_commands():
    """Register all CLI commands."""
    from .commands import (
        # Core utilities
        logs,
        init,
        detect,
        infrastructure,
        workspace,
        project,
        monitor,
        api,
        grpc,
        fleet,
        local,
        program,
        flash,
        unified_server,
        nginx,
        frontend,
        ledger,
        # Consolidated command groups
        doctor,
        forge,
        ship,
        probe,
        # Additional commands
        install,
        secrets,
        social,
        sysmon,
        sysnc,
        validate,
        health,
        # Standalone commands (also available under forge)
        standalone,
        # Shared infrastructure commands
        prepare,
        # Desktop binary and downloads infrastructure
        binaries,
        downloads,
        # Neural-net weight distribution (downloads.<domain>/models/)
        models,
        # Cross-project simulation-data extraction -> published data package (IDP)
        data,
        # Instance systemd service management
        services,
        # Desktop application build/package/sign/deploy
        desktop,
    )

    # Core utilities
    cli.add_command(logs.logs)
    cli.add_command(init.init)
    cli.add_command(detect.detect)
    cli.add_command(infrastructure.infrastructure)
    cli.add_command(workspace.workspace)
    cli.add_command(project.project)
    cli.add_command(monitor.monitor)
    cli.add_command(api.api)
    cli.add_command(grpc.grpc)
    cli.add_command(fleet.fleet)
    cli.add_command(local.local)
    cli.add_command(program.program)
    cli.add_command(flash.flash)
    cli.add_command(unified_server.unified_server)
    cli.add_command(nginx.nginx)
    cli.add_command(frontend.frontend)
    cli.add_command(ledger.ledger)

    # Additional commands
    cli.add_command(install.install)
    cli.add_command(secrets.secrets)
    cli.add_command(social.social)
    cli.add_command(sysmon.sysmon)
    cli.add_command(sysnc.sysnc)
    cli.add_command(validate.validate)
    cli.add_command(health.health)

    # Private plug-in: engine license-key minting (requires the private signing
    # backend). Excluded from the open-source snapshot; registers only when the
    # module is present.
    try:
        from sega.cli.commands import license
        cli.add_command(license.license)
    except ImportError:
        pass

    # Consolidated command groups
    cli.add_command(doctor.doctor)
    cli.add_command(forge.forge)
    cli.add_command(ship.ship)
    cli.add_command(probe.probe)

    # Add shared infrastructure commands
    cli.add_command(prepare.prepare)

    # Desktop binary and downloads infrastructure
    cli.add_command(binaries.binaries)
    cli.add_command(downloads.downloads)
    cli.add_command(models.models)
    cli.add_command(data.data)

    # Instance systemd service management
    cli.add_command(services.services)

    # Desktop application build/package/sign/deploy
    cli.add_command(desktop.desktop)


# Register commands on module load
register_commands()
