from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app.main.services import create_item_from_shorthand
from app.planner.recommendation import build_dashboard
from app.shorthand import ShorthandError, parse, FIELD_NAMES

bp = Blueprint("main", __name__)


@bp.route("/")
@login_required
def dashboard():
    settings = current_user.settings
    tzname = settings.timezone if settings else current_user.timezone
    lookahead = (settings.upcoming_lookahead_days if settings else 7) or 7
    data = build_dashboard(current_user.id, tzname, lookahead)
    return render_template("dashboard.html", data=data, fields=FIELD_NAMES)


@bp.post("/add")
@login_required
def add_item():
    raw = request.form.get("shorthand", "")
    try:
        item = create_item_from_shorthand(current_user, raw)
        flash(f"Added: {item.name}", "success")
    except ShorthandError as exc:
        for err in exc.errors:
            flash(err, "error")
    return redirect(url_for("main.dashboard"))


@bp.post("/preview")
@login_required
def preview():
    """Live parse check — returns a plain-text summary for the entry box."""
    try:
        entry = parse(request.form.get("shorthand", ""))
        return {"ok": True, "summary": entry.summary(), "warnings": entry.warnings}
    except ShorthandError as exc:
        return {"ok": False, "errors": exc.errors}


@bp.route("/calendar")
@login_required
def calendar():
    return render_template("dashboard.html", data=None, fields=FIELD_NAMES)  # TODO phase 2