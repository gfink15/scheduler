import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


class BaseConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "postgresql+psycopg://localhost/assignments_dev"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    DEFAULT_TIMEZONE = os.environ.get("DEFAULT_TIMEZONE", "America/New_York")

    # Planner defaults
    GENERATION_BACKFILL_DAYS = 7
    GENERATION_HORIZON_DAYS = 60
    DEFAULT_DUE_TIME = "23:59"
    DEFAULT_CHUNK_MINUTES = 30
    MAX_DAILY_ITEM_MINUTES = 120
    MAX_DAILY_ITEM_MINUTES_URGENT = 240
    UPCOMING_LOOKAHEAD_DAYS = 7

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"


class DevConfig(BaseConfig):
    DEBUG = True
    TEMPLATES_AUTO_RELOAD = True


class ProdConfig(BaseConfig):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    PREFERRED_URL_SCHEME = "https"


class TestConfig(BaseConfig):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "TEST_DATABASE_URL", "sqlite+pysqlite:///:memory:"
    )


CONFIGS = {"dev": DevConfig, "prod": ProdConfig, "test": TestConfig}


def get_config():
    return CONFIGS[os.environ.get("APP_ENV", "dev")]