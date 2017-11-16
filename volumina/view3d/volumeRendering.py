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
from PyQt5.QtWidgets import QApplication
import numpy
from colorsys import hsv_to_rgb
from threading import current_thread

from .meshgenerator import MeshGenerator

NUM_OBJECTS = 256


class LabelManager(object):
    def __init__(self, n):
        self._available = set(range(1, n))
        self._used = set([])
        self._n = n

    def request(self):
        if len(self._available) == 0:
            raise RuntimeError('out of labels')
        label = min(self._available)
        self._available.remove(label)
        self._used.add(label)
        return label

    def free(self, label=None):
        if label is None:
            self._used = set([])
            self._available = set(range(1, self._n))
        elif label in self._used:
            self._used.remove(label)
            self._available.add(label)


class RenderingManager(object):
    """Encapsulates the work of adding/removing objects to the
    rendered volume and setting their colors.

    Conceptually very simple: given a volume containing integer labels
    (where zero labels represent transparent background) and a color
    map, renders the objects in the appropriate color.

    """
    def __init__(self, overview_scene):
        self._overview_scene = overview_scene
        self.labelmgr = LabelManager(NUM_OBJECTS)
        self.ready = False
        self._cmap = {}
        self._mesh_thread = None
        self._dirty = False

        def _handle_scene_init():
            self.setup( self._overview_scene.dataShape )
            self.update()
        self._overview_scene.reinitialized.connect( _handle_scene_init )
        
    def setup(self, shape):
        shape = shape[::-1]
        self._volume = numpy.zeros(shape, dtype=numpy.uint8)
        self._mapping = {}
        self.ready = True

    def update(self):
        assert current_thread().name == 'MainThread', \
            "RenderingManager.update() must be called from the main thread to avoid segfaults."

        if not self._dirty:
            return
        self._dirty = False

        new_labels = set(numpy.unique(self._volume))
        new_names = set(filter(None, (self._mapping.get(label) for label in new_labels)))
        old_names = self._overview_scene.visible_objects
        for name in old_names - new_names:
            self._overview_scene.remove_object(name)

        names_to_add = new_names - old_names
        known = set(filter(self._overview_scene.has_object, names_to_add))
        generate = set(self._mapping[name] for name in names_to_add - known)

        for name in known:
            self._overview_scene.add_object(name)

        if generate:
            self._overview_scene.set_busy(True)
            self._mesh_thread = MeshGenerator(self._on_mesh_generated, self._volume, generate, self._mapping)

    def _on_mesh_generated(self, label, mesh):
        """
        Slot for the mesh generated signal from the MeshGenerator
        """
        assert current_thread().name == 'MainThread'
        if label == 0 and mesh is None:
            self._overview_scene.set_busy(False)
        else:
            mesh.setColor(self._cmap[self._mapping[label]] + (1,))
            mesh.setShader("toon")
            self._overview_scene.add_object(label, mesh)

    def setColor(self, label, color):
        self._cmap[label] = color

    @property
    def volume(self):
        # We store the volume in reverse-transposed form, so un-transpose it when it is accessed.
        return numpy.transpose(self._volume)

    @volume.setter
    def volume(self, value):
        # Must copy here because a reference to self._volume was stored in the pipeline (see setup())
        # store in reversed-transpose order to match the wireframe axes
        new_volume, mapping = value
        new_volume = numpy.transpose(new_volume)
        if numpy.any(new_volume != self._volume) or mapping != self._mapping:
            self._volume[:] = new_volume
            self._mapping = mapping
            self._dirty = True
            self.update()

    def addObject(self, color=None):
        label = self.labelmgr.request()
        if color is None:
            color = hsv_to_rgb(numpy.random.random(), 1.0, 1.0)
        self.setColor(label, color)
        return label

    def removeObject(self, label):
        self.labelmgr.free(label)

    def invalidateObject(self, name):
        self._overview_scene.invalidate_object(name)

    def clear(self, ):
        self._volume[:] = 0
        self.labelmgr.free()

