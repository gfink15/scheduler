import uuid

from app.constants import ITEM_TYPES, ITEM_STATUSES, SOURCE_TYPES, DEFAULT_PRIORITY
from app.extensions import db
from app.models.user import utcnow


class Item(db.Model):
    """Master record: a one-off assignment, a recurring template, or an event."""
    __tablename__ = "items"

    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), unique=True, nullable=False,
                     default=lambda: str(uuid.uuid4()))

    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"),
                        nullable=False, index=True)

    item_type = db.Column(db.String(16), nullable=False, default="assignment")
    name = db.Column(db.String(255), nullable=False)
    course = db.Column(db.String(64), index=True)
    description = db.Column(db.Text)

    status = db.Column(db.String(16), nullable=False, default="planned")
    priority = db.Column(db.Integer, nullable=False, default=DEFAULT_PRIORITY)

    due_at = db.Column(db.DateTime(timezone=True))
    available_at = db.Column(db.DateTime(timezone=True))

    estimated_minutes = db.Column(db.Integer)
    prep_minutes = db.Column(db.Integer)
    chunk_minutes = db.Column(db.Integer)
    weight_value = db.Column(db.Float)

    url = db.Column(db.Text)
    label = db.Column(db.String(64))

    source_type = db.Column(db.String(16), nullable=False, default="manual")
    source_ref = db.Column(db.String(255))

    recurrence_raw = db.Column(db.String(255))
    recurrence_kind = db.Column(db.String(16))
    recurrence_start_at = db.Column(db.DateTime(timezone=True))
    recurrence_end_at = db.Column(db.DateTime(timezone=True))
    last_generated_at = db.Column(db.DateTime(timezone=True))

    timezone = db.Column(db.String(64), nullable=False, default="America/New_York")
    raw_input = db.Column(db.Text)  # the original shorthand string, for editing/audit

    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False,
                           default=utcnow, onupdate=utcnow)
    archived_at = db.Column(db.DateTime(timezone=True))

    user = db.relationship("User", back_populates="items")
    tags = db.relationship("ItemTag", back_populates="item",
                           cascade="all, delete-orphan", lazy="selectin")
    occurrences = db.relationship("Occurrence", back_populates="item",
                                  cascade="all, delete-orphan", lazy="dynamic")

    __table_args__ = (
        db.CheckConstraint(f"item_type IN {ITEM_TYPES}", name="ck_items_type"),
        db.CheckConstraint(f"status IN {ITEM_STATUSES}", name="ck_items_status"),
        db.CheckConstraint(f"source_type IN {SOURCE_TYPES}", name="ck_items_source"),
        db.Index("ix_items_user_type", "user_id", "item_type"),
    )

    @property
    def is_recurring(self) -> bool:
        return bool(self.recurrence_kind) and self.recurrence_kind != "none"

    @property
    def tag_list(self) -> list[str]:
        return [t.tag for t in self.tags]

    def __repr__(self) -> str:
        return f"<Item {self.course}/{self.name}>"


class ItemTag(db.Model):
    __tablename__ = "item_tags"

    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey("items.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    tag = db.Column(db.String(64), nullable=False, index=True)

    item = db.relationship("Item", back_populates="tags")

    __table_args__ = (db.UniqueConstraint("item_id", "tag", name="uq_item_tag"),)