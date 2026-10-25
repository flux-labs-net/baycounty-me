# BayCounty.me for iOS

Native SwiftUI app for BayCounty.me. It reads the same published data as the website, so every dataset the site adds shows up in the app without an app update.

## Run it

Needs Xcode 15 or later (iOS 17 SDK) and [XcodeGen](https://github.com/yonaskolb/XcodeGen).

```bash
brew install xcodegen
cd ios
xcodegen                 # writes BayCountyMe.xcodeproj (not committed)
open BayCountyMe.xcodeproj
```

Set your Team under Signing & Capabilities, pick an iPhone simulator, press Run.

### Getting new changes into a build

`BayCountyMe.xcodeproj` is generated and not committed, so a pull alone doesn't update it.

```bash
cd ios
git pull origin main
xcodegen                 # always, after every pull: picks up new Swift files and the build number
open BayCountyMe.xcodeproj
```

In Xcode: Product > Clean Build Folder (Shift-Cmd-K), then Run. For TestFlight, bump
`CURRENT_PROJECT_VERSION` in `project.yml` first (App Store Connect rejects a build number it already has),
re-run `xcodegen`, then Product > Archive. About > App shows the version and build you're running.

## What's in it

| Tab | What it shows |
|---|---|
| Home | Search, the next three meetings, topic shortcuts, links to the site's interactive tools |
| Governments | All nine governments: budget, per-resident cost, tax rate, debt, audits, votes; every dataset filtered to that government |
| Meetings | Upcoming meetings by day, agenda items and documents, one-tap calendar subscription (all boards or one government) |
| Explore | Every dataset, grouped like the site's menu: search, filter, sort, totals, map view where records have locations |
| Search | Site-wide search (`/api/v1/search`), results open in the in-app browser |

CRA Spending has its own screen with the map, paid-out vs committed/budgeted totals and a chart by agency. It follows the site's data rules: only `count: true` rows go into totals, and Spent is kept separate from money that's only planned.

The tax calculator, My Address, Compare and Amendment 3 open the website page in an in-app browser for now.

## Data

- Datasets: `https://baycounty.me/downloads/<id>.json` (catalog at `/downloads/index.json`). Static, CDN-served, no rate limit, identical to what the site shows.
- Search: `https://baycounty.me/api/v1/search` (60 requests a minute per device without a key).
- Every response is cached on disk with its ETag and revalidated next time. Offline, the app shows the saved copy and says so.
- First launch with no network uses the seed in `BayCountyMe/Resources/Seed`. Refresh it with `ios/scripts/sync_seed.sh` before a release.
- How each dataset is presented (title, headline number, filters, Explore group, site page) is in `BayCountyKit/Sources/BayCountyKit/DatasetSpec.swift`. A dataset with no entry still works through a generic layout under "More data".

## Layout

```
ios/
  project.yml                 XcodeGen spec
  BayCountyKit/               Swift package: models, client, formatting (Foundation only)
    Tests/                    tests against site/public/downloads, plus an opt-in live test
  BayCountyMe/
    App/                      entry point, AppStore (app state)
    Views/                    Home, Governments, Meetings, Explore, Dataset, Record, CRA, Search, shared components
    Resources/                asset catalog (site palette, app icon, Flux Labs logo), seed data
  scripts/sync_seed.sh        refresh the bundled seed
```

## Tests

The data layer builds and tests on macOS or Linux:

```bash
cd ios/BayCountyKit
swift test                  # every published dataset decodes and reads; CRA totals; formatting
BCM_LIVE=1 swift test       # also hits baycounty.me: catalog, ETag revalidation, search, offline fallback
```

In Xcode, ⌘U runs the same tests.

## Next

1. Run it in the simulator and fix anything Xcode flags (the SwiftUI views haven't been compiled yet; BayCountyKit has).
2. Native versions of the tax calculator and My Address.
3. Push alerts for new agendas (the site already has email alerts and an agenda watcher).
4. Spanish, matching the site's `/es` pages.
5. Automatic build numbers for TestFlight uploads.
