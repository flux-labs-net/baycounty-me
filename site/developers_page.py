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
      <tr><th scope="row"><code>GET /api/v1/governments/{{slug}}</code></th><td>One profile, e.g. <a href="/api/v1/governments/lynn-haven">lynn-haven</a></td></tr>
      <tr><th scope="row"><code>GET /api/v1/search?q=</code></th><td>Search every page on the site, e.g. <a href="/api/v1/search?q=martin%20theatre">martin theatre</a></td></tr>
      <tr><th scope="row"><code>GET /downloads/{{id}}.json</code></th><td>The whole dataset as one file, for bulk use</td></tr>
    </tbody></table></div></section>
  <section class="tx-sec" id="filters"><div class="sec-hd"><h2>Filtering, sorting and paging</h2></div>
    <ul class="plain">
      <li><b>Match a column:</b> <code>?government=City%20of%20Callaway</code> (spaces as <code>%20</code>; the catalog lists each column's allowed values). Matching ignores capitals. Separate several values with commas to match any of them: <code>?outcome=failed,tabled</code>.</li>
      <li><b>Ranges:</b> add <code>_min</code> or <code>_max</code> to a number column (<code>amount_min=500000</code>) and <code>_from</code> or <code>_to</code> to a date (<code>date_from=2025-10-01</code>).</li>
      <li><b>Text:</b> <code>_contains</code> on a column (<code>vendor_contains=roberts</code>), or <code>q=</code> to search every column.</li>
      <li><b>Sort:</b> <code>sort=-amount,date</code> (a minus sign sorts high to low).</li>
      <li><b>Columns:</b> <code>fields=vendor,amount,source_url</code>.</li>
      <li><b>Paging:</b> <code>limit</code> (up to 1,000, default 100) and <code>offset</code>. The response's <code>meta.next</code> is the link to the next page.</li>
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
      <li><b>Claude:</b> add a custom connector and paste the address above.</li>
      <li><b>Other assistants and tools:</b> add it as a remote MCP server using the "Streamable HTTP" transport.</li>
      <li><b>Tools it offers:</b> <code>list_datasets</code>, <code>query_dataset</code>, <code>get_government</code> and <code>search_site</code>. Example question: "Which Bay County contracts over $5 million went to campaign donors, and how did commissioners vote?"</li>
    </ul></section>
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
