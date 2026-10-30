// Where each page's data comes from in the API. Every page listed in /data/app/pages.json must appear here, so a new
// page can't ship without its data being in the database and reachable through /api/v1 (api/__tests__/pages.test.js
// fails, naming the page, when one is missing or points at a dataset that doesn't exist).
// Served at GET /api/v1/pages. `none` explains a page that has no data of its own (a form, a policy, docs).
const PAGES = {
  '/': {datasets: ['site-updates', 'government-profiles', 'budget-detail', 'budget-per-resident', 'property-tax-rates', 'tax-districts', 'fema-michael-projects', 'debt', 'audit-findings', 'sales-tax-projects', 'cra-payments', 'community-events'],
    endpoints: ['/search']},
  // the realtor console prints the address report; agent accounts and branding are private (api/_realtor.js, migration 0074)
  '/realtor': {datasets: ['tax-districts', 'property-tax-rates', 'sales-tax-projects', 'people-directory', 'officeholder-terms', 'schools', 'school-zones', 'utility-providers', 'trash-pickup', 'trash-holidays', 'utility-rates', 'parks', 'beach-access', 'development-projects', 'road-contracts'], endpoints: ['/address-report'],
    note: 'Live map lookups (parcel, flood, districts) are made by the address-report endpoint at request time.'},
  '/my-address': {datasets: ['tax-districts', 'property-tax-rates', 'fees-assessments', 'cra-payments', 'property-tax-exemptions', 'meetings', 'schools', 'school-zones', 'utility-providers', 'trash-pickup', 'trash-holidays'], endpoints: ['/schools', '/utilities'],
    note: 'Per-parcel lookups (exemptions, districts) are not in the API yet.'},
  // a resident's own page: their saved home and choices are private (api/_account.js, migration 0077); what it shows is
  // the public nearby feed for that home
  '/account': {datasets: ['meetings', 'community-events', 'development-projects', 'sales-tax-projects', 'road-contracts', 'public-notices', 'restaurant-inspections', 'restaurants', 'new-businesses', 'beach-conditions', 'beach-access', 'trash-pickup'],
    endpoints: ['/nearby', '/emergency', '/utilities'], note: 'The saved home address and notification choices belong to the signed-in resident and are never published.'},
  '/public-money/cra-spending': {datasets: ['cra-payments']},
  '/public-money/cra-tax-increment': {datasets: ['cra-agencies', 'cra-tax-increment', 'cra-increment-checks', 'property-tax-rates']},
  '/public-money/tax-dollars': {datasets: ['property-tax-rates', 'tax-districts', 'budget-detail']},
  '/public-money/amendment-3': {datasets: ['property-tax-rates', 'tax-districts', 'property-tax-exemptions']},
  '/public-money/hurricane-michael': {datasets: ['fema-michael-projects']},
  '/public-money/tourist-tax': {datasets: ['bed-tax-collections', 'vendor-payments']},
  '/public-money/sales-tax-projects': {datasets: ['sales-tax-projects']},
  '/public-money/fees-and-bills': {datasets: ['fees-assessments']},
  '/governments': {datasets: ['government-profiles', 'data-completeness'], endpoints: ['/governments', '/import-progress']},
  '/compare': {datasets: ['government-profiles', 'budget-per-resident', 'debt', 'audit-findings'], endpoints: ['/governments']},
  '/open-data': {endpoints: ['/datasets', '/status']},
  '/developers': {endpoints: ['/openapi.json'], none: 'API documentation'},
  '/records-request': {none: 'a form that writes a records request'},
  '/correspondence': {endpoints: ['/correspondence']},
  '/connections/shared-owners': {datasets: ['shared-owner-groups', 'over-limit-gifts', 'shared-owner-vendors']},
  '/events': {datasets: ['community-events']},
  '/beaches': {datasets: ['beach-conditions', 'beach-water-sites', 'beach-water-samples', 'beach-access', 'beach-parking']},
  '/parks': {datasets: ['parks', 'boat-ramps', 'trails', 'recreation-departments']},
  '/development': {datasets: ['housing-permits', 'development-projects', 'development-companies']},
  '/roads': {datasets: ['road-contracts', 'road-work-program', 'sales-tax-projects', 'entity-profiles']},
  '/schools': {datasets: ['schools', 'school-grades', 'school-grade-state', 'school-bell-times', 'school-spending', 'school-enrollment', 'school-calendar', 'school-zones', 'meetings'], endpoints: ['/schools', '/overlaps']},
  '/utilities': {datasets: ['utility-providers', 'trash-pickup', 'trash-holidays', 'utility-rates'], endpoints: ['/utilities']},
  '/restaurants': {datasets: ['restaurants', 'restaurant-inspections']},
  '/new-businesses': {datasets: ['new-businesses', 'restaurants']},
  '/this-week': {datasets: ['weekly-roundup', 'community-events', 'meetings', 'votes', 'contracts', 'change-orders']},
  '/volunteer': {datasets: ['volunteer-needs', 'volunteer-orgs', 'nonprofits']},
  '/chambers': {datasets: ['chambers', 'chamber-leaders', 'chamber-events', 'nonprofit-payments', 'nonprofits', 'person-photos', 'chamber-overlaps']},
  '/military': {datasets: ['military-installations', 'military-news', 'federal-contracts', 'federal-contract-years']},
  '/public-safety': {datasets: ['safety-agencies', 'crime-counts', 'crime-monthly', 'police-staffing']},
  '/connections/nonprofits': {datasets: ['nonprofits', 'nonprofit-board-members', 'nonprofit-board-businesses', 'nonprofit-payments', 'nonprofit-grants', 'nonprofit-officials', 'charity-registrations', 'person-photos'], endpoints: ['/overlaps']},
  '/connections/business-ties': {datasets: ['official-businesses', 'official-business-links'], endpoints: ['/overlaps']},
  // overlaps between datasets (site/correlations.py); the hand-confirmed and checkbook joins are live (api/_overlaps.js)
  '/connections/overlaps': {datasets: ['donor-votes', 'vote-mentions', 'agenda-parties', 'development-companies', 'bid-trail', 'shared-owner-vendors', 'chamber-overlaps',
    'emergency-purchase-donors', 'campaign-results', 'official-businesses', 'nonprofit-officials', 'nonprofit-payments', 'checkbook-payments', 'school-grades', 'school-spending'],
  endpoints: ['/overlaps']},
  '/emergency': {datasets: ['evacuation-zones', 'emergency-shelters', 'emergency-resources', 'emergency-notices'], endpoints: ['/emergency', '/emergency-timeline', '/evacuation-zone']},
  '/hurricane-prep': {datasets: ['hurricane-prep', 'disaster-declarations', 'rebuild-money'], endpoints: ['/emergency']},
  '/alerts': {none: 'email alert sign-up form'},
  '/meetings': {datasets: ['meetings', 'agenda-parties'], endpoints: ['/meetings.ics']},
  '/connections/campaign-gifts': {datasets: ['campaign-finance', 'donor-contracts', 'campaign-contributions-2026', 'business-donor-sunbiz', 'owner-gifts'], endpoints: ['/overlaps']},
  '/public-money/budget-compare': {datasets: ['budget-years', 'government-years'], endpoints: ['/budget-compare']},
  '/public-money/checkbook': {datasets: ['checkbook-payments'], endpoints: ['/checkbook']},
  '/public-money/budget-tracker': {datasets: ['budget-actuals'], endpoints: ['/budget-actual']},
  '/elections': {datasets: ['candidates-2026', 'campaign-contributions-2026', 'election-dates']},
  '/elections/past': {datasets: ['campaign-history', 'campaign-contributions-history', 'campaign-results']},
  '/elections/results': {datasets: ['elections', 'election-results']},
  '/elections/voting': {datasets: ['election-dates', 'voting-locations', 'candidates-2026']},
  '/notices': {datasets: ['public-notices', 'bid-trail']},
  '/jobs': {datasets: ['job-openings', 'job-boards']},
  '/public-money/exemptions': {datasets: ['property-tax-exemptions']},
  '/public-money/contracts': {datasets: ['contracts', 'change-orders', 'emergency-purchases', 'emergency-purchase-donors'], endpoints: ['/overlaps']},
  '/public-money/accountability': {datasets: ['accountability-projects', 'accountability-events']},
  '/public-money/votes': {datasets: ['votes', 'member-votes', 'donor-votes', 'vote-mentions']},
  '/glossary': {datasets: ['glossary-terms']},
  '/updates': {datasets: ['site-updates'], endpoints: ['/changes']},
  '/search': {endpoints: ['/search']},
  '/ask': {none: 'a chatbot: answers come from the MCP tools (api/mcp.js) over the same datasets and endpoints, through /api/chat'},
  '/about': {none: 'about the site'},
  '/data-sources': {datasets: ['data-sources', 'data-source-sites', 'data-freshness'], endpoints: ['/import-progress']},
  '/privacy': {none: 'privacy policy'},
  '/connections': {datasets: ['connections-payees', 'connections-payments', 'connections-links', 'connections-gifts', 'money-map-gifts', 'money-map-contracts', 'money-map-votes']},
  '/public-money/vendors': {datasets: ['vendors-directory', 'contracts', 'vendor-payments', 'cra-payments', 'campaign-contributions-2026', 'entity-profiles', 'entity-connections'],
    endpoints: ['/entities/{id}']},
  '/people': {datasets: ['entity-profiles', 'people-directory', 'owner-gifts', 'officials-pay', 'salary-leaders', 'officeholder-terms', 'official-photos', 'person-photos'], endpoints: ['/entities']},
  // one shell page for every other profile: /profile/<kind>/<id> (vercel.json rewrite), filled from the API
  '/profile': {datasets: ['entity-profiles', 'entity-connections', 'business-officers', 'nonprofit-officials', 'official-businesses', 'official-business-links', 'shared-owner-groups', 'owner-gifts', 'person-photos'],
    endpoints: ['/entities/{id}']},
};
// Page families: each government's profile page.
// a government's page carries the dashboards' records for that government (gov.js narrows them by city and year), and its
// whole budget, debt, audits and savings ideas (site/gov_detail.py), which used to be dashboards of their own
const PREFIXES = {'/governments/': {datasets: ['government-profiles', 'government-years', 'budget-detail', 'officials-pay', 'votes', 'meetings', 'contracts', 'cra-payments',
  'accountability-projects', 'sales-tax-projects', 'fema-michael-projects', 'savings-opportunities', 'savings-evidence', 'debt', 'bonds', 'audit-findings', 'budget-per-resident', 'entity-connections', 'officeholder-terms', 'official-photos', 'person-photos', 'data-completeness'], endpoints: ['/governments/{slug}', '/entities/{id}', '/officials', '/import-progress']},
  // each official's and candidate's profile (site/people_pages.py)
  '/people/': {datasets: ['entity-profiles', 'entity-connections', 'people-directory', 'member-votes', 'campaign-finance', 'campaign-history', 'candidates-2026', 'officials-pay', 'salary-leaders',
    'money-map-votes', 'nonprofit-officials', 'official-businesses', 'official-business-links', 'shared-owner-groups', 'owner-gifts', 'officeholder-terms', 'official-photos', 'person-photos'], endpoints: ['/entities/{id}']},
  // one page per restaurant license (site/restaurants_page.py, page_url in the restaurants dataset)
  '/restaurants/': {datasets: ['restaurants', 'restaurant-inspections'], note: 'Filter by license_number: /api/v1/datasets/restaurant-inspections?license_number=...&sort=-date'},
  '/public-money/vendors/': {datasets: ['vendors-directory', 'contracts', 'change-orders', 'emergency-purchases', 'vendor-payments', 'cra-payments', 'campaign-contributions-2026', 'campaign-contributions-history', 'votes',
    'entity-profiles', 'entity-connections'], endpoints: ['/entities/{id}']}};

function sourceFor(path) {
  if (PAGES[path]) return PAGES[path];
  const k = Object.keys(PREFIXES).find(p => path.startsWith(p));
  return k ? PREFIXES[k] : null;
}

module.exports = {PAGES, PREFIXES, sourceFor};
