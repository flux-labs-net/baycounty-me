// Start a GitHub Actions workflow on main (needs GITHUB_DISPATCH_TOKEN in Vercel: a fine-grained token with
// Actions: write on flux-labs-net/baycounty-me).
const REPO = 'flux-labs-net/baycounty-me';

async function dispatch(workflow, inputs) {
  const tok = process.env.GITHUB_DISPATCH_TOKEN;
  if (!tok) throw Object.assign(new Error('GITHUB_DISPATCH_TOKEN is not set in Vercel'), {status: 409});
  const r = await fetch(`https://api.github.com/repos/${REPO}/actions/workflows/${workflow}/dispatches`, {
    method: 'POST', headers: {Authorization: `Bearer ${tok}`, Accept: 'application/vnd.github+json', 'User-Agent': 'baycounty-me'},
    body: JSON.stringify(inputs ? {ref: 'main', inputs} : {ref: 'main'})});
  if (r.status !== 204) throw Object.assign(new Error(`GitHub said ${r.status}: ${(await r.text()).slice(0, 200)}`), {status: 502});
  return {started: true};
}

module.exports = {REPO, dispatch};
