"""Checks the screenshot picker (app_screens.py). Run: python3 -m unittest discover -s .github/scripts"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
import app_screens as a  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


class Picks(unittest.TestCase):
    def test_one_view_picks_its_screen_on_both_apps(self):
        c = a.choose(["ios/BayCountyMe/Views/SchoolsView.swift"])
        self.assertEqual(c["ios"], ["schools"])
        self.assertEqual(c["ios_charts"], ["schools"])
        self.assertEqual(c["android"], ["schools"])
        self.assertFalse(c["staff"] or c["watch"] or c["all"])
        c = a.choose(["android/app/src/main/java/me/baycounty/app/screens/TaxBillScreen.kt"])
        self.assertEqual(c["android"], ["taxbill"])

    def test_prefix_names_pick_every_variant(self):
        c = a.choose(["ios/BayCountyMe/Views/HomeView.swift"])
        self.assertEqual(c["ios"], ["home", "home:rent", "home:unset"])
        c = a.choose(["ios/BayCountyMe/Views/GovernmentDetailView.swift"])
        self.assertEqual(c["ios"], ["gov:county", "gov:lh"])

    def test_addresses_keep_the_sample_street(self):
        c = a.choose(["ios/BayCountyMe/Views/UtilitiesView.swift"])
        self.assertEqual(c["ios"], ["utilities:825_Ohio_Ave"])
        self.assertEqual(c["android"], ["utilities"])

    def test_shared_file_gets_the_spot_check(self):
        c = a.choose(["ios/BayCountyMe/Views/Components.swift"])
        self.assertEqual(c["ios"], a.keep(a.SPOT_CHECK, a.IOS_ALL))
        self.assertLess(len(c["ios"]), 10)

    def test_files_that_draw_nothing_skip_the_jobs(self):
        c = a.choose(["ios/scripts/sync_seed.sh", "ios/BayCountyMeUITests/HomeTests.swift", "site/build_site.py", "README.md"])
        o = a.outputs(c)
        self.assertEqual((o["any_ios"], o["any_android"], o["staff"], o["watch"]), ("false", "false", "false", "false"))

    def test_staff_and_watch(self):
        c = a.choose(["ios/BayCountyStaff/Views/Flags.swift", "android/kit/src/main/kotlin/me/baycounty/kit/WatchBrief.kt"])
        self.assertTrue(c["staff"] and c["watch"])
        self.assertEqual(c["ios"], [])

    def test_description_line_wins_over_files(self):
        body = "Fixes the tax bill.\n\nScreens: taxbill, home:rent staff\n"
        c = a.choose(["ios/BayCountyMe/Views/Components.swift"], body=body)
        self.assertEqual(c["ios"], ["home:rent", "taxbill"])
        self.assertTrue(c["staff"])
        self.assertEqual(a.choose([], body="**Screens:** none")["ios"], [])
        self.assertTrue(a.choose([], body="Screens: all")["all"])

    def test_label_and_manual_run_take_everything(self):
        self.assertEqual(a.choose([], labels=["all-screens"])["ios"], a.IOS_ALL)
        self.assertTrue(a.choose([], manual="")["all"])
        self.assertEqual(a.choose([], manual="schools")["ios"], ["schools"])

    def test_lists_match_the_apps(self):
        """Every screen name the picker knows is one the apps open, and the file table names real screens."""
        known = set(a.IOS_ALL) | set(a.ANDROID_JVM) | set(a.ANDROID_EMU)
        for names in a.BY_FILE.values():
            for n in names.split():
                self.assertTrue(a.keep([n], sorted(known)), f"{n} picks no screen")
        for n in a.IOS_DARK + a.IOS_CHARTS + a.ANDROID_EMU_DARK + a.SPOT_CHECK:
            self.assertIn(n, known)
        home = open(os.path.join(ROOT, "ios/BayCountyMe/Views/HomeView.swift")).read()
        main = open(os.path.join(ROOT, "android/app/src/main/java/me/baycounty/app/MainActivity.kt")).read()
        for s in a.IOS_ALL:
            base = s.split(":")[0] + ":" if ":" in s and s.split(":")[0] in ("address", "utilities", "gov") else s
            if base.startswith(("home", "setup")):
                continue
            self.assertIn(f'"{base}', home, f"iOS app doesn't open -screen {s}")
        for s in a.ANDROID_JVM:
            base = s.split(":")[0] + ":" if s.startswith("gov:") else s
            if base.startswith(("home", "setup")):
                continue
            self.assertTrue(re.search(re.escape(f'"{base}'), main), f"Android app doesn't open screen {s}")


if __name__ == "__main__":
    unittest.main()
