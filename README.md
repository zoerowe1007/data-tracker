# Data Tracker

![tests](https://github.com/zoerowe1007/data-tracker/actions/workflows/tests.yml/badge.svg)
![daily run](https://github.com/zoerowe1007/data-tracker/actions/workflows/daily.yml/badge.svg)

A tool that downloads fresh values every day for **36 items** (12 coins, 12 cities with weather and 12
cities with air quality), adds them to a history with **one row per item per day**, reports what moved, and publishes the result
as an installable website.

* **Live site:** https://zoerowe1007.github.io/data-tracker/
* **Daily report:** the repository's *Issues* tab (one Issue per day, titled with the date)

## How it works

GitHub Actions runs `python -m tracker.run` on a schedule. Each run:

1. calls every source and saves exactly what it returned, compressed, to `data/raw/<UTC date>/<source>.<format>.gz`.
   One source failing does not stop the run; a failed source writes no raw file that day, and the result of every
   source (ok or failed, with the reason) is recorded in `data/run_log.json`;
2. builds `data/history.csv` **from the raw files alone** (so running the build again gives the same file, and a
   change to a rule applies to every day);
3. writes `data/status.json`;
4. opens the day's GitHub Issue and closes the previous day's;
5. the workflow commits the raw files, the history file, the status file and the run log.

A successful run is one that finishes and commits, even when some sources failed. A second run on the same UTC day
deletes that day's raw files first, fetches again, rebuilds the history and updates that day's Issue, so every day
counts once. The workflow runs twice a day for that reason: if GitHub skips or delays one run, the next one makes
the day up, and the later run simply replaces the earlier one.

## Sources

Every source is public and needs **no login and no API key** (nothing secret is stored in this repository).

| Source | Format | What it returns | What is kept |
|---|---|---|---|
| `crypto`: [CoinGecko](https://www.coingecko.com/en/api) `/api/v3/coins/markets?vs_currency=usd&ids=<ids>` | JSON (`crypto.json.gz`) | One object per coin with price, market cap, 24-hour volume, high, low and 24-hour change | The request names only the 12 tracked coin ids. Of each object the price, high, low, volume, change, market cap and update time are kept. |
| `weather`: [Open-Meteo](https://open-meteo.com) `/v1/forecast?latitude=<lats>&longitude=<lons>&current=...` | JSON (`weather.json.gz`) | The current conditions for every city in one answer | One call for the 12 tracked cities. Of the `current` block the temperature (°F), humidity, wind speed (mph) and surface pressure are kept. Open-Meteo snaps to its own grid, so each answer is matched to the nearest tracked city. |
| `air`: [Open-Meteo air quality](https://open-meteo.com/en/docs/air-quality-api) `/v1/air-quality?latitude=<lats>&longitude=<lons>&current=us_aqi,pm2_5,pm10,ozone` | JSON (`air.json.gz`) | The current air quality for every place in one answer | One call for the 12 tracked places (Texas and neighbouring states). Of the `current` block the US air quality index, PM2.5, PM10 and ozone are kept. As for weather, each answer is matched to the nearest tracked place. |

The tracked items, their names, categories and the headline value of each source are in `sources.json`. If a source
stops working, replace its entry (or add another source kind in `tracker/convert.py`); nothing else changes.

The raw file is the bytes the source sent, compressed (`gzip`, with a fixed timestamp so equal data gives equal
files). Before a raw file is saved the response is converted once to make sure it holds tracked items; a response
that cannot be read (an error page, a rate-limit message) counts as a failed source and writes no file.

## The history file: `data/history.csv`

One row per item per day, sorted by `date`, then `item_id`. A value a source does not report for an item is left
empty. Dates are UTC dates written `YYYY-MM-DD`; every run uses the UTC date of the moment it runs.

| Column | Meaning | Unit | Sources |
|---|---|---|---|
| `date` | UTC date of the run | `YYYY-MM-DD` | all |
| `item_id` | Key that identifies the item from one day to the next (CoinGecko id, or city slug; air-quality ids start with `air_`) | text | all |
| `item` | The item's name | text | all |
| `source` | Which source the row came from (`crypto`, `weather`, `air`) | text | all |
| `category` | Group the item belongs to (`Crypto`; `DFW` / `NWA` / `Other` for weather; `Texas` / `Neighbor states` for air) | text | all |
| `price` | Current price of the coin | US dollars | crypto |
| `high` | Highest price of the last 24 hours | US dollars | crypto |
| `low` | Lowest price of the last 24 hours | US dollars | crypto |
| `volume` | Amount traded in the last 24 hours | US dollars | crypto |
| `change_pct` | Price change over the last 24 hours, as reported by CoinGecko | percent | crypto |
| `market_cap` | Market capitalisation | US dollars | crypto |
| `temp_f` | Air temperature at 2 m | degrees Fahrenheit | weather |
| `humidity_pct` | Relative humidity at 2 m | percent | weather |
| `wind_mph` | Wind speed at 10 m | miles per hour | weather |
| `pressure_hpa` | Surface air pressure | hectopascal | weather |
| `us_aqi` | US air quality index (0 is clean, 100 and above is unhealthy for sensitive groups, 500 is the top of the scale) | index points | air |
| `pm2_5` | Particulate matter smaller than 2.5 micrometres, near the ground | micrograms per cubic metre | air |
| `pm10` | Particulate matter smaller than 10 micrometres, near the ground | micrograms per cubic metre | air |
| `ozone` | Ozone near the ground | micrograms per cubic metre | air |
| `as_of` | The time the source says the values are from (kept as the source writes it) | text | all |

Open-Meteo reports modelled values for the current hour at each place, so air-quality and weather values change a
little every run.

**Build the history file from the raw files** (this is the only thing the build reads):

```
python -m tracker.history
```

## The status file: `data/status.json`

`run_time` (UTC), `first_run_date` (date of the earliest raw file), `days_with_success` (number of different dates
with a raw file), `items` (number of items in the latest run), `new_today` (items that appeared), `gone_today`
(items that disappeared) and `sources`, a list with `name`, `ok` and `count` for every source.

*Appeared* and *disappeared* compare each source's latest run with the run before it (the previous date on which
that source has a raw file). A source that failed today is not compared, so its items are neither new nor gone.

## The move rule

A **move** is the percent change of an item's *headline value* since the source's previous run:

```
move % = (new value - old value) / |old value| x 100
```

The headline value is the price for coins (`price`), the temperature for weather cities (`temp_f`) and the US air quality index for air-quality places (`us_aqi`). For
temperatures the denominator is never smaller than 20, so a change from 2 °F to 4 °F is 10 %, not 100 %. An item
with no previous value has no move.

* **Issue:** the daily Issue lists the **10 biggest moves** by absolute percent (item, source, old value, new value,
  percent change), every item that appeared or disappeared, and any source that failed. It is opened every day,
  also on a day with no changes (it then says so), and the previous day's Issue is closed.
* **Today page:** the same ten biggest moves, and the change of every item.
* **Trends page:** day-to-day moves use the same rule between an item's consecutive days.

## The site

Three pages that load `data/history.csv` and `data/status.json` in the browser and do all the calculations there.

* **Today** (`index.html`): time of the last run, status of every source, counts, the latest value of every item
  with its change since the previous run, and the biggest moves.
* **Browse** (`browse.html`): latest values of every item with filters for source and category, a search box for
  item names, a sort by every column (numeric columns up and down) and a star on every item. The shortlist is kept
  in the browser (`localStorage`) and survives a reload.
* **Trends** (`trends.html`): a chart of each numeric value over the days with a picker for which items are shown,
  and five sections that each state a finding, explain it with the numbers and how they are computed, and show a
  chart: best and weakest item since the first run, the biggest one-day move, how far apart the cities are, which
  source moved the most, and which item swings the most. Every number is computed in the browser from the history
  file (`assets/trends-calc.js`); `tests/trends_check.mjs` checks them against the Python reference
  (`tracker/trends.py`).

The site is installable (web app manifest and a service worker). Online, the pages always load the data files from
the network; offline, the service worker answers from its cache and the page says it is showing the last data it
loaded.

## Tests

```
pip install pytest
python -m pytest            # converters, move rule, history logic, runs, repository files
node tests/trends_check.mjs # the browser calculations against the Python reference
```

GitHub Actions runs both on every push (`.github/workflows/tests.yml`).

## Files

| File | What it does |
|---|---|
| `README.md` | This file |
| `sources.json` | The watch list: every source, its items, names, categories and headline value |
| `tracker/__init__.py` | Marks `tracker` as a Python package (empty) |
| `tracker/common.py` | Column definitions and the row builder shared by everything |
| `tracker/http.py` | Downloads a URL with retries and returns the bytes as received |
| `tracker/rawstore.py` | Writes, reads, lists and clears the compressed raw files |
| `tracker/convert.py` | Builds each request and converts one raw file into rows with the common columns |
| `tracker/history.py` | Builds `data/history.csv` from the raw files (`python -m tracker.history`) |
| `tracker/analysis.py` | The move rule and the comparison of each source's latest run with the run before |
| `tracker/status.py` | Writes `data/status.json` and the per-day run log |
| `tracker/issues.py` | Builds and publishes the daily GitHub Issue and closes the previous one |
| `tracker/trends.py` | Python reference for the numbers on the Trends page |
| `tracker/run.py` | The daily pipeline (`python -m tracker.run`) |
| `data/raw/<date>/<source>.<format>.gz` | The raw responses, one file per source per day |
| `data/history.csv` | The history: one row per item per day |
| `data/status.json` | Description of the latest run |
| `data/run_log.json` | Result of every source on every day, with the reason for a failure |
| `index.html`, `browse.html`, `trends.html` | The three pages |
| `assets/style.css` | Fonts and colors shared by the three pages |
| `assets/common.js` | CSV parsing, number formatting, the move rule, run comparison, Browse filtering, shortlist, data loading |
| `assets/guide.js` | Plain-language labels: what each source and column means, the glossary, the data-flow strip and the links between pages |
| `assets/charts.js` | Line, bar and column charts drawn as SVG |
| `assets/trends-calc.js` | Every number on the Trends page |
| `assets/icons/*.png` | App icons |
| `manifest.webmanifest` | Web app manifest (makes the site installable) |
| `sw.js` | Service worker (offline support) |
| `tests/` | The pytest suite, its fixtures and the Node cross-check |
| `.github/workflows/daily.yml` | The daily run: pipeline, commit, Pages rebuild |
| `.github/workflows/tests.yml` | Runs the tests on every push |
| `requirements.txt` | `pytest` (the pipeline itself uses only the Python standard library) |
| `pytest.ini`, `conftest.py` | Test configuration |
