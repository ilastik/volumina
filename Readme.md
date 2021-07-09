**Volumina** - Volume Slicing and Editing Library
=============================================

[![build](https://github.com/ilastik/volumina/workflows/test/badge.svg)](https://github.com/ilastik/volumina/actions)
[![deployment](https://github.com/ilastik/volumina/workflows/deploy/badge.svg)](https://github.com/ilastik/volumina/actions)
[![black](https://github.com/ilastik/volumina/workflows/lint/badge.svg)](https://github.com/ilastik/volumina/actions)


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

To set up a development environment, we currently recommend to follow Contributing Guidelines of our main repository [ilastik](https://github.com/ilastik/ilastik): [CONTRIBUTING](https://github.com/ilastik/ilastik/blob/main/CONTRIBUTING.md)
