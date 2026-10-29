const { chromium } = require('playwright');
// Map-style App Store header + search results art (no phone screenshots).
// Run from the repo root: NODE_PATH=$(npm root -g) node ios/scripts/store_creative_map.js <dir with fonts/p500|p600|p700.woff2> <out dir>
const fs = require('fs'), path = require('path'), { execFileSync } = require('child_process');
const S = process.argv[2], OUT = process.argv[3];
const b64 = f => fs.readFileSync(f).toString('base64');
const font = w => `@font-face{font-family:P;font-weight:${w};src:url(data:font/woff2;base64,${b64(path.join(S,'fonts','p'+w+'.woff2'))}) format('woff2')}`;
const map = (k, ox, oy) => JSON.parse(execFileSync('python3', [path.join(__dirname,'store_creative_map.py'), k, ox, oy]).toString());
// icon: small inline SVGs
const I = {
  flag:'<path d="M5 21V4m0 0h11l-2 4 2 4H5" stroke="currentColor" stroke-width="2.2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
  fork:'<path d="M7 3v8m-3-8v5a3 3 0 0 0 6 0V3m-3 8v10m10-18c-2 0-3 3-3 7h3v11" stroke="currentColor" stroke-width="2.2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
  cal:'<rect x="3.5" y="5" width="17" height="15" rx="3" stroke="currentColor" stroke-width="2.2" fill="none"/><path d="M3.5 10h17M8 3v4m8-4v4" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/>',
  trash:'<path d="M4 7h16M9 7V4h6v3m-8 0 1 13h8l1-13" stroke="currentColor" stroke-width="2.2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
  home:'<path d="M3 11 12 4l9 7v9h-6v-6H9v6H3z" stroke="currentColor" stroke-width="2.2" fill="none" stroke-linejoin="round"/>',
  star:'<path d="M12 3l2.6 5.6 6 .7-4.5 4.1 1.2 6L12 16.4 6.7 19.4l1.2-6L3.4 9.3l6-.7z" stroke="currentColor" stroke-width="2.2" fill="none" stroke-linejoin="round"/>',
};
const card = (x, y, s, ic, tone, kicker, title, sub) => `<div class="card" style="left:${x}px;top:${y}px;transform:scale(${s});transform-origin:0 0">
  <div class="ic" style="background:${tone[0]};color:${tone[1]}"><svg viewBox="0 0 24 24" width="64" height="64">${I[ic]}</svg></div>
  <div><div class="k">${kicker}</div><div class="h">${title}</div><div class="sb">${sub}</div></div></div>`;
const T = {amber:['#FBEFD6','#B7791F'], green:['#DDF3E6','#1F7A47'], blue:['#E1E9F8','#1E3A76'], red:['#FBE3E0','#C23A2C'], teal:['#DCF1EF','#1F7A72']};
const page = (W, H, m, body) => `<html><head><style>${font(500)}${font(600)}${font(700)}
*{margin:0;box-sizing:border-box}body{width:${W}px;height:${H}px;overflow:hidden;font-family:P;position:relative;
background:radial-gradient(90% 120% at 50% 40%,#2A4C90 0%,#1E3A76 50%,#13285A 100%)}
.card{position:absolute;display:flex;gap:34px;align-items:center;background:#fff;border-radius:44px;padding:36px 52px 36px 36px;
box-shadow:0 30px 70px rgba(4,12,32,.45);white-space:nowrap}
.ic{width:112px;height:112px;border-radius:30px;display:flex;align-items:center;justify-content:center;flex:none}
.k{font-size:30px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:#7A86A0}
.h{font-size:56px;font-weight:700;color:#0F1B36;letter-spacing:-.01em;line-height:1.15}
.sb{font-size:32px;font-weight:500;color:#5B6680}
.bar{position:absolute;left:0;right:0;bottom:0;height:${Math.round(H*0.012)}px;display:flex}.bar i{flex:1}
.t{color:#fff;font-weight:700;letter-spacing:-.02em;line-height:1.04}.t em{font-style:normal;color:#F2B544}.s{color:#C9D5EE;font-weight:500}
</style></head><body>
<svg width="${W}" height="${H}" style="position:absolute;left:0;top:0">
<defs><pattern id="w" width="120" height="40" patternUnits="userSpaceOnUse"><path d="M0 20 Q30 8 60 20 T120 20" stroke="rgba(255,255,255,.05)" stroke-width="3" fill="none"/></pattern></defs>
<rect width="${W}" height="${H}" fill="url(#w)"/>
<filter id="g" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="40"/></filter><path d="${m.county}" fill="#6F95E0" opacity=".45" filter="url(#g)"/>
<path d="${m.county}" fill="#F4F7FC" stroke="#fff" stroke-width="4"/>
${m.cities}
${body.lines}
</svg>${body.html}
<div class="bar"><i style="background:#E5594B"></i><i style="background:#F2B544"></i><i style="background:#2E9E5B"></i><i style="background:#4A7BD8"></i></div></body></html>`;
const pin = (p, c) => `<circle cx="${p[0]}" cy="${p[1]}" r="30" fill="${c}" opacity=".25"/><circle cx="${p[0]}" cy="${p[1]}" r="16" fill="${c}" stroke="#fff" stroke-width="6"/>`;
const line = (p, x, y) => `<path d="M${p[0]},${p[1]} L${x},${y}" stroke="rgba(255,255,255,.55)" stroke-width="4" stroke-dasharray="2 12" stroke-linecap="round"/>`;
(async () => {
  const b = await chromium.launch();
  const shoot = async (W, H, html, name) => { const p = await b.newPage({viewport:{width:W,height:H}}); await p.setContent(html); await p.waitForTimeout(300); await p.screenshot({path:path.join(OUT,name)}); await p.close(); };
  // Header 3840x1646
  {
    const W=3840,H=1646, m=map(1900,1296,90), P=m.pts;
    const cards=[ // [pt, cardX, cardY, anchorX, anchorY, icon, tone, kicker, title, sub, color]
      [P.beach, 260, 300, 1010, 380, 'flag', T.green, 'Beaches today', 'Green flag', 'Low rip current risk · 78°F water', '#2E9E5B'],
      [P.food, 330, 760, 1110, 840, 'fork', T.red, 'Restaurant inspection', 'Met standards', 'Inspected Oct 27', '#E5594B'],
      [P.trash, 230, 1190, 960, 1270, 'trash', T.teal, 'Your pickup', 'Trash day: Friday', 'Yard waste Monday', '#2A9D8F'],
      [P.meeting, 2700, 330, 2700, 410, 'cal', T.blue, 'Next meeting', 'City Commission', 'Thursday, 5:30 PM', '#4A7BD8'],
      [P.tax, 2640, 790, 2640, 870, 'home', T.amber, 'Your tax bill', '$3,135 a year', 'Schools 38% · County 35%', '#F2B544'],
      [P.events, 2760, 1220, 2760, 1300, 'star', T.amber, 'This week', '41 things to do', 'From every town and the library', '#F2B544'],
    ];
    const lines=cards.map(c=>line(c[0],c[3],c[4])+pin(c[0],c[10])).join('');
    const html=cards.map(c=>card(c[1],c[2],1,c[5],c[6],c[7],c[8],c[9])).join('');
    await shoot(W,H,page(W,H,m,{lines,html}),'header-3840x1646.png');
  }
  // Search results 3840x2560: headline left, map right with three cards
  {
    const W=3840,H=2560, m=map(2900,2000,120), P=m.pts;
    const html=`<div style="position:absolute;left:220px;top:760px;width:1700px">
      <div class="t" style="font-size:170px">Everything<br>Bay County,<br><em>sourced</em></div>
      <div class="s" style="font-size:72px;margin-top:60px;line-height:1.3">Beaches, restaurants, meetings, your tax bill and what's near your home.</div></div>`
      + card(1700, 420, 1.15, 'flag', T.green, 'Beaches today', 'Green flag', 'Low rip current risk', '')
      + card(1780, 1560, 1.15, 'fork', T.red, 'Restaurant inspection', 'Met standards', 'Inspected Oct 27')
      + card(2700, 2050, 1.15, 'cal', T.blue, 'Next meeting', 'City Commission', 'Thursday, 5:30 PM');
    const lines=line(P.beach,2300,560)+pin(P.beach,'#2E9E5B')+line(P.food,2300,1700)+pin(P.food,'#E5594B')+line(P.meeting,3000,2060)+pin(P.meeting,'#4A7BD8');
    await shoot(W,H,page(W,H,m,{lines,html}),'search-results-3840x2560.png');
  }
  await b.close();
})();
