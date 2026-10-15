#!/usr/bin/env python3
# Copyright 2022-2026 Huntington Applied
"""
Unit tests for the live-status dashboard: the container-status collector logic
and the action-route gating/CSRF/busy-lock. Pure logic only — no docker, no
network, no subprocess execution.

Run:  pytest engine/tests/test_status_dashboard.py
"""

from types import SimpleNamespace

import pytest

from sega.probe.container_status import (
    ContainerStatusCollector,
    ProjectLive,
    ServiceLive,
    _classify_suffix,
    _collapse_duplicate_services,
    _container_slug_suffix,
    _norm,
)
from sega.core.config import action_routes as ar


# --------------------------------------------------------------------------- #
# container name matching / classification
# --------------------------------------------------------------------------- #
def test_norm_hyphenates_underscores():
    assert _norm("scanner_app") == "scanner-app"


@pytest.mark.parametrize("name,slug,expected", [
    ("atlas-landing", "atlas", "landing"),
    ("scanner-app-landing", "scanner_app", "landing"),  # underscore slug
    ("hermes", "hermes", ""),                                        # exact match
    ("team-x", "vega", None),                                       # boundary: not "vega-"
    ("other-api", "atlas", None),                             # unrelated
])
def test_container_slug_suffix(name, slug, expected):
    assert _container_slug_suffix(name, slug) == expected


@pytest.mark.parametrize("suffix,expected", [
    ("landing", ("landing", "web")),
    ("product", ("product_app", "web")),
    ("frontend", ("landing", "web")),
    ("backend", ("api", "web")),
    ("api", ("api", "web")),
    ("ide", ("ide", "web")),
    ("postgres", ("postgres", "infra")),
    ("worker-1", ("worker-1", "infra")),
    ("redis", ("redis", "infra")),
])
def test_classify_suffix(suffix, expected):
    assert _classify_suffix(suffix) == expected


# --------------------------------------------------------------------------- #
# per-session collapse — N atlas-ide-<user> containers -> one counted row
# --------------------------------------------------------------------------- #
def test_collapse_leaves_singletons_untouched():
    svcs = [
        ServiceLive(name="api", kind="web", status="healthy", container="atlas-api"),
        ServiceLive(name="redis", kind="infra", status="running", container="atlas-redis"),
    ]
    out = _collapse_duplicate_services(svcs)
    assert [s.name for s in out] == ["api", "redis"]
    assert all(s.count == 1 for s in out)


def test_collapse_ide_sessions_all_running():
    svcs = [ServiceLive(name="ide", kind="web", status="running", container=f"atlas-ide-{u}")
            for u in ("a", "b", "c")]
    out = _collapse_duplicate_services(svcs)
    assert len(out) == 1
    assert out[0].count == 3 and out[0].status == "running"
    assert out[0].detail == "3× running"


def test_collapse_ide_uses_worst_status_and_breakdown():
    svcs = [
        ServiceLive(name="ide", kind="web", status="running", container="atlas-ide-a"),
        ServiceLive(name="ide", kind="web", status="running", container="atlas-ide-b"),
        ServiceLive(name="ide", kind="web", status="down", container="atlas-ide-c"),
    ]
    out = _collapse_duplicate_services(svcs)
    assert len(out) == 1
    # worst status wins so a crashed session still surfaces in the rollup
    assert out[0].status == "down" and out[0].count == 3
    assert out[0].detail == "1× down, 2× running"  # worst-first ordering


def test_collapse_preserves_first_appearance_order():
    svcs = [
        ServiceLive(name="api", kind="web", status="healthy", container="atlas-api"),
        ServiceLive(name="ide", kind="web", status="running", container="atlas-ide-a"),
        ServiceLive(name="ide", kind="web", status="running", container="atlas-ide-b"),
        ServiceLive(name="redis", kind="infra", status="running", container="atlas-redis"),
    ]
    out = _collapse_duplicate_services(svcs)
    assert [s.name for s in out] == ["api", "ide", "redis"]
    assert next(s for s in out if s.name == "ide").count == 2


# --------------------------------------------------------------------------- #
# rollup (compute_overall) — infra counted, mixes → degraded
# --------------------------------------------------------------------------- #
def _pl(phase, *services):
    pl = ProjectLive(slug="x", name="X", phase=phase)
    pl.services = [ServiceLive(name=n, kind=k, status=s) for (n, k, s) in services]
    pl.compute_overall()
    return pl


def test_rollup_all_healthy():
    assert _pl("demo", ("api", "web", "healthy"), ("db", "infra", "running")).overall == "healthy"


def test_rollup_partial_is_degraded():
    assert _pl("demo", ("api", "web", "healthy"), ("landing", "web", "down")).overall == "degraded"


def test_rollup_infra_down_not_hidden_by_healthy_web():
    pl = _pl("production", ("api", "web", "healthy"), ("db", "infra", "down"))
    assert pl.overall == "degraded"
    assert pl.declared_vs_actual  # production deviation flagged


def test_rollup_all_down():
    assert _pl("demo", ("api", "web", "down")).overall == "down"


def test_rollup_unknown_does_not_mask_healthy():
    assert _pl("demo", ("api", "web", "healthy"), ("landing", "web", "unknown")).overall == "healthy"


def test_rollup_no_services_is_unknown():
    assert _pl("demo").overall == "unknown"


# --------------------------------------------------------------------------- #
# _merge — HTTP-primary for web-with-url, container-state otherwise
# --------------------------------------------------------------------------- #
def _merged(kind, url, http_ok, ps_entry):
    col = ContainerStatusCollector(SimpleNamespace(get_all_projects=lambda: []), enable_local_docker=False)
    svc = ServiceLive(name="s", kind=kind, url=url, http_ok=http_ok, container="c")
    col._merge(svc, {"c": ps_entry} if ps_entry else {})
    return svc.status


def test_merge_web_http_ok_healthy():
    assert _merged("web", "http://x", True, {"state": "running", "status": "Up"}) == "healthy"


def test_merge_web_up_not_serving_is_degraded():
    assert _merged("web", "http://x", False, {"state": "running", "status": "Up"}) == "degraded"


def test_merge_web_no_url_running_is_running():
    # no URL → cannot confirm HTTP → judged by container state, not penalized
    assert _merged("web", None, False, {"state": "running", "status": "Up (healthy)"}) == "running"


def test_merge_infra_exited_is_down():
    assert _merged("infra", None, False, {"state": "exited", "status": "Exited (137)"}) == "down"


def test_merge_healthy_container_unrouted_endpoint_is_unreachable():
    # container healthcheck passes but public URL fails → unreachable, not degraded
    assert _merged("web", "http://x", False, {"state": "running", "status": "Up (healthy)"}) == "unreachable"


def test_merge_running_no_healthcheck_http_fail_is_degraded():
    # running but no healthcheck signal + HTTP fail → degraded (can't vouch for it)
    assert _merged("web", "http://x", False, {"state": "running", "status": "Up"}) == "degraded"


def test_rollup_unreachable_does_not_alarm():
    # healthy web + unreachable api → project stays healthy (routing gap ≠ outage)
    assert _pl("production", ("landing", "web", "healthy"), ("api", "web", "unreachable")).overall == "healthy"


def test_rollup_only_unreachable():
    assert _pl("demo", ("api", "web", "unreachable")).overall == "unreachable"


# --------------------------------------------------------------------------- #
# prefix ownership — most-specific slug wins
# --------------------------------------------------------------------------- #
def test_owner_slug_longest_wins():
    cm = SimpleNamespace(get_all_projects=lambda: [
        {"slug": "doc", "name": "Doc", "status": "demo", "deployment": {}},
        {"slug": "doc-scanner", "name": "DS", "status": "production", "deployment": {}},
    ])
    col = ContainerStatusCollector(cm, enable_local_docker=False)
    ps = {"doc-scanner-api": {"state": "running", "status": "Up"}, "doc-api": {"state": "running", "status": "Up"}}
    col._local_ps = ps
    col._all_slugs = sorted(["doc", "doc-scanner"], key=len, reverse=True)
    doc = col._build_services({"slug": "doc", "deployment": {}}, ps)
    assert not any(s.container == "doc-scanner-api" for s in doc)  # not stolen by "doc"
    assert any(s.container == "doc-api" for s in doc)


# --------------------------------------------------------------------------- #
# action gating / CSRF / busy lock
# --------------------------------------------------------------------------- #
def _req(headers=None, addr="127.0.0.1", cookies=None):
    return SimpleNamespace(headers={} if headers is None else headers,
                           remote_addr=addr, cookies={} if cookies is None else cookies)


@pytest.mark.parametrize("addr,expected", [
    ("127.0.0.1", True), ("::1", True), ("10.8.0.5", True),
    ("192.168.1.9", True), ("8.8.8.8", False),
])
def test_is_local_addr(addr, expected):
    assert ar._is_local_addr(addr) is expected


def test_actions_allowed_requires_flag(monkeypatch):
    monkeypatch.delenv("SEGA_DASHBOARD_ACTIONS", raising=False)
    assert ar._actions_allowed(_req()) is False
    monkeypatch.setenv("SEGA_DASHBOARD_ACTIONS", "1")
    assert ar._actions_allowed(_req()) is True


def test_actions_blocked_behind_tunnel(monkeypatch):
    monkeypatch.setenv("SEGA_DASHBOARD_ACTIONS", "1")
    assert ar._actions_allowed(_req({"CF-Connecting-IP": "8.8.8.8"})) is False
    assert ar._actions_allowed(_req({"X-Forwarded-For": "8.8.8.8"})) is False


def test_csrf_requires_header():
    assert ar._csrf_ok(_req()) is False
    assert ar._csrf_ok(_req({"X-Requested-With": "fetch"})) is True


def test_csrf_rejects_foreign_origin():
    r = _req({"X-Requested-With": "fetch", "Origin": "http://evil.com", "Host": "127.0.0.1:8015"})
    assert ar._csrf_ok(r) is False
    r_ok = _req({"X-Requested-With": "fetch", "Origin": "http://127.0.0.1:8015", "Host": "127.0.0.1:8015"})
    assert ar._csrf_ok(r_ok) is True


@pytest.mark.parametrize("action,expect", [
    ("start", "up -d"), ("stop", "stop"), ("restart", "restart"), ("rebuild", "up -d --build"),
])
def test_build_argv_uses_real_compose(monkeypatch, action, expect):
    r = ar.JobRunner()
    monkeypatch.setattr(r, "resolve_compose", lambda slug: ("/tmp/ws/atlas/docker-compose.dev.yml", "atlas"))
    cmds = r.build_argv(action, "atlas")
    joined = " ".join(cmds[-1])
    assert "docker compose -f /tmp/ws/atlas/docker-compose.dev.yml -p atlas" in joined
    assert joined.endswith(expect)


def test_build_argv_falls_back_to_sega_local(monkeypatch):
    r = ar.JobRunner()
    monkeypatch.setattr(r, "resolve_compose", lambda slug: None)
    cmds = r.build_argv("start", "atlas")
    assert "local" in cmds[-1] and "up" in cmds[-1]


def test_busy_lock_blocks_second_action():
    runner = ar.JobRunner()
    runner._active.add("atlas")  # simulate an in-flight action (no thread launched)
    assert runner.is_busy("atlas") is True
    assert runner.start("stop", "atlas") is None  # rejected while busy
    assert runner.is_busy("orion") is False


# --------------------------------------------------------------------------- #
# token auth (remote unlock sessions)
# --------------------------------------------------------------------------- #
def test_auth_state_disabled_without_token(monkeypatch):
    monkeypatch.delenv("SEGA_DASHBOARD_TOKEN", raising=False)
    monkeypatch.delenv("SEGA_DASHBOARD_ACTIONS", raising=False)
    assert ar._auth_state(_req()) == "disabled"
    assert ar._actions_allowed(_req()) is False


def test_auth_state_locked_with_token(monkeypatch):
    monkeypatch.setenv("SEGA_DASHBOARD_TOKEN", "s3cret-token")
    monkeypatch.delenv("SEGA_DASHBOARD_ACTIONS", raising=False)
    assert ar._auth_state(_req()) == "locked"
    assert ar._actions_allowed(_req()) is False  # token alone isn't enough


def test_session_cookie_roundtrip(monkeypatch):
    monkeypatch.setenv("SEGA_DASHBOARD_TOKEN", "s3cret-token")
    cookie = ar._signer().dumps("unlocked")
    req = SimpleNamespace(headers={"CF-Connecting-IP": "8.8.8.8"},
                          remote_addr="127.0.0.1", cookies={ar._AUTH_COOKIE: cookie})
    # valid session works even through the tunnel (that's the point)
    assert ar._session_valid(req) is True
    assert ar._actions_allowed(req) is True
    assert ar._auth_state(req) == "session"


def test_session_cookie_tamper_rejected(monkeypatch):
    monkeypatch.setenv("SEGA_DASHBOARD_TOKEN", "s3cret-token")
    req = SimpleNamespace(headers={}, remote_addr="127.0.0.1",
                          cookies={ar._AUTH_COOKIE: "forged.garbage.value"})
    assert ar._session_valid(req) is False


def test_session_invalid_if_token_changed(monkeypatch):
    monkeypatch.setenv("SEGA_DASHBOARD_TOKEN", "s3cret-token")
    cookie = ar._signer().dumps("unlocked")
    monkeypatch.setenv("SEGA_DASHBOARD_TOKEN", "rotated-token")  # rotation kills sessions
    req = SimpleNamespace(headers={}, remote_addr="127.0.0.1",
                          cookies={ar._AUTH_COOKIE: cookie})
    assert ar._session_valid(req) is False


def test_unlock_limiter_blocks_after_max():
    lim = ar._UnlockLimiter(max_fails=3, lockout=60)
    for _ in range(3):
        assert lim.blocked("1.2.3.4") is False
        lim.record_failure("1.2.3.4")
    assert lim.blocked("1.2.3.4") is True
    assert lim.blocked("5.6.7.8") is False  # per-IP
    lim.reset("1.2.3.4")
    assert lim.blocked("1.2.3.4") is False


def test_launch_argv_is_native_dev():
    cmds = ar.JobRunner().build_argv("launch", "atlas")
    joined = " ".join(cmds[-1])
    assert joined.endswith("local launch -p atlas -t desktop --dev")
