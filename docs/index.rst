Volumina v0.6 documentation
====================================================
The *volumina* library is concerned with displaying slice views of high
dimensional image data and user interactions with the slice views. It is
written in `Python <http://python.org/>`_ and makes heavy use of the
`Qt <https://qt-project.org/>`_
graphical user interface library. *volumina* implements the following features:

* handling of data larger than main memory employing tile-based
  streaming
* support for 3d+t volumes with multiple channels and various numeric datatypes
* display of several volumes simultaneously rendered as a stack of layers
* slice views of any axes pair like x-y or z-time
* interaction modes like brushing labels or selecting objects
* ready-to-use viewer widgets 

The library is structured into a low level and high level part. The
low level part consists of a collection of loosely coupled classes
which can be combined to design a variety of systems
for slicing and editing multidimensional volumetric data. Besides
others the central low level components are the *pixel rendering
pipeline* (see: :doc:`ll/pixelpipeline`)  and the *interaction modes*
(see: :doc:`hl/interactionmodes`). The design of these components is
governed by the Observer and Model-View-Controller design
patterns. The high level part builds upon the low level components and
provides ready-to-use classes and widgets to be used in other applications; with the
*volume editor* (see: :doc:`hl/volumeeditor`) being the most important one.

Contents:

.. toctree::
   :maxdepth: 5
   :numbered:

   hl/index
   ll/index

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

