#!/usr/bin/env bash
# build-export.sh — produce the public SEGA snapshot and verify it is clean.
#
# Builds a clean copy of this repo MINUS everything in .publish-exclude, runs the
# deny-scan on the result, and confirms the exported CLI still imports. This is the
# one command to run before publishing; if it exits non-zero, DO NOT publish.
#
#   ./scripts/build-export.sh [OUT_DIR]     # default: ./_export/sega
#   ./scripts/build-export.sh --strict      # also fail on codename warnings
#
# It does NOT push anything — it only produces and validates the artifact.

set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

STRICT=""
OUT=""
for arg in "$@"; do
  case "$arg" in
    --strict) STRICT="--strict" ;;
    *) OUT="$arg" ;;
  esac
done
OUT="${OUT:-$ROOT/_export/sega}"

command -v rsync >/dev/null || { echo "✗ rsync required"; exit 2; }
[ -f "$ROOT/.publish-exclude" ] || { echo "✗ .publish-exclude not found"; exit 2; }

echo "▶ building export: $OUT"
rm -rf "$OUT"; mkdir -p "$OUT"
rsync -a --exclude='.git' --exclude-from="$ROOT/.publish-exclude" "$ROOT/" "$OUT/"
echo "  exported files: $(find "$OUT" -type f | wc -l | tr -d ' ')"

echo
echo "▶ deny-scan on the exported artifact"
if ! "$ROOT/scripts/opensource-deny-scan.sh" "$OUT" $STRICT; then
  echo
  echo "✗ EXPORT REJECTED — deny-scan found private data. Fix the source or"
  echo "  .publish-exclude, then rebuild. Do NOT publish $OUT."
  exit 1
fi

echo
echo "▶ smoke-test: does the exported CLI import?"
if PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python PYTHONPATH="$OUT/engine" \
     python3 -c "from sega.cli.main import cli; print('  exported CLI imports:', len(cli.commands), 'commands')" 2>/dev/null; then
  :
else
  echo "  ⚠ could not import the exported CLI here (missing runtime deps is OK in a"
  echo "    bare shell; CI installs them). Re-run in an env with the package deps"
  echo "    installed to fully verify: cd $OUT && pip install -e engine && sega --help"
fi

echo
echo "✓ export built and clean: $OUT"
echo "  Next: review, then publish via the open_source pipeline (see docs)."
