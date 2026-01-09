import pytest

from volumina.utility import preferences


@pytest.fixture(scope="session", autouse=True)
def change_preferences_path(tmp_path_factory):
    preferences.set_path(tmp_path_factory.mktemp("preferences") / "preferences.json")


@pytest.fixture()
def patch_threadpool():
    """
    Clean up the Render pool after every test

    avoids test hangs starting with python 3.10
    """
    import volumina.tiling.tileprovider

    if not volumina.tiling.tileprovider.USE_LAZYFLOW_THREADPOOL:
        from volumina.utility.prioritizedThreadPool import PrioritizedThreadPoolExecutor

        volumina.tiling.tileprovider.renderer_pool = PrioritizedThreadPoolExecutor(2)
        yield
        volumina.tiling.tileprovider.renderer_pool.shutdown()
        volumina.tiling.tileprovider.renderer_pool = None
    else:
        yield
