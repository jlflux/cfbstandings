#!/usr/bin/env bash
# Build the site. Used by Vercel (see vercel.json) and handy locally.
#
# Fetches from ESPN. If that is unreachable - a blocked egress, an ESPN
# outage, a deploy from a sandbox - it falls back to the last committed
# snapshot so the deploy still produces a working site rather than failing.
set -euo pipefail

out="${1:-site}"
snapshot="data/latest.json"

py=""
for candidate in python3 python python3.12 python3.11; do
  if command -v "$candidate" >/dev/null 2>&1; then py="$candidate"; break; fi
done
if [ -z "$py" ]; then
  echo "No Python interpreter found; this build needs Python 3.11 or newer." >&2
  exit 1
fi
echo "Building with $($py --version 2>&1)"

if PYTHONPATH=src "$py" -m cfb --pause 0.15 build --out "$out"; then
  exit 0
fi

echo "Live build failed." >&2
if [ -f "$snapshot" ]; then
  echo "Falling back to $snapshot - the site will show that snapshot's data." >&2
  PYTHONPATH=src "$py" -m cfb --season-file "$snapshot" build --out "$out"
else
  echo "No snapshot to fall back to." >&2
  exit 1
fi
