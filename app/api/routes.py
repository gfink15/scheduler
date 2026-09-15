from datetime import datetime, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo

from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user

from app.constants import PRIORITY_BY_VALUE
from app.extensions import db
from app.models import Occurrence, Item, WorkLog
from app.models.user import utcnow
from app.shorthand.values import parse_duration, ValueError_

bp = Blueprint("api", __name__)


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _user_tz() -> ZoneInfo:
    settings = current_user.settings
    return ZoneInfo(settings.timezone if settings else current_user.timezone)


def _parse_iso(raw: str | None, fallback: datetime) -> datetime:
    """FullCalendar sends '2026-09-01T00:00:00-04:00' or '...Z'."""
    if not raw:
        return fallback
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return fallback
    return dt if dt.tzinfo else dt.replace(tzinfo=dt_timezone.utc)


def _state(occ: Occurrence, now: datetime, tz: ZoneInfo) -> str:
    if occ.status in ("done", "skipped", "cancelled"):
        return occ.status
    today = now.astimezone(tz).date()
    if occ.due_at and occ.due_at < now:
        return "overdue"
    if occ.due_at and occ.due_at.astimezone(tz).date() == today:
        return "due_today"
    if occ.prep_start_at and occ.prep_start_at <= now:
        return "active"
    return "upcoming"


def _owned(uuid: str) -> Occurrence:
    return Occurrence.query.filter_by(
        uuid=uuid, user_id=current_user.id).first_or_404()


# --------------------------------------------------------------------------
# occurrence actions
# --------------------------------------------------------------------------

@bp.post("/occurrences/<uuid>/done")
@login_required
def mark_done(uuid):
    occ = _owned(uuid)
    occ.status = "done"
    occ.completed_at = utcnow()
    occ.completion_percent = 100
    occ.remaining_minutes = 0
    db.session.commit()
    return jsonify({"ok": True, "uuid": uuid, "status": occ.status})


@bp.post("/occurrences/<uuid>/skip")
@login_required
def mark_skipped(uuid):
    occ = _owned(uuid)
    occ.status = "skipped"
    db.session.commit()
    return jsonify({"ok": True, "uuid": uuid, "status": occ.status})


@bp.post("/occurrences/<uuid>/log")
@login_required
def log_work(uuid):
    occ = _owned(uuid)
    payload = request.get_json(silent=True) or {}
    raw = payload.get("duration") or request.form.get("duration", "")

    try:
        minutes = parse_duration(str(raw))
    except ValueError_ as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400

    db.session.add(WorkLog(
        occurrence_id=occ.id,
        user_id=current_user.id,
        minutes_spent=minutes,
        ended_at=utcnow(),
        note=payload.get("note"),
    ))

    base = occ.estimated_minutes or 0
    spent = occ.minutes_spent + minutes
    occ.remaining_minutes = max(0, base - spent) if base else None
    occ.completion_percent = min(100, round(spent / base * 100)) if base else 0

    if occ.status == "planned":
        occ.status = "active"
    if base and spent >= base:
        occ.status = "done"
        occ.completed_at = utcnow()

    db.session.commit()
    return jsonify({
        "ok": True, "spent": spent, "remaining": occ.remaining_minutes,
        "percent": occ.completion_percent, "status": occ.status,
    })


# --------------------------------------------------------------------------
# calendar feed
# --------------------------------------------------------------------------

@bp.get("/calendar/events")
@login_required
def calendar_events():
    now = utcnow()
    tz = _user_tz()
    start = _parse_iso(request.args.get("start"), now - timedelta(days=31))
    end = _parse_iso(request.args.get("end"), now + timedelta(days=62))
    show_prep = request.args.get("prep", "1") != "0"

    rows = (Occurrence.query
            .join(Item)
            .filter(Occurrence.user_id == current_user.id,
                    Occurrence.status != "cancelled",
                    Occurrence.occurrence_date >= start.date() - timedelta(days=2),
                    Occurrence.occurrence_date <= end.date() + timedelta(days=2))
            .all())

    events = []
    for occ in rows:
        item = occ.item
        state = _state(occ, now, tz)
        label = f"{item.course + ' ' if item.course else ''}{item.name}"
        shared = {
            "occurrence": occ.uuid,
            "course": item.course,
            "name": item.name,
            "itemType": item.item_type,
            "priority": PRIORITY_BY_VALUE.get(occ.priority, "medium"),
            "estimated": occ.estimated_minutes,
            "remaining": occ.remaining_minutes,
            "percent": occ.completion_percent,
            "status": occ.status,
            "state": state,
            "description": item.description,
            "url": item.url,
        }

        # assignments: a point event at the deadline
        if occ.due_at:
            events.append({
                "id": f"{occ.uuid}:due",
                "title": f"Due: {label}",
                "start": occ.due_at.isoformat(),
                "classNames": [f"ev--{state}", "ev--due"],
                "extendedProps": {**shared, "kind": "due"},
            })

        # habits / events: a block sized by the effort estimate
        if occ.start_at:
            minutes = occ.estimated_minutes or 30
            events.append({
                "id": f"{occ.uuid}:start",
                "title": label,
                "start": occ.start_at.isoformat(),
                "end": (occ.start_at + timedelta(minutes=minutes)).isoformat(),
                "classNames": [f"ev--{state}", "ev--block"],
                "extendedProps": {**shared, "kind": "block"},
            })

        # prep window opening — only when it differs from the due date
        if (show_prep and occ.prep_start_at and occ.due_at
                and occ.prep_start_at < occ.due_at
                and occ.status not in ("done", "skipped")):
            events.append({
                "id": f"{occ.uuid}:prep",
                "title": f"Start: {label}",
                "start": occ.prep_start_at.isoformat(),
                "classNames": ["ev--prep"],
                "extendedProps": {**shared, "kind": "prep"},
            })

    return jsonify(events)