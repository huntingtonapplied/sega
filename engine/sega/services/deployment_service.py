#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2025 SEGA
#
# DEPRECATED: This module has moved to sega.ship.service
# This file exists for backward compatibility only.
# Please update imports to: from sega.ship.service import DeploymentService

"""
Backward compatibility shim for deployment_service.

The DeploymentService has moved to sega.ship.service.
This file re-exports for backward compatibility.
"""

# Re-export from new location
from ..ship.service import DeploymentService, deployment_service

__all__ = ['DeploymentService', 'deployment_service']
