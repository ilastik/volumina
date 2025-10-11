###############################################################################
#   volumina: volume slicing and editing library
#
#       Copyright (C) 2011-2024, the ilastik developers
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
#          http://ilastik.org/license/
###############################################################################
import collections
import logging
from threading import RLock
import time
from contextlib import contextmanager
from functools import partial

from typing import Callable, Union
from qtpy.QtCore import QObject, QRect, QRectF, Signal
from qtpy.QtGui import QImage, QPainter, QTransform
from qtpy.QtWidgets import QGraphicsItem

from volumina.pixelpipeline.imagepump import StackedImageSources
from volumina.pixelpipeline.interface import IndeterminateRequestError
from volumina.pixelpipeline.slicesources import StackId
from volumina.utility import PrioritizedThreadPoolExecutor

from .cache import TilesCache
from .tiling import Tiling

logger = logging.getLogger(__name__)

# If lazyflow is installed, use that threadpool.
try:
    from lazyflow.request import Request

    USE_LAZYFLOW_THREADPOOL = True

except ImportError:
    USE_LAZYFLOW_THREADPOOL = False


renderer_pool = None

if USE_LAZYFLOW_THREADPOOL:
    from volumina.utility.lazyflowRequestBuffer import LazyflowRequestBuffer

    renderer_pool = LazyflowRequestBuffer(9)

    def clear_threadpool_vp(vp: "TileProvider", stack_id: StackId, keep_tiles: list[int]):
        renderer_pool.clear_vp_res(vp, stack_id, keep_tiles)

    def submit_to_threadpool(
        fn: Callable[[], None],
        priority: tuple[bool, float],
        viewport: "TileProvider",
        stack_id: StackId,
        tile_no: int,
    ):
        # Tiling requests are less prioritized than most requests.
        root_priority = [1] + list(priority)
        req = Request(fn, root_priority)
        # somehow this for the request thing
        assert isinstance(renderer_pool, LazyflowRequestBuffer)
        renderer_pool.submit(fn, priority, viewport, stack_id, tile_no)

else:
    renderer_pool = PrioritizedThreadPoolExecutor(6)

    def clear_threadpool_vp(*args, **kwargs):
        pass

    def submit_to_threadpool(
        fn: Callable[[], None],
        priority: tuple[bool, float],
        _viewport: "TileProvider",
        _stack_id: StackId,
        _tile_no: int,
    ):
        assert isinstance(renderer_pool, PrioritizedThreadPoolExecutor)
        renderer_pool.submit(fn, priority)


@contextmanager
def TileTimer():
    result = TileTime()
    start = time.time()
    try:
        yield result
    finally:
        result.seconds = time.time() - start


class TileTime(object):
    seconds = 0.0


class TrueInc:
    _count = 0
    _lock = RLock()

    def inc(self):
        with self._lock:
            self._count += 1
            return self._count


_Counter = TrueInc()


class TileProvider(QObject):
    """
    Note: Throughout this class, the terms 'layer', 'ImageSource', and 'ims' are used interchangeably.
    """

    Tile = collections.namedtuple(
        "Tile",
        [
            "id",  # tile number
            "qimg",  # composited tile as a QImage
            "qgraphicsitems",  # list of QGraphicsItems to be displayed over the tile
            "rectF",  # The patch dimensions (see Tiling class, above)
            "progress",
        ],
    )  # How 'complete' the composite tile is
    # (depending on how many layers are still dirty)

    sceneRectChanged = Signal(QRectF)

    @property
    def axesSwapped(self):
        return self._axesSwapped

    @axesSwapped.setter
    def axesSwapped(self, value):
        self._axesSwapped = value

    def __init__(self, tiling: Tiling, stackedImageSources: StackedImageSources, cache_size: int = 100) -> None:
        """
        Keyword Arguments:
        cache_size                -- maximal number of encountered stacks
                                     to cache, i.e. slices if the imagesources
                                     draw from slicesources (default 10)
        parent                    -- QObject

        """

        QObject.__init__(self, parent=None)

        self.tiling = tiling
        self.axesSwapped = False
        self._sims = stackedImageSources

        self._current_stack_id = self._sims.stackId
        self._cache = TilesCache(self._current_stack_id, self._sims, maxstacks=cache_size)

        self._sims.layerDirty.connect(self._onLayerDirty)
        self._sims.visibleChanged.connect(self._onVisibleChanged)
        self._sims.opacityChanged.connect(self._onOpacityChanged)
        self._sims.sizeChanged.connect(self._onSizeChanged)
        self._sims.orderChanged.connect(self._onOrderChanged)
        self._sims.stackIdChanged.connect(self._onStackIdChanged)

    @property
    def cache_size(self):
        return self._cache.maxstacks

    def set_cache_size(self, new_size):
        self._cache.set_maxstacks(new_size)

    def getTiles(self, rectF: QRectF, vp_rectF: QRectF):
        """Get tiles in rect and request a refresh.

        Returns tiles intersecting with rectF immediately and requests
        a refresh of these tiles. Next time you call this function the
        tiles may be already (partially) updated. If you want to wait
        until the rendering is fully complete, call join().

        """
        tile_nos = self.tiling.intersected(rectF)
        stack_id = self._current_stack_id
        keep_tiles = self.tiling.intersected(vp_rectF)
        clear_threadpool_vp(self, stack_id, keep_tiles)
        self.requestRefresh(rectF)

        for tile_no in tile_nos:
            with self._cache:
                qimg, progress = self._cache.tile(stack_id, tile_no)
                qgraphicsitems = self._cache.graphicsitem_layers(stack_id, tile_no)
            yield TileProvider.Tile(tile_no, qimg, qgraphicsitems, QRectF(self.tiling.imageRects[tile_no]), progress)

    def waitForTiles(self, rectF=QRectF(), sceneRectF=QRectF()):
        """
        This function is for testing purposes only.
        Block until all tiles intersecting the given rect are complete.
        """
        finished = False
        while not finished:
            finished = True
            tiles = self.getTiles(rectF, sceneRectF)
            for tile in tiles:
                finished &= tile.progress >= 1.0

    def requestRefresh(self, rectF, stack_id=None, prefetch=False, layer_indexes=None):
        """Requests tiles to be refreshed.

        Returns immediately. Call join() to wait for
        the end of the rendering.

        """
        stack_id = stack_id or self._current_stack_id
        tile_nos = self.tiling.intersected(rectF)

        for tile_no in tile_nos:
            self._refreshTile(stack_id, tile_no, prefetch, layer_indexes)

    def prefetch(self, rectF, through, layer_indexes=None):
        """Request fetching of tiles in advance.

        Returns immediately. Prefetch will commence after all regular
        tiles are refreshed (see requestRefresh() and getTiles() ).
        The prefetch is reset when the 'through' value of the slicing
        changes. Several calls to prefetch are handeled in Fifo
        order.

        """
        if self.cache_size == 0:
            return

        stack_id = (self._current_stack_id[0], tuple(enumerate(through)))
        with self._cache:
            if stack_id not in self._cache:
                self._cache.addStack(stack_id)
                self._cache.touchStack(self._current_stack_id)

        self.requestRefresh(rectF, stack_id, prefetch=True, layer_indexes=layer_indexes)

    def _refreshTile(self, stack_id, tile_no, prefetch=False, layer_indexes=None):
        """
        Trigger a refresh of a particular tile.

        In the common case**, this function does the following:

        For every layer in the patch specified by (stackid, tile_no):

            1. Blend the layers (ims) -- in their current,
               (possibly incomplete) state -- into a composite tile,
               and update the tile cache with it.

            2. Then, for dirty layers *that are actually visible*,
               create a request to fetch their data.

            3. Submit all the layer requests to the thread pool.

        **Less common cases:
             - In 'prefetch' mode: don't bother rendering composite tile, just fetch the layers.
             - For 'direct' layers, don't submit the request to the threadpool,
               just execute it immediately.
        """
        layers = self._sims.viewImageSources()
        if layer_indexes:
            layers = [layers[i] for i in layer_indexes]

        if not self.axesSwapped:
            # Who came up with this transform?
            transform = QTransform(0, 1, 0, 1, 0, 0, 1, 1, 1)
        else:
            transform = QTransform().rotate(90).scale(1, -1)
        transform *= self.tiling.data2scene

        try:
            with self._cache:
                if not self._cache.tileDirty(stack_id, tile_no):
                    return

            if not prefetch:
                with self._cache:
                    self._cache.setTileDirty(stack_id, tile_no, False)

                # Blend all (available) layers into the composite tile
                # and store it in the tile cache.
                tile_img = self._blendTile(stack_id, tile_no)
                with self._cache:
                    self._cache.setTile(
                        stack_id, tile_no, tile_img, self._sims.viewVisible(), self._sims.viewOccluded()
                    )
            # refresh dirty layer tiles
            need_reblend = False
            for ims in layers:
                with self._cache:
                    layer_dirty = self._cache.layerTileDirty(stack_id, ims, tile_no)

                # Don't bother fetching layers that are not visible or not dirty.
                if not (layer_dirty and not self._sims.isOccluded(ims) and self._sims.isVisible(ims)):
                    continue

                rect = self.tiling.imageRects[tile_no]
                dataRect = self.tiling.scene2data.mapRect(rect)

                try:
                    # Create the request object right now, from the main thread.
                    ims_req = ims.request(dataRect, stack_id[1])
                except IndeterminateRequestError:
                    # In ilastik, the viewer is still churning even as the user might be changing settings in the UI.
                    # Settings changes can cause 'slot not ready' errors during graph setup.
                    # Those errors are not really a problem, but we don't want to hide them from developers
                    # So, we show the exception (in the log), but we don't kill the thread.
                    logger.debug("Failed to create layer tile request", exc_info=True)
                    continue

                timestamp = _Counter.inc()
                fetch_fn = partial(
                    self._fetch_layer_tile, timestamp, ims, transform, tile_no, stack_id, ims_req, self._cache
                )

                if ims.direct and not prefetch:
                    # The ImageSource 'ims' is fast (it has the direct flag set to true),
                    # so we process the request synchronously here.
                    # This improves the responsiveness for layers that have the data readily available.
                    fetch_fn()
                    need_reblend = True
                else:
                    # Tasks with 'smaller' priority values are processed first.
                    # We want non-prefetch tasks to take priority (False < True)
                    # and then more recent tasks to take priority (more recent -> process first)
                    priority = (prefetch, -timestamp)
                    submit_to_threadpool(fetch_fn, priority, self, stack_id, tile_no)

            if need_reblend:
                # We synchronously fetched at least one direct layer.
                # We can immediately re-blend the composite tile.
                tile_img = self._blendTile(stack_id, tile_no)
                with self._cache:
                    self._cache.setTile(
                        stack_id, tile_no, tile_img, self._sims.viewVisible(), self._sims.viewOccluded()
                    )
        except KeyError:
            pass

    def setTileDirty(self, stack_id, tile_no):
        with self._cache:
            self._cache.setTileDirty(stack_id, tile_no, True)

    def _blendTile(self, stack_id, tile_nr):
        """
        Blend all of the QImage layers of the patch
        specified by (stack_id, tile_nr) into a single QImage.
        """
        qimg = None
        p = None
        for i, (visible, layerOpacity, layerImageSource) in enumerate(reversed(self._sims)):
            image_type = layerImageSource.image_type()
            if issubclass(image_type, QGraphicsItem):
                # Don't blend QGraphicsItem into the final tile.
                # (The ImageScene will just draw it on top of everything.)
                # But this is a convenient place to update the opacity/visible state.
                with self._cache:
                    patch = self._cache.layerTile(stack_id, layerImageSource, tile_nr)
                if patch is not None:
                    assert isinstance(
                        patch, image_type
                    ), "This ImageSource is producing a type of image that is not consistent with it's declared image_type()"
                    if patch.opacity() != layerOpacity or patch.isVisible() != visible:
                        patch.setOpacity(layerOpacity)
                        patch.setVisible(visible)
                    patch.setZValue(i)  # The sims ("stacked image sources") are ordered from
                    # top-to-bottom (see imagepump.py), but in Qt,
                    # higher Z-values are shown on top.
                    # Note that the current loop is iterating in reverse order.
                continue

            # No need to fetch non-visible image tiles.
            if not visible or layerOpacity == 0.0:
                continue

            with self._cache:
                patch = self._cache.layerTile(stack_id, layerImageSource, tile_nr)

            if patch is not None:
                assert isinstance(
                    patch, QImage
                ), "Unknown tile layer type: {}. Expected QImage or QGraphicsItem".format(type(patch))
                if qimg is None:
                    # First actually available layer - init the QImage and painter for this tile
                    qimg = QImage(self.tiling.imageRects[tile_nr].size(), QImage.Format_ARGB32_Premultiplied)
                    qimg.fill(0xFFFFFFFF)
                    p = QPainter(qimg)
                p.setOpacity(layerOpacity)
                p.drawImage(0, 0, patch)

        if p is not None:
            p.end()

        return qimg

    def _fetch_layer_tile(self, timestamp, ims, transform, tile_nr, stack_id, ims_req, cache):
        """
        Fetch a single tile from a layer (ImageSource).

        Parameters
        ----------
        timestamp
            The timestamp at which ims_req was created
        ims
            The layer (image source) we're fetching from
        transform
            The transform to apply to the fetched data, before storing it in the cache
        tile_nr
            The ID of the fetched tile
        stack_id
            The stack ID of the tile we're fetching (e.g. which T-slice and Z-slice this tile belongs to)
        ims_req
            A request object (e.g. GrayscaleImageRequest) with a wait() method that produces an item of
            the appropriate type for the layer (i.e. either a QImage or a QGraphicsItem)
        cache
            The value of self._cache at the time the ims_req was created.
            (The cache can be replaced occasionally. See TileProvider._onSizeChanged().)
        """
        try:
            try:
                with cache:
                    layerTimestamp = cache.layerTileTimestamp(stack_id, ims, tile_nr)
            except KeyError:
                # May not be a timestamp yet (especially when prefetching)
                layerTimestamp = 0

            tile_rect = QRectF(self.tiling.imageRects[tile_nr])

            if timestamp > layerTimestamp:
                img = ims_req.wait()
                if isinstance(img, QImage):
                    img = img.transformed(transform)
                elif isinstance(img, QGraphicsItem):
                    # FIXME: It *seems* like applying the same transform to QImages and QGraphicsItems
                    #        makes sense here, but for some strange reason it isn't right.
                    #        For QGraphicsItems, it seems obvious that this is the correct transform.
                    #        I do not understand the formula that produces 'transform', which is used for QImage tiles.
                    img.setTransform(QTransform.fromTranslate(tile_rect.left(), tile_rect.top()), combine=True)
                    img.setTransform(self.tiling.data2scene, combine=True)
                else:
                    assert False, "Unexpected image type: {}".format(type(img))

                with cache:
                    try:
                        cache.updateTileIfNecessary(stack_id, ims, tile_nr, timestamp, img)
                    except KeyError:
                        pass

                if stack_id == self._current_stack_id and cache is self._cache:
                    self.sceneRectChanged.emit(tile_rect)
        except BaseException:
            raise

    def _onLayerDirty(self, dirtyImgSrc, dataRect):
        """
        Called when one of the image sources we depend on has become dirty.
        Mark the appropriate entries in our tile/layer caches as dirty.
        """
        # Clip the dataRect to the boundaries of the tiling, to ensure
        # that the 'fast path' below is active when appropriate.
        # (datasources are permitted to mark wider dirty regions than the
        # scene boundaries, but the roi outside the scene bounds is just ignored.)
        tileshape = self.tiling.sliceShape

        datastart = (max(0, dataRect.left()), max(0, dataRect.top()))

        datastop = (
            min(tileshape[0], dataRect.x() + dataRect.width()),  # Don't use right()!
            min(tileshape[1], dataRect.y() + dataRect.height()),
        )  # Don't use bottom()!

        dataRect = QRect(datastart[0], datastart[1], datastop[0] - datastart[0], datastop[1] - datastart[1])

        sceneRect = self.tiling.data2scene.mapRect(dataRect)
        if dirtyImgSrc not in self._sims.viewImageSources():
            return

        visibleAndNotOccluded = self._sims.isVisible(dirtyImgSrc) and not self._sims.isOccluded(dirtyImgSrc)

        # Is EVERYTHING dirty?
        if not sceneRect.isValid() or dataRect == QRect(0, 0, *self.tiling.sliceShape):
            # Everything is dirty.
            # This is a FAST PATH for quickly setting all tiles dirty.
            # (It makes a HUGE difference for very large tiling scenes.)
            with self._cache:
                self._cache.setLayerTilesDirty(dirtyImgSrc)
                if visibleAndNotOccluded:
                    self._cache.setAllTilesDirty()
        else:
            # Slow path: Mark intersecting tiles as dirty.
            with self._cache:
                for tile_no in self.tiling.intersected(sceneRect):
                    self._cache.setLayerTileDirtyAllStacks(dirtyImgSrc, tile_no, True)
                    if visibleAndNotOccluded:
                        self._cache.setTileDirtyAllStacks(tile_no, True)
        if visibleAndNotOccluded:
            self.sceneRectChanged.emit(QRectF(sceneRect))

    def _onStackIdChanged(self, oldId, newId):
        """
        When the current 'stacked image source' has changed it's 'stack id'.
        The 'stack id' changes when the user scrolls to a new plane.
        When that happens, we keep all of our caches for the old plane,
        but we add (if necesssary) a new set of caches for all the tiles
        that will be shown in the new plane.
        """
        with self._cache:
            if newId in self._cache:
                self._cache.touchStack(newId)
            else:
                self._cache.addStack(newId)
        self._current_stack_id = newId
        self.sceneRectChanged.emit(QRectF())

    def _onVisibleChanged(self, ims, visible):
        """
        Called when one of the image sources we depend on has changed it's visibility.
        All tiles will need to be re-rendered (i.e. blended from layers).
        """
        with self._cache:
            self._cache.setAllTilesDirty()
        if not self._sims.isOccluded(ims):
            self.sceneRectChanged.emit(QRectF())

    def _onOpacityChanged(self, ims, opacity):
        """
        Called when one of the image sources we depend on has changed it's opacity.
        All tiles will need to be re-rendered (i.e. blended from layers).
        """
        with self._cache:
            self._cache.setAllTilesDirty()
        if self._sims.isVisible(ims) and not self._sims.isOccluded(ims):
            self.sceneRectChanged.emit(QRectF())

    def _onSizeChanged(self):
        """
        Called when the StackedImageSources object we depend on has changed it's size.
        This is rare, but it means that the entire tile cache is obsolete.
        """
        self._cache = TilesCache(self._current_stack_id, self._sims, maxstacks=self.cache_size)
        self.sceneRectChanged.emit(QRectF())

    def _onOrderChanged(self):
        """
        Called when the order of ImageSource objects the StackedImageSources
        (on which we depend) has changed.  The tiles all need to be re-rendered.
        """
        with self._cache:
            self._cache.setAllTilesDirty()
        self.sceneRectChanged.emit(QRectF())
