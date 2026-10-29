#!/usr/bin/env python3
"""A stand-in for baycounty.me used only for app store screenshots.

It answers like the live site, but swaps in made-up data for the screens shown in the stores, so the pictures
name no real restaurant, person or business: invented restaurants and inspections, a calm sunny beach day and
no active emergency notices. Everything else (events, meetings, tax rates) is passed through from the live site.

    python3 store/demo_server.py --port 8765

The apps reach it with a debug-only launch option: iOS `-apiBase http://127.0.0.1:8765`, Android
`--es apiBase http://10.0.2.2:8765` (see .github/workflows/store-screenshots.yml). Nothing here is published.
"""
import argparse
import datetime as dt
import json
import random
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from zoneinfo import ZoneInfo

SITE = "https://baycounty.me"
TODAY = dt.datetime.now(ZoneInfo("America/Chicago")).date()
SOURCE = "https://www2.myfloridalicense.com/hotels-restaurants/public-records/"

# Invented names. The license the apps' `-screen restaurant` opens (1305433) is the first one.
PLACES = [
    ("Sea Turtle Social", "Restaurant with seating", "Lynn Haven"),
    ("Pier Pressure Tacos", "Restaurant with seating", "Panama City Beach"),
    ("Sunrise Biscuit Co.", "Restaurant with seating", "Panama City"),
    ("Driftwood Noodle House", "Restaurant with seating", "Panama City Beach"),
    ("Sea Oat Smokehouse", "Restaurant with seating", "Callaway"),
    ("Dune Street Pizza", "Takeout, no seating", "Panama City Beach"),
    ("Lighthouse Lane Bakery", "Restaurant with seating", "Panama City"),
    ("Marina Moon Sushi", "Restaurant with seating", "Panama City"),
    ("Tidepool Taqueria", "Food truck", "Panama City Beach"),
    ("Saltmarsh Kitchen", "Restaurant with seating", "Mexico Beach"),
    ("Harbor Hound Hot Dogs", "Food truck", "Panama City"),
    ("Coquina Coffee Bar", "Restaurant with seating", "Lynn Haven"),
    ("Sunset Shrimp Shack", "Restaurant with seating", "Panama City Beach"),
    ("The Gilded Grouper", "Restaurant with seating", "Panama City Beach"),
    ("Little Heron Deli", "Takeout, no seating", "Panama City"),
    ("Sea Glass Poke", "Restaurant with seating", "Panama City Beach"),
    ("Moonlight Gelato", "Restaurant with seating", "Panama City Beach"),
    ("Starfish Street Eats", "Food truck", "Callaway"),
    ("Boardwalk Bagels", "Restaurant with seating", "Lynn Haven"),
    ("Sand Dollar Supper Club", "Restaurant with seating", "Panama City"),
    ("Shell Key Smoothies", "Takeout, no seating", "Panama City Beach"),
    ("Cypress Corner Cafe", "Restaurant with seating", "Parker"),
    ("Saltbox BBQ", "Restaurant with seating", "Panama City"),
    ("Wave Runner Wings", "Restaurant with seating", "Panama City Beach"),
    ("Magnolia Bay Bistro", "Restaurant with seating", "Panama City"),
    ("Jetty Juice Co.", "Takeout, no seating", "Mexico Beach"),
    ("Porch Light Pancakes", "Restaurant with seating", "Panama City Beach"),
    ("Twin Palms Thai", "Restaurant with seating", "Lynn Haven"),
    ("Lagoon Lobster Rolls", "Food truck", "Panama City Beach"),
    ("Low Tide Ramen", "Restaurant with seating", "Panama City"),
    ("Breezeway Burgers", "Restaurant with seating", "Callaway"),
    ("Seashell Creamery", "Restaurant with seating", "Panama City Beach"),
    ("Anchor Down Catering", "Caterer", "Panama City"),
    ("Coastal Crumbs Bakery", "Takeout, no seating", "Lynn Haven"),
    ("Blue Heron Bowls", "Restaurant with seating", "Panama City Beach"),
    ("Kingfish Kitchen", "Restaurant with seating", "Mexico Beach"),
]
STREETS = ["Harbor Light Blvd", "Sea Oat Way", "Pelican Walk", "Seagrove Ave", "Sandollar Ln", "Marsh Hen Rd", "Gulf Heron Dr"]
ZIPS = {"Lynn Haven": "32444", "Panama City Beach": "32413", "Panama City": "32401", "Callaway": "32404",
        "Mexico Beach": "32456", "Parker": "32404"}
VIOLATIONS = ["Food held at the wrong temperature", "Hand sink blocked or missing soap", "Food manager certification or employee training",
              "Floors, walls or ceilings need cleaning", "Food not labeled with a date", "Equipment in poor repair"]
RESULTS = {"ok": ("Met inspection standards", "Inspection Completed - No Further Action"),
           "warning": ("Warning, follow-up visit set", "Warning Issued"),
           "fixed": ("Follow-up visit: fixed", "Inspection Completed - No Further Action")}


def day(n):
    return (TODAY - dt.timedelta(days=n)).isoformat()


def build():
    rnd = random.Random(7)
    places, visits = [], []
    for i, (name, kind, city) in enumerate(PLACES):
        lic = "1305433" if i == 0 else str(1390000 + i * 37)
        last = 1 + (i * 3) // 4 + (0 if i < 12 else rnd.randint(0, 20))
        history, gap = [], last
        pattern = ["ok", "fixed", "warning", "ok", "ok", "ok"] if i in (2, 6, 13) else ["ok"] * 6
        if i == 0:
            pattern = ["ok", "ok", "fixed", "warning", "ok", "ok", "ok"]
        if i in (5, 19):
            pattern = ["warning", "ok", "ok", "ok", "ok"]
        for lv in pattern:
            history.append((day(gap), lv))
            gap += 14 if lv == "warning" else rnd.randint(110, 190)
        for v, (date, lv) in enumerate(history):
            result, disp = RESULTS[lv]
            bad = [] if lv in ("ok", "fixed") and rnd.random() < .6 else rnd.sample(VIOLATIONS, 1 if lv != "warning" else 2)
            visits.append({"place_id": "fl-bay", "visit_id": f"9{lic}{v:02d}", "license_number": lic, "business_name": name, "city": city,
                           "date": date, "inspection_type": "Routine - Food", "visit_number": len(history) - v, "disposition": disp,
                           "result": result, "result_level": "warning" if lv == "warning" else "ok",
                           "high_priority": 1 if lv == "warning" else 0, "intermediate": len(bad), "basic": 0,
                           "total_violations": len(bad), "violation_codes": None, "violation_items": "; ".join(bad) or None,
                           "source_url": SOURCE, "gov_id": None})
        newest = history[0]
        levels = ["warning" if lv == "warning" else "ok" for _, lv in history]
        opened = history[-1][0] if i not in (9, 16) else day(60 + i)
        truck = kind in ("Food truck", "Caterer")
        places.append({
            "place_id": "fl-bay", "license_number": lic, "license_type": "Restaurant or food service", "kind": kind,
            "business_name": name, "licensee": None, "licensee_entity_id": None,
            "address": None if truck else f"{100 + i * 47} {STREETS[i % len(STREETS)]}", "city": city, "zip": ZIPS[city],
            "seats": None if truck else 40 + (i * 13) % 120, "licensed_now": True, "license_expires": "2027-06-01",
            "risk_level": "Risk Level 2", "opened": opened, "first_inspection": history[-1][0], "last_inspection": newest[0],
            "last_result": RESULTS[newest[1]][0], "last_result_level": levels[0], "last_high_priority": 1 if levels[0] == "warning" else 0,
            "last_routine_date": newest[0], "last_routine_violations": 0, "last_routine_high_priority": 0,
            "inspections": len(history), "inspections_last_year": sum(1 for d, _ in history if d >= day(365)),
            "high_priority_last_year": levels.count("warning"), "closures": 0, "last_closure": None,
            "recent_results": " ".join(levels[:6]), "page_url": None, "source_url": SOURCE, "gov_id": None})
    return places, visits


def beach():
    base = {"place_id": "fl-bay", "zone": "FLZ112", "issued": f"{TODAY}T11:00:00+00:00", "flag_color": None, "meaning": None,
            "rip_current_risk": "Low", "surf_height": None, "uv_index": None, "water_temperature": None, "weather": None,
            "high_temperature": None, "winds": None, "sunrise": None, "sunset": None, "summary": None, "date": None, "ends": None,
            "sort_order": None, "source_url": "https://api.weather.gov/", "kind": "forecast", "gov_id": None}
    names = [(TODAY + dt.timedelta(days=d)).strftime("%A") for d in range(1, 4)]
    rows = [
        {**base, "period": "Today", "sort_order": 1, "flag_color": "Green", "surf_height": "1 foot or less", "uv_index": "Very high",
         "water_temperature": "78 degrees", "weather": "Sunny", "high_temperature": "Around 84", "winds": "Light breeze from the south",
         "sunrise": "6:58 AM", "sunset": "6:12 PM", "summary": "Calm seas and sunshine. A great beach day."},
        {**base, "period": names[0], "sort_order": 2, "weather": "Sunny", "high_temperature": "Around 83", "winds": "South winds around 5 mph",
         "surf_height": "1 foot or less"},
        {**base, "period": names[1], "sort_order": 3, "summary": "Low rip current risk. Surf 1 to 2 feet. Mostly sunny. Highs in the lower 80s."},
        {**base, "period": names[2], "sort_order": 4, "summary": "Low rip current risk. Sunny. Highs around 82. Light winds."},
    ]
    legend = [("Double red", "Water closed to the public", "Swimming and wading are against the law while double red flags fly."),
              ("Red", "High hazard", "High surf and/or strong currents. Experienced swimmers only, and only close to shore."),
              ("Yellow", "Medium hazard", "Moderate surf and/or currents. Use caution."),
              ("Green", "Low hazard", "Calm conditions. Rip currents can still form near piers, jetties and sandbars."),
              ("Purple", "Dangerous marine life", "Jellyfish, stingrays or other marine life seen. Flies with another flag.")]
    for n, (c, m, s) in enumerate(legend, 1):
        rows.append({**base, "issued": None, "period": None, "rip_current_risk": None, "kind": "legend", "flag_color": c,
                     "meaning": m, "summary": s, "sort_order": n, "source_url": "https://www.pcbfl.gov/174/Beach-Flags"})
    return rows


PLACES_ROWS, VISITS = build()
DOWNLOADS = {
    "restaurants": PLACES_ROWS,
    "restaurant-inspections": VISITS,
    "beach-conditions": beach(),
    "emergency-notices": [],
}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        url = urllib.parse.urlsplit(self.path)
        q = urllib.parse.parse_qs(url.query)
        for ds, rows in DOWNLOADS.items():
            if url.path in (f"/downloads/{ds}.json", f"/data/{ds}.json"):
                return self.send(200, rows)
            if url.path == f"/api/v1/datasets/{ds}":
                hit = [r for r in rows if all(str(r.get(k)) == v[0] for k, v in q.items() if k in r)]
                if q.get("sort", [""])[0].lstrip("-") == "date":
                    hit.sort(key=lambda r: r.get("date") or "", reverse=q["sort"][0].startswith("-"))
                return self.send(200, {"data": hit, "meta": {"count": len(hit)}})
        try:
            req = urllib.request.Request(SITE + self.path, headers={"User-Agent": "BayCountyMe store screenshots"})
            with urllib.request.urlopen(req, timeout=30) as r:
                self.send(r.status, r.read(), r.headers.get("Content-Type", "application/json"))
        except urllib.error.HTTPError as e:
            self.send(e.code, e.read(), e.headers.get("Content-Type", "text/plain"))
        except Exception as e:  # network trouble: let the app fall back to its bundled copy
            self.send(502, str(e).encode(), "text/plain")

    def send(self, code, body, ctype="application/json"):
        if not isinstance(body, bytes):
            body = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print(self.address_string(), fmt % args, flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--host", default="127.0.0.1")
    a = ap.parse_args()
    ThreadingHTTPServer((a.host, a.port), Handler).serve_forever()
