// Letters for records requests drafted when a source goes stale (data/civic/scripts/stale_requests.py finds the gaps).
// compose(check, gaps) -> {subject, body} for just the gaps that haven't been requested yet, so a request never asks
// again for something already sent. Add a letter here when a check is added there.
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
const longDate = s => { const [y, m, d] = String(s).slice(0, 10).split('-').map(Number); return `${MONTHS[m - 1]} ${d}, ${y}`; };
const andList = xs => xs.length < 2 ? xs.join('') : xs.slice(0, -1).join(', ') + ' and ' + xs[xs.length - 1];
const SIGNATURE = 'Jeremy McSpadden\nBayCounty.me';
const CLOSING = `This is a non-commercial request. The records will be shown to residents on BayCounty.me, an independent public-records site for Bay County, next to the official source. If fulfilling it will cost more than $25, please send an estimate before starting.

Thank you,
${SIGNATURE}`;

const usd = n => '$' + Math.round(n).toLocaleString('en-US');

const LETTERS = {
  // contract awards in the minutes with nothing on record after them (site/award_followup.py, gaps from stale_requests.py)
  'award-follow-up': gaps => {
    const many = gaps.length > 1;
    const lines = gaps.map((g, i) => `${i + 1}. ${g.company}, approved by the ${g.board || 'board'} on ${longDate(g.award_date)}${g.amount ? ` (${usd(g.amount)} in the minutes)` : ''}`
      + `${g.bid_numbers ? `, ${g.bid_numbers.split('; ').length > 1 ? 'numbers' : 'number'} ${g.bid_numbers}` : ''}.\n   The minutes say: ${g.headline}\n   Minutes: ${g.source_url}`).join('\n');
    return {
      subject: `Public records request: contract${many ? 's' : ''} and payments for ${many ? `${gaps.length} awards` : `the ${longDate(gaps[0].award_date)} award to ${gaps[0].company}`}`,
      body: `Under Chapter 119, Florida Statutes, I’m requesting records for the contract award${many ? 's' : ''} below.

The meeting minutes record ${many ? 'each award' : 'the award'}, but we were unable to locate any later public record of the work: no signed contract, change order, later agenda item or payment that names the company. It may well be on file; this request is to fill in the public record.

${lines}

For ${many ? 'each award' : 'the award'}, please send:

1. The signed contract, agreement or purchase order, with any amendments, change orders or task orders.
2. A list of payments made to the company under it (date, check or payment number, amount), for example from the check register or vendor history report.
3. If the award was not carried out (cancelled, rebid, or the company declined), the record showing that and the date.

An export or spreadsheet is ideal, and if any of this is posted online, a link is all I need. If any part can’t be found, please send what exists rather than holding the rest.

${CLOSING}`,
    };
  },
  'beach-water': gaps => {
    const many = gaps.length > 1;
    const lines = gaps.map(g => `- ${g.location}${g.listed_as ? `, listed by the state as ${g.listed_as}` : ''}${g.epa_beach_id ? ` (EPA beach ID ${g.epa_beach_id})` : ''}: `
      + `the newest sample shown is from ${longDate(g.last_record)}, ${g.last_result}.\n  Where we looked: ${g.source_url}`).join('\n');
    return {
      subject: `Public records request: Healthy Beaches water samples for ${andList(gaps.map(g => g.location))}`,
      body: `Under Chapter 119, Florida Statutes, I’m requesting records of the Florida Healthy Beaches Program water sampling in Bay County.

The program’s Beach Water Quality page usually shows a new sample at each Bay County site every week or two. We were unable to locate any newer results for ${many ? 'these sites' : 'this site'} on that official source:

${lines}

For ${many ? 'each site' : 'this site'}, please send:

1. Every enterococcus sample result taken since the date above (sample date, result per 100 mL and rating).
2. Any health advisories or warnings issued or lifted for the site in that time, with their dates.
3. If sampling stopped or moved, the record showing when and why (for example a memo, email or program notice), and the site that replaced it, if any.

An export or spreadsheet is ideal, and if the results are posted somewhere else online, a link is all I need. If any part can’t be found, please send what exists rather than holding the rest.

${CLOSING}`,
    };
  },
};

// A plain letter for a check without its own: names each place, its newest record and where we looked.
function generic(title, gaps) {
  const lines = gaps.map(g => `- ${g.location}: the newest record published is from ${longDate(g.last_record)}.\n  Where we looked: ${g.source_url}`).join('\n');
  return {
    subject: `Public records request: ${title}`,
    body: `Under Chapter 119, Florida Statutes, I’m requesting the records described below.

We were unable to locate updated information at the official source, which usually publishes more often than this:

${lines}

Please send the records created since each date above, or tell me where they are posted. If any part can’t be found, please send what exists rather than holding the rest.

${CLOSING}`,
  };
}

function compose(check, title, gaps) {
  return (LETTERS[check] ? LETTERS[check](gaps) : generic(title || 'records not yet published', gaps));
}

module.exports = {compose, longDate, LETTERS};
