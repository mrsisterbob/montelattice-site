# Monte Lattice — the Cockpit (`/console`)

## Context

The site is a job-seeker's portfolio + product storefront (Flask/Jinja, Apple-restraint teal/off-white).
The owner wants a **private control panel** — a "mothership" — that both *shows* every system's numbers
and, where cheap, lets him *act*. A 3-judge panel settled the nav question (no hamburger split; one
discreet "Console" link). A 2-judge review of the thin "Option A" plan flagged real regressions and
demanded a KPI row. The owner then asked for the full **cockpit** (judges' Option C), accepting the
larger scope.

## What "cockpit" means here (6 pillars)

1. **Today strip** — actionable one-liners, top of page: overdue follow-ups, unactioned warm-company
   jobs, stale pipeline run, crypto circuit-breaker state. "All clear." when nothing needs him.
2. **KPI row** — ~7 count-up tiles across all three systems (applications, reply rate, open positions,
   realized PnL, net this month, this-week applies, active-day streak).
3. **Live** — silent 60s auto-refresh; every section carries a freshness stamp ("data 4 min old ✓").
4. **Status board** — per-system green/amber/red from each project's own health signals (DB reachable,
   last-run age, key config).
5. **Trends** — 3 small Chart.js charts (already loaded globally): applies/week, reply-rate by source,
   crypto equity curve.
6. **Telegram loop** — bots POST a heartbeat to `/api/console/heartbeat`; cockpit shows "pipeline ran
   12 min ago, 4 cards, 1 warm match" without opening Telegram. (Read-only in v1; action buttons later.)

Plus: **`/console/demo`** — a read-only, number-scrubbed snapshot the owner can link in applications.

## Judge-mandated corrections to the earlier plan (all folded in)

- **Do NOT gate `/api/job-engine/summary` or `/api/crypto/summary`.** `home.html` drives the public
  "Live from the Job Engine" strip (and the site's one count-up animation) off the job summary; gating
  it 302s the fetch and kills the strip for recruiters forever. Only `/api/budget/*` gets gated.
  New cockpit-only detail data goes in **new** endpoints under `/api/console/*` behind the gate.
- **Password env var is `BUDGET_SITE_PASSWORD`** (Python const `SITE_PASSWORD`, `main.py:20`). Keep
  reading it; accept `SITE_PASSWORD` too as an alias with a one-line deprecation log. No host change.
- **Session key** `budget_authed` → `console_authed`: one forced re-login, acceptable, noted here.
- `/budget` becomes a **public** marketing page (docfiler-parity: 3 explain cards + a static sample
  doughnut, no live data, no lead form). The **real** budget dashboard moves into the cockpit.
- Strip dead `#dashboard` markup + `load*Dashboard()` scripts from the public `job_engine.html` /
  `crypto.html` (the cockpit owns live rendering now); keep their sample tables as storefront proof.
- Chart.js is **already** loaded in `base.html` — no new dependency.
- `home.html`: retitle the Budget card (no longer "Private" / "Access restricted").

## File plan

### `main.py`
- `SITE_PASSWORD = os.environ.get("BUDGET_SITE_PASSWORD") or os.environ.get("SITE_PASSWORD")`; log
  a deprecation line if only the new alias is set. Rename `budget_login`→`console_login`,
  `budget_logout`→`console_logout`, `session["budget_authed"]`→`session["console_authed"]`,
  `url_for("budget_login")`→`url_for("console_login")` in `login_required`.
- `/budget`: **remove** `@login_required`, render the new public `budget.html`.
- `/console` (GET, `@login_required`) → `console.html`.
- `/console/demo` (GET, **public**) → `console.html` with `demo=True` (template scrubs numbers via a
  JS flag; server still only ever reads its own sibling DBs read-only).
- New gated JSON endpoints (all `@login_required`, all via `_read_only_query`, all tolerant of missing
  DBs → empty/zeroed payloads):
  - `/api/console/kpis` — rolled-up counts for the KPI row (reuses the same queries the existing
    summary endpoints run, plus `daily_activity` slices for "this week" / streak).
  - `/api/console/today` — computes the actionable list: overdue-followup count (from
    `application_outcomes` + `daily_activity` — whatever the job DB actually exposes; fall back to
    "n/a" cleanly), warm-company-unactioned count, pipeline-run age, crypto circuit-breaker flag.
  - `/api/console/status` — per-system `{state: ok|warn|down, detail, checked_at}`; `down` if the DB
    file is absent/unreadable, `warn` if newest row is older than a threshold.
  - `/api/console/trends` — `{applies_by_week: [...], reply_rate_by_source: {...}, crypto_equity: [...]}`.
- `/api/console/heartbeat` (POST, shared-secret header `X-Console-Token` == `CONSOLE_HEARTBEAT_TOKEN`
  env; **not** the session gate, since bots call it): upsert a row into a tiny local
  `console_heartbeats` SQLite table in *this* app's own dir (the only DB this app writes). Body:
  `{source, ran_at, summary}`. `/api/console/today` reads the latest per source.
- Keep `/api/budget/*` exactly as-is (still `@login_required`).

### templates
- **`console.html`** (extends `base.html`): `head_extra` sets a `.console` body scope + a Console-only
  theme override (warmer off-white, faint green cast; still light/dark aware via the existing token
  pattern). Sections in order: Today strip · Status board · KPI row (count-up, reuses `data-count`) ·
  Job Engine (live tiles + applies/week + by-source charts, lifted from `job_engine.html`) · Crypto
  (live tiles + equity curve + signals/positions lists, lifted from `crypto.html`) · Budget (income vs
  expenses + spending doughnut, lifted from `budget.html`). Each section header carries a
  `<span class="freshness">` filled by JS. One `<script>` block: fetch all `/api/console/*` +
  `/api/budget/*`, render, then `setInterval(refresh, 60000)`. Respects `prefers-reduced-motion`
  (count-up already does; charts get `animation:false` when reduced).
- **`console_login.html`** (from `budget_login.html`, wording only: "Private Access" → "Console").
- **`budget.html`** rewritten as the public marketing page: `_product_head.html` + 3 `.explain-card`s
  + one static sample doughnut (inline SVG in teal/gold, captioned "Sample — your real breakdown lives
  behind the Console"). No `#dashboard`, no logout button, no fetch.
- **`job_engine.html`** / **`crypto.html`**: delete `#dashboard` block + the `<script>`; keep
  `_product_head`, explain grid, sample table.
- **`home.html`**: Budget card tag `is-private`/"Private"/"Access restricted" → `"Utility · Public"` /
  "Personal income and spending tracker." Leave the Live strip + its script untouched (API stays public).
- **`base.html`**: footer gains `<a href="/console">Console</a>`. Topbar Budget link unchanged (now
  points at a real public page).

### static
- **`static/css/rapture.css`**: append a `~120-line` `.console` block — `.today-strip`,
  `.today-item` (with a left gold rule; `.is-clear` state), `.status-board` / `.status-dot`
  (`--ok`/`--warn`/`--down` colors defined on `:root` + dark override), `.freshness`,
  `.kpi-row` (reuses `.data-card` visually, tighter), and the warmer Console theme tokens scoped to
  `.console`. Nothing outside `.console` changes.
- **`static/js/site.js`**: add nothing structural — cockpit JS lives inline in `console.html`. Only
  export a small `formatRelative(ts)` helper from `MonteLattice` for the freshness stamps, reused by
  the Today strip.
- Optional later: `static/js/console.js` if the inline block grows past ~200 lines.

### README
- New env vars: `CONSOLE_HEARTBEAT_TOKEN` (optional; disables `/api/console/heartbeat` if unset).
- Note `BUDGET_SITE_PASSWORD` now also gates `/console`; `SITE_PASSWORD` accepted as alias.
- Note `/budget` is now public; the real budget view is at `/console`.

## Build order (each step compiles + runs on its own)

1. **main.py plumbing** — env alias, session/route renames, `/budget` public, `/console` +
   `/console/demo` routes returning a stub template. Verify existing `/budget/login` flow still works
   under the new names; verify `/console` redirects to login when logged out.
2. **Public page cleanup** — new public `budget.html`, strip dead blocks from `job_engine.html` /
   `crypto.html`, fix `home.html` Budget card, footer link. Verify all 5 public pages + home Live
   strip still render at 375px.
3. **`/api/console/kpis` + KPI row** — the judges' must-have. Cockpit shows a real count-up row.
4. **`/api/console/status` + status board.**
5. **`/api/console/today` + Today strip** (+ `formatRelative` helper).
6. **Lift the 3 live sections** (Job / Crypto / Budget) into `console.html` from their old templates,
   wire freshness stamps, add the 60s `setInterval`.
7. **`/api/console/trends` + 3 charts.**
8. **`/api/console/heartbeat` + Telegram-run line** in the Today strip. (Bots wired separately, later.)
9. **Console theme** (warmer off-white/green) + **`/console/demo`** number-scrubbing.
10. **CSS pass**, Lighthouse check (gated page still ≥90), dark-mode check, commit per step.

## Verification

```
cd C:\Users\kjmil\montelattice-site
$env:BUDGET_SITE_PASSWORD = "testpw"
python main.py            # http://127.0.0.1:5003/
```
- `/` → Live strip still works (job summary API still public).
- `/budget` → public marketing page, no login.
- `/console` logged-out → redirects to `/console/login`; wrong pw rejects; right pw → cockpit.
- Cockpit with sibling DBs present → real numbers; with them absent → graceful zeros + "down" dots,
  no JS errors.
- `/console/demo` (no login) → same layout, scrubbed numbers.
- `curl -XPOST /api/console/heartbeat -H "X-Console-Token: <tok>" -d '{"source":"job","ran_at":"...","summary":"4 cards"}'`
  → appears in the Today strip.
- 375px: no horizontal scroll on cockpit; Today strip + KPI row wrap.
- `prefers-reduced-motion`: no count-up tween, charts static.

## Constraints honored

- `main.py` of the sibling repos: never touched. This app only ever *reads* their DBs (`mode=ro`),
  and only ever *writes* its own `console_heartbeats` table.
- Public site aesthetic unchanged; all cockpit styling scoped to `.console`.
- One animation rule: the count-up stays the only tween; charts get `animation:false` under reduced
  motion, and the 60s refresh mutates text/values silently (no motion).
- 375px + Lighthouse ≥90 verified per step.
