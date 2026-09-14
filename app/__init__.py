import click
from flask import Flask
from dotenv import load_dotenv

from app.config import get_config
from app.extensions import db, migrate, login_manager, csrf

load_dotenv()


def create_app(config_object=None):
    app = Flask(__name__)
    app.config.from_object(config_object or get_config())

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    from app import models  # noqa: F401  (register mappers)

    from app.auth.routes import bp as auth_bp
    from app.main.routes import bp as main_bp
    from app.api.routes import bp as api_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    _register_cli(app)
    _register_template_helpers(app)
    return app


def _register_template_helpers(app):
    from app.shorthand.values import format_minutes
    from app.constants import PRIORITY_BY_VALUE
    app.jinja_env.filters["minutes"] = format_minutes
    app.jinja_env.globals["priority_name"] = lambda v: PRIORITY_BY_VALUE.get(v, "medium")


def _register_cli(app):
    @app.cli.command("generate")
    @click.option("--user-id", type=int, default=None)
    def generate(user_id):
        """Roll occurrences forward for one user or everybody."""
        from app.models import User
        from app.planner.generation import generate_for_user
        ids = [user_id] if user_id else [u.id for u in User.query.all()]
        for uid in ids:
            click.echo(f"user {uid}: {generate_for_user(uid)} occurrences written")

    @app.cli.command("create-user")
    @click.argument("username")
    @click.argument("email")
    @click.password_option()
    def create_user(username, email, password):
        from app.main.services import register_user
        user = register_user(username, email, password)
        click.echo(f"created {user.username} (id={user.id})")