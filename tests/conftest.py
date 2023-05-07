import pytest

from volumina.utility import preferences


@pytest.fixture(scope="session", autouse=True)
def change_preferences_path(tmp_path_factory):
    preferences.set_path(tmp_path_factory.mktemp("preferences") / "preferences.json")
