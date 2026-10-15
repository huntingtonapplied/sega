"""IDPPackager — build a staged extract into swarm's Swarm Dataset Package (IDP) structure.

sega packages TO swarm's DATA_PRODUCTS standard (card.json + datasheet + sharded data + sha256);
it does NOT import swarm code — the coupling is to the STANDARD (a data format), not the package.
See sega/docs/plans/SIM_DATA_EXPORT_PLAN.md and swarm/public_data/DATA_PRODUCTS.md.

IDP layout produced:
  <idp_dir>/<project>_<dataset>/<version>/
    card.json        # machine spec: schema/units, provenance, splits, license, checksums, version
    datasheet.md     # human "Datasheet for Dataset"
    data/<table>.parquet   # sharded data (sim RESULTS extract; no held-out benchmark split)
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from typing import Any, Dict, List, Optional


def _dedup_line(d) -> str:
    if not d:
        return "**Deduplication.** None applied."
    return (f"**Deduplication.** {d['methods']} → {d['rows_extracted']} extracted, "
            f"{d['dropped']} duplicate(s) dropped, {d['rows_after_dedup']} published.")


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _schema_of(path: str) -> Dict[str, Any]:
    """Columns + dtypes + row count from a parquet (pandas) or csv (header + count)."""
    if path.endswith(".parquet"):
        try:
            import pandas as pd
            df = pd.read_parquet(path)
            return {"columns": {c: str(t) for c, t in df.dtypes.items()}, "rows": len(df)}
        except Exception:
            return {"columns": {}, "rows": None}
    # csv
    try:
        with open(path) as fh:
            header = fh.readline().rstrip("\n")
            rows = sum(1 for _ in fh)
        return {"columns": {c: "unknown" for c in header.split(",")}, "rows": rows}
    except Exception:
        return {"columns": {}, "rows": None}


def _dedup_shard(path: str, dedup: dict) -> tuple:
    """De-dup a staged shard in place. Returns (rows_in, rows_out, method).
    - exact  : drop byte-identical rows (content hash of the whole row).
    - by_key : drop dups on the key cols (already SQL-deduped at extract; this enforces/verifies).
    - none   : no-op.
    Uses pandas if available; CSV falls back to a line-hash pass (exact only)."""
    level = (dedup or {}).get("level", "none")
    if level == "none":
        return None, None, "none"
    try:
        import pandas as pd
        df = pd.read_parquet(path) if path.endswith(".parquet") else pd.read_csv(path)
        n_in = len(df)
        df2 = df.drop_duplicates(subset=dedup.get("key")) if level == "by_key" else df.drop_duplicates()
        n_out = len(df2)
        if n_out != n_in:
            df2.to_parquet(path, index=False) if path.endswith(".parquet") else df2.to_csv(path, index=False)
        return n_in, n_out, level
    except ImportError:
        if level != "exact" or not path.endswith(".csv"):
            return None, None, level + "(skipped: needs pandas)"
        with open(path) as fh:
            lines = fh.readlines()
        if not lines:
            return 0, 0, "exact"
        header, seen, out = lines[0], set(), [lines[0]]
        for ln in lines[1:]:
            h = hashlib.sha256(ln.encode()).hexdigest()
            if h not in seen:
                seen.add(h); out.append(ln)
        if len(out) != len(lines):
            with open(path, "w") as fh:
                fh.writelines(out)
        return len(lines) - 1, len(out) - 1, "exact"


def _row_identity(values, keys_idx=None) -> str:
    """Stable per-row content hash. by_key → hash the key cols; else → hash the whole row."""
    parts = [str(values[i]) for i in keys_idx] if keys_idx is not None else [str(v) for v in values]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def _delta_filter(path: str, dedup: dict, ledger: set):
    """Drop rows whose identity is already in `ledger` (published in a prior version). In place.
    Returns (rows_before, rows_after, new_identities). Needs pandas; returns None if unavailable."""
    try:
        import pandas as pd
    except ImportError:
        return None
    df = pd.read_parquet(path) if path.endswith(".parquet") else pd.read_csv(path)
    n_before = len(df)
    keys = (dedup or {}).get("key") if (dedup or {}).get("level") == "by_key" else None
    keys_idx = [df.columns.get_loc(k) for k in keys] if keys else None
    ids = [_row_identity(tuple(r), keys_idx) for r in df.itertuples(index=False, name=None)]
    mask = [i not in ledger for i in ids]
    kept = df[mask]
    new_ids = [ids[j] for j, keep in enumerate(mask) if keep]
    if len(kept) != n_before:
        kept.to_parquet(path, index=False) if path.endswith(".parquet") else kept.to_csv(path, index=False)
    return n_before, len(kept), new_ids


class IDPPackager:
    def __init__(self, exporter):
        self.ex = exporter

    def ledger_path(self, project: str, dataset: str) -> str:
        """Per-dataset published-identity ledger (across versions) — the incremental record."""
        return os.path.join(self.ex.idp_dir, f"{project}_{dataset}", "published_ledger.json")

    def _load_ledger(self, project: str, dataset: str) -> set:
        p = self.ledger_path(project, dataset)
        if os.path.exists(p):
            return set(json.load(open(p)).get("identities", []))
        return set()

    def idp_path(self, project: str, dataset: str, version: str) -> str:
        return os.path.join(self.ex.idp_dir, f"{project}_{dataset}", version)

    def package(self, project_spec, dataset_spec) -> Dict[str, Any]:
        """Build the IDP for one project/dataset from its staged extract. Returns a summary
        (idp_dir, card, shards). Builds regardless of the publish gate — the gate is enforced
        at PUBLISH; a packaged-but-ungated IDP is fine to inspect locally."""
        proj, ds = project_spec.project, dataset_spec
        staged = os.path.join(self.ex.staging_dir, proj, ds.name)
        if not os.path.isdir(staged):
            raise FileNotFoundError(f"no staged extract at {staged} — run `sega data extract` first")
        manifest_path = os.path.join(staged, "manifest.json")
        manifest = json.load(open(manifest_path)) if os.path.exists(manifest_path) else {}

        idp = self.idp_path(proj, ds.name, ds.dataset_version)
        datadir = os.path.join(idp, "data")
        os.makedirs(datadir, exist_ok=True)

        delta = ds.mode == "delta"
        # delta filtering + by_key shard-dedup need pandas; without it they'd silently no-op and ship
        # un-deduplicated / already-published rows. Fail loud instead (exact dedup has a CSV fallback).
        needs_pandas = delta or any((t.dedup or {}).get("level") == "by_key" for t in ds.tables)
        if needs_pandas:
            try:
                import pandas  # noqa: F401
            except ImportError:
                raise RuntimeError(
                    f"{proj}/{ds.name}: mode=delta or by_key dedup requires pandas "
                    f"(pip install pandas pyarrow) — refusing to ship un-deduplicated data")
        ledger = self._load_ledger(proj, ds.name) if delta else set()
        pending_ids: List[str] = []                               # new identities → committed at publish
        incr = {"rows_before_incremental": 0, "rows_new": 0} if delta else None

        shards: List[Dict[str, Any]] = []
        schema: Dict[str, Any] = {}
        total_rows = 0
        for t in ds.tables:
            for ext in (self.ex.format, "csv", "parquet"):        # find the staged file
                src = os.path.join(staged, f"{t.name}.{ext}")
                if os.path.exists(src):
                    break
            else:
                shards.append({"table": t.name, "missing": True})
                continue
            dst = os.path.join(datadir, os.path.basename(src))
            shutil.copy2(src, dst)
            n_in, n_out, method = _dedup_shard(dst, t.dedup)     # de-dup in place
            shard = {"table": t.name, "file": f"data/{os.path.basename(dst)}"}
            if n_in is not None:
                shard["dedup"] = {"method": method, "rows_extracted": n_in,
                                  "rows_after_dedup": n_out, "dropped": n_in - n_out}
            if delta:                                             # drop rows published in a prior version
                df = _delta_filter(dst, t.dedup, ledger)
                if df:
                    b, a, new_ids = df
                    pending_ids.extend(new_ids)
                    incr["rows_before_incremental"] += b
                    incr["rows_new"] += a
                    shard["incremental"] = {"rows_before": b, "rows_new": a, "carried_forward": b - a}
            sch = _schema_of(dst)                                 # schema/sha AFTER dedup + delta
            schema[t.name] = {"query": t.query, **sch}
            total_rows += sch.get("rows") or 0
            shard.update({"sha256": _sha256(dst), "rows": sch.get("rows"),
                          "bytes": os.path.getsize(dst)})
            shards.append(shard)

        if delta:                                                 # stage pending ids; publish commits them
            os.makedirs(idp, exist_ok=True)
            json.dump({"identities": pending_ids}, open(os.path.join(idp, "_pending_ledger.json"), "w"))

        # dataset-level dedup provenance (honesty — goes on the datasheet)
        ded = [s["dedup"] for s in shards if s.get("dedup")]
        dedup_summary = {
            "rows_extracted": sum(d["rows_extracted"] for d in ded),
            "rows_after_dedup": sum(d["rows_after_dedup"] for d in ded),
            "dropped": sum(d["dropped"] for d in ded),
            "methods": sorted({d["method"] for d in ded}),
        } if ded else None

        card = {
            "schema_version": "1.0",
            "name": f"{proj}_{ds.name}",
            "project": proj,
            "dataset": ds.name,
            "description": ds.description,
            "kind": "sim_results",                # DB-extracted simulation results (not ML train/test)
            "truth_level": "engine",              # real engine output (vs closed_form / generated)
            "license": ds.license,
            "version": ds.dataset_version,
            "created_at": manifest.get("extracted_at"),
            "provenance": manifest.get("provenance", {}),
            "splits": {"corpus": total_rows},     # raw results corpus; no held-out benchmark split
            "firewall_ok": True,                  # no benchmark test-set to protect for raw results
            "mode": ds.mode,                      # snapshot | delta
            "dedup": dedup_summary,               # rows_extracted → after_dedup, methods (provenance)
            "incremental": incr,                  # delta: rows_before_incremental → rows_new (vs prior versions)
            "shards": [s for s in shards if not s.get("missing")],
            "schema": schema,
        }
        with open(os.path.join(idp, "card.json"), "w") as fh:
            json.dump(card, fh, indent=2)
        self._write_datasheet(idp, card)
        return {"idp_dir": idp, "rows": total_rows,
                "shards": len(card["shards"]), "missing": [s["table"] for s in shards if s.get("missing")],
                "card": card}

    @staticmethod
    def _write_datasheet(idp: str, card: Dict[str, Any]) -> None:
        prov = card.get("provenance", {})
        tables = "\n".join(f"- `{n}` — {m.get('rows', '?')} rows, {len(m.get('columns', {}))} cols "
                           f"(query: `{m.get('query', '')[:80]}`)"
                           for n, m in (card.get("schema") or {}).items())
        md = f"""# Datasheet — {card['name']} v{card['version']}

**Purpose.** {card.get('description', '')}

**Composition.** Simulation *results* extracted from the {card['project']} project database
(`{prov.get('db', '?')}` on `{prov.get('host', '?')}`, container `{prov.get('container', '?')}`).
Corpus: {card['splits'].get('corpus', '?')} rows across {len(card.get('shards', []))} shard(s).

Tables:
{tables}

**Provenance.** Extracted {card.get('created_at') or '(unset)'} by `sega data`. Truth level:
`{card['truth_level']}` (real engine output). Each shard is sha256-checksummed in `card.json`.
{_dedup_line(card.get('dedup'))}

**Uses.** Research/analysis of {card['project']} simulation outputs. **Limits.** These are raw
engine results, not an ML benchmark — there is no held-out eval split; do not treat as a
train/test dataset without defining one.

**License.** {card.get('license') or '(UNSET — not publishable until set)'}.

**Citation.** Huntington Applied — {card['name']} v{card['version']}.
"""
        with open(os.path.join(idp, "datasheet.md"), "w") as fh:
            fh.write(md)
