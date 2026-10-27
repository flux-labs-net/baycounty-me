#!/usr/bin/env node
// Legal notices from Bay County's public notice website -> stdout as JSON (raw), read by data/notices/build_notices.py.
//
//   node data/notices/fetch_notices.js > /tmp/notices_raw.json
//
// publicnoticesbaycountyfl.gov is where Bay County, the cities and other local agencies publish legally required notices
// (s. 50.0311, Florida Statutes): bids, public hearings, meetings, ordinances, plus court and tax deed notices. The site
// draws its list in the browser, so this opens it in a headless browser the way a visitor would, presses "Load More"
// until every notice from the last 30 days (the site's default window) is shown, and keeps the notices the page loaded.
const { chromium } = require('playwright');

const URL = 'https://publicnoticesbaycountyfl.gov/';

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  const seen = new Map();
  let total = null;
  page.on('response', async (r) => {
    if (!r.url().includes('/search/public-notices')) return;
    try {
      const j = await r.json();
      total = j.page && j.page.total_results;
      for (const n of j.results || []) seen.set(n.id, n);
    } catch (e) { /* not JSON */ }
  });
  await page.goto(URL, { waitUntil: 'networkidle', timeout: 90000 });
  for (let i = 0; i < 60; i++) {
    const more = page.locator('text="Load More" >> visible=true');
    if (!(await more.count())) break;
    await more.first().click({ timeout: 15000 });
    await page.waitForLoadState('networkidle', { timeout: 30000 }).catch(() => {});
    await page.waitForTimeout(800);
    if (total && seen.size >= total) break;
  }
  await browser.close();
  process.stdout.write(JSON.stringify({ fetched_at: new Date().toISOString(), source_url: URL, total, notices: [...seen.values()] }));
  if (!seen.size) process.exit(1);
})().catch((e) => { console.error(e); process.exit(1); });
