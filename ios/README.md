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

In Xcode: Product > Clean Build Folder (Shift-Cmd-K), then Run. TestFlight builds normally come from the
iOS release workflow (below). To archive by hand instead, set `CURRENT_PROJECT_VERSION` in `project.yml` above the
last build number in App Store Connect (the workflow uses 100 and up), re-run `xcodegen`, then Product > Archive. About > App shows the version and build you're running.

## Releasing from GitHub

The **iOS release** workflow (`.github/workflows/ios-release.yml`) archives a signed App Store build and uploads it to
App Store Connect, where it appears in TestFlight after processing. Run it from Actions > iOS release > Run workflow,
or push a version tag (`git tag v1.1.0 && git push origin v1.1.0`), which sets the version to 1.1.0 and also starts
the Android release. The build number is the run number plus 100, so no more hand bumps. Submitting a build for App
Store review is still done in App Store Connect. It builds on Blacksmith macOS by default; pick `macpro` to use the
self-hosted Mac Pro runner.

### Secrets (one time)

Add these in GitHub: Settings > Secrets and variables > Actions.

| Secret | What it is |
|---|---|
| `ASC_KEY_ID` | App Store Connect > Users and Access > Integrations > App Store Connect API > Team Keys. Make a key with the **App Manager** role; this is its Key ID. |
| `ASC_ISSUER_ID` | The Issuer ID shown above the keys on the same page. |
| `ASC_KEY_P8` | The whole text of the downloaded `AuthKey_XXXX.p8` (it downloads only once). |
| `IOS_DIST_CERT_P12_BASE64` | An **Apple Distribution** certificate with its private key. In Keychain Access, right-click the certificate > Export as .p12 with a password, then `base64 -i dist.p12 \| pbcopy`. Xcode makes one under Settings > Accounts > Manage Certificates if you don't have it. |
| `IOS_DIST_CERT_PASSWORD` | The .p12 password. |
| `IOS_PROFILE_BASE64` | An **App Store Connect** provisioning profile for `me.baycounty.app` that uses that certificate. Create it at developer.apple.com > Certificates, IDs & Profiles > Profiles > + > App Store Connect, download it, then `base64 -i BayCountyMe_AppStore.mobileprovision \| pbcopy`. |

The certificate and profile expire after a year; make new ones and replace the last three secrets. The profile picks
up the App ID's capabilities (Push Notifications and Time Sensitive Notifications), so make it after those are on.

## What's in it

| Tab | What it shows |
|---|---|
| Home | Search, the next three meetings, topic shortcuts, links to the site's interactive tools |
| Governments | All nine governments: budget, per-resident cost, tax rate, debt, audits, votes; every dataset filtered to that government |
| Meetings | Upcoming meetings by day, agenda items and documents, one-tap calendar subscription (all boards or one government) |
| Explore | Every dataset, grouped like the site's menu: search, filter, sort, totals, map view where records have locations |
| Search | Site-wide search (`/api/v1/search`), results open in the in-app browser |

CRA Spending has its own screen with the map, paid-out vs committed/budgeted totals and a chart by agency. It follows the site's data rules: only `count: true` rows go into totals, and Spent is kept separate from money that's only planned.

Budget compare and CRA tax increment have native screens. Their numbers come from BayCountyKit ports of the site's own rules (`BudgetCompare` from api/_budget.js, `Officeholders` from api/_officials.js, `CRAIncrement` from site/cra_increment.js), and `ApiParityTests` checks them against the API's answers (fixtures from `node ios/scripts/make_fixtures.js`). Government screens follow the site's government page: who's in charge by fiscal year, the money, debt, audit findings, savings ideas and the CRA. Ask, Compare, Connections and the forms open the website page in the in-app browser. `SitePages.swift` lists how the app covers every site page.

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
