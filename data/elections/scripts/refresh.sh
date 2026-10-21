#!/usr/bin/env bash
# Refresh 2026/2027 local campaign finance from the Bay County SOE. Leaves finance_2026.json unchanged if the SOE is unreachable.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; W="${1:-$(mktemp -d)}"
python3 "$HERE/fetch.py" "$W" || { echo "SOE campaign finance site unavailable; keeping existing data"; exit 0; }
python3 "$HERE/pages.py" "$W" >/dev/null
python3 "$HERE/build.py" "$W" "$W/out.json" | grep -E "REVIEW|MISMATCH" || true
python3 "$HERE/final.py" "$W/out.json" "$HERE/../finance_2026.json"
