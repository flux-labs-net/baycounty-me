// Server-side Postgres connection (Supabase) for API keys, throttles, logs and the admin section.
// Uses DATABASE_URL from Vercel. Supabase's direct address is IPv6-only, which serverless functions can't
// reach, so it is rewritten to the IPv4 transaction pooler (port 6543), the mode meant for serverless.
let pool = null;

function connectionString() {
  const raw = process.env.DATABASE_URL || process.env.POSTGRES_URL;
  if (!raw) return null;
  const u = new URL(raw);
  const m = u.hostname.match(/^db\.([a-z0-9]+)\.supabase\.co$/);
  if (m) {
    u.hostname = process.env.SUPABASE_POOLER_HOST || 'aws-0-us-east-2.pooler.supabase.com';
    u.port = '6543';
    u.username = encodeURIComponent((decodeURIComponent(u.username) || 'postgres') + '.' + m[1]);
  }
  u.searchParams.delete('sslmode'); // TLS is set below
  return u.toString();
}

// TLS settings. Supabase's certificate is signed by Supabase's own CA, which Node doesn't ship with.
// * SUPABASE_CA_CERT set (the PEM text from Supabase > Database settings > SSL configuration > Download certificate,
//   pasted as-is, or with literal \n for line breaks): the connection is encrypted AND the server is verified.
// * Not set: FALLBACK. Still encrypted, but the certificate isn't checked, so a network attacker who could
//   intercept the connection could impersonate the database. Set SUPABASE_CA_CERT to close that gap.
function tlsOptions(cs) {
  if (/@(localhost|127\.0\.0\.1)[:/]/.test(cs)) return false;
  const ca = String(process.env.SUPABASE_CA_CERT || '').replace(/\\n/g, '\n').trim();
  if (ca) return {ca, rejectUnauthorized: true};
  return {rejectUnauthorized: false};
}

function getPool() {
  if (pool) return pool;
  const cs = connectionString();
  if (!cs) return null;
  const {Pool} = require('pg'); // loaded on first use, so modules that never touch the database don't need it
  pool = new Pool({connectionString: cs, max: 3, idleTimeoutMillis: 10000, connectionTimeoutMillis: 4000, ssl: tlsOptions(cs)});
  pool.on('error', e => console.error('pg pool', e.message));
  return pool;
}

async function q(text, params = []) {
  const p = getPool();
  if (!p) throw new Error('DATABASE_URL is not set');
  return (await p.query(text, params)).rows;
}

module.exports = {q, hasDb: () => !!(process.env.DATABASE_URL || process.env.POSTGRES_URL)};
