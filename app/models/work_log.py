from app.extensions import db
from app.models.user import utcnow


class WorkLog(db.Model):
    __tablename__ = "work_logs"

    id = db.Column(db.Integer, primary_key=True)
    occurrence_id = db.Column(db.Integer,
                              db.ForeignKey("occurrences.id", ondelete="CASCADE"),
                              nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"),
                        nullable=False, index=True)

    started_at = db.Column(db.DateTime(timezone=True))
    ended_at = db.Column(db.DateTime(timezone=True))
    minutes_spent = db.Column(db.Integer, nullable=False, default=0)
    note = db.Column(db.Text)

    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    occurrence = db.relationship("Occurrence", back_populates="work_logs")