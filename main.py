"""Monte Lattice site: unifying Flask app for the 4-project dashboard.

Serves 4 public/private pages (home, job-engine, docfiler, crypto, budget) in a shared Art
Deco theme. Static pages (home, docfiler) need no backend data. The two utility dashboards
(job-engine, crypto) read from their respective project's own SQLite DB directly - this app
does not duplicate their logic, it only queries their existing tables read-only. The budget
page is gated behind a single shared-password session, since it's a single-user private tool.
"""
from __future__ import annotations

import os
import sqlite3
from functools import wraps

from flask import Flask, jsonify, redirect, render_template, request, session, url_for

app = Flask(__name__)
app.secret_key = os.environ.get("SITE_SECRET_KEY", "dev-only-change-me")

SITE_PASSWORD = os.environ.get("BUDGET_SITE_PASSWORD")  # required to unlock /budget

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
        if not session.get("budget_authed"):
            return redirect(url_for("budget_login"))
        return view(*args, **kwargs)
    return wrapped


# ---------------------------------------------------------------------------
# Public pages
# ---------------------------------------------------------------------------
@app.route("/")
def home():
    return render_template("home.html")


@app.route("/job-engine")
def job_engine():
    return render_template("job_engine.html", active_page="job-engine")


@app.route("/docfiler")
def docfiler():
    return render_template("docfiler.html", active_page="docfiler")


@app.route("/crypto")
def crypto():
    return render_template("crypto.html", active_page="crypto")


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
# Budget tracker: password-gated
# ---------------------------------------------------------------------------
@app.route("/budget/login", methods=["GET", "POST"])
def budget_login():
    error = None
    if request.method == "POST":
        if SITE_PASSWORD and request.form.get("password") == SITE_PASSWORD:
            session["budget_authed"] = True
            return redirect(url_for("budget"))
        error = "Incorrect password."
    return render_template("budget_login.html", error=error)


@app.route("/budget/logout")
def budget_logout():
    session.pop("budget_authed", None)
    return redirect(url_for("home"))


@app.route("/budget")
@login_required
def budget():
    return render_template("budget.html", active_page="budget")


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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5003, debug=False)
