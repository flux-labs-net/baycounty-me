"""Developer documentation for the public API and MCP server (/developers)."""
import html, json, os

e = lambda s: html.escape(str(s if s is not None else ''))
SITE = 'https://baycounty.me'


def developers_page(out_dir):
    try:
        cat = json.load(open(os.path.join(out_dir, 'downloads', 'index.json')))
    except FileNotFoundError:
        cat = {'datasets': []}
    rows = ''.join(f'''<tr><th scope="row"><code>{e(d["id"])}</code><small>{e(d["title"])}</small></th><td class="num">{d["rows"]:,}</td>
      <td class="small"><a href="/api/v1/datasets/{e(d["id"])}?limit=5">Try it</a> · <a href="/api/v1/datasets/{e(d["id"])}/schema">Columns</a> · <a href="{e(d["csv"])}">CSV</a></td></tr>''' for d in cat['datasets'])
    code = lambda s: f'<pre class="dev-code"><code>{e(s)}</code></pre>'
    anon = 'a set number of requests a minute and per day (each response\'s headers show how many are left)'
    return f'''<div class="page tax dev">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Learn and reuse · API</span><h1>BayCounty.me API</h1>
    <p class="lede">Connect your own app, spreadsheet, newsroom tool or AI assistant to the public records on this site. Free, read-only, and no key needed.</p></div>
    <div class="stamp"><a class="pill" href="/api/v1">Open the API</a><span>{len(cat["datasets"])} datasets</span></div></header>
  <nav class="jump" aria-label="On this page"><a href="#start">Quick start</a><a href="#endpoints">Endpoints</a><a href="#filters">Filtering</a><a href="#datasets">Datasets</a><a href="#keys">API keys</a><a href="#mcp">AI assistants (MCP)</a><a href="#terms">Use and limits</a></nav>
  <section class="tx-sec" id="start"><div class="sec-hd"><h2>Quick start</h2></div>
    <p>Every dataset on the <a href="/open-data">Open data</a> page is also available as an API. Responses are JSON (or CSV with <code>format=csv</code>), and every row carries a link to its source record. Rows are served live from the BayCounty.me database, so newly added records show up within about five minutes; each response says where its rows came from in <code>meta.data_source</code>.</p>
    {code(f"curl '{SITE}/api/v1/datasets/contracts?government=Bay%20County%20BOCC&amount_min=1000000&sort=-amount&limit=5'")}
    {code(f"curl '{SITE}/api/v1/datasets/votes?board=Lynn%20Haven%20City%20Commission&split=true&date_from=2025-01-01'")}
    {code(f"curl '{SITE}/api/v1/datasets/salary-positions?category=law_enforcement&fields=employer,title,pay_min,pay_max&format=csv'")}
    <p class="small muted">Base URL: <code>{SITE}/api/v1</code> · Machine-readable description: <a href="/api/v1/openapi.json">OpenAPI 3.1</a> (import it into Postman, a GPT action, or any OpenAPI tool).</p></section>
  <section class="tx-sec" id="endpoints"><div class="sec-hd"><h2>Endpoints</h2></div>
    <div class="tablewrap"><table class="tx-table"><thead><tr><th scope="col">Request</th><th scope="col">Returns</th></tr></thead><tbody>
      <tr><th scope="row"><code>GET /api/v1</code></th><td>Index: every dataset with row counts and links</td></tr>
      <tr><th scope="row"><code>GET /api/v1/datasets</code></th><td>Catalog with every column, its type and, for short lists, its allowed values</td></tr>
      <tr><th scope="row"><code>GET /api/v1/datasets/{{id}}</code></th><td>Rows: <code>{{data: [...], meta: {{total, limit, offset, next}}}}</code></td></tr>
      <tr><th scope="row"><code>GET /api/v1/datasets/{{id}}/schema</code></th><td>Columns and types for one dataset</td></tr>
      <tr><th scope="row"><code>GET /api/v1/governments</code></th><td>A profile of each local government: budget, tax rate, debt, audits, votes, staff</td></tr>
      <tr><th scope="row"><code>GET /api/v1/governments/{{slug}}</code></th><td>One profile, with <code>years</code>: budget, tax rate, audited actuals, residents, debt and staff for each fiscal year on record. E.g. <a href="/api/v1/governments/lynn-haven">lynn-haven</a></td></tr>
      <tr><th scope="row"><code>GET /api/v1/officials?gov=&amp;year=</code></th><td>Who held each elected seat on one government in a fiscal year (or on a <code>date=</code>, or today): mayor, commissioners or council, school board and superintendent, and the county or city manager, with profile ids, term dates and sources, 2016 on. E.g. <a href="/api/v1/officials?gov=lh&amp;year=2019">Lynn Haven in FY2019</a></td></tr>
      <tr><th scope="row"><code>GET /api/v1/budget-compare?gov=&amp;from=&amp;to=</code></th><td>One government's budget in two fiscal years: totals, funds, General Fund departments and services, with dollar and percent changes. Add <code>basis=actual</code> for audited revenue and spending. E.g. <a href="/api/v1/budget-compare?gov=lh&amp;from=2025&amp;to=2026">Lynn Haven FY2025 vs FY2026</a>; without <code>gov</code>, the years on record for each government</td></tr>
      <tr><th scope="row"><code>GET /api/v1/checkbook?gov=&amp;fy=</code></th><td>One government's payments in a fiscal year, from its own check register: total, by month, top payees, by fund and the largest payments. E.g. <a href="/api/v1/checkbook?gov=lh">Lynn Haven</a>. Every payment: <a href="/api/v1/datasets/checkbook-payments">checkbook-payments</a></td></tr>
      <tr><th scope="row"><code>GET /api/v1/budget-actual?gov=&amp;fy=&amp;as_of=</code></th><td>Spending and revenue against the budget, by department, as of a month end, with the share of the year gone. E.g. <a href="/api/v1/budget-actual?gov=lh">Lynn Haven</a>. Every line: <a href="/api/v1/datasets/budget-actuals">budget-actuals</a></td></tr>
      <tr><th scope="row"><code>GET /api/v1/import-progress</code></th><td>How far loading every board's meeting minutes since 2016 has got: files found in each archive, downloaded, read into motions and checked, per board and year, with the estimated time left. Shown live on <a href="/data-sources#progress">Where our data comes from</a></td></tr>
      <tr><th scope="row"><code>GET /api/v1/status</code></th><td>Rows in each dataset, when the database last loaded it, and any load errors</td></tr>
      <tr><th scope="row"><code>GET /api/v1/changes?since=</code></th><td>Records added since a date or time, e.g. <a href="/api/v1/changes?since=2026-10-01&amp;dataset=contracts">new contracts since Oct. 1</a>. Add <code>dataset=</code> to pick datasets</td></tr>
      <tr><th scope="row"><code>GET /api/v1/meetings.ics?gov=</code></th><td>Calendar feed of upcoming meetings for one government, e.g. <a href="/api/v1/meetings.ics?gov=lh">Lynn Haven</a>. Keys: county, schools, pc, pcb, lh, cw, sp, parker, mb; a board such as <code>lh-cra</code> works too, and commas combine them. Paste the link into Google Calendar, Outlook or Apple Calendar ("subscribe by URL"). Every board at once: <a href="/meetings.ics">/meetings.ics</a></td></tr>
      <tr><th scope="row"><code>GET /api/v1/correspondence?year=</code></th><td>Published letters BayCounty.me sent to officials, with their replies, e.g. <a href="/api/v1/correspondence?year=all">every year</a>. Add <code>government=</code> for one government. Only threads approved for publication are included</td></tr>
      <tr><th scope="row"><code>GET /api/v1/pages</code></th><td>Which datasets and endpoints hold the data behind each page on the site, e.g. <a href="/api/v1/pages?page=/connections">the Connections network</a></td></tr>
      <tr><th scope="row"><code>GET /api/v1/entities?q=</code></th><td>Find a company, official, candidate, nonprofit, board member, business or government by name, e.g. <a href="/api/v1/entities?q=dewberry">dewberry</a>. Add <code>kind=</code> (gov, vendor, person, nonprofit, member, owner, business, committee)</td></tr>
      <tr><th scope="row"><code>GET /api/v1/entities/{{id}}</code></th><td>One profile and every documented connection: payments, contracts, campaign gifts from organizations, votes, board seats, businesses and grants, each with its source, e.g. <a href="/api/v1/entities/vendor:dewberry">vendor:dewberry</a>. Officials' board seats and businesses appear once an editor checks the match</td></tr>
      <tr><th scope="row"><code>GET /api/v1/search?q=</code></th><td>Search every page on the site, e.g. <a href="/api/v1/search?q=martin%20theatre">martin theatre</a></td></tr>
      <tr><th scope="row"><code>GET /downloads/{{id}}.json</code></th><td>The whole dataset as one file, for bulk use</td></tr>
    </tbody></table></div></section>
  <section class="tx-sec" id="filters"><div class="sec-hd"><h2>Filtering, sorting and paging</h2></div>
    <ul class="plain">
      <li><b>Match a column:</b> <code>?government=City%20of%20Callaway</code> (spaces as <code>%20</code>; the catalog lists each column's allowed values). Matching ignores capitals. Separate several values with commas to match any of them: <code>?outcome=failed,tabled</code>.</li>
      <li><b>Ranges:</b> add <code>_min</code> or <code>_max</code> to a number column (<code>amount_min=500000</code>) and <code>_from</code> or <code>_to</code> to a date (<code>date_from=2025-10-01</code>).</li>
      <li><b>Text:</b> <code>_contains</code> on a column (<code>vendor_contains=roberts</code>), or <code>q=</code> to search every column.</li>
      <li><b>Not equal:</b> <code>_ne</code> leaves out values (<code>outcome_ne=passed</code>; commas for several).</li>
      <li><b>Empty or not:</b> <code>_null=true</code> finds rows where a column is blank, <code>_null=false</code> rows where it has a value (<code>amount_null=false</code>). Blank values never match <code>_min</code>, <code>_max</code>, <code>_from</code> or <code>_to</code>.</li>
      <li><b>Totals:</b> <code>group_by=government&amp;sum=amount</code> returns one row per group with <code>count</code>, <code>sum_amount</code> and <code>n_amount</code> (how many numbers were added), largest group first. Filters apply first, and it works with <code>format=csv</code>. Example: <a href="/api/v1/datasets/contracts?group_by=government&amp;sum=amount">contract dollars by government</a>.</li>
      <li><b>Sort:</b> <code>sort=-amount,date</code> (a minus sign sorts high to low).</li>
      <li><b>Columns:</b> <code>fields=vendor,amount,source_url</code>.</li>
      <li><b>Paging:</b> <code>limit</code> (up to 1,000, default 100) and <code>offset</code>. The response's <code>meta.next</code> is the link to the next page.</li>
      <li><b>Caching:</b> responses carry an <code>ETag</code> (and <code>Last-Modified</code> where the data's date is known). Send it back as <code>If-None-Match</code> (or <code>If-Modified-Since</code>) and you get <code>304 Not Modified</code> with no body when nothing changed.</li>
    </ul></section>
  <section class="tx-sec" id="datasets"><div class="sec-hd"><h2>Datasets</h2><span class="muted">Updated {e(cat.get("updated"))}</span></div>
    <div class="tablewrap"><table class="tx-table cm-table"><thead><tr><th scope="col">Dataset id</th><th scope="col" class="num">Rows</th><th scope="col">Links</th></tr></thead><tbody>{rows}</tbody></table></div></section>
  <section class="tx-sec" id="keys"><div class="sec-hd"><h2>API keys and limits</h2></div>
    <p>You don't need a key. Without one, each connection can make {anon}. If you need more, or want your use tracked separately, <a href="/about#contact">ask for a key</a>.</p>
    <p>Send a key in any of these ways (the header is best, so the key stays out of logs and browser history):</p>
    {code(f"curl -H 'Authorization: Bearer bcm_your_key' '{SITE}/api/v1/datasets/votes?limit=5'")}
    <ul class="plain">
      <li><code>Authorization: Bearer &lt;key&gt;</code> or <code>X-API-Key: &lt;key&gt;</code> header, or <code>?api_key=&lt;key&gt;</code> on the URL. The MCP server takes the same header.</li>
      <li>Every response carries <code>X-RateLimit-Limit</code> and <code>X-RateLimit-Remaining</code> (per minute), plus <code>X-RateLimit-Limit-Day</code> and <code>X-RateLimit-Remaining-Day</code> when a daily limit applies. Daily limits reset at midnight Central time.</li>
      <li>Over a limit, you get status <code>429</code> with a <code>Retry-After</code> header in seconds. A wrong key gets <code>401</code>; a paused, revoked or expired key gets <code>403</code>.</li>
    </ul></section>
  <section class="tx-sec" id="mcp"><div class="sec-hd"><h2>Connect an AI assistant (MCP)</h2></div>
    <p>BayCounty.me runs a <a href="https://modelcontextprotocol.io" target="_blank" rel="noopener">Model Context Protocol</a> server, so AI assistants that support remote MCP servers can look up these records directly and cite them. There's no sign-in.</p>
    {code(f"{SITE}/api/mcp")}
    <ul class="plain">
      <li><b>AI assistants and tools:</b> add it as a custom connector or remote MCP server using the "Streamable HTTP" transport.</li>
      <li><b>Tools it offers:</b> <code>list_datasets</code>, <code>query_dataset</code>, <code>get_government</code>, <code>search_site</code>, <code>upcoming_meetings</code> (by government, days ahead or a keyword such as a street name), <code>member_voting_record</code> (one board member's votes, including when they were in the minority) and <code>vendor_profile</code> (one company's contracts, change orders, payments, CRA payments and business campaign contributions; a match doesn't show why anything happened) and <code>official_correspondence</code> (published letters to officials and their replies), <code>compare_budget_years</code> (one government's budget in two fiscal years, by fund, department and service, or audited revenue and spending), <code>officials_in_office</code> (who held each elected seat in a given year), <code>government_checkbook</code> and <code>budget_vs_actual</code> (a government's own payments and its spending against the budget this year), and <code>find_entity</code> and <code>get_entity</code> (anyone or anything on the site and every documented connection: who paid it, campaign gifts from organizations, votes, board seats and businesses).</li>
      <li><b>Resources:</b> each dataset is also an MCP resource at <code>baycounty://datasets/&lt;id&gt;</code> (up to 2,000 rows; the full file is linked).</li>
      <li><b>Example question:</b> "Which Bay County contracts over $5 million went to campaign donors, and how did commissioners vote?"</li>
    </ul>
    <p>The site's own <a href="/ask">Ask</a> page uses these same tools: an AI assistant answers visitors' questions from this data and links each source.</p></section>
  <section class="tx-sec method" id="terms"><div class="sec-hd"><h2>Use and limits</h2></div>
    <ul class="plain">
      <li>The data is compiled from public records and free to reuse. Please credit BayCounty.me and link to the source record for any figure you publish.</li>
      <li>Check the original record before relying on a single number. Each dataset's notes and gaps are on its page on this site.</li>
      <li>Individual campaign donors and rank-and-file public employees are not named, here or anywhere on the site.</li>
      <li>Each API and MCP request is logged with its time, query, key (if any) and IP address, to enforce limits and stop abuse. IP addresses are deleted from the log after 90 days.</li>
      <li>Requests are limited per connection or per key (see <a href="#keys">API keys</a>). For bulk use, download the full files from <code>/downloads</code>. Data refreshes as the site updates, and meetings and campaign reports refresh every morning.</li>
      <li>Questions or a use you'd like supported? <a href="/about#contact">Get in touch</a>.</li>
    </ul></section>
</div>
<link rel="stylesheet" href="/assets/tax.css">'''
