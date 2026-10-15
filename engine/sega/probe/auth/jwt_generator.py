"""
Test JWT Generator
==================
Generates JWT tokens for testing authenticated endpoints.

These tokens are designed to work with backends running in test mode,
where they accept tokens signed with a known test secret rather than
requiring Auth0 verification.
"""

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class TestUserConfig:
    """Configuration for a test user."""

    auth0_id: str = "auth0|sega-test-000"
    email: str = "sega-test@fleet.local"
    name: str = "SEGA Test User"
    nickname: str = "sega-test"
    # Database ID (if known) - used for user provisioning
    db_id: Optional[int] = 1
    # Role information
    role: str = "user"
    is_admin: bool = False

    def to_jwt_claims(self) -> Dict[str, Any]:
        """Convert to JWT claims payload."""
        return {
            "sub": self.auth0_id,
            "email": self.email,
            "email_verified": True,
            "name": self.name,
            "nickname": self.nickname,
            "picture": f"https://ui-avatars.com/api/?name={self.name.replace(' ', '+')}",
        }


# Standard test users for different scenarios
SEGA_TEST_USER = TestUserConfig(
    auth0_id="auth0|sega-test-000",
    email="sega-test@fleet.local",
    name="SEGA Test User",
    nickname="sega-test",
    db_id=1,
    role="user",
    is_admin=False,
)

SEGA_ADMIN_USER = TestUserConfig(
    auth0_id="auth0|sega-admin-000",
    email="sega-admin@fleet.local",
    name="SEGA Admin User",
    nickname="sega-admin",
    db_id=2,
    role="admin",
    is_admin=True,
)


class TestJWTGenerator:
    """
    Generates JWT tokens for test purposes.

    These tokens are signed with a test secret and are intended
    to be used with backends running in SEGA_TEST_MODE=true,
    where they bypass Auth0 verification.
    """

    # Default test secret - backends should check for this in test mode
    DEFAULT_TEST_SECRET = "sega-test-secret-do-not-use-in-production"

    # Test issuer that backends should accept in test mode
    TEST_ISSUER = "https://sega-test.fleet.local/"

    # Test audience
    TEST_AUDIENCE = "sega-test-api"

    def __init__(
        self,
        secret: Optional[str] = None,
        issuer: Optional[str] = None,
        audience: Optional[str] = None,
        token_lifetime: int = 3600,
    ):
        """
        Initialize JWT generator.

        Args:
            secret: Signing secret (defaults to test secret)
            issuer: Token issuer (defaults to test issuer)
            audience: Token audience (defaults to test audience)
            token_lifetime: Token validity in seconds (default 1 hour)
        """
        self.secret = secret or self.DEFAULT_TEST_SECRET
        self.issuer = issuer or self.TEST_ISSUER
        self.audience = audience or self.TEST_AUDIENCE
        self.token_lifetime = token_lifetime

    def generate(self, user: Optional[TestUserConfig] = None) -> str:
        """
        Generate a JWT token for the given user.

        Args:
            user: Test user configuration (defaults to SEGA_TEST_USER)

        Returns:
            JWT token string
        """
        user = user or SEGA_TEST_USER
        now = int(time.time())

        # Build header
        header = {
            "alg": "HS256",
            "typ": "JWT",
        }

        # Build payload with user claims
        payload = {
            **user.to_jwt_claims(),
            "iss": self.issuer,
            "aud": self.audience,
            "iat": now,
            "exp": now + self.token_lifetime,
        }

        # Encode and sign
        return self._encode_jwt(header, payload)

    def generate_expired(self, user: Optional[TestUserConfig] = None) -> str:
        """Generate an expired token for testing token expiration handling."""
        user = user or SEGA_TEST_USER
        now = int(time.time())

        header = {"alg": "HS256", "typ": "JWT"}
        payload = {
            **user.to_jwt_claims(),
            "iss": self.issuer,
            "aud": self.audience,
            "iat": now - 7200,  # 2 hours ago
            "exp": now - 3600,  # Expired 1 hour ago
        }

        return self._encode_jwt(header, payload)

    def generate_invalid_signature(self, user: Optional[TestUserConfig] = None) -> str:
        """Generate a token with invalid signature for testing."""
        user = user or SEGA_TEST_USER
        now = int(time.time())

        header = {"alg": "HS256", "typ": "JWT"}
        payload = {
            **user.to_jwt_claims(),
            "iss": self.issuer,
            "aud": self.audience,
            "iat": now,
            "exp": now + self.token_lifetime,
        }

        # Sign with wrong secret
        return self._encode_jwt(header, payload, secret="wrong-secret")

    def _encode_jwt(
        self,
        header: Dict[str, Any],
        payload: Dict[str, Any],
        secret: Optional[str] = None,
    ) -> str:
        """Encode header and payload into a JWT."""
        secret = secret or self.secret

        # Base64url encode header and payload
        header_b64 = self._base64url_encode(json.dumps(header, separators=(",", ":")))
        payload_b64 = self._base64url_encode(json.dumps(payload, separators=(",", ":")))

        # Create signature
        message = f"{header_b64}.{payload_b64}"
        signature = hmac.new(
            secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        signature_b64 = self._base64url_encode_bytes(signature)

        return f"{header_b64}.{payload_b64}.{signature_b64}"

    @staticmethod
    def _base64url_encode(data: str) -> str:
        """Base64url encode a string."""
        return base64.urlsafe_b64encode(data.encode("utf-8")).rstrip(b"=").decode("utf-8")

    @staticmethod
    def _base64url_encode_bytes(data: bytes) -> str:
        """Base64url encode bytes."""
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")
