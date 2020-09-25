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
import pathlib
import threading
from typing import Any, Tuple, Union

import appdirs

logger = logging.getLogger(__name__)


class Preferences:
    def __init__(self, path: Union[str, bytes, os.PathLike]):
        self.path = path
        self._lock = threading.RLock()

    @property
    def path(self):
        return self._path

    @path.setter
    def path(self, path: Union[str, bytes, os.PathLike]):
        self._path = pathlib.Path(path)

    def get(self, group: str, setting: str, default: Any = None) -> Any:
        return self.getmany((group, setting, default))[0]

    def set(self, group: str, setting: str, value: Any) -> None:
        self.setmany((group, setting, value))

    def getmany(self, *args: Tuple[str, str, Any]) -> Tuple:
        with self._lock:
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
            with open(self.path) as f:
                return json.load(f)
        except FileNotFoundError:
            return {}

    def write(self, data):
        os.makedirs(self.path.parent, exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(data, f, indent=2, sort_keys=True)

    def migrate(self, old_path):
        if not old_path.exists():
            return

        import pickle

        try:
            with open(old_path, "rb") as f:
                old_preferences = pickle.load(f)
        except Exception:
            return

        old_path.unlink()
        self.write(old_preferences)


_preferences = Preferences(
    os.path.join(
        appdirs.user_config_dir(appname="ilastik", appauthor=False),
        "preferences.json",
    )
)


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


def get_path() -> pathlib.Path:
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


def migrate(old_path=pathlib.Path.home() / ".ilastik_preferences"):
    """Migrate from the old pickle-based preferences file format."

    Load data from the old preferences file, remove the old file
    from disk, and write the loaded data to the new JSON format.
    """
    _preferences.migrate(old_path)
