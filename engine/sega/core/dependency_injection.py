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
# SEGA MODULE - DEPENDENCY INJECTION
# ===============================================================
# File: src/sega/core/dependency_injection.py
# Purpose: Dependency injection container for SEGA platform
#
# Description: Provides a lightweight dependency injection system for managing
# service instances and factories. Supports singleton and transient lifetimes,
# decorator-based injection, and automatic dependency resolution.
#
# Dependencies:
# - External: typing, functools
# - Internal: None (core infrastructure component)
#
# Used by: All SEGA services and components requiring dependency management
#

"""Dependency injection container for SEGA platform."""

from typing import (
    Dict,
    Any,
    Type,
    TypeVar,
    Callable,
    Optional,
    Set,
    List,
    get_type_hints,
)
from functools import wraps
import inspect
import sys

T = TypeVar("T")


class ServiceContainer:
    """Simple dependency injection container."""

    _instance: Optional["ServiceContainer"] = None

    def __init__(self):
        self._services: Dict[str, Any] = {}
        self._factories: Dict[str, Callable] = {}
        self._singletons: Dict[str, Any] = {}
        self._classes: Dict[str, Type] = {}
        self._service_types: Dict[
            str, Type
        ] = {}  # Track original service types
        self._resolution_stack: Set[str] = set()

    @classmethod
    def get_instance(cls) -> "ServiceContainer":
        """Get singleton instance of the container."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(
        self, service_type: Type[T], implementation: T, singleton: bool = True
    ) -> None:
        """Register a service implementation."""
        service_name = service_type.__name__
        self._service_types[service_name] = service_type

        if singleton:
            self._singletons[service_name] = implementation
        else:
            self._services[service_name] = implementation

    def register_factory(
        self,
        service_type: Type[T],
        factory: Callable[[], T],
        singleton: bool = True,
    ) -> None:
        """Register a factory function for creating services."""
        service_name = service_type.__name__
        self._service_types[service_name] = service_type
        self._factories[service_name] = (factory, singleton)

    def get(self, service_type: Type[T]) -> T:
        """Get service instance with automatic dependency resolution."""
        service_name = service_type.__name__

        # Check for circular dependencies
        if service_name in self._resolution_stack:
            raise ValueError(
                f"Circular dependency detected: {' -> '.join(self._resolution_stack)} -> {service_name}"
            )

        # Check singletons first
        if service_name in self._singletons:
            return self._singletons[service_name]

        # Check registered services
        if service_name in self._services:
            return self._services[service_name]

        # Add to resolution stack
        self._resolution_stack.add(service_name)

        try:
            # Check factories
            if service_name in self._factories:
                factory, singleton = self._factories[service_name]
                instance = factory()

                if singleton:
                    self._singletons[service_name] = instance

                return instance

            # Check registered classes with constructor injection
            if service_name in self._classes:
                cls = self._classes[service_name]
                instance = self._instantiate_class(cls)
                return instance

            # If not registered anywhere, raise error
            raise ValueError(f"Service {service_name} not registered")

        finally:
            # Remove from resolution stack
            self._resolution_stack.discard(service_name)

    def _instantiate_class(self, cls: Type[T]) -> T:
        """Instantiate a class with automatic dependency injection."""
        # Get constructor signature for parameters and defaults
        sig = inspect.signature(cls.__init__)
        params = sig.parameters

        # Try to get type hints, which resolves forward references
        try:
            # Get the module where the class is defined
            module = sys.modules[cls.__module__]
            # Build a namespace that includes all registered classes
            namespace = dict(module.__dict__)
            # Add all registered classes to namespace to help resolve forward refs
            for reg_cls in self._classes.values():
                namespace[reg_cls.__name__] = reg_cls

            # Get type hints with the enhanced namespace
            type_hints = get_type_hints(cls.__init__, globalns=namespace)
        except NameError as e:
            # Forward reference resolution failed
            print(
                f"Warning: Forward reference resolution failed for {cls.__name__}: {e}"
            )
            type_hints = {}
            if hasattr(cls.__init__, "__annotations__"):
                for (
                    param_name,
                    annotation,
                ) in cls.__init__.__annotations__.items():
                    type_hints[param_name] = annotation
        except AttributeError as e:
            # Module or class missing expected attributes
            print(
                f"Warning: Attribute error resolving type hints for {cls.__name__}: {e}"
            )
            type_hints = {}
            if hasattr(cls.__init__, "__annotations__"):
                for (
                    param_name,
                    annotation,
                ) in cls.__init__.__annotations__.items():
                    type_hints[param_name] = annotation
        except TypeError as e:
            # Invalid type annotation format
            print(
                f"Warning: Type error in annotations for {cls.__name__}: {e}"
            )
            type_hints = {}
            if hasattr(cls.__init__, "__annotations__"):
                for (
                    param_name,
                    annotation,
                ) in cls.__init__.__annotations__.items():
                    type_hints[param_name] = annotation

        # Prepare kwargs for constructor
        kwargs = {}

        # Process each parameter
        for param_name, param in params.items():
            if param_name == "self":
                continue

            # Get type from resolved hints or raw annotation
            param_type = type_hints.get(param_name)
            if (
                param_type is None
                and param.annotation != inspect.Parameter.empty
            ):
                param_type = param.annotation

            if param_type is None:
                continue

            # Handle string annotations (forward references)
            if isinstance(param_type, str):
                # Try to find the class by name in registered classes
                found = False
                for reg_name, reg_cls in self._classes.items():
                    if reg_cls.__name__ == param_type:
                        try:
                            kwargs[param_name] = self.get(reg_cls)
                            found = True
                            break
                        except ValueError:
                            pass

                if not found and param.default == inspect.Parameter.empty:
                    raise ValueError(
                        f"Service {param_type} not registered (required by {cls.__name__})"
                    )
                continue

            # Try to resolve the dependency
            try:
                kwargs[param_name] = self.get(param_type)
            except ValueError as e:
                # Re-raise circular dependency errors
                if "Circular dependency" in str(e):
                    raise
                # If dependency not found and no default value, raise error
                if param.default == inspect.Parameter.empty:
                    type_name = getattr(
                        param_type, "__name__", str(param_type)
                    )
                    raise ValueError(
                        f"Service {type_name} not registered (required by {cls.__name__})"
                    )

        # Create instance with resolved dependencies
        return cls(**kwargs)

    def register_instance(self, service_type: Type[T], instance: T) -> None:
        """Register a specific instance."""
        service_name = service_type.__name__
        self._service_types[service_name] = service_type
        self._singletons[service_name] = instance
        self._services[service_name] = instance

    def register_singleton(
        self, service_type: Type[T], factory: Callable[[], T]
    ) -> None:
        """Register a singleton factory (alias for register_factory with singleton=True)."""
        self.register_factory(service_type, factory, singleton=True)

    def register_class(self, service_type: Type[T]) -> None:
        """Register a class for automatic instantiation with constructor injection."""
        service_name = service_type.__name__
        self._service_types[service_name] = service_type
        self._classes[service_name] = service_type

    def clear(self) -> None:
        """Clear all registrations."""
        self._services.clear()
        self._factories.clear()
        self._singletons.clear()
        self._classes.clear()
        self._service_types.clear()
        self._resolution_stack.clear()

    def has(self, service_type: Type[T]) -> bool:
        """Check if a service is registered."""
        service_name = service_type.__name__
        return (
            service_name in self._singletons
            or service_name in self._services
            or service_name in self._factories
            or service_name in self._classes
        )

    def get_all(self) -> List[Type]:
        """Get all registered service types."""
        types = []
        # Use stored service types
        for service_type in self._service_types.values():
            if service_type not in types:  # Avoid duplicates
                types.append(service_type)
        return types


# Global container instance (will be replaced with singleton after DIContainer alias)
container = None


def inject(*dependencies: Type) -> Callable:
    """Decorator for dependency injection."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get the global container instance
            cont = DIContainer.get_instance()

            # Get function signature to find parameter names
            sig = inspect.signature(func)
            params = sig.parameters

            # Inject dependencies as keyword arguments
            for dep_type in dependencies:
                # Find parameter that matches this type
                for param_name, param in params.items():
                    if (
                        param.annotation == dep_type
                        and param_name not in kwargs
                    ):
                        kwargs[param_name] = cont.get(dep_type)
                        break

            return func(*args, **kwargs)

        return wrapper

    return decorator


def setup_default_dependencies():
    """Setup default service dependencies using configuration."""
    # Register SegaConfig singleton first (core configuration)
    try:
        from sega.core.config import SegaConfig, get_config
        container.register_factory(SegaConfig, get_config, singleton=True)
    except ImportError as e:
        print(f"Warning: Failed to register SegaConfig: {e}")

    # Define service configuration
    service_config = [
        {
            "import_path": "sega.project.project_detector",
            "class_name": "ProjectDetector",
            "singleton": True,
            "factory": lambda: _import_and_create(
                "sega.project.project_detector", "ProjectDetector"
            ),
        },
        {
            "import_path": "sega.ship.deployers.deployment_router",
            "class_name": "DeploymentRouter",
            "singleton": True,
            "factory": lambda: _import_and_create(
                "sega.ship.deployers.deployment_router", "DeploymentRouter"
            ),
        },
        {
            "import_path": "sega.services.deployment_service",
            "class_name": "DeploymentService",
            "singleton": True,
            "factory": lambda: _import_and_create(
                "sega.services.deployment_service", "DeploymentService"
            ),
        },
        {
            "import_path": "sega.core.workspace_manager",
            "class_name": "WorkspaceManager",
            "singleton": True,
            "factory": lambda: _import_and_create(
                "sega.core.workspace_manager", "WorkspaceManager"
            ),
        },
    ]

    # Register services from configuration
    for service in service_config:
        try:
            cls = _get_class_from_config(service)
            container.register_factory(
                cls, service["factory"], singleton=service["singleton"]
            )
        except ImportError as e:
            print(
                f"Warning: Failed to register service {service['class_name']}: {e}"
            )


def _get_class_from_config(service_config):
    """Get class from service configuration."""
    module_path = service_config["import_path"]
    class_name = service_config["class_name"]

    # Import module dynamically
    import importlib

    module = importlib.import_module(module_path, package=__package__)
    return getattr(module, class_name)


def _import_and_create(module_path, class_name):
    """Dynamically import and create class instance."""
    import importlib

    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    return cls()


# Backward compatibility aliBases
DIContainer = ServiceContainer

# Also need to update the global container to use the singleton
container = DIContainer.get_instance()
