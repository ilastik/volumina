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
from future import standard_library

standard_library.install_aliases()
from builtins import object
import os
import threading
import warnings
from pathlib import Path
import pickle as pickle
from future.utils import with_metaclass


class PreferencesManagerMeta(type):
    _instance_cache = {}

    def __call__(cls, path: Path = Path("~/.ilastik_preferences")):
        expanded_path = Path(path).expanduser().absolute()
        instance = cls._instance_cache.get(expanded_path, super().__call__(expanded_path))
        cls._instance_cache[expanded_path] = instance
        return instance


class PreferencesManager(metaclass=PreferencesManagerMeta):
    # TODO: Maybe this should be a wrapper API around QSettings (but with pickle strings)
    #       Pros:
    #         - Settings would be stored in standard locations for each platform
    #       Cons:
    #         - QT dependency (currently there are no non-gui preferences, but maybe someday)
    def get(self, group, setting, default=None):
        try:
            return self._prefs[group][setting]
        except KeyError:
            return default

    def set(self, group, setting, value):
        if group not in self._prefs:
            self._prefs[group] = {}
        if setting not in self._prefs[group] or self._prefs[group][setting] != value:
            self._prefs[group][setting] = value
            self._dirty = True
        if not self._poolingSave:
            self._save()

    def __init__(self, path: Path):
        self._filePath = path
        self._lock = threading.Lock()
        self._prefs = self._load()
        self._poolingSave = False
        self._dirty = False

    def _load(self):
        with self._lock:
            if not os.path.exists(self._filePath):
                return {}
            else:
                try:
                    with open(self._filePath, "rb") as f:
                        return pickle.load(f)
                except EOFError:
                    os.remove(self._filePath)
                    return {}
                except ValueError:
                    warnings.warn("Unable to load preferences from {}. Overwriting...".format(self._filePath))
                    os.remove(self._filePath)
                    return {}

    def _save(self):
        if self._dirty:
            with self._lock:
                with open(self._filePath, "wb") as f:
                    pickle.dump(self._prefs, f, 0)
                self._dirty = False

    # We support the 'with' keyword, in which case a sequence of settings can be set,
    # and the preferences file won't be updated until the __exit__ function is called.
    # (Otherwise, each call to set() triggers a new save.)

    def __enter__(self):
        self._poolingSave = True
        return self

    def __exit__(self, *args):
        self._poolingSave = False
        self._save()

    class Setting(object):
        """
        Convenience class for getting/setting for a single setting multiple times in a row.
        """

        def __init__(self, group, setting):
            self._group = group
            self._setting = setting

        def get(self, default=None):
            return PreferencesManager().get(self._group, self._setting, default)

        def set(self, value):
            PreferencesManager().set(self._group, self._setting, value)
