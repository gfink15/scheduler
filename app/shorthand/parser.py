"""The shorthand entry language.

    n='Test 1' c='BIO110' d='2026-09-18 11:59pm' e='2h' p='3d' y='high'
"""
import re
from dataclasses import dataclass, field

from app.constants import ITEM_TYPES, ITEM_STATUSES, PRIORITY_BY_NAME, DEFAULT_PRIORITY
from app.shorthand import values
from app.shorthand.recurrence import parse_recurrence, Recurrence

FIELD_RE = re.compile(r"([a-z])\s*=\s*'((?:[^'\\]|\\.)*)'")
UNESCAPE_RE = re.compile(r"\\(.)")

FIELD_NAMES = {
    "m": "mode", "n": "name", "c": "course", "d": "due", "e": "estimate",
    "p": "prep", "r": "recurrence", "b": "recur_begin", "z": "recur_end",
    "a": "available", "y": "priority", "x": "description", "t": "tags",
    "s": "status", "u": "url", "k": "chunk", "w": "weight", "l": "label",
}


class ShorthandError(Exception):
    def __init__(self, message: str, errors: list[str] | None = None):
        super().__init__(message)
        self.errors = errors or [message]


@dataclass
class ParsedEntry:
    item_type: str = "assignment"
    name: str | None = None
    course: str | None = None
    description: str | None = None
    status: str = "planned"
    priority: int = DEFAULT_PRIORITY

    due_at = None
    due_date_only: bool = False
    available_at = None

    estimated_minutes: int | None = None
    prep_minutes: int | None = None
    chunk_minutes: int | None = None
    weight_value: float | None = None

    url: str | None = None
    label: str | None = None
    tags: list[str] = field(default_factory=list)

    recurrence: Recurrence | None = None
    recurrence_start_at = None
    recurrence_end_at = None

    raw_input: str = ""
    warnings: list[str] = field(default_factory=list)

    def summary(self) -> str:
        bits = [f"{self.item_type}", self.name or "?"]
        if self.course:
            bits.append(f"({self.course})")
        if self.due_at:
            bits.append(f"due {self.due_at:%Y-%m-%d %H:%M}")
        if self.recurrence and self.recurrence.is_recurring:
            bits.append(f"repeats {self.recurrence.raw}")
        return " ".join(bits)


def _tokenize(raw: str) -> tuple[list[tuple[str, str]], list[str]]:
    pairs, errors, cursor = [], [], 0
    for match in FIELD_RE.finditer(raw):
        gap = raw[cursor:match.start()]
        if gap.strip():
            errors.append(f"unparsed text before position {match.start()}: {gap.strip()!r}")
        if cursor != 0 and not gap:
            errors.append(f"missing space before {match.group(1)}=... "
                          "(fields must be separated by whitespace)")
        pairs.append((match.group(1), UNESCAPE_RE.sub(r"\1", match.group(2))))
        cursor = match.end()
    trailing = raw[cursor:]
    if trailing.strip():
        errors.append(f"unparsed text at end: {trailing.strip()!r}")
    return pairs, errors


def parse(raw: str, *, default_due_time: str = "23:59", strict: bool = True) -> ParsedEntry:
    raw = (raw or "").strip()
    if not raw:
        raise ShorthandError("Empty input.")

    pairs, errors = _tokenize(raw)
    if not pairs:
        raise ShorthandError(
            "Nothing recognised. Expected fields like n='Test' c='BIO110'.", errors
        )

    fields: dict[str, str] = {}
    entry = ParsedEntry(raw_input=raw)

    for key, value in pairs:
        if key not in FIELD_NAMES:
            msg = f"unknown field {key!r}"
            (errors if strict else entry.warnings).append(msg)
            continue
        if key in fields:
            entry.warnings.append(f"duplicate field {key!r}: last value wins")
        fields[key] = value

    def take(key, fn, label):
        if key not in fields:
            return None
        try:
            return fn(fields[key])
        except ValueError as exc:
            errors.append(f"{label} ({key}=): {exc}")
            return None

    # --- scalars ------------------------------------------------------
    if "m" in fields:
        mode = fields["m"].strip().lower()
        if mode not in ITEM_TYPES:
            errors.append(f"mode must be one of {', '.join(ITEM_TYPES)}, got {mode!r}")
        else:
            entry.item_type = mode

    entry.name = fields.get("n", "").strip() or None
    entry.course = (fields.get("c", "").strip() or None)
    entry.description = fields.get("x")
    entry.url = fields.get("u", "").strip() or None
    entry.label = fields.get("l", "").strip() or None

    if "y" in fields:
        p = fields["y"].strip().lower()
        if p not in PRIORITY_BY_NAME:
            errors.append(f"priority must be low|medium|high|urgent, got {p!r}")
        else:
            entry.priority = PRIORITY_BY_NAME[p]

    if "s" in fields:
        st = fields["s"].strip().lower()
        if st not in ITEM_STATUSES:
            errors.append(f"status must be one of {', '.join(ITEM_STATUSES)}, got {st!r}")
        else:
            entry.status = st

    if "t" in fields:
        entry.tags = values.parse_tags(fields["t"])

    if "w" in fields:
        try:
            entry.weight_value = float(fields["w"])
        except ValueError:
            errors.append(f"weight must be numeric, got {fields['w']!r}")

    # --- durations ----------------------------------------------------
    entry.estimated_minutes = take("e", values.parse_duration, "bad estimate")
    entry.prep_minutes = take("p", values.parse_duration, "bad prep window")
    entry.chunk_minutes = take("k", values.parse_duration, "bad chunk size")

    # --- datetimes ----------------------------------------------------
    if "d" in fields:
        try:
            entry.due_at, entry.due_date_only = values.parse_datetime(
                fields["d"], default_time=default_due_time)
        except ValueError as exc:
            errors.append(f"bad due date (d=): {exc}")

    for key, attr, dflt in (("a", "available_at", "00:00"),
                            ("b", "recurrence_start_at", "00:00"),
                            ("z", "recurrence_end_at", "23:59")):
        if key in fields:
            try:
                dt, _ = values.parse_datetime(fields[key], default_time=dflt)
                setattr(entry, attr, dt)
            except ValueError as exc:
                errors.append(f"bad date ({key}=): {exc}")

    # --- recurrence ---------------------------------------------------
    if "r" in fields:
        try:
            entry.recurrence = parse_recurrence(fields["r"], default_time=default_due_time)
        except ValueError as exc:
            errors.append(f"bad recurrence (r=): {exc}")

    errors.extend(_validate(entry))
    if errors:
        raise ShorthandError("; ".join(errors), errors)
    return entry


def _validate(e: ParsedEntry) -> list[str]:
    errs = []
    if not e.name:
        errs.append("n= (name) is required")

    recurring = e.recurrence is not None and e.recurrence.is_recurring

    if e.item_type == "assignment":
        if not e.course:
            errs.append("c= (course) is required for assignments")
        if not e.due_at and not recurring:
            errs.append("assignments need either d= (due date) or r= (recurrence)")
    elif e.item_type == "habit":
        if not e.course:
            errs.append("c= (course) is required for habits")
        if not recurring:
            errs.append("habits need r= (recurrence)")
    elif e.item_type == "event":
        if not e.due_at and not recurring:
            errs.append("events need either d= or r=")

    if e.recurrence_start_at and e.recurrence_end_at and \
            e.recurrence_start_at > e.recurrence_end_at:
        errs.append("b= (recurrence begin) must be on or before z= (recurrence end)")
    if e.available_at and e.due_at and e.available_at > e.due_at:
        errs.append("a= (available) must be on or before d= (due)")
    return errs