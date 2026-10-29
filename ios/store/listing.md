# App Store listing

Paste these into App Store Connect > BayCounty.me > App Store (iOS app, version 1.0). The screenshots are in
`screenshots/` here. Character limits are Apple's; every field below is within them.

## App Information (applies to every version)

| Field | Value |
|---|---|
| Name (30) | BayCounty.me |
| Subtitle (30) | Everything Bay County, sourced |
| Primary category | Reference |
| Secondary category | News |
| Content rights | Yes, it shows third-party content, and you have the rights: Florida public records (Chapter 119), credited to their source |
| Age rating | See "Age rating answers" below; expect 4+ |
| Privacy policy URL | https://baycounty.me/privacy |

## Version 1.0

**Promotional text (170).** Can be changed any time without a new build.

```
Your home, your county: alerts near your address, beaches, parks, restaurant inspections, your tax bill, budgets, contracts, votes and meetings. Every number is sourced.
```

**Description (4,000)**

```
BayCounty.me is an independent, free app that puts Bay County, Florida public records in one place, in plain language. It covers all nine local governments: Bay County, Bay District Schools, Panama City, Panama City Beach, Lynn Haven, Callaway, Springfield, Parker and Mexico Beach.

MY HOME

• Save your home to see what's happening nearby: meetings, road and building projects, public notices and events.
• Get phone alerts for emergencies and boil-water notices that reach your address.

LIVING HERE

• Look up any address for its tax bill, schools, trash day, officials and nearby projects.
• Restaurant inspections, new businesses, beaches, parks, events, government jobs, emergency alerts and hurricane prep.

YOUR MONEY

• Budgets by year, tax rates and fees, contracts and vendors, CRA and sales tax spending, and Hurricane Michael recovery.
• An accountability console that follows major projects from approval to final cost.

WHO DECIDES

• Every elected official and department leader, their pay, how they voted and their campaign gifts.
• The business and nonprofit ties between people, companies and governments.

ELECTIONS AND GETTING INVOLVED

• Your ballot, where and when to vote, and results since 2016.
• Meetings with agendas and minutes, one tap to your calendar, public notices and records requests.

WHERE IT COMES FROM

Every figure comes from a public record: budgets, audits, meeting agendas and minutes, campaign finance reports, state business filings, map layers and state inspection data. Each one links to its source, and records go back to 2016. New records are added every day, without an app update.

INDEPENDENT AND PRIVATE

BayCounty.me is built and run by Flux Labs in Panama City. It is not run by, and does not speak for, any government, and isn't paid for by any government, candidate or campaign. No ads and no tracking. An account is optional: sign in with a code sent to your email to save your home and get alerts, and delete it in the app at any time. "Use my location" is used once on your phone and never sent to us.
```

**Keywords (100).** Commas, no spaces. The name and subtitle words are already indexed, so they're left out.

```
panama city,lynn haven,callaway,florida,alerts,beach,restaurants,property tax,contracts,parks
```

| Field | Value |
|---|---|
| Support URL | https://baycounty.me/about#contact |
| Marketing URL | https://baycounty.me |
| Copyright | 2026 Flux Labs |
| What's New | Leave empty for 1.0 (Apple hides it on a first release) |

## App Review information

- Sign-in required: **No**. Leave "Sign-in required" unchecked: the app works fully without an account, and the optional My home account signs in with a one-time code sent to any email address (no password), so reviewers can use their own email.
- Contact: Jeremy, hello@fluxlabs.net, your phone number.
- Notes:

```
BayCounty.me is a free, read-only guide to public records for Bay County, Florida. No account or sign-in. All data is published public records (budgets, contracts, votes, meetings, campaign finance reports) from Bay County, its cities, the school district, the Supervisor of Elections and the State of Florida; each record links to its source. The app is independent and is not affiliated with any government. An account is optional: My home > Sign in sends a one-time code to any email address, then lets you save a home address and turn on alerts for emergencies and boil-water notices near it. The account can be deleted in the app (My home > Settings > Delete account). Location is optional: "Use my location" finds the nearest address once and does not store or send it. To try address features, use 825 Ohio Ave, Lynn Haven.
```

## App Privacy (the "nutrition label")

The optional My home account means the app now **collects data**. Answer "Yes, we collect data from this app",
then add these three types. For each: **linked to the user**, **not used for tracking**, purpose **App Functionality** only.

| Category | Data type | Why |
|---|---|---|
| Contact Info | Email Address | Sign-in code and home emails |
| Contact Info | Name | The optional first name on the account |
| Contact Info | Physical Address | The saved home, used to find what's nearby |

Nothing else: no location (it's used on the phone and not sent), no identifiers, usage data, diagnostics or ads.
This matches `PrivacyInfo.xcprivacy` and https://baycounty.me/privacy. Account deletion is in the app
(My home > Settings > Delete account), which Apple requires for any app with account sign-up.

## Age rating answers

Every content question (violence, sexual content, profanity, drugs, gambling, horror, medical, contests) is
**None**. Then:

- Unrestricted web access: **No** (pages open in Safari view from baycounty.me links; there's no browser or address bar).
- Messaging or chat: **No** (alerts are one-way notices from us).
- User-generated content: **No**.
- Advertising: **No**.
- Parental controls, age assurance: **No**.

Expected rating: **4+**.

## Pricing and availability

- Price: Free.
- Availability: United States is enough (it's a Bay County app); all countries is fine too.
- Device: iPhone only (iPad runs it in iPhone mode; no iPad screenshots needed).

## Screenshots

`screenshots/` holds the 6.9" iPhone set (9 shots, 1320 × 2868), which App Store Connect scales down for every
smaller iPhone. Upload in order; the first three show in search results.
