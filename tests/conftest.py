import pytest
from PyQt5.QtWidgets import QApplication, QPushButton

from volumina.utility import preferences


@pytest.fixture(scope="class")
def qtapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    yield app

    del app


@pytest.fixture(scope="session", autouse=True)
def change_preferences_path(tmp_path_factory):
    preferences.set_path(tmp_path_factory.mktemp("preferences") / "preferences.json")
