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

from threading import Event
from typing import List, NamedTuple, Optional, Tuple
from unittest.mock import MagicMock

import pytest

from volumina.pixelpipeline.slicesources import StackId
from volumina.utility.lazyflowRequestBuffer import LazyflowRequestBuffer


class TimeoutExceeded(BaseException):
    pass


class TimeoutRaisingEvent(Event):
    """Helper class to ensure Events don't silently time out"""

    def wait_raise(self, timeout: float | None = 0.2):
        success = super().wait(timeout)
        if not success:
            raise TimeoutExceeded()


class WaitingFunc:
    """Function that pauses execution until req_continue event is set"""

    def __init__(self, side_effect: Optional[Exception] = None):
        self.side_effect = side_effect
        self.running: bool = False
        self.req_continue: TimeoutRaisingEvent = TimeoutRaisingEvent()
        self.started: TimeoutRaisingEvent = TimeoutRaisingEvent()
        self.done: TimeoutRaisingEvent = TimeoutRaisingEvent()

        global _waiting_reg
        _waiting_reg.append(self)

    def __call__(self):
        self.running = True
        self.started.set()
        try:
            if self.side_effect is not None:
                raise self.side_effect
            self.req_continue.wait()
        except Exception as ex:
            raise ex
        finally:
            self.running = False
            self.done.set()


_waiting_reg: List[WaitingFunc] = []


@pytest.fixture(autouse=True)
def cleanup_waiting_functions():
    """Make sure no instance of WaitingFunc is blocking

    otherwise this will block the tests to continue. This can happen on test
    failures before `WaitingFunc.req_continue.set()` was called.
    """
    yield

    global _waiting_reg
    for w in _waiting_reg:
        if w.running:
            w.req_continue.set()
            w.done.wait()

    _waiting_reg = []


class Context(NamedTuple):
    """Some context variables needed by LazyflowRequestBuffer

    normally these are determined in `TileProvider`.
    """

    view_port: MagicMock
    stack_id: StackId
    tile_no: int
    priority: Tuple[int, ...]


@pytest.fixture
def default_context() -> Context:
    """Some default context that is reused in many tests"""
    return Context(MagicMock(), (object(), ((0, 0))), 0, (-100,))


@pytest.fixture
def finished_evt() -> TimeoutRaisingEvent:
    """Fixture that is both used in the `request_buffer` fixture

    Separate fixture to avoid unpacking in every test.
    """
    return TimeoutRaisingEvent()


def install_finish_even(
    obj: LazyflowRequestBuffer, func: str, event: Optional[TimeoutRaisingEvent] = None, n_calls: int = 1
):
    """
    Helper function that wraps any function and sets an event after the function
    has been called `n_calls` times.

    Needed to ensure asynchronous calls are waited on. Not possible to wrap in a
    mock - no guarantee the calls have been done when checking the mock.
    """
    old_func = getattr(obj, func)

    n_calls_made = 0

    event = event or TimeoutRaisingEvent()

    def new_func(*args, **kwargs):
        nonlocal n_calls_made
        ret = old_func(*args, **kwargs)
        n_calls_made += 1
        if n_calls_made == n_calls:
            event.set()
        return ret

    setattr(obj, func, new_func)

    return event


@pytest.fixture
def default_waiting_func():
    """Default fixture to use in request_buffer

    Separate fixture to avoid unpacking
    """
    return WaitingFunc()


@pytest.fixture
def request_buffer(finished_evt: TimeoutRaisingEvent, default_context: Context, default_waiting_func: WaitingFunc):
    """Default request buffer

    Already preloaded with one running WaitingFunc task with the default context.

    Hint use `default_waiting_func` fixture in tests to interact with this blocking task.
    """
    buffer = LazyflowRequestBuffer(1)
    _ = install_finish_even(buffer, "decr", event=finished_evt)
    buffer.submit(
        default_waiting_func,
        priority=default_context.priority,
        viewport_ref=default_context.view_port,
        stack_id=default_context.stack_id,
        tile_no=default_context.tile_no,
    )
    default_waiting_func.started.wait_raise()
    assert default_waiting_func.running
    return buffer


@pytest.mark.parametrize(
    "n_concurrent_tasks",
    [
        -1,
        -5,
        0,
    ],
)
def test_raises_on_init(n_concurrent_tasks: int):
    with pytest.raises(RuntimeError):
        _ = LazyflowRequestBuffer(n_concurrent_tasks)


def test_task_calls_decr(
    request_buffer: LazyflowRequestBuffer, finished_evt: TimeoutRaisingEvent, default_waiting_func: WaitingFunc
):
    assert request_buffer._active == 1  # pyright: ignore [reportPrivateUsage]

    default_waiting_func.req_continue.set()
    finished_evt.wait_raise()
    assert not default_waiting_func.running
    assert request_buffer._active == 0  # pyright: ignore [reportPrivateUsage]
    assert request_buffer._failed == 0  # pyright: ignore [reportPrivateUsage]


@pytest.mark.qt_no_exception_capture
def test_task_calls_decr_on_error(default_context: Context):
    # can't use default fixture - need to ensure patched function is called twice before emitting signal
    request_buffer = buffer = LazyflowRequestBuffer(1)
    finished_evt = install_finish_even(buffer, "decr", n_calls=1)
    waiting_func1 = WaitingFunc(side_effect=ValueError("AARGH"))

    request_buffer.submit(
        waiting_func1,
        priority=(-100,),
        viewport_ref=default_context.view_port,
        stack_id=default_context.stack_id,
        tile_no=default_context.tile_no,
    )
    waiting_func1.started.wait_raise()

    waiting_func1.req_continue.set()

    finished_evt.wait_raise()
    assert request_buffer._active == 0  # pyright: ignore [reportPrivateUsage]
    assert not waiting_func1.running
    assert request_buffer._failed == 1  # pyright: ignore [reportPrivateUsage]


def test_queuing(default_context: Context):
    # can't use default fixture - need to ensure patched function is called twice before emitting signal
    request_buffer = buffer = LazyflowRequestBuffer(1)
    finished_evt = install_finish_even(buffer, "decr", n_calls=2)

    waiting_func1 = WaitingFunc()
    waiting_func2 = WaitingFunc()

    request_buffer.submit(
        waiting_func1,
        priority=default_context.priority,
        viewport_ref=default_context.view_port,
        stack_id=default_context.stack_id,
        tile_no=default_context.tile_no,
    )
    # submit with higher priority for good measure
    request_buffer.submit(
        waiting_func2,
        priority=(-120,),
        viewport_ref=default_context.view_port,
        stack_id=default_context.stack_id,
        tile_no=default_context.tile_no,
    )

    waiting_func1.started.wait_raise()
    assert waiting_func1.running
    # waiting_func2 is not running despite higher priority - submit is eagerly starting tasks as they come
    assert not waiting_func2.running

    waiting_func1.req_continue.set()
    waiting_func1.done.wait_raise()
    waiting_func2.started.wait_raise()
    assert waiting_func2.running

    assert not finished_evt.is_set()
    waiting_func2.req_continue.set()
    waiting_func2.done.wait_raise()
    assert not waiting_func2.running

    finished_evt.wait_raise()

    assert request_buffer._active == 0  # pyright: ignore [reportPrivateUsage]
    assert request_buffer._cleared_tasks == 0  # pyright: ignore [reportPrivateUsage]


def test_requests_are_cancelled_bc_keep_tiles(
    request_buffer: LazyflowRequestBuffer,
    default_waiting_func: WaitingFunc,
    finished_evt: TimeoutRaisingEvent,
    default_context: Context,
):
    request_buffer.clear_vp_res(default_context.view_port, default_context.stack_id, keep_tiles=[])
    assert default_waiting_func.running
    for _ in range(10):
        request_buffer.submit(
            lambda: None,
            default_context.priority,
            viewport_ref=default_context.view_port,
            stack_id=default_context.stack_id,
            tile_no=1,
        )
    assert request_buffer._cleared_tasks == 0  # pyright: ignore [reportPrivateUsage]
    request_buffer.clear_vp_res(default_context.view_port, default_context.stack_id, keep_tiles=[])
    assert request_buffer._cleared_tasks == 10  # pyright: ignore [reportPrivateUsage]
    assert default_waiting_func.running
    default_waiting_func.req_continue.set()
    default_waiting_func.done.wait_raise()
    assert not default_waiting_func.running
    finished_evt.wait_raise()
    assert default_context.view_port.setTileDirty.call_count == 10
    assert request_buffer._active == 0  # pyright: ignore [reportPrivateUsage]


def test_requests_are_cancelled_bc_keep_different_stack(
    request_buffer: LazyflowRequestBuffer,
    default_waiting_func: WaitingFunc,
    finished_evt: TimeoutRaisingEvent,
    default_context: Context,
):
    stack_id2 = (object(), ((0, 0)))
    request_buffer.clear_vp_res(default_context.view_port, default_context.stack_id, keep_tiles=[])
    assert default_waiting_func.running
    for _ in range(10):
        request_buffer.submit(
            lambda: None,
            priority=default_context.priority,
            viewport_ref=default_context.view_port,
            stack_id=stack_id2,
            tile_no=default_context.tile_no,
        )
    assert request_buffer._cleared_tasks == 0  # pyright: ignore [reportPrivateUsage]
    request_buffer.clear_vp_res(default_context.view_port, default_context.stack_id, keep_tiles=[0])
    assert request_buffer._cleared_tasks == 10  # pyright: ignore [reportPrivateUsage]
    assert default_waiting_func.running
    default_waiting_func.req_continue.set()
    default_waiting_func.done.wait_raise()
    assert not default_waiting_func.running
    finished_evt.wait_raise()
    assert default_context.view_port.setTileDirty.call_count == 10
    assert request_buffer._active == 0  # pyright: ignore [reportPrivateUsage]


def test_requests_other_vp_not_cancelled(
    request_buffer: LazyflowRequestBuffer,
    default_waiting_func: WaitingFunc,
    finished_evt: TimeoutRaisingEvent,
    default_context: Context,
):
    viewPort2 = MagicMock()
    request_buffer.clear_vp_res(default_context.view_port, default_context.stack_id, keep_tiles=[])
    assert default_waiting_func.running
    for _ in range(10):
        request_buffer.submit(
            lambda: None,
            priority=default_context.priority,
            viewport_ref=viewPort2,
            stack_id=default_context.stack_id,
            tile_no=default_context.tile_no,
        )
    assert request_buffer._cleared_tasks == 0  # pyright: ignore [reportPrivateUsage]
    request_buffer.clear_vp_res(default_context.view_port, default_context.stack_id, keep_tiles=[0])
    assert request_buffer._cleared_tasks == 0  # pyright: ignore [reportPrivateUsage]
    assert default_waiting_func.running
    default_waiting_func.req_continue.set()
    default_waiting_func.done.wait()
    assert not default_waiting_func.running
    finished_evt.wait_raise()
    assert default_context.view_port.setTileDirty.call_count == 0
    assert viewPort2.setTileDirty.call_count == 0
    assert request_buffer._active == 0  # pyright: ignore [reportPrivateUsage]


def test_requests_are_cancelled_bc_priority(
    request_buffer: LazyflowRequestBuffer,
    default_waiting_func: WaitingFunc,
    finished_evt: TimeoutRaisingEvent,
    default_context: Context,
):
    request_buffer.clear_vp_res(default_context.view_port, default_context.stack_id, keep_tiles=[])
    assert default_waiting_func.running
    for i in range(10):
        request_buffer.submit(
            lambda: None,
            priority=(-i,),
            viewport_ref=default_context.view_port,
            stack_id=default_context.stack_id,
            tile_no=default_context.tile_no,
        )
    assert request_buffer._cleared_tasks == 0  # pyright: ignore [reportPrivateUsage]
    request_buffer.clear_vp_res(
        default_context.view_port, default_context.stack_id, keep_tiles=[default_context.tile_no]
    )
    # Note: we expect one task to be  left in the queue. The overall assumption is that control
    # over priorities and submissions lies outside. In general running requests are not considered
    # for cancellations.
    # Any request submitted is considered legit - so despite one request already running for the
    # same tile, one request here is left intact.
    assert request_buffer._cleared_tasks == 9  # pyright: ignore [reportPrivateUsage]
    assert default_waiting_func.running
    default_waiting_func.req_continue.set()
    default_waiting_func.done.wait()
    assert not default_waiting_func.running
    finished_evt.wait_raise()
    assert default_context.view_port.setTileDirty.call_count == 0
    assert request_buffer._active == 0  # pyright: ignore [reportPrivateUsage]


def test_clear(
    request_buffer: LazyflowRequestBuffer,
    default_waiting_func: WaitingFunc,
    finished_evt: TimeoutRaisingEvent,
    default_context: Context,
):
    """Test clearing of the whole queue, irrespective of stack_ids, viewports, and so on"""
    request_buffer.clear_vp_res(default_context.view_port, default_context.stack_id, keep_tiles=[])
    assert default_waiting_func.running
    for i in range(10):
        # priorities, stack_ids, viewport_refs tile_no all does not matter
        request_buffer.submit(
            lambda: None, priority=(-i,), viewport_ref=MagicMock(), stack_id=(object(), ((0, 0))), tile_no=0
        )
    assert request_buffer._cleared_tasks == 0  # pyright: ignore [reportPrivateUsage]
    request_buffer.clear()
    assert request_buffer._cleared_tasks == 10  # pyright: ignore [reportPrivateUsage]
    assert default_waiting_func.running
    default_waiting_func.req_continue.set()
    default_waiting_func.done.wait()
    assert not default_waiting_func.running
    finished_evt.wait_raise()
    assert default_context.view_port.setTileDirty.call_count == 0  # pyright: ignore [reportPrivateUsage]
    assert request_buffer._active == 0  # pyright: ignore [reportPrivateUsage]
