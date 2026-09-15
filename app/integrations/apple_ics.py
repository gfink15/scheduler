"""Tokenized read-only ICS feed for Apple Calendar / Google Calendar subscription."""
from datetime import datetime, timedelta, timezone as dt_timezone

from icalendar import Calendar, Event

from app.models import Occurrence, Item, UserIntegration

BACKFILL_DAYS = 14
HORIZON_DAYS = 90


def _event(uid: str, summary: str, start: datetime, *, minutes: int = 15,
           description: str | None = None, url: str | None = None) -> Event:
    ev = Event()
    ev.add("uid", uid)
    ev.add("summary", summary)
    ev.add("dtstart", start)
    ev.add("dtend", start + timedelta(minutes=minutes))
    ev.add("dtstamp", datetime.now(dt_timezone.utc))
    if description:
        ev.add("description", description)
    if url:
        ev.add("url", url)
    return ev


def build_feed(integration: UserIntegration) -> bytes:
    user = integration.user
    now = datetime.now(dt_timezone.utc)
    lo = (now - timedelta(days=BACKFILL_DAYS)).date()
    hi = (now + timedelta(days=HORIZON_DAYS)).date()

    cal = Calendar()
    cal.add("prodid", "-//scheduler//assignment planner//EN")
    cal.add("version", "2.0")
    cal.add("x-wr-calname", f"{user.display_name or user.username} — assignments")
    cal.add("x-wr-timezone", user.timezone)
    # hint to Apple/Google how often to re-poll
    cal.add("x-published-ttl", "PT1H")
    cal.add("refresh-interval;value=duration", "PT1H")

    rows = (Occurrence.query
            .join(Item)
            .filter(Occurrence.user_id == user.id,
                    Occurrence.status.notin_(("cancelled", "skipped")),
                    Occurrence.occurrence_date >= lo,
                    Occurrence.occurrence_date <= hi)
            .all())

    for occ in rows:
        item = occ.item
        label = f"{item.course + ' ' if item.course else ''}{item.name}"
        done = occ.status == "done"
        note_bits = []
        if item.description:
            note_bits.append(item.description)
        if occ.estimated_minutes:
            note_bits.append(f"Estimated: {occ.estimated_minutes}m")
        if occ.remaining_minutes:
            note_bits.append(f"Remaining: {occ.remaining_minutes}m")
        note = "\n".join(note_bits) or None

        if occ.due_at:
            cal.add_component(_event(
                f"{occ.uuid}-due@scheduler",
                ("✓ " if done else "Due: ") + label,
                occ.due_at, minutes=15, description=note, url=item.url))

        if occ.start_at:
            cal.add_component(_event(
                f"{occ.uuid}-start@scheduler",
                ("✓ " if done else "") + label,
                occ.start_at, minutes=occ.estimated_minutes or 30,
                description=note, url=item.url))

        if (occ.prep_start_at and occ.due_at
                and occ.prep_start_at < occ.due_at and not done):
            cal.add_component(_event(
                f"{occ.uuid}-prep@scheduler",
                f"Start prep: {label}",
                occ.prep_start_at, minutes=15, description=note, url=item.url))

    return cal.to_ical()