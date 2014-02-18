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

from setuptools import setup

packages=['volumina', 
          'volumina.pixelpipeline',
          'volumina.skeletons',
          'volumina.colorama',
          'volumina.widgets',
          'volumina.widgets.ui',
          'volumina.utility',
          'volumina.view3d',
          'volumina._testing']

package_data={'volumina.widgets.ui': ['*.ui'],
              'volumina.widgets': ['*.ui'],
              'volumina': ['*.ui'],
              'volumina._testing': ['*.tif',
                                    '*.png', 
                                    'lena.npy', 
                                    'rgba129x104.npy']}

setup(name='volumina',
      version='0.6a',
      description='Volume Slicing and Editing',
      url='https://github.com/Ilastik/volumina',
      packages=packages,
      package_data=package_data,
      setup_requires=['nose>=1.0']
     )
