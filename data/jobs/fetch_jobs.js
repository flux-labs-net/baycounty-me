#!/usr/bin/env node
// Government job openings in Bay County -> data/jobs/<county>/jobs.json
//
//   node data/jobs/fetch_jobs.js
//
// Each employer posts openings on its own job board. Most of these boards draw their list in the browser, so this opens
// each one in a headless browser the way a job seeker would and reads the openings it shows: title, department, pay
// and type when listed, the date posted or closing date, and the link to apply. A board that fails keeps the openings
// it had last time and records the error, so one broken site never empties the list.
//
// Boards: Bay County (Workday), Bay District Schools (Focus), Panama City (NEOGOV), Lynn Haven (Keldair), Callaway
// (city website jobs feed), Parker (city website), Northwest Florida Beaches International Airport (airport website).
// Panama City Beach, Springfield and Mexico Beach are listed with a link: Panama City Beach's site turns away automated
// readers, and Springfield and Mexico Beach post openings only as notices or application forms.
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const COUNTY = (process.env.PLACE || 'fl-bay').split('-').slice(1).join('-');
const OUT = path.join(__dirname, COUNTY, 'jobs.json');
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36';
const clean = (s) => (s || '').replace(/[­​]/g, '').replace(/\s+/g, ' ').trim();

const BOARDS = [
  { key: 'county', gov_id: 'county', employer: 'Bay County', url: 'https://baycountyfl.wd12.myworkdayjobs.com/en-US/Bay_County_External_Career_Site', read: workday },
  { key: 'schools', gov_id: 'schools', employer: 'Bay District Schools', url: 'https://focus.bayschools.net/focus/jobs/#!Jobs', read: focus },
  { key: 'pc', gov_id: 'pc', employer: 'City of Panama City', url: 'https://www.governmentjobs.com/careers/pcgov', read: neogov },
  { key: 'lh', gov_id: 'lh', employer: 'City of Lynn Haven', url: 'https://jobs.keldair.com/cityoflynnhaven', read: keldair },
  { key: 'cw', gov_id: 'cw', employer: 'City of Callaway', url: 'https://www.cityofcallaway.com/Jobs.aspx', feed: 'https://www.cityofcallaway.com/RSSFeed.aspx?ModID=66&CID=All-0', read: civicplus },
  { key: 'parker', gov_id: 'parker', employer: 'City of Parker', url: 'https://cityofparker.com/government/careers/', read: wpJobs },
  { key: 'airport', gov_id: null, employer: 'Northwest Florida Beaches International Airport', url: 'https://www.iflybeaches.com/airport-district/employment', read: airport },
  { key: 'pcb', gov_id: 'pcb', employer: 'City of Panama City Beach', url: 'https://www.pcbfl.gov/departments/human-resources/job-openings', read: null,
    note: "The city's website turns away automated readers; see its job openings page." },
  { key: 'sp', gov_id: 'sp', employer: 'City of Springfield', url: 'https://www.springfieldfl.org/', read: null, note: 'Springfield posts openings as notices on its website.' },
  { key: 'mb', gov_id: 'mb', employer: 'City of Mexico Beach', url: 'https://mexicobeachfl.gov/government/employment-opportunities/', read: null,
    note: 'Mexico Beach takes applications on its employment page; openings are not listed one by one.' },
];

async function open(browser, url, wait = 5000) {
  const page = await browser.newPage({ userAgent: UA, viewport: { width: 1280, height: 1000 } });
  await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForTimeout(wait);
  return page;
}

function posted(s, today) {
  // "Posted Today", "Posted Yesterday", "Posted 8 Days Ago", "Posted 30+ Days Ago", "Posted 1 week ago" -> ISO date (approximate)
  s = (s || '').toLowerCase();
  const d = new Date(today);
  if (/today/.test(s)) return d.toISOString().slice(0, 10);
  if (/yesterday/.test(s)) { d.setDate(d.getDate() - 1); return d.toISOString().slice(0, 10); }
  const m = s.match(/(\d+)\+?\s*(day|week|month)/);
  if (m) { d.setDate(d.getDate() - Number(m[1]) * ({ day: 1, week: 7, month: 30 }[m[2]])); return d.toISOString().slice(0, 10); }
  const us = s.match(/(\d{1,2})\/(\d{1,2})\/(\d{4})/);
  if (us) return `${us[3]}-${us[1].padStart(2, '0')}-${us[2].padStart(2, '0')}`;
  return null;
}

async function workday(browser, b, today) {
  const page = await open(browser, b.url, 7000);
  const out = [];
  for (let n = 0; n < 10; n++) {
    const rows = await page.$$eval('li.css-1q2dra3', (lis) => lis.map((li) => {
      const a = li.querySelector('a[data-automation-id="jobTitle"]');
      const dd = (id) => { const x = li.querySelector(`[data-automation-id="${id}"] dd`); return x ? x.innerText : ''; };
      return { title: a && a.innerText, href: a && a.href, location: dd('locations'), type: dd('time'), posted: dd('postedOn'),
        ref: (li.querySelector('ul[data-automation-id="subtitle"] li') || {}).innerText || '' };
    }));
    for (const r of rows) {
      if (!r.title) continue;
      out.push({ title: clean(r.title), department: clean(r.location), job_type: clean(r.type) || null, pay: null,
        posted: posted(r.posted, today), closes: null, ref: clean(r.ref) || (r.href.match(/_(JR\d+)/) || [])[1] || null, url: r.href });
    }
    const next = page.locator('button[aria-label="next"]:not([disabled])');
    if (!(await next.count())) break;
    await next.first().click(); await page.waitForTimeout(3000);
  }
  await page.close();
  return out;
}

async function focus(browser, b) {
  const page = await open(browser, b.url, 8000);
  const text = await page.innerText('body');
  await page.close();
  const list = text.split(/Available Jobs/)[1] || '';
  const out = [];
  for (const block of list.split(/\n\s*View\s*\n/)) {
    const lines = block.split('\n').map(clean).filter(Boolean);
    const num = block.match(/POSTING NUMBER:\s*(\d+)/);
    if (!num || !lines.length) continue;
    const date = (label) => { const m = block.match(new RegExp(label + ':?\\s*(\\d{2}/\\d{2}/\\d{4})')); return m ? posted(m[1]) : null; };
    out.push({ title: lines[0], department: lines[3] || null, job_type: lines[2] ? lines[2].toLowerCase().replace(/^\w/, (c) => c.toUpperCase()) : null,
      pay: null, posted: date('Date Posted'), closes: date('Closing Date'), ref: num[1], url: b.url });
  }
  return out;
}

async function neogov(browser, b, today) {
  const page = await open(browser, b.url, 4000);
  const out = [];
  for (let n = 0; n < 20; n++) {
    const rows = await page.$$eval('li.list-item', (lis) => lis.map((li) => {
      const a = li.querySelector('a.item-details-link');
      const meta = [...li.querySelectorAll('ul.list-meta li')].map((x) => x.innerText);
      return { id: li.dataset.jobId, title: a && a.innerText, href: a && a.href, dept: a && a.dataset.departmentName, meta,
        posted: (li.querySelector('.list-entry-starts') || {}).innerText || '' };
    }));
    for (const r of rows) {
      if (!r.title || out.some((o) => o.ref === r.id)) continue;
      const typePay = clean(r.meta.find((m) => /\$|time|hour|annual/i.test(m)) || '');
      const [jt, pay] = typePay.split(/\s+-\s+/);
      out.push({ title: clean(r.title), department: clean(r.dept) || null, job_type: clean(jt) || null, pay: clean(pay) || null,
        posted: posted(r.posted, today), closes: null, ref: r.id, url: r.href });
    }
    const next = page.locator('ul.pagination li.PagedList-skipToNext a');
    if (!(await next.count())) break;
    await next.first().click(); await page.waitForTimeout(3500);
  }
  await page.close();
  return out;
}

async function keldair(browser, b, today) {
  const page = await open(browser, b.url, 5000);
  const text = await page.innerText('body');
  const links = await page.$$eval('a', (as) => as.map((a) => [a.innerText.trim(), a.href]));
  await page.close();
  const body = (text.split(/Posted Date/)[1] || '').split(/Displaying/)[0];
  const lines = body.split('\n').map(clean).filter(Boolean);
  const out = [];
  for (let i = 0; i + 3 < lines.length + 1; i += 4) {
    const [title, , dept, date] = lines.slice(i, i + 4);
    if (!title || !date) break;
    const link = links.find(([t]) => t === title);
    const m = date.match(/([A-Z][a-z]{2}) (\d{1,2})/);
    let iso = null;
    if (m) {
      const d = new Date(`${m[1]} ${m[2]}, ${today.getFullYear()}`);
      if (d > today) d.setFullYear(d.getFullYear() - 1);
      iso = d.toISOString().slice(0, 10);
    }
    out.push({ title, department: dept || null, job_type: null, pay: null, posted: iso, closes: null, ref: null, url: link ? link[1] : b.url });
  }
  return out;
}

async function civicplus(browser, b) {
  const r = await fetch(b.feed, { headers: { 'User-Agent': UA } });
  const xml = await r.text();
  const out = [];
  for (const item of xml.split('<item>').slice(1)) {
    const tag = (t) => { const m = item.match(new RegExp(`<${t}>([\\s\\S]*?)</${t}>`)); return m ? clean(m[1].replace(/<!\[CDATA\[|\]\]>/g, '').replace(/&amp;/g, '&').replace(/&amp;/g, '&')) : ''; };
    const title = tag('title');
    if (!title || /business and employment notice/i.test(title)) continue;
    const pub = tag('pubDate');
    out.push({ title, department: null, job_type: null, pay: null, posted: pub ? new Date(pub).toISOString().slice(0, 10) : null, closes: null,
      ref: null, url: tag('link') || b.url });
  }
  return out;
}

async function wpJobs(browser, b) {
  const page = await open(browser, b.url, 4000);
  const rows = await page.$$eval('ul.job_listings li.job_listing', (lis) => lis.map((li) => ({
    title: (li.querySelector('h3') || {}).innerText, href: (li.querySelector('a') || {}).href,
    type: (li.querySelector('li.job-type') || {}).innerText, date: (li.querySelector('time') || { getAttribute: () => null }).getAttribute('datetime') })));
  await page.close();
  return rows.filter((r) => r.title).map((r) => ({ title: clean(r.title), department: null, job_type: clean(r.type) || null, pay: null,
    posted: r.date || null, closes: null, ref: null, url: r.href || b.url }));
}

async function airport(browser, b) {
  const page = await open(browser, b.url, 3000);
  const text = await page.innerText('body');
  await page.close();
  const part = (text.split(/CUR\S*RENT JOB OPEN\S*INGS/i)[1] || '').split(/JOB APPLI\S*CA\S*TION/i)[0];
  return part.split('\n').map(clean).filter((t) => t && t.length < 80).map((title) => ({ title, department: null, job_type: null, pay: null,
    posted: null, closes: null, ref: null, url: b.url }));
}

(async () => {
  const today = new Date();
  const old = fs.existsSync(OUT) ? JSON.parse(fs.readFileSync(OUT, 'utf8')) : { jobs: [], boards: [] };
  const browser = await chromium.launch();
  const jobs = [];
  const boards = [];
  for (const b of BOARDS) {
    const info = { key: b.key, gov_id: b.gov_id, employer: b.employer, url: b.url, read: !!b.read, note: b.note || null, error: null, count: 0 };
    if (b.read) {
      try {
        const got = await b.read(browser, b, today);
        if (!got.length && b.key !== 'parker' && b.key !== 'cw' && b.key !== 'lh') throw new Error('no openings found (page layout may have changed)');
        for (const j of got) jobs.push({ board: b.key, gov_id: b.gov_id, employer: b.employer, ...j });
        info.count = got.length;
      } catch (e) {
        info.error = String(e.message || e).slice(0, 200);
        const kept = old.jobs.filter((j) => j.board === b.key);
        jobs.push(...kept);
        info.count = kept.length;
      }
    }
    boards.push(info);
    console.error(`${b.key}: ${info.count}${info.error ? ' (error: ' + info.error + ')' : ''}`);
  }
  await browser.close();
  // first_seen: the first day this list saw the opening (boards without a posted date)
  const seen = new Map(old.jobs.map((j) => [`${j.board}|${j.ref || j.url}|${j.title}`, j.first_seen]));
  const day = today.toISOString().slice(0, 10);
  for (const j of jobs) j.first_seen = seen.get(`${j.board}|${j.ref || j.url}|${j.title}`) || day;
  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  fs.writeFileSync(OUT, JSON.stringify({ as_of: today.toISOString(), boards, jobs }, null, 1));
  console.error(`${jobs.length} openings -> ${path.relative(process.cwd(), OUT)}`);
})().catch((e) => { console.error(e); process.exit(1); });
