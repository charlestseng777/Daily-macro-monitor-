# Macro Morning: Global Macro Research Dashboard

> **What happened overnight, why did it happen, and what should I remember?**

A morning dashboard for a London rates / global-markets research analyst. It
is built to be read in under ten minutes and to make the numbers stick: one
headline regime, the moves that mattered, the levels worth knowing cold, the
causal links between assets, and five interview questions and five
flashcards generated from that morning's data.

It does not try to be a terminal. Every section answers a question, detail
sits behind progressive disclosure, and colour is used only for meaning:

| Colour | Meaning |
|---|---|
| Blue / red | Direction of a move. Shown in colour only when the move exceeds 1σ of 20-day vol |
| Amber | Surprise: a 1-year extreme, a broken textbook relationship, a spread wide or tight vs its 3M range |
| Green / red badges | Risk-on / risk-off |

---

## Architecture

```
  FRED · US Treasury · ECB · Bundesbank · BoE (IADB + fitted curves) · MOF Japan
  Yahoo · CNBC · Stooq · EIA · AlphaVantage · Refinitiv (optional) · RSS feeds
                              │  clients/  (retry + backoff, disk cache, stale fallback)
                              ▼
                  SourceRouter: per-instrument ordered source list
                              │
                              ▼
          observations table (PostgreSQL or SQLite): full daily history
                              │
                              ▼
     analytics/  moves · vol · z · percentiles · curves · spreads · forwards
                 policy paths (OIS bootstrap / fed funds futures) · breakeven
                 attribution · movers · heatmap · regime classifier
                              │
                              ▼
     narrative/  deterministic commentary → optional Claude restyle, rejected
                 unless every number appears in the computed facts
                 relationships · interview questions · flashcards (SM-2)
                              │
                              ▼
          snapshots table: one precomputed JSON payload per run
                              │
                              ▼
     api/  FastAPI: /api/dashboard (served from memory, ETag) · /api/series
                              │
                              ▼
     web/  React + Tailwind + lightweight-charts: formats, never calculates
```

| Path | What it is |
|---|---|
| `config/instruments.json` | Every series: kind, region, ordered sources. Fix a source code here, no Python needed |
| `config/central_banks.json` | Meeting calendars, OIS RICs, fallback pricing method per bank |
| `config/feeds.json` | Speech RSS feeds and FRED release ids for the calendar |
| `backend/macrodash/clients/` | One module per provider, plus `demo.py` (synthetic, labelled) |
| `backend/macrodash/db/` | SQLAlchemy Core schema and the repository (all SQL lives here) |
| `backend/macrodash/analytics/` | All calculations |
| `backend/macrodash/narrative/` | Commentary, relationships, interview, flashcards, LLM layer |
| `backend/macrodash/pipeline.py` | fetch → store → compute → narrate → snapshot |
| `backend/macrodash/scheduler.py` | APScheduler, weekdays 05:30 and 06:30 Europe/London |
| `backend/macrodash/api/app.py` | REST API (and serves `web/dist` if built) |
| `backend/tests/` | 47 tests: analytics, parsers, narrative grounding, SRS, end-to-end API |
| `web/src/sections/` | One component per homepage question |
| `web/src/components/` | Reusable pieces: charts, sparkline, percentile bar, tooltip |
| `data/export/` | History CSVs + latest snapshot, committed daily by GitHub Actions |

---

## Quick start

```bash
cd backend
python3.13 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt

# Real data, option A: fetch live (needs open internet)
python -m macrodash run

# Real data, option B: load the history GitHub Actions committed, then compute
python -m macrodash import && python -m macrodash run --skip-ingest

# No network at all: clearly-labelled synthetic data
python -m macrodash run --demo

python -m macrodash serve            # API on http://127.0.0.1:8000
```

```bash
cd web
npm install
npm run dev                          # http://localhost:5173, /api proxied to :8000
npm run build                        # dist/ is served by the API at / if present
```

Other commands:

```bash
python -m macrodash sources [US10Y DE10Y ...]   # probe every source of every instrument
python -m macrodash scheduler [--now]           # daily 05:30 UK refresh loop
python -m macrodash export                      # write data/export (history CSVs + snapshot)
python -m pytest -q                             # from backend/
```

### The website

Each morning (first successful run from 05:33 UK; GitHub often starts scheduled runs late, so there are retry slots up to 09:00) the run also publishes the dashboard to GitHub Pages:
**https://charlestseng777.github.io/Daily-macro-monitor-/**
(`python -m macrodash export-static` writes the snapshot and every chart
series as files; the site is built with `VITE_STATIC=1`). On the hosted page,
flashcards show the day's five cards; spaced-repetition scheduling needs the
backend (`python -m macrodash serve`).

### Daily refresh

Two supported ways:

1. **GitHub Actions** (`.github/workflows/daily-data.yml`). Runs at 05:30 UK on
   weekdays (a gate step keeps it at 05:30 across BST/GMT), and on every push
   that touches the backend. It runs the tests, probes every source, runs the
   live pipeline, and commits `data/export/`. GitHub's runners have open
   internet, so this also gets real data into environments that block market
   data hosts: they just `import`.
   Scheduled runs only fire from the default branch, so merge to `main` to
   enable the 05:30 schedule.
2. **Your own server**: `python -m macrodash scheduler` (or cron
   `30 5 * * 1-5` with `TZ=Europe/London` calling `python -m macrodash run`).
   Point `MACRO_DATABASE_URL` at PostgreSQL in production.

Repository secrets the workflow reads (all optional): `FRED_API_KEY`,
`EIA_API_KEY`, `ALPHAVANTAGE_API_KEY`, `ANTHROPIC_API_KEY`, and the
`REFINITIV_*` set described in `.env.example`.

---

## Data sources and fallbacks

Each instrument lists sources in priority order; the first that returns data
wins and the provider used is recorded per series (`/api/instruments`, and
the footer of the page lists anything unavailable).

| Block | Primary | Fallbacks |
|---|---|---|
| US Treasuries 1Y–30Y, bills | US Treasury par curve (same-day) | FRED `DGS*` |
| Gilts 2/5/10/30Y | BoE fitted nominal zero-coupon curve | BoE IADB par yields, CNBC |
| Bunds 2/5/10/30Y | Bundesbank zero-coupon (BBSIS) | CNBC |
| JGBs 1/2/10/30Y | Japan MOF benchmark yields | CNBC |
| OAT / BTP / Bono / CGB 10Y | CNBC | Stooq |
| US breakevens, TIPS real | FRED `T5YIE`, `T10YIE`, `DFII10` | |
| UK 10Y breakeven | BoE fitted implied-inflation curve (RPI) | Refinitiv |
| DE breakeven, JP inflation swap | Refinitiv only (codes flagged *verify*) | shown as n/a |
| Policy rates, fixings | FRED (Fed), BoE IADB, ECB, FRED (Japan, monthly) | |
| FX, equities, commodities | Yahoo Finance | ECB reference rates, FRED, EIA |
| Credit | ICE BofA OAS via FRED; GBP corporate ETF (SLXX) | Refinitiv iTraxx for JP/Asia |
| Speeches | Fed, BoE, ECB, BoJ RSS | |
| Calendar | Central bank meeting dates (config) | FRED release dates with a key |

Refinitiv sits first in every list when credentials work. The account allows
one session at a time: if Workspace or another job holds it ("Session quota is
reached"), the client waits and retries, and it always signs out at the end of
a run. After a definitive failure it is skipped for the rest of the run.

### Policy expectations: method per bank

| Bank | Without Refinitiv | Quality |
|---|---|---|
| Fed | 30-day fed funds futures, CME FedWatch month-averaging method | high |
| BoE | Bank of England's published SONIA OIS curve | high |
| ECB | Euro-area AAA bill curve proxy anchored on €STR | indicative: a term/credit basis to OIS |
| BoJ | JGB 1Y/2Y proxy anchored on the call rate | indicative |

OIS curves are bootstrapped into a meeting-by-meeting path: spot rates are
interpolated linearly in zero-rate space, converted to discount factors, and
the average forward across each inter-meeting window is the expected
overnight rate after that meeting. Moves are measured from today's fixing and
added to the policy rate, so the overnight-to-policy basis cancels. Next-
meeting probability = implied change ÷ 25bp. Twelve-month pricing is stored
daily, which gives the day-on-day change and the pricing-history chart.

Meeting dates beyond the current year are provisional and flagged in the UI;
update `config/central_banks.json` each year from the linked official calendars.

---

## Calculations

All server-side (`backend/macrodash/analytics`). The frontend never computes.

| Metric | Definition |
|---|---|
| Daily / weekly / monthly / YTD / 1Y change | vs previous print / value on or before T−7d, T−1M, 31 Dec, T−1Y. bp for yields and spreads, % for prices |
| 20-day volatility | stdev of the last 20 daily moves, in move units |
| Move z-score | today's move ÷ the 20-day vol *excluding today* |
| Level z-score | (level − 1Y mean) ÷ 1Y stdev |
| Percentiles | share of the window at or below today (1M, 1Y, full history) |
| Curve slopes | back − front, bp, on a holiday-aligned calendar (≤3-day carry) |
| Steepener / flattener | from the two legs' moves: bear/bull × steepener/flattener, twist, parallel |
| Spreads, relative value | a − b in bp; signal from the z-score vs the 3M mean |
| Forwards | annually-compounded forwards from spot yields: 1y1y, 5y5y, 10y20y, 5y5y inflation |
| Breakeven attribution | Δnominal = Δreal + Δbreakeven; ≥70% share → that driver, else both or offsetting |
| Largest movers | ranked by move z-score across rates, FX, equities, commodities, credit |
| Regime | each regime is a cross-asset signature; score = weighted agreement with today's clipped z's; regimes whose defining factor moved the wrong way are excluded |

## Commentary and the LLM

The deterministic layer writes every paragraph from computed numbers. If
`ANTHROPIC_API_KEY` is set, Claude restyles the regime paragraph and the
five regional summaries, given only the computed facts. The result is
accepted only if every number in it appears in those facts and the 100- and
60-word limits hold; otherwise the deterministic text is kept and the reason is
recorded in `meta.llm`. Requests use server-side refusal fallback
(`fallbacks: "default"`).

## Learning design

- **Chunking**: six questions on the homepage, each a single card or table.
- **Recognition over recall**: sparklines and percentile bars beside every level.
- **Active recall**: interview answers stay hidden until you reveal them.
- **Spaced repetition**: SM-2 scheduling on the server. Concept cards keep
  stable IDs so they recur at growing intervals; market-fact cards are dated.
- **Progressive disclosure**: drill-down panels load their charts only when opened.

## API

| Route | |
|---|---|
| `GET /api/dashboard` | The latest snapshot (ETag, served from memory) |
| `GET /api/series/{id}?range=1W\|1M\|3M\|6M\|YTD\|1Y\|5Y\|MAX` | History + range stats for an instrument, curve (`US_2s10s`), spread (`IT10_DE10`), forward (`US_5y5y`) or pricing series (`PRICING_FED_12M`) |
| `GET /api/series?ids=a,b&range=` | Up to 8 at once |
| `GET /api/instruments` | Registry with the source used and last date |
| `GET /api/flashcards/due` · `POST /api/flashcards/{id}/review` | Spaced repetition |
| `GET /api/health` | Snapshot date, mode and last run |
| `POST /api/admin/refresh` | Re-run the pipeline (needs `X-Admin-Token` = `MACRO_ADMIN_TOKEN`) |

## Known limits

- CNBC, Yahoo and Stooq are unofficial endpoints and can change without notice;
  the sources report (`data/export/sources-report.txt`) shows what worked on the
  last run. Stooq currently returns HTML instead of CSV, so it fails and is skipped.
- The BoJ policy rate falls back to a monthly OECD series when Refinitiv is
  unavailable, so it is flagged as stale between months.
- German breakevens, Japanese inflation swaps and JP/Asia credit need Refinitiv.
- Not investment advice.
