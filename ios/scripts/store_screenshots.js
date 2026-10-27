// Frames raw app screenshots for the App Store and Google Play: brand background, caption, phone outline.
// Usage: node ios/scripts/store_screenshots.js spec.json. The spec lists each shot (img, title, accent word, sub)
// and the size: 1320x2868 for the App Store, 1080x1920 for Play. fonts = a folder with Poppins p500/p600/p700.woff2
// (from @fontsource/poppins). Raw shots come from the iOS screenshots and Android workflow artifacts.
// node render.js <spec.json>  spec: {fonts, out, w, h, shots:[{img, title, accent, sub, dark}]}
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path');
const spec = JSON.parse(fs.readFileSync(process.argv[2]));
const b64 = f => fs.readFileSync(f).toString('base64');
const font = w => `@font-face{font-family:P;font-weight:${w};src:url(data:font/woff2;base64,${b64(path.join(spec.fonts, 'p' + w + '.woff2'))}) format('woff2')}`;
const css = font(500) + font(600) + font(700);
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: spec.w, height: spec.h } });
  fs.mkdirSync(spec.out, { recursive: true });
  const W = spec.w, H = spec.h, u = W / 1320; // scale everything from the 1320-wide design
  for (const [i, s] of spec.shots.entries()) {
    const title = s.title.replace(s.accent, `<em>${s.accent}</em>`);
    const bg = s.dark ? '#0F1B36' : '#1E3A76';
    const html = `<html><head><style>${css}
      *{margin:0;box-sizing:border-box}
      body{width:${W}px;height:${H}px;overflow:hidden;background:${bg};font-family:P;color:#fff;position:relative;display:flex;flex-direction:column;align-items:center;padding:${92*u}px ${90*u}px ${110*u}px}
      body:before{content:"";position:absolute;inset:0;background:radial-gradient(120% 60% at 50% 0%,rgba(255,255,255,.10),transparent 60%)}
      .mark{font-weight:700;font-size:${44*u}px;letter-spacing:-.5px;opacity:.92;position:relative}
      .mark span{color:#F07A6F}
      h1{margin-top:${44*u}px;text-align:center;font-weight:700;font-size:${100*u}px;line-height:1.1;letter-spacing:-1.5px;position:relative;text-wrap:balance;height:${2*1.1*100*u}px;width:100%;justify-content:center;display:flex;align-items:center}
      h1 span{display:block;width:100%;text-wrap:balance}
      h1 em{font-style:normal;color:#F2B657}
      p{margin-top:${30*u}px;text-align:center;font-weight:500;font-size:${46*u}px;line-height:1.32;color:rgba(255,255,255,.80);max-width:${1060*u}px;position:relative;text-wrap:balance;height:${2*1.32*46*u}px}
      .slot{flex:1;min-height:0;margin-top:${80*u}px;display:flex;justify-content:center;position:relative}
      .phone{height:100%;border-radius:${86*u}px;background:#0B1226;padding:${22*u}px;box-shadow:0 ${40*u}px ${120*u}px rgba(0,0,0,.45),0 0 0 ${3*u}px rgba(255,255,255,.14)}
      .phone img{display:block;height:100%;width:auto;border-radius:${66*u}px}
      .strip{position:absolute;bottom:0;left:0;right:0;height:${18*u}px;display:flex;z-index:5}
      .strip i{flex:1}
    </style></head><body>
      <div class="mark">BayCounty<span>.me</span></div>
      <h1><span>${title}</span></h1><p>${s.sub}</p>
      <div class="slot"><div class="phone"><img src="data:image/png;base64,${b64(s.img)}"></div></div>
      <div class="strip"><i style="background:#E5564A"></i><i style="background:#E8A33D"></i><i style="background:#1F8A7A"></i><i style="background:#4C7BD9"></i></div>
    </body></html>`;
    await page.setContent(html, { waitUntil: 'load' });
    await page.evaluate(() => document.fonts.ready);
    const name = String(i + 1).padStart(2, '0') + '-' + s.name + '.png';
    await page.screenshot({ path: path.join(spec.out, name) });
    console.log(name);
  }
  await browser.close();
})();
