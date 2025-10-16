###############################################################################
#   ilastik: interactive learning and segmentation toolkit
#
#       Copyright (C) 2011-2025, the ilastik developers
#                                <team@ilastik.org>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# In addition, as a special exception, the copyright holders of
# ilastik give you permission to combine ilastik with applets,
# workflows and plugins which are not covered under the GNU
# General Public License.
#
# See the LICENSE file for details. License information is also available
# on the ilastik web site at:
#          http://ilastik.org/license.html
###############################################################################
import logging
import heapq
from itertools import chain
from threading import Lock
from typing import TYPE_CHECKING, Callable, Final, List, Tuple

from lazyflow.request import Request

from volumina.pixelpipeline.slicesources import StackId

logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from volumina.tiling.tileprovider import TileProvider


class PrioTask:
    def __init__(
        self,
        func: "Request",
        prio: tuple[bool | int | float, ...],
        viewport_ref: "TileProvider",
        stack_id: StackId,
        tile_no: int,
    ):
        self._func: "Request" = func
        self._tile_no = tile_no
        self._prio = prio
        self._vp = viewport_ref
        self._stack_id = stack_id

    @property
    def vp(self):
        return self._vp

    @property
    def stack_id(self):
        return self._stack_id

    @property
    def tile_no(self):
        return self._tile_no

    def subscribe_complete(self, func: Callable[[Request], None]):
        self._func.add_done_callback(func)

    def run(self) -> None:
        self._func.submit()

    def __lt__(self, other: "PrioTask"):
        return self._prio < other._prio

    def cancel(self, set_dirty=True):
        try:
            self._func.cancel()
        finally:
            if set_dirty:
                self.vp.setTileDirty(self.stack_id, self.tile_no)


class LazyflowRequestBuffer:
    """
    This class is cooperating with `TileProvider`.

    `TileProvider` will fire off requests for various image sources that might
    spawn many requests when data is passed through the graph.
    This can overwhelm the lazyflow request system that eagerly starts all
    tasks. This leads to unresponsiveness and high memory consumption.

    The LazyflowRequestBuffer acts in between the `TileProvider` and the lazyflow
    request system. Requests are submitted only up to an upper limit defined by
    `n_concurrent_tasks`. The other tasks are queued and can be cleared, see
    `clear_non_relevant_tasks_from_queue`.
    """

    def __init__(self, n_concurrent_tasks: int = 8):
        """
        Args:
          n_concurrent_tasks: How many viewer requests will be submitted to the
            request system. Anecdotally it seems a good compromise to have as
            many as threads in the lazyflow threadpool.
        """
        if n_concurrent_tasks <= 0:
            raise RuntimeError(f"Instantiating LazyflowRequestBuffer with {n_concurrent_tasks=}, must be >0.")
        self._lock = Lock()
        self._cleared_tasks: int = 0
        self._n_concurrent_tasks: Final[int] = n_concurrent_tasks
        self._queue: List[PrioTask] = []
        self._active: int = 0
        self._failed: int = 0

    def submit(
        self,
        func: Callable[[], None],
        /,
        priority: tuple[bool | int | float, ...],
        viewport_ref: "TileProvider",
        stack_id: StackId,
        tile_no: int,
    ):
        root_priority = [1] + list(priority)
        req = Request(func, root_priority)
        with self._lock:
            heapq.heappush(self._queue, PrioTask(req, priority, viewport_ref, stack_id, tile_no))
        self.run()

    def run(self):
        with self._lock:
            while self._active < self._n_concurrent_tasks:
                try:
                    req = heapq.heappop(self._queue)
                except IndexError:
                    return

                if req:
                    req.subscribe_complete(self.decr)
                    self._active += 1
                    req.run()

    def decr(self, req: Request):
        with self._lock:
            self._active -= 1
            if req.exception:
                self._failed += 1
        self.run()

    def clear(self):
        with self._lock:
            for task in self._queue:
                task.cancel()
                self._cleared_tasks += 1
            self._queue = []

    def clear_non_relevant_tasks_from_queue(self, viewport: "TileProvider", stack_id: StackId, keep_tiles: list[int]):
        """Remove waiting tiles no longer visible or outdated for the current viewport

        Cancellation criteria are:
          * same tile, but older request
          * task in a different 2d slice
          * tasks in the same slice, but outside the field of view

        Args:
          viewport: The viewport that requests new tiles to be rendered
          stack_id: corresponding to the slice requested by the viewport
          keep_tiles: list of all tiles in the current view
        """
        tmp_queue: dict[Tuple[StackId, int], PrioTask] = {}
        tmp_queue_other_vp: List[PrioTask] = []
        with self._lock:
            for task in self._queue:
                # don't touch tasks outside the current viewport
                if task.vp != viewport:
                    tmp_queue_other_vp.append(task)
                    continue

                # Remove older requests of the same tile in the current 2d_slice
                if (stack_id, task.tile_no) in tmp_queue:
                    task.cancel(set_dirty=False)
                    self._cleared_tasks += 1
                    continue

                # Remove
                # * tasks outside current 2d slice from the queue
                # * tasks in the current slice, but no longer visible (not in keep_tiles)
                if task.stack_id != stack_id or task.tile_no not in keep_tiles:
                    task.cancel()
                    self._cleared_tasks += 1
                    continue

                tmp_queue[(stack_id, task.tile_no)] = task

            self._queue = list(chain(tmp_queue.values(), tmp_queue_other_vp))
            heapq.heapify(self._queue)
