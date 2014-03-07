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

NO3D = False
import api

verboseRequests = False

import colorama
colorama.init()

import threading
printLock = threading.Lock()

# volumina.icons_rc is needed on some machines for the icons to be displayed correctly
import volumina.icons_rc

def strSlicing(slicing):
    str = "("
    for i,s in enumerate(slicing):
        str += "%d:%d" % (s.start, s.stop)
        if i != len(slicing)-1:
            str += ","
    str += ")"
    return str

def strQRect(qrect):
    return "(x=%d,y=%d,w=%d,h=%d)" % (qrect.x(),qrect.y(), qrect.width(), qrect.height())
