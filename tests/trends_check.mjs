// Compares the browser calculations (assets/*.js) with the Python reference numbers on a fixture history.
//   node tests/trends_check.mjs        (exit code 1 on any difference)
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const here = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
require(path.join(here, '../assets/common.js'));
require(path.join(here, '../assets/trends-calc.js'));
const DT = globalThis.DT;

const rows = DT.parseCSV(readFileSync(path.join(here, 'fixtures/trends_history.csv'), 'utf8')).map(DT.typed);
const exp = JSON.parse(readFileSync(path.join(here, 'fixtures/trends_expected.json'), 'utf8'));
let bad = 0, checked = 0;
function same(label, a, b) {
  checked++;
  const ok = (typeof a === 'number' && typeof b === 'number') ? Math.abs(a - b) <= 1e-9 * Math.max(1, Math.abs(b)) : a === b;
  if (!ok) { bad++; console.log('DIFF', label, 'browser:', a, 'python:', b); }
}
function list(label, a, b, keys) {
  same(label + ' length', a.length, b.length);
  b.forEach((x, i) => keys.forEach(k => same(`${label}[${i}].${k}`, a[i] && a[i][k], x[k])));
}

const T = DT.trends(rows), E = exp.trends;
same('items', T.items, E.items);
same('days', T.days.join(), E.days.join());
list('sinceFirst', T.sinceFirst, E.sinceFirst, ['item_id', 'first', 'last', 'pct']);
same('riser', T.riser.item_id, E.riser.item_id); same('faller', T.faller.item_id, E.faller.item_id);
list('daily', T.daily, E.daily, ['date', 'n', 'maxItemId', 'maxPct', 'maxAbs', 'meanAbs']);
for (const k of ['date', 'item_id', 'pct']) same('biggest.' + k, T.biggest[k], E.biggest[k]);
for (const k of ['date', 'n', 'gap']) same('spread.' + k, T.spread[k], E.spread[k]);
same('spread.hottest', T.spread.hottest.item, E.spread.hottest.item); same('spread.coldest', T.spread.coldest.item, E.spread.coldest.item);
list('spread.cities', T.spread.cities, E.spread.cities, ['item', 'temp']);
list('dailyGap', T.dailyGap, E.dailyGap, ['date', 'gap', 'n']);
list('bySource', T.bySource, E.bySource, ['source', 'mean', 'n']);
list('volatility', T.volatility, E.volatility, ['item_id', 'sd', 'n']);

// Today page: biggest moves and what appeared or disappeared
const diff = DT.compare(rows), moves = DT.biggestMoves(diff.changes, 10);
same('latestDate', diff.latestDate, exp.today.latestDate);
list('moves', moves, exp.today.moves, ['item_id', 'pct', 'old', 'new']);
same('new', diff.isNew.map(r => r.item_id).join(), exp.today.new.join());
same('gone', diff.gone.map(r => r.item_id).join(), exp.today.gone.join());

// Browse: filter, search and sort
const latest = DT.latestRows(rows);
same('latestRows count', latest.length, 39);
const crypto = DT.browseRows(latest, { source: 'crypto', sort: 'price', dir: 'desc' });
same('browse source filter', crypto.length, 12);
same('browse sort desc', crypto.every((r, i) => !i || crypto[i - 1].price >= r.price), true);
same('browse search', DT.browseRows(latest, { q: 'dal' }).map(r => r.item_id).join(), 'dallas');
same('browse starred', DT.browseRows(latest, { starred: ['WMT', 'bitcoin'] }).length, 2);
const withGaps = DT.browseRows(latest, { sort: 'market_cap', dir: 'asc' });
same('browse empties last (asc)', withGaps.slice(-27).every(r => r.market_cap == null), true);
const desc = DT.browseRows(latest, { sort: 'market_cap', dir: 'desc' });
same('browse empties last (desc)', desc.slice(-27).every(r => r.market_cap == null), true);

console.log(bad ? `${bad} of ${checked} checks differ` : `all ${checked} checks match the Python reference`);
process.exit(bad ? 1 : 0);
