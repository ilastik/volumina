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
import configparser
import os

from functools import cached_property

default_config = """
[volumina]
pixelpipeline_verbose: false
show_3d_widget: true
enable_fallback_viewports: false
"""

_cfg = configparser.ConfigParser()
_cfg.read_string(default_config)
userConfig = os.path.expanduser("~/.voluminarc")
if os.path.exists(userConfig):
    _cfg.read(userConfig)

_256MB = 256 * 1024 * 1024


class _Config:
    def __init__(self, cfg):
        self._cfg = cfg
        self._env = os.environ

    @cached_property
    def verbose_pixelpipeline(self):
        return self._get_boolean("volumina", "pixelpipeline_verbose")

    @cached_property
    def show_3d_widget(self):
        return self._get_boolean("volumina", "show_3d_widget")

    @cached_property
    def enable_fallback_viewports(self):
        return self._get_boolean("volumina", "enable_fallback_viewports")

    @cached_property
    def cache_size(self):
        return self._cfg.getint("volumina", "cache_size", fallback=_256MB)

    def _get_boolean(self, section: str, option: str) -> bool:
        val = self._env.get(f"{section.upper()}_{option.upper()}")
        if val is None:
            return self._cfg.getboolean(section, option)

        try:
            return bool(int(val))
        except ValueError as e:
            raise ValueError(f"environment variable {val!r} is not a boolean") from e


CONFIG = _Config(_cfg)
