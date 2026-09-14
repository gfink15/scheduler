"""Coercion helpers: durations, datetimes, priorities."""
import re
from datetime import datetime, time, date

DURATION_RE = re.compile(r"^(?:(\d+)\s*([mhdw]))+$", re.IGNORECASE)
DURATION_PART_RE = re.compile(r"(\d+)\s*([mhdw])", re.IGNORECASE)

UNIT_MINUTES = {"m": 1, "h": 60, "d": 60 * 24, "w": 60 * 24 * 7}

DATETIME_FORMATS = (
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d %I:%M%p",
    "%Y-%m-%d %I%p",
    "%Y-%m-%dT%H:%M",
    "%Y-%m-%d",
)


class ValueError_(ValueError):
    """Domain-specific parse failure."""


def parse_duration(raw: str) -> int:
    """'1h30m' -> 90.  Returns minutes."""
    s = raw.strip().replace(" ", "")
    if not s or not DURATION_RE.match(s):
        raise ValueError_(f"invalid duration: {raw!r} (try '30m', '2h', '1h30m', '3d')")
    total = 0
    for amount, unit in DURATION_PART_RE.findall(s):
        total += int(amount) * UNIT_MINUTES[unit.lower()]
    if total <= 0:
        raise ValueError_(f"duration must be > 0: {raw!r}")
    return total


def parse_datetime(raw: str, *, default_time: str = "23:59") -> tuple[datetime, bool]:
    """Returns (naive local datetime, date_only_flag)."""
    s = raw.strip().replace("  ", " ")
    normalised = re.sub(r"(?i)\s*([ap])\.?m\.?$", lambda m: m.group(1).upper() + "M", s)
    for fmt in DATETIME_FORMATS:
        try:
            dt = datetime.strptime(normalised, fmt)
        except ValueError:
            continue
        date_only = fmt == "%Y-%m-%d"
        if date_only:
            hh, mm = (int(x) for x in default_time.split(":"))
            dt = datetime.combine(dt.date(), time(hh, mm))
        return dt, date_only
    raise ValueError_(
        f"invalid datetime: {raw!r} (try '2026-09-18 23:59' or '2026-09-18 11:59pm')"
    )


def parse_time_of_day(raw: str) -> time:
    hh, mm = raw.split(":")
    h, m = int(hh), int(mm)
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError_(f"invalid time of day: {raw!r}")
    return time(h, m)


def parse_tags(raw: str) -> list[str]:
    seen, out = set(), []
    for part in raw.split(","):
        tag = part.strip().lower()
        if tag and tag not in seen:
            seen.add(tag)
            out.append(tag)
    return out


def format_minutes(minutes: int | None) -> str:
    if not minutes:
        return "—"
    h, m = divmod(minutes, 60)
    if h and m:
        return f"{h}h{m}m"
    return f"{h}h" if h else f"{m}m"