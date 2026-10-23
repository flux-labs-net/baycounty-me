// Flag rules for the finance workspace (Phase 1: rules 1-10 and 16 of the plan).
// runRules(data) is pure: it takes a workspace's rows and returns flags. Each flag carries a fingerprint built from the
// facts that make it this flag, so a re-run updates the same flag and an "explained" flag stays quiet until those
// facts change (a different amount is a different fingerprint).
const crypto = require('crypto');
const {round2} = require('./normalize');

const DEFAULTS = {
  bid_threshold: 35000,          // formal bid / commission approval (Lynn Haven policy, 12/9/2025)
  manager_threshold: 3500,       // city manager approval
  rec_due_days: 30,              // a month's bank rec should be done within 30 days of month end
  stale_check_days: 180,
  burn_rate_points: 0.20,        // spent share of budget more than 20 points ahead of the share of the year elapsed
  burn_rate_min_budget: 10000,
  duplicate_window_days: 30,
  duplicate_min_amount: 100,
  split_window_days: 14,
  split_window_days_small: 7,     // the City Manager level: tighter window
  split_min_share_small: 0.7,     // and each payment at least 70% of it, i.e. just under
  round_dollar_min: 5000,
  weekend_min: 1000,
  spike_multiple: 3,
  spike_min_increase: 5000,
  spike_history_months: 6,
  new_vendor_large: 25000,
};

const WEIGHT = {info: 0.25, review: 1, urgent: 3};
const RULES = {
  file_tie: {n: 1, name: 'File doesn’t tie to its own total'},
  rec_overdue: {n: 2, name: 'Bank reconciliation overdue'},
  rec_difference: {n: 3, name: 'Unreconciled difference'},
  stale_check: {n: 4, name: 'Stale outstanding check'},
  over_budget: {n: 5, name: 'Over budget'},
  burn_rate: {n: 6, name: 'Spending ahead of the year'},
  duplicate_payment: {n: 7, name: 'Possible duplicate payment'},
  split_purchase: {n: 8, name: 'Possible split purchase'},
  round_or_weekend: {n: 9, name: 'Round-dollar or weekend payment'},
  payee_spike: {n: 10, name: 'Vendor spending spike'},
  audit_repeat: {n: 16, name: 'Repeat audit finding'},
};

const fp = (...parts) => crypto.createHash('sha1').update(parts.map(p => String(p ?? '')).join('|')).digest('hex').slice(0, 20);
const usd = n => (n === null || n === undefined ? '—' : (n < 0 ? '-' : '') + '$' + Math.abs(n).toLocaleString('en-US', Number.isInteger(n) ? {} : {minimumFractionDigits: 2, maximumFractionDigits: 2}));
const days = (a, b) => Math.round((Date.parse(b) - Date.parse(a)) / 864e5);
const addDays = (d, n) => new Date(Date.parse(d) + n * 864e5).toISOString().slice(0, 10);
const monthEnd = ym => new Date(Date.UTC(+ym.slice(0, 4), +ym.slice(5, 7), 0)).toISOString().slice(0, 10);
const nextMonth = ym => { const y = +ym.slice(0, 4), m = +ym.slice(5, 7); return m === 12 ? `${y + 1}-01` : `${y}-${String(m + 1).padStart(2, '0')}`; };
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
const niceDate = d => `${MONTHS[+d.slice(5, 7) - 1].slice(0, 3)} ${+d.slice(8, 10)}, ${d.slice(0, 4)}`;
const monthName = ym => `${MONTHS[+ym.slice(5, 7) - 1]} ${ym.slice(0, 4)}`;
const monthList = yms => yms.map(monthName).join(', ');
const median = xs => { if (!xs.length) return 0; const s = [...xs].sort((a, b) => a - b), h = s.length >> 1; return s.length % 2 ? s[h] : (s[h - 1] + s[h]) / 2; };

function flag(rule, severity, key, f) {
  const amount = f.amount_at_risk === undefined || f.amount_at_risk === null ? null : round2(Math.abs(f.amount_at_risk));
  return {rule, rule_no: RULES[rule].n, severity, fingerprint: fp(rule, ...key), title: f.title, detail: f.detail || null,
    amount_at_risk: amount, score: round2(Math.max(amount || 0, 1) * WEIGHT[severity]), refs: f.refs || [], facts: f.facts || {}};
}

// US federal holidays (observed) for a year, as 'YYYY-MM-DD'. Payments on these days are as unusual as weekends.
function holidays(y) {
  const d = (m, day) => new Date(Date.UTC(y, m - 1, day));
  const nth = (m, wd, n) => { const first = d(m, 1); return d(m, 1 + ((7 + wd - first.getUTCDay()) % 7) + 7 * (n - 1)); };
  const last = (m, wd) => { const end = d(m + 1, 0); return d(m, end.getUTCDate() - ((7 + end.getUTCDay() - wd) % 7)); };
  const observed = dt => { const w = dt.getUTCDay(); return w === 6 ? new Date(+dt - 864e5) : w === 0 ? new Date(+dt + 864e5) : dt; };
  return new Set([observed(d(1, 1)), nth(1, 1, 3), nth(2, 1, 3), last(5, 1), observed(d(6, 19)), observed(d(7, 4)), nth(9, 1, 1),
    nth(10, 1, 2), observed(d(11, 11)), nth(11, 4, 4), observed(d(12, 25))].map(x => x.toISOString().slice(0, 10)));
}
const holidayCache = new Map();
const isHoliday = s => { const y = +s.slice(0, 4); if (!holidayCache.has(y)) holidayCache.set(y, holidays(y)); return holidayCache.get(y).has(s); };
const weekday = s => new Date(s + 'T00:00:00Z').getUTCDay();

// Revenue lines are left out of the budget rules (collecting more than budgeted is not overspending). A line is revenue
// when its type says so, or its account has a Florida Uniform Accounting System revenue code (3xx) and no expense code.
function isRevenue(l) {
  const t = `${l.type || ''}`.toLowerCase();
  if (/rev|income|receipt/.test(t)) return true;
  if (/exp|appro|cost/.test(t)) return false;
  if (/\brevenues?\b/i.test(`${l.fund || ''} ${l.department || ''}`)) return true;
  const segs = String(l.account || '').split(/[^0-9]+/).filter(Boolean);
  const has = re => segs.some(s => re.test(s));
  return has(/^3\d\d$/) && !has(/^[5-9]\d\d$/);
}

// ---- Rule 1: uploads whose rows don't add up to the printed total ----
function fileTie(uploads) {
  return uploads.filter(u => u.tie_status === 'mismatch' && u.status !== 'replaced').map(u => flag('file_tie', 'urgent', [u.id, u.tie_difference], {
    title: `${u.original_name} doesn’t tie: off by ${usd(u.tie_difference)}`,
    detail: `The rows in this file add up to ${usd(u.parsed_total)}, but the file's printed total is ${usd(u.printed_total)}. ` +
      'The file is held and none of its rows are used until it ties. Re-export it, or enter the correct control total.',
    amount_at_risk: u.tie_difference, refs: [{table: 'uploads', id: u.id}], facts: {upload_id: u.id, parsed: u.parsed_total, printed: u.printed_total}}));
}

// ---- Rules 2 and 3: bank reconciliations ----
function bankRecs({bankTxns, bankRecs, today, s}) {
  const out = [], accounts = new Map();
  const acct = h => { if (!accounts.has(h)) accounts.set(h, {label: null, months: new Map(), recs: []}); return accounts.get(h); };
  for (const t of bankTxns) {
    if (!t.account_hash || !t.posted_on) continue;
    const a = acct(t.account_hash), ym = t.posted_on.slice(0, 7);
    a.label = a.label || t.account_label;
    const m = a.months.get(ym) || {activity: 0, ids: []};
    m.activity += Math.abs(t.amount || 0); m.ids.push(t.id); a.months.set(ym, m);
  }
  for (const r of bankRecs) { if (!r.account_hash) continue; const a = acct(r.account_hash); a.label = a.label || r.account_label; a.recs.push(r); }

  for (const [hash, a] of accounts) {
    const label = a.label || 'account';
    const recByMonth = new Map(a.recs.filter(r => r.period_end).map(r => [r.period_end.slice(0, 7), r]));
    // Months that need a rec: every month from the first month with activity or a rec, through the last month
    // whose due date (month end + rec_due_days) has passed.
    const known = [...a.months.keys(), ...recByMonth.keys()].sort();
    if (known.length) {
      const missing = [];
      for (let ym = known[0]; monthEnd(ym) < today; ym = nextMonth(ym)) {
        const due = addDays(monthEnd(ym), s.rec_due_days);
        if (due >= today) break;
        const rec = recByMonth.get(ym);
        if (!rec) { missing.push(ym); continue; }
        if (rec.reconciled_on && rec.reconciled_on > due) {
          const late = days(due, rec.reconciled_on);
          out.push(flag('rec_overdue', late > 60 ? 'urgent' : 'review', [hash, ym, 'late'], {
            title: `${monthName(ym)} rec for ${label} finished ${late} days late`,
            detail: `The ${monthName(ym)} reconciliation was completed ${rec.reconciled_on}, ${late} days after its ${s.rec_due_days}-day due date (${due}).`,
            amount_at_risk: a.months.get(ym)?.activity ?? null, refs: [{table: 'bank_recs', id: rec.id}], facts: {account: label, month: ym, reconciled_on: rec.reconciled_on, due}}));
        }
      }
      if (missing.length) {
        const activity = missing.reduce((x, ym) => x + (a.months.get(ym)?.activity || 0), 0);
        const oldest = missing[0], overdue = days(addDays(monthEnd(oldest), s.rec_due_days), today);
        out.push(flag('rec_overdue', overdue > 60 ? 'urgent' : 'review', [hash, 'missing', missing.join(',')], {
          title: `No reconciliation on file for ${label}: ${missing.length} month${missing.length === 1 ? '' : 's'}`,
          detail: `Months with no rec uploaded: ${monthList(missing)}. The oldest is ${overdue} days past due. ` +
            `${usd(activity)} of bank activity in those months hasn't been tied to the books. Upload the rec summaries if they were done.`,
          amount_at_risk: activity, refs: missing.flatMap(ym => (a.months.get(ym)?.ids || []).slice(0, 50).map(id => ({table: 'bank_transactions', id}))),
          facts: {account: label, months: missing}}));
      }
    }
    // Rule 3: statement - outstanding + in transit + adjustments should equal the book balance.
    for (const r of a.recs) {
      if (r.statement_balance === null || r.book_balance === null) continue;
      const adjusted = round2(r.statement_balance - (r.outstanding_checks || 0) + (r.deposits_in_transit || 0) + (r.other_adjustments || 0));
      const diff = round2(adjusted - r.book_balance);
      if (Math.abs(diff) < 0.01) continue;
      out.push(flag('rec_difference', Math.abs(diff) >= 1000 ? 'urgent' : 'review', [hash, r.period_end, diff], {
        title: `${label}, ${monthName(r.period_end.slice(0, 7))}: reconciliation off by ${usd(diff)}`,
        detail: `Bank ${usd(r.statement_balance)} − outstanding checks ${usd(r.outstanding_checks || 0)} + deposits in transit ${usd(r.deposits_in_transit || 0)}` +
          `${r.other_adjustments ? ` + adjustments ${usd(r.other_adjustments)}` : ''} = ${usd(adjusted)}, but the books show ${usd(r.book_balance)}.`,
        amount_at_risk: diff, refs: [{table: 'bank_recs', id: r.id}], facts: {account: label, period_end: r.period_end, adjusted, book: r.book_balance}}));
    }
    if (a.recs.length && !a.recs.some(r => r.approved_by)) {
      out.push(flag('rec_overdue', 'info', [hash, 'no-reviewer'], {
        title: `${label}: no reviewer recorded on any reconciliation`,
        detail: 'None of the uploaded recs for this account show who reviewed or approved them. A second person signing off is the standard control for the repeat reconciliation finding.',
        refs: a.recs.slice(0, 24).map(r => ({table: 'bank_recs', id: r.id})), facts: {account: label}}));
    }
  }
  return out;
}

// ---- Rule 4: checks written but not cleared the bank after stale_check_days ----
function staleChecks({disb, bankTxns, s}) {
  const out = [], posted = bankTxns.filter(t => t.posted_on).map(t => t.posted_on).sort();
  if (!posted.length) return out;
  const start = posted[0], end = posted[posted.length - 1];
  const cleared = new Set(bankTxns.filter(t => t.check_no).map(t => String(t.check_no).replace(/^0+/, '')));
  const byAmount = new Map();
  for (const t of bankTxns) if (t.amount < 0 && !t.check_no) { const k = Math.abs(t.amount).toFixed(2); byAmount.set(k, (byAmount.get(k) || 0) + 1); }
  const voided = new Set(disb.filter(d => d.is_void || d.amount < 0).map(d => d.doc_no).filter(Boolean));
  for (const d of disb) {
    if (d.method !== 'check' || !d.doc_no || d.is_void || voided.has(d.doc_no) || !(d.amount > 0) || !d.paid_on) continue;
    if (d.paid_on < start) continue;                       // written before the bank data starts: can't tell
    const age = days(d.paid_on, end);
    if (age <= s.stale_check_days) continue;
    if (cleared.has(d.doc_no.replace(/^0+/, ''))) continue;
    const k = d.amount.toFixed(2);
    if (byAmount.get(k)) { byAmount.set(k, byAmount.get(k) - 1); continue; } // cleared without a check number
    out.push(flag('stale_check', d.amount >= 5000 ? 'review' : 'info', [d.doc_no, d.amount, d.paid_on], {
      title: `Check ${d.doc_no} to ${d.payee} (${usd(d.amount)}) hasn't cleared in ${age} days`,
      detail: `Written ${niceDate(d.paid_on)}; the bank data runs through ${niceDate(end)} with no matching check. Stale checks should be voided and, ` +
        'if the payee can’t be reached, reported as unclaimed property.',
      amount_at_risk: d.amount, refs: [{table: 'disbursements', id: d.id}], facts: {doc_no: d.doc_no, payee: d.payee, age_days: age}}));
  }
  return out;
}

// ---- Rules 5 and 6: budget vs actual, latest snapshot per fiscal year ----
// Checked per department (fund when there's no department): Florida cities adopt and control budgets at that level,
// so one line running over inside a department that's within budget is a transfer, not overspending. The lines
// driving a department's number are listed on the flag.
function budgetRules({budget, s, fyStartMonth}) {
  const out = [];
  const latest = new Map();
  for (const l of budget) { const k = l.fiscal_year; if (!latest.has(k) || (l.as_of || '') > latest.get(k)) latest.set(k, l.as_of || ''); }
  const groups = new Map();
  for (const l of budget) {
    if ((l.as_of || '') !== latest.get(l.fiscal_year) || isRevenue(l)) continue;
    const unit = l.department || l.fund || 'Unassigned';
    const k = [l.fiscal_year, l.fund || '', unit].join('|');
    if (!groups.has(k)) groups.set(k, {fy: l.fiscal_year, fund: l.fund, unit, as_of: l.as_of, budget: 0, actual: 0, enc: 0, lines: []});
    const g = groups.get(k);
    g.budget += l.amended_budget ?? l.original_budget ?? 0; g.actual += l.actual_ytd || 0; g.enc += l.encumbered || 0; g.lines.push(l);
  }
  const lineList = (g, n = 4) => g.lines.map(l => ({l, over: (l.actual_ytd || 0) + (l.encumbered || 0) - (l.amended_budget ?? l.original_budget ?? 0)}))
    .sort((a, b) => b.over - a.over).slice(0, n).filter(x => x.over > 0.5)
    .map(x => `${x.l.description || x.l.account} (${usd(round2(x.over))} over)`).join('; ');
  for (const g of groups.values()) {
    const b = round2(g.budget), spent = round2(g.actual + g.enc), key = [g.fy, g.fund, g.unit];
    const refs = g.lines.slice(0, 60).map(l => ({table: 'budget_lines', id: l.id}));
    if (b <= 0 && spent > 0) {
      out.push(flag('over_budget', spent >= 10000 ? 'urgent' : 'review', [...key, 'unbudgeted', spent], {
        title: `${g.unit}: ${usd(spent)} spent with no budget`, detail: `FY${g.fy} as of ${g.as_of}: no appropriation, but ${usd(spent)} is spent or encumbered.`,
        amount_at_risk: spent, refs, facts: {fiscal_year: g.fy, budget: b, spent}}));
      continue;
    }
    if (b <= 0) continue;
    if (spent > b + 0.5) {
      const over = round2(spent - b), pct = over / b, top = lineList(g);
      out.push(flag('over_budget', over >= 10000 || pct >= 0.05 ? 'urgent' : 'review', [...key, over], {
        title: `${g.unit}: ${usd(over)} over budget (${Math.round(pct * 100)}%)`,
        detail: `FY${g.fy} as of ${g.as_of}: budget ${usd(b)}; spent ${usd(round2(g.actual))}${g.enc ? ` plus ${usd(round2(g.enc))} on open purchase orders` : ''} = ${usd(spent)}. ` +
          `Spending past the adopted amount needs a budget amendment approved by the Commission.${top ? ` Lines over: ${top}.` : ''}`,
        amount_at_risk: over, refs, facts: {fiscal_year: g.fy, budget: b, spent, over}}));
      continue;
    }
    // Rule 6: share of budget used vs share of the fiscal year elapsed.
    if (!g.as_of || b < s.burn_rate_min_budget) continue;
    if (/debt\s*service/i.test(`${g.unit} ${g.fund || ''}`)) continue; // paid on a fixed schedule, often once a year
    const fyStart = `${g.fy - (fyStartMonth > 1 ? 1 : 0)}-${String(fyStartMonth).padStart(2, '0')}-01`;
    const elapsed = Math.min(1, Math.max(0, (days(fyStart, g.as_of) + 1) / 365));
    if (elapsed < 1 / 12 || elapsed >= 0.95) continue;
    const used = spent / b;
    if (used - elapsed > s.burn_rate_points) {
      const ahead = round2((used - elapsed) * b);
      out.push(flag('burn_rate', 'review', [...key, Math.round(used * 100), g.as_of.slice(0, 7)], {
        title: `${g.unit}: ${Math.round(used * 100)}% used, ${Math.round(elapsed * 100)}% of the year gone`,
        detail: `FY${g.fy} as of ${g.as_of}: ${usd(spent)} of ${usd(b)} spent or encumbered. At this pace the budget runs out before the year ends. ` +
          'Costs paid once a year (insurance, software licenses, debt payments) look like this legitimately: mark those explained.',
        amount_at_risk: ahead, refs, facts: {fiscal_year: g.fy, used: round2(used), elapsed: round2(elapsed)}}));
    }
  }
  return out;
}

// ---- Rules 7-10: payments ----
function paymentRules({disb, s}) {
  const out = [];
  const voidDocs = new Set(disb.filter(d => d.is_void || d.amount < 0).map(d => d.doc_no).filter(Boolean));
  const live = disb.filter(d => !d.is_void && d.amount > 0 && d.paid_on && !voidDocs.has(d.doc_no));
  const byPayee = new Map();
  for (const d of live) { if (!d.payee_key) continue; if (!byPayee.has(d.payee_key)) byPayee.set(d.payee_key, []); byPayee.get(d.payee_key).push(d); }
  for (const list of byPayee.values()) list.sort((a, b) => a.paid_on.localeCompare(b.paid_on) || String(a.doc_no).localeCompare(String(b.doc_no)));

  // Rule 7: same payee and amount within the window, or the same invoice number paid twice.
  for (const [key, list] of byPayee) {
    const seen = new Set();
    for (let i = 0; i < list.length; i++) for (let j = i + 1; j < list.length; j++) {
      const a = list[i], b = list[j];
      if (days(a.paid_on, b.paid_on) > s.duplicate_window_days) break;
      if (a.doc_no && a.doc_no === b.doc_no) continue;
      const sameInvoice = a.invoice_no && b.invoice_no && a.invoice_no.toUpperCase() === b.invoice_no.toUpperCase();
      if (sameInvoice || (a.amount === b.amount && a.amount >= s.duplicate_min_amount)) {
        const id = [a.id, b.id].join('-'); if (seen.has(id)) continue; seen.add(id);
        out.push(flag('duplicate_payment', sameInvoice ? 'urgent' : 'review', [key, a.amount, a.paid_on, b.paid_on, a.doc_no, b.doc_no], {
          title: `${a.payee}: ${usd(b.amount)} paid twice${sameInvoice ? ` on invoice ${a.invoice_no}` : ` within ${days(a.paid_on, b.paid_on)} days`}`,
          detail: `${a.doc_no ? 'Check ' + a.doc_no : 'A payment'} on ${niceDate(a.paid_on)} (${usd(a.amount)}) and ${b.doc_no ? 'check ' + b.doc_no : 'another'} on ${niceDate(b.paid_on)} (${usd(b.amount)}).` +
            (sameInvoice ? ' Same invoice number on both.' : ' Recurring bills of the same amount (rent, utilities) trip this rule; mark those explained.'),
          amount_at_risk: Math.min(a.amount, b.amount), refs: [{table: 'disbursements', id: a.id}, {table: 'disbursements', id: b.id}],
          facts: {payee: a.payee, same_invoice: !!sameInvoice}}));
      }
    }
  }

  // Rule 8: two or more payments to one vendor, each under an approval threshold (and at least half of it),
  // inside the window, adding up past the threshold.
  for (const [key, list] of byPayee) {
    for (const [T, sev, who, win, share] of [[s.bid_threshold, 'review', 'need Commission approval and formal bids', s.split_window_days, 0.5],
                                              [s.manager_threshold, 'info', 'need City Manager approval', s.split_window_days_small, s.split_min_share_small]]) {
      const near = list.filter(d => d.amount < T && d.amount >= T * share);
      let i = 0;
      while (i < near.length) {
        let j = i, sum = 0;
        while (j < near.length && days(near[i].paid_on, near[j].paid_on) <= win) { sum += near[j].amount; j++; }
        if (j - i >= 2 && sum >= T) {
          const grp = near.slice(i, j);
          out.push(flag('split_purchase', sev, [key, T, grp.map(d => d.id).join(',')], {
            title: `${grp[0].payee}: ${grp.length} payments under ${usd(T)} total ${usd(round2(sum))} in ${days(grp[0].paid_on, grp[grp.length - 1].paid_on)} days`,
            detail: `Purchases of ${usd(T)} and up ${who}. Payments: ${grp.map(d => `${niceDate(d.paid_on)}, ${usd(d.amount)}`).join('; ')}. ` +
              'Check whether these were one purchase split up, or separate needs.',
            amount_at_risk: sum, refs: grp.map(d => ({table: 'disbursements', id: d.id})), facts: {payee: grp[0].payee, threshold: T, count: grp.length}}));
          i = j;
        } else i++;
      }
    }
  }

  // Rule 9: exact round amounts, and payments dated on weekends or federal holidays.
  for (const d of live) {
    const reasons = [];
    if (d.amount >= s.round_dollar_min && Math.abs(d.amount % 1000) < 0.005) reasons.push('an exact round amount');
    if (d.amount >= s.weekend_min) {
      const w = weekday(d.paid_on);
      if (w === 0 || w === 6) reasons.push(`dated on a ${w === 0 ? 'Sunday' : 'Saturday'}`);
      else if (isHoliday(d.paid_on)) reasons.push('dated on a federal holiday');
    }
    if (!reasons.length) continue;
    out.push(flag('round_or_weekend', 'info', [d.id, d.amount, d.paid_on], {
      title: `${d.payee}: ${usd(d.amount)}, ${reasons.join(' and ')}`,
      detail: `${d.doc_no ? 'Check ' + d.doc_no : 'Payment'} on ${niceDate(d.paid_on)}. Round amounts and off-day payments are common in fraud cases but usually have ordinary explanations (deposits, retainers, grants, batch dates).`,
      amount_at_risk: d.amount, refs: [{table: 'disbursements', id: d.id}], facts: {payee: d.payee, reasons}}));
  }

  // Rule 10: a vendor's month far above its usual paid month (median of the months it was paid in the prior year).
  const months = [...new Set(live.map(d => d.paid_on.slice(0, 7)))].sort();
  if (months.length) {
    const all = []; for (let ym = months[0]; ym <= months[months.length - 1]; ym = nextMonth(ym)) all.push(ym);
    for (const [key, list] of byPayee) {
      const tot = new Map();
      for (const d of list) { const ym = d.paid_on.slice(0, 7); tot.set(ym, (tot.get(ym) || 0) + d.amount); }
      all.forEach((ym, idx) => {
        const cur = tot.get(ym) || 0;
        if (!cur || idx < s.spike_history_months) return;
        const window = all.slice(Math.max(0, idx - 12), idx), paid = window.map(m => tot.get(m) || 0).filter(x => x > 0);
        const first = list.find(d => d.paid_on.slice(0, 7) === ym);
        const refs = list.filter(d => d.paid_on.slice(0, 7) === ym).map(d => ({table: 'disbursements', id: d.id}));
        if (!paid.length) {
          if (cur >= s.new_vendor_large) out.push(flag('payee_spike', 'info', [key, ym, round2(cur), 'new'], {
            title: `${first.payee}: ${usd(cur)} in ${monthName(ym)}, first payment in ${window.length} months of records`,
            detail: 'A large first payment to a vendor. Confirm the vendor record, W-9 and the contract or purchase order behind it.',
            amount_at_risk: cur, refs, facts: {payee: first.payee, month: ym, total: round2(cur)}}));
          return;
        }
        if (paid.length < 3) return; // too little history to call anything usual
        const med = median(paid);
        if (cur > s.spike_multiple * med && cur - med >= s.spike_min_increase) {
          out.push(flag('payee_spike', 'review', [key, ym, round2(cur)], {
            title: `${first.payee}: ${usd(cur)} in ${monthName(ym)}, ${(cur / med).toFixed(1)}× its usual month`,
            detail: `In the ${paid.length} months it was paid during the prior year, its typical month was ${usd(med)}.`,
            amount_at_risk: cur - med, refs, facts: {payee: first.payee, month: ym, total: round2(cur), median: round2(med)}}));
        }
      });
    }
  }
  return out;
}

// ---- Rule 16: prior audit findings still open ----
// A reconciliation finding stays "review" until three straight months of recs are on file, on time and in balance;
// then it drops to "info" as evidence of corrective action.
function auditRepeat({findings, recFlags, bankRecs, today, s}) {
  const out = [], latest = new Map();
  for (const f of findings) if (!latest.has(f.topic) || f.fiscal_year > latest.get(f.topic).fiscal_year) latest.set(f.topic, f);
  for (const f of latest.values()) {
    const years = findings.filter(x => x.topic === f.topic).map(x => x.fiscal_year).sort();
    let severity = 'review', evidence = '';
    if (f.topic === 'reconciliation') {
      const recent = [...new Set(bankRecs.map(r => r.period_end && r.period_end.slice(0, 7)).filter(Boolean))].sort().slice(-3);
      const clean = recent.length === 3 && !recFlags.some(x => x.severity !== 'info') && days(monthEnd(recent[2]), today) <= s.rec_due_days + 31;
      if (clean) { severity = 'info'; evidence = ` The last three months of recs (${recent.join(', ')}) are on file, on time and in balance: evidence the finding is being fixed.`; }
      else evidence = ' The dashboard will mark this as improving once three straight months of recs are uploaded, on time and in balance.';
    }
    out.push(flag('audit_repeat', severity, [f.topic, f.fiscal_year, severity], {
      title: `Audit finding ${f.finding_id}: ${f.title}`,
      detail: `Reported in FY${years.join(', FY')}${f.repeat ? ' (repeat finding)' : ''}. Latest management response: ${f.mgmt_response || 'none recorded'}.${evidence}`,
      refs: [{table: 'audit_findings', id: f.id}], facts: {topic: f.topic, years, source_url: f.source_url}}));
  }
  return out;
}

// data: {workspace, uploads, budget, disbursements, bankTxns, bankRecs, findings, today}
function runRules(data) {
  const s = {...DEFAULTS, ...(data.workspace?.settings || {})};
  const today = data.today || new Date().toISOString().slice(0, 10);
  const fyStartMonth = data.workspace?.fy_start_month || 10;
  const disb = data.disbursements || [], bankTxns = data.bankTxns || [], recs = data.bankRecs || [];
  const recFlags = bankRecs({bankTxns, bankRecs: recs, today, s});
  const flags = [
    ...fileTie(data.uploads || []),
    ...recFlags,
    ...staleChecks({disb, bankTxns, s}),
    ...budgetRules({budget: data.budget || [], s, fyStartMonth}),
    ...paymentRules({disb, s}),
    ...auditRepeat({findings: data.findings || [], recFlags, bankRecs: recs, today, s}),
  ];
  const seen = new Set();
  return flags.filter(f => (seen.has(f.fingerprint) ? false : seen.add(f.fingerprint))).sort((a, b) => b.score - a.score);
}

module.exports = {runRules, DEFAULTS, RULES, isRevenue, holidays, usd};
