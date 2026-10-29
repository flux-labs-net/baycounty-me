const { chromium } = require('playwright');
const fs = require('fs'), path = require('path');
const S = process.argv[2], OUT = process.argv[3];
const b64 = f => fs.readFileSync(f).toString('base64');
const font = w => `@font-face{font-family:P;font-weight:${w};src:url(data:font/woff2;base64,${b64(path.join(S,'fonts','p'+w+'.woff2'))}) format('woff2')}`;
const img = n => `data:image/png;base64,${b64(path.join(S,'storeios',n+'.png'))}`;
const icon = `data:image/png;base64,${b64(process.argv[4])}`;
const phone = (n, w, extra='') => `<div class="ph" style="width:${w}px;${extra}"><img src="${img(n)}"></div>`;
const base = (W,H,body) => `<html><head><style>${font(500)}${font(600)}${font(700)}
*{margin:0;box-sizing:border-box}body{width:${W}px;height:${H}px;overflow:hidden;font-family:P;
background:radial-gradient(120% 90% at 50% 0%,#2C4F95 0%,#1E3A76 45%,#152B5A 100%);position:relative}
.ph{position:absolute;border-radius:9%/4.2%;background:#0B1328;padding:1.1%;box-shadow:0 40px 90px rgba(5,12,30,.55)}
.ph img{width:100%;display:block;border-radius:8%/3.7%}
.bar{position:absolute;left:0;right:0;bottom:0;height:${Math.round(H*0.012)}px;display:flex}
.bar i{flex:1}.t{color:#fff;font-weight:700;letter-spacing:-.02em;line-height:1.04}.t em{font-style:normal;color:#F2B544}
.s{color:#C9D5EE;font-weight:500}
</style></head><body>${body}<div class="bar"><i style="background:#E5594B"></i><i style="background:#F2B544"></i><i style="background:#2E9E5B"></i><i style="background:#4A7BD8"></i></div></body></html>`;
(async () => {
  const b = await chromium.launch();
  // Header 3840x1646: five phones fanned across the middle, no text (the product page puts the name and icon under it).
  {
    const W=3840,H=1646,pw=620;
    const cx=W/2, top=210;
    const set=[['restaurants',-1460,170,-6],['tab_living',-760,80,-3],['home',0,0,0],['beaches',760,80,3],['events',1460,170,6]];
    let body=set.map(([n,dx,dy,r],i)=>phone(n,pw,`left:${cx+dx-pw/2}px;top:${top+dy}px;transform:rotate(${r}deg);z-index:${i==2?5:(i==1||i==3?4:3)}`)).join('');
    const p=await b.newPage({viewport:{width:W,height:H}}); await p.setContent(base(W,H,body)); await p.waitForTimeout(300);
    await p.screenshot({path:path.join(OUT,'header-3840x1646.png')}); await p.close();
  }
  // Search results 3840x2560: icon + one line on top, three phones below.
  {
    const W=3840,H=2560,pw=800;
    const body=`<div style="position:absolute;top:150px;left:0;right:0;text-align:center">
      <div class="t" style="font-size:150px">Everything Bay County, <em>sourced</em></div>
      <div class="s" style="font-size:72px;margin-top:36px">Beaches, restaurants, meetings, your tax bill and what's near your home</div></div>`
      + phone('restaurants',pw,`left:${W/2-pw/2-980}px;top:760px;transform:rotate(-4deg)`)
      + phone('beaches',pw,`left:${W/2-pw/2+980}px;top:760px;transform:rotate(4deg)`)
      + phone('home',pw+40,`left:${W/2-(pw+40)/2}px;top:640px;z-index:5`);
    const p=await b.newPage({viewport:{width:W,height:H}}); await p.setContent(base(W,H,body)); await p.waitForTimeout(300);
    await p.screenshot({path:path.join(OUT,'search-results-3840x2560.png')}); await p.close();
  }
  // Play feature graphic 1024x500 with the current tagline.
  {
    const W=1024,H=500;
    const body=`<img src="${icon}" style="position:absolute;left:96px;top:130px;width:240px;border-radius:52px;box-shadow:0 18px 40px rgba(5,12,30,.45)">
      <div style="position:absolute;left:390px;top:150px"><div class="t" style="font-size:76px">BayCounty.me</div>
      <div class="s" style="font-size:34px;margin-top:22px;line-height:1.3">Everything Bay County,<br>sourced.</div></div>`;
    const p=await b.newPage({viewport:{width:W,height:H}}); await p.setContent(base(W,H,body)); await p.waitForTimeout(300);
    await p.screenshot({path:path.join(OUT,'feature-graphic.png')}); await p.close();
  }
  await b.close();
})();
