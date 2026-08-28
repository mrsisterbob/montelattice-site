# montelattice-site

The portfolio site for montelattice.com plus the private **Console** cockpit. The public pages are
a recruiter-facing storefront; the Console is the owner's one-screen control panel for every
sibling system.

| Page | Treatment | Purpose |
|---|---|---|
| `/` | Public | Landing page, links to all 4 projects. Keeps a "Live from the Job Engine" strip fed by `/api/job-engine/summary` (public, aggregate counts only). |
| `/job-engine` | Public, marketing | How the pipeline works + a sample outcome table. Live metrics moved to the Console. |
| `/docfiler` | Public, marketing | Pitch page for small law firms/RIAs, with a lead-capture contact form. |
| `/crypto` | Public, marketing | How the regime dashboard works + a sample signal table. Live portfolio moved to the Console. |
| `/budget` | Public, marketing | What the budget tracker does + a static sample breakdown. The real charts are in the Console. |
| `/console` | **Private (password-gated)** | The cockpit: Today strip, system-status board, KPI row, live Job/Crypto/Budget sections, trend charts. Refreshes every 60s. |
| `/console/demo` | Public, number-scrubbed | A safe-to-link snapshot of the cockpit with fake illustrative numbers. |

The Console is gated by the same shared password that historically gated `/budget`
(`BUDGET_SITE_PASSWORD`). Old `/budget/login` and `/budget/logout` URLs redirect to the
`/console/*` equivalents.

## Architecture

```
main.py                    Flask app: public pages, marketing routes, the gated Console,
                           read-only sibling-DB rollups, and /api/console/snapshot.
templates/base.html        Shared layout (nav, fonts, Chart.js) + footer Console link.
templates/home.html        Landing page with 4 project cards + the Live strip.
templates/job_engine.html  Marketing: how-it-works + sample table.
templates/docfiler.html    Marketing page + contact form.
templates/crypto.html      Marketing: what-it-tracks + sample signal table.
templates/budget.html      Marketing: what's-inside + a static sample doughnut.
templates/console.html     The cockpit (also serves /console/demo, scrubbed).
templates/console_login.html   Password gate.
static/css/rapture.css     Corporate/Apple light theme; the `.console` block adds a
                           warmer cockpit theme (light + dark) scoped to that page only.
static/js/site.js          The one count-up animation + MonteLattice.formatRelative().
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
| `BUDGET_SITE_PASSWORD` | Yes, to unlock `/console` | Single shared password gating the Console cockpit. `SITE_PASSWORD` is accepted as an alias (logs a deprecation line). |
| `CONSOLE_HEARTBEAT_TOKEN` | Optional | Shared secret the bots present in an `X-Console-Token` header to `POST /api/console/heartbeat`. If unset, that endpoint returns 503 (no unauthenticated writes). |
| `JOB_ENGINE_DB_PATH` | Optional | Overrides the default path to job-outreach-engine's SQLite DB. |
| `CRYPTO_ENGINE_DB_PATH` | Optional | Overrides the default path to crypto-trading-engine's SQLite DB. |
| `BUDGET_TRACKER_DB_PATH` | Optional | Overrides the default path to budget-tracker's SQLite DB. |

### Telegram-run heartbeat

The job/crypto bots can POST a one-line run summary so the Console's Today strip shows
"pipeline ran 12 min ago" without opening Telegram:

```
curl -XPOST https://montelattice.com/api/console/heartbeat \
  -H "X-Console-Token: $CONSOLE_HEARTBEAT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"source":"job","ran_at":"2026-08-28T09:00:00","summary":"5 cards, 1 warm match"}'
```

`source` is `job` (or `job-engine`) / `crypto`. Rows are upserted into `console_heartbeats.db`
in this app's directory &mdash; the only database this app ever writes.

Run: `python main.py` (serves on port 5003).

## Deployment

### Render (current)

Deployed as a **Web Service** (not a Cron Job). `render.yaml` in the repo root is the blueprint;
or configure manually:

| Field | Value |
|---|---|
| Build command | `pip install -r requirements.txt` |
| Start command | `gunicorn main:app --workers 2 --bind 0.0.0.0:$PORT --timeout 30` |
| Health check path | `/` |

Set these in the dashboard's **Environment** tab (never in git):

- `SITE_SECRET_KEY` — any long random string
- `BUDGET_SITE_PASSWORD` — the Console password
- `CONSOLE_HEARTBEAT_TOKEN` — optional; only needed once the bots POST run heartbeats

On the free plan the service sleeps after 15 min idle (first request then takes ~30-50s to wake),
and the filesystem is ephemeral — `console_heartbeats.db` resets on each deploy, which just makes
the Today strip fall back to "no pipeline run recorded yet". Upgrade to Starter for always-on, or
set `CONSOLE_HEARTBEAT_DB` to a path on a persistent disk.

**Live Console data:** `/console` reads the sibling projects' SQLite files by local path. On a
generic host those don't exist, so the Console sections show "down" and `/console/demo` (baked
fake data) is the shareable view. To get real Console numbers public, run this app on the same
box as the bots.

### DNS (Namecheap -> Render)

In Render, add the custom domain `montelattice.com` (and `www`); Render shows the exact target.
Then in Namecheap **Advanced DNS**: remove the old `A @` records and the `www` CNAME pointing at
the previous host, add Render's records, and **keep** the SPF/DMARC `TXT` records (email, unrelated).
