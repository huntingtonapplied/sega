#!/usr/bin/env python3
# Copyright 2022-2026 Huntington Applied
# License: Apache-2.0
#
# SEGA Live Status routes
# Serves segaapp.com/ (live platform status landing) + /v1/status (JSON API)
# on the same Flask server that hosts the Dash config dashboard.

"""
SEGA Live Status routes.

Adds three routes to the Dash app's underlying Flask server so that
``segaapp.com`` has a purposeful root page instead of a 404:

- ``GET /``            HTML live-status landing (project cards, auto-refresh)
- ``GET /v1/status``   JSON: live status of every project/service
- ``GET /healthz``     lightweight liveness probe

The heavy lifting lives in ``sega.probe.container_status.ContainerStatusCollector``.
Routes are registered against ``dash_app.server`` (the Flask instance) and do not
interfere with the Dash callbacks mounted under ``/config/``.
"""

from __future__ import annotations

from typing import Optional

from flask import jsonify, request

# FLEET brand tokens mirrored from fleet/docs/design/tokens/colors.ts (TS can't be
# imported into Python). Keep in sync with COLOR_PALETTE_STANDARD.md.
BRAND = {
    "primary": "#c27b7f",   # dusty rose
    "secondary": "#8fa890", # hermes
    "neutral": "#1a1a1a",
    "highlight": "#f5f5f5",
    "contrast": "#6b8db5",  # blue
}


def register_status_routes(dash_app, config_manager, collector=None) -> None:
    """Register live-status routes on the Dash app's Flask server."""
    from sega.probe.container_status import ContainerStatusCollector

    server = dash_app.server
    if collector is None:
        collector = ContainerStatusCollector(config_manager)

    # Systems strip: host metrics (load/mem/disk over SSH) for the machines in
    # config/system_monitors.yaml. Kept separate from the container collector —
    # different cadence, different failure modes.
    from sega.probe.system_status import SystemStatusCollector

    sys_collector = SystemStatusCollector()

    @server.route("/v1/systems")
    def v1_systems():
        force = request.args.get("force", "").lower() in ("1", "true", "yes")
        return jsonify(sys_collector.to_json(force=force))

    @server.route("/v1/status")
    def v1_status():
        force = request.args.get("force", "").lower() in ("1", "true", "yes")
        return jsonify(collector.to_json(force=force))

    @server.route("/v1/status/<slug>")
    def v1_status_project(slug: str):
        statuses = collector.collect_all()
        pl = statuses.get(slug)
        if pl is None:
            return jsonify({"error": f"unknown project: {slug}"}), 404
        return jsonify(pl.to_dict())

    @server.route("/healthz")
    def healthz():
        return jsonify({"ok": True, "service": "sega-dashboard"})

    import os
    from flask import send_file

    _ASSETS = os.path.join(os.path.dirname(__file__), "assets")

    @server.route("/favicon.ico")
    def favicon():
        p = os.path.join(_ASSETS, "favicon.ico")
        return send_file(p) if os.path.isfile(p) else ("", 404)

    @server.route("/assets/<path:name>")
    def assets(name):
        p = os.path.join(_ASSETS, os.path.basename(name))  # basename → no traversal
        return send_file(p) if os.path.isfile(p) else ("", 404)

    @server.route("/status")
    def landing():
        return LANDING_HTML

    # Root hub — SEGA logo + links to the two views (/status + /config), which
    # live at symmetric single-segment paths. Self-contained, shares the theme.
    @server.route("/")
    def root_hub():
        return ROOT_HTML

    # Legacy path → new consistent URL. The config editor moved from
    # /config/dashboard/ to /config/; keep old bookmarks and any external
    # healthchecks working.
    @server.route("/config/dashboard/")
    @server.route("/config/dashboard")
    def legacy_config_redirect():
        from flask import redirect

        return redirect("/config/", code=302)


# ---------------------------------------------------------------------------
# Landing page — self-contained (no build step). Fetches /v1/status and renders
# project cards with a live status dot per service. Auto-refreshes every 30s.
# ---------------------------------------------------------------------------
LANDING_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>SEGA · Command and Control</title>
<link rel="icon" href="/favicon.ico?v=2" sizes="any"/>
<link rel="icon" type="image/png" sizes="32x32" href="/assets/favicon-32.png?v=2"/>
<link rel="apple-touch-icon" href="/assets/apple-touch-icon.png?v=2"/>
<style>
  :root {
    --primary:#c27b7f; --secondary:#8fa890; --neutral:#1a1a1a;
    --highlight:#f5f5f5; --contrast:#6b8db5;
    --bg:#0e1013; --bg2:#0b0d0f; --panel:#16181c; --panel2:#1c1f24; --line:#282c32;
    --line2:#33383f; --text:#eceae6; --muted:#8b9096; --muted2:#6a6f76;
    --ok:#4ade80; --warn:#fbbf24; --down:#f87171; --idle:#6b7280; --unknown:#9ca3af;
    --mono:ui-monospace,'SF Mono',SFMono-Regular,Menlo,'Cascadia Mono',monospace;
    --sans:-apple-system,BlinkMacSystemFont,'Segoe UI',Inter,Roboto,sans-serif;
    --dotgrid:rgba(255,255,255,.028); --glow1:rgba(194,123,127,.06); --glow2:rgba(143,168,144,.05);
    --header-bg:linear-gradient(180deg, rgba(16,18,22,.92) 0%, rgba(14,16,19,.72) 100%);
  }
  :root[data-theme="light"] {
    --header-bg:linear-gradient(180deg, rgba(255,255,255,.94) 0%, rgba(245,246,248,.78) 100%);
    --bg:#f5f6f8; --bg2:#eceef1; --panel:#ffffff; --panel2:#f2f4f6; --line:#e4e7ec; --line2:#d3d8df;
    --text:#1a1d21; --muted:#5b616a; --muted2:#878d96;
    --ok:#16a34a; --warn:#c2740b; --down:#dc2626; --unknown:#6b7280; --contrast:#2563eb;
    --dotgrid:rgba(0,0,0,.045); --glow1:rgba(194,123,127,.10); --glow2:rgba(143,168,144,.09);
  }
  * { box-sizing:border-box; }
  body {
    margin:0; color:var(--text); font-family:var(--sans); -webkit-font-smoothing:antialiased;
    background:
      radial-gradient(circle at 1px 1px, var(--dotgrid) 1px, transparent 1.6px) 0 0/22px 22px,
      radial-gradient(1200px 600px at 78% -8%, var(--glow1), transparent 60%),
      radial-gradient(1000px 500px at 8% -10%, var(--glow2), transparent 55%),
      var(--bg);
    background-attachment:fixed; transition:background-color .2s, color .2s;
  }
  header {
    padding:22px 30px 16px; border-bottom:1px solid var(--line);
    background:var(--header-bg);
    position:sticky; top:0; z-index:5; backdrop-filter:blur(10px);
  }
  .iconbtn { width:34px; height:34px; padding:0; display:inline-flex; align-items:center; justify-content:center;
    border:1px solid var(--line2); background:var(--panel2); color:var(--text); border-radius:8px;
    font-size:14px; cursor:pointer; font-family:var(--sans); transition:border-color .15s, color .15s; }
  .iconbtn:hover { border-color:var(--primary); color:var(--primary); }
  .iconbtn.sm { width:28px; height:28px; font-size:13px; }
  header::after { content:""; display:block; position:absolute; left:0; right:0; bottom:-1px; height:1px;
    background:linear-gradient(90deg, transparent, var(--primary) 20%, var(--secondary) 80%, transparent); opacity:.5; }
  .topbar { display:flex; align-items:center; justify-content:space-between; gap:20px; }
  .brand { display:flex; align-items:center; gap:14px; text-decoration:none; color:inherit; }
  .brand:hover .wordmark { color:#fff; }
  .brand .logo { width:38px; height:38px; opacity:.95; filter:drop-shadow(0 0 10px rgba(194,123,127,.25));
    transition:transform .2s; }
  .brand:hover .logo { transform:scale(1.05); }
  .topnav { display:flex; gap:12px; align-items:center; }
  .navgroup { display:flex; background:var(--panel); border:1px solid var(--line2); border-radius:9px; padding:3px; }
  .navlink { color:var(--muted); text-decoration:none; font-size:11.5px; text-transform:uppercase;
    letter-spacing:.07em; padding:7px 15px; border-radius:6px; transition:all .15s; }
  .navlink:hover { color:var(--text); }
  .navlink.active { color:var(--text); background:var(--panel2); box-shadow:inset 0 0 0 1px var(--line2); }
  .livedot { width:7px; height:7px; border-radius:50%; background:var(--ok);
    animation:pulse 2.4s infinite; flex:none; }
  @keyframes pulse { 0%{box-shadow:0 0 0 0 rgba(74,222,128,.45);}
    70%{box-shadow:0 0 0 6px rgba(74,222,128,0);} 100%{box-shadow:0 0 0 0 rgba(74,222,128,0);} }
  .wordmark { font-size:21px; font-weight:700; letter-spacing:.14em; line-height:1; }
  .wordmark .platform { color:var(--muted); font-weight:500; letter-spacing:.04em; font-size:14px; }
  .subtitle { color:var(--muted); font-size:11px; margin-top:5px; text-transform:uppercase;
    letter-spacing:.16em; }
  .subtitle .tagline { color:var(--secondary); font-style:italic; text-transform:none; letter-spacing:0; }
  .summary { display:flex; gap:10px; margin-top:16px; flex-wrap:wrap; align-items:center; }
  .pill { display:flex; align-items:center; gap:7px; font-size:11px; color:var(--muted);
    text-transform:uppercase; letter-spacing:.09em; background:var(--panel);
    border:1px solid var(--line); border-radius:8px; padding:6px 11px; }
  .pill b { color:var(--text); font-family:var(--mono); font-size:13px; letter-spacing:0; }
  .swatch { width:8px; height:8px; border-radius:50%; }
  .meta { margin-left:auto; color:var(--muted); font-size:12px; display:flex; gap:16px; align-items:center; }
  #checked { font-family:var(--mono); font-size:11px; color:var(--muted2); }
  .btn { cursor:pointer; border:1px solid var(--line2); background:var(--panel2); color:var(--text);
    border-radius:8px; padding:6px 12px; font-size:12px; transition:border-color .15s; }
  .btn:hover { border-color:var(--primary); }
  .controls { padding:18px 30px 0; display:flex; gap:8px; flex-wrap:wrap; align-items:center; }
  .filter { border:1px solid var(--line); background:transparent; color:var(--muted);
    border-radius:7px; padding:6px 13px; font-size:11px; cursor:pointer; text-transform:uppercase;
    letter-spacing:.08em; transition:all .15s; }
  .filter:hover { color:var(--text); }
  .filter.active { color:var(--text); border-color:var(--primary); background:rgba(194,123,127,.14); }
  .flabel { font-size:10px; color:var(--muted2); text-transform:uppercase; letter-spacing:.14em;
    margin:0 4px 0 2px; }
  .fsep { width:1px; height:18px; background:var(--line2); margin:0 10px; }
  .fsw { width:7px; height:7px; border-radius:50%; display:inline-block; margin-right:6px; }
  /* --- systems strip (host metrics from /v1/systems) ----------------------- */
  .systems { padding:16px 30px 0; display:flex; gap:8px; flex-wrap:wrap; align-items:center; }
  .syschip { display:inline-flex; align-items:center; gap:10px; background:var(--panel);
    border:1px solid var(--line); border-radius:8px; padding:7px 12px; }
  .syschip .sysname { font-size:11.5px; font-weight:600; letter-spacing:.04em; color:var(--text); }
  .syschip.unreachable .sysname { color:var(--muted); }
  .sysdot { width:7px; height:7px; border-radius:50%; flex:none; }
  .sysmetrics { display:inline-flex; gap:10px; font-family:var(--mono); font-size:11px;
    color:var(--muted); align-items:baseline; }
  .sysmetrics b { color:var(--text); font-weight:600; }
  .sysmetric.warn b { color:var(--warn); }
  .sysmetric.critical b { color:var(--down); }
  main { padding:22px 30px 64px; display:grid; gap:15px;
    grid-template-columns:repeat(auto-fill,minmax(360px,1fr)); }
  .card { position:relative; background:var(--panel); border:1px solid var(--line); border-radius:12px;
    padding:15px 17px; transition:border-color .18s, transform .18s, box-shadow .18s; overflow:hidden; }
  /* Single restrained brand accent for all cards — status lives in the per-service
     dots + phase chip, not a full-card color. Only a real outage (down) gets a red
     accent so it still catches the eye. */
  .card::before { content:""; position:absolute; left:0; top:0; bottom:0; width:3px;
    background:var(--primary); opacity:.45; }
  .card:hover { border-color:var(--line2); transform:translateY(-2px);
    box-shadow:0 10px 30px rgba(0,0,0,.35); }
  .card:hover::before { opacity:.75; }
  .card.st-down::before { background:var(--down); opacity:.8; }
  .card-head { display:flex; align-items:flex-start; justify-content:space-between; gap:8px; }
  .titlewrap { display:flex; align-items:flex-start; gap:9px; }
  .ostat { width:9px; height:9px; border-radius:50%; flex:none; margin-top:5px; }
  .card-head .name { font-size:15.5px; font-weight:650; letter-spacing:.01em; }
  .card-head .sub { color:var(--muted2); font-size:11px; margin-top:3px; font-family:var(--mono);
    text-transform:uppercase; letter-spacing:.06em; }
  /* Phase + health rendered as the SAME outline-chip language for cohesion. */
  .chips { display:flex; gap:6px; align-items:center; }
  .phase, .hchip { font-size:9.5px; text-transform:uppercase; letter-spacing:.1em; font-weight:700;
    padding:3px 8px; border-radius:5px; border:1px solid var(--line2); white-space:nowrap;
    background:transparent; color:var(--muted); display:inline-flex; align-items:center; gap:6px; }
  .phase.production { color:var(--ok); border-color:rgba(74,222,128,.45); }
  .phase.alpha { color:var(--warn); border-color:rgba(251,191,36,.45); }
  .phase.demo { color:var(--muted); border-color:var(--line2); }
  .hchip .hdot { width:7px; height:7px; border-radius:50%; background:var(--unknown); }
  .hchip.st-healthy { color:var(--ok); border-color:rgba(74,222,128,.45); }
  .hchip.st-healthy .hdot { background:var(--ok); }
  .hchip.st-running { color:var(--secondary); border-color:rgba(143,168,144,.5); }
  .hchip.st-running .hdot { background:var(--secondary); }
  .hchip.st-unreachable { color:var(--contrast); border-color:rgba(107,141,181,.5); }
  .hchip.st-unreachable .hdot { background:var(--contrast); }
  .hchip.st-degraded { color:var(--warn); border-color:rgba(251,191,36,.45); }
  .hchip.st-degraded .hdot { background:var(--warn); }
  .hchip.st-down { color:var(--down); border-color:rgba(248,113,113,.5); }
  .hchip.st-down .hdot { background:var(--down); }
  .svc { display:flex; align-items:center; gap:10px; padding:7px 0; border-top:1px solid var(--line); }
  .svc:first-of-type { border-top:none; margin-top:10px; }
  .svc .sdot { width:8px; height:8px; border-radius:50%; flex:none; }
  .svc .sname { font-size:12.5px; min-width:92px; font-weight:500; }
  .svc .sdetail { color:var(--muted); font-size:11px; margin-left:auto;
    font-family:var(--mono); text-align:right; }
  .svc .scount { font-size:10px; font-weight:600; color:var(--secondary); font-family:var(--mono);
    background:var(--panel2); border:1px solid var(--line); border-radius:4px; padding:0 5px; }
  .svc .kind { font-size:9px; color:var(--muted2); text-transform:uppercase; letter-spacing:.08em;
    border:1px solid var(--line); border-radius:4px; padding:1px 5px; }
  /* Status colors apply ONLY to the small dot indicators (.sdot per-service,
     .ostat card header) — never to the card itself, which also carries an st-*
     class purely for its ::before accent logic. */
  .sdot.st-healthy,.ostat.st-healthy{background:var(--ok); box-shadow:0 0 7px rgba(74,222,128,.6);}
  .sdot.st-running,.ostat.st-running{background:var(--secondary);}
  .sdot.st-unreachable,.ostat.st-unreachable{background:var(--contrast);}
  .sdot.st-degraded,.ostat.st-degraded{background:var(--warn);}
  .sdot.st-down,.ostat.st-down{background:var(--down); box-shadow:0 0 7px rgba(248,113,113,.5);}
  .sdot.st-unknown,.ostat.st-unknown{background:var(--unknown);}
  .warnbar { margin-top:11px; font-size:11.5px; color:var(--warn);
    background:rgba(251,191,36,.07); border:1px solid rgba(251,191,36,.22);
    border-radius:7px; padding:6px 10px; }
  .footer { padding:0 30px 44px; color:var(--muted2); font-size:11px; letter-spacing:.03em; }
  a.cfg { color:var(--contrast); text-decoration:none; }
  a.cfg:hover { text-decoration:underline; }
  .loading { color:var(--muted); padding:56px; grid-column:1/-1; text-align:center; font-family:var(--mono);
    font-size:13px; letter-spacing:.05em; }
  .svc-link { color:var(--contrast); text-decoration:none; }
  .svc-link:hover { text-decoration:underline; }
  .actions { display:flex; gap:6px; flex-wrap:wrap; margin-top:12px; padding-top:10px;
    border-top:1px dashed var(--line); }
  .abtn { cursor:pointer; font-size:11px; border:1px solid var(--line); background:var(--panel2);
    color:var(--text); border-radius:6px; padding:4px 10px; }
  .abtn:hover { border-color:var(--primary); }
  .abtn[data-a="stop"]:hover, .abtn[data-a="rebuild"]:hover { border-color:var(--down); color:var(--down); }
  .abtn:disabled { opacity:.5; cursor:default; }
  #toast { position:fixed; right:20px; bottom:20px; display:flex; flex-direction:column; gap:8px; z-index:50; }
  .toast { background:var(--panel2); border:1px solid var(--line); border-left:3px solid var(--accent,var(--primary));
    border-radius:8px; padding:10px 14px; font-size:13px; max-width:340px; box-shadow:0 6px 20px rgba(0,0,0,.4); }
  .toast.ok { border-left-color:var(--ok); } .toast.err { border-left-color:var(--down); }
  #modal { position:fixed; inset:0; background:rgba(0,0,0,.6); display:none; align-items:center;
    justify-content:center; z-index:60; }
  #modal.show { display:flex; }
  .modal-box { background:var(--panel); border:1px solid var(--line); border-radius:12px;
    width:min(900px,92vw); max-height:80vh; display:flex; flex-direction:column; }
  .modal-head { display:flex; justify-content:space-between; align-items:center; padding:12px 16px;
    border-bottom:1px solid var(--line); }
  .modal-body { overflow:auto; padding:14px 16px; }
  .modal-body pre { margin:0; font-size:12px; white-space:pre-wrap; color:var(--text);
    font-family:ui-monospace,SFMono-Regular,Menlo,monospace; }
  #unlock { position:fixed; inset:0; background:rgba(0,0,0,.6); display:none; align-items:center;
    justify-content:center; z-index:70; }
  #unlock.show { display:flex; }
  .unlock-box { width:min(420px,92vw); }
  .unlock-hint { color:var(--muted); font-size:12.5px; margin:0 0 12px; }
  #unlock-form { display:flex; gap:8px; }
  .tinput { flex:1; background:var(--panel2); border:1px solid var(--line2); color:var(--text);
    border-radius:8px; padding:8px 12px; font-size:13px; outline:none; }
  .tinput:focus { border-color:var(--primary); }
  .unlock-btn { border-color:var(--primary) !important; }
  .unlock-msg { margin-top:10px; font-size:12px; color:var(--down); min-height:16px; }

  /* --- settings popover (gear) -------------------------------------------- */
  .settings-wrap { position:relative; display:inline-flex; }
  .settings-pop { position:absolute; right:0; top:calc(100% + 8px); width:250px;
    background:var(--panel); border:1px solid var(--line2); border-radius:10px; padding:12px;
    z-index:60; display:none; box-shadow:0 12px 34px rgba(0,0,0,.42); }
  .settings-pop.show { display:block; }
  .settings-row { margin-bottom:12px; }
  .settings-row:last-child { margin-bottom:0; }
  .settings-label { display:block; font-size:10px; text-transform:uppercase; letter-spacing:.12em;
    color:var(--muted2); margin-bottom:6px; }
  .seg { display:inline-flex; flex-wrap:wrap; gap:2px; background:var(--panel2);
    border:1px solid var(--line2); border-radius:8px; padding:2px; }
  .seg button { border:none; background:transparent; color:var(--muted); font-family:var(--sans);
    font-size:11px; padding:5px 11px; border-radius:6px; cursor:pointer; transition:color .12s, background .12s; }
  .seg button:hover { color:var(--text); }
  .seg button.active { background:var(--panel); color:var(--text); box-shadow:inset 0 0 0 1px var(--line2); }
  .settings-op-btn { width:100%; text-align:left; cursor:pointer; border:1px solid var(--line2);
    background:var(--panel2); color:var(--text); border-radius:8px; padding:7px 11px; font-size:12px;
    font-family:var(--sans); transition:border-color .15s; }
  .settings-op-btn:hover { border-color:var(--primary); }
  .settings-env { font-size:11px; color:var(--muted); line-height:1.7; font-family:var(--mono); }
  .settings-env b { color:var(--text); font-weight:600; }

  /* --- mobile ------------------------------------------------------------- */
  /* The header stays a single row (brand · controls) but tightens; the card
     grid collapses to one column so 360px-min tracks don't overflow narrow
     phones, and the horizontal page padding shrinks throughout. */
  @media (max-width: 640px) {
    header { padding:14px 16px 12px; }
    .topbar { position:relative; gap:12px; }
    .brand { gap:10px; }
    .brand .logo { width:30px; height:30px; }
    .wordmark { font-size:17px; letter-spacing:.1em; }
    .topnav { gap:8px; }
    .navlink { padding:6px 10px; font-size:10.5px; letter-spacing:.05em; }
    /* Anchor the settings popover to the full-width topbar instead of the
       gear button, so the 250px menu can't hang past the viewport edge. */
    .settings-wrap { position:static; }
    .settings-pop { max-width:calc(100vw - 32px); }
    .summary { margin-top:12px; }
    .meta { margin-left:0; gap:12px; }
    .controls { padding:14px 16px 0; }
    .systems { padding:12px 16px 0; }
    main { padding:16px 16px 48px; grid-template-columns:1fr; gap:12px; }
    .footer { padding:0 16px 32px; }
  }
  @media (max-width: 380px) {
    .wordmark { font-size:15px; }
    .navlink { padding:5px 8px; letter-spacing:.03em; }
  }
</style>
</head>
<body>
<header>
  <div class="topbar">
    <a class="brand" href="/">
      <img class="logo" id="logo" src="/assets/sega-icon-light.png" alt="SEGA"/>
      <span class="wordmark">SEGA</span>
    </a>
    <nav class="topnav">
      <button class="iconbtn" id="refresh" title="Refresh now">&#10227;</button>
      <div class="settings-wrap">
        <button class="iconbtn" id="settings-toggle" title="Settings" aria-label="Settings">&#9881;&#xFE0E;</button>
        <div class="settings-pop" id="settings-pop">
          <div class="settings-row">
            <span class="settings-label">Theme</span>
            <div class="seg">
              <button data-theme-set="light">Light</button>
              <button data-theme-set="dark">Dark</button>
            </div>
          </div>
          <div class="settings-row">
            <span class="settings-label">Auto-refresh</span>
            <div class="seg">
              <button data-refresh-set="15">15s</button>
              <button data-refresh-set="30">30s</button>
              <button data-refresh-set="60">60s</button>
              <button data-refresh-set="0">Off</button>
            </div>
          </div>
          <div class="settings-row" id="settings-ops-row" style="display:none">
            <span class="settings-label">Operations</span>
            <button class="settings-op-btn" id="op-toggle">Unlock operations…</button>
          </div>
          <div class="settings-row">
            <span class="settings-label">Environment</span>
            <div class="settings-env" id="env-readout">…</div>
          </div>
        </div>
      </div>
      <div class="navgroup">
        <a class="navlink active" href="/status">Live Status</a>
        <a class="navlink" href="/config/">Config</a>
      </div>
    </nav>
  </div>
  <div class="summary" id="summary">
    <div class="meta">
      <span class="livedot"></span><span id="checked">connecting…</span>
    </div>
  </div>
</header>
<div class="controls" id="filters"></div>
<div class="systems" id="systems" style="display:none"></div>
<main id="cards"><div class="loading">Checking every reachable container…</div></main>
<div class="footer">Auto-refreshes every 30s · HTTP reachability + Docker container state · segaapp.com</div>
<div id="toast"></div>
<div id="modal"><div class="modal-box">
  <div class="modal-head"><strong id="modal-title">Logs</strong>
    <button class="btn" onclick="document.getElementById('modal').classList.remove('show')">Close</button></div>
  <div class="modal-body"><pre id="modal-pre">…</pre></div>
</div></div>
<div id="unlock"><div class="modal-box unlock-box">
  <div class="modal-head"><strong>Unlock operations</strong>
    <button class="btn" onclick="document.getElementById('unlock').classList.remove('show')">Close</button></div>
  <div class="modal-body">
    <p class="unlock-hint">Enter the dashboard password to enable start / stop / restart / logs for this session (8h).</p>
    <form id="unlock-form">
      <input type="password" id="unlock-pass" class="tinput" placeholder="Dashboard password" autocomplete="current-password"/>
      <button type="submit" class="btn unlock-btn">Unlock</button>
    </form>
    <div id="unlock-msg" class="unlock-msg"></div>
  </div>
</div></div>

<script>
const SWATCH = {healthy:'var(--ok)',running:'var(--secondary)',unreachable:'var(--contrast)',degraded:'var(--warn)',down:'var(--down)',unknown:'var(--unknown)'};
const LABEL  = {healthy:'Healthy',running:'Running',unreachable:'Unreachable',degraded:'Degraded',down:'Down',unknown:'Unknown'};
let FILTER = 'all';
let HFILTER = 'all';
let DATA = null;
let CAPS = {actions_enabled:false};
const PHASES = ['production','alpha','demo'];

function applyTheme(t){
  document.documentElement.dataset.theme = t;
  try{ localStorage.setItem('sega-theme', t); }catch(e){}
  const logo=document.getElementById('logo');
  if(logo) logo.src = t==='light' ? '/assets/sega-icon-dark.png' : '/assets/sega-icon-light.png';
  document.querySelectorAll('[data-theme-set]').forEach(b=>
    b.classList.toggle('active', b.dataset.themeSet===t));
}
(function(){
  let t; try{ t=localStorage.getItem('sega-theme'); }catch(e){}
  if(!t) t = (window.matchMedia && matchMedia('(prefers-color-scheme: light)').matches) ? 'light' : 'dark';
  applyTheme(t);
})();

/* Auto-refresh interval \u2014 user-set via the settings popover, persisted so the
   choice sticks across reloads. '0' = off (manual refresh only). */
let refreshTimer=null;
function getRefresh(){ let v; try{ v=localStorage.getItem('sega-refresh'); }catch(e){} return v==null?'30':v; }
function applyRefresh(sec){
  sec=String(sec);
  try{ localStorage.setItem('sega-refresh', sec); }catch(e){}
  if(refreshTimer){ clearInterval(refreshTimer); refreshTimer=null; }
  const s=parseInt(sec,10);
  if(s>0) refreshTimer=setInterval(()=>load(false), s*1000);
  document.querySelectorAll('[data-refresh-set]').forEach(b=>
    b.classList.toggle('active', b.dataset.refreshSet===sec));
}
function toggleSettings(force){
  const p=document.getElementById('settings-pop'); if(!p) return;
  p.classList.toggle('show', force==null ? !p.classList.contains('show') : force);
}
const ACTIONS = [['start','Start'],['stop','Stop'],['restart','Restart'],['rebuild','Rebuild'],['logs','Logs']];

// Escape untrusted values (project names, container names, error details, docker
// state strings) before inserting into innerHTML.
function esc(s){ return String(s==null?'':s).replace(/[&<>"']/g,
  c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
function phaseCls(p){ return PHASES.includes(p)?p:'demo'; }
function statusCls(s){ return SWATCH[s]?s:'unknown'; }

function fmtTime(ts){ if(!ts) return 'live'; const d=new Date(ts*1000);
  return 'updated '+d.toLocaleTimeString(); }

/* Health counts live ONLY in the filter chips (single source, no duplication);
   the header keeps just the live/updated telemetry. Refresh lives in the navbar. */
function summaryBar(s){
  return `<div class="meta"><span class="livedot"></span>`+
    `<span id="checked">${fmtTime(s.checked_at)}</span></div>`;
}

function filterBar(projects){
  const phases=['all','production','alpha','demo'];
  const healths=['all','healthy','running','unreachable','degraded','down','unknown'];
  const pchips = phases.map(p=>{
    const n = p==='all'?projects.length:projects.filter(x=>x.phase===p).length;
    return `<span class="filter ${FILTER===p?'active':''}" data-g="p" data-f="${p}">${p} · ${n}</span>`;
  }).join('');
  const hchips = healths.map(h=>{
    const n = h==='all'?projects.length:projects.filter(x=>x.overall===h).length;
    if(h!=='all' && n===0) return '';
    const sw = h==='all'?'':`<i class="fsw" style="background:${SWATCH[h]}"></i>`;
    return `<span class="filter ${HFILTER===h?'active':''}" data-g="h" data-f="${h}">${sw}${h} · ${n}</span>`;
  }).join('');
  return `<span class="flabel">Phase</span>${pchips}`+
         `<span class="fsep"></span><span class="flabel">Health</span>${hchips}`;
}

function svcRow(sv){
  const cls='st-'+statusCls(sv.status);
  const detail = sv.detail || sv.container_state || '';
  // "Open in browser": linkify web services that expose a URL.
  const name = sv.url
    ? `<a class="svc-link sname" href="${esc(sv.url)}" target="_blank" rel="noopener">${esc(sv.name)} ↗</a>`
    : `<span class="sname">${esc(sv.name)}</span>`;
  // >1 when per-session containers (e.g. atlas-ide-<user_id>) are collapsed.
  const count = sv.count>1 ? `<span class="scount" title="${sv.count} containers">×${sv.count}</span>` : '';
  return `<div class="svc"><span class="sdot ${cls}"></span>`+
    name + count + `<span class="kind">${esc(sv.kind)}</span>`+
    `<span class="sdetail">${esc(detail)}</span></div>`;
}

function actionBar(p){
  if(!CAPS.actions_enabled) return '';
  const slug = p.slug;
  let list = ACTIONS.slice();
  // Native desktop launch: only for native-mode projects AND when the server can
  // actually reach the host (a containerized dashboard can't open host apps).
  if(CAPS.native_launch && p.mode==='native_dev') list.push(['launch','Launch ▶']);
  const btns = list.map(([a,label])=>
    `<button class="abtn" data-a="${a}" data-s="${esc(slug)}">${label}</button>`).join('');
  return `<div class="actions">${btns}</div>`;
}

function card(p){
  const svcs = (p.services||[]).map(svcRow).join('');
  const warn = p.declared_vs_actual ? `<div class="warnbar">⚠ ${esc(p.declared_vs_actual)}</div>`:'';
  return `<div class="card st-${statusCls(p.overall)}">`+
    `<div class="card-head"><div><div class="name">${esc(p.name)}</div>`+
    `<div class="sub">${esc(p.slug)}${p.instance?' · '+esc(p.instance):''}</div></div>`+
    `<div class="chips">`+
    `<span class="hchip st-${statusCls(p.overall)}"><i class="hdot"></i>${esc(p.overall)}</span>`+
    `<span class="phase ${phaseCls(p.phase)}">${esc(p.phase)}</span>`+
    `</div></div>`+
    svcs + warn + actionBar(p) + `</div>`;
}

function toast(msg, kind){
  const el=document.createElement('div'); el.className='toast '+(kind||'');
  el.textContent=msg; document.getElementById('toast').appendChild(el);
  setTimeout(()=>el.remove(), 6000);
}

async function pollJob(id, slug, action){
  for(let i=0;i<120;i++){
    await new Promise(r=>setTimeout(r,2000));
    let j; try{ j=await (await fetch('/v1/jobs/'+id)).json(); }catch(e){ continue; }
    if(j.status && j.status!=='running'){
      const ok = j.status==='succeeded';
      toast(`${slug} ${action}: ${j.status}`, ok?'ok':'err');
      if(!ok) showOutput(`${slug} ${action} (failed)`, j.output||'(no output)');
      load(true); return;
    }
  }
  toast(`${slug} ${action}: still running…`);
}

async function doAction(slug, action){
  if(action==='logs') return showLogs(slug);
  const dangerous = (action==='stop'||action==='rebuild');
  if(dangerous && !confirm(`${action} ${slug}? This affects running containers.`)) return;
  toast(`${slug}: ${action} started…`);
  try{
    const r=await fetch(`/v1/actions/${slug}/${action}`,
      {method:'POST', headers:{'X-Requested-With':'fetch'}});
    const j=await r.json();
    if(!r.ok){ toast(`${slug} ${action}: ${j.error||'error'}`,'err'); return; }
    pollJob(j.job_id, slug, action);
  }catch(e){ toast(`${slug} ${action}: request failed`,'err'); }
}

function showOutput(title, text){
  document.getElementById('modal-title').textContent=title;
  document.getElementById('modal-pre').textContent=text;
  document.getElementById('modal').classList.add('show');
}
async function showLogs(slug){
  showOutput(`Logs · ${slug}`, 'loading…');
  try{
    const j=await (await fetch('/v1/logs/'+slug+'?tail=200')).json();
    showOutput(`Logs · ${slug}`, j.output||'(no output)');
  }catch(e){ showOutput(`Logs · ${slug}`, 'failed to fetch logs'); }
}

function render(){
  if(!DATA) return;
  document.getElementById('summary').innerHTML = summaryBar(DATA.summary);
  document.getElementById('filters').innerHTML = filterBar(DATA.projects);
  const list = DATA.projects.filter(p=>
    (FILTER==='all'||p.phase===FILTER) && (HFILTER==='all'||p.overall===HFILTER));
  document.getElementById('cards').innerHTML =
    list.length ? list.map(card).join('') : '<div class="loading">No matching projects.</div>';
  document.getElementById('refresh').onclick = ()=>load(true);
  document.querySelectorAll('.filter').forEach(el=>
    el.onclick=()=>{ if(el.dataset.g==='h') HFILTER=el.dataset.f; else FILTER=el.dataset.f; render(); });
  document.querySelectorAll('.abtn').forEach(el=>
    el.onclick=()=>doAction(el.dataset.s, el.dataset.a));
}

async function loadCaps(){
  try{ CAPS = await (await fetch('/v1/capabilities')).json(); }catch(e){ CAPS={actions_enabled:false,auth:'disabled'}; }
  syncLock(); syncEnv();
}

/* Operations row in the settings popover: only shown when a password is
   configured (locked → offer unlock; session → offer lock). Local-trusted or
   unconfigured dashboards hide it entirely. */
function syncLock(){
  const row=document.getElementById('settings-ops-row');
  const btn=document.getElementById('op-toggle');
  if(!row||!btn) return;
  if(CAPS.auth==='locked'){ row.style.display=''; btn.textContent='Unlock operations…'; btn.dataset.mode='unlock'; }
  else if(CAPS.auth==='session'){ row.style.display=''; btn.textContent='Lock operations'; btn.dataset.mode='lock'; }
  else { row.style.display='none'; }
}

function syncEnv(){
  const el=document.getElementById('env-readout'); if(!el) return;
  const rt = CAPS.in_container ? 'container' : 'host';
  const act = CAPS.auth==='disabled' ? 'read-only' : (CAPS.actions_enabled?'enabled':'locked');
  el.innerHTML = `Runtime: <b>${rt}</b><br>Actions: <b>${esc(act)}</b>`;
}

async function doUnlock(ev){
  ev.preventDefault();
  const pass=document.getElementById('unlock-pass').value;
  const msg=document.getElementById('unlock-msg');
  msg.textContent='';
  try{
    const r=await fetch('/v1/auth/unlock',{method:'POST',
      headers:{'X-Requested-With':'fetch','Content-Type':'application/json'},
      body:JSON.stringify({password:pass})});
    const j=await r.json();
    if(!r.ok){ msg.textContent=j.error||'unlock failed'; return; }
    document.getElementById('unlock').classList.remove('show');
    document.getElementById('unlock-pass').value='';
    toast('Operations unlocked for this session','ok');
    await loadCaps(); render();
  }catch(e){ msg.textContent='request failed'; }
}

async function doLock(){
  try{ await fetch('/v1/auth/lock',{method:'POST',headers:{'X-Requested-With':'fetch'}}); }catch(e){}
  toast('Operations locked');
  await loadCaps(); render();
}

async function load(force){
  loadSystems(force);  // fire-and-forget: slow SSH must never delay project cards
  try{
    const r = await fetch('/v1/status'+(force?'?force=1':''));
    DATA = await r.json(); render();
  }catch(e){
    document.getElementById('cards').innerHTML =
      '<div class="loading">Status API unreachable.</div>';
  }
}

/* Systems strip — host metrics (load/mem/disk) for the machines of interest.
   Hidden entirely when the endpoint fails or no hosts are configured. */
const SYSDOT = {ok:'var(--ok)', warn:'var(--warn)', critical:'var(--down)', unreachable:'var(--unknown)'};
function sysLvl(v,w,c){ return v==null?'':(v>=c?'critical':(v>=w?'warn':'')); }
function sysChip(s){
  const dot = `<i class="sysdot" style="background:${SYSDOT[s.status]||SYSDOT.unreachable}"></i>`;
  const name = `<span class="sysname">${esc(s.name)}</span>`;
  if(s.status==='unreachable')
    return `<span class="syschip unreachable" title="${esc(s.label)}">${dot}${name}`+
           `<span class="sysmetrics">unreachable</span></span>`;
  const m = [];
  if(s.load1!=null) m.push(`<span class="sysmetric ${sysLvl(s.cpu_pct,70,90)}">load <b>${s.load1}</b>${s.cpus?'/'+s.cpus:''}</span>`);
  if(s.mem_pct!=null) m.push(`<span class="sysmetric ${sysLvl(s.mem_pct,80,95)}">mem <b>${s.mem_pct}%</b></span>`);
  if(s.disk_pct!=null) m.push(`<span class="sysmetric ${sysLvl(s.disk_pct,75,90)}">disk <b>${s.disk_pct}%</b></span>`);
  const tip = `${s.label||''}${s.uptime?' · up '+s.uptime:''}${s.mem_total_gb?' · '+s.mem_total_gb+'GB RAM':''}`+
              `${s.disk_total_gb?' · '+s.disk_used_gb+'/'+s.disk_total_gb+'GB disk':''}`;
  return `<span class="syschip" title="${esc(tip)}">${dot}${name}`+
         `<span class="sysmetrics">${m.join('')}</span></span>`;
}
async function loadSystems(force){
  const el = document.getElementById('systems');
  try{
    const j = await (await fetch('/v1/systems'+(force?'?force=1':''))).json();
    if(!j.systems || !j.systems.length){ el.style.display='none'; return; }
    el.innerHTML = `<span class="flabel">Systems</span>` + j.systems.map(sysChip).join('');
    el.style.display='flex';
  }catch(e){ el.style.display='none'; }
}
// Settings popover: open/close, segmented theme + refresh controls, operations.
document.getElementById('settings-toggle').onclick = (e)=>{ e.stopPropagation(); toggleSettings(); };
document.addEventListener('click', (e)=>{
  const pop=document.getElementById('settings-pop');
  if(pop && pop.classList.contains('show') && !e.target.closest('.settings-wrap')) toggleSettings(false);
});
document.addEventListener('keydown', (e)=>{ if(e.key==='Escape') toggleSettings(false); });
document.querySelectorAll('[data-theme-set]').forEach(b=>
  b.onclick=()=>applyTheme(b.dataset.themeSet));
document.querySelectorAll('[data-refresh-set]').forEach(b=>
  b.onclick=()=>applyRefresh(b.dataset.refreshSet));
document.getElementById('op-toggle').onclick = ()=>{
  const mode=document.getElementById('op-toggle').dataset.mode;
  toggleSettings(false);
  if(mode==='lock'){ doLock(); }
  else { document.getElementById('unlock').classList.add('show');
         document.getElementById('unlock-pass').focus(); }
};
document.getElementById('unlock-form').addEventListener('submit', doUnlock);
applyRefresh(getRefresh());
loadCaps().then(()=>load(false));
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Root hub — served at "/". SEGA logo + two cards linking to the Live Status and
# Config views. Self-contained (no build step); shares the theme tokens, dot-grid
# background, and the 'sega-theme' localStorage key with the other pages.
# ---------------------------------------------------------------------------
ROOT_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>SEGA · Huntington Applied</title>
<link rel="icon" href="/favicon.ico?v=2" sizes="any"/>
<link rel="icon" type="image/png" sizes="32x32" href="/assets/favicon-32.png?v=2"/>
<link rel="apple-touch-icon" href="/assets/apple-touch-icon.png?v=2"/>
<style>
  :root {
    --primary:#c27b7f; --secondary:#8fa890; --contrast:#6b8db5;
    --bg:#0e1013; --panel:#16181c; --panel2:#1c1f24; --line:#282c32; --line2:#33383f;
    --text:#eceae6; --muted:#8b9096; --muted2:#6a6f76;
    --sans:-apple-system,BlinkMacSystemFont,'Segoe UI',Inter,Roboto,sans-serif;
    --dotgrid:rgba(255,255,255,.028); --glow1:rgba(194,123,127,.07); --glow2:rgba(143,168,144,.06);
  }
  :root[data-theme="light"] {
    --bg:#f5f6f8; --panel:#ffffff; --panel2:#f2f4f6; --line:#e4e7ec; --line2:#d3d8df;
    --text:#1a1d21; --muted:#5b616a; --muted2:#878d96; --contrast:#2563eb;
    --dotgrid:rgba(0,0,0,.045); --glow1:rgba(194,123,127,.12); --glow2:rgba(143,168,144,.10);
  }
  * { box-sizing:border-box; }
  body {
    margin:0; min-height:100vh; color:var(--text); font-family:var(--sans);
    -webkit-font-smoothing:antialiased; display:flex; flex-direction:column;
    background:
      radial-gradient(circle at 1px 1px, var(--dotgrid) 1px, transparent 1.6px) 0 0/22px 22px,
      radial-gradient(1200px 600px at 78% -8%, var(--glow1), transparent 60%),
      radial-gradient(1000px 500px at 8% -10%, var(--glow2), transparent 55%),
      var(--bg);
    background-attachment:fixed; transition:background-color .2s, color .2s;
  }
  .toggle-wrap { position:fixed; top:18px; right:20px; }
  .iconbtn { width:34px; height:34px; display:inline-flex; align-items:center; justify-content:center;
    border:1px solid var(--line2); background:var(--panel2); color:var(--text); border-radius:8px;
    font-size:14px; cursor:pointer; font-family:var(--sans); transition:border-color .15s, color .15s; }
  .iconbtn:hover { border-color:var(--primary); color:var(--primary); }
  .hub { flex:1; display:flex; flex-direction:column; align-items:center; justify-content:center;
    text-align:center; padding:48px 20px; }
  .hub .logo { width:92px; height:92px; opacity:.96;
    filter:drop-shadow(0 0 20px rgba(194,123,127,.28)); }
  .hub .wordmark { font-size:44px; font-weight:700; letter-spacing:.2em; line-height:1; margin-top:20px; }
  .hub .tagline { color:var(--secondary); font-style:italic; font-size:15px; margin-top:12px; }
  .hub .sub { color:var(--muted2); font-size:11px; text-transform:uppercase; letter-spacing:.18em; margin-top:8px; }
  .cards { display:flex; gap:16px; margin-top:44px; flex-wrap:wrap; justify-content:center; }
  .navcard { position:relative; overflow:hidden; text-decoration:none; color:var(--text);
    display:flex; flex-direction:column; align-items:flex-start; gap:7px; text-align:left;
    width:250px; padding:20px 22px; background:var(--panel); border:1px solid var(--line);
    border-radius:14px; transition:border-color .18s, transform .18s, box-shadow .18s; }
  .navcard::before { content:""; position:absolute; left:0; top:0; bottom:0; width:3px;
    background:var(--primary); opacity:.5; }
  .navcard:hover { border-color:var(--line2); transform:translateY(-3px); box-shadow:0 12px 34px rgba(0,0,0,.35); }
  .navcard:hover::before { opacity:.85; }
  .navcard .ic { font-size:20px; line-height:1; }
  .navcard .t { font-size:16.5px; font-weight:650; letter-spacing:.01em; }
  .navcard .d { font-size:12px; color:var(--muted); line-height:1.5; }
  .navcard .go { margin-top:4px; font-size:11px; text-transform:uppercase; letter-spacing:.1em;
    color:var(--contrast); }
  .footer { text-align:center; color:var(--muted2); font-size:11px; padding:22px; letter-spacing:.03em; }
  @media (max-width:520px) {
    .hub { padding:36px 18px; }
    .hub .logo { width:74px; height:74px; }
    .hub .wordmark { font-size:34px; letter-spacing:.16em; }
    .cards { margin-top:34px; }
    .navcard { width:100%; max-width:320px; }
  }
</style>
</head>
<body>
  <div class="toggle-wrap">
    <button class="iconbtn" id="theme-toggle" title="Toggle light / dark">&#x263E;&#xFE0E;</button>
  </div>
  <main class="hub">
    <img class="logo" id="logo" src="/assets/sega-icon-light.png" alt="SEGA"/>
    <div class="wordmark">SEGA</div>
    <div class="tagline">Ogni Dove</div>
    <div class="sub">Huntington Applied</div>
    <div class="cards">
      <a class="navcard" href="/status">
        <span class="ic">&#9673;</span>
        <span class="t">Live Status</span>
        <span class="d">Real-time health of every reachable container and service.</span>
        <span class="go">Open &rarr;</span>
      </a>
      <a class="navcard" href="/config/">
        <span class="ic">&#9881;&#xFE0E;</span>
        <span class="t">Config</span>
        <span class="d">Manage the project registry — ports, phases, labs, and domains.</span>
        <span class="go">Open &rarr;</span>
      </a>
    </div>
  </main>
  <div class="footer">segaapp.com &middot; Huntington Applied infrastructure orchestrator</div>
  <script>
    function applyTheme(t){
      document.documentElement.dataset.theme=t;
      try{ localStorage.setItem('sega-theme', t); }catch(e){}
      var logo=document.getElementById('logo');
      if(logo) logo.src = t==='light' ? '/assets/sega-icon-dark.png' : '/assets/sega-icon-light.png';
      var btn=document.getElementById('theme-toggle');
      if(btn) btn.textContent = t==='light' ? '\\u2600\\ufe0e' : '\\u263E\\ufe0e';
    }
    (function(){ var t; try{ t=localStorage.getItem('sega-theme'); }catch(e){}
      if(!t) t=(window.matchMedia && matchMedia('(prefers-color-scheme: light)').matches)?'light':'dark';
      applyTheme(t); })();
    document.getElementById('theme-toggle').onclick=function(){
      applyTheme(document.documentElement.dataset.theme==='light'?'dark':'light'); };
  </script>
</body>
</html>"""
