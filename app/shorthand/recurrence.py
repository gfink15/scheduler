"""Recurrence grammar:

    none
    daily@HH:MM
    weekday@HH:MM
    weekly:MO,WE,FR@HH:MM
    monthly:15@HH:MM
    yearly:09-01@HH:MM
    cron:<5-field expression>
"""
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, time

from croniter import croniter, CroniterBadCronError

from app.constants import WEEKDAY_TOKENS
from app.shorthand.values import parse_time_of_day, ValueError_

TIME_SUFFIX_RE = re.compile(r"^(?P<body>[^@]*)(?:@(?P<time>\d{1,2}:\d{2}))?$")


@dataclass
class Recurrence:
    kind: str                       # none | daily | weekday | weekly | monthly | yearly | cron
    raw: str
    at: time | None = None
    weekdays: list[int] = field(default_factory=list)   # 0=Mon
    day_of_month: int | None = None
    month_day: tuple[int, int] | None = None            # (month, day) for yearly
    cron_expr: str | None = None

    @property
    def is_recurring(self) -> bool:
        return self.kind != "none"


def parse_recurrence(raw: str, *, default_time: str = "23:59") -> Recurrence:
    s = raw.strip()
    if not s or s.lower() == "none":
        return Recurrence(kind="none", raw="none")

    if s.lower().startswith("cron:"):
        expr = s[5:].strip()
        if not croniter.is_valid(expr):
            raise ValueError_(f"invalid cron expression: {expr!r}")
        return Recurrence(kind="cron", raw=s, cron_expr=expr)

    m = TIME_SUFFIX_RE.match(s)
    if not m:
        raise ValueError_(f"invalid recurrence: {raw!r}")
    body = m.group("body").strip()
    at = parse_time_of_day(m.group("time") or default_time)

    head, _, arg = body.partition(":")
    head = head.strip().lower()
    arg = arg.strip()

    if head == "daily":
        return Recurrence(kind="daily", raw=s, at=at)

    if head in ("weekday", "weekdays"):
        return Recurrence(kind="weekday", raw=s, at=at, weekdays=[0, 1, 2, 3, 4])

    if head == "weekly":
        if not arg:
            raise ValueError_("weekly recurrence needs days, e.g. weekly:MO,WE@18:00")
        days = []
        for token in arg.split(","):
            key = token.strip().upper()
            if key not in WEEKDAY_TOKENS:
                raise ValueError_(f"unknown weekday {token!r} (use MO TU WE TH FR SA SU)")
            days.append(WEEKDAY_TOKENS[key])
        return Recurrence(kind="weekly", raw=s, at=at, weekdays=sorted(set(days)))

    if head == "monthly":
        if not arg.isdigit() or not 1 <= int(arg) <= 31:
            raise ValueError_("monthly recurrence needs a day 1-31, e.g. monthly:1@09:00")
        return Recurrence(kind="monthly", raw=s, at=at, day_of_month=int(arg))

    if head == "yearly":
        parts = arg.split("-")
        if len(parts) != 2 or not all(p.isdigit() for p in parts):
            raise ValueError_("yearly recurrence needs MM-DD, e.g. yearly:09-01@00:00")
        return Recurrence(kind="yearly", raw=s, at=at,
                          month_day=(int(parts[0]), int(parts[1])))

    raise ValueError_(f"unknown recurrence kind: {head!r}")


def expand(rec: Recurrence, start: datetime, end: datetime) -> list[datetime]:
    """All naive-local occurrence datetimes in [start, end]. DST-safe because we
    work in local wall-clock time and convert to UTC only at storage time."""
    if not rec.is_recurring or start > end:
        return []

    if rec.kind == "cron":
        out, it = [], croniter(rec.cron_expr, start - timedelta(minutes=1))
        while True:
            nxt = it.get_next(datetime)
            if nxt > end:
                break
            out.append(nxt)
            if len(out) > 5000:            # safety valve
                break
        return out

    out, cursor = [], start.date()
    end_date = end.date()
    while cursor <= end_date:
        hit = (
            rec.kind == "daily"
            or (rec.kind in ("weekday", "weekly") and cursor.weekday() in rec.weekdays)
            or (rec.kind == "monthly" and cursor.day == rec.day_of_month)
            or (rec.kind == "yearly" and (cursor.month, cursor.day) == rec.month_day)
        )
        if hit:
            dt = datetime.combine(cursor, rec.at)
            if start <= dt <= end:
                out.append(dt)
        cursor += timedelta(days=1)
    return out