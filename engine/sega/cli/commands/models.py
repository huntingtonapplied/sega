#!/usr/bin/env python3
"""
SEGA MODELS — neural-net weight distribution
==============================================================================
File: engine/sega/cli/commands/models.py
Purpose: Publish Swarm craft weight bundles (safetensors + card + checksums)
         to downloads.<domain>/models/, and build the shared Model Zoo
         catalog that links to them.

Companion to `sega downloads` (nginx/SSL infra) and `sega binaries` (CLI/desktop
artifacts). Reuses the same /var/www/downloads/<project> roots — models live
under a sibling `models/` path next to `cli/` and `desktop/`.

Producer side (staging bundles) is `swarm publish`. This command ships them.
Ref: ~/fleet/swarm/docs/MODEL_PUBLISHING_PLAN.md
==============================================================================
"""

import hashlib
import json
import subprocess
import urllib.request
from pathlib import Path

import click

from ...core.config import get_config
from ...infrastructure import get_instance, get_ssh_key_path, get_ssh_options
from .downloads import PROJECT_DOMAINS


# Cloudflare fronts the downloads subdomains and blocks the bare Python-urllib
# User-Agent with a 403; present a browser-like UA for live verification fetches.
_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) sega-models-verify/1.0"


def _default_local_root() -> str:
    if Path("/opt/homebrew/var/www").exists():
        return "/opt/homebrew/var/www"
    if Path("/usr/local/var/www").exists():
        return "/usr/local/var/www"
    return str(Path.cwd())


def _staged_projects(staging: Path):
    """Yield (project, models_dir) for each project tree under the swarm staging root."""
    for proj_dir in sorted(p for p in staging.iterdir() if p.is_dir()):
        models_dir = proj_dir / "models"
        if models_dir.is_dir():
            yield proj_dir.name, models_dir


@click.group()
def models():
    """Publish & catalog neural-net weight bundles (downloads.<domain>/models/)."""
    pass


# --------------------------------------------------------------------------
# publish
# --------------------------------------------------------------------------
@models.command()
@click.option("--staging", "-s", type=click.Path(exists=True, file_okay=False, path_type=Path),
              default=Path.home() / "fleet" / "swarm" / "dist" / "models", show_default=True,
              help="Swarm staging root produced by `swarm publish` (contains <project>/models/…)")
@click.option("--project", "-p", help="Publish a single project (default: every staged project)")
@click.option("--local", is_flag=True, help="Publish to local nginx root (no SSH)")
@click.option("--local-root", default=None, help="Local web root (default: auto-detect Homebrew nginx root)")
@click.option("--instance", "-i", type=int, default=None, help="Target EC2 instance number")
@click.option("--dry-run", is_flag=True, help="Show what would be shipped")
def publish(staging, project, local, local_root, instance, dry_run):
    """Ship staged model bundles to /var/www/downloads/<project>/models/."""
    if local and instance is not None:
        raise click.ClickException("Use either --local or --instance, not both")
    if not local and instance is None:
        raise click.ClickException("Specify exactly one of: --local or --instance")

    instance_config = None
    if instance is not None:
        instance_config = get_instance(str(instance))
        if not instance_config or not instance_config.ip:
            raise click.ClickException(f"Unknown/invalid instance: {instance}")

    targets = [(p, d) for p, d in _staged_projects(staging) if not project or p == project]
    if not targets:
        raise click.ClickException(f"No staged model bundles found under {staging}"
                                   + (f" for project '{project}'" if project else ""))

    for proj, models_dir in targets:
        _publish_one(proj, models_dir, local, local_root, instance_config, dry_run)


def _stage_package_tarball(project, dest_models_dir, local, ssh_key=None, ssh_opts=None, host=None):
    """(Re-)stage the runnable `<project>-models.tar.gz` INTO the CDN models dir, right
    after the `--delete` mirror above (which would otherwise leave the tarball wiped —
    it shares the mirrored dir). Built from the compiled package at
    `open_source/_build/<project>-models/` (produced by `swarm package` /
    build-models-package.py). No-op if no package has been built yet."""
    import tempfile, shutil
    pkg_build = Path.home() / "fleet" / "open_source" / "_build" / f"{project}-models"
    if not pkg_build.exists() or not list((pkg_build / "dist").glob("*.whl")):
        return  # no package built for this project — skip silently
    tmp = Path(tempfile.mkdtemp(prefix=f"{project}-pkgtar-"))
    try:
        stg = tmp / f"{project}-models"; stg.mkdir()
        for whl in (pkg_build / "dist").glob("*.whl"):
            shutil.copy(whl, stg)
        for f in ("README.md", "LICENSE"):
            if (pkg_build / f).exists():
                shutil.copy(pkg_build / f, stg)
        pkg_models = pkg_build / f"{project}_models" / "models"
        if pkg_models.exists():
            shutil.copytree(pkg_models, stg / "models")
        subprocess.run("shasum -a 256 * models/*/* > SHA256SUMS 2>/dev/null || true",
                       shell=True, cwd=stg)
        tarball = tmp / f"{project}-models.tar.gz"
        subprocess.run(["tar", "-czf", str(tarball), "-C", str(tmp), f"{project}-models"], check=True)
        if local:
            shutil.copy(tarball, Path(dest_models_dir) / f"{project}-models.tar.gz")
        else:
            subprocess.run(["scp", *ssh_opts, "-i", str(ssh_key), str(tarball),
                            f"{host}:/tmp/{project}-models.tar.gz"], check=True)
            subprocess.run(["ssh", *ssh_opts, "-i", str(ssh_key), host,
                            f"sudo mv /tmp/{project}-models.tar.gz '{dest_models_dir}/' && "
                            f"sudo chown www-data:www-data '{dest_models_dir}/{project}-models.tar.gz'"],
                           check=True)
        click.echo(f"  ✓ staged {project}-models.tar.gz (package)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _publish_one(project, models_dir, local, local_root, instance_config, dry_run):
    if local:
        root = f"{(local_root or _default_local_root()).rstrip('/')}/downloads/{project}"
        dest = f"{root}/models"
        click.echo(f"\n[{project}] local → {dest}")
        crafts = [c.name for c in models_dir.iterdir() if c.is_dir()]
        click.echo(f"  crafts: {', '.join(crafts) or '(none)'}")
        if dry_run:
            click.echo("  (dry-run)")
            return
        subprocess.run(["mkdir", "-p", dest], check=True)
        # ADD/UPDATE only — NEVER `--delete`. The swarm staging dir carries only the LATEST
        # version per craft, so `--delete` would wipe every older `{version}/` prefix already
        # on the CDN — destroying release history and violating VERSIONING_STANDARDS §3
        # (immutable `{version}/`). Observed: it silently 404'd published 0.1.0 bundles when
        # 0.2.0 shipped. A new version = a new prefix added; old prefixes stay. (The remote
        # `--instance` branch below is already additive via `cp -r`.) The exporter removes a
        # stale safetensors from staging when a craft turns card-only, so no cross-version
        # prune is needed here. Trailing slash: copy contents into dest/.
        subprocess.run(["rsync", "-a", f"{models_dir}/", f"{dest}/"], check=True)
        click.echo("  ✓ published (add/update, versions preserved)")
        _stage_package_tarball(project, dest, local=True)
    else:
        ssh_key = get_ssh_key_path()
        ssh_opts = get_ssh_options()
        host = instance_config.ssh_host
        remote_root = f"/var/www/downloads/{project}"
        remote_models = f"{remote_root}/models"
        tmp = f"/tmp/models-{project}"
        click.echo(f"\n[{project}] {host} → {remote_models}")
        crafts = [c.name for c in models_dir.iterdir() if c.is_dir()]
        click.echo(f"  crafts: {', '.join(crafts) or '(none)'}")
        if dry_run:
            click.echo("  (dry-run)")
            return
        # rsync tree to a tmp staging on the host (no sudo needed there), then sudo-move into place
        subprocess.run(
            ["rsync", "-a", "-e", f"ssh -i {ssh_key} " + " ".join(ssh_opts),
             f"{models_dir}/", f"{host}:{tmp}/"],
            check=True,
        )
        deploy = (
            f"sudo mkdir -p '{remote_models}' && "
            f"sudo cp -r '{tmp}/.' '{remote_models}/' && "
            f"rm -rf '{tmp}' && "
            f"sudo chown -R www-data:www-data '{remote_root}' && "
            f"sudo chmod -R 755 '{remote_root}'"
        )
        subprocess.run(["ssh", *ssh_opts, "-i", str(ssh_key), host, deploy], check=True)
        _stage_package_tarball(project, remote_models, local=False, ssh_key=ssh_key,
                               ssh_opts=ssh_opts, host=host)
        dom = PROJECT_DOMAINS.get(project)
        click.echo("  ✓ published")
        if dom:
            click.echo(f"  → https://downloads.{dom}/models/")


# --------------------------------------------------------------------------
# verify
# --------------------------------------------------------------------------
@models.command()
@click.option("--project", "-p", required=True, help="Project to verify (uses its download domain)")
@click.option("--staging", "-s", type=click.Path(exists=True, file_okay=False, path_type=Path),
              default=Path.home() / "fleet" / "swarm" / "dist" / "models", show_default=True)
def verify(project, staging):
    """HTTP + SHA256 check the live /models bundles for a project."""
    dom = PROJECT_DOMAINS.get(project)
    if not dom:
        raise click.ClickException(f"No download domain mapped for '{project}'")
    idx = staging / project / "models" / "index.json"
    if not idx.exists():
        raise click.ClickException(f"No local index.json to verify against: {idx}")
    manifest = json.loads(idx.read_text())
    base = f"https://downloads.{dom}/models"
    ok = fail = 0
    for craft_id, node in manifest.get("crafts", {}).items():
        for version, v in node.get("versions", {}).items():
            for fname, expected in (v.get("files") or {}).items():
                url = f"{base}/{craft_id}/{version}/{fname}"
                try:
                    # Cloudflare 403s the default Python-urllib UA; send a browser-like one.
                    req = urllib.request.Request(url, headers={"User-Agent": _UA})
                    with urllib.request.urlopen(req, timeout=20) as r:
                        got = hashlib.sha256(r.read()).hexdigest()
                    if got == expected:
                        ok += 1
                    else:
                        fail += 1
                        click.echo(f"  ✗ CHECKSUM {url}")
                except Exception as e:  # noqa: BLE001
                    fail += 1
                    click.echo(f"  ✗ {url} — {e}")
    click.echo(f"\n{project}: {ok} OK, {fail} failed  ({base}/)")
    if fail:
        raise click.Abort()
    click.echo("✓ all live bundles match local checksums")


# --------------------------------------------------------------------------
# frontend — generate the landing-page modelsData.ts from the staged index
# --------------------------------------------------------------------------
def _size_label(n):
    if not n:
        return "—"
    return f"{n / 1024:.0f} KB" if n < 1024 * 1024 else f"{n / 1024 / 1024:.1f} MB"


def _semver_key(v):
    out = []
    for part in str(v).split("."):
        digits = "".join(ch for ch in part if ch.isdigit())
        out.append(int(digits) if digits else 0)
    return tuple(out)


def _build_release_history(staging: Path, project: str) -> list:
    """Per-craft headline eval metric ACROSS releases, for the landing progression chart.
    Read from the REGISTRY (the staged index only carries the latest version; the registry
    keeps per-version history). Only crafts with >=1 numeric metric point are emitted —
    an honest empty state otherwise. The chart really populates once a 2nd release lands."""
    reg_path = staging.parent.parent / "data" / "models" / "registry.json"
    if not reg_path.exists():
        return []
    reg = json.loads(reg_path.read_text()).get("crafts", {})
    out = []
    for craft_id, entry in sorted(reg.items()):
        if not craft_id.startswith(project + "_"):
            continue
        versions = entry.get("versions", {})
        # Pick the craft's headline metric (consistent across its versions).
        metric_key = metric_label = None
        lower_is_better = True
        for node in versions.values():
            m = node.get("metrics") or node.get("validation_metrics") or {}
            if isinstance(m.get("best_val_loss"), (int, float)):
                metric_key, metric_label, lower_is_better = "best_val_loss", "val loss", True
                break
            if isinstance(m.get("held_out_accuracy"), (int, float)):
                metric_key, metric_label, lower_is_better = "held_out_accuracy", "accuracy", False
                break
        if not metric_key:
            continue
        points = []
        for ver in sorted(versions, key=_semver_key):
            m = versions[ver].get("metrics") or versions[ver].get("validation_metrics") or {}
            val = m.get(metric_key)
            points.append({"version": ver, "value": val if isinstance(val, (int, float)) else None})
        if any(p["value"] is not None for p in points):
            title = craft_id.replace("_", " ").replace(f"{project} ", "").title()
            out.append({"craftId": craft_id, "title": title, "metric": metric_label,
                        "lowerIsBetter": lower_is_better, "points": points})
    return out


@models.command()
@click.option("--project", "-p", required=True, help="Project whose landing app to generate modelsData.ts for")
@click.option("--staging", "-s", type=click.Path(exists=True, file_okay=False, path_type=Path),
              default=Path.home() / "fleet" / "swarm" / "dist" / "models", show_default=True)
@click.option("--license", "license_id", default="LicenseRef-FLEET-Model-EULA-1.0", show_default=True)
@click.option("-o", "--out", "out_path", type=click.Path(path_type=Path), default=None,
              help="Override output path (default: <project>/frontend/landing_app/src/components/Pages/Models/modelsData.ts)")
def frontend(project, staging, license_id, out_path):
    """Generate the landing-app modelsData.ts (static data for the Models section)."""
    idx = staging / project / "models" / "index.json"
    if not idx.exists():
        raise click.ClickException(f"No staged index.json: {idx}")
    manifest = json.loads(idx.read_text())
    dom = PROJECT_DOMAINS.get(project)
    base = f"https://downloads.{dom}/models" if dom else "/models"

    rows = []
    for craft_id, node in sorted(manifest.get("crafts", {}).items()):
        latest = node.get("latest")
        v = (node.get("versions") or {}).get(latest, {})
        m = v.get("metrics") or {}
        metric = m.get("best_val_loss", m.get("final_val_loss"))
        metric_str = f"val loss {metric:.4f}" if isinstance(metric, (int, float)) else "—"
        title = craft_id.replace("_", " ").replace(f"{project} ", "").title()

        # Full performance.json (parity/error/speedup) for the Models charts,
        # read from the staged bundle. None for untrained/not-yet-evaluated
        # crafts — the page then shows an honest empty state, never fake curves.
        perf_path = staging / project / "models" / craft_id / (latest or "") / "performance.json"
        performance = json.loads(perf_path.read_text()) if perf_path.exists() else None

        # Physical input schema (field -> description) from the craft's PUBLIC config —
        # drives the domain-neutral "what you provide" on the landing page. Empty when
        # the craft's device_family has no rich schema yet (honest generic fallback).
        cfg_path = staging / project / "models" / craft_id / (latest or "") / "config.json"
        input_schema = {}
        if cfg_path.exists():
            cfg = json.loads(cfg_path.read_text())
            input_schema = ((cfg.get("input") or {}).get("fields")) or {}

        rows.append({
            "craftId": craft_id,
            "title": title,
            "version": latest,
            # Generic on purpose — the model topology is compiled inside the package,
            # not advertised (see MODEL_INFERENCE_PACKAGE_STRATEGY.md §3).
            "architecture": "neural inference surrogate",
            "status": v.get("status", "trained"),
            "weightsPublished": v.get("weights_published", True),
            "parameters": f"{v.get('total_parameters', 0):,}",
            "inputFeatures": v.get("input_features") or v.get("node_feature_dim"),
            "nodeFeatureDim": v.get("node_feature_dim"),
            "edgeFeatureDim": v.get("edge_feature_dim"),
            "outputCount": v.get("output_count") or len(v.get("output_channels") or []),
            "sizeLabel": _size_label(v.get("size_bytes")),
            "format": "safetensors",
            "license": license_id,
            "channels": v.get("output_channels") or [],
            "inputSchema": input_schema,
            "metric": metric_str,
            "tags": v.get("tags") or [],
            "downloadUrl": (f"{base}/{craft_id}/{latest}/model.safetensors"
                            if v.get("weights_published", True) else None),
            "cardUrl": f"{base}/{craft_id}/{latest}/README.md",
            "bundleUrl": f"{base}/{craft_id}/{latest}/",
            "performance": performance,
        })

    # Package-level metadata for the Models-page headline (pip install + bundle).
    # The inference package is the primary path; the per-craft safetensors are demoted.
    package = {
        "packageName": f"{project}-models",
        "pipInstall": f"pip install {project}-models",
        "bundleTarballUrl": f"{base}/{project}-models.tar.gz",
    }
    release_history = _build_release_history(staging, project)
    ts = _render_models_ts(rows, package, release_history)
    dest = out_path or (Path.home() / "fleet" / project / "frontend" / "landing_app"
                        / "src" / "components" / "Pages" / "Models" / "modelsData.ts")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(ts)
    click.echo(f"✓ generated {len(rows)} model row(s) → {dest}")


def _render_models_ts(rows, package=None, release_history=None) -> str:
    body = json.dumps(rows, indent=2)
    package = package or {"packageName": "", "pipInstall": "", "bundleTarballUrl": ""}
    pkg_body = json.dumps(package, indent=2)
    rh_body = json.dumps(release_history or [], indent=2)
    return (
        "/**\n"
        " * Model weights data — GENERATED by `sega models frontend`.\n"
        " * Do not edit by hand; regenerate from swarm's published index.json.\n"
        " */\n\n"
        "/**\n"
        " * Standardized eval-metrics artifact (performance.json) — see\n"
        " * docs/standards/models/MODEL_PERFORMANCE_METRICS_STANDARD.md.\n"
        " * `null` when a craft is untrained / not yet evaluated. Any inner block\n"
        " * may be null when that metric could not be computed; charts hide it.\n"
        " */\n"
        "export interface ModelPerformance {\n"
        "  schema_version: string;\n"
        "  provenance?: Record<string, unknown>;\n"
        "  convergence?: { epochs: number[]; train_loss: number[] | null; val_loss: number[] | null } | null;\n"
        "  channel_error?: { channel: string; unit: string | null; rel_error_pct: number; mae: number; rmse: number }[] | null;\n"
        "  parity?: { channel: string; unit: string | null; r2: number | null; slope: number | null; n_samples: number; samples: [number, number][] }[] | null;\n"
        "  error_distribution?: { channel: string; unit: string | null; bin_edges_pct: number[]; counts: number[] }[] | null;\n"
        "  speedup?: { surrogate_ms: number | null; reference_ms: number | null; reference_name: string | null; speedup_factor: number | null; measured: boolean } | null;\n"
        "}\n\n"
        "export interface ModelInfo {\n"
        "  craftId: string;\n"
        "  title: string;\n"
        "  version: string;\n"
        "  status: string;\n"
        "  weightsPublished: boolean;\n"
        "  architecture: string;\n"
        "  parameters: string;\n"
        "  inputFeatures: number | null;\n"
        "  nodeFeatureDim: number | null;\n"
        "  edgeFeatureDim: number | null;\n"
        "  outputCount: number;\n"
        "  sizeLabel: string;\n"
        "  format: string;\n"
        "  license: string;\n"
        "  channels: string[];\n"
        "  inputSchema?: Record<string, string>;\n"
        "  metric: string;\n"
        "  tags: string[];\n"
        "  downloadUrl: string | null;\n"
        "  cardUrl: string;\n"
        "  bundleUrl: string;\n"
        "  performance: ModelPerformance | null;\n"
        "}\n\n"
        "/** Package-level metadata for the Models-page headline (the primary path). */\n"
        "export interface ModelPackage {\n"
        "  packageName: string;\n"
        "  pipInstall: string;\n"
        "  bundleTarballUrl: string;\n"
        "}\n\n"
        f"export const modelPackage: ModelPackage = {pkg_body};\n\n"
        "/** Per-craft headline eval metric across releases — drives the release-progression\n"
        " *  chart. Populates once a craft has >=2 published versions. */\n"
        "export interface ReleasePoint { version: string; value: number | null }\n"
        "export interface ReleaseHistory {\n"
        "  craftId: string;\n"
        "  title: string;\n"
        "  metric: string;\n"
        "  lowerIsBetter: boolean;\n"
        "  points: ReleasePoint[];\n"
        "}\n\n"
        f"export const releaseHistory: ReleaseHistory[] = {rh_body};\n\n"
        f"export const models: ModelInfo[] = {body};\n"
    )


# --------------------------------------------------------------------------
# catalog
# --------------------------------------------------------------------------
def _model_zoo_default() -> Path:
    """Default Model Zoo catalog path, from `[fleet] model_zoo_path` config."""
    rel = get_config().fleet.model_zoo_path or "shared/model-zoo.json"
    return Path.home() / "fleet" / rel


@models.command()
@click.option("--staging", "-s", type=click.Path(exists=True, file_okay=False, path_type=Path),
              default=Path.home() / "fleet" / "swarm" / "dist" / "models", show_default=True)
@click.option("-o", "--out", "out_path", type=click.Path(path_type=Path),
              default=_model_zoo_default(),
              show_default=True,
              help="Where to write the merged Model Zoo catalog (default: the shared frontend "
                   "dir the Model Zoo page imports from)")
def catalog(staging, out_path):
    """Merge every project's index.json into the Model Zoo catalog."""
    entries = []
    for project, models_dir in _staged_projects(staging):
        idx = models_dir / "index.json"
        if not idx.exists():
            continue
        manifest = json.loads(idx.read_text())
        dom = PROJECT_DOMAINS.get(project)
        base = f"https://downloads.{dom}/models" if dom else None
        for craft_id, node in manifest.get("crafts", {}).items():
            latest = node.get("latest")
            v = (node.get("versions") or {}).get(latest, {})
            entries.append({
                "craft_id": craft_id,
                "project": project,
                "domain": dom,
                "latest_version": latest,
                "status": v.get("status", "trained"),
                "weights_published": v.get("weights_published", True),
                "total_parameters": v.get("total_parameters"),
                "input_features": v.get("input_features") or v.get("node_feature_dim"),
                "node_feature_dim": v.get("node_feature_dim"),
                "edge_feature_dim": v.get("edge_feature_dim"),
                "output_count": v.get("output_count") or len(v.get("output_channels") or []),
                "size_bytes": v.get("size_bytes"),
                "metrics": v.get("metrics"),
                "performance": v.get("performance"),  # compact eval summary (mean_r2, speedup_factor, …); None if unevaluated
                "tags": v.get("tags"),
                "output_channels": v.get("output_channels"),
                "download_url": (f"{base}/{craft_id}/{latest}/model.safetensors"
                                 if base and v.get("weights_published", True) else None),
                "model_card_url": f"{base}/{craft_id}/{latest}/README.md" if base else None,
                "bundle_url": f"{base}/{craft_id}/{latest}/" if base else None,
            })
    catalog_doc = {
        "generated_by": "sega models catalog",
        "count": len(entries),
        "projects": sorted({e["project"] for e in entries}),
        "models": sorted(entries, key=lambda e: (e["project"], e["craft_id"])),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(catalog_doc, indent=2) + "\n")
    click.echo(f"✓ catalog: {len(entries)} model(s) across {len(catalog_doc['projects'])} project(s)")
    click.echo(f"  → {out_path}")
