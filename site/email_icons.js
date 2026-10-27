// Draws the small PNG icons the emails use (site/email-icons/<icon>-<tone>[-d].png, copied to /assets/email/ by
// build_site.py). Email clients don't show SVG, so these are PNGs at 2x. Re-run after changing an icon or a tone:
//   node site/email_icons.js      (needs Playwright's Chromium, a dev-only tool)
const fs = require('fs');
const path = require('path');
const {ICONS, TONES, TONES_DARK} = require('../api/_email_ui');
const PATHS = {
  alert: '<path d="M12 4 2.5 20h19L12 4ZM12 10v4M12 17h.01"/>',
  bell: '<path d="M6 16V11a6 6 0 0 1 12 0v5l2 2H4l2-2ZM10 21h4"/>',
  calendar: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>',
  chat: '<path d="M4 5h16v11H9l-5 4V5Z"/>',
  check: '<path d="m5 12 4.5 4.5L19 7"/>',
  dollar: '<path d="M12 3v18M17 7H9.5a3 3 0 0 0 0 6h5a3 3 0 0 1 0 6H6"/>',
  file: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5ZM14 3v5h5M9 13h6M9 17h4"/>',
  key: '<circle cx="8" cy="15" r="4"/><path d="m11 12 9-9M17 6l3 3M15 8l2 2"/>',
  lock: '<rect x="4" y="10" width="16" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/>',
  mail: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>',
  megaphone: '<path d="M4 10v4a1 1 0 0 0 1 1h2l5 4V5L7 9H5a1 1 0 0 0-1 1ZM16 9a4 4 0 0 1 0 6M19 6a8 8 0 0 1 0 12"/>',
  reply: '<path d="M9 14 4 9l5-5"/><path d="M4 9h10a6 6 0 0 1 6 6v5"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
  spark: '<path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M6 18l2.5-2.5M15.5 8.5 18 6"/>',
  vote: '<path d="m9 12 2 2 4-4"/><rect x="4" y="4" width="16" height="16" rx="2"/>',
};
(async () => {
  const {chromium} = require('playwright');
  const out = path.join(__dirname, 'email-icons');
  fs.mkdirSync(out, {recursive: true});
  const b = await chromium.launch();
  const page = await b.newPage({viewport: {width: 48, height: 48}, deviceScaleFactor: 1});
  let n = 0;
  for (const name of ICONS) for (const [tone] of Object.entries(TONES)) for (const dark of [false, true]) {
    const color = (dark ? TONES_DARK : TONES)[tone][1];
    await page.setContent(`<html><body style="margin:0;background:transparent"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="${color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${PATHS[name]}</svg></body></html>`);
    await page.screenshot({path: path.join(out, `${name}-${tone}${dark ? '-d' : ''}.png`), omitBackground: true});
    n++;
  }
  await b.close();
  console.log(`${n} icons in ${out}`);
})();
