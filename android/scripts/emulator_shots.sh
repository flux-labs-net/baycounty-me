#!/usr/bin/env bash
# Installs the app on a running emulator and screenshots each screen in light and dark, with live data.
# Usage: emulator_shots.sh <app-debug.apk> <output folder>. Used by .github/workflows/android.yml.
# Optional: SHOTS / DARK_SHOTS replace the screen lists, and API_BASE points the app at the store screenshot
# server (store/demo_server.py, used by .github/workflows/store-screenshots.yml).
# Screen names are the same as the iOS app's -screen names (see openScreenshotRoute in MainActivity.kt).
set -u
APK=$1
OUT=$2
PKG=me.baycounty
mkdir -p "$OUT"
adb install -r "$APK"
# A slow CI emulator often shows "System UI isn't responding" over every shot. Hide error dialogs and let it settle.
adb shell settings put global hide_error_dialogs 1
adb shell settings put global anr_show_background 0
sleep 30
# A clean status bar: 9:41, full battery, no notifications.
adb shell settings put global sysui_demo_allowed 1
adb shell am broadcast -a com.android.systemui.demo -e command enter >/dev/null
adb shell am broadcast -a com.android.systemui.demo -e command clock -e hhmm 0941 >/dev/null
adb shell am broadcast -a com.android.systemui.demo -e command battery -e level 100 -e plugged false >/dev/null
adb shell am broadcast -a com.android.systemui.demo -e command notifications -e visible false >/dev/null

API_ARGS=""
[ -n "${API_BASE:-}" ] && API_ARGS="--es apiBase $API_BASE"
shot() { # name, dark (true/false), screen ("" for home)
  adb shell am force-stop "$PKG"
  if [ -z "$3" ]; then
    adb shell am start -W -n "$PKG/me.baycounty.app.MainActivity" --ez dark "$2" $API_ARGS >/dev/null
  else
    # adb shell joins its arguments into one command line, so spaces in a screen name need escaping.
    adb shell am start -W -n "$PKG/me.baycounty.app.MainActivity" --ez dark "$2" $API_ARGS --es screen "${3// /\\ }" >/dev/null
  fi
  sleep 12
  adb exec-out screencap -p > "$OUT/$1.png"
}

LIGHT=${SHOTS-"home myhome restaurants restaurant beaches parks events emergency address:825_Ohio_Ave tax amendment3 glossary vendors vendor people person moneymap donors contracts votes salaries accountability accproject cra craincrement budget pastelections updates about explore myaddress tab:living tab:governments tab:money tab:meetings tab:search gov:county gov:lh record:contract record:vote record:board record:nonprofit"}
DARK=${DARK_SHOTS-"home tab:living tab:governments tab:money tab:meetings gov:county person budget tax cra craincrement record:board accountability"}
for s in $LIGHT; do
  screen=${s//_/ }; [ "$screen" = home ] && screen=""
  shot "$(echo "$s" | tr ':' '_')" false "$screen"
done
for s in $DARK; do
  screen=$s; [ "$screen" = home ] && screen=""
  shot "$(echo "$s" | tr ':' '_')_dark" true "$screen"
done
adb shell am broadcast -a com.android.systemui.demo -e command exit >/dev/null
ls "$OUT"
