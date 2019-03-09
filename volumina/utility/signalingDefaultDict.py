from __future__ import print_function
from PyQt5.Qt import pyqtSignal
from PyQt5.QtCore import QObject

class SignalingDefaultDict( QObject ):
    """
    Provides a defaultdict-like interface, but emits a signal whenever the dict is updated.
    
    Note: To simplify the API, this offers only one signal, 
          which is used any time a value is updated, even for deleted items.
          When an item is deleted, the signal is emitted with the default_value.
          
    TODO: Some dict functions are not implemented yet:
          - pop()
          - popitem()
          - setdefault()
          - viewvalues()
          - __missing__()
    """
    updated = pyqtSignal(object) # set(updated_keys) 
    
    def __init__(self, parent, default_value):
        super( SignalingDefaultDict, self ).__init__(parent)
        self._dict = {}
        self.default_value = default_value
        assert not callable(default_value), "Pass a default_value, not a default_factory"
        
    def __len__(self):                 return len(self._dict)
    def __iter__(self):                return self._dict.__iter__()
    def __contains__(self, key):       return self._dict.__contains__(key)
    def viewkeys(self):                return self._dict.keys()
    def items(self):                   return list(self._dict.items())
    def iteritems(self):               return iter(self._dict.items())
    def keys(self):                    return list(self._dict.keys())
    def iterkeys(self):                return iter(self._dict.keys())
    def itervalues(self):              return iter(self._dict.values())
    def values(self):                  return list(self._dict.values())

    def __getitem__(self, key):
        try:
            return self._dict[key]
        except KeyError:
            return self.default_value

    def get(self, key, default=None):
        try:
            return self._dict[key]
        except KeyError:
            return default

    def __setitem__(self, key, value):
        if key not in self._dict or self._dict[key] != value:
            self._dict[key] = value
            self.updated.emit( set([key]) )
    
    def __delitem__(self, key):
        del self._dict[key]
        self.updated.emit( set([key]) )
    
    def update(self, *other_dict, **other_kwargs):
        """
        Update the dict with the contents of the 'other' dict.
        This will call the updated() signal several times (once per changed/added key).
        """
        if other_dict:
            assert len(other_dict) == 1
            other = other_dict[0]
        else:
            other = other_kwargs
        
        other_keys = set(other.keys())
        original_keys = set(self._dict.keys())
        
        added_keys = other_keys - original_keys
        
        common_keys = original_keys.intersection(other_keys)
        changed_keys = [key for key in common_keys if self._dict[key] != other[key]]

        self._dict.update(other)
        self.updated.emit( set(changed_keys).union(added_keys) )
    
    def clear(self):
        keys = list(self._dict.keys())
        self._dict.clear()
        self.updated.emit( set(keys) )

    def overwrite(self, other):
        """
        Replace all values in self with the values from other.
        This will call the updated() signal several times (once per changed/added/deleted key).
        """
        other_keys = set(other.keys())
        original_keys = set(self._dict.keys())
        
        added_keys = other_keys - original_keys
        
        common_keys = original_keys.intersection(other_keys)
        changed_keys = [key for key in common_keys if self._dict[key] != other[key]]
        deleted_keys = original_keys - other_keys

        self._dict = dict(other)
        self.updated.emit( set(changed_keys).union(added_keys).union(deleted_keys) )

if __name__ == "__main__":
    from PyQt5.QtCore import QCoreApplication
    app = QCoreApplication([])
    
    d = SignalingDefaultDict(None, 0)
    orig_dict = {'a' : 1, 'b' : 2, 'c' : 3}
    d.overwrite(orig_dict)

    assert set(d.keys()) == set(d.keys()) == set(d.keys()) == set('abc')
    assert set(d.values()) == set(d.values()) == set([1,2,3])
    assert set(d.items()) == set(d.items()) == set(orig_dict.items())

    assert d['a'] == 1
    assert d['z'] == 0
    assert d.get('b') == 2
    assert d.get('y') is None # This is what defaultdict does
    assert d.get('y', 100) == 100

    handled_items = []
    def f(keys):
        handled_items.extend( (k,d[k]) for k in keys )
    
    d.updated.connect(f)
    
    d['b'] = 20
    d['d'] = 4
    del d['a']
    
    assert set(handled_items) == {('b', 20), ('d', 4), ('a', 0)}, \
        "Got: {}".format( handled_items )

    handled_items = []
    d.update( {'a' : 1, 'c' : 30} )
    assert set(handled_items) == {('a', 1), ('c', 30)}, \
        "Got: {}".format( handled_items )
    
    handled_items = []
    keys = list(d.keys())
    d.clear()
    assert set(handled_items) == { (k, 0) for k in keys }
    print("DONE.")
        
