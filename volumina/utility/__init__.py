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
from log_exception import log_exception
from getMainWindow import getMainWindow
from singleton import Singleton
from preferencesManager import PreferencesManager
from shortcutManager import ShortcutManager
from shortcutManagerDlg import ShortcutManagerDlg
from qstring_codec import encode_from_qstring, decode_to_qstring
from volumina.utility.edge_coords import edge_coords_along_axis, edge_coords_nd
from volumina.utility.signalingDefaultDict import SignalingDefaultDict
from volumina.utility.segmentationEdgesItem import SegmentationEdgesItem
