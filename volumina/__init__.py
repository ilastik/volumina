from __future__ import absolute_import

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
import sys
import logging

volumina_logger = logging.getLogger("volumina")


def has_handler(logger):
    if len(logger.handlers) > 0:
        return True
    if logger.parent is None:
        return False
    return has_handler(logger.parent)


# If the system already has a logging setup, then don't add our own handlers to it.
if not has_handler(volumina_logger):
    volumina_logging_handler = logging.StreamHandler(sys.stdout)
    volumina_logger.addHandler(volumina_logging_handler)

    volumina_logger.setLevel(logging.INFO)
    volumina_logging_handler.setLevel(logging.INFO)


from . import api

# volumina.icons_rc is needed on some machines for the icons to be displayed correctly
import volumina.icons_rc


def strQRect(qrect):
    return "(x=%d,y=%d,w=%d,h=%d)" % (qrect.x(), qrect.y(), qrect.width(), qrect.height())
