# Simulator helpers for the Mac CI jobs. Source it: `. scripts/ci_sim.sh` (from ios/).
#
# ci_device [pattern]  prints this runner's own simulator, booted. Each runner on the Mac gets its own
#                      ("CI <runner name>"), so two runners never boot, shut down or wipe each other's.
#                      pattern picks the iPhone model (default: the newest "iPhone NN Pro").
# ci_shot <dev> <png>  saves a screenshot once the screen has stopped changing, instead of a fixed wait:
#                      at least CI_SHOT_MIN seconds (default 3), then as soon as the screen has looked the same
#                      for 2 seconds (three matching pictures 1 second apart), at most CI_SHOT_MAX seconds
#                      (default 16). Loading spinners and data arriving
#                      keep it waiting; a finished screen is taken right away.

ci_device() {
  local pattern=${1:-"iPhone [0-9]+ Pro"}
  local name="CI ${RUNNER_NAME:-local}${1:+ $1}"
  local dev
  dev=$(xcrun simctl list devices available -j | python3 -c '
import json, sys
name = sys.argv[1]
for devs in json.load(sys.stdin)["devices"].values():
    for d in devs:
        if d["name"] == name and d.get("isAvailable", True):
            print(d["udid"]); raise SystemExit' "$name")
  if [ -z "$dev" ]; then
    local runtime type
    runtime=$(xcrun simctl list runtimes -j | python3 -c '
import json, sys
r = [x for x in json.load(sys.stdin)["runtimes"] if x["isAvailable"] and x["platform"] == "iOS"]
print(r[-1]["identifier"])')
    type=$(xcrun simctl list devicetypes -j | python3 -c '
import json, re, sys
pat = re.compile("^" + sys.argv[1] + "$")
t = [x for x in json.load(sys.stdin)["devicetypes"] if pat.match(x["name"])]
t.sort(key=lambda x: int(re.search(r"\d+", x["name"]).group()))
print(t[-1]["identifier"])' "$pattern")
    dev=$(xcrun simctl create "$name" "$type" "$runtime")
  fi
  xcrun simctl boot "$dev" >/dev/null 2>&1 || true
  xcrun simctl bootstatus "$dev" -b >/dev/null
  echo "$dev"
}

ci_shot() {
  local dev=$1 out=$2 min=${CI_SHOT_MIN:-3} max=${CI_SHOT_MAX:-16}
  local prev="$out.prev.png" waited=$min same=0
  sleep "$min"
  xcrun simctl io "$dev" screenshot "$prev" >/dev/null 2>&1
  while [ "$waited" -lt "$max" ]; do
    sleep 1; waited=$((waited + 1))
    xcrun simctl io "$dev" screenshot "$out" >/dev/null 2>&1
    if cmp -s "$out" "$prev"; then same=$((same + 1)); else same=0; fi
    if [ "$same" -ge 2 ]; then rm -f "$prev"; return 0; fi
    mv -f "$out" "$prev"
  done
  mv -f "$prev" "$out"
}
