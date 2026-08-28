"""Monte Lattice site: unifying Flask app for the portfolio site + the private Console cockpit.

Public marketing pages (home, job-engine, docfiler, crypto, budget) share an Art Deco theme and
carry sample/explainer content only. The private Console (/console) is the owner's control panel:
it reads every sibling project's own SQLite DB read-only (never writes to them) and rolls the
numbers into one cockpit - a Today strip, a status board, a KPI row, live per-system sections,
trend charts, and a Telegram-run heartbeat. The Console is gated behind a single shared-password
session; /console/demo is a public, number-scrubbed snapshot for linking in applications.

The only database this app itself writes is console_heartbeats.db in this directory, populated by
POSTs from the bots to /api/console/heartbeat.
"""
from __future__ import annotations

import datetime as _dt
import logging
import os
import sqlite3
from functools import wraps

from flask import Flask, jsonify, redirect, render_template, request, session, url_for


def _load_dotenv():
    """Minimal .env loader (no dependency): KEY=VALUE lines, '#' comments, optional quotes.
    Real environment variables always win over the file, so a host's config is never overridden.
    """
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                os.environ.setdefault(key, val)
    except FileNotFoundError:
        pass


_load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SITE_SECRET_KEY", "dev-only-change-me")

# Canonical name is BUDGET_SITE_PASSWORD (it has gated /budget historically and still gates
# /console). SITE_PASSWORD is accepted as an alias so a future rename doesn't lock the owner out.
SITE_PASSWORD = os.environ.get("BUDGET_SITE_PASSWORD") or os.environ.get("SITE_PASSWORD")
if not os.environ.get("BUDGET_SITE_PASSWORD") and os.environ.get("SITE_PASSWORD"):
    logging.warning("Using SITE_PASSWORD; prefer BUDGET_SITE_PASSWORD (canonical name for the Console gate).")

# Shared secret the bots present (X-Console-Token header) to POST run heartbeats. If unset, the
# heartbeat endpoint is disabled (returns 503) rather than accepting unauthenticated writes.
CONSOLE_HEARTBEAT_TOKEN = os.environ.get("CONSOLE_HEARTBEAT_TOKEN")
CONSOLE_HEARTBEAT_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "console_heartbeats.db")

# Paths to the other projects' SQLite DBs - read-only queries only, never written to from here.
# Overridable via env vars so this app can run on the same host as the other repos without
# hardcoding absolute paths that only make sense on one machine.
JOB_ENGINE_DB_PATH = os.environ.get("JOB_ENGINE_DB_PATH", r"C:\Users\kjmil\job-outreach-engine\jobs_cache.db")
CRYPTO_ENGINE_DB_PATH = os.environ.get("CRYPTO_ENGINE_DB_PATH", r"C:\Users\kjmil\crypto-trading-engine\crypto_engine.db")
BUDGET_TRACKER_DB_PATH = os.environ.get("BUDGET_TRACKER_DB_PATH", r"C:\Users\kjmil\budget-tracker\budget_tracker.db")


def _read_only_query(db_path: str, query: str, params: tuple = ()) -> list[dict]:
    """Opens a DB strictly for reading (mode=ro) so this dashboard app can never corrupt or
    lock another project's live database - if the file doesn't exist yet, returns an empty
    list rather than raising, since a project may not have generated any data yet."""
    if not os.path.exists(db_path):
        return []
    uri = f"file:{db_path}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True, timeout=5)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("console_authed"):
            return redirect(url_for("console_login"))
        return view(*args, **kwargs)
    return wrapped


def _relpath_exists(path: str) -> bool:
    try:
        return bool(path) and os.path.exists(path)
    except OSError:
        return False


def _newest_ts(db_path: str, query: str):
    """Return the single scalar (usually a timestamp string) from `query`, or None."""
    rows = _read_only_query(db_path, query)
    if rows:
        first = rows[0]
        return next(iter(first.values()), None)
    return None


# ---------------------------------------------------------------------------
# Public source repos - the single source of truth for the /code page and the
# "View source" links on the product pages. Static by design: repo URLs don't
# change, and no recruiter is checking whether "updated" is live. `slug` ties a
# repo to the product page that should show its inline link.
# ---------------------------------------------------------------------------
REPOS = [
    {
        "name": "job-outreach-engine",
        "slug": "job-engine",
        "url": "https://github.com/mrsisterbob/job-outreach-engine",
        "blurb": "The AI-screened job-search pipeline behind the Job Engine page: multi-board "
                 "sourcing, Gemini as a strict classifier/router, a deterministic Typst résumé "
                 "compiler, a Google Sheets CRM, and a swipe-reply Telegram bot.",
        "stack": "Python · Flask · SQLite · APScheduler · Gemini",
        "highlight": "177 commits · 54 unit tests · ~6k lines",
    },
    {
        "name": "montelattice-site",
        "slug": None,
        "url": "https://github.com/mrsisterbob/montelattice-site",
        "blurb": "This site. A Flask app that serves the public project pages and a private "
                 "read-only Console cockpit rolling up live metrics from each project's own database.",
        "stack": "Python · Flask · Jinja · Chart.js",
        "highlight": "Zero-build, one animation, Lighthouse-clean",
    },
]
REPOS_BY_SLUG = {r["slug"]: r for r in REPOS if r["slug"]}


# ---------------------------------------------------------------------------
# Public pages
# ---------------------------------------------------------------------------
@app.route("/")
def home():
    return render_template("home.html", active_page="home")


@app.route("/code")
def code():
    return render_template("code.html", active_page="code", repos=REPOS)


@app.route("/job-engine")
def job_engine():
    return render_template("job_engine.html", active_page="job-engine",
                           repo=REPOS_BY_SLUG.get("job-engine"))


@app.route("/docfiler")
def docfiler():
    return render_template("docfiler.html", active_page="docfiler")


@app.route("/crypto")
def crypto():
    return render_template("crypto.html", active_page="crypto")


@app.route("/budget")
def budget():
    # Public marketing page now (the real budget dashboard lives in the Console).
    return render_template("budget.html", active_page="budget")


# ---------------------------------------------------------------------------
# Job engine: read-only metrics API
# ---------------------------------------------------------------------------
@app.route("/api/job-engine/summary")
def api_job_engine_summary():
    outcomes = _read_only_query(
        JOB_ENGINE_DB_PATH,
        "SELECT sheet_uuid, source, outreach_path, status, created_at FROM application_outcomes ORDER BY created_at ASC",
    )
    by_source: dict[str, dict] = {}
    total_applied = 0
    total_interviews = 0
    for row in outcomes:
        source = row["source"] or "unknown"
        by_source.setdefault(source, {"applied": 0, "interview": 0})
        if row["status"] == "applied":
            by_source[source]["applied"] += 1
            total_applied += 1
        elif row["status"] == "interview":
            by_source[source]["interview"] += 1
            total_interviews += 1

    for stats in by_source.values():
        stats["reply_rate_pct"] = round((stats["interview"] / stats["applied"] * 100), 1) if stats["applied"] else 0.0

    daily = _read_only_query(
        JOB_ENGINE_DB_PATH,
        "SELECT date, drafts_staged, applied_count, notes_logged FROM daily_activity ORDER BY date ASC LIMIT 90",
    )

    return jsonify({
        "total_applied": total_applied,
        "total_interviews": total_interviews,
        "reply_rate_pct": round((total_interviews / total_applied * 100), 1) if total_applied else 0.0,
        "by_source": by_source,
        "daily_activity": daily,
        "data_available": bool(outcomes or daily),
    })


# ---------------------------------------------------------------------------
# Crypto engine: read-only regime/portfolio API
# ---------------------------------------------------------------------------
@app.route("/api/crypto/summary")
def api_crypto_summary():
    open_trades = _read_only_query(
        CRYPTO_ENGINE_DB_PATH,
        "SELECT symbol, entry_price, stop_loss, take_profit, opened_at FROM paper_portfolio WHERE status = 'OPEN'",
    )
    closed = _read_only_query(
        CRYPTO_ENGINE_DB_PATH,
        "SELECT pnl_usd, status FROM paper_portfolio WHERE status IN ('CLOSED_TP', 'CLOSED_SL', 'CLOSED_BE', 'CLOSED_MANUAL')",
    )
    recent_signals = _read_only_query(
        CRYPTO_ENGINE_DB_PATH,
        "SELECT symbol, confidence_score, context_summary, triggered_at FROM open_signals ORDER BY triggered_at DESC LIMIT 10",
    )

    total_closed = len(closed)
    wins = sum(1 for c in closed if (c["pnl_usd"] or 0) > 0)
    realized_pnl = sum((c["pnl_usd"] or 0) for c in closed)

    return jsonify({
        "open_positions": open_trades,
        "recent_signals": recent_signals,
        "closed_trade_count": total_closed,
        "win_rate_pct": round((wins / total_closed * 100), 1) if total_closed else 0.0,
        "realized_pnl_usd": round(realized_pnl, 2),
        "data_available": bool(open_trades or closed or recent_signals),
    })


# ---------------------------------------------------------------------------
# Docfiler contact form (lead capture - stored locally, no email service wired yet)
# ---------------------------------------------------------------------------
@app.route("/api/docfiler/contact", methods=["POST"])
def api_docfiler_contact():
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    email = (payload.get("email") or "").strip()
    message = (payload.get("message") or "").strip()
    if not name or not email:
        return jsonify({"error": "Name and email are required."}), 400

    leads_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docfiler_leads.txt")
    with open(leads_path, "a", encoding="utf-8") as f:
        f.write(f"{name} | {email} | {message}\n")

    return jsonify({"message": "Thanks - I'll be in touch shortly."}), 200


# ---------------------------------------------------------------------------
# Console: the private cockpit (password-gated). /console/demo is public + scrubbed.
# ---------------------------------------------------------------------------
@app.route("/console/login", methods=["GET", "POST"])
def console_login():
    error = None
    if request.method == "POST":
        if SITE_PASSWORD and request.form.get("password") == SITE_PASSWORD:
            session["console_authed"] = True
            return redirect(url_for("console"))
        error = "Incorrect password."
    return render_template("console_login.html", error=error)


@app.route("/console/logout")
def console_logout():
    session.pop("console_authed", None)
    return redirect(url_for("home"))


@app.route("/console")
@login_required
def console():
    return render_template("console.html", demo=False)


@app.route("/console/demo")
def console_demo():
    # Public, number-scrubbed snapshot - same layout, values rounded/masked client-side.
    return render_template("console.html", demo=True)


# Back-compat: old /budget/login and /budget/logout links redirect to the Console equivalents.
@app.route("/budget/login")
def _legacy_budget_login():
    return redirect(url_for("console_login"))


@app.route("/budget/logout")
def _legacy_budget_logout():
    return redirect(url_for("console_logout"))


@app.route("/api/budget/income-over-time")
@login_required
def api_budget_income():
    rows = _read_only_query(BUDGET_TRACKER_DB_PATH, "SELECT date, amount, bucket FROM transactions ORDER BY date ASC")
    from collections import defaultdict
    monthly = defaultdict(lambda: {"income": 0.0, "expenses": 0.0})
    for r in rows:
        month_key = r["date"][:7]
        if r["bucket"] == "income":
            monthly[month_key]["income"] += r["amount"]
        else:
            monthly[month_key]["expenses"] += abs(r["amount"])
    months = sorted(monthly.keys())
    return jsonify({
        "months": months,
        "income": [round(monthly[m]["income"], 2) for m in months],
        "expenses": [round(monthly[m]["expenses"], 2) for m in months],
    })


@app.route("/api/budget/spending-wheel")
@login_required
def api_budget_wheel():
    rows = _read_only_query(BUDGET_TRACKER_DB_PATH, "SELECT amount, bucket FROM transactions WHERE bucket != 'income'")
    from collections import defaultdict
    totals = defaultdict(float)
    for r in rows:
        totals[r["bucket"]] += abs(r["amount"])
    return jsonify({"bucket_totals": {k: round(v, 2) for k, v in totals.items()}})


# ---------------------------------------------------------------------------
# Console cockpit APIs (all gated; all read sibling DBs read-only; all degrade
# to zeros / "down" rather than raising when a DB file is missing).
# ---------------------------------------------------------------------------
_STALE_HOURS = 24  # a system whose newest row is older than this shows "warn"


def _job_engine_rollup() -> dict:
    outcomes = _read_only_query(
        JOB_ENGINE_DB_PATH,
        "SELECT source, status, created_at FROM application_outcomes ORDER BY created_at ASC",
    )
    daily = _read_only_query(
        JOB_ENGINE_DB_PATH,
        "SELECT date, drafts_staged, applied_count, notes_logged FROM daily_activity ORDER BY date ASC LIMIT 120",
    )
    applied = sum(1 for r in outcomes if r["status"] == "applied")
    interviews = sum(1 for r in outcomes if r["status"] == "interview")
    by_source: dict[str, dict] = {}
    for r in outcomes:
        s = r["source"] or "unknown"
        b = by_source.setdefault(s, {"applied": 0, "interview": 0})
        if r["status"] == "applied":
            b["applied"] += 1
        elif r["status"] == "interview":
            b["interview"] += 1
    for b in by_source.values():
        b["reply_rate_pct"] = round(b["interview"] / b["applied"] * 100, 1) if b["applied"] else 0.0

    today = _dt.date.today()
    week_ago = (today - _dt.timedelta(days=7)).isoformat()
    applies_this_week = sum(int(r["applied_count"] or 0) for r in daily if str(r["date"]) >= week_ago)
    active_days = [r for r in daily if (int(r["applied_count"] or 0) + int(r["drafts_staged"] or 0)) > 0]
    streak = 0
    seen = {str(r["date"]) for r in active_days}
    probe = today
    while probe.isoformat() in seen:
        streak += 1
        probe -= _dt.timedelta(days=1)

    return {
        "applied": applied,
        "interviews": interviews,
        "reply_rate_pct": round(interviews / applied * 100, 1) if applied else 0.0,
        "by_source": by_source,
        "daily": daily,
        "applies_this_week": applies_this_week,
        "active_day_streak": streak,
        "newest_ts": outcomes[-1]["created_at"] if outcomes else (daily[-1]["date"] if daily else None),
        "has_db": _relpath_exists(JOB_ENGINE_DB_PATH),
        "has_data": bool(outcomes or daily),
    }


def _crypto_rollup() -> dict:
    open_trades = _read_only_query(
        CRYPTO_ENGINE_DB_PATH,
        "SELECT symbol, entry_price, stop_loss, take_profit, opened_at FROM paper_portfolio WHERE status = 'OPEN'",
    )
    closed = _read_only_query(
        CRYPTO_ENGINE_DB_PATH,
        "SELECT pnl_usd, status, closed_at FROM paper_portfolio "
        "WHERE status IN ('CLOSED_TP','CLOSED_SL','CLOSED_BE','CLOSED_MANUAL') ORDER BY closed_at ASC",
    )
    signals = _read_only_query(
        CRYPTO_ENGINE_DB_PATH,
        "SELECT symbol, confidence_score, context_summary, triggered_at FROM open_signals ORDER BY triggered_at DESC LIMIT 10",
    )
    wins = sum(1 for c in closed if (c["pnl_usd"] or 0) > 0)
    realized = sum((c["pnl_usd"] or 0) for c in closed)
    equity, running = [], 0.0
    for c in closed:
        running += c["pnl_usd"] or 0
        equity.append({"t": c["closed_at"], "equity": round(running, 2)})

    # Circuit breaker: best-effort read of an engine state table if it exists; else None.
    cb_rows = _read_only_query(
        CRYPTO_ENGINE_DB_PATH,
        "SELECT value FROM engine_state WHERE key = 'circuit_breaker'",
    )
    circuit_breaker = (cb_rows[0]["value"] if cb_rows else None)

    newest = None
    for cand in (signals[0]["triggered_at"] if signals else None,
                 open_trades[-1]["opened_at"] if open_trades else None,
                 closed[-1]["closed_at"] if closed else None):
        if cand and (newest is None or str(cand) > str(newest)):
            newest = cand

    return {
        "open_positions": open_trades,
        "recent_signals": signals,
        "closed_trade_count": len(closed),
        "win_rate_pct": round(wins / len(closed) * 100, 1) if closed else 0.0,
        "realized_pnl_usd": round(realized, 2),
        "equity_curve": equity,
        "circuit_breaker": circuit_breaker,
        "newest_ts": newest,
        "has_db": _relpath_exists(CRYPTO_ENGINE_DB_PATH),
        "has_data": bool(open_trades or closed or signals),
    }


def _budget_rollup() -> dict:
    rows = _read_only_query(
        BUDGET_TRACKER_DB_PATH, "SELECT date, amount, bucket FROM transactions ORDER BY date ASC"
    )
    from collections import defaultdict
    monthly = defaultdict(lambda: {"income": 0.0, "expenses": 0.0})
    for r in rows:
        key = str(r["date"])[:7]
        if r["bucket"] == "income":
            monthly[key]["income"] += r["amount"] or 0
        else:
            monthly[key]["expenses"] += abs(r["amount"] or 0)
    months = sorted(monthly)
    this_month = _dt.date.today().isoformat()[:7]
    net_this_month = round(monthly[this_month]["income"] - monthly[this_month]["expenses"], 2) if this_month in monthly else 0.0
    return {
        "months": months,
        "income": [round(monthly[m]["income"], 2) for m in months],
        "expenses": [round(monthly[m]["expenses"], 2) for m in months],
        "net_this_month": net_this_month,
        "newest_ts": str(rows[-1]["date"]) if rows else None,
        "has_db": _relpath_exists(BUDGET_TRACKER_DB_PATH),
        "has_data": bool(rows),
    }


def _heartbeat_init():
    try:
        conn = sqlite3.connect(CONSOLE_HEARTBEAT_DB, timeout=5)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS console_heartbeats ("
            "source TEXT PRIMARY KEY, ran_at TEXT, summary TEXT, received_at TEXT)"
        )
        conn.commit()
        conn.close()
    except sqlite3.Error as exc:  # pragma: no cover
        logging.warning("heartbeat DB init failed: %s", exc)


def _heartbeats() -> list[dict]:
    if not os.path.exists(CONSOLE_HEARTBEAT_DB):
        return []
    return _read_only_query(
        CONSOLE_HEARTBEAT_DB, "SELECT source, ran_at, summary, received_at FROM console_heartbeats"
    )


def _parse_ts(ts):
    """Best-effort parse of the assorted timestamp shapes the sibling DBs use."""
    if not ts:
        return None
    s = str(ts).strip().replace("Z", "+00:00")
    try:
        return _dt.datetime.fromisoformat(s).replace(tzinfo=None)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%Y-%m"):
        try:
            return _dt.datetime.strptime(s[:19], fmt)
        except ValueError:
            continue
    return None


def _age_hours(ts):
    dt = _parse_ts(ts)
    if dt is None:
        return None
    return (_dt.datetime.now() - dt).total_seconds() / 3600.0


def _system_status(name: str, has_db: bool, has_data: bool, newest_ts) -> dict:
    if not has_db:
        state, detail = "down", "database not reachable"
    elif not has_data:
        state, detail = "warn", "no rows yet"
    else:
        age = _age_hours(newest_ts)
        if age is None:
            state, detail = "ok", "live"
        elif age > _STALE_HOURS:
            state, detail = "warn", f"newest data {int(age)}h old"
        else:
            state, detail = "ok", f"data {int(age)}h old" if age >= 1 else "data <1h old"
    return {"system": name, "state": state, "detail": detail, "newest_ts": newest_ts}


def _today_items(j, c):
    items = []

    # Pipeline freshness from the bot heartbeat (preferred) or the newest outcome row.
    hb = {h["source"]: h for h in _heartbeats()}
    job_hb = hb.get("job") or hb.get("job-engine")
    pipeline_ts = (job_hb["ran_at"] if job_hb else j["newest_ts"])
    age = _age_hours(pipeline_ts)
    if age is None:
        items.append({"kind": "pipeline", "level": "info", "text": "No pipeline run recorded yet."})
    elif age > 24:
        items.append({"kind": "pipeline", "level": "warn",
                      "text": f"Job pipeline last ran {int(age)}h ago — stale."})
    else:
        extra = f" ({job_hb['summary']})" if job_hb and job_hb.get("summary") else ""
        items.append({"kind": "pipeline", "level": "ok",
                      "text": f"Job pipeline ran {int(age)}h ago{extra}."})

    # Crypto circuit breaker
    cb = (c["circuit_breaker"] or "").lower()
    if cb in ("1", "true", "tripped", "on"):
        items.append({"kind": "crypto", "level": "warn", "text": "Crypto circuit breaker is TRIPPED."})

    # Streak nudge
    if j["active_day_streak"] == 0 and j["has_data"]:
        items.append({"kind": "job", "level": "warn", "text": "No outreach activity logged today."})
    elif j["applies_this_week"] == 0 and j["has_data"]:
        items.append({"kind": "job", "level": "warn", "text": "Zero applications sent this week."})

    # Only show "All clear." when nothing actually needs attention (no warn/info items).
    if not any(i["level"] in ("warn", "info") for i in items):
        items = [{"kind": "all", "level": "clear", "text": "All clear."}] + items

    return {"items": items, "generated_at": _dt.datetime.now().isoformat(timespec="seconds")}


def _trends(j, c):
    from collections import defaultdict
    weekly = defaultdict(int)
    for r in j["daily"]:
        dt = _parse_ts(r["date"])
        if dt:
            iso = dt.isocalendar()
            weekly[f"{iso[0]}-W{iso[1]:02d}"] += int(r["applied_count"] or 0)
    weeks = sorted(weekly)
    return {
        "applies_by_week": {"weeks": weeks, "counts": [weekly[w] for w in weeks]},
        "reply_rate_by_source": {
            "sources": list(j["by_source"].keys()),
            "applied": [v["applied"] for v in j["by_source"].values()],
            "interview": [v["interview"] for v in j["by_source"].values()],
        },
        "crypto_equity": c["equity_curve"],
    }


def _demo_snapshot() -> dict:
    """A baked, plausible-but-fake snapshot for the public /console/demo. Numbers are
    illustrative only - nothing here touches a real database."""
    weeks = [f"2026-W{n:02d}" for n in range(28, 35)]
    return {
        "demo": True,
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "kpis": {
            "applications_sent": 63, "reply_rate_pct": 14.3, "applies_this_week": 9,
            "active_day_streak": 6, "open_positions": 2, "realized_pnl_usd": 418.20,
            "net_this_month": 1240.0,
        },
        "status": {
            "checked_at": _dt.datetime.now().isoformat(timespec="seconds"),
            "systems": [
                {"system": "Job Engine", "state": "ok", "detail": "data 4h old", "newest_ts": None},
                {"system": "Crypto", "state": "ok", "detail": "data <1h old", "newest_ts": None},
                {"system": "Budget", "state": "warn", "detail": "newest data 9d old", "newest_ts": None},
            ],
        },
        "today": {"items": [
            {"kind": "pipeline", "level": "ok", "text": "Job pipeline ran 4h ago (5 cards, 1 warm match)."},
            {"kind": "job", "level": "warn", "text": "3 follow-ups overdue."},
        ], "generated_at": _dt.datetime.now().isoformat(timespec="seconds")},
        "job": {
            "total_applied": 63, "total_interviews": 9, "reply_rate_pct": 14.3,
            "daily_activity": [{"date": w, "applied_count": 0} for w in weeks],
        },
        "crypto": {
            "open_positions": [
                {"symbol": "BTCUSDT", "entry_price": 61240, "stop_loss": 59800, "take_profit": 64100},
                {"symbol": "ETHUSDT", "entry_price": 2980, "stop_loss": 2870, "take_profit": 3220},
            ],
            "recent_signals": [
                {"symbol": "SOLUSDT", "confidence_score": 71, "context_summary": "RVOL expansion at range high", "triggered_at": None},
                {"symbol": "BTCUSDT", "confidence_score": 64, "context_summary": "Funding reset", "triggered_at": None},
            ],
            "closed_trade_count": 41, "win_rate_pct": 58.5, "realized_pnl_usd": 418.20,
        },
        "budget": {
            "months": ["2026-05", "2026-06", "2026-07", "2026-08"],
            "income": [4100, 4100, 4300, 4100],
            "expenses": [3050, 3380, 2910, 2860],
            "bucket_totals": {"Housing": 1450, "Food": 620, "Transport": 340, "Everything else": 450},
        },
        "trends": {
            "applies_by_week": {"weeks": weeks, "counts": [7, 11, 5, 9, 8, 6, 9]},
            "reply_rate_by_source": {"sources": ["jsearch", "greenhouse", "lever", "referral"],
                                     "applied": [28, 14, 9, 12], "interview": [3, 2, 1, 3]},
            "crypto_equity": [{"t": f"2026-08-{d:02d}", "equity": v}
                              for d, v in zip(range(1, 22, 3), [40, 95, 60, 180, 250, 330, 418])],
        },
    }


def _live_snapshot() -> dict:
    j, c, b = _job_engine_rollup(), _crypto_rollup(), _budget_rollup()
    return {
        "demo": False,
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "kpis": {
            "applications_sent": j["applied"],
            "reply_rate_pct": j["reply_rate_pct"],
            "applies_this_week": j["applies_this_week"],
            "active_day_streak": j["active_day_streak"],
            "open_positions": len(c["open_positions"]),
            "realized_pnl_usd": c["realized_pnl_usd"],
            "net_this_month": b["net_this_month"],
        },
        "status": {
            "checked_at": _dt.datetime.now().isoformat(timespec="seconds"),
            "systems": [
                _system_status("Job Engine", j["has_db"], j["has_data"], j["newest_ts"]),
                _system_status("Crypto", c["has_db"], c["has_data"], c["newest_ts"]),
                _system_status("Budget", b["has_db"], b["has_data"], b["newest_ts"]),
            ],
        },
        "today": _today_items(j, c),
        "job": {
            "total_applied": j["applied"], "total_interviews": j["interviews"],
            "reply_rate_pct": j["reply_rate_pct"], "daily_activity": j["daily"],
        },
        "crypto": {
            "open_positions": c["open_positions"], "recent_signals": c["recent_signals"],
            "closed_trade_count": c["closed_trade_count"], "win_rate_pct": c["win_rate_pct"],
            "realized_pnl_usd": c["realized_pnl_usd"],
        },
        "budget": {
            "months": b["months"], "income": b["income"], "expenses": b["expenses"],
            "bucket_totals": _budget_bucket_totals(),
        },
        "trends": _trends(j, c),
    }


def _budget_bucket_totals() -> dict:
    rows = _read_only_query(
        BUDGET_TRACKER_DB_PATH, "SELECT amount, bucket FROM transactions WHERE bucket != 'income'"
    )
    from collections import defaultdict
    totals = defaultdict(float)
    for r in rows:
        totals[r["bucket"]] += abs(r["amount"] or 0)
    return {k: round(v, 2) for k, v in totals.items()}


@app.route("/api/console/snapshot")
def api_console_snapshot():
    # One payload for the whole cockpit. Public + baked when ?demo=1; gated + live otherwise.
    if request.args.get("demo") == "1":
        return jsonify(_demo_snapshot())
    if not session.get("console_authed"):
        return jsonify({"error": "auth required"}), 401
    return jsonify(_live_snapshot())


@app.route("/api/console/heartbeat", methods=["POST"])
def api_console_heartbeat():
    if not CONSOLE_HEARTBEAT_TOKEN:
        return jsonify({"error": "heartbeat disabled (CONSOLE_HEARTBEAT_TOKEN unset)"}), 503
    if request.headers.get("X-Console-Token") != CONSOLE_HEARTBEAT_TOKEN:
        return jsonify({"error": "unauthorized"}), 401
    payload = request.get_json(silent=True) or {}
    source = (payload.get("source") or "").strip().lower()
    if not source:
        return jsonify({"error": "source required"}), 400
    ran_at = (payload.get("ran_at") or _dt.datetime.now().isoformat(timespec="seconds")).strip()
    summary = (payload.get("summary") or "").strip()[:200]
    _heartbeat_init()
    try:
        conn = sqlite3.connect(CONSOLE_HEARTBEAT_DB, timeout=5)
        conn.execute(
            "INSERT INTO console_heartbeats (source, ran_at, summary, received_at) VALUES (?,?,?,?) "
            "ON CONFLICT(source) DO UPDATE SET ran_at=excluded.ran_at, summary=excluded.summary, received_at=excluded.received_at",
            (source, ran_at, summary, _dt.datetime.now().isoformat(timespec="seconds")),
        )
        conn.commit()
        conn.close()
    except sqlite3.Error as exc:
        logging.warning("heartbeat write failed: %s", exc)
        return jsonify({"error": "write failed"}), 500
    return jsonify({"ok": True}), 200


if __name__ == "__main__":
    _heartbeat_init()
    app.run(host="0.0.0.0", port=5003, debug=False)

