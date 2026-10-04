# SEGA Entry Point
"""Slim entry point that delegates to cli.main."""

from .cli.main import cli

if __name__ == "__main__":
    cli()
