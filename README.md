# montelattice-site

The unifying dashboard/portfolio site for montelattice.com: home page + 4 project pages in a
shared Art Deco (Rapture) theme.

| Page | Treatment | Purpose |
|---|---|---|
| `/` | Public | Landing page, links to all 4 projects |
| `/job-engine` | Public, utility | Live pipeline metrics from job-outreach-engine (applications, interviews, reply rate, daily activity) |
| `/docfiler` | Public, marketing | Pitch page for small law firms/RIAs, with a lead-capture contact form |
| `/crypto` | Public, utility | Live portfolio/signal dashboard from crypto-trading-engine (paper trading only) |
| `/budget` | Private (password-gated) | Personal income/spending charts from budget-tracker |

## Architecture

```
main.py                   Flask app: routes for all pages + read-only JSON APIs.
templates/base.html        Shared layout (nav, fonts, Chart.js) every page extends.
templates/home.html        Landing page with 4 project cards.
templates/job_engine.html  Utility dashboard: metric tiles + 2 charts.
templates/docfiler.html    Marketing page + contact form.
templates/crypto.html      Utility dashboard: portfolio metrics + recent signals.
templates/budget_login.html / budget.html   Password gate + private charts.
static/css/rapture.css     Shared Art Deco theme (dark navy/teal, brass/gold accents,
                            ornate panel borders, Cinzel/EB Garamond typography).
```

## How this reads other repos' data

This app does **not** duplicate any project's logic - it opens each project's own SQLite DB in
strict read-only mode (`mode=ro`) and queries existing tables directly:

- `job-outreach-engine`'s `jobs_cache.db` (`application_outcomes`, `daily_activity`)
- `crypto-trading-engine`'s `crypto_engine.db` (`paper_portfolio`, `open_signals`)
- `budget-tracker`'s `budget_tracker.db` (`transactions`)

If a DB file doesn't exist yet (a project hasn't been run), the API returns an empty/graceful
response (`data_available: false`) rather than erroring - so this site works even before every
project has real accumulated data.

## Setup

```
pip install -r requirements.txt
```

Environment variables:

| Variable | Required | Purpose |
|---|---|---|
| `SITE_SECRET_KEY` | Recommended | Flask session signing key. Set a real random value in production. |
| `BUDGET_SITE_PASSWORD` | Yes, to unlock `/budget` | Single shared password gating the private budget page. |
| `JOB_ENGINE_DB_PATH` | Optional | Overrides the default path to job-outreach-engine's SQLite DB. |
| `CRYPTO_ENGINE_DB_PATH` | Optional | Overrides the default path to crypto-trading-engine's SQLite DB. |
| `BUDGET_TRACKER_DB_PATH` | Optional | Overrides the default path to budget-tracker's SQLite DB. |

Run: `python main.py` (serves on port 5003).

## Deployment

Intended to run on the same always-on host as job-outreach-engine and crypto-trading-engine, so
its read-only DB paths resolve without any network hop. Point `montelattice.com`'s DNS at
whichever host serves this app once deployed.
