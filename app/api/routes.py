from flask import Blueprint, jsonify
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Occurrence
from app.models.user import utcnow

from datetime import datetime, timedelta, timezone as dt_timezone

from app.constants import PRIORITY_BY_VALUE

bp = Blueprint("api", __name__)


@bp.post("/occurrences/<uuid>/done")
@login_required
def mark_done(uuid):
    occ = Occurrence.query.filter_by(uuid=uuid, user_id=current_user.id).first_or_404()
    occ.status = "done"
    occ.completed_at = utcnow()
    occ.completion_percent = 100
    occ.remaining_minutes = 0
    db.session.commit()
    return jsonify({"ok": True, "uuid": uuid, "status": occ.status})


@bp.post("/occurrences/<uuid>/skip")
@login_required
def mark_skipped(uuid):
    occ = Occurrence.query.filter_by(uuid=uuid, user_id=current_user.id).first_or_404()
    occ.status = "skipped"
    db.session.commit()
    return jsonify({"ok": True, "uuid": uuid, "status": occ.status})

def _parse_iso(raw: str | None, fallback: datetime) -> datetime:
    """FullCalendar sends '2026-09-01T00:00:00-04:00' or '...Z'."""
    if not raw:
        return fallback
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return fallback
    return dt if dt.tzinfo else dt.replace(tzinfo=dt_timezone.utc)


def _state(occ: Occurrence, now: datetime) -> str:
    if occ.status in ("done", "skipped", "cancelled"):
        return occ.status
    if occ.due_at and occ.due_at < now:
        return "overdue"
    if occ.due_at and occ.due_at.date() == now.date():
        return "due_today"
    if occ.prep_start_at and occ.prep_start_at <= now:
        return "active"
    return "upcoming"


@bp.get("/calendar/events")
@login_required
def calendar_events():
    now = utcnow()
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
        state = _state(occ, now)
        label = f"{item.course + ' ' if item.course else ''}{item.name}"
        shared = {
            "occurrence": occ.uuid,
            "course": item.course,
            "name": item.name,
            "itemType": item.item_type,
            "priority": PRIORITY_BY_VALUE.get(occ.priority, "medium"),
            "estimated": occ.estimated_minutes,
            "remaining": occ.remaining_minutes,
            "status": occ.status,
            "state": state,
            "description": item.description,
            "url": item.url,
        }

        # Assignments: a point event at the deadline
        if occ.due_at:
            events.append({
                "id": f"{occ.uuid}:due",
                "title": f"Due: {label}",
                "start": occ.due_at.isoformat(),
                "classNames": [f"ev--{state}", "ev--due"],
                "extendedProps": {**shared, "kind": "due"},
            })

        # Habits / events: a block sized by the effort estimate
        if occ.start_at:
            minutes = occ.estimated_minutes or 30
            events.append({
                "id": f"{occ.uuid}:start",
                "title": f"{label}",
                "start": occ.start_at.isoformat(),
                "end": (occ.start_at + timedelta(minutes=minutes)).isoformat(),
                "classNames": [f"ev--{state}", "ev--block"],
                "extendedProps": {**shared, "kind": "block"},
            })

        # Prep window opening — only when it differs from the due date
        if show_prep and occ.prep_start_at and occ.due_at \
                and occ.prep_start_at < occ.due_at and occ.status not in ("done", "skipped"):
            events.append({
                "id": f"{occ.uuid}:prep",
                "title": f"Start: {label}",
                "start": occ.prep_start_at.isoformat(),
                "classNames": ["ev--prep"],
                "extendedProps": {**shared, "kind": "prep"},
            })

    return jsonify(events)