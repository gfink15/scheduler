import uuid
from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db, login_manager


def _uuid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), unique=True, nullable=False, default=_uuid)

    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(120))

    timezone = db.Column(db.String(64), nullable=False, default="America/New_York")

    is_active_flag = db.Column("is_active", db.Boolean, nullable=False, default=True)
    is_admin = db.Column(db.Boolean, nullable=False, default=False)

    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False,
                           default=utcnow, onupdate=utcnow)

    items = db.relationship("Item", back_populates="user",
                            cascade="all, delete-orphan", lazy="dynamic")
    settings = db.relationship("UserSettings", back_populates="user",
                               uselist=False, cascade="all, delete-orphan")
    integrations = db.relationship("UserIntegration", back_populates="user",
                                   uselist=False, cascade="all, delete-orphan")

    # --- auth helpers -------------------------------------------------
    def set_password(self, raw: str) -> None:
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw: str) -> bool:
        return check_password_hash(self.password_hash, raw)

    @property
    def is_active(self) -> bool:          # Flask-Login contract
        return self.is_active_flag

    def __repr__(self) -> str:
        return f"<User {self.username}>"


class UserSettings(db.Model):
    __tablename__ = "user_settings"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"),
                        nullable=False, unique=True)

    timezone = db.Column(db.String(64), nullable=False, default="America/New_York")
    default_due_time = db.Column(db.String(5), nullable=False, default="23:59")
    default_digest_time = db.Column(db.String(5), nullable=False, default="07:00")
    default_assignment_prep_minutes = db.Column(db.Integer, default=0)
    default_chunk_minutes = db.Column(db.Integer, default=30)
    workday_start_time = db.Column(db.String(5), default="09:00")
    workday_end_time = db.Column(db.String(5), default="22:00")
    upcoming_lookahead_days = db.Column(db.Integer, default=7)

    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False,
                           default=utcnow, onupdate=utcnow)

    user = db.relationship("User", back_populates="settings")


class UserIntegration(db.Model):
    """Secrets live here, separate from ordinary preferences."""
    __tablename__ = "user_integrations"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"),
                        nullable=False, unique=True)

    matrix_homeserver = db.Column(db.String(255))
    matrix_user_id = db.Column(db.String(255))
    matrix_room_id = db.Column(db.String(255))
    matrix_access_token = db.Column(db.Text)
    digest_enabled = db.Column(db.Boolean, nullable=False, default=False)

    moodle_ics_url = db.Column(db.Text)
    moodle_import_enabled = db.Column(db.Boolean, nullable=False, default=False)
    moodle_last_sync_at = db.Column(db.DateTime(timezone=True))

    apple_feed_token = db.Column(db.String(64), unique=True, index=True)

    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False,
                           default=utcnow, onupdate=utcnow)

    user = db.relationship("User", back_populates="integrations")


@login_manager.user_loader
def load_user(user_id: str):
    return db.session.get(User, int(user_id))