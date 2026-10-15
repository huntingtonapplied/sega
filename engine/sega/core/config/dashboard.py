#!/usr/bin/env python3
# Copyright 2022-2026 Huntington Applied
# License: Apache-2.0
#
# SEGA Configuration Dashboard
# Dash-based UI for managing fleet-projects.json
#
# AUTHORITATIVE REFERENCES:
# - Port Allocation Standards: /docs/standards/infrastructure/PORT_ALLOCATION_STANDARDS.md

"""
SEGA Configuration Dashboard

Interactive Dash application for managing FLEET project configurations.

Features:
- View all projects in interactive table
- Filter by status, category, lab assignment
- Search projects by name/slug
- Inline editing with validation
- Save with automatic backup
- Rollback capability
- Export functionality

Launch:
    from sega.core.config.dashboard import create_dashboard
    from sega.core.config import ProjectConfigManager

    config_manager = ProjectConfigManager()
    app = create_dashboard(config_manager)
    app.run(host='127.0.0.1', port=8015, debug=False)
"""

try:
    import dash
    from dash import dcc, html, dash_table, Input, Output, State, callback_context
    import dash_bootstrap_components as dbc

    DASH_AVAILABLE = True
except ImportError:
    DASH_AVAILABLE = False
    # Define dummy classes for type hints
    dash = None
    dcc = None
    html = None
    dash_table = None
    dbc = None

from typing import Any, Dict, List, Optional
import json

from .project_config import ProjectConfigManager
from .validators import ConfigValidator


# Full column set for the projects table. Which columns actually render is
# user-controlled via the "Columns" picker (see the column-picker callback);
# DEFAULT_VISIBLE_COLUMNS is the initial selection. The home flags
# (featured/carousel) and the secondary ports (mobile/db/redis/metrics) are
# hidden by default — low signal for day-to-day config work — but one click away.
TABLE_COLUMNS = [
    {"name": "ID", "id": "id", "editable": False, "type": "numeric"},
    {"name": "Slug", "id": "slug", "editable": False},
    {"name": "Name", "id": "name", "editable": True},
    {"name": "Status", "id": "status", "editable": True, "presentation": "dropdown"},
    {"name": "Category", "id": "category", "editable": True},
    {"name": "Lab", "id": "lab_assignment", "editable": True},
    {"name": "API Port", "id": "port_api", "editable": True, "type": "numeric"},
    {"name": "Frontend Port", "id": "port_frontend", "editable": True, "type": "numeric"},
    {"name": "Desktop Port", "id": "port_desktop", "editable": True, "type": "numeric"},
    {"name": "Mobile Port", "id": "port_mobile", "editable": True, "type": "numeric"},
    {"name": "DB Port", "id": "port_database", "editable": True, "type": "numeric"},
    {"name": "Redis Port", "id": "port_redis", "editable": True, "type": "numeric"},
    {"name": "Metrics Port", "id": "port_metrics", "editable": True, "type": "numeric"},
    {"name": "Domain", "id": "primary_domain", "editable": True},
    {"name": "Featured", "id": "home_featured", "editable": True, "type": "any"},
    {"name": "Carousel", "id": "home_carousel", "editable": True, "type": "any"},
]

DEFAULT_VISIBLE_COLUMNS = [
    "id", "slug", "name", "status", "category", "lab_assignment",
    "port_api", "port_frontend", "port_desktop", "primary_domain",
]

# Rendered in monospace (by column id, so it survives reordering/hiding).
PORT_COLUMN_IDS = [
    "port_api", "port_frontend", "port_desktop",
    "port_mobile", "port_database", "port_redis", "port_metrics",
]


def create_dashboard(config_manager: ProjectConfigManager) -> "dash.Dash":
    """
    Create and configure Dash application for configuration management.

    Args:
        config_manager: ProjectConfigManager instance

    Returns:
        Configured Dash application

    Raises:
        ImportError: If Dash dependencies not installed
    """
    if not DASH_AVAILABLE:
        raise ImportError("Dash dependencies not installed. Install with: pip install dash dash-bootstrap-components")

    # Create Dash app (dark theme to match the live-status landing)
    app = dash.Dash(
        __name__,
        external_stylesheets=[dbc.themes.DARKLY],
        # Consistent, tidy URL: pairs with the landing at "/" (was /config/dashboard/;
        # the old path 302-redirects here, see status_routes.py).
        url_base_pathname="/config/",
        suppress_callback_exceptions=True,
        # Mobile: Dash omits the viewport meta by default, which makes the page render
        # at desktop width on phones. Add it so the responsive header/rows engage.
        meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
    )

    # Set app title
    app.title = "SEGA Configuration Dashboard"

    # Create layout
    app.layout = create_layout(config_manager)

    # Register callbacks
    register_callbacks(app, config_manager)

    # Register live-status routes (segaapp.com/ landing + /v1/status JSON).
    # Purely additive: the config dashboard remains untouched at /config/.
    try:
        from .status_routes import register_status_routes

        register_status_routes(app, config_manager)
    except Exception as e:  # never let the status layer break the config dashboard
        import logging

        logging.getLogger(__name__).warning("Live-status routes not registered: %s", e)

    # Local/internal-only action controls (start/stop/restart/rebuild/logs).
    # Gated at request time by SEGA_DASHBOARD_ACTIONS + non-tunnelled local peer.
    try:
        from .action_routes import register_action_routes

        register_action_routes(app, config_manager)
    except Exception as e:
        import logging

        logging.getLogger(__name__).warning("Action routes not registered: %s", e)

    return app


def create_layout(config_manager: ProjectConfigManager) -> dbc.Container:
    """
    Create dashboard layout.

    Args:
        config_manager: ProjectConfigManager instance

    Returns:
        Dash layout container
    """
    # Load initial data
    projects = config_manager.get_all_projects()

    # Get unique values for filters
    statuses = sorted(set(p.get("status", "") for p in projects if p.get("status")))
    categories = sorted(set(p.get("category", "") for p in projects if p.get("category")))
    labs = sorted(set(p.get("lab_assignment", "") for p in projects if p.get("lab_assignment")))

    return dbc.Container(
        [
            # Shared top nav — identical structure/classes to the landing header
            # (styled by assets/sega-theme.css; theme toggle wired by sega-theme.js).
            html.Div(
                [
                    html.A(
                        [
                            html.Img(src="/assets/sega-icon-light.png", id="logo", className="logo"),
                            html.Span("SEGA", className="wordmark"),
                        ],
                        href="/",
                        className="brand",
                    ),
                    html.Div(
                        [
                            # Settings popover (gear) \u2014 same structure/behavior as the
                            # landing header. Theme + environment are handled by the
                            # shared vanilla JS (sega-theme.js); the auto-refresh
                            # segmented control is wired to live-interval via a callback.
                            html.Div(
                                [
                                    html.Button("\u2699\ufe0e", id="settings-toggle",
                                                className="iconbtn", title="Settings",
                                                **{"aria-label": "Settings"}),
                                    html.Div(
                                        [
                                            html.Div(
                                                [
                                                    html.Span("Theme", className="settings-label"),
                                                    html.Div(
                                                        [
                                                            html.Button("Light", **{"data-theme-set": "light"}),
                                                            html.Button("Dark", **{"data-theme-set": "dark"}),
                                                        ],
                                                        className="seg",
                                                    ),
                                                ],
                                                className="settings-row",
                                            ),
                                            html.Div(
                                                [
                                                    html.Span("Auto-refresh", className="settings-label"),
                                                    html.Div(
                                                        [
                                                            html.Button("15s", id="rf-15", className="seg-btn"),
                                                            html.Button("30s", id="rf-30", className="seg-btn active"),
                                                            html.Button("60s", id="rf-60", className="seg-btn"),
                                                            html.Button("Off", id="rf-0", className="seg-btn"),
                                                        ],
                                                        className="seg",
                                                    ),
                                                ],
                                                className="settings-row",
                                            ),
                                            html.Div(
                                                [
                                                    html.Span("Environment", className="settings-label"),
                                                    html.Div("\u2026", className="settings-env", id="env-readout"),
                                                ],
                                                className="settings-row",
                                            ),
                                        ],
                                        className="settings-pop",
                                        id="settings-pop",
                                    ),
                                ],
                                className="settings-wrap",
                            ),
                            html.Div(
                                [
                                    html.A("Live Status", href="/status", className="navlink"),
                                    html.A("Config", href="/config/", className="navlink active"),
                                ],
                                className="navgroup",
                            ),
                        ],
                        className="topnav",
                    ),
                ],
                className="sega-nav",
            ),
            # Action bar: unsaved badge + validation help on the left, buttons right
            dbc.Row(
                [
                    dbc.Col(
                        [
                            html.P(
                                [
                                    html.Span(id="unsaved-changes-badge"),
                                    html.I(
                                        className="ms-2 bi bi-info-circle",
                                        id="validation-help-icon",
                                        style={"cursor": "pointer", "fontSize": "0.9rem"},
                                    ),
                                ],
                                className="text-muted mb-0 d-flex align-items-center",
                            ),
                            dbc.Tooltip(
                                [
                                    html.Strong("Validation Rules:"),
                                    html.Ul(
                                        [
                                            html.Li("Status must be: demo, alpha, or production"),
                                            html.Li("API ports: 8000-8099"),
                                            html.Li("Frontend ports: 3000-3099"),
                                            html.Li("Desktop ports: 3300-3399"),
                                            html.Li("No duplicate ports across projects"),
                                            html.Li("Required fields: id, slug, name, status, category, lab"),
                                        ],
                                        className="mb-0",
                                        style={"fontSize": "0.85rem"},
                                    ),
                                ],
                                target="validation-help-icon",
                                placement="bottom",
                            ),
                        ],
                        xs=12,
                        md=6,
                    ),
                    dbc.Col(
                        [
                            dbc.ButtonGroup(
                                [
                                    dcc.Loading(
                                        id="loading-validate",
                                        type="default",
                                        children=dbc.Button(
                                            "Validate", id="btn-validate", color="info", outline=True, className="me-2"
                                        ),
                                    ),
                                    dcc.Loading(
                                        id="loading-export",
                                        type="default",
                                        children=dbc.Button(
                                            "Export", id="btn-export", color="secondary", outline=True, className="me-2"
                                        ),
                                    ),
                                    dbc.Button(
                                        "Rollback", id="btn-rollback", color="danger", outline=True, className="me-2"
                                    ),
                                    dcc.Loading(
                                        id="loading-save",
                                        type="default",
                                        children=dbc.Button(
                                            "Save Changes", id="btn-save", color="primary", className="fw-bold"
                                        ),
                                    ),
                                ]
                            )
                        ],
                        xs=12,
                        md=6,
                        className="d-flex flex-wrap justify-content-start justify-content-md-end "
                        "align-items-center mt-2 mt-md-0",
                    ),
                ],
                className="mb-3 align-items-center",
            ),
            # Filter bar
            dbc.Row(
                [
                    dbc.Col(
                        [
                            html.Label("Status", className="fw-bold mb-1"),
                            dcc.Dropdown(
                                id="filter-status",
                                options=[{"label": "All", "value": "all"}]
                                + [{"label": s.capitalize(), "value": s} for s in statuses],
                                value="all",
                                clearable=False,
                                className="mb-2",
                            ),
                        ],
                        xs=12,
                        sm=6,
                        lg=3,
                    ),
                    dbc.Col(
                        [
                            html.Label("Category", className="fw-bold mb-1"),
                            dcc.Dropdown(
                                id="filter-category",
                                options=[{"label": "All", "value": "all"}]
                                + [{"label": c, "value": c} for c in categories],
                                value="all",
                                clearable=False,
                                className="mb-2",
                            ),
                        ],
                        xs=12,
                        sm=6,
                        lg=3,
                    ),
                    dbc.Col(
                        [
                            html.Label("Lab Assignment", className="fw-bold mb-1"),
                            dcc.Dropdown(
                                id="filter-lab",
                                options=[{"label": "All", "value": "all"}] + [{"label": l, "value": l} for l in labs],
                                value="all",
                                clearable=False,
                                className="mb-2",
                            ),
                        ],
                        xs=12,
                        sm=6,
                        lg=3,
                    ),
                    dbc.Col(
                        [
                            html.Label("Search", className="fw-bold mb-1"),
                            dbc.Input(
                                id="search-box",
                                type="text",
                                placeholder="Search by name or slug...",
                                debounce=True,
                                className="mb-2",
                            ),
                        ],
                        xs=12,
                        sm=6,
                        lg=3,
                    ),
                ],
                className="mb-4 p-3 rounded sega-panel",
            ),
            # Stats row (declared config counts)
            dbc.Row([dbc.Col([html.Div(id="stats-display", className="mb-3")])]),
            # Live runtime-health summary (refreshed on interval, non-editing)
            dbc.Row([dbc.Col([html.Div(id="live-status-summary", className="mb-3")])]),
            dcc.Interval(id="live-interval", interval=30000, n_intervals=0),
            # Column visibility picker — choose which columns the table shows.
            # Persisted locally so the choice sticks across reloads.
            dbc.Row(
                [
                    dbc.Col(
                        [
                            html.Label("Columns", className="fw-bold mb-1"),
                            dcc.Dropdown(
                                id="column-picker",
                                options=[{"label": c["name"], "value": c["id"]} for c in TABLE_COLUMNS],
                                value=DEFAULT_VISIBLE_COLUMNS,
                                multi=True,
                                clearable=False,
                                placeholder="Select columns to display…",
                                persistence=True,
                                persistence_type="local",
                                className="mb-2",
                            ),
                        ]
                    )
                ],
                className="mb-3",
            ),
            # Projects table
            dbc.Row(
                [
                    dbc.Col(
                        [
                            html.Div(
                                [
                                    dash_table.DataTable(
                                        id="projects-table",
                                        columns=TABLE_COLUMNS,
                                        hidden_columns=[
                                            c["id"] for c in TABLE_COLUMNS
                                            if c["id"] not in DEFAULT_VISIBLE_COLUMNS
                                        ],
                                        data=projects,
                                        editable=True,
                                        filter_action="native",
                                        sort_action="native",
                                        page_action="native",
                                        page_size=25,
                                        style_table={"overflowX": "auto", "minWidth": "100%"},
                                        # Port columns in mono, keyed by id so it survives
                                        # column reorder/hide (index-based CSS would not).
                                        style_cell_conditional=[
                                            {"if": {"column_id": cid},
                                             "fontFamily": "ui-monospace, SFMono-Regular, Menlo, monospace",
                                             "fontSize": "12.5px"}
                                            for cid in PORT_COLUMN_IDS
                                        ],
                                        style_cell={
                                            "textAlign": "left",
                                            "padding": "10px",
                                            "fontSize": "14px",
                                            "fontFamily": "sans-serif",
                                            "backgroundColor": "#17191c",
                                            "color": "#e8e6e3",
                                            "border": "1px solid #2a2e33",
                                        },
                                        style_header={
                                            "fontWeight": "bold",
                                            "backgroundColor": "#1e2125",
                                            "color": "#ffffff",
                                            "borderBottom": "2px solid #c27b7f",
                                        },
                                        style_data={"backgroundColor": "#17191c", "color": "#e8e6e3"},
                                        style_data_conditional=[
                                            {"if": {"row_index": "odd"}, "backgroundColor": "#1b1e21"}
                                        ],
                                        dropdown={
                                            "status": {
                                                "options": [
                                                    {"label": "Demo", "value": "demo"},
                                                    {"label": "Alpha", "value": "alpha"},
                                                    {"label": "Production", "value": "production"},
                                                ]
                                            }
                                        },
                                    )
                                ],
                                className="table-responsive",
                            )
                        ]
                    )
                ]
            ),
            # Status panel for messages
            dbc.Row([dbc.Col([html.Div(id="status-panel", className="mt-4")])]),
            # Hidden storage for state management
            dcc.Store(id="config-store", data=projects),
            dcc.Store(id="original-config-store", data=projects),
            # Download component for exports
            dcc.Download(id="download-config"),
            # Confirmation modal
            dbc.Modal(
                [
                    dbc.ModalHeader(dbc.ModalTitle("Confirm Action")),
                    dbc.ModalBody(id="modal-body"),
                    dbc.ModalFooter(
                        [
                            dbc.Button("Cancel", id="modal-cancel", color="secondary", className="me-2"),
                            dbc.Button("Confirm", id="modal-confirm", color="primary"),
                        ]
                    ),
                ],
                id="confirm-modal",
                is_open=False,
            ),
        ],
        fluid=True,
        className="p-4",
    )


def register_callbacks(app: "dash.Dash", config_manager: ProjectConfigManager):
    """
    Register Dash callbacks for interactivity.

    Args:
        app: Dash application
        config_manager: ProjectConfigManager instance
    """
    validator = ConfigValidator()

    # Shared collector for the live runtime-health summary (cached ~30s).
    try:
        from sega.probe.container_status import ContainerStatusCollector

        live_collector = ContainerStatusCollector(config_manager)
    except Exception:
        live_collector = None

    # Callback 0: Live runtime-health summary (does NOT touch the editable table).
    # Rendered as the same outline chips (dot + mono count) as the live-status page.
    @app.callback(Output("live-status-summary", "children"), Input("live-interval", "n_intervals"))
    def update_live_summary(_n):
        if live_collector is None:
            return ""
        try:
            s = live_collector.summary()
        except Exception:
            return html.Small("Live status unavailable", className="text-muted")
        counts = s.get("counts", {})
        order = [
            ("healthy", "ok"), ("running", "run"), ("unreachable", "unr"),
            ("degraded", "warn"), ("down", "down"), ("unknown", ""),
        ]
        chips = [
            html.Span([html.I(className="cdot"), html.B(str(counts[k])), k],
                      className=f"schip {cls}".strip())
            for k, cls in order if counts.get(k)
        ]
        if not chips:
            return html.Small("No live data", className="text-muted")
        return html.Div(
            [html.Span("Health", className="schip-label")] + chips,
            className="d-flex align-items-center flex-wrap",
        )

    # Callback 0b: Auto-refresh control (settings popover) → live-interval.
    # Mirrors the landing's refresh setting. "Off" disables the interval so the
    # live health summary stops polling until re-enabled.
    @app.callback(
        Output("live-interval", "interval"),
        Output("live-interval", "disabled"),
        Output("rf-15", "className"),
        Output("rf-30", "className"),
        Output("rf-60", "className"),
        Output("rf-0", "className"),
        Input("rf-15", "n_clicks"),
        Input("rf-30", "n_clicks"),
        Input("rf-60", "n_clicks"),
        Input("rf-0", "n_clicks"),
        prevent_initial_call=True,
    )
    def set_refresh(_n15, _n30, _n60, _n0):
        ctx = callback_context
        which = ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else "rf-30"
        seconds = {"rf-15": 15, "rf-30": 30, "rf-60": 60, "rf-0": 0}.get(which, 30)
        interval = seconds * 1000 if seconds > 0 else 60_000
        disabled = seconds == 0
        cls = lambda key: "seg-btn active" if key == which else "seg-btn"
        return interval, disabled, cls("rf-15"), cls("rf-30"), cls("rf-60"), cls("rf-0")

    # Callback 0c: Column visibility — the picker lists columns to SHOW; anything
    # not selected is hidden. Empty selection falls back to the default set so the
    # table never renders with zero columns.
    @app.callback(
        Output("projects-table", "hidden_columns"),
        Input("column-picker", "value"),
    )
    def set_visible_columns(visible):
        visible = visible or DEFAULT_VISIBLE_COLUMNS
        return [c["id"] for c in TABLE_COLUMNS if c["id"] not in visible]

    # Callback 1: Update table based on filters
    @app.callback(
        Output("projects-table", "data"),
        [
            Input("filter-status", "value"),
            Input("filter-category", "value"),
            Input("filter-lab", "value"),
            Input("search-box", "value"),
        ],
        State("config-store", "data"),
    )
    def update_table(status_filter, category_filter, lab_filter, search, stored_data):
        """Filter and update projects table"""
        projects = stored_data if stored_data else config_manager.get_all_projects()

        # Apply filters
        filtered = projects

        if status_filter and status_filter != "all":
            filtered = [p for p in filtered if p.get("status") == status_filter]

        if category_filter and category_filter != "all":
            filtered = [p for p in filtered if p.get("category") == category_filter]

        if lab_filter and lab_filter != "all":
            filtered = [p for p in filtered if p.get("lab_assignment") == lab_filter]

        if search:
            search_lower = search.lower()
            filtered = [
                p
                for p in filtered
                if search_lower in p.get("name", "").lower() or search_lower in p.get("slug", "").lower()
            ]

        return filtered

    # Callback 2: Track unsaved changes
    @app.callback(
        Output("unsaved-changes-badge", "children"),
        Input("projects-table", "data"),
        State("original-config-store", "data"),
    )
    def track_changes(current_data, original_data):
        """Show badge if there are unsaved changes"""
        if current_data != original_data:
            return dbc.Badge("Unsaved Changes", color="warning", className="fs-6")
        return ""

    # Callback 3: Update statistics
    @app.callback(Output("stats-display", "children"), Input("projects-table", "data"))
    def update_stats(table_data):
        """Display statistics about filtered projects"""
        if not table_data:
            return ""

        total = len(table_data)
        by_status = {}
        for p in table_data:
            status = p.get("status", "unknown")
            by_status[status] = by_status.get(status, 0) + 1

        # Same outline-chip language as the live-status page's phase chips.
        cls_map = {"production": "ok", "alpha": "warn", "demo": ""}
        stats_items = [
            html.Span("Phase", className="schip-label"),
            html.Span([html.B(str(total)), "all"], className="schip neutral"),
        ]
        for status in ("production", "alpha", "demo"):
            if by_status.get(status):
                stats_items.append(
                    html.Span([html.I(className="cdot"), html.B(str(by_status[status])), status],
                              className=f"schip {cls_map[status]}".strip())
                )
        for status, count in sorted(by_status.items()):  # any unexpected values
            if status not in cls_map:
                stats_items.append(html.Span([html.B(str(count)), status], className="schip neutral"))

        return html.Div(stats_items, className="d-flex align-items-center flex-wrap")

    # Callback 4: Validate configuration
    @app.callback(
        Output("status-panel", "children"),
        Input("btn-validate", "n_clicks"),
        State("projects-table", "data"),
        prevent_initial_call=True,
    )
    def validate_config(n_clicks, table_data):
        """Validate current configuration"""
        if not n_clicks:
            return ""

        config = {"projects": table_data}
        result = validator.validate_all(config)

        if result.is_valid:
            return dbc.Alert(
                [
                    html.H4("✓ Validation Passed", className="alert-heading"),
                    html.P(f"All {len(table_data)} projects validated successfully."),
                    html.Hr(),
                    html.P("No port conflicts or validation errors detected.", className="mb-0"),
                ],
                color="success",
                dismissable=True,
            )
        else:
            return dbc.Alert(
                [
                    html.H4("⚠ Validation Errors", className="alert-heading"),
                    html.Ul([html.Li(error) for error in result.errors]),
                    html.Hr(),
                    html.P(f"{len(result.errors)} issue(s) found. Please fix before saving.", className="mb-0"),
                ],
                color="warning",
                dismissable=True,
            )

    # Callback 5: Export configuration
    @app.callback(
        Output("download-config", "data"),
        Input("btn-export", "n_clicks"),
        State("projects-table", "data"),
        prevent_initial_call=True,
    )
    def export_config(n_clicks, table_data):
        """Export configuration to JSON file"""
        if not n_clicks:
            return None

        from datetime import datetime

        config = {"projects": table_data}
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        return dict(
            content=json.dumps(config, indent=2, ensure_ascii=False), filename=f"fleet-projects.export.{timestamp}.json"
        )

    # Callback 6: Save configuration (placeholder - will implement with modal)
    @app.callback(
        Output("modal-body", "children"),
        Output("confirm-modal", "is_open"),
        Input("btn-save", "n_clicks"),
        State("projects-table", "data"),
        prevent_initial_call=True,
    )
    def show_save_modal(n_clicks, table_data):
        """Show confirmation modal before saving"""
        if not n_clicks:
            return "", False

        # Validate first
        config = {"projects": table_data}
        result = validator.validate_all(config)

        if not result.is_valid:
            error_list = html.Ul([html.Li(error) for error in result.errors])
            modal_content = html.Div(
                [
                    html.P("Cannot save: Configuration has validation errors:"),
                    error_list,
                    html.P("Please fix these errors before saving.", className="text-danger fw-bold mt-3"),
                ]
            )
            return modal_content, True

        modal_content = html.Div(
            [
                html.P(f"You are about to save changes to {len(table_data)} projects."),
                html.P("A backup will be created automatically."),
                html.P("Do you want to continue?", className="fw-bold mt-3"),
            ]
        )

        return modal_content, True

    # Callback 7: Confirm save action
    @app.callback(
        Output("status-panel", "children", allow_duplicate=True),
        Output("confirm-modal", "is_open", allow_duplicate=True),
        Output("original-config-store", "data"),
        Input("modal-confirm", "n_clicks"),
        Input("modal-cancel", "n_clicks"),
        State("projects-table", "data"),
        prevent_initial_call=True,
    )
    def handle_save_confirmation(confirm_clicks, cancel_clicks, table_data):
        """Handle save confirmation"""
        ctx = callback_context
        if not ctx.triggered:
            return "", False, table_data

        button_id = ctx.triggered[0]["prop_id"].split(".")[0]

        if button_id == "modal-cancel":
            return "", False, table_data

        if button_id == "modal-confirm":
            try:
                config = {"projects": table_data}
                config_manager.save_config(config, backup=True)

                alert = dbc.Alert(
                    [
                        html.H4("✓ Save Successful", className="alert-heading"),
                        html.P("Configuration saved with backup created."),
                    ],
                    color="success",
                    dismissable=True,
                    duration=4000,
                )

                return alert, False, table_data

            except Exception as e:
                alert = dbc.Alert(
                    [
                        html.H4("✗ Save Failed", className="alert-heading"),
                        html.P(f"Error: {str(e)}"),
                    ],
                    color="danger",
                    dismissable=True,
                )

                return alert, False, table_data

        return "", False, table_data

    # Callback 8: Rollback to previous backup
    @app.callback(
        Output("status-panel", "children", allow_duplicate=True),
        Output("projects-table", "data", allow_duplicate=True),
        Output("config-store", "data"),
        Input("btn-rollback", "n_clicks"),
        prevent_initial_call=True,
    )
    def rollback_changes(n_clicks):
        """Rollback to last backup"""
        if not n_clicks:
            return "", [], []

        try:
            config_manager.rollback()
            projects = config_manager.get_all_projects()

            alert = dbc.Alert(
                [
                    html.H4("✓ Rollback Successful", className="alert-heading"),
                    html.P("Configuration restored from last backup."),
                ],
                color="info",
                dismissable=True,
                duration=4000,
            )

            return alert, projects, projects

        except Exception as e:
            alert = dbc.Alert(
                [
                    html.H4("✗ Rollback Failed", className="alert-heading"),
                    html.P(f"Error: {str(e)}"),
                ],
                color="danger",
                dismissable=True,
            )

            return alert, [], []

    # Callback 9: Cell-level validation highlighting
    @app.callback(Output("projects-table", "style_data_conditional"), Input("projects-table", "data"))
    def highlight_validation_errors(table_data):
        """Highlight cells with validation errors"""
        styles = [
            # Alternating row colors (base style, dark theme)
            {"if": {"row_index": "odd"}, "backgroundColor": "#1b1e21"},
            # Phase column: same color language as the live-status page's phase chips —
            # colored text only, never a cell fill (per design rules).
            {"if": {"filter_query": '{status} = "production"', "column_id": "status"},
             "color": "#4ade80", "fontWeight": "600", "textTransform": "uppercase",
             "fontSize": "11px", "letterSpacing": "0.06em"},
            {"if": {"filter_query": '{status} = "alpha"', "column_id": "status"},
             "color": "#fbbf24", "fontWeight": "600", "textTransform": "uppercase",
             "fontSize": "11px", "letterSpacing": "0.06em"},
            {"if": {"filter_query": '{status} = "demo"', "column_id": "status"},
             "color": "#8b9096", "fontWeight": "600", "textTransform": "uppercase",
             "fontSize": "11px", "letterSpacing": "0.06em"},
        ]

        if not table_data:
            return styles

        for i, project in enumerate(table_data):
            # Highlight invalid status values
            status = project.get("status", "")
            if status and not validator.validate_status(status):
                styles.append(
                    {
                        "if": {"row_index": i, "column_id": "status"},
                        "backgroundColor": "#3a1e1e",
                        "color": "#f87171",
                        "fontWeight": "bold",
                    }
                )

            # Highlight port conflicts
            if validator.has_port_conflict(project, table_data):
                # Highlight API port if there's a conflict
                if project.get("port_api"):
                    styles.append(
                        {
                            "if": {"row_index": i, "column_id": "port_api"},
                            "backgroundColor": "#3a2f12",
                            "color": "#fbbf24",
                            "fontWeight": "bold",
                        }
                    )

                # Highlight Frontend port if there's a conflict
                if project.get("port_frontend"):
                    styles.append(
                        {
                            "if": {"row_index": i, "column_id": "port_frontend"},
                            "backgroundColor": "#3a2f12",
                            "color": "#fbbf24",
                            "fontWeight": "bold",
                        }
                    )

                # Highlight Desktop port if there's a conflict
                if project.get("port_desktop"):
                    styles.append(
                        {
                            "if": {"row_index": i, "column_id": "port_desktop"},
                            "backgroundColor": "#3a2f12",
                            "color": "#fbbf24",
                            "fontWeight": "bold",
                        }
                    )

            # Check for ports out of range
            port_api = project.get("port_api")
            if port_api and (port_api < 8000 or port_api > 8099):
                styles.append(
                    {
                        "if": {"row_index": i, "column_id": "port_api"},
                        "backgroundColor": "#3a1e1e",
                        "color": "#f87171",
                        "fontWeight": "bold",
                    }
                )

            port_frontend = project.get("port_frontend")
            if port_frontend and (port_frontend < 3000 or port_frontend > 3099):
                styles.append(
                    {
                        "if": {"row_index": i, "column_id": "port_frontend"},
                        "backgroundColor": "#3a1e1e",
                        "color": "#f87171",
                        "fontWeight": "bold",
                    }
                )

            port_desktop = project.get("port_desktop")
            if port_desktop and (port_desktop < 3300 or port_desktop > 3399):
                styles.append(
                    {
                        "if": {"row_index": i, "column_id": "port_desktop"},
                        "backgroundColor": "#3a1e1e",
                        "color": "#f87171",
                        "fontWeight": "bold",
                    }
                )

        return styles


def run_dashboard(host: str = "127.0.0.1", port: int = 8015, debug: bool = False, config_path: Optional[str] = None):
    """
    Convenience function to run dashboard.

    Args:
        host: Host to bind to (default: 127.0.0.1)
        port: Port to run on (default: 8015 - SEGA backend port)
        debug: Enable debug mode (default: False)
        config_path: Optional path to fleet-projects.json
    """
    config_manager = ProjectConfigManager(config_path)
    app = create_dashboard(config_manager)

    print(f"Starting SEGA Configuration Dashboard...")
    print(f"Hub:         http://{host}:{port}/")
    print(f"Live status: http://{host}:{port}/status")
    print(f"Config:      http://{host}:{port}/config/")
    print(f"Managing: {config_manager.config_path}")

    app.run(host=host, port=port, debug=debug)
