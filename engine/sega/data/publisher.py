"""IDPPublisher — gate, upload a packaged IDP to R2 (swarm-data-products), register in
swarm's products.json. sega DOES the publish; swarm's registry is the source of truth.

The "optionally add to the published data package" is enforced HERE: the per-dataset gate
(`publish: true` + a `license`) must pass, else nothing is uploaded. See the plan doc.
"""
from __future__ import annotations

import json
import os
import subprocess
from typing import Any, Dict, Optional, Tuple

from .packager import IDPPackager


class IDPPublisher:
    def __init__(self, exporter):
        self.ex = exporter
        self.packager = IDPPackager(exporter)

    # ---- gate ------------------------------------------------------------
    @staticmethod
    def gate(dataset_spec) -> Tuple[bool, str]:
        """The publishability gate. Returns (ok, reason)."""
        if not dataset_spec.publish:
            return False, "publish=false in descriptor (flip to true once verified)"
        if not dataset_spec.license:
            return False, "no license set (required to publish)"
        return True, "ok"

    # ---- publish ---------------------------------------------------------
    def publish(self, project_spec, dataset_spec, dry_run: bool = False,
                now: Optional[str] = None) -> Dict[str, Any]:
        proj, ds = project_spec.project, dataset_spec
        ok, reason = self.gate(ds)
        if not ok:
            return {"published": False, "gate": reason, "project": proj, "dataset": ds.name}

        idp = self.packager.idp_path(proj, ds.name, ds.dataset_version)
        if not os.path.exists(os.path.join(idp, "card.json")):
            # package on demand so `publish` is one step
            self.packager.package(project_spec, ds)
        card = json.load(open(os.path.join(idp, "card.json")))

        # Respect swarm's registry (its gate, not just the descriptor's): refuse to publish over a
        # product swarm flagged firewall-protected, or to silently change a published product's license.
        conflict = self._registry_conflict(card)
        if conflict:
            return {"published": False, "gate": "ok", "project": proj, "dataset": ds.name,
                    "error": conflict}

        if not self.ex.r2_endpoint:
            return {"published": False, "gate": "ok",
                    "error": "no r2_endpoint in descriptor defaults", "project": proj}
        prefix = f"idp/{proj}_{ds.name}/{ds.dataset_version}/"
        dest = f"s3://{self.ex.r2_bucket}/{prefix}"
        # `_pending_ledger.json` is internal delta bookkeeping (staged at package, committed to the
        # per-dataset ledger at publish) — it must NOT land in the public data bucket.
        cmd = ["aws", "--profile", self.ex.r2_profile, "--endpoint-url", self.ex.r2_endpoint,
               "--region", "auto", "s3", "sync", idp, dest, "--delete",
               "--exclude", "_pending_ledger.json"]

        if dry_run:
            return {"published": False, "dry_run": True, "project": proj, "dataset": ds.name,
                    "gate": "ok", "plan": " ".join(cmd),
                    "url": f"{self.ex.r2_endpoint}/{self.ex.r2_bucket}/{prefix}"}

        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if res.returncode != 0:
            return {"published": False, "gate": "ok", "project": proj, "dataset": ds.name,
                    "error": f"R2 sync failed: {(res.stderr or '').strip()[:300]}"}
        committed = self._commit_ledger(proj, ds.name, idp) if card.get("mode") == "delta" else 0
        registered = self._register(card, prefix, now)
        return {"published": True, "project": proj, "dataset": ds.name,
                "r2_prefix": prefix, "shards": len(card.get("shards", [])),
                "registered": registered, "ledger_committed": committed}

    def _commit_ledger(self, project: str, dataset: str, idp_dir: str) -> int:
        """On successful publish of a delta version, merge its pending identities into the
        per-dataset published ledger — so the NEXT version won't re-ship these rows."""
        pending_p = os.path.join(idp_dir, "_pending_ledger.json")
        if not os.path.exists(pending_p):
            return 0
        new_ids = json.load(open(pending_p)).get("identities", [])
        existing = self.packager._load_ledger(project, dataset)
        existing.update(new_ids)
        ledger_p = self.packager.ledger_path(project, dataset)
        os.makedirs(os.path.dirname(ledger_p), exist_ok=True)
        json.dump({"identities": sorted(existing)}, open(ledger_p, "w"))
        return len(new_ids)

    # ---- registry (swarm products.json — sega writes the published entry) ----
    def _registry_conflict(self, card: Dict[str, Any]) -> Optional[str]:
        """Guard swarm's registry integrity before publishing. Returns a refusal reason or None.
        (products.json has no `visibility` field yet — when swarm adds one, gate on it here too.)"""
        reg = self.ex.products_registry
        if not reg or not os.path.exists(reg):
            return None
        try:
            products = json.load(open(reg)).get("products", [])
        except (ValueError, OSError):
            return None
        for p in products:
            if p.get("name") != card["name"]:
                continue
            if p.get("firewall_ok") is False:
                return (f"swarm registry marks '{card['name']}' firewall_ok=false — "
                        f"refusing to publish over a firewall-protected product")
            if p.get("license") and card.get("license") and p["license"] != card["license"]:
                return (f"license drift for '{card['name']}': registry has '{p['license']}', "
                        f"descriptor has '{card['license']}' — reconcile before publishing")
        return None

    def _register(self, card: Dict[str, Any], prefix: str, now: Optional[str]) -> bool:
        reg = self.ex.products_registry
        if not reg or not os.path.exists(reg):
            return False
        data = json.load(open(reg))
        products = data.setdefault("products", [])
        entry = {
            "craft_id": None,                     # sim-results extract, not a craft
            "name": card["name"], "project": card["project"], "dataset": card.get("dataset"),
            "kind": card.get("kind", "sim_results"), "truth_level": card.get("truth_level"),
            "license": card.get("license"), "version": card["version"],
            "splits": card.get("splits", {}), "shards": len(card.get("shards", [])),
            "firewall_ok": card.get("firewall_ok", True),
            "r2_prefix": prefix, "created_at": card.get("created_at") or now,
        }
        # dedupe by (name, version): replace an existing same-version entry, else append
        products[:] = [p for p in products
                       if not (p.get("name") == entry["name"] and p.get("version") == entry["version"])]
        products.append(entry)
        # atomic write — a crash mid-write must not corrupt swarm's registry
        tmp = f"{reg}.tmp"
        with open(tmp, "w") as fh:
            json.dump(data, fh, indent=2)
        os.replace(tmp, reg)
        return True
