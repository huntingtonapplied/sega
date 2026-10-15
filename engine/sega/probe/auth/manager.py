"""
Test Authentication Manager
===========================
Manages authentication modes for SEGA API testing.

Supports three authentication modes:
1. NONE: No authentication (for public endpoints)
2. MOCK_JWT: Generate test JWTs (for backends in test mode)
3. REAL_TOKEN: Use real Auth0 tokens (from environment)
"""

import os
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional

from .jwt_generator import (
    SEGA_ADMIN_USER,
    SEGA_TEST_USER,
    TestJWTGenerator,
    TestUserConfig,
)


class AuthMode(Enum):
    """Authentication mode for API testing."""

    NONE = "none"  # No authentication
    MOCK_JWT = "mock"  # Generate test JWT (requires backend test mode)
    REAL_TOKEN = "real"  # Use real token from environment


@dataclass
class AuthConfig:
    """Authentication configuration."""

    mode: AuthMode = AuthMode.MOCK_JWT
    # For MOCK_JWT mode
    test_user: TestUserConfig = None
    jwt_secret: Optional[str] = None
    # For REAL_TOKEN mode
    token_env_var: str = "SEGA_TEST_AUTH_TOKEN"
    # Headers to include
    additional_headers: Dict[str, str] = None

    def __post_init__(self):
        if self.test_user is None:
            self.test_user = SEGA_TEST_USER
        if self.additional_headers is None:
            self.additional_headers = {}


class TestAuthManager:
    """
    Manages authentication for SEGA API testing.

    Usage:
        # Default: mock JWT mode
        auth = TestAuthManager()
        headers = auth.get_auth_headers()

        # Real token mode (from environment)
        auth = TestAuthManager(mode=AuthMode.REAL_TOKEN)
        headers = auth.get_auth_headers()

        # No authentication
        auth = TestAuthManager(mode=AuthMode.NONE)
        headers = auth.get_auth_headers()  # Returns {}

        # Admin user
        auth = TestAuthManager(user=SEGA_ADMIN_USER)
        headers = auth.get_auth_headers()
    """

    def __init__(
        self,
        mode: AuthMode = AuthMode.MOCK_JWT,
        user: Optional[TestUserConfig] = None,
        config: Optional[AuthConfig] = None,
    ):
        """
        Initialize auth manager.

        Args:
            mode: Authentication mode
            user: Test user configuration (for MOCK_JWT mode)
            config: Full auth configuration (overrides mode/user)
        """
        if config:
            self.config = config
        else:
            self.config = AuthConfig(
                mode=mode,
                test_user=user or SEGA_TEST_USER,
            )

        self._jwt_generator: Optional[TestJWTGenerator] = None
        self._cached_token: Optional[str] = None

    @property
    def jwt_generator(self) -> TestJWTGenerator:
        """Lazy-load JWT generator."""
        if self._jwt_generator is None:
            self._jwt_generator = TestJWTGenerator(
                secret=self.config.jwt_secret,
            )
        return self._jwt_generator

    def get_token(self) -> Optional[str]:
        """
        Get authentication token based on current mode.

        Returns:
            JWT token string, or None if mode is NONE
        """
        if self.config.mode == AuthMode.NONE:
            return None

        if self.config.mode == AuthMode.REAL_TOKEN:
            token = os.environ.get(self.config.token_env_var)
            if not token:
                raise ValueError(
                    f"Real token mode requires {self.config.token_env_var} "
                    "environment variable to be set"
                )
            return token

        if self.config.mode == AuthMode.MOCK_JWT:
            # Generate mock JWT
            if self._cached_token is None:
                self._cached_token = self.jwt_generator.generate(self.config.test_user)
            return self._cached_token

        raise ValueError(f"Unknown auth mode: {self.config.mode}")

    def get_auth_headers(self) -> Dict[str, str]:
        """
        Get authentication headers for API requests.

        Returns:
            Dict with Authorization header (if applicable) and any additional headers
        """
        headers = dict(self.config.additional_headers)

        token = self.get_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"

        return headers

    def refresh_token(self) -> str:
        """Force regeneration of mock token."""
        self._cached_token = None
        return self.get_token()

    def get_user_info(self) -> Dict[str, str]:
        """Get information about the current test user."""
        if self.config.mode == AuthMode.NONE:
            return {"mode": "none", "user": None}

        if self.config.mode == AuthMode.REAL_TOKEN:
            return {
                "mode": "real",
                "source": self.config.token_env_var,
                "token_set": bool(os.environ.get(self.config.token_env_var)),
            }

        return {
            "mode": "mock",
            "auth0_id": self.config.test_user.auth0_id,
            "email": self.config.test_user.email,
            "name": self.config.test_user.name,
            "is_admin": self.config.test_user.is_admin,
        }

    @classmethod
    def from_env(cls) -> "TestAuthManager":
        """
        Create auth manager from environment variables.

        Environment variables:
            SEGA_TEST_AUTH_MODE: none, mock, real (default: mock)
            SEGA_TEST_AUTH_TOKEN: Token for real mode
            SEGA_TEST_USER_EMAIL: Override test user email
            SEGA_TEST_USER_AUTH0_ID: Override test user Auth0 ID
        """
        mode_str = os.environ.get("SEGA_TEST_AUTH_MODE", "mock").lower()

        try:
            mode = AuthMode(mode_str)
        except ValueError:
            mode = AuthMode.MOCK_JWT

        # Build test user from env if specified
        user = TestUserConfig(
            auth0_id=os.environ.get("SEGA_TEST_USER_AUTH0_ID", SEGA_TEST_USER.auth0_id),
            email=os.environ.get("SEGA_TEST_USER_EMAIL", SEGA_TEST_USER.email),
            name=os.environ.get("SEGA_TEST_USER_NAME", SEGA_TEST_USER.name),
        )

        return cls(mode=mode, user=user)


# Convenience functions
def get_test_auth_headers(mode: AuthMode = AuthMode.MOCK_JWT) -> Dict[str, str]:
    """Quick function to get auth headers."""
    return TestAuthManager(mode=mode).get_auth_headers()


def get_test_token(mode: AuthMode = AuthMode.MOCK_JWT) -> Optional[str]:
    """Quick function to get auth token."""
    return TestAuthManager(mode=mode).get_token()


# Re-export for convenience
__all__ = [
    "AuthMode",
    "AuthConfig",
    "TestAuthManager",
    "TestUserConfig",
    "SEGA_TEST_USER",
    "SEGA_ADMIN_USER",
    "get_test_auth_headers",
    "get_test_token",
]
