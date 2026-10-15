#!/usr/bin/env python3
"""Drive K8sFleetDeployer directly until `sega ship k8s` is wired into the router.

Runs on the build/provision host. Imports the deployer, builds a spec,
and runs either a dry-run plan or the finally-wrapped test (provision -> deploy ->
hold -> teardown, with the TTL self-terminate as the backstop).

    python run_k8s_fleet_test.py --dry-run                 # no AWS spend — plan + prereq checks
    python run_k8s_fleet_test.py --arch amd64 --hold 600   # LIVE: spins up EC2, tears down after
    python run_k8s_fleet_test.py --keep                    # leave it up (TTL still self-terminates)
"""
import argparse
import base64
import os
import re
import secrets
import subprocess
import sys

# sega must be importable; default to the standard checkout on the provision host.
SEGA_ENGINE = os.path.expanduser(os.environ.get("SEGA_ENGINE", "~/workspace/sega/engine"))
if SEGA_ENGINE not in sys.path:
    sys.path.insert(0, SEGA_ENGINE)


def _existing_db_pw(project: str):
    """Return the DB password already stored in the running release's secret, so a
    re-deploy reuses the password baked into the (persistent, initdb-skipped) PVC
    instead of minting a fresh one that no longer matches. None if not found."""
    try:
        out = subprocess.run(
            ["kubectl", "--context", f"sega-{project}", "-n", project, "get", "secret",
             f"{project}-secrets", "-o", "jsonpath={.data.postgresql_url}"],
            capture_output=True, text=True, timeout=15)
        raw = (out.stdout or "").strip()
        if not raw:
            return None
        url = base64.b64decode(raw).decode()
        m = re.search(r"://[^:]+:([^@]+)@", url)
        return m.group(1) if m else None
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", default="atlas")
    ap.add_argument("--arch", default="amd64", choices=["amd64", "arm64"],
                    help="amd64 for build-host images (default); arm64 for mini-built")
    ap.add_argument("--sim-nodes", type=int, default=2)
    ap.add_argument("--hold", type=int, default=600, help="seconds to hold before auto-teardown")
    ap.add_argument("--keep", action="store_true", help="skip teardown (TTL still terminates)")
    ap.add_argument("--spot", action="store_true", help="spot sim pool (unsafe while DB shares nodes)")
    ap.add_argument("--dry-run", action="store_true", help="plan + prereq checks, no AWS spend")
    ap.add_argument("--test", action="store_true", help="one-shot: deploy -> hold -> auto-teardown")
    ap.add_argument("--teardown", action="store_true", help="destroy the fleet (terminate + sweep)")
    ap.add_argument("--no-ebs", action="store_true", help="skip EBS/IAM profile; use k3s local-path")
    ap.add_argument("--image-delivery", default="sideload", choices=["sideload", "baked-ami"],
                    help="baked-ami = launch nodes from a pre-baked image (no sideload, ~90s)")
    ap.add_argument("--bake-from", default=None, help="snapshot this node name into a baked AMI, then exit")
    ap.add_argument("--build-and-bake", action="store_true",
                    help="build image in-region on a builder + bake a baked-AMI, then exit (optimal)")
    ap.add_argument("--ttl", type=int, default=90, help="node TTL self-terminate minutes")
    ap.add_argument("--decommission-idle", action="store_true",
                    help="scale-DOWN: terminate sim nodes running 0 app pods (KEDA drained)")
    ap.add_argument("--min-keep", type=int, default=0, help="sim nodes to keep warm on decommission")
    ap.add_argument("--overlay", default=None,
                    help="values overlay filename under the chart dir to layer instead of the "
                         "default values-<project>-test.yaml (e.g. values-atlas-hybridtest.yaml "
                         "for the mini-data-plane + EC2-engine hybrid test)")
    ap.add_argument("--external-data", action="store_true",
                    help="DB/Redis live outside the cluster (hybrid: mac mini over tailnet); the "
                         "overlay supplies their creds — skip in-cluster secret/PVC injection")
    a = ap.parse_args()

    import secrets
    from sega.ship.deployers.k8s_fleet import K8sFleetDeployer, K8sFleetSpec

    spec = K8sFleetSpec(project=a.project, arch=a.arch, sim_nodes=a.sim_nodes,
                        spot=a.spot, image_delivery=a.image_delivery, ttl_minutes=a.ttl)
    # Layer an overlay over the base values-<project>.yaml: --overlay wins, else the
    # default brief-test overlay (in-cluster DB/redis on gp3, ingress off), if present.
    overlay = os.path.join(spec.helm_chart, a.overlay or f"values-{a.project}-test.yaml")
    if os.path.exists(overlay):
        spec.extra_values_files = [overlay]
        print(f"overlay: {os.path.basename(overlay)}")
    # Throwaway creds for the isolated, torn-down cluster (never real/committed).
    # REUSE the password already baked into a persistent PVC's initdb, else a
    # re-run mints a new pw while initdb (skipped on a non-empty local-path PVC)
    # keeps the old one -> "password authentication failed" (hit live 2026-08-01).
    spec.helm_set = {}
    if a.external_data:
        # Hybrid: the DB/Redis live OUTSIDE the cluster (e.g. a mac mini over the
        # tailnet) and the overlay supplies their creds. Do NOT inject in-cluster
        # secret overrides — a `--set` here would clobber the overlay's external creds.
        print("external-data: skipping in-cluster DB/redis secret injection (overlay owns the data plane)")
    else:
        # Throwaway creds for the isolated, torn-down cluster (never real/committed).
        # REUSE the password already baked into a persistent PVC's initdb, else a
        # re-run mints a new pw while initdb (skipped on a non-empty local-path PVC)
        # keeps the old one -> "password authentication failed" (hit live 2026-08-01).
        pw = os.environ.get("TEST_DB_PW") or _existing_db_pw(a.project) or secrets.token_hex(16)
        spec.helm_set = {
            "secret.data.redisPassword": pw,
            "secret.data.postgresqlUrl":
                f"postgresql://{a.project}:{pw}@{a.project}-postgres:5432/{a.project}",
        }
    # One backend image, tagged as both api + worker (the chart references both).
    spec.sideload_images = [f"{a.project}/api:latest", f"{a.project}/worker:latest"]
    if a.no_ebs:  # no iam:CreateRole for this account -> skip EBS, use k3s local-path
        spec.use_ebs = False
        if not a.external_data:   # only relevant when in-cluster DB/redis PVCs exist
            spec.helm_set["database.persistence.storageClass"] = "local-path"
            spec.helm_set["redis.persistence.storageClass"] = "local-path"

    dep = K8sFleetDeployer()
    if a.build_and_bake:
        ami = dep.build_and_bake(spec)
        print(f"\nBAKED AMI: {ami} (name={spec.baked_ami_name}) — provision with --image-delivery baked-ami")
        return 0
    if a.bake_from:
        ami = dep.bake_ami(spec, a.bake_from)
        print(f"\nBAKED AMI: {ami} (name={spec.baked_ami_name}) — reuse with --image-delivery baked-ami")
        return 0
    if a.decommission_idle:
        result = dep.decommission_idle(spec, min_keep=a.min_keep, dry_run=a.dry_run)
    elif a.teardown:
        result = dep.teardown(spec, destroy_infra=True, yes=True)
    elif a.dry_run:
        result = dep.deploy_fleet(spec, dry_run=True)
    elif a.test:
        result = dep.deploy_test(spec, hold_seconds=a.hold, keep=a.keep)
    else:  # default: provision + deploy, KEEP up for iterating (TTL still self-terminates)
        result = dep.deploy_fleet(spec)

    ok = bool(getattr(result, "success", False))
    print(f"\n{'OK' if ok else 'FAIL'}: {getattr(result, 'message', result)}")
    md = getattr(result, "metadata", None)
    if md:
        print("metadata:", md)
    err = getattr(result, "error", None)
    if err:
        print("error:", err)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
