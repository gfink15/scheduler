"""Shared vocabulary for the whole app. Keep DB CHECK constraints in sync."""

ITEM_TYPES = ("assignment", "habit", "event")
ITEM_STATUSES = ("planned", "active", "done", "cancelled", "archived")
OCCURRENCE_STATUSES = ("planned", "active", "done", "cancelled", "skipped")
SOURCE_TYPES = ("manual", "moodle", "imported", "system")

PRIORITY_BY_NAME = {"low": 1, "medium": 2, "high": 3, "urgent": 4}
PRIORITY_BY_VALUE = {v: k for k, v in PRIORITY_BY_NAME.items()}
DEFAULT_PRIORITY = 2

# Computed (not stored) states used by the dashboard + digest
COMPUTED_STATES = (
    "upcoming", "active", "due_today", "overdue", "done", "cancelled", "skipped",
)

WEEKDAY_TOKENS = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}