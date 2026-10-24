// Where each page's data comes from in the API. Every page listed in /data/app/pages.json must appear here, so a new
// page can't ship without its data being in the database and reachable through /api/v1 (api/__tests__/pages.test.js
// fails, naming the page, when one is missing or points at a dataset that doesn't exist).
// Served at GET /api/v1/pages. `none` explains a page that has no data of its own (a form, a policy, docs).
const PAGES = {
  '/': {datasets: ['site-updates', 'government-profiles', 'budget-detail', 'budget-per-resident', 'property-tax-rates', 'tax-districts', 'fema-michael-projects', 'debt', 'audit-findings', 'sales-tax-projects', 'cra-payments'],
    endpoints: ['/search']},
  '/my-address': {datasets: ['tax-districts', 'property-tax-rates', 'fees-assessments', 'cra-payments', 'property-tax-exemptions', 'meetings'],
    note: 'Per-parcel lookups (exemptions, districts) are not in the API yet.'},
  '/public-money/cra-spending': {datasets: ['cra-payments']},
  '/public-money/tax-dollars': {datasets: ['property-tax-rates', 'tax-districts', 'budget-detail']},
  '/public-money/amendment-3': {datasets: ['property-tax-rates', 'tax-districts', 'property-tax-exemptions']},
  '/public-money/hurricane-michael': {datasets: ['fema-michael-projects']},
  '/public-money/tourist-tax': {datasets: ['bed-tax-collections']},
  '/public-money/sales-tax-projects': {datasets: ['sales-tax-projects']},
  '/public-money/fees-and-bills': {datasets: ['fees-assessments']},
  '/governments': {datasets: ['government-profiles'], endpoints: ['/governments']},
  '/compare': {datasets: ['government-profiles', 'budget-per-resident'], endpoints: ['/governments']},
  '/open-data': {endpoints: ['/datasets', '/status']},
  '/developers': {endpoints: ['/openapi.json'], none: 'API documentation'},
  '/records-request': {none: 'a form that writes a records request'},
  '/correspondence': {endpoints: ['/correspondence']},
  '/connections/shared-owners': {datasets: ['shared-owner-groups']},
  '/alerts': {none: 'email alert sign-up form'},
  '/meetings': {datasets: ['meetings'], endpoints: ['/meetings.ics']},
  '/connections/campaign-gifts': {datasets: ['campaign-finance', 'donor-contracts', 'campaign-contributions-2026', 'business-donor-sunbiz']},
  '/who-runs-bay-county': {datasets: ['people-directory', 'officials-pay', 'salary-leaders']},
  '/public-money/budget-explorer': {datasets: ['budget-detail', 'budget-per-resident']},
  '/elections': {datasets: ['candidates-2026', 'campaign-contributions-2026']},
  '/public-money/exemptions': {datasets: ['property-tax-exemptions']},
  '/connections/money-map': {datasets: ['money-map-gifts', 'money-map-contracts', 'money-map-votes']},
  '/public-money/who-gets-paid': {datasets: ['vendor-payments']},
  '/public-money/contracts': {datasets: ['contracts', 'change-orders', 'emergency-purchases']},
  '/public-money/accountability': {datasets: ['accountability-projects', 'accountability-events']},
  '/public-money/savings': {datasets: ['savings-opportunities', 'savings-evidence']},
  '/public-money/votes': {datasets: ['votes', 'member-votes']},
  '/public-money/debt': {datasets: ['debt', 'bonds']},
  '/public-money/audits': {datasets: ['audit-findings']},
  '/glossary': {datasets: ['glossary-terms']},
  '/updates': {datasets: ['site-updates'], endpoints: ['/changes']},
  '/search': {endpoints: ['/search']},
  '/about': {none: 'about the site'},
  '/privacy': {none: 'privacy policy'},
  '/connections': {datasets: ['connections-payees', 'connections-payments', 'connections-links', 'connections-gifts']},
  '/public-money/map': {datasets: ['cra-payments', 'sales-tax-projects', 'fema-michael-projects']},
  '/public-money/vendors': {datasets: ['vendors-directory', 'contracts', 'vendor-payments', 'cra-payments', 'campaign-contributions-2026']},
};
// Page families: each government's profile page.
// a government's page carries the dashboards' records for that government (gov.js narrows them by city and year)
const PREFIXES = {'/governments/': {datasets: ['government-profiles', 'government-years', 'budget-detail', 'officials-pay', 'votes', 'meetings', 'contracts', 'cra-payments',
  'accountability-projects', 'sales-tax-projects', 'fema-michael-projects', 'savings-opportunities', 'debt', 'audit-findings'], endpoints: ['/governments/{slug}']}};

function sourceFor(path) {
  if (PAGES[path]) return PAGES[path];
  const k = Object.keys(PREFIXES).find(p => path.startsWith(p));
  return k ? PREFIXES[k] : null;
}

module.exports = {PAGES, PREFIXES, sourceFor};
