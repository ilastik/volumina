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

import logging
import os
import pathlib
import pickle
import threading
from typing import Any, Tuple, MutableMapping

logger = logging.getLogger(__name__)


class _Preferences:
    def __init__(self, path: pathlib.Path):
        self._path = path
        self._data = _load_preferences(path)
        self._lock = threading.Lock()

    def get(self, group: str, setting: str, default: Any = None) -> Any:
        return self.getmany((group, setting, default))[0]

    def set(self, group: str, setting: str, value: Any) -> None:
        self.setmany((group, setting, value))

    def getmany(self, *args: Tuple[str, str, Any]) -> Tuple[Any, ...]:
        with self._lock:
            result = []
            for group, setting, default in args:
                try:
                    result.append(self._data[group][setting])
                except KeyError:
                    result.append(default)
            return tuple(result)

    def setmany(self, *args: Tuple[str, str, Any]) -> None:
        with self._lock:
            for group, setting, value in args:
                self._data.setdefault(group, {})[setting] = value
            try:
                with open(self._path, "wb") as f:
                    # Use the lowest available protocol for backwards compatibility.
                    pickle.dump(self._data, f, protocol=0)
            except Exception as e:
                logger.exception(f"Failed to save preferences to {str(self._path)!r}")
                if not isinstance(e, IOError):
                    self._path.unlink()

    def get_location(self) -> pathlib.Path:
        with self._lock:
            return self._path

    def set_location(self, path: os.PathLike) -> None:
        with self._lock:
            self._path = pathlib.Path(path)
            self._data = _load_preferences(self._path)


def _load_preferences(path: pathlib.Path) -> MutableMapping[str, MutableMapping[str, Any]]:
    try:
        with open(path, "rb") as f:
            return pickle.load(f)
    except FileNotFoundError:
        return {}
    except Exception as e:
        logger.exception(f"Failed to load preferences from {str(path)!r}")
        if not isinstance(e, IOError):
            path.unlink()
        return {}


_preferences = _Preferences(pathlib.Path.home() / ".ilastik_preferences")


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


def getmany(*args: Tuple[str, str, Any]) -> Tuple[Any, ...]:
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


def get_location() -> pathlib.Path:
    """Return the current preferences file location.

    See Also:
          :func:`set_location`.
    """
    return _preferences.get_location()


def set_location(path: os.PathLike) -> None:
    """Change the preferences file location.

    Discard all existing preferences and read preferences from the new
    file. This file will be used for all subsequent preferences writes.

    See Also:
          :func:`get_location`.
    """
    _preferences.set_location(path)
