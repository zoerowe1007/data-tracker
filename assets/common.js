/* Shared helpers for all three pages (also loaded by Node for the tests). */
(function (root) {
  'use strict';
  var DT = {};

  /* ---------- columns ---------- */
  DT.NUMERIC = ['price', 'open', 'high', 'low', 'volume', 'change_pct', 'market_cap',
                'temp_f', 'humidity_pct', 'wind_mph', 'pressure_hpa'];
  // label, unit and decimals for display. Volume is shares for stocks and USD traded in 24h for crypto.
  DT.COLS = {
    price:        { label: 'Price',       unit: '$',   dec: 2 },
    open:         { label: 'Open',        unit: '$',   dec: 2 },
    high:         { label: 'High',        unit: '$',   dec: 2 },
    low:          { label: 'Low',         unit: '$',   dec: 2 },
    volume:       { label: 'Volume',      unit: '',    dec: 0, compact: true },
    change_pct:   { label: '24h change',  unit: '%',   dec: 2 },
    market_cap:   { label: 'Market cap',  unit: '$',   dec: 0, compact: true },
    temp_f:       { label: 'Temperature', unit: '°F',  dec: 1 },
    humidity_pct: { label: 'Humidity',    unit: '%',   dec: 0 },
    wind_mph:     { label: 'Wind',        unit: 'mph', dec: 1 },
    pressure_hpa: { label: 'Pressure',    unit: 'hPa', dec: 1 }
  };
  // The headline value of each source: the one a "move" is measured on (must match sources.json).
  DT.HEADLINE = { stocks: 'price', crypto: 'price', weather: 'temp_f' };
  DT.headline = function (source) { return DT.HEADLINE[source] || 'price'; };
  DT.DENOMINATOR_FLOOR = 20;

  /* ---------- CSV ---------- */
  // Parses RFC 4180 CSV (quoted fields, doubled quotes, newlines inside quotes) into objects.
  DT.parseCSV = function (text) {
    var rows = [], row = [], field = '', i = 0, q = false, c;
    if (text.charCodeAt(0) === 0xFEFF) text = text.slice(1);
    while (i < text.length) {
      c = text[i];
      if (q) {
        if (c === '"') { if (text[i + 1] === '"') { field += '"'; i++; } else q = false; }
        else field += c;
      } else if (c === '"') q = true;
      else if (c === ',') { row.push(field); field = ''; }
      else if (c === '\n' || c === '\r') {
        if (c === '\r' && text[i + 1] === '\n') i++;
        row.push(field); field = '';
        if (row.length > 1 || row[0] !== '') rows.push(row);
        row = [];
      } else field += c;
      i++;
    }
    if (field !== '' || row.length) { row.push(field); rows.push(row); }
    if (!rows.length) return [];
    var head = rows.shift();
    return rows.map(function (r) {
      var o = {};
      head.forEach(function (h, k) { o[h] = r[k] === undefined ? '' : r[k]; });
      return o;
    });
  };

  // Numeric cells become numbers; an empty cell becomes null.
  DT.typed = function (r) {
    DT.NUMERIC.forEach(function (c) { r[c] = (r[c] === '' || r[c] == null) ? null : Number(r[c]); });
    return r;
  };

  /* ---------- text and numbers ---------- */
  DT.esc = function (s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  };
  DT.plural = function (n, one, many) { return n + ' ' + (n === 1 ? one : (many || one + 's')); };
  DT.fmt = function (n) { return Number(n).toLocaleString('en-US'); };
  DT.num = function (v, dec) {
    return v == null ? '—' : Number(v).toLocaleString('en-US', { minimumFractionDigits: dec, maximumFractionDigits: dec });
  };
  // A value with its unit, e.g. $102.10, 71.4 °F, 1.2M.
  DT.value = function (col, v) {
    if (v == null) return '—';
    var c = DT.COLS[col] || { unit: '', dec: 2 };
    if (c.compact) {
      var s = new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 2 }).format(v);
      return (c.unit === '$' ? '$' : '') + s;
    }
    if (c.unit === '$') return '$' + DT.num(v, Math.abs(v) < 1 ? 4 : c.dec);
    return DT.num(v, c.dec) + (c.unit ? (c.unit === '%' ? '%' : ' ' + c.unit) : '');
  };
  DT.pct = function (p) { return p == null ? '—' : (p > 0 ? '+' : '') + p.toFixed(2) + '%'; };

  /* ---------- the move rule (the pipeline uses the same one) ---------- */
  // Percent change of the headline value since the previous run: (new - old) / |old| * 100.
  // For temperatures the denominator is never smaller than 20, so 2°F -> 4°F is 10%, not 100%.
  DT.movePct = function (oldV, newV, col) {
    if (oldV == null || newV == null) return null;
    var floor = col === 'temp_f' ? DT.DENOMINATOR_FLOOR : 1e-12;
    return (newV - oldV) / Math.max(Math.abs(oldV), floor) * 100;
  };

  /* ---------- compare each source's latest run with the run before it ---------- */
  // A run is a day on which a source has rows. A source missing from the latest day (it failed) is
  // not compared, so its items are neither new nor gone.
  DT.compare = function (rows) {
    var bySource = {}, latestAll = '';
    rows.forEach(function (r) {
      var s = bySource[r.source] || (bySource[r.source] = {});
      (s[r.date] || (s[r.date] = {}))[r.item_id] = r;
      if (r.date > latestAll) latestAll = r.date;
    });
    var out = { changes: [], isNew: [], gone: [], latest: {}, latestDate: latestAll };
    Object.keys(bySource).sort().forEach(function (name) {
      var days = bySource[name], dates = Object.keys(days).sort(), last = dates[dates.length - 1];
      out.latest[name] = last;
      if (last !== latestAll) return;
      var prev = dates.length > 1 ? days[dates[dates.length - 2]] : null, col = DT.headline(name);
      Object.keys(days[last]).sort().forEach(function (id) {
        var row = days[last][id], old = prev ? prev[id] : null;
        var e = { item_id: id, item: row.item, source: name, column: col, row: row,
                  'new': row[col], old: old ? old[col] : null,
                  pct: old ? DT.movePct(old[col], row[col], col) : null,
                  isNew: !!prev && !old };
        out.changes.push(e);
        if (e.isNew) out.isNew.push(row);
      });
      if (prev) Object.keys(prev).sort().forEach(function (id) { if (!days[last][id]) out.gone.push(prev[id]); });
    });
    return out;
  };

  DT.biggestMoves = function (changes, limit) {
    return changes.filter(function (c) { return c.pct != null; })
      .sort(function (a, b) { return (Math.abs(b.pct) - Math.abs(a.pct)) || (a.item_id < b.item_id ? -1 : 1); })
      .slice(0, limit);
  };

  // Each item's most recent row (items of a source that failed today keep their last known values).
  DT.latestRows = function (rows) {
    var last = {};
    rows.forEach(function (r) { if (!last[r.item_id] || r.date >= last[r.item_id].date) last[r.item_id] = r; });
    return Object.keys(last).sort().map(function (k) { return last[k]; });
  };

  /* ---------- Browse: pure filtering and sorting so it can be tested ---------- */
  // opts: {source, category, q, starred: array of item_ids | null, sort: column, dir: 'asc'|'desc'}
  // Empty values always sort last, whichever direction is chosen.
  DT.browseRows = function (rows, o) {
    var q = (o.q || '').trim().toLowerCase();
    var out = rows.filter(function (r) {
      if (o.source && r.source !== o.source) return false;
      if (o.category && r.category !== o.category) return false;
      if (o.starred && o.starred.indexOf(r.item_id) === -1) return false;
      if (q && r.item.toLowerCase().indexOf(q) === -1 && r.item_id.toLowerCase().indexOf(q) === -1) return false;
      return true;
    });
    var key = o.sort || 'item', dir = o.dir === 'desc' ? -1 : 1;
    out.sort(function (a, b) {
      var x = a[key], y = b[key];
      if (x == null || x === '') { if (y == null || y === '') return a.item_id < b.item_id ? -1 : 1; return 1; }
      if (y == null || y === '') return -1;
      if (x !== y) return (x < y ? -1 : 1) * dir;
      return a.item_id < b.item_id ? -1 : 1;
    });
    return out;
  };

  root.DT = DT;
  if (typeof module !== 'undefined' && module.exports) module.exports = DT;
  if (typeof document === 'undefined') return;

  /* ---------- browser only ---------- */
  var DATA = { history: 'data/history.csv', status: 'data/status.json' };

  // Load both data files. Online they come from the network; offline the service worker answers
  // from its cache and marks the response (x-from-cache) so the page can say so.
  DT.loadData = function () {
    function get(url) {
      return fetch(url, { cache: 'no-cache' }).then(function (res) {
        if (!res.ok) throw new Error(url + ' -> ' + res.status);
        var cached = res.headers.get('x-from-cache') === '1';
        return res.text().then(function (t) { return { text: t, cached: cached }; });
      });
    }
    return Promise.all([get(DATA.status), get(DATA.history)]).then(function (a) {
      var status = JSON.parse(a[0].text);
      var history = DT.parseCSV(a[1].text).map(DT.typed);
      var cached = a[0].cached || a[1].cached;
      if (cached) {
        var b = document.getElementById('banner');
        if (b) {
          b.hidden = false;
          b.textContent = 'You are offline. Showing the data from the last run this device loaded (' +
            DT.runLabel(status.run_time) + ').';
        }
      }
      return { status: status, history: history, cached: cached };
    });
  };

  DT.runLabel = function (iso) { return isNaN(new Date(iso)) ? iso : iso.slice(0, 10) + ' ' + iso.slice(11, 16) + ' UTC'; };

  DT.showError = function (err) {
    var el = document.getElementById('content') || document.querySelector('main');
    el.insertAdjacentHTML('afterbegin',
      '<div class="card" role="alert"><strong>Could not load the data.</strong> ' + DT.esc(err.message) +
      '<br>The pipeline may not have run yet. Open the Actions tab of the repository and run "daily run".</div>');
  };

  /* ---------- shortlist (stars), kept in the browser ---------- */
  var KEY = 'datatracker.shortlist.v1';
  DT.shortlist = {
    all: function () { try { return JSON.parse(localStorage.getItem(KEY) || '[]'); } catch (e) { return []; } },
    has: function (id) { return this.all().indexOf(id) !== -1; },
    toggle: function (id) {
      var list = this.all(), i = list.indexOf(id);
      if (i === -1) list.push(id); else list.splice(i, 1);
      try { localStorage.setItem(KEY, JSON.stringify(list)); } catch (e) { /* storage blocked */ }
      return i === -1;
    }
  };

  /* ---------- service worker ---------- */
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', function () {
      navigator.serviceWorker.register('sw.js').catch(function () { /* not fatal */ });
    });
  }
})(typeof window !== 'undefined' ? window : globalThis);
