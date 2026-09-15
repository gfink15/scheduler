from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app.main.services import create_item_from_shorthand
from app.planner.recommendation import build_dashboard
from app.shorthand import ShorthandError, parse, FIELD_NAMES

from app.main.services import update_item_from_shorthand
from app.models import Item

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
    return render_template("calendar.html", fields=FIELD_NAMES)


@bp.post("/items/<uuid>/edit")
@login_required
def edit_item(uuid):
    item = Item.query.filter_by(uuid=uuid, user_id=current_user.id).first_or_404()
    try:
        update_item_from_shorthand(current_user, item, request.form.get("shorthand", ""))
        flash(f"Updated: {item.name}", "success")
    except ShorthandError as exc:
        for err in exc.errors:
            flash(err, "error")
    return redirect(request.referrer or url_for("main.dashboard"))


@bp.post("/items/<uuid>/delete")
@login_required
def delete_item(uuid):
    from app.extensions import db
    item = Item.query.filter_by(uuid=uuid, user_id=current_user.id).first_or_404()
    name = item.name
    db.session.delete(item)          # cascades to occurrences, tags, work_logs
    db.session.commit()
    flash(f"Deleted: {name}", "warning")
    return redirect(url_for("main.dashboard"))

@bp.route("/items")
@login_required
def items():
    rows = (Item.query.filter_by(user_id=current_user.id)
            .order_by(Item.course, Item.name).all())
    return render_template("items.html", items=rows)