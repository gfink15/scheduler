import pytest
from app.shorthand import parse, ShorthandError


def test_basic_assignment():
    e = parse("n='Test 1' c='BIO110' d='2026-09-18 11:59pm' e='2h' p='3d' y='high'")
    assert e.item_type == "assignment"
    assert e.name == "Test 1"
    assert e.estimated_minutes == 120
    assert e.prep_minutes == 4320
    assert e.priority == 3
    assert e.due_at.hour == 23 and e.due_at.minute == 59


def test_habit_requires_recurrence():
    with pytest.raises(ShorthandError):
        parse("m='habit' n='Flashcards' c='CHEM101'")


def test_weekly_recurrence():
    e = parse("m='habit' n='Flashcards' c='CHEM101' r='weekly:MO,WE,FR@18:00' e='30m'")
    assert e.recurrence.kind == "weekly"
    assert e.recurrence.weekdays == [0, 2, 4]


def test_missing_space_is_rejected():
    with pytest.raises(ShorthandError):
        parse("n='Test'c='BIO110' d='2026-09-18'")


def test_escaped_quote():
    e = parse(r"n='Mendel\'s laws' c='BIO110' d='2026-09-18'")
    assert e.name == "Mendel's laws"