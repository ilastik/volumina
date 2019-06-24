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
import configparser
import os

default_config = """
[pixelpipeline]
verbose: false

[viewport]
use_opengl: true
"""

_cfg = configparser.ConfigParser()
_cfg.read_string(default_config)
userConfig = os.path.expanduser("~/.voluminarc")
if os.path.exists(userConfig):
    _cfg.read(userConfig)


class Config:
    def __init__(self, cfg):
        self._cfg = cfg
        self._env = os.environ

    @property
    def verbose_pixelpipeline(self):
        return self._get_boolean("pixelpipeline", "verbose")

    @property
    def use_opengl_viewport(self):
        return self._get_boolean("viewport", "use_opengl")

    def _get_boolean(self, section: str, option: str) -> bool:
        val = self._env.get(f"{section.upper()}_{option.upper()}")
        if val is not None:
            try:
                return bool(int(val))
            except ValueError:
                pass

        return self._cfg.getboolean(section, option)


CONFIG = Config(_cfg)
