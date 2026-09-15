import pytest

from app import create_app
from app.config import TestConfig
from app.extensions import db
from app.main.services import register_user


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        register_user("tester", "t@example.com", "password1234")
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    c = app.test_client()
    c.post("/auth/login", data={"username": "tester", "password": "password1234"})
    return c


def test_calendar_events_returns_json(client):
    res = client.get("/api/calendar/events")
    assert res.status_code == 200
    assert res.is_json
    assert isinstance(res.get_json(), list)


def test_dashboard_renders(client):
    assert client.get("/").status_code == 200


def test_calendar_page_renders(client):
    assert client.get("/calendar").status_code == 200


def test_items_page_renders(client):
    assert client.get("/items").status_code == 200


def test_unauthenticated_is_redirected():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        res = app.test_client().get("/api/calendar/events")
        assert res.status_code in (302, 401)
        db.drop_all()