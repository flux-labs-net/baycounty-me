#!/usr/bin/env python3
"""Picks which app screens CI screenshots, so a pull request shows proof of what it changed instead of every screen.

Order of choice:
  1. A manual run (workflow_dispatch) uses its `screens` input: "all" (the default), "none", or a list.
  2. A pull request labelled `all-screens` gets the full set.
  3. A "Screens:" line in the pull request description picks them by hand, e.g. "Screens: taxbill, home, staff".
     "all" and "none" work there too. "staff" adds the staff app, "watch" the Apple Watch / Wear OS app.
  4. Otherwise the changed files pick them: HomeView.swift / HomeScreen.kt -> home, SchoolsView.swift -> schools, and so on.
     A shared file (theme, components, app store) picks a small spot-check set. Files that can't change a screen
     (tests, scripts, docs, other parts of the repo) pick nothing, and the screenshot jobs are skipped.

A name picks every screen it prefixes: "home" is home, home:rent and home:unset; "gov" is gov:county and gov:lh.

Usage: app_screens.py [--files FILE] [--body TEXT] [--labels JSON] [--manual SCREENS]
Changed file paths come one per line from --files (or stdin). Writes the choices to $GITHUB_OUTPUT when set,
a short explanation to $GITHUB_STEP_SUMMARY, and prints both.
"""
import argparse
import json
import os
import re
import sys

# Every screen each job can draw, in the order the full runs take them. Names match the apps' -screen argument.
IOS_ALL = ("home home:rent home:unset setup taxbill myhome myhome:settings address:825_Ohio_Ave tax amendment3 glossary "
           "vendors vendor people person moneymap donors contracts votes salaries accountability accproject cra "
           "craincrement chambers events beaches parks roads development schools emergency hurricaneprep "
           "utilities:825_Ohio_Ave restaurants restaurant newbusinesses volunteer military publicsafety overlaps budget "
           "pastelections updates tab:living tab:governments gov:county gov:lh tab:money tab:meetings tab:search "
           "record:contract record:vote record:board record:nonprofit").split()
IOS_DARK = "home:rent taxbill myhome tab:living tab:governments tab:money tab:meetings gov:county person budget tax record:board".split()
IOS_CHARTS = "craincrement cra budget vendor person tax contracts schools publicsafety overlaps".split()
ANDROID_JVM = ("home,home:rent,home:unset,setup,taxbill,tab:living,tab:governments,tab:money,tab:meetings,tab:search,"
               "gov:county,gov:lh,tax,amendment3,glossary,vendors,vendor,people,person,moneymap,donors,contracts,votes,"
               "salaries,accountability,accproject,cra,craincrement,chambers,events,beaches,parks,roads,development,"
               "schools,emergency,hurricaneprep,utilities,restaurants,restaurant,newbusinesses,volunteer,military,"
               "publicsafety,overlaps,budget,pastelections,updates,about,explore,myaddress,myhome,myhome:settings,"
               "record:contract,record:vote,record:board,record:nonprofit").split(",")
ANDROID_EMU = ("home home:rent setup taxbill myhome restaurants restaurant beaches parks events emergency "
               "address:825_Ohio_Ave tax amendment3 glossary vendors vendor people person moneymap donors contracts votes "
               "salaries accountability accproject cra craincrement budget pastelections updates about explore myaddress "
               "tab:living tab:governments tab:money tab:meetings tab:search gov:county gov:lh record:contract record:vote "
               "record:board record:nonprofit").split()
ANDROID_EMU_DARK = ("home home:rent taxbill tab:living tab:governments tab:money tab:meetings gov:county person budget tax "
                    "cra craincrement record:board accountability").split()

# A change to a shared file is checked on a few screens that use most of the shared pieces.
SPOT_CHECK = "home tab:living tab:governments tab:money gov:county person record:contract".split()

# File name (lowercased, without .swift/.kt and a View/Views/Screen/Screens ending) -> the screens it draws.
# The iOS and Android files share names, so one table covers both apps and their kits.
BY_FILE = {
    "accountability": "accountability accproject",
    "address": "address myaddress",
    "addresslookup": "address myaddress utilities myhome home",
    "addressreport": "address myaddress",
    "alertarea": "emergency myhome:settings",
    "alertmap": "emergency",
    "account": "myhome:settings",
    "browse": "contracts votes salaries roads newbusinesses",
    "budgetcompare": "budget",
    "calculators": "tax amendment3 taxbill",
    "chambers": "chambers events",
    "chartticks": "craincrement budget",
    "company": "vendors vendor donors moneymap",
    "cra": "cra",
    "craincrement": "craincrement",
    "dataset": "contracts votes salaries record:contract record:vote",
    "datasetspec": "contracts votes salaries record",
    "emergency": "emergency",
    "entity": "vendors vendor donors moneymap",
    "events": "events",
    "explore": "explore",
    "government": "gov",
    "governmentdetail": "gov",
    "governments": "tab:governments",
    "places": "tab:governments",
    "home": "home",
    "homesetup": "setup",
    "hometiles": "home",
    "hurricaneprep": "hurricaneprep",
    "livinghere": "tab:living",
    "meetings": "tab:meetings",
    "military": "military",
    "money": "tab:money",
    "myhome": "myhome",
    "officeholders": "gov person",
    "outdoors": "beaches parks",
    "overlaps": "overlaps",
    "people": "people person",
    "periods": "tab:meetings votes",
    "publicsafety": "publicsafety",
    "record": "record",
    "recordprofile": "record person vendor",
    "recordshare": "record",
    "reference": "glossary updates about",
    "remotephoto": "people person gov",
    "restaurants": "restaurants restaurant",
    "schooldetails": "schools",
    "schools": "schools",
    "search": "tab:search",
    "share": "record",
    "taxbill": "taxbill",
    "tax": "tax amendment3",
    "termsheet": "glossary tax",
    "todaybrief": "home",
    "todaycomponents": "home",
    "utilities": "utilities",
    "volunteer": "volunteer",
}
# Files that only matter to the companion apps.
STAFF_FILES = {"staff"}
WATCH_FILES = {"watchbrief", "watchsync"}

# Folders whose files draw main-app screens; anything else in them that isn't in BY_FILE gets the spot check.
APP_DIRS = ("ios/BayCountyMe/", "ios/BayCountyKit/Sources/", "android/app/src/main/", "android/kit/src/main/",
            "site/public/data/app/")
STAFF_DIRS = ("ios/BayCountyStaff/", "android/staff/src/main/")
WATCH_DIRS = ("ios/BayCountyWatch", "android/wear/src/main/")  # BayCountyWatch, ...WatchShared, ...WatchComplications
# Changing how screenshots are taken is checked on the spot-check set too.
SELF = (".github/workflows/ios-screenshots.yml", ".github/workflows/android.yml", ".github/scripts/app_screens.py",
        ".github/actions/pick-screens/action.yml",
        "android/scripts/emulator_shots.sh", "android/app/src/test/java/me/baycounty/app/ScreensTest.kt")


def stem(path):
    name = os.path.basename(path)
    name = re.sub(r"\.(swift|kt)$", "", name).lower()
    return re.sub(r"(views?|screens?)$", "", name) or name


def from_files(files):
    """The screens, staff/watch flags, and a reason per file, for a list of changed paths."""
    picked, staff, watch, why = [], False, False, []
    for f in files:
        f = f.strip()
        if not f:
            continue
        s = stem(f)
        if f.startswith(STAFF_DIRS) or (f.startswith(APP_DIRS) and s in STAFF_FILES):
            staff = True
            why.append(f"{f}: staff app")
        elif f.startswith(WATCH_DIRS) or (f.startswith(APP_DIRS) and s in WATCH_FILES):
            watch = True
            why.append(f"{f}: watch app")
        elif f in SELF:
            picked += SPOT_CHECK
            why.append(f"{f}: screenshot setup, spot check")
        elif f.startswith(APP_DIRS):
            if f.endswith((".swift", ".kt")) and s in BY_FILE:
                names = BY_FILE[s].split()
                picked += names
                why.append(f"{f}: {' '.join(names)}")
            elif f.endswith((".swift", ".kt", ".json", ".xml", ".xcstrings", ".strings", ".plist")):
                picked += SPOT_CHECK
                why.append(f"{f}: shared, spot check")
    return dedupe(picked), staff, watch, why


def dedupe(names):
    seen, out = set(), []
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def parse_list(text):
    """'taxbill, home staff' -> (names, staff, watch, everything)."""
    words = [w for w in re.split(r"[\s,]+", text.strip()) if w]
    lower = [w.lower() for w in words]
    if "all" in lower:
        return [], True, True, True
    names = [w for w in words if w.lower() not in ("none", "staff", "watch")]
    return names, "staff" in lower, "watch" in lower, False


def from_body(body):
    """The 'Screens:' line of a pull request description, or None."""
    m = re.search(r"^\s*(?:[*_`>-]\s*)*screens?\s*:\s*(.+?)\s*$", body or "", re.I | re.M)
    return m.group(1).strip("`*_ ") if m else None


def keep(names, full):
    """The entries of `full` that a picked name selects (the name itself, or name:anything)."""
    names = [n.replace(" ", "_") for n in names]
    return [s for s in full if any(s == n or s.startswith(n + ":") for n in names)]


def choose(files=(), body="", labels=(), manual=None):
    if manual is not None:
        names, staff, watch, everything = parse_list(manual or "all")
        reason = f"manual run: {manual or 'all'}"
    elif "all-screens" in labels:
        names, staff, watch, everything = [], True, True, True
        reason = "pull request labelled all-screens"
    elif (line := from_body(body)) is not None:
        names, staff, watch, everything = parse_list(line)
        reason = f"pull request description: Screens: {line}"
    else:
        names, staff, watch, why = from_files(files)
        everything = False
        reason = "changed files:\n" + ("\n".join("  " + w for w in why) if why else "  none that draw a screen")
    if everything:
        out = {
            "ios": IOS_ALL, "ios_dark": IOS_DARK, "ios_charts": IOS_CHARTS,
            "android": ANDROID_JVM, "android_emu": ANDROID_EMU, "android_emu_dark": ANDROID_EMU_DARK,
        }
    else:
        # Every picked screen in light and dark, so the proof shows both.
        ios = keep(names, IOS_ALL)
        emu = keep(names, ANDROID_EMU)
        out = {
            "ios": ios, "ios_dark": ios, "ios_charts": keep(names, IOS_CHARTS),
            "android": keep(names, ANDROID_JVM), "android_emu": emu, "android_emu_dark": emu,
        }
    out["staff"], out["watch"], out["all"], out["reason"] = staff, watch, everything, reason
    return out


def outputs(c):
    """GitHub step outputs: space lists for the shell loops, a comma list for Gradle, and yes/no flags."""
    b = lambda v: "true" if v else "false"
    return {
        "ios": " ".join(c["ios"]), "ios_dark": " ".join(c["ios_dark"]), "ios_charts": " ".join(c["ios_charts"]),
        "android": ",".join(c["android"]), "android_emu": " ".join(c["android_emu"]),
        "android_emu_dark": " ".join(c["android_emu_dark"]),
        "staff": b(c["staff"]), "watch": b(c["watch"]), "all": b(c["all"]),
        "any_ios": b(c["ios"] or c["ios_charts"]), "any_android": b(c["android"]),
        "any_android_emu": b(c["android_emu"]),
    }


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--files", help="file with changed paths, one per line (default: stdin)")
    p.add_argument("--body", default=os.environ.get("PR_BODY", ""))
    p.add_argument("--labels", default=os.environ.get("PR_LABELS", "[]"), help="JSON list of label names")
    p.add_argument("--manual", default=os.environ.get("MANUAL_SCREENS"))
    a = p.parse_args(argv)
    if a.manual is not None and a.manual.strip() == "" and os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch":
        a.manual = None
    files = []
    if a.manual is None:
        files = open(a.files).read().splitlines() if a.files else sys.stdin.read().splitlines()
    labels = [l if isinstance(l, str) else l.get("name", "") for l in (json.loads(a.labels or "[]") or [])]
    c = choose(files, a.body, labels, a.manual)
    out = outputs(c)
    summary = [f"Screens picked by {c['reason']}", ""]
    if c["all"]:
        summary.append("Full set: every screen, staff app and watch app.")
    else:
        summary.append("iOS: " + (out["ios"] or "none"))
        summary.append("Android: " + (out["android"].replace(",", " ") or "none"))
        summary.append("Staff app: " + ("yes" if c["staff"] else "no") + ". Watch app: " + ("yes" if c["watch"] else "no") + ".")
    summary.append("")
    summary.append('Pick by hand with a "Screens: taxbill, home" line in the pull request description, '
                   'the all-screens label, or a manual run.')
    text = "\n".join(summary)
    print(text)
    for k, v in out.items():
        print(f"{k}={v}")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as fh:
            for k, v in out.items():
                fh.write(f"{k}={v}\n")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as fh:
            fh.write("### App screenshots\n\n```\n" + text + "\n```\n")


if __name__ == "__main__":
    main()
