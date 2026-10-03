"""Regression tests for the config-driven deployment topology.

Guards the open-source refactor that replaced the hardcoded 2-value
``DeploymentTarget`` enum (``PROD_01``/``PROD_02`` = ``fleet-prod-01``/``fleet-prod-02``)
with plain-string targets resolved against the config-driven ``instances`` map.
These are hermetic unit tests — they build config objects in memory and need no
sega.toml, no filesystem, and no third-party deploy dependencies.
"""

from sega.core.config.loader import _parse_deployment_target
from sega.core.config.schema import (
    DeploymentTarget,
    InstanceConfig,
    ProjectConfig,
    SegaConfig,
)


def test_deployment_target_has_no_hardcoded_instances():
    # Plain-constants class now; the old FLEET-specific enum values are gone.
    assert not hasattr(DeploymentTarget, "PROD_01")
    assert not hasattr(DeploymentTarget, "PROD_02")
    assert DeploymentTarget.LOCAL == "local"
    assert DeploymentTarget.NOT_SERVED == "not_served"
    assert DeploymentTarget.RESERVED == frozenset({"local", "not_served"})


def test_parse_deployment_target_normalizes_without_hardcoding():
    assert _parse_deployment_target("") == "local"
    assert _parse_deployment_target("LOCAL") == "local"
    assert _parse_deployment_target("not-served") == "not_served"
    # Arbitrary instance names pass through -> supports any number of instances.
    assert _parse_deployment_target("prod-07") == "prod-07"
    assert _parse_deployment_target("fleet-prod-01") == "fleet-prod-01"


def _config():
    instances = {
        "east-1": InstanceConfig(name="east-1", ip="203.0.113.1", projects=["web"]),
        "east-2": InstanceConfig(name="east-2", ip="203.0.113.2", projects=["api"]),
        "east-3": InstanceConfig(name="east-3", ip="203.0.113.3", projects=["worker"]),
    }
    projects = {
        "web": ProjectConfig(id=1, name="web", deployment_target="east-1"),
        "api": ProjectConfig(id=2, name="api", deployment_target="east-2"),
        # a 3rd instance the old 2-value enum could never have resolved
        "worker": ProjectConfig(id=3, name="worker", deployment_target="east-3"),
        "tool": ProjectConfig(id=4, name="tool", deployment_target="local"),
    }
    return SegaConfig(instances=instances, projects=projects)


def test_instance_resolves_for_more_than_two_instances():
    c = _config()
    assert c.get_instance_for_project("web").ip == "203.0.113.1"
    assert c.get_instance_for_project("api").ip == "203.0.113.2"
    # Regression: the old enum only knew PROD_01/PROD_02, so a 3rd instance
    # silently failed. It must resolve now.
    assert c.get_instance_for_project("worker").ip == "203.0.113.3"
    assert c.get_instance_for_project("tool") is None  # local -> no host


def test_is_served_and_local_partition():
    c = _config()
    assert c.get_project("web").is_served is True
    assert c.get_project("tool").is_served is False
    assert {p.name for p in c.get_served_projects()} == {"web", "api", "worker"}
    assert {p.name for p in c.get_local_projects()} == {"tool"}


def test_to_dict_serializes_deployment_target_as_plain_string():
    d = _config().get_project("web").to_dict()
    assert d["deployment_target"] == "east-1"  # plain string, not enum .value
