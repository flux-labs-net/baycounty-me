// Tests for v1.js conditional responses (ETag / Last-Modified / 304). Run: npm test
const test = require('node:test');
const assert = require('node:assert/strict');
const {conditional} = require('../v1');

const mk = (headers = {}) => {
  const res = {statusCode: 200, headers: {}, body: undefined, setHeader(k, v) { this.headers[k.toLowerCase()] = v; }, removeHeader(k) { delete this.headers[k.toLowerCase()]; },
    status(c) { this.statusCode = c; return this; }, json(b) { this.body = JSON.stringify(b); return this; }, send(b) { this.body = b; return this; }};
  conditional({headers}, res);
  return res;
};

test('ETag on 200, 304 on a matching If-None-Match or If-Modified-Since', () => {
  const a = mk(); a.status(200).json({x: 1});
  const tag = a.headers.etag;
  assert.ok(tag && a.statusCode === 200 && a.body === '{"x":1}');
  const b = mk({'if-none-match': tag}); b.status(200).json({x: 1});
  assert.equal(b.statusCode, 304); assert.equal(b.body, '');
  const c = mk({'if-none-match': tag}); c.status(200).json({x: 2});
  assert.equal(c.statusCode, 200, 'changed body gets a new ETag');
  const d = mk({'if-modified-since': 'Wed, 21 Oct 2026 00:00:00 GMT'}); d.locals.lastModified = new Date('2026-10-21T00:00:00Z'); d.status(200).json({x: 1});
  assert.equal(d.statusCode, 304);
  assert.equal(d.headers['last-modified'], 'Wed, 21 Oct 2026 00:00:00 GMT');
  const e = mk({'if-none-match': tag}); e.status(404).json({x: 1});
  assert.equal(e.statusCode, 404, 'errors are never 304');
  const f = mk({'if-none-match': tag}); f.status(200).send('{"x":1}');
  assert.equal(f.statusCode, 304, 'send() with the same text matches too');
});
