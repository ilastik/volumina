# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# Copyright 2011-2014, the ilastik developers

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

