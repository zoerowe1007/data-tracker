/* Small dependency-free SVG charts (they work offline). Each function returns an SVG string. */
(function (root) {
  'use strict';
  var DT = root.DT, W = 720;
  var PALETTE = ['#d63384', '#e8742a', '#2f8f83', '#5b6bd6', '#b07d00', '#b03a2e', '#2a7ab0', '#7d3c98', '#4d8f2f', '#8a2459'];

  // A readable scale: steps of 1, 2 or 5 times a power of ten, at most about six ticks.
  function scale(min, max) {
    if (min === max) { min -= 1; max += 1; }
    var raw = (max - min) / 5, mag = Math.pow(10, Math.floor(Math.log10(raw))), step = mag;
    [1, 2, 5, 10].some(function (m) { step = m * mag; return raw <= step; });
    var lo = Math.floor(min / step) * step, hi = Math.ceil(max / step) * step, ticks = [];
    for (var v = lo; v <= hi + step / 2; v += step) ticks.push(Math.round(v / step) * step);
    return { min: lo, max: hi, ticks: ticks };
  }
  function tick(v) {
    var a = Math.abs(v);
    if (a >= 1e9) return (v / 1e9).toFixed(1).replace(/\.0$/, '') + 'B';
    if (a >= 1e6) return (v / 1e6).toFixed(1).replace(/\.0$/, '') + 'M';
    if (a >= 1e4) return (v / 1e3).toFixed(0) + 'k';
    return Number(v.toPrecision(6)).toLocaleString('en-US');
  }
  function svg(h, label, body) {
    return '<svg class="chart" viewBox="0 0 ' + W + ' ' + h + '" role="img" aria-label="' + DT.esc(label) + '">' + body + '</svg>';
  }
  function trim(s, n) { return s.length > n ? s.slice(0, n - 1) + '…' : s; }

  // Lines over the days. o: {label, dates:[...], series:[{name, points:[{date,value}]}], decimals}
  function line(o) {
    var H = 300, L = 62, R = 14, T = 14, B = 34, n = o.dates.length;
    var vals = [];
    o.series.forEach(function (s) { s.points.forEach(function (p) { if (p.value != null) vals.push(p.value); }); });
    if (!n || !vals.length) return '';
    var sc = scale(Math.min.apply(null, vals), Math.max.apply(null, vals)), pw = W - L - R, ph = H - T - B;
    function X(i) { return n === 1 ? L + pw / 2 : L + pw * i / (n - 1); }
    function Y(v) { return T + ph - ph * (v - sc.min) / (sc.max - sc.min); }
    var g = '';
    sc.ticks.forEach(function (t) {
      g += '<line class="grid" x1="' + L + '" x2="' + (W - R) + '" y1="' + Y(t).toFixed(1) + '" y2="' + Y(t).toFixed(1) + '"/>' +
        '<text x="' + (L - 6) + '" y="' + (Y(t) + 4).toFixed(1) + '" text-anchor="end">' + tick(t) + '</text>';
    });
    var step = Math.ceil(n / 8);
    o.dates.forEach(function (d, i) {
      if (i % step === 0 || i === n - 1) g += '<text x="' + X(i).toFixed(1) + '" y="' + (H - 12) + '" text-anchor="middle">' + d.slice(5) + '</text>';
    });
    g += '<line class="axis" x1="' + L + '" x2="' + (W - R) + '" y1="' + (T + ph) + '" y2="' + (T + ph) + '"/>';
    o.series.forEach(function (s, k) {
      var color = PALETTE[k % PALETTE.length], pts = [], path = '', dots = '';
      s.points.forEach(function (p) {
        if (p.value == null) return;
        var x = X(o.dates.indexOf(p.date)), y = Y(p.value);
        pts.push(x.toFixed(1) + ',' + y.toFixed(1));
        dots += '<circle cx="' + x.toFixed(1) + '" cy="' + y.toFixed(1) + '" r="3.2" fill="' + color + '"><title>' +
          DT.esc(s.name + ' · ' + p.date + ' · ' + Number(p.value.toPrecision(7)).toLocaleString('en-US')) + '</title></circle>';
      });
      if (pts.length > 1) path = '<polyline fill="none" stroke="' + color + '" stroke-width="2.2" stroke-linejoin="round" points="' + pts.join(' ') + '"/>';
      g += path + dots;
    });
    return svg(H, o.label, g);
  }
  function legend(series) {
    return '<div class="legend">' + series.map(function (s, k) {
      return '<span><i style="background:' + PALETTE[k % PALETTE.length] + '"></i>' + DT.esc(s.name) + '</span>';
    }).join('') + '</div>';
  }

  // Horizontal bars, positive or negative: rows [[label, value]]; format(v) makes the value label.
  function bars(o) {
    var rows = o.rows, rowH = 26, T = 6, L = 150, R = 74, H = T * 2 + rowH * rows.length;
    if (!rows.length) return '';
    var lo = Math.min.apply(null, rows.map(function (r) { return r[1]; }).concat([0]));
    var hi = Math.max.apply(null, rows.map(function (r) { return r[1]; }).concat([0]));
    var span = (hi - lo) || 1, pw = W - L - R, zero = L + pw * (0 - lo) / span, g = '';
    rows.forEach(function (r, i) {
      var y = T + i * rowH, w = Math.abs(r[1]) / span * pw, x = r[1] >= 0 ? zero : zero - w;
      var lab = o.format ? o.format(r[1]) : Number(r[1].toFixed(2)).toLocaleString('en-US');
      g += '<text x="' + (L - 8) + '" y="' + (y + 17) + '" text-anchor="end">' + DT.esc(trim(r[0], 24)) + '</text>' +
        '<rect class="' + (r[1] >= 0 ? (o.cls || 'bar-role') : 'bar-warn') + '" x="' + x.toFixed(2) + '" y="' + (y + 3) + '" width="' +
        Math.max(w, 1).toFixed(2) + '" height="' + (rowH - 8) + '" rx="2"><title>' + DT.esc(r[0] + ': ' + lab) + '</title></rect>' +
        '<text class="vlabel" x="' + (r[1] >= 0 ? x + w + 6 : x - 6) + '" y="' + (y + 17) + '" text-anchor="' + (r[1] >= 0 ? 'start' : 'end') + '">' + DT.esc(lab) + '</text>';
    });
    g += '<line class="axis" x1="' + zero.toFixed(2) + '" x2="' + zero.toFixed(2) + '" y1="' + T + '" y2="' + (H - T) + '"/>';
    return svg(H, o.label, g);
  }

  // Vertical bars over the days: labels, values.
  function columns(o) {
    var H = 260, L = 56, R = 10, T = 14, B = 34, n = o.labels.length;
    if (!n) return '';
    var sc = scale(Math.min.apply(null, o.values.concat([0])), Math.max.apply(null, o.values.concat([0]))), pw = W - L - R, ph = H - T - B;
    var slot = pw / n, bw = Math.max(3, Math.min(48, slot * 0.7)), g = '';
    function Y(v) { return T + ph - ph * (v - sc.min) / (sc.max - sc.min); }
    sc.ticks.forEach(function (t) {
      g += '<line class="grid" x1="' + L + '" x2="' + (W - R) + '" y1="' + Y(t).toFixed(1) + '" y2="' + Y(t).toFixed(1) + '"/>' +
        '<text x="' + (L - 6) + '" y="' + (Y(t) + 4).toFixed(1) + '" text-anchor="end">' + tick(t) + (o.unit || '') + '</text>';
    });
    o.values.forEach(function (v, j) {
      var y0 = Y(0), y1 = Y(v), x = L + slot * j + (slot - bw) / 2;
      g += '<rect class="' + (v >= 0 ? 'bar-role' : 'bar-warn') + '" x="' + x.toFixed(2) + '" y="' + Math.min(y0, y1).toFixed(2) + '" width="' + bw.toFixed(2) +
        '" height="' + Math.max(Math.abs(y0 - y1), 1).toFixed(2) + '"><title>' + DT.esc(o.labels[j] + ': ' + Number(v.toFixed(3)) + (o.unit || '')) + '</title></rect>';
    });
    var step = Math.ceil(n / 10);
    o.labels.forEach(function (lab, j) {
      if (j % step === 0 || j === n - 1) g += '<text x="' + (L + slot * j + slot / 2).toFixed(1) + '" y="' + (H - 12) + '" text-anchor="middle">' + DT.esc(lab.slice(5)) + '</text>';
    });
    g += '<line class="axis" x1="' + L + '" x2="' + (W - R) + '" y1="' + Y(0).toFixed(1) + '" y2="' + Y(0).toFixed(1) + '"/>';
    return svg(H, o.label, g);
  }

  // A table with the numbers behind a chart (accessible, and lets anyone check the chart).
  function dataTable(head, rows) {
    return '<details class="data"><summary>Show the numbers</summary><table><thead><tr>' +
      head.map(function (h, i) { return '<th' + (i ? ' class="num"' : '') + '>' + DT.esc(h) + '</th>'; }).join('') +
      '</tr></thead><tbody>' + rows.map(function (r) {
        return '<tr>' + r.map(function (c, i) { return '<td' + (i ? ' class="num"' : '') + '>' + DT.esc(c) + '</td>'; }).join('') + '</tr>';
      }).join('') + '</tbody></table></details>';
  }

  root.DTCharts = { line: line, legend: legend, bars: bars, columns: columns, dataTable: dataTable, scale: scale, PALETTE: PALETTE };
})(window);
