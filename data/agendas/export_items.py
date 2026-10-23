#!/usr/bin/env python3
"""
export_items.py - write data/agendas/agenda_items.json from the agendas tables, for site search.

One row per item from each document's current, successfully read version, newest meetings first. Run by the daily
meetings refresh before the site build; site/search_page.py indexes the file ("Agenda item" results).

Privacy (the site's rules: no private individuals by name): `parties` keeps companies, agencies and other
organizations and drops entries that look like a person's name, e.g. a homeowner on a code-enforcement item.
Usage: DATABASE_URL=... python3 data/agendas/export_items.py [--out PATH]
"""
import datetime as dt
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
OUT = os.path.join(HERE, "agenda_items.json")

ORG = re.compile(r"\b(LLC|L\.L\.C|Inc|Corp|Corporation|Co|Company|Ltd|LLP|LP|PA|P\.A|PLLC|Group|Brothers|Bros|Partners|"
                 r"Associates|Holdings|Properties|Development|Developers|Construction|Contractors|Contracting|Engineers?|"
                 r"Engineering|Consultants?|Consulting|Services|Solutions|Systems|Technologies|Industries|Enterprises|"
                 r"Department|Dept|County|City|Town|State|District|Authority|Agency|Commission|Board|Council|Office|"
                 r"Association|Society|Club|League|Church|Ministries|University|College|School|Academy|Foundation|"
                 r"Trust|Fund|Bank|Hospital|Center|Institute|Partnership|Coalition|Alliance|Network|Utilities|"
                 r"Transportation|Transit|Tech|Medical|Health|Water|Electric|Energy|Communications|Management|Logistics|Labs?|"
                 r"Florida|FDOT|FDEP|FEMA|DEO|USDA|HUD|EPA)\b|&", re.I)
PERSON = re.compile(r"^(Mr\.?|Mrs\.?|Ms\.?|Dr\.?)?\s*[A-Z][a-z'’-]+(\s+[A-Z]\.?)?(\s+[A-Z][a-z'’-]+){1,2}(,?\s+(Jr|Sr|II|III)\.?)?$")


def keep_party(p):
    p = (p or "").strip()
    if not p:
        return False
    if ORG.search(p):
        return True
    return not PERSON.match(p)


def rows(cur):
    import watch_agendas as wa
    names = {b["id"]: b["name"] for b in wa.fm.BOARDS}
    cur.execute("""
        select d.board, d.source_key, coalesce(e.meeting_date, d.meeting_date), d.url, d.title,
               i.item_number, i.section, i.title, i.summary, i.kind, i.total_amount, i.parties, i.addresses, i.position
          from agendas.items i
          join agendas.extractions e on e.id = i.extraction_id and e.status = 'ok'
          join agendas.documents d on d.id = i.document_id and d.current_sha256 = e.sha256
         order by 3 desc nulls last, d.id, i.position""")
    out = []
    for board, src, mdate, url, mtitle, num, section, title, summary, kind, amount, parties, addresses, _pos in cur.fetchall():
        out.append({"board": board or src, "body": names.get(board) or board or src,
                    "gov": wa.GOV_OF_BOARD.get(board) or src, "date": mdate.isoformat() if mdate else None,
                    "meeting": mtitle, "number": num, "section": section, "title": title, "summary": summary,
                    "kind": kind, "amount": float(amount) if amount is not None else None,
                    "parties": [p for p in (parties or []) if keep_party(p)], "addresses": addresses or [],
                    "url": url if str(url).startswith("http") else None})
    return out


def main(argv):
    out_path = argv[argv.index("--out") + 1] if "--out" in argv else OUT
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL is not set; agenda_items.json left as is")
        return 0
    import watch_agendas as wa
    db = wa.DB(url, False)
    with db.conn.cursor() as cur:
        items = rows(cur)
    doc = {"generated": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
           "note": "Agenda items read from posted agendas by a Claude model (data/agendas/extract_agendas.py). "
                   "Amounts are the largest dollar figure printed on the item, not necessarily spending. "
                   "Check the agenda itself before relying on an item.",
           "items": items}
    tmp = out_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(tmp, out_path)
    print("wrote %s: %d items" % (out_path, len(items)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
