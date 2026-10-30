#!/bin/bash
# Screenshots of the Apple Watch app from its made-up demo day (-demo): the brief, the all-clear brief, the alert
# list and the watch face complications. Usage: ios/scripts/watch_screenshots.sh [out-dir]
set -euo pipefail
cd "$(dirname "$0")/.."
OUT="${1:-watch-shots}"; mkdir -p "$OUT"
scripts/ensure_watchos.sh

RUNTIME=$(xcrun simctl list runtimes -j | python3 -c 'import json,sys; r=[x for x in json.load(sys.stdin)["runtimes"] if x["isAvailable"] and x["platform"]=="watchOS"]; print(r[-1]["identifier"])')
TYPE=$(xcrun simctl list devicetypes -j | python3 -c '
import json,sys
all=[x for x in json.load(sys.stdin)["devicetypes"] if x["name"].startswith("Apple Watch")]
t=[x for x in all if x["name"].startswith("Apple Watch Series") and "46mm" in x["name"]] or all
print(t[-1]["identifier"])')
DEV=$(xcrun simctl create "BayCounty watch shots" "$TYPE" "$RUNTIME")
trap 'xcrun simctl shutdown "$DEV" >/dev/null 2>&1 || true; xcrun simctl delete "$DEV" >/dev/null 2>&1 || true' EXIT
xcrun simctl boot "$DEV"; xcrun simctl bootstatus "$DEV" -b

xcodebuild -project BayCountyMe.xcodeproj -scheme BayCountyWatch -destination "id=$DEV" \
  -derivedDataPath build/watch CODE_SIGNING_ALLOWED=NO build -quiet
APP=$(find build/watch/Build/Products -name "BayCountyWatch.app" -path "*watchsimulator*" | head -1)
xcrun simctl install "$DEV" "$APP"

BUNDLE=me.baycounty.app.watchkitapp
shoot() {
  local name=$1; shift
  xcrun simctl terminate "$DEV" "$BUNDLE" >/dev/null 2>&1 || true
  xcrun simctl launch "$DEV" "$BUNDLE" "$@" >/dev/null
  sleep 8
  xcrun simctl io "$DEV" screenshot "$OUT/watch_$name.png"
}
shoot brief -demo
shoot clear -demo-clear
shoot alerts -demo -screen alerts
shoot faces -demo -screen faces
ls -la "$OUT"
