// Every serverless function and helper must parse. A bad merge once left api/admin.js unparseable,
// which took down /admin sign-in while every other test passed. Run: npm test
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');
const {execFileSync} = require('child_process');

const root = path.join(__dirname, '..');
const files = [];
(function walk(dir) {
  for (const e of fs.readdirSync(dir, {withFileTypes: true})) {
    if (e.name === '__tests__' || e.name === 'node_modules') continue;
    const p = path.join(dir, e.name);
    if (e.isDirectory()) walk(p); else if (e.name.endsWith('.js')) files.push(p);
  }
})(root);

test('finds the api files', () => assert.ok(files.some(f => f.endsWith('admin.js'))));
for (const f of files) {
  test('parses: ' + path.relative(root, f), () => {
    execFileSync(process.execPath, ['--check', f], {stdio: 'pipe'});
  });
}
