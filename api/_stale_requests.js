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

const LETTERS = {
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
