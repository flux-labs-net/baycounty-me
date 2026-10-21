"""Public records request generator (/records-request).

Each suggestion is a record this site is missing (see the 'What we couldn't find' notes
on each page). Residents can send the request themselves; Florida law (Ch. 119, F.S.)
lets anyone ask, without giving a name or reason.
"""
import json, os
from govs import GOVS, _load

HERE = os.path.dirname(os.path.abspath(__file__))

# Records the site is missing, written as requests. Keep them specific and answerable.
SUGGEST = {
    'county': [
        ('Check registers, FY2023', 'The check registers (accounts payable disbursement reports) for the Board of County Commissioners for October 1, 2022 through December 31, 2023, in electronic format (Excel or CSV if available).'),
        ('County manager contract', 'The current employment agreement for the County Manager, including any amendments, and his current annual salary.'),
        ('FY2026 and FY2027 budget hearing minutes', 'The approved minutes of the Board of County Commissioners budget hearings held September 3 and September 16, 2025, and September 2026, and the July 21, 2026 meeting at which the maximum millage was set.'),
        ('Tourist Development Plan', 'The current Tourist Development Plan and any resolution or ordinance setting how the tourist development tax is allocated by cent.'),
        ('AshBritt debris contract', 'The Hurricane Michael debris removal contract with AshBritt, Inc., all amendments, and the total amount paid under it.'),
        ('Front Beach Road CRA agreement', 'The 2024 interlocal agreement with the City of Panama City Beach capping Front Beach Road CRA revenue, and a list of all payments or rebates made under the 2020 interlocal agreement.'),
    ],
    'schools': [
        ('Board meeting minutes', 'The approved minutes of all School Board meetings from January 1, 2024 to date, including roll-call votes.'),
        ('Final FY2025-26 budget', 'The final adopted FY2025-26 budget (all funds) and the adopted millage resolution.'),
        ('Half-cent project list', 'The project list presented with the 2018 school half-cent sales tax referendum, and a report of surtax spending by project from 2019 to date.'),
        ('Contracts over $100,000', 'A list of contracts over $100,000 approved by the School Board since July 1, 2023, with vendor, amount and approval date.'),
    ],
    'pc': [
        ('Check registers', 'The City\'s check registers or accounts payable reports for fiscal year 2025-26 to date, in electronic format (Excel or CSV if available).'),
        ('City manager pay', 'The current employment agreement for the City Manager, including salary and benefits.'),
        ('CRA payments to vendors', 'A vendor-level payment report for the Community Redevelopment Agency (Fund 701) for fiscal years 2021-22 through 2025-26.'),
        ('$150M Series 2023 note', 'The resolution authorizing the $150 million Capital Improvement Revenue Note, Series 2023, the loan agreement, and the list of projects it funds.'),
        ('Martin Theatre contracts', 'The original construction contract and all change orders for the Martin Theatre project.'),
    ],
    'pcb': [
        ('Council minutes, 2024', 'The approved minutes of all City Council meetings held in calendar year 2024, including the September 2024 budget and millage hearings.'),
        ('Check registers', 'The City\'s check registers or accounts payable reports for fiscal year 2025-26 to date, in electronic format.'),
        ('Front Beach Road Segment 3 contract', 'The original construction contract for Front Beach Road Segment 3 (Resolution 21-127) and change orders 1 through 6 with their amounts.'),
        ('Residential garbage rate', 'The current residential garbage collection rate schedule and the number of full-time-equivalent employees in the adopted FY2025-26 budget.'),
        ('CRA bond documents', 'The official statements and most recent annual continuing disclosure for the Front Beach Road CRA Series 2006, 2015, 2020 and any 2024 bonds.'),
    ],
    'lh': [
        ('Check registers, FY2026', 'The City\'s check registers or accounts payable reports for fiscal year 2025-26 to date, in electronic format.'),
        ('FY2026-27 budget', 'The adopted FY2026-27 budget, including the utility rate schedule effective October 1, 2026.'),
        ('City manager pay', 'The current employment agreement for the City Manager, including salary.'),
        ('Commission seat terms', 'A list of the current Mayor and Commissioners with the date each term began and ends.'),
        ('CRA budget, FY2025-26', 'A readable copy of the approved FY2025-26 Community Redevelopment Agency budget, with line items.'),
    ],
    'cw': [
        ('Adopted budget', 'The adopted FY2025-26 and FY2026-27 budgets, including general fund detail by department.'),
        ('Check registers', 'The City\'s check registers or accounts payable reports for fiscal year 2025-26 to date, in electronic format.'),
        ('Contracts over $50,000', 'A list of contracts over $50,000 approved by the City Commission since October 1, 2022, with vendor, amount and approval date.'),
        ('CRA annual reports', 'The Community Redevelopment Agency annual reports for 2021 through 2025 and its adopted budgets for FY2024 through FY2027.'),
    ],
    'sp': [
        ('Adopted budget', 'The adopted FY2025-26 and FY2026-27 budgets, including general fund detail by department.'),
        ('Budget hearing minutes', 'The approved minutes of the final budget hearings held September 16, 2024 and September 22, 2026.'),
        ('Contracts and purchases', 'A list of contracts and purchase orders over $25,000 approved since October 1, 2022, with vendor, amount and approval date.'),
        ('Check registers', 'The City\'s check registers or accounts payable reports for fiscal year 2025-26 to date, in electronic format.'),
        ('Employee count', 'The number of full-time and part-time employees in the adopted FY2025-26 budget.'),
    ],
    'parker': [
        ('Final FY2025-26 budget', 'The final adopted FY2025-26 budget in a text-searchable format, and the FY2026-27 adopted budget.'),
        ('Utility rates', 'The current water, sewer and garbage rate schedules.'),
        ('Council minutes since April 2024', 'The approved minutes of City Council meetings from April 2024 to date, including the September 24, 2026 final budget hearing.'),
        ('CRA records', 'The Community Redevelopment Agency\'s adopted budgets for FY2025 through FY2027 and any annual reports.'),
    ],
    'mb': [
        ('Adopted budget', 'The adopted FY2025-26 and FY2026-27 budgets, including general fund detail by department.'),
        ('Check registers', 'The City\'s check registers or accounts payable reports for fiscal year 2025-26 to date, in electronic format.'),
        ('Debris contracts', 'The Hurricane Michael debris removal contracts and the total paid to each contractor.'),
        ('Employee count and administrator pay', 'The number of full-time-equivalent employees and the City Administrator\'s current salary and contract.'),
    ],
}


L_EN = {'sendTo': 'Send to:', 'email': 'Email:', 'phone': 'Phone:', 'mail': 'Mail:', 'online': 'Online:', 'portal': 'records request portal',
        'noEmail': "We don't have a records email on file.", 'contact': 'Contact page', 'site': 'Website', 'askClerk': 'ask for the city clerk or records custodian.',
        'policy': 'Their records policy', 'other': 'Something else', 'otherD': 'Write your own description below.',
        'copied': 'Copied. Paste it into an email or letter.', 'selectAll': 'Select all and copy.',
        'namePh': '[Your name]', 'emailPh': '[Your email]', 'need': 'Add your name and email first. The office needs them to send a cost estimate and the records.'}


# Who the letter is addressed to (records.json custodian_title holds research notes, not a salutation)
TO = {'county': 'Public Records Custodian', 'schools': 'Records Management Liaison Officer', 'lh': 'Public Records Custodian',
      'pc': 'City Clerk', 'pcb': 'City Clerk', 'cw': 'City Clerk', 'sp': 'City Clerk', 'parker': 'City Clerk', 'mb': 'City Clerk'}


def records_data():
    D = _load()
    rec = {}
    for a in (D.get('records') or {}).get('agencies', []):
        if a.get('gov') in {g['key'] for g in GOVS} and a.get('gov') not in rec:
            rec[a['gov']] = a
    out = []
    for g in GOVS:
        fg = next((x for x in D['fees']['governments'] if x['name'] == g['fees']), {})
        a = rec.get(g['key'], {})
        out.append({'k': g['key'], 'n': g['short'], 'agency': a.get('name') or g['name'], 'title': TO.get(g['key'], 'Records Custodian'),
                    'email': a.get('email'), 'phone': a.get('phone'), 'address': a.get('address'), 'portal': a.get('portal_url'),
                    'policy': a.get('policy_url'), 'site': fg.get('website'), 'contact': fg.get('contact_url'),
                    's': [{'t': t, 'd': d} for t, d in SUGGEST.get(g['key'], [])]})
    return out


def records_page(out_dir):
    js = open(os.path.join(HERE, 'records.js')).read().replace('__REC__', json.dumps(records_data(), separators=(',', ':'))).replace('__L__', json.dumps(L_EN))
    open(os.path.join(out_dir, 'assets', 'records.js'), 'w').write(js)
    return '''<div class="page tax">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Get involved</span><h1>Request a public record</h1>
    <p class="lede">Florida's public records law lets anyone see government records, without saying why. Pick a government and a record this site is missing, or describe your own, and we'll write the request for you.</p></div></header>
  <div class="rq">
    <div class="rq-form">
      <label class="vf"><span>1. Government</span><select id="rqG"></select></label>
      <div class="vf"><span>2. What do you want?</span><div id="rqS" class="rq-s" role="radiogroup" aria-label="Suggested records"></div></div>
      <label class="vf"><span>Describe the records</span><textarea id="rqD" rows="5" placeholder="Be specific: what, which dates, which department. For example: the contract and change orders for the Martin Theatre project."></textarea></label>
      <div class="cf-row"><label class="vf"><span>Your name</span><input id="rqN" type="text" autocomplete="name" required></label>
        <label class="vf"><span>Your email</span><input id="rqC" type="email" autocomplete="email" required></label></div>
      <label class="vf"><span>Phone <em>(optional)</em></span><input id="rqP" type="tel" autocomplete="tel"></label>
      <p class="note small">Many requests carry a copying or staff-time charge. Your name and email let the office send you a cost estimate and the records.</p>
      <label class="chk"><input type="checkbox" id="rqE" checked> Ask for electronic copies</label>
    </div>
    <div class="rq-out">
      <div class="rq-to" id="rqTo"></div>
      <label class="vf"><span>Your request</span><textarea id="rqL" rows="16" readonly></textarea></label>
      <div class="rq-btns"><button type="button" class="pill" id="rqCopy">Copy</button><a class="pill" id="rqMail" href="#">Open in email</a><a class="pill" id="rqPortal" href="#" target="_blank" rel="noopener" hidden>Open records portal</a><button type="button" class="pill" id="rqPrint">Print</button></div>
      <p class="note small" id="rqMsg" role="status"></p>
    </div>
  </div>
  <section class="tx-sec method"><div class="sec-hd"><h2 id="tips">Good to know</h2></div><ul class="plain">
    <li><b>Anyone can ask.</b> Under Chapter 119, Florida Statutes, you can request records in person, by phone, email or letter, and you don't have to explain why. The law doesn't require your name, but when there's a charge the office needs a way to send the estimate, collect payment and deliver the records, so this form includes it.</li>
    <li><b>Costs.</b> Agencies may charge for copies (usually 15 cents a page) and, for requests that take extensive staff time, a special service charge. The request asks them to tell you before running up a charge.</li>
    <li><b>Exemptions.</b> If they hold something back, they must tell you which law exempts it and release the rest.</li>
    <li><b>Help this site.</b> If you get records that fill a gap here, <a href="/about#contact">send them in</a> and we'll add them with credit to the public record.</li>
    <li><b>The office replies to you.</b> The letter says it was prepared on BayCounty.me, and asks that every reply, cost estimate and record go directly to you. BayCounty.me doesn't receive anything.</li>
    <li>This page writes the request; it doesn't send it or keep a copy. Nothing you type here is stored.</li></ul></section>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<script src="/assets/records.js" defer></script>'''
