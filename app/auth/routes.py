from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user

from app.auth.forms import LoginForm, RegisterForm
from app.models import User
from app.main.services import register_user

bp = Blueprint("auth", __name__, url_prefix="/auth")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data.strip()).first()
        if user and user.check_password(form.password.data) and user.is_active:
            login_user(user, remember=form.remember.data)
            nxt = request.args.get("next")
            return redirect(nxt if nxt and nxt.startswith("/") else url_for("main.dashboard"))
        flash("Invalid username or password.", "error")
    return render_template("auth/login.html", form=form)


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter_by(username=form.username.data.strip()).first():
            flash("That username is taken.", "error")
        elif User.query.filter_by(email=form.email.data.strip().lower()).first():
            flash("That email is already registered.", "error")
        else:
            user = register_user(
                form.username.data.strip(), form.email.data.strip().lower(),
                form.password.data, display_name=form.display_name.data.strip() or None,
                tzname=form.timezone.data)
            login_user(user)
            return redirect(url_for("main.dashboard"))
    return render_template("auth/register.html", form=form)


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))