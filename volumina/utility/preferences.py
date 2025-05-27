###############################################################################
#   volumina: volume slicing and editing library
#
#       Copyright (C) 2011-2014, the ilastik developers
#                                <team@ilastik.org>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the Lesser GNU General Public License
# as published by the Free Software Foundation; either version 2.1
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# See the files LICENSE.lgpl2 and LICENSE.lgpl3 for full text of the
# GNU Lesser General Public License version 2.1 and 3 respectively.
# This information is also available on the ilastik web site at:
# 		   http://ilastik.org/license/
###############################################################################

"""Application-wide persistent preferences.

All public functions in this module are thread-safe.
"""

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any, Tuple, Union

import platformdirs

logger = logging.getLogger(__name__)


class Preferences:
    def __init__(self, path: Union[str, bytes, os.PathLike]):
        self._path = Path(path)
        self._lock = threading.RLock()

    @property
    def path(self) -> Path:
        with self._lock:
            return self._path

    @path.setter
    def path(self, path: Union[str, bytes, os.PathLike]):
        with self._lock:
            self._path = Path(path)

    def get(self, group: str, setting: str, default: Any = None) -> Any:
        return self.getmany((group, setting, default))[0]

    def set(self, group: str, setting: str, value: Any) -> None:
        self.setmany((group, setting, value))

    def getmany(self, *args: Tuple[str, str, Any]) -> Tuple:
        data = self.read()
        result = []
        for group, setting, default in args:
            try:
                result.append(data[group][setting])
            except KeyError:
                result.append(default)
        return tuple(result)

    def setmany(self, *args: Tuple[str, str, Any]) -> None:
        with self._lock:
            data = self.read()
            for group, setting, value in args:
                data.setdefault(group, {})[setting] = value
            self.write(data)

    def read(self):
        try:
            with self._lock:
                text = self.path.read_text()
            return json.loads(text)
        except FileNotFoundError:
            return {}
        except Exception:
            logger.exception("Failed to read preferences from %s", self.path)
            return {}

    def write(self, data) -> bool:
        try:
            text = json.dumps(data, indent=2, sort_keys=True)
            with self._lock:
                os.makedirs(self.path.parent, exist_ok=True)
                self.path.write_text(text)
            return True
        except Exception:
            logger.exception("Failed to write preferences to %s", self.path)
            return False

    def migrate(self, old_path: Path) -> None:
        if self.path.exists() or not old_path.exists():
            return

        import pickle
        from volumina.utility import ShortcutManager as SM

        try:
            old_preferences = pickle.loads(old_path.read_bytes())
            # Old pickled preferences saved shortcuts as a dict
            # with tuple keys, but JSON can only have string keys,
            # so transform the old dict into the new format.
            reversemap = old_preferences.get(SM.PreferencesGroup, {}).get(SM.PreferencesSetting, {})
            if reversemap:
                old_preferences.setdefault(SM.PreferencesGroup, {})[SM.PreferencesSetting] = [
                    {"group": group, "name": name, "keyseq": keyseq} for (group, name), keyseq in reversemap.items()
                ]
        except Exception:
            logger.exception("Failed to read old preferences")
            return

        self.write(old_preferences)


_preferences = Preferences(Path(platformdirs.user_config_dir(appname="ilastik", appauthor=False)) / "preferences.json")


def get(group: str, setting: str, default: Any = None) -> Any:
    """Return a preference setting in the specified group.

    If there is no such group, or there is no such setting in the
    existing group, the default value is returned.

    See Also:
        :func:`getmany`.
    """
    return _preferences.get(group, setting, default)


def set(group: str, setting: str, value: Any) -> None:
    """Set a preference setting in the specified group.

    If the group or the setting in a group does not exist, it will be
    created.

    See Also:
        :func:`setmany`.
    """
    return _preferences.set(group, setting, value)


def getmany(*args: Tuple[str, str, Any]) -> Tuple:
    """Return multiple preference settings in a single transaction.

    See Also:
        :func:`get`.
    """
    return _preferences.getmany(*args)


def setmany(*args: Tuple[str, str, Any]) -> None:
    """Set multiple preference settings in a single transaction.

    See Also:
        :func:`set`.
    """
    return _preferences.setmany(*args)


def get_path() -> Path:
    """Return path to the preferences file.

    See Also:
        :func:`set_path`.
    """
    return _preferences.path


def set_path(path: Union[str, bytes, os.PathLike]) -> None:
    """Assign a new path to the preferences file.

    The old file will be kept intact.

    See Also:
        :func:`get_path`.
    """
    _preferences.path = path


def migrate(old_path=Path.home() / ".ilastik_preferences"):
    """Migrate from the old pickle-based preferences file format."

    Load data from the old preferences file, remove the old file
    from disk, and write the loaded data to the new JSON format.
    """
    _preferences.migrate(old_path)
