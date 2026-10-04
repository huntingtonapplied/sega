"""SimDataExporter — extract publishable data from each simulation project's DB.

sega owns the cross-project orchestration (enumerate projects, reach each host+DB, extract,
emit a standardized extract + manifest); swarm owns the IDP standard + publishability gate
downstream. See docs/plans/SIM_DATA_EXPORT_PLAN.md.

Extraction runs ON the project's host (the DB is docker-internal), reusing the db-backup
access pattern: `ssh <host> docker exec <container> psql -U <user> -d <db> -c "\\copy (<query>)
to stdout with csv header"`. No secrets here — local peer/trust auth, same as db-backup.
"""
from __future__ import annotations

import csv
import io
import json
import os
import subprocess
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import yaml

from ..utils.paths import get_fleet_root

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG = os.path.abspath(
    os.path.join(_THIS_DIR, "..", "..", "..", "config", "sim-data-export.yaml")
)
# non-login SSH to a mini lacks colima's docker on PATH — prepend it (harmless elsewhere).
_REMOTE_PATH = "export PATH=/opt/homebrew/bin:/usr/local/bin:$PATH; "
_SSH_OPTS = ["-o", "ConnectTimeout=15", "-o", "BatchMode=yes",
             "-o", "StrictHostKeyChecking=accept-new"]


@dataclass
class TableSpec:
    name: str
    query: str
    dedup: Optional[Dict[str, Any]] = None    # {level: none|exact|by_key, key: [...], order: col}
    # Per-table connection override — for the split relational/TimescaleDB topology (hermes/hermes/
    # atlas keep timeseries in a SEPARATE container+db). None → inherit the project's coords.
    # NOTE: the fleet STANDARD is a single unified timescaledb instance (atlas/hermes); these
    # overrides exist to extract from the drifted split projects until they're consolidated.
    container: Optional[str] = None
    db: Optional[str] = None


@dataclass
class DatasetSpec:
    name: str
    description: str
    tables: List[TableSpec]
    publish: bool = False                     # gate: must be True to publish
    license: Optional[str] = None             # gate: must be set to publish
    dataset_version: str = "0.1.0"
    mode: str = "snapshot"                     # snapshot (full deduped corpus) | delta (only new rows)


@dataclass
class ProjectSpec:
    project: str
    host: str
    container: str
    user: str
    db: str
    port: Optional[int] = None
    ssh: Optional[str] = None                 # ssh target; defaults to <host>.<tailnet>
    datasets: List[DatasetSpec] = field(default_factory=list)

    def ssh_target(self, tailnet: str) -> str:
        return self.ssh or f"{self.host}.{tailnet}"


class SimDataExporter:
    """Reads the descriptor, extracts publishable tables per project → standardized extracts."""

    def __init__(self, config_path: Optional[str] = None, tailnet: str = "tailnet-example.ts.net"):
        self.config_path = config_path or DEFAULT_CONFIG
        self.tailnet = tailnet
        self._cfg = self._load()
        d = self._cfg.get("defaults", {}) or {}
        self.format = d.get("format", "parquet")
        self.staging_dir = os.path.expanduser(
            d.get("staging_dir") or str(get_fleet_root() / "data" / "sim-export"))
        self.idp_dir = os.path.expanduser(
            d.get("idp_dir") or str(get_fleet_root() / "data" / "idp"))
        self.r2_endpoint = d.get("r2_endpoint", "")
        self.r2_bucket = d.get("r2_bucket", "swarm-data-products")
        self.r2_profile = d.get("r2_profile", "fleet-r2")
        # products.json path is relative to the descriptor file's dir (config/) → resolve.
        reg = d.get("products_registry", "")
        self.products_registry = os.path.normpath(
            os.path.join(os.path.dirname(self.config_path), reg)) if reg else ""

    # ---- config ----------------------------------------------------------
    def _load(self) -> Dict[str, Any]:
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"descriptor not found: {self.config_path}")
        with open(self.config_path) as fh:
            return yaml.safe_load(fh) or {}

    def projects(self, only: Optional[str] = None) -> List[ProjectSpec]:
        out = []
        for name, p in (self._cfg.get("projects", {}) or {}).items():
            if only and name != only:
                continue
            out.append(ProjectSpec(
                project=name, host=p["host"], container=p["container"],
                user=p["user"], db=p["db"], port=p.get("port"), ssh=p.get("ssh"),
                datasets=[DatasetSpec(
                    name=ds["name"], description=ds.get("description", ""),
                    tables=[TableSpec(t["name"], t["query"], t.get("dedup"),
                                      t.get("container"), t.get("db"))
                            for t in ds.get("tables", [])],
                    publish=bool(ds.get("publish", False)), license=ds.get("license"),
                    dataset_version=str(ds.get("dataset_version", "0.1.0")),
                    mode=ds.get("mode", "snapshot"),
                ) for ds in p.get("datasets", [])],
            ))
        return out

    # ---- validation (structural lint, no DB) ----------------------------
    def validate(self, only: Optional[str] = None) -> List[Dict[str, str]]:
        """Structural lint of the descriptor — catches typos before a live run. Returns a list of
        {level: error|warn, where, issue}. No DB touched. `error`s should block a live extract."""
        import re
        issues: List[Dict[str, str]] = []
        for p in self.projects(only):
            ds_names = [d.name for d in p.datasets]
            for dup in {n for n in ds_names if ds_names.count(n) > 1}:
                issues.append({"level": "error", "where": f"{p.project}/{dup}",
                               "issue": "duplicate dataset name — IDP path collision (same idp_dir)"})
            for ds in p.datasets:
                where = f"{p.project}/{ds.name}"
                t_names = [t.name for t in ds.tables]
                for dup in {n for n in t_names if t_names.count(n) > 1}:
                    issues.append({"level": "error", "where": f"{where}/{dup}",
                                   "issue": "duplicate table name — shard overwrite in the IDP"})
                if ds.publish and not ds.license:
                    issues.append({"level": "error", "where": where,
                                   "issue": "publish=true but no license (gate will reject)"})
                if ds.mode not in ("snapshot", "delta"):
                    issues.append({"level": "error", "where": where,
                                   "issue": f"unknown mode '{ds.mode}' (want snapshot|delta)"})
                if not ds.tables:
                    issues.append({"level": "warn", "where": where, "issue": "no tables"})
                for t in ds.tables:
                    tw = f"{where}/{t.name}"
                    d = t.dedup or {}
                    lvl = d.get("level", "none")
                    if lvl not in ("none", "exact", "by_key"):
                        issues.append({"level": "error", "where": tw,
                                       "issue": f"unknown dedup level '{lvl}'"})
                    if lvl == "by_key":
                        keys = d.get("key") or []
                        if not keys:
                            issues.append({"level": "error", "where": tw,
                                           "issue": "dedup by_key with no key columns"})
                        # DISTINCT ON footgun: every key + order col must be selected by the query,
                        # else the generated `SELECT DISTINCT ON (...) ... ORDER BY ...` fails at runtime.
                        ql = t.query.lower()
                        for col in list(keys) + ([d["order"]] if d.get("order") else []):
                            if not re.search(r"\b" + re.escape(str(col).lower()) + r"\b", ql):
                                issues.append({"level": "warn", "where": tw,
                                               "issue": f"dedup col '{col}' not in query SELECT — "
                                                        f"DISTINCT ON rewrite will error"})
                    if not t.query.strip().lower().startswith("select"):
                        issues.append({"level": "warn", "where": tw,
                                       "issue": "query does not start with SELECT"})
        return issues

    # ---- planning (dry-run) ---------------------------------------------
    def plan(self, only: Optional[str] = None) -> List[Dict[str, Any]]:
        """The extraction plan — what would run, no DB touched. Drives --dry-run + `list`."""
        rows = []
        for p in self.projects(only):
            for ds in p.datasets:
                for t in ds.tables:
                    rows.append({
                        "project": p.project, "dataset": ds.name, "table": t.name,
                        "host": p.host, "ssh": p.ssh_target(self.tailnet),
                        "container": t.container or p.container, "db": t.db or p.db,
                        "user": p.user, "query": t.query,
                        "out": os.path.join(self.staging_dir, p.project, ds.name,
                                            f"{t.name}.{self.format}"),
                    })
        return rows

    # ---- extraction ------------------------------------------------------
    @staticmethod
    def dedup_query(query: str, dedup: Optional[Dict[str, Any]]) -> str:
        """Rewrite the query to de-dup at the DB (cheapest — no data movement). by_key keeps one
        row per key (newest if `order` given); exact/none are handled in the packager hash-pass."""
        if not dedup or dedup.get("level") != "by_key":
            return query
        keys = ", ".join(dedup.get("key", []))
        if not keys:
            return query
        order = f", {dedup['order']} DESC" if dedup.get("order") else ""
        return f"SELECT DISTINCT ON ({keys}) * FROM ({query}) _dd ORDER BY {keys}{order}"

    def _extract_csv(self, p: ProjectSpec, query: str,
                     container: Optional[str] = None, db: Optional[str] = None) -> str:
        """Run one \\copy over SSH and return the CSV text. Raises on failure.
        container/db override the project's coords (split relational/TimescaleDB topology)."""
        port = f"-p {p.port} " if p.port else ""
        # \copy is client-side → works for any role; escape the query's double quotes for the
        # outer double-quoted psql -c argument.
        q = query.replace('"', '\\"')
        psql = (f'docker exec {container or p.container} psql -U {p.user} -d {db or p.db} {port}'
                f'-v ON_ERROR_STOP=1 -c "\\copy ({q}) to stdout with csv header"')
        res = subprocess.run(
            ["ssh", *_SSH_OPTS, p.ssh_target(self.tailnet), _REMOTE_PATH + psql],
            capture_output=True, text=True, check=False,
        )
        if res.returncode != 0:
            raise RuntimeError(f"{p.project}: extract failed: {(res.stderr or '').strip()[:300]}")
        return res.stdout

    def _write(self, csv_text: str, out_path: str) -> Dict[str, Any]:
        """Write CSV→parquet (if pandas+pyarrow) else CSV. Returns {file, rows, bytes, fmt}."""
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        rows = max(0, csv_text.count("\n") - 1)          # minus header
        if self.format == "parquet":
            try:
                import pandas as pd
                df = pd.read_csv(io.StringIO(csv_text)) if csv_text.strip() else pd.DataFrame()
                df.to_parquet(out_path, index=False)
                return {"file": out_path, "rows": len(df), "bytes": os.path.getsize(out_path),
                        "fmt": "parquet"}
            except Exception:
                out_path = out_path.rsplit(".", 1)[0] + ".csv"   # graceful fallback
        with open(out_path, "w", newline="") as fh:
            fh.write(csv_text)
        return {"file": out_path, "rows": rows, "bytes": os.path.getsize(out_path), "fmt": "csv"}

    def extract(self, only: Optional[str] = None, dry_run: bool = False,
                now: Optional[str] = None) -> Dict[str, Any]:
        """Extract publishable tables for `only` (or all projects). Returns a summary.
        `now` = ISO timestamp for the manifest (caller supplies; None → omitted)."""
        result: Dict[str, Any] = {"dry_run": dry_run, "projects": [], "errors": []}
        for p in self.projects(only):
            pinfo = {"project": p.project, "datasets": []}
            for ds in p.datasets:
                dsdir = os.path.join(self.staging_dir, p.project, ds.name)
                manifest = {"project": p.project, "dataset": ds.name,
                            "description": ds.description, "extracted_at": now,
                            "provenance": {"host": p.host, "container": p.container,
                                           "db": p.db}, "tables": []}
                for t in ds.tables:
                    out = os.path.join(dsdir, f"{t.name}.{self.format}")
                    entry = {"name": t.name, "query": t.query, "out": out, "dedup": t.dedup}
                    if dry_run:
                        entry["planned"] = True
                    else:
                        try:
                            csv_text = self._extract_csv(
                                p, self.dedup_query(t.query, t.dedup), t.container, t.db)
                            entry.update(self._write(csv_text, out))
                        except Exception as e:                # never abort the whole run on one table
                            entry["error"] = str(e)
                            result["errors"].append(f"{p.project}/{ds.name}/{t.name}: {e}")
                    manifest["tables"].append(entry)
                if not dry_run:
                    os.makedirs(dsdir, exist_ok=True)
                    with open(os.path.join(dsdir, "manifest.json"), "w") as fh:
                        json.dump(manifest, fh, indent=2)
                pinfo["datasets"].append(manifest)
            result["projects"].append(pinfo)
        return result
