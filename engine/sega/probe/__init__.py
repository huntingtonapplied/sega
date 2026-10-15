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
SEGA Probe Module
=====================================================
File: engine/sega/probe/__init__.py
Purpose: Package initialization for testing framework modules
Dependencies: None
Authors: FLEET Development Team
Copyright: 2022-2026 Huntington Applied
License: Apache-2.0
Last Modified: 2025-12-15
"""

# OpenAPI Discovery
from .openapi import (
    DiscoveredAPI,
    HttpMethod,
    OpenAPIDiscoverer,
    OpenAPIEndpoint,
    OpenAPIParameter,
    OpenAPISchema,
    OpenAPISchemaParser,
    print_discovery_results,
)

# Test Chaining
from .chaining import (
    COMMON_EXTRACTORS,
    ChainedTestRunner,
    ChainResult,
    SampleDataGenerator,
    StepResult,
    TestChain,
    TestChainBuilder,
    TestContext,
    TestStep,
    ValueExtractor,
    create_id_extractor,
    print_chain_results,
    print_chains,
)

# Test Authentication
from .auth import (
    AuthMode,
    TestAuthManager,
    TestJWTGenerator,
    TestUserConfig,
)

__all__ = [
    # OpenAPI Discovery
    "OpenAPIDiscoverer",
    "OpenAPISchemaParser",
    "DiscoveredAPI",
    "OpenAPIEndpoint",
    "OpenAPIParameter",
    "OpenAPISchema",
    "HttpMethod",
    "print_discovery_results",
    # Test Chaining
    "TestChainBuilder",
    "TestChain",
    "TestStep",
    "ChainedTestRunner",
    "ChainResult",
    "StepResult",
    "ValueExtractor",
    "TestContext",
    "COMMON_EXTRACTORS",
    "create_id_extractor",
    "SampleDataGenerator",
    "print_chains",
    "print_chain_results",
    # Test Authentication
    "AuthMode",
    "TestAuthManager",
    "TestJWTGenerator",
    "TestUserConfig",
]
