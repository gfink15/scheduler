import uuid

from app.constants import OCCURRENCE_STATUSES, DEFAULT_PRIORITY
from app.extensions import db
from app.models.user import utcnow


class Occurrence(db.Model):
    """A concrete, dated instance of an Item. This is what you actually do."""
    __tablename__ = "occurrences"

    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), unique=True, nullable=False,
                     default=lambda: str(uuid.uuid4()))

    item_id = db.Column(db.Integer, db.ForeignKey("items.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    # denormalised for cheap per-user queries
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"),
                        nullable=False, index=True)

    occurrence_date = db.Column(db.Date, nullable=False, index=True)
    start_at = db.Column(db.DateTime(timezone=True))
    due_at = db.Column(db.DateTime(timezone=True), index=True)
    prep_start_at = db.Column(db.DateTime(timezone=True))

    status = db.Column(db.String(16), nullable=False, default="planned", index=True)
    priority = db.Column(db.Integer, nullable=False, default=DEFAULT_PRIORITY)

    estimated_minutes = db.Column(db.Integer)
    remaining_minutes = db.Column(db.Integer)
    recommended_minutes = db.Column(db.Integer)
    completion_percent = db.Column(db.Integer, nullable=False, default=0)

    is_generated = db.Column(db.Boolean, nullable=False, default=False)
    generator_key = db.Column(db.String(128))
    manual_override = db.Column(db.Boolean, nullable=False, default=False)
    source_snapshot = db.Column(db.JSON)

    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False,
                           default=utcnow, onupdate=utcnow)
    completed_at = db.Column(db.DateTime(timezone=True))
    cancelled_at = db.Column(db.DateTime(timezone=True))

    item = db.relationship("Item", back_populates="occurrences")
    work_logs = db.relationship("WorkLog", back_populates="occurrence",
                                cascade="all, delete-orphan", lazy="selectin")

    __table_args__ = (
        db.CheckConstraint(f"status IN {OCCURRENCE_STATUSES}", name="ck_occ_status"),
        db.UniqueConstraint("item_id", "generator_key", name="uq_occ_generator"),
        db.Index("ix_occ_user_date", "user_id", "occurrence_date"),
    )

    @property
    def is_closed(self) -> bool:
        return self.status in ("done", "cancelled", "skipped")

    @property
    def minutes_spent(self) -> int:
        return sum(w.minutes_spent for w in self.work_logs)

    def __repr__(self) -> str:
        return f"<Occurrence {self.item_id} {self.occurrence_date}>"