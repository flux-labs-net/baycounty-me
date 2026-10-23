// Supabase Storage for original uploads (private bucket "finance-uploads", created by migration 0015).
// Server-side only: uses SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY from Vercel.
const BUCKET = 'finance-uploads';
const base = () => String(process.env.SUPABASE_URL || '').replace(/\/$/, '');
const key = () => process.env.SUPABASE_SERVICE_ROLE_KEY;
const configured = () => !!(base() && key());
const enc = path => path.split('/').map(encodeURIComponent).join('/');
const fail = (msg, status = 502) => Object.assign(new Error(msg), {status});

async function call(method, path, body, headers = {}) {
  if (!configured()) throw fail('File storage isn’t configured (SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY).', 500);
  return fetch(`${base()}/storage/v1${path}`, {method, body, headers: {Authorization: `Bearer ${key()}`, apikey: key(), ...headers}});
}

async function put(path, buffer, contentType = 'application/octet-stream') {
  const r = await call('POST', `/object/${BUCKET}/${enc(path)}`, buffer, {'Content-Type': contentType, 'x-upsert': 'true'});
  if (!r.ok) throw fail(`Storage didn’t accept the file (${r.status}).`);
}

async function get(path) {
  const r = await call('GET', `/object/${BUCKET}/${enc(path)}`);
  if (r.status === 404 || r.status === 400) throw fail('That file isn’t in storage. Upload it again.', 404);
  if (!r.ok) throw fail(`Storage didn’t return the file (${r.status}).`);
  return Buffer.from(await r.arrayBuffer());
}

// A one-time URL the browser or app PUTs the file to directly (no size limit from the function). Valid 2 hours.
async function signedUpload(path) {
  const r = await call('POST', `/object/upload/sign/${BUCKET}/${enc(path)}`, null, {'x-upsert': 'true'});
  const j = await r.json().catch(() => ({}));
  if (!r.ok || !j.url) throw fail('Storage didn’t return an upload link: ' + (j.message || r.status));
  return {url: `${base()}/storage/v1${j.url}`, token: new URL(`${base()}/storage/v1${j.url}`).searchParams.get('token')};
}

async function signedDownload(path, seconds = 300) {
  const r = await call('POST', `/object/sign/${BUCKET}/${enc(path)}`, JSON.stringify({expiresIn: seconds}), {'Content-Type': 'application/json'});
  const j = await r.json().catch(() => ({}));
  if (!r.ok || !(j.signedURL || j.signedUrl)) throw fail('Storage didn’t return a link: ' + (j.message || r.status));
  return `${base()}/storage/v1${j.signedURL || j.signedUrl}`;
}

module.exports = {BUCKET, configured, put, get, signedUpload, signedDownload};
