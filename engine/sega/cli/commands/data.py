"""`sega data` — cross-project simulation-data extraction → published data package.

sega orchestrates (enumerate projects, reach each host+DB, extract, stage a standardized
extract); swarm gates + packages downstream (IDP standard + products.json + license/firewall).
See sega/docs/plans/SIM_DATA_EXPORT_PLAN.md.
"""
import sys
from datetime import datetime, timezone

import click

from ...data.exporter import SimDataExporter
from ...data.packager import IDPPackager
from ...data.publisher import IDPPublisher


@click.group()
def data():
    """Extract simulation data from project DBs into the published data package (IDP)."""


@data.command(name="list")
@click.option("--project", default=None, help="Single project (default: all)")
@click.option("--config", default=None, help="Descriptor path override")
def list_plan(project, config):
    """Show the extraction plan — what would be pulled from where (no DB touched).

    \b
    Example:
        sega data list
        sega data list --project hermes
    """
    ex = SimDataExporter(config_path=config)
    rows = ex.plan(only=project)
    if not rows:
        click.echo(f"no datasets in descriptor{' for ' + project if project else ''}")
        return
    click.echo(f"{'PROJECT':<12} {'DATASET':<26} {'TABLE':<18} SOURCE")
    for r in rows:
        click.echo(f"{r['project']:<12} {r['dataset']:<26} {r['table']:<18} "
                   f"{r['ssh']} docker exec {r['container']} psql -d {r['db']}")
    click.echo(f"\n{len(rows)} table(s); staged to {ex.staging_dir} as .{ex.format}")


@data.command(name="validate")
@click.option("--project", default=None, help="Single project (default: all)")
@click.option("--config", default=None, help="Descriptor path override")
def validate_cfg(project, config):
    """Structural lint of the descriptor — catches typos before a live run (no DB touched).

    Checks dedup blocks are well-formed, by_key dedup columns are actually SELECTed (the
    DISTINCT-ON footgun), publish/license coherence, and query shape. Exits 1 on any error.
    """
    ex = SimDataExporter(config_path=config)
    issues = ex.validate(only=project)
    if not issues:
        click.echo("✓ descriptor OK (no structural issues)")
        return
    errors = [i for i in issues if i["level"] == "error"]
    for i in issues:
        sym = "✗" if i["level"] == "error" else "⚠"
        click.echo(f"  {sym} [{i['level']}] {i['where']}: {i['issue']}",
                   err=i["level"] == "error")
    click.echo(f"\n{len(errors)} error(s), {len(issues) - len(errors)} warning(s)")
    if errors:
        sys.exit(1)


@data.command()
@click.option("--project", default=None, help="Single project (default: all)")
@click.option("--dry-run", is_flag=True, help="Print the plan; touch no DB")
@click.option("--config", default=None, help="Descriptor path override")
def extract(project, dry_run, config):
    """Extract publishable tables per the descriptor → standardized extract + manifest.

    Runs on each project's host (`ssh <host> docker exec <container> psql \\copy`); writes
    parquet/csv + a manifest.json per dataset to the staging dir. Downstream: swarm packages
    the staged extract as an IDP (license/visibility gate), then sega publishes to R2.

    \b
    Examples:
        sega data extract --dry-run          # see exactly what will run
        sega data extract --project hermes     # extract one project for real
    """
    ex = SimDataExporter(config_path=config)
    now = datetime.now(timezone.utc).isoformat()
    res = ex.extract(only=project, dry_run=dry_run, now=now)

    tables = ok = 0
    for p in res["projects"]:
        for ds in p["datasets"]:
            for t in ds["tables"]:
                tables += 1
                mark = "PLAN" if dry_run else ("OK  " if "error" not in t else "FAIL")
                if mark == "OK  ":
                    ok += 1
                extra = (f"{t.get('rows', '?')} rows -> {t.get('file', t['out'])}"
                         if not dry_run and "error" not in t else t.get("error", t["out"]))
                click.echo(f"  [{mark}] {p['project']}/{ds['dataset']}/{t['name']}: {extra}")

    if dry_run:
        click.echo(f"\n(dry-run) {tables} table(s) planned; re-run without --dry-run to extract.")
    elif res["errors"]:
        click.echo(f"\n✗ {ok}/{tables} extracted; {len(res['errors'])} failed:", err=True)
        for e in res["errors"]:
            click.echo(f"    {e}", err=True)
        sys.exit(1)
    else:
        click.echo(f"\n✓ {ok}/{tables} table(s) extracted to {ex.staging_dir}")


@data.command()
@click.option("--project", default=None, help="Single project (default: all)")
@click.option("--config", default=None, help="Descriptor path override")
def package(project, config):
    """Package staged extracts into Swarm Dataset Packages (card.json + datasheet + sharded data).

    Builds the IDP structure per swarm's DATA_PRODUCTS standard; does NOT publish (see `publish`).
    """
    ex = SimDataExporter(config_path=config)
    pk = IDPPackager(ex)
    n = 0
    for p in ex.projects(only=project):
        for ds in p.datasets:
            try:
                r = pk.package(p, ds)
                miss = f" (MISSING: {', '.join(r['missing'])})" if r["missing"] else ""
                click.echo(f"  [OK] {p.project}/{ds.name} v{ds.dataset_version}: "
                           f"{r['shards']} shard(s), {r['rows']} rows -> {r['idp_dir']}{miss}")
                n += 1
            except Exception as e:
                click.echo(f"  [FAIL] {p.project}/{ds.name}: {e}", err=True)
    click.echo(f"\n{n} IDP(s) built under {ex.idp_dir}")


@data.command()
@click.option("--project", default=None, help="Single project (default: all)")
@click.option("--dry-run", is_flag=True, help="Gate + print the R2 plan; upload nothing")
@click.option("--config", default=None, help="Descriptor path override")
def publish(project, dry_run, config):
    """Gate → upload the IDP to R2 (swarm-data-products) → register in swarm's products.json.

    The gate (`publish: true` + a `license` in the descriptor) is enforced here — this is where
    "optionally add to the published data package" is decided. Packages on demand if needed.

    \b
    Examples:
        sega data publish --dry-run          # see the gate verdict + R2 plan
        sega data publish --project hermes     # publish hermes's datasets that pass the gate
    """
    from datetime import datetime, timezone
    ex = SimDataExporter(config_path=config)
    pub = IDPPublisher(ex)
    now = datetime.now(timezone.utc).isoformat()
    published = gated = failed = 0
    for p in ex.projects(only=project):
        for ds in p.datasets:
            r = pub.publish(p, ds, dry_run=dry_run, now=now)
            tag = f"{p.project}/{ds.name} v{ds.dataset_version}"
            if r.get("dry_run"):
                click.echo(f"  [PLAN] {tag}: gate ok -> {r['plan']}")
            elif r.get("published"):
                click.echo(f"  [PUBLISHED] {tag}: {r['shards']} shard(s) -> {r['r2_prefix']} "
                           f"(registered: {r['registered']})")
                published += 1
            elif r.get("gate") and not r.get("error"):
                click.echo(f"  [GATED] {tag}: {r['gate']}")
                gated += 1
            else:
                click.echo(f"  [FAIL] {tag}: {r.get('error', 'unknown')}", err=True)
                failed += 1
    if not dry_run:
        click.echo(f"\n{published} published, {gated} gated (not published), {failed} failed")
        if failed:
            sys.exit(1)


@data.command()
@click.option("--project", default=None, help="Single project (default: all in the catalog with a landing-app output path)")
@click.option("--data-base-url", default=None, help="Public base URL for hosted IDPs (e.g. https://data.atlas.app); omit to keep everything 'coming-soon'")
@click.option("--dry-run", is_flag=True, help="Print the generated TS; write nothing")
def frontend(project, data_base_url, dry_run):
    """Generate each project's landing-app `dataProductsData.ts` from the catalog SOT.

    Joins the authored copy (swarm/public_data/catalog.json) with the published
    registry (swarm/public_data/products.json) so the /data page can never drift
    from what is actually published. A dataset stays 'coming-soon' until it has a
    registry entry AND a --data-base-url is given (so no link ever dangles).

    \b
    Examples:
        sega data frontend --project atlas
        sega data frontend --project atlas --data-base-url https://data.atlas.app
        sega data frontend --dry-run
    """
    from ...data.frontend import generate_project, projects_in_catalog, repo_root, OUTPUT_REL

    root = repo_root()
    targets = [project] if project else [p for p in projects_in_catalog(root) if p in OUTPUT_REL]
    if not targets:
        click.echo("no projects to generate (none in the catalog have a landing-app output path)")
        return
    for proj in targets:
        ts = generate_project(proj, root=root, data_base_url=data_base_url, write=not dry_run)
        if dry_run:
            click.echo(ts)
        else:
            click.echo(f"  [GENERATED] {proj}: {OUTPUT_REL[proj]} ({ts.count(chr(10))} lines)")
