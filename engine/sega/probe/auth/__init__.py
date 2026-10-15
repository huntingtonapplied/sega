"""
SEGA Test Authentication Module
===============================
Provides authentication support for automated API testing.

This module enables testing of protected endpoints by:
1. Generating test JWTs that match seed data users
2. Managing auth modes (bypass, mock token, real token)
3. Providing standard test user configuration

Usage:
    from sega.testing.auth import TestAuthManager, AuthMode

    # Create auth manager
    auth = TestAuthManager(mode=AuthMode.MOCK_JWT)

    # Get headers for API calls
    headers = auth.get_auth_headers()

    # Use with ChainedTestRunner
    runner = ChainedTestRunner(auth_token=auth.get_token())
"""

from .manager import AuthMode, TestAuthManager, TestUserConfig
from .jwt_generator import TestJWTGenerator

__all__ = [
    "AuthMode",
    "TestAuthManager",
    "TestUserConfig",
    "TestJWTGenerator",
]
