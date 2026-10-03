# fleet-project — fleet Helm chart

The parameterized Helm chart that renders any simulation/scientific project's
full Kubernetes serving stack from a single `values-<proj>.yaml`. This is the
**T1 / G1** deliverable of the production-k8s effort and the artifact `sega ship
deploy --deploy-platform k8s` (the K8sDeployer) consumes.

- **Architecture it implements:** [PRODUCTION_K8S_DEPLOYMENT_ARCHITECTURE.md](../../../../docs/architecture/infrastructure/aws/PRODUCTION_K8S_DEPLOYMENT_ARCHITECTURE.md) (fleet), plus the reference project's production-deploy architecture doc (G1).
- **How it's tested:** [K8S_DEPLOYMENT_TESTING_STANDARD.md](../../../../docs/architecture/infrastructure/aws/K8S_DEPLOYMENT_TESTING_STANDARD.md) — the L0 guards below are its static level.
- **Per-project inputs:** the reference project's docker/k8s parity plan, Appendix E (queue keys, worker entrypoints, defects).

> ⚠️ **Authored, not yet linted.** The laptop has no `helm` binary and its C++
> toolchain is broken — **validation runs on a build host**. Run the commands below there
> before trusting any render. This chart has never been applied to a cluster; the
> first live proof is RUNBOOK step 9 (sega T4 / testing-standard L5).

## What it renders

| Template | Objects | Notes |
|---|---|---|
| `config.yaml` | ConfigMap `<proj>-config` (+ `<proj>-engine-config`) | `redis_url`; engine TOML mounted into workers |
| `secret.yaml` | Secret `<proj>-secrets` | **only if `secret.create=true`** — production uses `sega secrets push` |
| `rbac.yaml` | ServiceAccount + Role + RoleBinding | worker lists pods/configmaps (K8sAdapter) |
| `redis.yaml` | StatefulSet + Service | in-cluster, AOF, auth from Secret |
| `database.yaml` | StatefulSet + Service | TimescaleDB (RDS ruled out, F4), initdb-only |
| `web.yaml` | Deployment + Service per `web.*` | api/landing/product/ide |
| `worker.yaml` | Deployment + KEDA ScaledObject | the proven E.2-reconciled shape |
| `daemons.yaml` | Deployment (+ Service) per `daemons.*` | celery, forwarder, reporter, swarm triad |
| `ingress.yaml` | one ALB Ingress | host rules derived from `web[*].host` |

## Validate (on a host with helm)

```bash
cd ~/workspace/sega/infrastructure/helm/fleet-project
helm lint . -f values-atlas.yaml
helm template atlas . -f values-atlas.yaml | kubeconform -strict -ignore-missing-schemas
# eyeball the worker + KEDA object specifically:
helm template atlas . -f values-atlas.yaml -s templates/worker.yaml
```

## L0 static guards (regression net — from testing standard §3)

These encode defects we actually hit (parity plan Appendix E.2). The chart is
built to satisfy them; a per-project values file must not reintroduce them:

1. **Queue-type-aware KEDA trigger** — `worker.keda.listName` must be a Redis
   **LIST** the coordinator writes (or a ZSET mirrored to a LIST). A raw ZSET
   returns `LLEN 0` and never scales. The reference project mirrors its ZSET into
   `atlas:jobs:pending` (`_sync_pending_depth`). The chart `required`s this value.
2. **FQDN KEDA address** — defaulted to `<proj>-redis.<ns>.svc.cluster.local:<port>`;
   a short `redis:6379` fails DNS from the `keda` namespace and never goes Ready.
3. **`REDIS_PASSWORD` supplied** — the worker template always wires it from the Secret.
4. **Worker label `app=<proj>-worker`** — hardcoded; `K8sAdapter.get_worker_status`
   selects on it.
5. **Single canonical manifest set** — this chart replaces the hand-rolled
   per-project `k8s/` + `deploy/k8s/` sets; never apply the chart *and* those.

## Onboard a sibling project

1. Copy the reference values file → `values-<proj>.yaml`.
2. Substitute the Appendix E inputs: `worker.keda.listName` (real LIST key),
   `worker.command`/`args` (real worker module), web ports, engine TOML.
3. **Blocked cases** (testing standard §2): a project with no Redis-backed queue
   (e.g. an in-memory heapq) must grow one before `worker.keda` can work; a project
   with two orchestration layers must consolidate them first. These are parity tasks (K3).
4. `helm lint . -f values-<proj>.yaml`, then run testing-standard L0–L3 locally.

## Known limitations (this first cut)

- **DB password reuses the `redis_password` Secret key** (`database.yaml`) as a
  stand-in. Split into a dedicated `db_password` key (and align `postgresql_url`)
  when wiring `sega secrets` for real. Flagged inline.
- **No PgBouncer, no wal-g sidecar** yet (deferred: D11, added when pod count /
  backups demand — architecture G-items).
- **Swarm FedAvg round protocol** (aggregator single-writer, S3 lifecycle) is
  represented only as plain daemons here; the round protocol itself is G5.
- **S3/CloudFront downloads + ALB controller/ACM/EBS-CSI** are terraform (T2),
  not this chart. The ingress annotations are placeholders until T2 supplies them.
