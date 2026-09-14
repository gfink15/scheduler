"""Categorise occurrences and suggest today's workload."""
import math
from datetime import datetime, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo

from app.models import Occurrence, Item

MAX_DAILY = 120
MAX_DAILY_URGENT = 240
MIN_DAILY = 15


def _round15(minutes: float) -> int:
    return int(math.ceil(minutes / 15.0) * 15)


def recommended_minutes(occ: Occurrence, now_utc: datetime) -> int | None:
    remaining = occ.remaining_minutes
    if not remaining:
        return None
    if occ.due_at:
        days = max(1, (occ.due_at.date() - now_utc.date()).days + 1)
    else:
        days = 1
    raw = remaining / days
    mins = max(MIN_DAILY, _round15(raw))
    urgent = occ.due_at and occ.due_at <= now_utc + timedelta(days=1)
    cap = MAX_DAILY_URGENT if urgent else MAX_DAILY
    return min(mins, remaining, cap)


def score(occ: Occurrence, now_utc: datetime) -> int:
    s = occ.priority * 50
    if occ.due_at:
        delta = occ.due_at - now_utc
        if delta.total_seconds() < 0:
            s += 1000
        elif occ.due_at.date() == now_utc.date():
            s += 700
        elif delta <= timedelta(days=1):
            s += 500
        elif delta <= timedelta(days=3):
            s += 300
        elif delta <= timedelta(days=7):
            s += 100
    if occ.prep_start_at and occ.prep_start_at <= now_utc:
        s += 150
    if occ.prep_start_at and occ.prep_start_at.date() == now_utc.date():
        s += 125
    if (occ.remaining_minutes or 0) > 300:
        s += 100
    elif (occ.remaining_minutes or 0) > 120:
        s += 50
    return s


def build_dashboard(user_id: int, tzname: str, lookahead_days: int = 7) -> dict:
    now_utc = datetime.now(dt_timezone.utc)
    today = datetime.now(ZoneInfo(tzname)).date()
    horizon = now_utc + timedelta(days=lookahead_days)

    rows = (Occurrence.query
            .join(Item)
            .filter(Occurrence.user_id == user_id,
                    Occurrence.status.in_(("planned", "active")),
                    Occurrence.occurrence_date <= (today + timedelta(days=lookahead_days)))
            .order_by(Occurrence.due_at.asc().nullslast())
            .all())

    buckets = {k: [] for k in ("overdue", "due_today", "scheduled_today",
                               "start_today", "continue_work", "upcoming")}

    for occ in rows:
        occ.recommended_minutes = recommended_minutes(occ, now_utc)
        placed = False

        if occ.due_at and occ.due_at < now_utc:
            buckets["overdue"].append(occ); placed = True
        elif occ.due_at and occ.due_at.astimezone(ZoneInfo(tzname)).date() == today:
            buckets["due_today"].append(occ); placed = True
        elif occ.start_at and occ.start_at.astimezone(ZoneInfo(tzname)).date() == today:
            buckets["scheduled_today"].append(occ); placed = True
        elif occ.prep_start_at:
            prep_day = occ.prep_start_at.astimezone(ZoneInfo(tzname)).date()
            if prep_day == today:
                buckets["start_today"].append(occ); placed = True
            elif prep_day < today and occ.due_at and occ.due_at > now_utc:
                buckets["continue_work"].append(occ); placed = True

        if not placed and occ.due_at and occ.due_at <= horizon:
            buckets["upcoming"].append(occ)

    for key in buckets:
        buckets[key].sort(key=lambda o: score(o, now_utc), reverse=True)

    buckets["total_recommended_minutes"] = sum(
        (o.recommended_minutes or 0)
        for k in ("overdue", "due_today", "scheduled_today", "start_today", "continue_work")
        for o in buckets[k]
    )
    return buckets