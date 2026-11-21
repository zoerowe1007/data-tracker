/* Plain-language labels, explanations and small page pieces shared by the three pages.
   (Browser only: the numbers themselves are computed in common.js and trends-calc.js.) */
(function (root) {
  'use strict';
  var DT = root.DT, esc = DT.esc;

  /* What each source is, in plain words. Keys match the source names in sources.json. */
  DT.SOURCES = {
    crypto: {
      title: 'Coins', provider: 'CoinGecko',
      what: 'Price and trading figures for 12 well-known cryptocurrencies, in US dollars.',
      measured: 'The price in US dollars. A coin that is up 3% is worth 3% more than at the previous run.',
      cron: 'Prices change all day, so each value is the price at the moment the tracker ran.'
    },
    weather: {
      title: 'Weather', provider: 'Open-Meteo',
      what: 'Current temperature, humidity, wind and air pressure in 12 cities around Dallas–Fort Worth, Northwest Arkansas and nearby.',
      measured: 'The air temperature in °F. A change from 60°F to 66°F is shown as +10%.',
      cron: 'Each value is the current reading at the time of the run (the exact hour is in the as_of column of the history).'
    },
    air: {
      title: 'Air quality', provider: 'Open-Meteo air quality',
      what: 'How clean the air is in 12 cities in Texas and neighboring states: the US air quality index and the particle and ozone readings behind it.',
      measured: 'The US air quality index (0 is clean; higher is worse). 50 or less is "Good".',
      cron: 'Each value is the current modelled reading for the city.'
    }
  };
  DT.sourceInfo = function (name) {
    return DT.SOURCES[name] || { title: name, provider: '', what: '', measured: '', cron: '' };
  };
  // "Price (USD)", "Temperature (°F)", "Air quality index": what a source's headline column is.
  DT.measureLabel = function (source) {
    var c = DT.COLS[DT.headline(source)];
    return c.label + (c.unit === '$' ? ' (USD)' : c.unit ? ' (' + c.unit + ')' : '');
  };
  DT.colLabel = function (col) {
    var c = DT.COLS[col];
    return c.label + (c.unit === '$' ? ' (USD)' : c.unit ? ' (' + c.unit + ')' : '');
  };

  /* What every column of the history means (same wording as the README). */
  DT.HELP = {
    price: ['Current price of the coin', 'crypto'],
    high: ['Highest price in the last 24 hours', 'crypto'],
    low: ['Lowest price in the last 24 hours', 'crypto'],
    volume: ['US dollars of this coin traded in the last 24 hours', 'crypto'],
    change_pct: ['How much the price moved over the last 24 hours, as reported by CoinGecko', 'crypto'],
    market_cap: ['Price times the number of coins in circulation: the coin\'s total value', 'crypto'],
    temp_f: ['Air temperature, 2 m above the ground', 'weather'],
    humidity_pct: ['Relative humidity: how much of the water vapor the air could hold it is holding', 'weather'],
    wind_mph: ['Wind speed, 10 m above the ground', 'weather'],
    pressure_hpa: ['Air pressure at the surface. Lower pressure often means unsettled weather', 'weather'],
    us_aqi: ['US air quality index: 0–50 Good, 51–100 Moderate, 101–150 unhealthy for sensitive groups, above 150 unhealthy', 'air'],
    pm2_5: ['Particles smaller than 2.5 micrometres (smoke, haze). These reach deep into the lungs', 'air'],
    pm10: ['Particles smaller than 10 micrometres (dust, pollen)', 'air'],
    ozone: ['Ozone near the ground (smog)', 'air']
  };
  DT.aqiBand = function (v) {
    if (v == null) return '';
    return v <= 50 ? 'Good' : v <= 100 ? 'Moderate' : v <= 150 ? 'Unhealthy for sensitive groups' : v <= 200 ? 'Unhealthy' : v <= 300 ? 'Very unhealthy' : 'Hazardous';
  };

  /* Words used on the pages. */
  DT.TERMS = [
    ['Item', 'One thing we track: a coin, a weather city or an air-quality city. It has a stable key (item_id), so the same item lines up from day to day.'],
    ['Source', 'Where the numbers come from. Each source is a public website that GitHub downloads from every day.'],
    ['Run', 'One check of all the sources. The tracker runs twice a day; a second run on the same day replaces the first, so each date counts once.'],
    ['History', 'The file data/history.csv: one row per item per day. Every page below is calculated from it.'],
    ['Headline value', 'The one number per source that "moves" are measured on: price for coins, temperature for weather, air quality index for air.'],
    ['Move', 'The percent change of an item\'s headline value since the previous run: (latest − previous) ÷ previous × 100. For temperatures the divisor is never below 20, so 2°F to 4°F is +10%, not +100%.'],
    ['Appeared / disappeared', 'An item that has a value in the latest run but not the one before (appeared), or the other way round (disappeared).'],
    ['Index (first day = 100)', 'A way to chart items of very different size together: each item\'s first day is set to 100, so 110 means +10% since then.'],
    ['UTC', 'The time zone every date uses. A UTC day can start late in the evening in the United States.']
  ];
  DT.guide = {};
  DT.guide.glossary = function () {
    return '<details class="card glossary"><summary>Glossary: what the words on these pages mean</summary><dl>' +
      DT.TERMS.map(function (t) { return '<dt>' + esc(t[0]) + '</dt><dd>' + esc(t[1]) + '</dd>'; }).join('') + '</dl></details>';
  };
  // The path of the data, with live numbers. `here` is the step this page belongs to (1 to 4).
  DT.guide.flow = function (c) {
    function step(n, title, text) {
      return '<li class="step' + (n === 4 ? ' here' : '') + '"><span class="n">' + n + '</span><strong>' + title + '</strong><span>' + text + '</span></li>';
    }
    return '<ol class="flow" aria-label="How the data gets to this page">' +
      step(1, 'Public sources', esc(c.sourceNames) + '. No login needed.') +
      step(2, 'Daily download', 'GitHub saves each answer untouched in <code>data/raw/</code> twice a day. ' + DT.plural(c.days, 'day') + ' saved so far.') +
      step(3, 'History table', 'Every run adds one row per item per day to <code>data/history.csv</code>: ' + DT.fmt(c.rows) + ' rows so far.') +
      step(4, 'These pages', 'Your browser reads that one file and does all the sums: <a href="index.html">Today</a> (what changed), <a href="browse.html">Browse</a> (look up items), <a href="trends.html">Trends</a> (how values moved).') +
      '</ol>';
  };
  DT.guide.next = function (links) {
    return '<nav class="next" aria-label="Where to next"><strong>Where to next</strong>' +
      links.map(function (l) { return '<a class="btn ghost" href="' + l[0] + '">' + esc(l[1]) + '</a>'; }).join('') + '</nav>';
  };
  DT.trendHref = function (id) { return 'trends.html#item=' + encodeURIComponent(id); };
  DT.hash = function () {
    var out = {};
    location.hash.replace(/^#/, '').split('&').forEach(function (p) {
      var kv = p.split('='); if (kv[0]) out[kv[0]] = decodeURIComponent(kv[1] || '');
    });
    return out;
  };
})(window);
