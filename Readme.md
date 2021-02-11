**Volumina** - Volume Slicing and Editing Library
=============================================

[![Build Status](https://travis-ci.org/ilastik/volumina.svg?branch=master)](https://travis-ci.org/ilastik/volumina)
[![Build status](https://ci.appveyor.com/api/projects/status/t371b1yf0eo7u5mp/branch/master?svg=true)](https://ci.appveyor.com/project/k-dominik/volumina-r7dc9/branch/master)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)

Installing
==========

```bash
conda install -c ilastik-forge -c conda-forge volumina
```

Using Volumina as an Image Viewer
=================================

Currently, only format supported is `.npy`.

Open an `.npy` image and display it:

```bash
# Usage: volumina image axisorder
volumina <myimage.npy> yx
```

axisorder should correspond to the data. Only `t` (time), `c` (channel), and the spacial axes `x`, `y`, `z` are valid.


Volumina Development
====================

Create a development environment
--------------------------------

To set up a development environment, we currently recommend to follow Contributing Guidelines of our main repository [ilastik](https://github.com/ilastik/ilastik): [CONTRIBUTING](https://github.com/ilastik/ilastik/blob/master/CONTRIBUTING.md)
