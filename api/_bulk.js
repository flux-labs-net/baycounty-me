// Shared helper for the admin review queues (Business owners, Gifts over the limit, Nonprofit boards, Business ties).
// A review body names one item (its fields at the top level) or many (`items`, for the bulk buttons on /admin). Each
// item is checked by the caller's `check`, which throws on a bad id. A bare string or number in the list arrives as
// {value}. Files starting with _ are not routes.
const MAX = 500;
const bad = (msg, status = 400) => Object.assign(new Error(msg), {status});

// Pure: body -> checked, de-duplicated list of items. `listKey` lets an older bulk field (careers `pairs`) keep working.
function items(body, check, listKey = 'items') {
  const list = Array.isArray(body[listKey]) ? body[listKey] : Array.isArray(body.items) ? body.items : [body];
  if (!list.length || list.length > MAX) throw bad(`Send 1 to ${MAX} items.`);
  const seen = new Set(), out = [];
  for (const raw of list) {
    const x = check(raw && typeof raw === 'object' ? raw : {value: raw});
    const k = JSON.stringify(x);
    if (!seen.has(k)) { seen.add(k); out.push(x); }
  }
  return out;
}

module.exports = {items, MAX};
