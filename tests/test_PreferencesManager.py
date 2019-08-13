import pytest
from pathlib import Path

from volumina.utility.preferencesManager import PreferencesManager


def test_same_path_returns_same_instance(tmp_path, monkeypatch):
    preferences_file_path = tmp_path / "my_preferences"
    preferences_file_path.touch()

    manager_absolute_path = PreferencesManager(preferences_file_path.absolute())

    monkeypatch.chdir(tmp_path)
    manager_relative = PreferencesManager(preferences_file_path.name)

    assert id(manager_absolute_path) == id(manager_relative)

    preferences_file_path_2 = tmp_path / "my_preferences2"
    preferences_file_path_2.touch()
    manager_absolute_path_2 = PreferencesManager(preferences_file_path_2)
    manager_relative_2 = PreferencesManager(preferences_file_path_2.name)

    assert id(manager_absolute_path_2) == id(manager_relative_2)
    assert id(manager_absolute_path) != id(manager_absolute_path_2)
    assert id(manager_relative) != id(manager_relative_2)


def test_default_preferences_writing_into_home_dir(monkeypatch, tmp_path_factory):
    monkeypatch.setenv("HOME", tmp_path_factory.mktemp("some_temp_dir").as_posix())

    prefsMgr = PreferencesManager()
    with PreferencesManager() as prefsMgr:
        prefsMgr.set("Group 1", "Setting1", [1, 2, 3])
        prefsMgr.set("Group 1", "Setting2", ["a", "b", "c"])
        prefsMgr.set("Group 2", "Setting1", "Forty-two")

    prefsMgr2 = PreferencesManager()
    assert id(prefsMgr) == id(prefsMgr2), "It's supposed to be a singleton!"

    assert prefsMgr2.get("Group 1", "Setting1") == [1, 2, 3]
    assert prefsMgr2.get("Group 1", "Setting2") == ["a", "b", "c"]
    assert prefsMgr2.get("Group 2", "Setting1") == "Forty-two"
