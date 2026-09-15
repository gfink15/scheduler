import secrets
from datetime import timedelta
from zoneinfo import ZoneInfo

from app.extensions import db
from app.models import User, UserSettings, UserIntegration, Item, ItemTag, Occurrence
from app.planner.generation import generate_for_item
from app.shorthand import parse


def register_user(username, email, password, *, display_name=None,
                  tzname="America/New_York") -> User:
    user = User(username=username, email=email,
                display_name=display_name or username, timezone=tzname)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    db.session.add(UserSettings(user_id=user.id, timezone=tzname))
    db.session.add(UserIntegration(user_id=user.id,
                                   apple_feed_token=secrets.token_urlsafe(32)))
    db.session.commit()
    return user


def _localize(naive, tzname):
    """Naive local wall-clock -> aware UTC."""
    if naive is None:
        return None
    return naive.replace(tzinfo=ZoneInfo(tzname)).astimezone(ZoneInfo("UTC"))


def create_item_from_shorthand(user: User, raw: str) -> Item:
    """Parse shorthand, persist the Item + tags, and generate its occurrences."""
    settings = user.settings
    tzname = (settings.timezone if settings else user.timezone)
    default_due = settings.default_due_time if settings else "23:59"

    entry = parse(raw, default_due_time=default_due)

    item = Item(
        user_id=user.id,
        item_type=entry.item_type,
        name=entry.name,
        course=entry.course,
        description=entry.description,
        status=entry.status,
        priority=entry.priority,
        due_at=_localize(entry.due_at, tzname),
        available_at=_localize(entry.available_at, tzname),
        estimated_minutes=entry.estimated_minutes,
        prep_minutes=entry.prep_minutes,
        chunk_minutes=entry.chunk_minutes,
        weight_value=entry.weight_value,
        url=entry.url,
        label=entry.label,
        source_type="manual",
        recurrence_raw=entry.recurrence.raw if entry.recurrence else None,
        recurrence_kind=entry.recurrence.kind if entry.recurrence else None,
        recurrence_start_at=_localize(entry.recurrence_start_at, tzname),
        recurrence_end_at=_localize(entry.recurrence_end_at, tzname),
        timezone=tzname,
        raw_input=entry.raw_input,
    )
    db.session.add(item)
    db.session.flush()

    for tag in entry.tags:
        db.session.add(ItemTag(item_id=item.id, tag=tag))

    generate_for_item(item)
    db.session.commit()
    return item

def update_item_from_shorthand(user: User, item: Item, raw: str) -> Item:
    """Apply shorthand to an existing item. Only supplied fields change."""
    from app.shorthand.parser import _tokenize
    settings = user.settings
    tzname = settings.timezone if settings else user.timezone
    default_due = settings.default_due_time if settings else "23:59"

    entry = parse(raw, default_due_time=default_due)
    supplied = {k for k, _ in _tokenize(raw)[0]}

    field_map = {
        "n": ("name", entry.name),
        "c": ("course", entry.course),
        "x": ("description", entry.description),
        "y": ("priority", entry.priority),
        "s": ("status", entry.status),
        "u": ("url", entry.url),
        "l": ("label", entry.label),
        "e": ("estimated_minutes", entry.estimated_minutes),
        "p": ("prep_minutes", entry.prep_minutes),
        "k": ("chunk_minutes", entry.chunk_minutes),
        "w": ("weight_value", entry.weight_value),
        "d": ("due_at", _localize(entry.due_at, tzname)),
        "a": ("available_at", _localize(entry.available_at, tzname)),
        "b": ("recurrence_start_at", _localize(entry.recurrence_start_at, tzname)),
        "z": ("recurrence_end_at", _localize(entry.recurrence_end_at, tzname)),
    }
    for key, (attr, value) in field_map.items():
        if key in supplied:
            setattr(item, attr, value)

    if "r" in supplied and entry.recurrence:
        item.recurrence_raw = entry.recurrence.raw
        item.recurrence_kind = entry.recurrence.kind
        # recurrence changed: drop open generated occurrences and rebuild
        item.occurrences.filter(
            Occurrence.is_generated.is_(True),
            Occurrence.status.in_(("planned", "active")),
            Occurrence.manual_override.is_(False),
        ).delete(synchronize_session=False)

    if "t" in supplied:
        ItemTag.query.filter_by(item_id=item.id).delete()
        for tag in entry.tags:
            db.session.add(ItemTag(item_id=item.id, tag=tag))

    generate_for_item(item)
    db.session.commit()
    return item