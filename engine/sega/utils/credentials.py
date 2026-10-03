#!/usr/bin/env python
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

# ===============================================================
# SEGA MODULE - Credentials Resolver
# ===============================================================
# File: engine/sega/utils/credentials.py
# Purpose: Entity-aware credential resolution for deployment platforms
#
# Description: Resolves API credentials for deployment platforms from 
# environment variables. Supports entity-specific overrides where tokens
# can be suffixed with entity name (e.g., VERCEL_TOKEN_LAMAR).
#
# Dependencies:
# - External: os
# - Internal: None
#
# Used by: All platform deployers (Vercel, Firebase, Supabase, Render, etc.)
#

"""Entity-aware credentials resolver for SEGA deployment platforms."""

import os
from typing import Dict, Any, Optional
from dataclasses import dataclass


# Entity to credential suffix mapping, from the `[credentials.entity_suffixes]`
# config table (operator data; ships empty for new installs).
def _entity_suffixes() -> Dict[str, str]:
    from sega.core.config import get_config
    return dict(get_config().credentials.entity_suffixes)


ENTITY_SUFFIXES = _entity_suffixes()


@dataclass
class PlatformCredentials:
    """Credentials for a deployment platform."""
    platform: str
    entity: Optional[str] = None
    token: Optional[str] = None
    api_key: Optional[str] = None
    org_id: Optional[str] = None
    project_id: Optional[str] = None
    extra: Dict[str, str] = None
    
    def __post_init__(self):
        if self.extra is None:
            self.extra = {}
    
    @property
    def is_valid(self) -> bool:
        """Check if credentials are sufficient."""
        return bool(self.token or self.api_key)


class CredentialsResolver:
    """
    Resolves credentials for deployment platforms with entity-specific overrides.
    
    Lookup order:
    1. Entity-specific: VERCEL_TOKEN_LAMAR
    2. Generic: VERCEL_TOKEN
    
    Environment variable mapping:
    - Vercel: VERCEL_TOKEN, VERCEL_ORG_ID, VERCEL_PROJECT_ID
    - Supabase: SUPABASE_ACCESS_TOKEN, SUPABASE_DB_PASSWORD
    - Render: RENDER_API_KEY
    - Firebase: FIREBASE_TOKEN, GOOGLE_APPLICATION_CREDENTIALS
    - GitHub: GITHUB_TOKEN
    - Cloudflare: CLOUDFLARE_TOKEN
    """
    
    # Platform to environment variable mapping
    PLATFORM_ENV_VARS = {
        "vercel": {
            "token": "VERCEL_TOKEN",
            "org_id": "VERCEL_ORG_ID",
            "project_id": "VERCEL_PROJECT_ID",
        },
        "supabase": {
            "token": "SUPABASE_ACCESS_TOKEN",
            "db_password": "SUPABASE_DB_PASSWORD",
        },
        "render": {
            "api_key": "RENDER_API_KEY",
        },
        "firebase": {
            "token": "FIREBASE_TOKEN",
            "service_account": "GOOGLE_APPLICATION_CREDENTIALS",
            "project_id": "FIREBASE_PROJECT_ID",
        },
        "github": {
            "token": "GITHUB_TOKEN",
        },
        "cloudflare": {
            "token": "CLOUDFLARE_TOKEN",
        },
        "amplify": {
            "access_key": "AWS_ACCESS_KEY_ID",
            "secret_key": "AWS_SECRET_ACCESS_KEY",
            "region": "AWS_DEFAULT_REGION",
        },
    }
    
    def __init__(self):
        self._cache: Dict[str, PlatformCredentials] = {}
    
    def get_credentials(
        self, 
        platform: str, 
        entity: Optional[str] = None
    ) -> PlatformCredentials:
        """
        Get credentials for a platform, optionally scoped to an entity.
        
        Args:
            platform: Platform name (vercel, supabase, render, firebase, etc.)
            entity: Optional entity name for entity-specific credentials
            
        Returns:
            PlatformCredentials instance
        """
        cache_key = f"{platform}:{entity or 'default'}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        creds = self._resolve_credentials(platform, entity)
        self._cache[cache_key] = creds
        return creds
    
    def _resolve_credentials(
        self, 
        platform: str, 
        entity: Optional[str]
    ) -> PlatformCredentials:
        """Resolve credentials from environment variables."""
        env_vars = self.PLATFORM_ENV_VARS.get(platform, {})
        entity_suffix = ENTITY_SUFFIXES.get(entity, "") if entity else ""
        
        def get_env(key: str) -> Optional[str]:
            """Get env var, trying entity-specific first."""
            env_name = env_vars.get(key)
            if not env_name:
                return None
            
            # Try entity-specific first
            if entity_suffix:
                value = os.environ.get(f"{env_name}_{entity_suffix}")
                if value:
                    return value
            
            # Fall back to generic
            return os.environ.get(env_name)
        
        extra = {}
        
        if platform == "vercel":
            return PlatformCredentials(
                platform=platform,
                entity=entity,
                token=get_env("token"),
                org_id=get_env("org_id"),
                project_id=get_env("project_id"),
            )
        
        elif platform == "supabase":
            extra["db_password"] = get_env("db_password") or ""
            return PlatformCredentials(
                platform=platform,
                entity=entity,
                token=get_env("token"),
                extra=extra,
            )
        
        elif platform == "render":
            return PlatformCredentials(
                platform=platform,
                entity=entity,
                api_key=get_env("api_key"),
            )
        
        elif platform == "firebase":
            extra["service_account"] = get_env("service_account") or ""
            return PlatformCredentials(
                platform=platform,
                entity=entity,
                token=get_env("token"),
                project_id=get_env("project_id"),
                extra=extra,
            )
        
        elif platform == "github":
            return PlatformCredentials(
                platform=platform,
                entity=entity,
                token=get_env("token"),
            )
        
        elif platform == "cloudflare":
            return PlatformCredentials(
                platform=platform,
                entity=entity,
                token=get_env("token"),
            )
        
        elif platform == "amplify":
            extra["access_key"] = get_env("access_key") or ""
            extra["secret_key"] = get_env("secret_key") or ""
            extra["region"] = get_env("region") or "us-east-1"
            return PlatformCredentials(
                platform=platform,
                entity=entity,
                extra=extra,
            )
        
        return PlatformCredentials(platform=platform, entity=entity)
    
    def clear_cache(self):
        """Clear the credentials cache."""
        self._cache.clear()


# Singleton instance
_credentials_resolver: Optional[CredentialsResolver] = None


def get_credentials_resolver() -> CredentialsResolver:
    """Get the singleton credentials resolver."""
    global _credentials_resolver
    if _credentials_resolver is None:
        _credentials_resolver = CredentialsResolver()
    return _credentials_resolver


def get_platform_token(platform: str, entity: Optional[str] = None) -> Optional[str]:
    """Convenience function to get a platform token."""
    resolver = get_credentials_resolver()
    creds = resolver.get_credentials(platform, entity)
    return creds.token or creds.api_key
