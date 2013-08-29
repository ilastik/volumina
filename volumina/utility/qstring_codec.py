import sys
from PyQt4.QtCore import QString

def encode_from_qstring(qstr):
    """Convert the given QString into a Python str with the same encoding as the filesystem."""
    assert isinstance(qstr, QString)
    return unicode(qstr).encode( sys.getfilesystemencoding() )

def decode_to_qstring(s):
    """Convert the given Python str into a QString assuming the same encoding as the filesystem."""
    # pyqt converts unicode to QString correctly.
    assert isinstance(s, str)
    return QString( s.decode( sys.getfilesystemencoding() ) )


assert sys.version_info.major == 2, \
    "This file assumes Python 2 str/unicode semantics. "\
    "If you upgrade to Python 3,  you'll have to change it. "\
    "(Or maybe just get rid of it?)/"

