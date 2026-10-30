# BayCounty.me for Android

Native Kotlin and Jetpack Compose app for BayCounty.me, built to match the iOS app (`ios/`) screen for screen. It reads the same published data as the website and the iPhone app, so every dataset the site adds shows up without an app update.

## Run it

Needs Android Studio (Ladybug or later) or the command line with JDK 21 and the Android SDK (platform 36).

```bash
cd android
./gradlew :app:installDebug        # build and install on a connected phone or a running emulator
```

Or open the `android/` folder in Android Studio and press Run. About > App shows the version and build you're running.

## What's in it

Four tabs, like the iPhone app: **Today** (search, the next meetings, topic shortcuts), **Places** (the nine governments compared and each one's page), **Money** (spending, contracts, campaign money, the calculators) and **Meetings** (upcoming meetings by day, agenda items and documents, add to calendar). Search opens from Today, and Ask opens the site's `/ask` page.

Every route the iPhone app has is native here too: governments, people and officials, companies, donors with contracts, the money map, every dataset (list, table, map and vote layouts), record pages, Explore, CRA spending, CRA tax increment, budget compare, the tax calculator with each government's budget, Amendment 3, My Address (typed or "Use my location"), the Accountability console, glossary, what's new and about.

The numbers come from `:kit`, a Kotlin port of BayCountyKit (`ios/BayCountyKit`): the same dataset specs, the same rules for totals (CRA `count: true`, Spent kept apart from planned money), budget compare, officeholder terms and the CRA increment model. `ParityTest` checks them against the API's answers, as `ApiParityTests` does on iOS.

App rules, the same as iOS: no data before 2016, chip rows that wrap instead of scrolling sideways, phone content that fits the screen, dark mode, icon-only toolbar buttons with the county mark top left, Poppins at weight 700, navy `#1E3A76` and salmon `#E5564A`, charts with at most six axis labels.

## Data

- Datasets: `https://baycounty.me/downloads/<id>.json` (catalog at `/downloads/index.json`), app files from `/data/app`, search from `/api/v1/search`.
- Responses are cached on the phone with their ETag. Offline, the app shows the saved copy and says so.
- First launch with no network uses the seed in `app/src/main/assets/seed`. Refresh it with `android/scripts/sync_seed.sh` before a release.
- Maps use OpenStreetMap tiles (osmdroid). The privacy page says so.

## Layout

```
android/
  kit/                 JVM module: models, client, formatting, the site's rules (tests in kit/src/test)
  app/
    src/main/java/me/baycounty/app/
      MainActivity.kt  tabs, back stacks, the route-to-screen map, screenshot routes
      AppStore.kt      app state, loading and caching
      Route.kt         every place a row can lead to
      screens/         one file per area (Home, Places, Money, Meetings, Government, People, Dataset, Record, CRA, Tax...)
      ui/              theme, shared components, icons, the records map
    src/test/          ScreensTest: renders screens on the JVM (Paparazzi)
  scripts/             sync_seed.sh, emulator_shots.sh
```

## Tests and screenshots

```bash
cd android
./gradlew :kit:test                                     # every published dataset decodes; the site's rules match the API
./gradlew :app:testDebugUnitTest --tests 'me.baycounty.app.ScreensTest' \
  -Dscreens="home,gov:lh,tax,budget" -Dpages=2 -Dfullres=$PWD/shots   # light and dark PNGs in android/shots
```

Screen names are the iOS app's `-screen` names (`home`, `tab:money`, `gov:county`, `person`, `record:vote`, `craincrement`...). The app also takes them from an intent: `adb shell am start -n me.baycounty/me.baycounty.app.MainActivity --es screen tax --ez dark true`.

On GitHub, the **Android** workflow (`.github/workflows/android.yml`) runs on every pull request that touches `android/`: kit tests, the debug APK, every screen rendered on the JVM in light and dark, and real emulator screenshots with live data. All three are in the run's artifacts.

## Publishing on Google Play

### One time

1. **Developer account.** Sign up at [play.google.com/console](https://play.google.com/console) with the Flux Labs Google account (one-time $25 fee). Choose an **organization** account and verify Flux Labs with its D-U-N-S number; organization accounts skip the 12-tester, 14-day closed test that new personal accounts must run before going public.
2. **Upload key.** Make the key that signs uploads (keep the file and passwords in the Flux Labs password manager; losing it means asking Google to reset it):
   ```bash
   keytool -genkeypair -v -keystore upload.jks -alias upload -keyalg RSA -keysize 4096 -validity 10000 \
     -dname "CN=Flux Labs, O=Flux Labs, L=Panama City, ST=FL, C=US"
   ```
3. **GitHub secrets.** In the repository's Settings > Secrets and variables > Actions, add:
   - `BCM_KEYSTORE_BASE64`: the output of `base64 -w0 upload.jks` (on a Mac, `base64 -i upload.jks`)
   - `BCM_KEYSTORE_PASSWORD`: the keystore password
   - `BCM_KEY_ALIAS`: `upload`
   - `BCM_KEY_PASSWORD`: the key password (the same as the keystore password if you pressed Enter at that prompt)
4. **Create the app** in the Play Console: name "BayCounty.me", default language English (US), App, Free.
5. **App content** (Policy > App content):
   - Privacy policy: `https://baycounty.me/privacy`
   - Ads: no ads
   - App access: all functionality is available without special access
   - Content rating: fill in the questionnaire (reference app, no user content, no violence); expect Everyone
   - Target audience: 18 and over is simplest (13+ is fine too; don't pick children's ages)
   - Data safety: **collected, not shared**, only when a resident makes an optional My home account: email address, home address and an optional first name, for app functionality, and the resident can delete them in the app (Settings → Delete account). **App activity → App interactions: collected, not shared**, for **Analytics**, optional (About → Share anonymous usage counts), not linked to an account or device id: once a day, times opened and screens viewed. No ads; location is used on the phone once to find the nearest address and isn't sent to us. Data is encrypted in transit (HTTPS).
   - Government apps: answer **No**. BayCounty.me is independent and isn't made by or for a government. Say so in the description too.
   - News app: No. Financial features: None.
6. **Store listing:** everything is in `android/store/`: the text to paste (`listing.md`), the 512×512 icon, the 1024×500 feature graphic and phone screenshots. To refresh the screenshots, take them from the Android workflow's `screens-emulator` artifact; Play needs the long side at most twice the short side, so trim 1080×2400 shots to 2160 tall or less. Category: Education or News & Magazines; contact email hello@fluxlabs.net; website https://baycounty.me.

### Releasing from GitHub (one time)

The **Android release** workflow sends the bundle straight to Play. It needs a Google service account that may
release the app:

1. [Google Cloud console](https://console.cloud.google.com) > pick or create a project > APIs & Services > enable the
   **Google Play Android Developer API**.
2. IAM & Admin > Service accounts > Create (name it `github-release`, no roles needed) > Keys > Add key > JSON. Keep the file.
3. Play Console > Users and permissions > Invite new users: the service account's email. Under App permissions add
   BayCounty.me with **Release apps to testing tracks** (add **Release to production** if you want the workflow to
   publish to Production too). Send the invite.
4. In GitHub, add the secret `PLAY_SERVICE_ACCOUNT_JSON` with the whole JSON file as its value.

Play only accepts API uploads after the first bundle was uploaded by hand, which is already done.

### Each release

1. Refresh the seed: `android/scripts/sync_seed.sh`, commit, merge.
2. Either push a version tag (`git tag v1.1.0 && git push origin v1.1.0`), which builds versionName 1.1.0, sends it to
   **Internal testing** and also starts the iOS release; or run Actions > **Android release** > Run workflow and pick
   the track (internal, alpha, beta, production, or none to only build). Each run runs the kit tests and builds a
   signed `app-release.aab` with a new version code (the run number plus 100). Without a tag, versionName comes from
   `app/build.gradle.kts`.
3. The .aab is also in the run's `app-release-aab` artifact. If Play answers "Only releases with status draft may be
   created on draft app", run it again with status **draft** and roll it out in the Play Console.
4. Testers get it from the Play Store. When it looks right, Play Console > **Promote release** to Production (or run
   the workflow with track production). The first production review usually takes a few days; updates are often faster.

## Changing it

Keep it in step with iOS: a new iOS screen or dataset layout gets the same change here, and `kit` follows BayCountyKit. Any page data still comes from the database and `/api/v1` (see the repo's CLAUDE.md), never only from the app.
