{{/*
Project name — the short identifier that drives resource names and labels.
*/}}
{{- define "fleet-project.name" -}}
{{- .Values.project.name | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Namespace — explicit override, else the project name.
*/}}
{{- define "fleet-project.namespace" -}}
{{- default .Values.project.name .Values.project.namespace -}}
{{- end -}}

{{/*
Secret name the workloads reference (created out-of-band by `sega secrets push`,
or by this chart when .Values.secret.create).
*/}}
{{- define "fleet-project.secretName" -}}
{{- default (printf "%s-secrets" (include "fleet-project.name" .)) .Values.secret.name -}}
{{- end -}}

{{/*
ServiceAccount name.
*/}}
{{- define "fleet-project.serviceAccountName" -}}
{{- default (printf "%s-worker" (include "fleet-project.name" .)) .Values.serviceAccount.name -}}
{{- end -}}

{{/*
Common labels applied to every object.
*/}}
{{- define "fleet-project.labels" -}}
app.kubernetes.io/part-of: {{ include "fleet-project.name" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" }}
{{- end -}}

{{/*
Fully-qualified image reference from a component image map.
Usage: include "fleet-project.image" (dict "root" $ "image" .componentImage)
Falls back to the global registry/tag when the component omits them.
*/}}
{{- define "fleet-project.image" -}}
{{- $root := .root -}}
{{- $img := .image | default dict -}}
{{- $registry := $img.registry | default $root.Values.image.registry -}}
{{- $repo := $img.repository -}}
{{- $tag := $img.tag | default $root.Values.image.tag -}}
{{- if $registry -}}
{{- printf "%s/%s:%s" $registry $repo $tag -}}
{{- else -}}
{{- printf "%s:%s" $repo $tag -}}
{{- end -}}
{{- end -}}

{{/*
Redis in-cluster Service name / host.
*/}}
{{- define "fleet-project.redisHost" -}}
{{- printf "%s-redis" (include "fleet-project.name" .) -}}
{{- end -}}

{{/*
Database in-cluster Service name / host.
*/}}
{{- define "fleet-project.dbHost" -}}
{{- printf "%s-postgres" (include "fleet-project.name" .) -}}
{{- end -}}

{{/*
Worker liveness/readiness probe body.
Usage: include "fleet-project.workerProbe" (dict "worker" $w "initialDelay" 30)

worker.probe.type selects the probe kind (default "redis-ping" — a python
redis-ping exec, the proven python-worker default; reference projects unchanged):
  redis-ping  — python -c redis.from_url(...).ping()   [default]
  exec        — arbitrary exec command (worker.probe.command) — e.g. a Rust
                worker's `["atlas-engine","--health-check"]`. Rust images
                have NO python binary, so redis-ping would crash-loop them.
  tcp         — tcpSocket on worker.probe.port (Rust workers exposing a port)
  none        — no probe (caller skips this block)
Timing is overridable via worker.probe.{periodSeconds,timeoutSeconds,failureThreshold}.
*/}}
{{- define "fleet-project.workerProbe" -}}
{{- $w := .worker -}}
{{- $p := $w.probe | default dict -}}
{{- $type := $p.type | default "redis-ping" -}}
{{- if eq $type "redis-ping" }}
exec:
  command:
    - python
    - -c
    - "import os,redis; redis.from_url(os.environ['REDIS_URL'], password=os.environ.get('REDIS_PASSWORD') or None).ping()"
{{- else if eq $type "exec" }}
exec:
  command:
    {{- toYaml (required "worker.probe.command is required when worker.probe.type=exec" $p.command) | nindent 4 }}
{{- else if eq $type "tcp" }}
tcpSocket:
  port: {{ required "worker.probe.port is required when worker.probe.type=tcp" $p.port }}
{{- end }}
initialDelaySeconds: {{ $p.initialDelaySeconds | default .initialDelay }}
periodSeconds: {{ $p.periodSeconds | default .initialDelay }}
timeoutSeconds: {{ $p.timeoutSeconds | default 5 }}
failureThreshold: {{ $p.failureThreshold | default 3 }}
{{- end -}}
