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
from setuptools import setup
import setuptools_scm

packages = [
    "volumina",
    "volumina._testing",
    "volumina.icons",
    "volumina.pixelpipeline",
    "volumina.pixelpipeline.datasources",
    "volumina.pixelpipeline.imagesources",
    "volumina.skeletons",
    "volumina.tiling",
    "volumina.utility",
    "volumina.view3d",
    "volumina.widgets",
]

package_data = {
    "volumina": ["*.ui"],
    "volumina._testing": ["*.npy", "*.txt"],
    "volumina.icons": ["*"],
    "volumina.view3d": ["ui/*.ui"],
    "volumina.widgets": ["*.ui", "ui/*.ui"],
}

_version = setuptools_scm.get_version(write_to="volumina/_version.py")

setup(
    name="volumina",
    version=_version,
    description="Volume Slicing and Editing",
    url="https://github.com/Ilastik/volumina",
    packages=packages,
    package_data=package_data,
    python_requires=">=3.7",
    entry_points={"console_scripts": ["volumina = volumina.__main__:main"]},
)
