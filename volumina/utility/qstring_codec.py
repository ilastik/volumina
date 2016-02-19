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
import sys
from PyQt4.QtCore import QString

def encode_from_qstring(qstr, encoding=sys.getfilesystemencoding()):
    """
    Convert the given QString into a Python str.
    If no encoding is provided, use the same encoding as the filesystem.
    """
    assert isinstance(qstr, QString)
    return unicode(qstr).encode( encoding )

def decode_to_qstring(s, encoding=sys.getfilesystemencoding()):
    """
    Convert the given Python str into a QString.
    If not encoding is specified, use the same encoding as the filesystem.
    """
    # pyqt converts unicode to QString correctly.
    assert isinstance(s, str) or isinstance(s, unicode)
    return QString( s.decode( encoding ) )


assert sys.version_info.major == 2, \
    "This file assumes Python 2 str/unicode semantics. "\
    "If you upgrade to Python 3,  you'll have to change it. "\
    "(Or maybe just get rid of it?)/"

