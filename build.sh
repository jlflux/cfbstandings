#!/usr/bin/env bash
# Build the site. Used by Vercel (see vercel.json) and handy locally.
set -euo pipefail

py=""
for candidate in python3 python python3.12 python3.11; do
  if command -v "$candidate" >/dev/null 2>&1; then py="$candidate"; break; fi
done
if [ -z "$py" ]; then
  echo "No Python interpreter found; this build needs Python 3.11 or newer." >&2
  exit 1
fi

echo "Building with $($py --version)"
PYTHONPATH=src "$py" -m cfb --pause 0.15 build --out "${1:-site}"
