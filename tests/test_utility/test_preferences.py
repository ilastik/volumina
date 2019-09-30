import pytest
from volumina.utility.preferences import _Preferences


@pytest.fixture
def preferences(tmp_path):
    return _Preferences(tmp_path / "preferences")


def test_get_default(preferences):
    assert preferences.get("spam", "eggs", 42) == 42


def test_set_get(preferences):
    preferences.set("spam", "eggs", 42)
    assert preferences.get("spam", "eggs") == 42


def test_setmany_getmany(preferences):
    preferences.setmany(("spam", "eggs1", 42), ("spam", "eggs2", "python"), ("ham", "eggs3", "antigravity"))
    assert preferences.getmany(("spam", "eggs1", None), ("ham", "eggs3", None)) == (42, "antigravity")


def test_set_location(tmp_path, preferences):
    preferences.set("spam", "eggs", 42)
    preferences.set_location(tmp_path / "preferences2")
    assert preferences.get("spam", "eggs", 42) == 42
