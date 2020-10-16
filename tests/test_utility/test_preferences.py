import pickle

import pytest
from volumina.utility.preferences import Preferences


@pytest.fixture
def preferences(tmp_path):
    return Preferences(tmp_path / "preferences.json")


def test_get_default(preferences):
    assert preferences.get("spam", "eggs", 42) == 42


def test_set_get(preferences):
    preferences.set("spam", "eggs", 42)
    assert preferences.get("spam", "eggs") == 42


def test_setmany_getmany(preferences):
    preferences.setmany(("spam", "eggs1", 42), ("spam", "eggs2", "python"), ("ham", "eggs3", "antigravity"))
    assert preferences.getmany(("spam", "eggs1", None), ("ham", "eggs3", None)) == (42, "antigravity")


def test_set_path(tmp_path, preferences):
    preferences.set("spam", "eggs", 42)

    preferences.path = tmp_path / "preferences2.json"
    assert preferences.get("spam", "eggs", 0) == 0

    preferences.path = tmp_path / "preferences.json"
    assert preferences.get("spam", "eggs", 0) == 42


def test_migrate(tmp_path, preferences):
    data = {"s1": {"k1": "spam"}, "s2": {"k2": 42, "k3": True, "k4": 0.42, "k5": None}}
    old_path = tmp_path / "old_preferences.pickle"
    old_path.write_bytes(pickle.dumps(data))

    preferences.migrate(old_path)

    assert old_path.exists()

    m = type("Missing", (), {"__repr__": lambda _self: "<missing>"})()
    keys = ("s1", "k1", m), ("s2", "k2", m), ("s2", "k3", m), ("s2", "k4", m), ("s2", "k5", m)
    assert preferences.getmany(*keys) == ("spam", 42, True, 0.42, None)


def test_migrate_invalid_data(tmp_path, preferences):
    old_path = tmp_path / "old_preferences.pickle"
    old_path.write_bytes(pickle.dumps(object()))

    preferences.migrate(old_path)

    assert old_path.exists()
    assert not preferences.read()


def test_migrate_shortcuts(tmp_path, preferences):
    data = {"Shortcut Preferences v2": {"all_shortcuts": {("Ilastik Shell", "shell next image"): "PgDown"}}}

    old_path = tmp_path / "old_preferences.pickle"
    with open(old_path, "wb") as f:
        pickle.dump(data, f)

    preferences.migrate(old_path)

    shortcuts = [{"group": "Ilastik Shell", "name": "shell next image", "keyseq": "PgDown"}]
    assert preferences.get("Shortcut Preferences v2", "all_shortcuts") == shortcuts
