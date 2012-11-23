from setuptools import setup

packages=['volumina', 
          'volumina.pixelpipeline',
          'volumina.colorama',
          'volumina.widgets',
          'volumina.widgets.ui',
          'volumina.utility',
          'volumina.view3d',
          'volumina._testing']

package_data={'volumina.widgets.ui': ['*.ui'],
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
      package_data=package_data
     )
