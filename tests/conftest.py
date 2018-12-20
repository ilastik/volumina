import pytest

from PyQt5.QtWidgets import QApplication, QPushButton


@pytest.fixture(scope='class')
def qtapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    yield app

    del app
