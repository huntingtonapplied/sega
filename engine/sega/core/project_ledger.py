#!/usr/bin/env python3
# Copyright 2025 SEGA
#
# DEPRECATED: This module has moved to sega.project.ledger
# This file exists for backward compatibility only.
# Please update imports to: from sega.project.ledger import ProjectLedger

"""
Backward compatibility shim for project_ledger.

The ProjectLedger has moved to sega.project.ledger.
This file re-exports for backward compatibility.
"""

# Re-export from new location
from ..project.ledger import (
    ProjectReservation,
    ProjectLedger,
    acquire_project,
    release_project,
    is_project_available,
)

__all__ = [
    'ProjectReservation',
    'ProjectLedger',
    'acquire_project',
    'release_project',
    'is_project_available',
]
