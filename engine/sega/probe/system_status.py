#!/usr/bin/env python3
# Copyright 2022-2026 Huntington Applied
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
System Status Collector
=======================
Live host metrics (load, CPU, memory, disk) for the physical machines the FLEET
platform runs on — the "systems of interest" (Mac minis, NODE-5, future EC2).

This is the dashboard-facing sibling of the ``sega sysmon`` CLI: same signals
and thresholds (see sega/system/sysmon/lib/config.sh), but collected in-process
over SSH so the Live Status page can render a Systems strip. One SSH round-trip
per host runs a small POSIX script that works on both macOS and Linux; every
failure degrades to status "unreachable" — nothing here raises on a dead host.

Hosts are declared in ``config/system_monitors.yaml`` (mounted into the
container next to domain_registry.yaml). The SSH key is staged to a 0600
tempfile before use because the container mount may carry looser permissions
than the ssh CLI accepts.

Thresholds (percent, mirroring sysmon defaults):
  disk 75/90 · memory 80/95 · cpu (load1/cores) 70/90
"""

from __future__ import annotations

import os
import re
import stat
import subprocess
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

S_OK = "ok"
S_WARN = "warn"
S_CRITICAL = "critical"
S_UNREACHABLE = "unreachable"

_SEVERITY = {S_OK: 0, S_WARN: 1, S_CRITICAL: 2}

# One round-trip metrics script. @-prefixed markers keep parsing order-proof;
# the /proc/meminfo branch covers Linux, the sysctl/vm_stat branch macOS.
_METRICS_SCRIPT = (
    'echo "@OS $(uname -s)"; '
    'echo "@UPTIME $(uptime)"; '
    'echo "@CPUS $( (nproc 2>/dev/null || sysctl -n hw.ncpu) 2>/dev/null )"; '
    'echo "@DISK $(df -k / | tail -1)"; '
    "if [ -r /proc/meminfo ]; then "
    "awk '/^MemTotal:/{print \"@MEMTOTALKB\", $2} /^MemAvailable:/{print \"@MEMAVAILKB\", $2}' /proc/meminfo; "
    "else "
    'echo "@MEMBYTES $(sysctl -n hw.memsize)"; '
    'echo "@PAGESIZE $(sysctl -n hw.pagesize)"; '
    "vm_stat | awk -F'[:.]' "
    "'/Pages active/{print \"@PGACTIVE\", $2} "
    "/Pages wired down/{print \"@PGWIRED\", $2} "
    "/Pages occupied by compressor/{print \"@PGCOMP\", $2}'; "
    "fi"
)


def _worst(*statuses: str) -> str:
    return max(statuses, key=lambda s: _SEVERITY.get(s, 0))


def _threshold(value: Optional[float], warn: float, critical: float) -> str:
    if value is None:
        return S_OK  # missing metric must not paint the host red
    if value >= critical:
        return S_CRITICAL
    if value >= warn:
        return S_WARN
    return S_OK


class SystemStatusCollector:
    """Collect live host metrics for every system in system_monitors.yaml."""

    DISK_THRESHOLDS = (75.0, 90.0)
    MEM_THRESHOLDS = (80.0, 95.0)
    CPU_THRESHOLDS = (70.0, 90.0)  # load1 / cores, as a percentage

    def __init__(
        self,
        config_path: Optional[Path] = None,
        ssh_timeout: int = 8,
        cache_ttl: float = 30.0,
    ):
        self.ssh_timeout = ssh_timeout
        self.cache_ttl = cache_ttl
        self._config = self._load_config(config_path) or {}
        self._defaults = self._config.get("defaults", {}) or {}
        self._systems: List[Dict[str, Any]] = self._config.get("systems", []) or []

        self._cache: List[Dict[str, Any]] = []
        self._cache_ts: float = 0.0
        self._lock = threading.Lock()
        self._staged_keys: Dict[str, str] = {}  # source path -> 0600 tempfile

    # -- config --------------------------------------------------------------
    @staticmethod
    def _load_config(path: Optional[Path]) -> Optional[Dict[str, Any]]:
        if yaml is None:
            return None
        if path is None:
            here = Path(__file__).resolve()
            for parent in here.parents:
                cand = parent / "config" / "system_monitors.yaml"
                if cand.exists():
                    path = cand
                    break
        if not path or not Path(path).exists():
            return None
        try:
            with open(path) as f:
                return yaml.safe_load(f)
        except Exception:
            return None

    # -- ssh -----------------------------------------------------------------
    def _key_path(self, host: Dict[str, Any]) -> Optional[str]:
        raw = (
            os.environ.get("SEGA_SYSMON_SSH_KEY")
            or host.get("ssh_key")
            or self._defaults.get("ssh_key")
        )
        if not raw:
            return None
        src = str(Path(raw).expanduser())
        if not Path(src).is_file():
            return None
        # ssh rejects group/other-readable keys, and a bind mount from the mac
        # host typically arrives world-readable — stage a private 0600 copy.
        staged = self._staged_keys.get(src)
        if staged and Path(staged).is_file():
            return staged
        try:
            mode = Path(src).stat().st_mode
            if not (mode & (stat.S_IRGRP | stat.S_IROTH)):
                return src  # already private; use as-is
            fd, tmp = tempfile.mkstemp(prefix="sega-sysmon-key-")
            with os.fdopen(fd, "wb") as out, open(src, "rb") as inp:
                out.write(inp.read())
            os.chmod(tmp, 0o600)
            self._staged_keys[src] = tmp
            return tmp
        except Exception:
            return src

    def _ssh(self, host: Dict[str, Any], command: str) -> Optional[str]:
        user = host.get("user") or self._defaults.get("user") or "ubuntu"
        addr = host.get("address")
        if not addr:
            return None
        cmd = ["ssh"]
        key = self._key_path(host)
        if key:
            cmd += ["-i", key]
        cmd += [
            "-o", "BatchMode=yes",
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "LogLevel=ERROR",
            "-o", f"ConnectTimeout={self.ssh_timeout}",
            f"{user}@{addr}",
            command,
        ]
        try:
            r = subprocess.run(
                cmd, capture_output=True, text=True, timeout=self.ssh_timeout * 2
            )
        except Exception:
            return None
        return r.stdout if r.returncode == 0 else None

    # -- parsing ---------------------------------------------------------------
    @staticmethod
    def _parse_markers(text: str) -> Dict[str, str]:
        out: Dict[str, str] = {}
        for line in (text or "").splitlines():
            if line.startswith("@") and " " in line:
                k, v = line[1:].split(" ", 1)
                out[k] = v.strip()
        return out

    @staticmethod
    def _parse_load(uptime_line: str) -> Optional[float]:
        # linux: "load average: 1.20, 0.80, 0.60" · macOS: "load averages: 1.20 0.80 0.60"
        m = re.search(r"load averages?:\s*([\d.]+)", uptime_line or "")
        return float(m.group(1)) if m else None

    @staticmethod
    def _parse_uptime(uptime_line: str) -> str:
        m = re.search(r"up\s+(.*?),\s*\d+\s+users?", uptime_line or "")
        return m.group(1).strip() if m else ""

    @staticmethod
    def _parse_disk(df_line: str) -> tuple[Optional[float], Optional[float], Optional[float]]:
        """Return (total_gb, used_gb, used_pct) from a `df -k /` data row."""
        parts = (df_line or "").split()
        if len(parts) < 5:
            return None, None, None
        try:
            total = float(parts[1]) / 1024 / 1024
            used = float(parts[2]) / 1024 / 1024
            pct = float(parts[4].rstrip("%"))
            return round(total, 1), round(used, 1), pct
        except (ValueError, IndexError):
            return None, None, None

    def _parse_memory(self, mk: Dict[str, str]) -> tuple[Optional[float], Optional[float]]:
        """Return (total_gb, used_pct) from marker dict (Linux or macOS shape)."""
        try:
            if "MEMTOTALKB" in mk:
                total_kb = float(mk["MEMTOTALKB"])
                avail_kb = float(mk.get("MEMAVAILKB", 0))
                pct = (total_kb - avail_kb) / total_kb * 100 if total_kb else None
                return round(total_kb / 1024 / 1024, 1), round(pct, 1) if pct is not None else None
            if "MEMBYTES" in mk:
                total = float(mk["MEMBYTES"])
                page = float(mk.get("PAGESIZE", 16384))
                used_pages = sum(
                    float(mk.get(k, "0").strip() or 0)
                    for k in ("PGACTIVE", "PGWIRED", "PGCOMP")
                )
                pct = used_pages * page / total * 100 if total else None
                return round(total / 1024**3, 1), round(pct, 1) if pct is not None else None
        except (ValueError, ZeroDivisionError):
            pass
        return None, None

    # -- per host --------------------------------------------------------------
    def _collect_host(self, host: Dict[str, Any]) -> Dict[str, Any]:
        name = host.get("name", host.get("address", "?"))
        base = {
            "name": name,
            "label": host.get("label", ""),
            "address": host.get("address", ""),
        }
        out = self._ssh(host, _METRICS_SCRIPT)
        if not out:
            return {**base, "status": S_UNREACHABLE, "detail": "ssh unreachable"}

        mk = self._parse_markers(out)
        load1 = self._parse_load(mk.get("UPTIME", ""))
        cpus = None
        try:
            cpus = int(mk.get("CPUS", "").strip() or 0) or None
        except ValueError:
            pass
        cpu_pct = round(load1 / cpus * 100, 1) if (load1 is not None and cpus) else None
        disk_total, disk_used, disk_pct = self._parse_disk(mk.get("DISK", ""))
        mem_total, mem_pct = self._parse_memory(mk)

        status = _worst(
            _threshold(cpu_pct, *self.CPU_THRESHOLDS),
            _threshold(mem_pct, *self.MEM_THRESHOLDS),
            _threshold(disk_pct, *self.DISK_THRESHOLDS),
        )
        return {
            **base,
            "status": status,
            "os": mk.get("OS", ""),
            "uptime": self._parse_uptime(mk.get("UPTIME", "")),
            "load1": load1,
            "cpus": cpus,
            "cpu_pct": cpu_pct,
            "mem_total_gb": mem_total,
            "mem_pct": mem_pct,
            "disk_total_gb": disk_total,
            "disk_used_gb": disk_used,
            "disk_pct": disk_pct,
            "detail": "",
        }

    # -- public API ------------------------------------------------------------
    def collect_all(self, force: bool = False) -> List[Dict[str, Any]]:
        now = time.time()
        if not force and self._cache and (now - self._cache_ts) < self.cache_ttl:
            return self._cache
        with self._lock:
            now = time.time()
            if not force and self._cache and (now - self._cache_ts) < self.cache_ttl:
                return self._cache
            if not self._systems:
                self._cache, self._cache_ts = [], now
                return self._cache
            with ThreadPoolExecutor(max_workers=min(8, len(self._systems))) as ex:
                result = list(ex.map(self._collect_host, self._systems))
            self._cache, self._cache_ts = result, now
            return result

    def to_json(self, force: bool = False) -> Dict[str, Any]:
        systems = self.collect_all(force=force)
        return {
            "summary": {"total": len(systems), "checked_at": self._cache_ts},
            "systems": systems,
        }
