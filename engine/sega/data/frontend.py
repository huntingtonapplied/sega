#!/usr/bin/env python3
"""
sega data frontend — generate each project's landing-app `dataProductsData.ts`
from the two data-catalog sources of truth, so the /data page can never drift.

The join (LEFT, catalog-driven):

    swarm/public_data/catalog.json   (authored PRESENTATION copy — one file, all
                                       projects: modality / description / schema+
                                       units / truth notes / highlights)
                 ×
    swarm/public_data/products.json  (machine REGISTRY of what is actually
                                       PUBLISHED — written by `sega data publish`:
                                       version / license / splits / r2_prefix)
                 →
    <project>/frontend/landing_app/.../dataProductsData.ts   (GENERATED — never
                                       hand-edited; consumed by DataProductsSection)

Division of truth:
  * REGISTRY owns status / version / license / download+datasheet URLs. A dataset
    reads "coming-soon" until a registry entry exists AND a public base URL is
    configured — so the page is honest by construction (nothing links to a bucket
    key that isn't hosted yet).
  * CATALOG owns the human copy (authored once per project; truthLevel/truthNote
    stay authored to avoid the registry's machine truth_level enum leaking in).

Stdlib only (json / pathlib) so it runs anywhere without the sega venv; the
`sega data frontend` CLI command is a thin wrapper over `generate_project()`.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Repo-root-relative locations of the two SOT files + per-project output paths.
CATALOG_REL = "swarm/public_data/catalog.json"
REGISTRY_REL = "swarm/public_data/products.json"

# Where each project's landing app consumes the generated catalog, from the
# `[fleet.data_frontend_outputs]` config map (add a config row to bring a new
# project online; ships empty for new installs).
def _output_rel() -> Dict[str, str]:
    from sega.core.config import get_config
    return dict(get_config().fleet.data_frontend_outputs)


OUTPUT_REL: Dict[str, str] = _output_rel()


def repo_root(start: Optional[Path] = None) -> Path:
    """Walk up to the ~/fleet monorepo root (the dir holding swarm/ + sega/)."""
    p = (start or Path(__file__)).resolve()
    for anc in [p, *p.parents]:
        if (anc / CATALOG_REL).exists() and (anc / REGISTRY_REL).exists():
            return anc
    # Fallback: assume this file lives at sega/engine/sega/data/frontend.py
    return Path(__file__).resolve().parents[4]


def _version_key(version: Any) -> Tuple[Tuple[int, int, str], ...]:
    """Numeric-aware sort key for dotted version strings (0.10.0 > 0.9.0).

    Non-numeric segments sort after numeric ones and compare as strings,
    so malformed versions never raise — they just lose to real ones.
    """
    parts: List[Tuple[int, int, str]] = []
    for seg in str(version).split("."):
        try:
            parts.append((0, int(seg), ""))
        except ValueError:
            parts.append((1, 0, seg))
    return tuple(parts)


def _registry_index(registry: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """name -> latest published registry entry (highest version wins on dupes)."""
    idx: Dict[str, Dict[str, Any]] = {}
    for p in registry.get("products", []):
        name = p.get("name")
        if not name:
            continue
        prev = idx.get(name)
        if prev is None or _version_key(p.get("version", "")) >= _version_key(prev.get("version", "")):
            idx[name] = p
    return idx


def _resolve_status(
    cat_product: Dict[str, Any],
    reg_entry: Optional[Dict[str, Any]],
    data_base_url: Optional[str],
) -> Tuple[str, Optional[str], Optional[str], str, str]:
    """Return (status, downloadUrl, datasheetUrl, version, license).

    Published ONLY when a registry entry exists AND we can form a real public URL
    (registry has an r2_prefix AND a base URL is configured). Otherwise coming-soon
    with the authored fallbacks — never a dangling link.
    """
    version = str(cat_product.get("version", "0.1.0"))
    license_ = cat_product.get("license", "CC-BY-4.0")
    if reg_entry:
        version = str(reg_entry.get("version", version))
        license_ = reg_entry.get("license", license_)
        prefix = reg_entry.get("r2_prefix")
        if data_base_url and prefix:
            base = data_base_url.rstrip("/") + "/" + str(prefix).strip("/")
            return "published", base, f"{base}/datasheet.md", version, license_
    return "coming-soon", None, None, version, license_


def build_products(
    project: str,
    catalog: Dict[str, Any],
    registry: Dict[str, Any],
    data_base_url: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Join one project's authored catalog against the published registry."""
    proj = catalog.get("projects", {}).get(project)
    if proj is None:
        raise KeyError(f"project '{project}' not found in {CATALOG_REL}")
    reg_idx = _registry_index(registry)

    products: List[Dict[str, Any]] = []
    for c in proj.get("products", []):
        reg_entry = reg_idx.get(c.get("registryName") or c.get("idpId"))
        status, dl, ds, version, license_ = _resolve_status(c, reg_entry, data_base_url)
        entry: Dict[str, Any] = {
            "idpId": c["idpId"],
            "title": c["title"],
            "modality": c["modality"],
            "description": c["description"],
            "version": version,
            "status": status,
            "inputSchema": c.get("inputSchema", []),
            "outputSchema": c.get("outputSchema", []),
            "truthLevel": c["truthLevel"],
            "truthNote": c["truthNote"],
            "license": license_,
            "splitNote": c["splitNote"],
            "downloadUrl": dl,
            "datasheetUrl": ds,
        }
        if c.get("highlight"):
            entry["highlight"] = c["highlight"]
        products.append(entry)

    intro = proj.get("intro", {"noExternalEquivalent": False, "note": ""})
    return products, intro


# ---- TS emission --------------------------------------------------------------

_HEADER = """/**
 * GENERATED FILE — DO NOT EDIT.
 *
 * Produced by `sega data frontend --project {project}` from the two data-catalog
 * sources of truth:
 *   - swarm/public_data/catalog.json   (authored presentation copy)
 *   - swarm/public_data/products.json  (published registry, written by publish)
 *
 * Edit the COPY in catalog.json; edit STATUS/URLs by publishing (products.json).
 * Re-run the generator to refresh this file. This keeps the /data page from
 * drifting away from what is actually published.
 */
"""

_TYPES = '''
/** Honest truth-level flag — never claim engine-truth for a closed-form oracle. */
export type TruthLevel = "engine_truth" | "closed_form_oracle" | "synthetic" | "mixed";

export type DataStatus = "published" | "coming-soon";

export interface SchemaField {
  /** field name as it appears on disk (e.g. "node_features", "targets.φ_p") */
  name: string;
  /** shape summary, e.g. "[N, 50]" or "per node" */
  shape: string;
  /** physical unit(s), or "—" when dimensionless / categorical */
  unit: string;
}

export interface DataProductInfo {
  /** stable id (matches the IDP directory name idp/<id>/) */
  idpId: string;
  title: string;
  /** one-line modality label, e.g. "Device mesh graph" */
  modality: string;
  /** longer human summary of what the dataset is */
  description: string;
  version: string;
  status: DataStatus;
  /** input-side schema fields (shape + units) */
  inputSchema: SchemaField[];
  /** output/target-side schema fields (shape + units) */
  outputSchema: SchemaField[];
  truthLevel: TruthLevel;
  /** human truth-level note (what "truth" means for this set) */
  truthNote: string;
  license: string;
  /** how the canonical held-out test split is reserved as the eval firewall */
  splitNote: string;
  /** headline claim / why this dataset is novel (optional) */
  highlight?: string;
  /** stable public URL for the sharded archive (null until hosted) */
  downloadUrl: string | null;
  /** the human "Datasheet for Dataset" (null until published) */
  datasheetUrl: string | null;
}
'''


def render_ts(project: str, products: List[Dict[str, Any]], intro: Dict[str, Any]) -> str:
    intro_ts = json.dumps(intro, indent=2, ensure_ascii=False)
    products_ts = json.dumps(products, indent=2, ensure_ascii=False)
    return (
        _HEADER.format(project=project)
        + _TYPES
        + f"\nexport const dataIntro = {intro_ts};\n"
        + f"\nexport const dataProducts: DataProductInfo[] = {products_ts};\n"
    )


def generate_project(
    project: str,
    root: Optional[Path] = None,
    data_base_url: Optional[str] = None,
    write: bool = True,
) -> str:
    """Generate (and optionally write) one project's dataProductsData.ts."""
    root = root or repo_root()
    catalog = json.loads((root / CATALOG_REL).read_text())
    registry = json.loads((root / REGISTRY_REL).read_text())
    products, intro = build_products(project, catalog, registry, data_base_url)
    ts = render_ts(project, products, intro)
    if write:
        out_rel = OUTPUT_REL.get(project)
        if not out_rel:
            raise KeyError(f"no landing-app output path registered for '{project}' in OUTPUT_REL")
        out = root / out_rel
        out.write_text(ts)
    return ts


def projects_in_catalog(root: Optional[Path] = None) -> List[str]:
    root = root or repo_root()
    catalog = json.loads((root / CATALOG_REL).read_text())
    return sorted(catalog.get("projects", {}).keys())


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Generate dataProductsData.ts from the data-catalog SOT.")
    ap.add_argument("--project", help="project name (default: all in catalog with an output path)")
    ap.add_argument("--data-base-url", default=None, help="public base URL for hosted IDPs (e.g. https://data.example.com); omit to keep everything coming-soon")
    ap.add_argument("--dry-run", action="store_true", help="print the generated TS, do not write")
    args = ap.parse_args()

    root = repo_root()
    targets = [args.project] if args.project else [p for p in projects_in_catalog(root) if p in OUTPUT_REL]
    for proj in targets:
        ts = generate_project(proj, root=root, data_base_url=args.data_base_url, write=not args.dry_run)
        if args.dry_run:
            print(ts)
        else:
            print(f"generated {OUTPUT_REL[proj]} ({ts.count(chr(10))} lines)")
