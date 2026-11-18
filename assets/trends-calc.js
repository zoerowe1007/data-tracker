/* Every number on the Trends page is computed here, in the browser, from the rows of history.csv.
   tracker/trends.py computes the same numbers in Python; a test compares the two. */
(function (root) {
  'use strict';
  var DT = root.DT;

  function byAbsThenId(a, b) { return (Math.abs(b.pct) - Math.abs(a.pct)) || (a.item_id < b.item_id ? -1 : a.item_id > b.item_id ? 1 : 0); }
  function mean(xs) { return xs.reduce(function (a, b) { return a + b; }, 0) / xs.length; }
  function sd(xs) {
    var m = mean(xs);
    return Math.sqrt(xs.reduce(function (a, x) { return a + (x - m) * (x - m); }, 0) / (xs.length - 1));
  }

  DT.trends = function (rows) {
    // each item's headline series, by date
    var items = {}, dates = {};
    rows.forEach(function (r) {
      dates[r.date] = true;
      var col = DT.headline(r.source), v = r[col];
      if (v == null) return;
      var it = items[r.item_id] || (items[r.item_id] = { item_id: r.item_id, item: r.item, source: r.source, column: col, points: [] });
      it.points.push({ date: r.date, value: v });
    });
    var ids = Object.keys(items).sort();
    ids.forEach(function (id) { items[id].points.sort(function (a, b) { return a.date < b.date ? -1 : a.date > b.date ? 1 : 0; }); });

    // 1. change since the first run
    var sinceFirst = [];
    ids.forEach(function (id) {
      var it = items[id], p = it.points;
      if (p.length < 2) return;
      sinceFirst.push({ item_id: id, item: it.item, source: it.source, first: p[0].value, last: p[p.length - 1].value,
        firstDate: p[0].date, lastDate: p[p.length - 1].date,
        pct: DT.movePct(p[0].value, p[p.length - 1].value, it.column) });
    });
    sinceFirst.sort(function (a, b) { return (b.pct - a.pct) || (a.item_id < b.item_id ? -1 : 1); });
    var riser = sinceFirst.length ? sinceFirst[0] : null;
    var faller = sinceFirst.length ? sinceFirst.slice().sort(function (a, b) { return (a.pct - b.pct) || (a.item_id < b.item_id ? -1 : 1); })[0] : null;

    // 2. day-to-day moves
    var moves = [], perItem = {};
    ids.forEach(function (id) {
      var it = items[id], p = it.points;
      for (var i = 1; i < p.length; i++) {
        var m = { date: p[i].date, item_id: id, item: it.item, pct: DT.movePct(p[i - 1].value, p[i].value, it.column) };
        moves.push(m);
        (perItem[id] || (perItem[id] = [])).push(m.pct);
      }
    });
    var byDate = {};
    moves.forEach(function (m) { (byDate[m.date] || (byDate[m.date] = [])).push(m); });
    var daily = Object.keys(byDate).sort().map(function (d) {
      var ms = byDate[d].slice().sort(byAbsThenId);
      return { date: d, n: ms.length, maxItem: ms[0].item, maxItemId: ms[0].item_id, maxPct: ms[0].pct,
               maxAbs: Math.abs(ms[0].pct), meanAbs: mean(ms.map(function (x) { return Math.abs(x.pct); })) };
    });
    var biggest = moves.slice().sort(function (a, b) { return byAbsThenId(a, b) || (a.date < b.date ? -1 : 1); })[0] || null;

    // 3. how far apart the cities are (temperature)
    var temps = {};
    rows.forEach(function (r) { if (r.temp_f != null) (temps[r.date] || (temps[r.date] = [])).push(r); });
    var tdates = Object.keys(temps).sort(), spread = null, dailyGap = [];
    tdates.forEach(function (d) {
      var cs = temps[d].slice().sort(function (a, b) { return (b.temp_f - a.temp_f) || (a.item_id < b.item_id ? -1 : 1); });
      if (cs.length >= 2) dailyGap.push({ date: d, gap: cs[0].temp_f - cs[cs.length - 1].temp_f, n: cs.length });
    });
    if (tdates.length) {
      var d = tdates[tdates.length - 1];
      var desc = temps[d].slice().sort(function (a, b) { return (b.temp_f - a.temp_f) || (a.item_id < b.item_id ? -1 : 1); });
      var asc = temps[d].slice().sort(function (a, b) { return (a.temp_f - b.temp_f) || (a.item_id < b.item_id ? -1 : 1); });
      spread = { date: d, n: desc.length, hottest: { item: desc[0].item, temp: desc[0].temp_f },
                 coldest: { item: asc[0].item, temp: asc[0].temp_f }, gap: desc[0].temp_f - asc[0].temp_f,
                 cities: desc.map(function (r) { return { item: r.item, temp: r.temp_f }; }) };
    }

    // 4. average change since the first run, by source
    var groups = {};
    sinceFirst.forEach(function (s) { (groups[s.source] || (groups[s.source] = [])).push(s.pct); });
    var bySource = Object.keys(groups).map(function (k) { return { source: k, mean: mean(groups[k]), n: groups[k].length }; })
      .sort(function (a, b) { return (b.mean - a.mean) || (a.source < b.source ? -1 : 1); });

    // 5. which items swing the most (sample standard deviation of their day-to-day moves)
    var volatility = Object.keys(perItem).filter(function (id) { return perItem[id].length >= 2; }).map(function (id) {
      return { item_id: id, item: items[id].item, source: items[id].source, sd: sd(perItem[id]), n: perItem[id].length };
    }).sort(function (a, b) { return (b.sd - a.sd) || (a.item_id < b.item_id ? -1 : 1); });

    return { days: Object.keys(dates).sort(), items: ids.length, sinceFirst: sinceFirst, riser: riser, faller: faller,
             daily: daily, biggest: biggest, spread: spread, dailyGap: dailyGap, bySource: bySource, volatility: volatility,
             series: items };
  };

  // Data for the line chart of one numeric column. mode 'value' or 'index' (first value = 100).
  DT.lineSeries = function (rows, col, itemIds, mode) {
    var by = {};
    rows.forEach(function (r) {
      if (itemIds.indexOf(r.item_id) === -1 || r[col] == null) return;
      (by[r.item_id] || (by[r.item_id] = { id: r.item_id, name: r.item, points: [] })).points.push({ date: r.date, value: r[col] });
    });
    return Object.keys(by).sort().map(function (id) {
      var s = by[id];
      s.points.sort(function (a, b) { return a.date < b.date ? -1 : 1; });
      if (mode === 'index') {
        var base = s.points[0].value;
        s.points = s.points.map(function (p) { return { date: p.date, value: base ? p.value / base * 100 : null }; });
      }
      return s;
    });
  };
})(typeof window !== 'undefined' ? window : globalThis);
