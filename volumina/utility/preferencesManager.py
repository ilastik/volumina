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
#		   http://ilastik.org/license/
###############################################################################
import os
import threading
import warnings
import cPickle as pickle
from volumina.utility import Singleton

class PreferencesManager():
    # TODO: Maybe this should be a wrapper API around QSettings (but with pickle strings)
    #       Pros:
    #         - Settings would be stored in standard locations for each platform
    #       Cons:
    #         - QT dependency (currently there are no non-gui preferences, but maybe someday)
    
    __metaclass__ = Singleton

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

    def __init__(self):
        self._filePath = os.path.expanduser('~/.ilastik_preferences')
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
                    with open(self._filePath, 'rb') as f:
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
                with open(self._filePath, 'wb') as f:
                    pickle.dump(self._prefs, f)
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
            return PreferencesManager().get( self._group, self._setting, default )
        
        def set(self, value):
            PreferencesManager().set( self._group, self._setting, value )
        

if __name__ == "__main__":
    prefsMgr = PreferencesManager()
    prefsMgr2 = PreferencesManager()
    assert id(prefsMgr) == id(prefsMgr2), "It's supposed to be a singleton!"
    
    with PreferencesManager() as prefsMgr:
        prefsMgr.set("Group 1", "Setting1", [1,2,3])
        prefsMgr.set("Group 1", "Setting2", ['a', 'b', 'c'])
        
        prefsMgr.set("Group 2", "Setting1", "Forty-two")
    
    # Force a new instance
    PreferencesManager.instance = None
    prefsMgr = PreferencesManager()
    assert prefsMgr != prefsMgr2, "For this test, I want a separate instance"
    
    assert prefsMgr.get("Group 1", "Setting1") == [1,2,3]
    assert prefsMgr.get("Group 1", "Setting2") == ['a', 'b', 'c']
    
    assert prefsMgr.get("Group 2", "Setting1") == "Forty-two"

