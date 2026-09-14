from flask import Blueprint, jsonify
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Occurrence
from app.models.user import utcnow

bp = Blueprint("api", __name__)


@bp.post("/occurrences/<uuid>/done")
@login_required
def mark_done(uuid):
    occ = Occurrence.query.filter_by(uuid=uuid, user_id=current_user.id).first_or_404()
    occ.status = "done"
    occ.completed_at = utcnow()
    occ.completion_percent = 100
    occ.remaining_minutes = 0
    db.session.commit()
    return jsonify({"ok": True, "uuid": uuid, "status": occ.status})


@bp.post("/occurrences/<uuid>/skip")
@login_required
def mark_skipped(uuid):
    occ = Occurrence.query.filter_by(uuid=uuid, user_id=current_user.id).first_or_404()
    occ.status = "skipped"
    db.session.commit()
    return jsonify({"ok": True, "uuid": uuid, "status": occ.status})