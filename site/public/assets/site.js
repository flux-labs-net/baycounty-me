(() => {
  const root = document.documentElement, tb = document.getElementById('themeBtn');
  const NAMES = {system: 'System', light: 'Light', dark: 'Dark'}, NEXT = {system: 'light', light: 'dark', dark: 'system'};
  const current = () => root.getAttribute('data-theme') || 'system';
  const show = m => { tb.dataset.mode = m; tb.querySelector('.theme-lbl').textContent = NAMES[m]; tb.setAttribute('aria-label', 'Theme: ' + (m === 'system' ? 'match system' : NAMES[m].toLowerCase()) + '. Click to change.'); };
  show(current());
  tb.addEventListener('click', () => {
    const m = NEXT[current()];
    if (m === 'system') root.removeAttribute('data-theme'); else root.setAttribute('data-theme', m);
    try { if (m === 'system') localStorage.removeItem('theme'); else localStorage.setItem('theme', m); } catch (e) {}
    show(m);
  });
  const btn = document.querySelector('.menu-btn'), menu = document.getElementById('site-menu');
  const setMenu = o => { btn.setAttribute('aria-expanded', o); menu.classList.toggle('open', o); document.documentElement.classList.toggle('nav-locked', o); if (o) menu.scrollTop = 0; };
  btn.addEventListener('click', () => setMenu(btn.getAttribute('aria-expanded') !== 'true'));
  menu.addEventListener('click', e => { if (e.target.closest('a')) setMenu(false); });
  const mq = matchMedia('(min-width:721px)'), onMq = e => { if (e.matches) setMenu(false); };
  if (mq.addEventListener) mq.addEventListener('change', onMq); else if (mq.addListener) mq.addListener(onMq);
  document.querySelectorAll('.sub-toggle').forEach(t => t.addEventListener('click', e => {
    e.stopPropagation(); const o = t.getAttribute('aria-expanded') === 'true';
    document.querySelectorAll('.sub-toggle').forEach(x => x.setAttribute('aria-expanded', 'false'));
    t.setAttribute('aria-expanded', !o); }));
  document.addEventListener('click', e => { if (!e.target.closest('.has-sub')) document.querySelectorAll('.sub-toggle').forEach(x => x.setAttribute('aria-expanded', 'false')); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') { document.querySelectorAll('.sub-toggle').forEach(x => x.setAttribute('aria-expanded', 'false')); if (menu.classList.contains('open')) { setMenu(false); btn.focus(); } } });
})();

(() => {
  const G = {"cra": {"term": "Community Redevelopment Agency (CRA)", "simple": "A savings jar for one neighborhood that needs fixing up. When the neighborhood's property gets more valuable, the extra tax money goes into the jar, and it can only be spent in that neighborhood."}, "cra-district": {"term": "CRA district", "simple": "The line drawn on the map around the neighborhood a CRA covers. Money raised inside the line is spent inside the line."}, "tif": {"term": "Tax increment (TIF)", "simple": "The extra property tax a neighborhood brings in because its property became worth more after the CRA started. That extra is what fills the CRA's jar."}, "base-year": {"term": "Base year", "simple": "The starting snapshot of how much all the property in a CRA was worth. Only growth above this number pays into the CRA."}, "trust-fund": {"term": "CRA trust fund", "simple": "The CRA's own bank account. Tax increment goes in, and by law it can only be spent on that CRA's plan."}, "sunset": {"term": "Sunset date", "simple": "The day a CRA is scheduled to end. After that, the extra tax money goes back to the city and county budgets."}, "tif-rebate": {"term": "TIF rebate", "simple": "A deal where the CRA gives a builder back part of the new taxes their project creates, for a set number of years, to help get the project built."}, "facade-grant": {"term": "Façade or storefront grant", "simple": "Money a CRA gives a business owner to fix up the front of their building, usually matching what the owner spends."}, "ad-valorem": {"term": "Property tax (ad valorem tax)", "simple": "A tax based on what your house or land is worth. More valuable property pays more."}, "taxing-authority": {"term": "Taxing authority", "simple": "Any government allowed to put a property tax on your bill, like the county, the school board or your city."}, "millage": {"term": "Millage (mills)", "simple": "How property tax rates are written. One mill means $1 of tax for every $1,000 your property is taxed on."}, "just-value": {"term": "Just value", "simple": "The Property Appraiser's estimate of what your property would sell for."}, "assessed-value": {"term": "Assessed value", "simple": "Your property's value after any limits on how fast it can go up. For a homestead, it usually rises more slowly than the market."}, "taxable-value": {"term": "Taxable value", "simple": "The number your tax is actually figured on: the assessed value minus any exemptions."}, "homestead": {"term": "Homestead exemption", "simple": "A discount on property taxes for the home you live in full time, as long as you apply for it."}, "rolled-back": {"term": "Rolled-back rate", "simple": "The tax rate that would bring in the same money as last year from the same properties. If a government picks a higher rate, the law calls it a tax increase, even if the rate didn't change."}, "trim": {"term": "TRIM notice", "simple": "The postcard you get each August showing your proposed taxes and when the public hearings are."}, "non-ad-valorem": {"term": "Non-ad valorem assessment", "simple": "A flat fee on your tax bill for a service, like garbage pickup or fire protection. It isn't based on what your property is worth."}, "mstu": {"term": "MSTU", "simple": "An extra county tax area that pays for services in only part of the county, usually the areas outside cities."}, "rle": {"term": "Required Local Effort", "simple": "The school tax rate the state tells every school district to charge so it can get its share of state school money."}, "save-our-homes": {"term": "Save Our Homes cap", "simple": "A limit on how fast a homestead's taxed value can go up: 3% a year, or less if inflation is lower. Rentals, businesses and second homes have a looser 10% limit."}, "rec": {"term": "Revenue Estimating Conference", "simple": "The state's team of economists that estimates how much money a new law or amendment would add or take away."}, "levy": {"term": "Levy", "simple": "The total property tax a government collects in a year: its rate times all the taxable value in its area."}, "fiscal-year": {"term": "Fiscal year (FY)", "simple": "A government's budget year. In Florida it runs from October 1 to September 30."}, "general-fund": {"term": "General fund", "simple": "A government's main checking account for everyday services like police, parks and running city hall."}, "enterprise-fund": {"term": "Enterprise fund", "simple": "An account for a service you pay for directly, like water and sewer. The bills you pay cover the service."}, "special-revenue": {"term": "Special revenue fund", "simple": "Money that by law can only be spent on one thing, like gas tax for roads or a CRA's trust fund."}, "state-shared": {"term": "State shared revenue", "simple": "Money the state collects, mostly from sales tax, and sends back to cities and counties."}, "charges-services": {"term": "Charges for services", "simple": "Money a government earns by charging for things it provides, like water bills, garbage pickup, permits and park fees."}, "intergovernmental": {"term": "Intergovernmental revenue", "simple": "Money one government gets from another, like federal grants or state shared revenue."}, "constitutional-officers": {"term": "Constitutional officers", "simple": "The elected county officials named in Florida's constitution: the sheriff, property appraiser, tax collector, clerk of court and supervisor of elections."}, "audit": {"term": "Audit / annual financial report", "simple": "A yearly check of a government's books by outside accountants, to make sure the numbers add up and the rules were followed."}, "spent": {"term": "Spent", "simple": "The record says the money was actually paid out."}, "committed": {"term": "Committed", "simple": "A contract or award has been approved, but not all of the money has been paid yet."}, "budgeted": {"term": "Budgeted", "simple": "Money set aside in a plan. It may or may not be spent."}, "proposed": {"term": "Proposed", "simple": "An idea or request that hasn't been approved."}, "left-out": {"term": "Left out of totals", "simple": "Shown on the site, but not added into the totals, so the same dollar is never counted twice."}, "change-order": {"term": "Change order", "simple": "An approved change to a contract after it is signed, which often adds cost or time."}, "right-of-way": {"term": "Right-of-way", "simple": "The land a road sits on plus the strip alongside it for sidewalks, utilities and drainage."}, "eminent-domain": {"term": "Eminent domain", "simple": "When a government buys private land for a public project even if the owner doesn't want to sell. A court decides the fair price."}, "bond": {"term": "Bond", "simple": "A way for a government to borrow money now and pay it back with interest over many years, like a mortgage."}, "cdd": {"term": "Community Development District (CDD)", "simple": "A special government created for one development to build and pay for its roads, pipes and other basics. The property owners there pay for it."}, "interlocal": {"term": "Interlocal agreement", "simple": "A contract between two governments, like a city and the county."}, "public-records": {"term": "Public records request", "simple": "Asking a government to show you or send you its records. In Florida, anyone can ask, and you don't have to say why."}, "check-register": {"term": "Check register", "simple": "A government's list of every payment it made: who got paid, how much, when and for what."}};
  let pop = null, cur = null, hideT = null, shownAt = 0;
  const ensure = () => {
    if (pop) return pop;
    pop = document.createElement('div'); pop.className = 'term-pop'; pop.id = 'term-pop';
    pop.setAttribute('role', 'tooltip'); pop.hidden = true; document.body.appendChild(pop);
    pop.addEventListener('pointerenter', () => clearTimeout(hideT));
    pop.addEventListener('pointerleave', e => { if (e.pointerType === 'mouse') later(); });
    return pop;
  };
  function show(el) {
    const g = G[el.dataset.term]; if (!g) return;
    ensure(); clearTimeout(hideT);
    if (cur && cur !== el) cur.removeAttribute('aria-describedby');
    if (cur !== el || pop.hidden) shownAt = Date.now();
    cur = el;
    pop.innerHTML = '<b></b><p></p><a></a>';
    pop.querySelector('b').textContent = g.term;
    pop.querySelector('p').textContent = g.simple;
    const a = pop.querySelector('a'); a.href = '/glossary#' + el.dataset.term; a.textContent = 'More in the glossary \u2192';
    pop.hidden = false; el.setAttribute('aria-describedby', 'term-pop');
    const r = el.getBoundingClientRect(), w = Math.min(300, innerWidth - 24);
    pop.style.width = w + 'px';
    const x = Math.max(12, Math.min(r.left + r.width / 2 - w / 2, innerWidth - w - 12));
    const h = pop.offsetHeight;
    let y = r.bottom + 8; if (y + h > innerHeight - 8) y = r.top - h - 8;
    pop.style.left = (x + scrollX) + 'px'; pop.style.top = (Math.max(8, y) + scrollY) + 'px';
  }
  function hide() { if (pop) pop.hidden = true; if (cur) cur.removeAttribute('aria-describedby'); cur = null; }
  function later() { clearTimeout(hideT); hideT = setTimeout(hide, 160); }
  const termOf = e => e.target.closest && e.target.closest('.term');
  document.addEventListener('pointerover', e => { if (e.pointerType !== 'mouse') return; const t = termOf(e); if (t) show(t); });
  document.addEventListener('pointerout', e => { if (e.pointerType === 'mouse' && termOf(e)) later(); });
  document.addEventListener('focusin', e => { const t = termOf(e); if (t) show(t); });
  document.addEventListener('focusout', e => { if (termOf(e)) later(); });
  document.addEventListener('click', e => {
    const t = termOf(e);
    if (t) { e.preventDefault(); e.stopPropagation(); if (cur === t && pop && !pop.hidden && Date.now() - shownAt > 500) hide(); else show(t); }
    else if (!(e.target.closest && e.target.closest('.term-pop'))) hide();
  }, true);
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') hide();
    const t = termOf(e); if (t && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); show(t); }
  });
  addEventListener('scroll', () => { if (cur) show(cur); }, {passive: true});
  const prep = () => document.querySelectorAll('.term:not([tabindex])').forEach(t => { t.tabIndex = 0; t.setAttribute('role', 'button'); });
  prep(); new MutationObserver(prep).observe(document.body, {childList: true, subtree: true});
})();
