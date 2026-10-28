# Votes from meeting minutes

Every motion each governing board voted on since 2016, read from the official minutes, with each member's vote.
Built 2026-10-26 (Jeremy approved Sonnet 5.5 for the backfill, about $100).

```
crawl_minutes.py  ->  agendas.documents (kind 'minutes', files in the private "agendas" bucket)
read_minutes.py   ->  text (OCR for scans) -> Message Batches -> agendas.minutes_reads + agendas.motions
match.py          ->  names matched to officeholder-terms, votes filled in, checks run
/admin            ->  "Votes from minutes": flagged motions and spot checks, approve or reject
export_votes.py   ->  data/votes/minutes_votes.json -> votes and member-votes datasets (site/opendata.py)
```

The **Read minutes** workflow (`.github/workflows/read-minutes.yml`) runs the crawl by hand and the reading every
3 hours. The daily **Refresh meetings** workflow runs the export, so new votes reach the site and `/api/v1` the next
morning. The agenda watcher keeps capturing new minutes, so new meetings flow through the same way.

## Progress

Every crawl stores how many files each archive lists per board and year (`agendas.minutes_inventory`; run the
workflow with step `list` to count without downloading). The view `public.minutes_progress` compares that with what
was captured, read and checked (counts only). It feeds the live "What we've loaded so far" section on
`/data-sources`, `GET /api/v1/import-progress` (`api/_progress.js`), and the /admin **Import progress** tab, which adds
spend and the estimated cost to finish.

## Where the minutes are (checked 2026-10-26)

| Board | Source | Online from | Notes |
|---|---|---|---|
| Bay County Commission | Clerk of Court OnBase Public Access, query 105 "BOCC - Minutes Search" (`bayforms.baycoclerk.com/PublicAccess/api`) | 2016 | JSON search by year; document ids expire, so files are fetched during the crawl and stored. Text PDFs. The same API has Contract (104), Resolution (106), Ordinance (107) and Check Registry (129) searches. |
| School Board | BoardDocs `go.boarddocs.com/fl/bcsdfl`, committee A4EP6J588C05, `BD-GetMinutes` | 2022 | HTML minutes, Yes/No by name. 2016-2021 need a records request. Expulsion hearings are in the minutes; the prompt never copies student names. |
| Panama City + CRA | AgendaCenter year search | 2016 | 2016-2019 files are scans (OCR). |
| Lynn Haven + CRA | Old AgendaCenter (until Aug 2026; CivicClerk after, which the watcher covers) | 2018 | No 2016-2017 commission minutes posted. |
| Callaway + CRA | Archive Center modules 35 (commission) and 38 (CRA) | 2010 (we take 2016+) | AgendaCenter only starts in 2021. Scans. |
| Panama City Beach | Granicus view 1 (`MinutesViewer.php`) | Dec 2019 | Minutes are filed under the later meeting that approved them, so one file often holds the minutes of an earlier meeting (the date check allows that). Most 2022 to Mar 2024 meetings have no minutes in Granicus: `pcb_drafts()` takes the draft minutes linked from the next meetings' agenda PDFs (Legistar attachments, text PDFs). Nothing before Dec 2019 is online. |
| Springfield | `springfieldfl.net/meetings/recent?page=N` | 2018 | Scans. |
| Parker | Agendas & Minutes page (filr table) | 2020; 2016 and 2017 as one file per year | Yearly files are read as several meetings. |
| Mexico Beach | Council Meetings page, yearly accordion | 2022 | Earlier years list meetings without minutes. |

## Reading

- Text: `pdftotext` per page; a page with under 80 letters is rendered at 300 dpi and read with Tesseract.
  Pages are marked `=== Page N ===` so each motion carries its page. Files over about 90,000 characters are split
  at page breaks (preferring a page where a new meeting starts) into several requests.
- Model: `MINUTES_MODEL`, default `claude-sonnet-5-5`, through the Message Batches API (half price). A `gpt-*` name
  (for example `gpt-6.1-sol`) sends the same prompt and schema to OpenAI's Batch API instead (also half price; needs
  the `OPENAI_API_KEY` secret). Each batch remembers its model, so switching mid-backlog is safe, and the spending
  caps count both providers. A hand run of the workflow can set `model` for that run only. See `data/llm.py`. The prompt asks
  for every voted motion (procedural ones only when split), the roll call at the start of each meeting, and per
  motion the printed yes/no/abstain/absent names, the tally as printed, outcome, mover, seconder, amounts,
  ordinance and resolution numbers, organizations, page, and a one-sentence summary. Nothing not printed.
- Cost: about 3 cents a file at batch prices. Caps: `MINUTES_SUBMIT_MAX` files per run (150),
  `MINUTES_BATCH_BUDGET_USD` per run ($25), `MINUTES_TOTAL_BUDGET_USD` for everything ($150). The /admin tab shows
  spend so far.
- Privacy: no student names or initials; private individuals in code-enforcement, lien or disciplinary matters
  aren't named. Only officeholders' votes are recorded.

## Matching and checks (match.py)

Names are matched to whoever held a voting seat on that board that day in `data/civic/officeholders.json` (CRA
boards use their city commission). Last names are matched with room for one OCR slip; first names break ties.
"Carried unanimously" or "carried" with no dissent named records every member present at roll call as yes (the
`vote_method` says which). A motion is flagged when:

| Check | Meaning |
|---|---|
| `tally_mismatch` | named votes don't add up to the printed tally |
| `unmatched_name` | a printed name matched no officeholder |
| `off_term` | the voter held a seat on this body, but not on this date per officeholder-terms |
| `no_vote_detail` | outcome only, no names or count |
| `no_quorum`, `too_many_votes`, `outcome_mismatch`, `outcome_unclear` | the count doesn't make sense |
| `no_roster` | no officeholders on file for the date (an officeholder-terms gap) |
| `date_mismatch` | the meeting date is more than 4 days from the file's listed date |

`unmatched_name`, `off_term` and `no_roster` flags also point at gaps in officeholder-terms: fix the terms in
`data/civic/scripts/officeholders.py`, rebuild, and run the workflow with step `rematch` (review decisions are kept).

## Publishing (export_votes.py)

Published: motions that passed every check and weren't rejected, plus flagged motions approved on /admin. When the
same meeting was captured twice (Callaway's Archive Center and AgendaCenter), the file with more motions is used.
Motions that repeat a hand-researched vote in `votes.json` (same board and date, and the same amount, ordinance or
resolution number, or wording) are skipped. Each row keeps `source_type` (`researched` or `minutes`), `verified`
(`hand-checked`, `auto-checked`, `reviewed`), `vote_method`, mover, seconder and the source page.

Not yet: site pages (How They Voted, profiles, vendor pages) still show the hand-researched votes; the minutes
votes are in the `votes` and `member-votes` datasets and `/api/v1`. Linking minutes votes to contracts
(`contract_votes.json`) is also still to do.

## Run it locally

```
python3 data/minutes/archive.py pc,county 2016            # count minutes files per board and year
python3 data/minutes/text.py file.pdf                     # text with OCR
python3 data/minutes/read_minutes.py --file file.pdf --board pc --date 2016-12-13            # the request
ANTHROPIC_API_KEY=... python3 data/minutes/read_minutes.py --file file.pdf --board pc --direct # read it now
python3 -m unittest discover data/minutes/tests
```
