"""Rolling occurrence generation."""
from datetime import datetime, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo

from app.extensions import db
from app.models import Item, Occurrence
from app.shorthand.recurrence import parse_recurrence, expand


def _to_utc(naive_local: datetime, tzname: str) -> datetime:
    return naive_local.replace(tzinfo=ZoneInfo(tzname)).astimezone(dt_timezone.utc)


def _prep_start(due_utc, prep_minutes, available_utc):
    if due_utc is None or not prep_minutes:
        return due_utc
    start = due_utc - timedelta(minutes=prep_minutes)
    return max(start, available_utc) if available_utc else start


def generate_for_item(item: Item, *, backfill_days=7, horizon_days=60) -> int:
    """Create/refresh occurrences inside the moving window. Returns rows written."""
    tz = ZoneInfo(item.timezone)
    now_local = datetime.now(tz).replace(tzinfo=None)

    if not item.recurrence_raw or item.recurrence_kind == "none":
        return _ensure_single_occurrence(item)

    rec = parse_recurrence(item.recurrence_raw)

    window_start = now_local - timedelta(days=backfill_days)
    window_end = now_local + timedelta(days=horizon_days)

    if item.recurrence_start_at:
        anchor = item.recurrence_start_at.astimezone(tz).replace(tzinfo=None)
        window_start = max(window_start, anchor)
    if item.recurrence_end_at:
        stop = item.recurrence_end_at.astimezone(tz).replace(tzinfo=None)
        window_end = min(window_end, stop)

    written = 0
    for local_dt in expand(rec, window_start, window_end):
        key = f"{item.uuid}:{local_dt.isoformat()}"
        occ = Occurrence.query.filter_by(item_id=item.id, generator_key=key).first()
        if occ and (occ.is_closed or occ.manual_override):
            continue

        when_utc = _to_utc(local_dt, item.timezone)
        is_assignment = item.item_type == "assignment"
        due_utc = when_utc if is_assignment else None
        start_utc = None if is_assignment else when_utc

        if occ is None:
            occ = Occurrence(item_id=item.id, user_id=item.user_id,
                             generator_key=key, is_generated=True)
            db.session.add(occ)

        occ.occurrence_date = local_dt.date()
        occ.due_at = due_utc
        occ.start_at = start_utc
        occ.prep_start_at = _prep_start(due_utc, item.prep_minutes, item.available_at)
        occ.priority = item.priority
        occ.estimated_minutes = item.estimated_minutes
        if occ.remaining_minutes is None:
            occ.remaining_minutes = item.estimated_minutes
        written += 1

    item.last_generated_at = datetime.now(dt_timezone.utc)
    return written


def _ensure_single_occurrence(item: Item) -> int:
    occ = item.occurrences.filter_by(is_generated=False).first()
    if occ and (occ.is_closed or occ.manual_override):
        return 0
    if occ is None:
        occ = Occurrence(item_id=item.id, user_id=item.user_id, is_generated=False)
        db.session.add(occ)

    tz = ZoneInfo(item.timezone)
    anchor = item.due_at or item.available_at
    occ.occurrence_date = (anchor.astimezone(tz).date() if anchor
                           else datetime.now(tz).date())
    occ.due_at = item.due_at
    occ.start_at = item.available_at if item.item_type != "assignment" else None
    occ.prep_start_at = _prep_start(item.due_at, item.prep_minutes, item.available_at)
    occ.priority = item.priority
    occ.estimated_minutes = item.estimated_minutes
    if occ.remaining_minutes is None:
        occ.remaining_minutes = item.estimated_minutes
    return 1


def generate_for_user(user_id: int, **kwargs) -> int:
    total = 0
    items = Item.query.filter_by(user_id=user_id).filter(
        Item.status.notin_(("cancelled", "archived"))).all()
    for item in items:
        total += generate_for_item(item, **kwargs)
    db.session.commit()
    return total