from concurrent.futures.thread import ThreadPoolExecutor, _WorkItem
import concurrent.futures._base 
import queue

class PrioritizedTask(_WorkItem):
    """
    A task object that executes requests for layer data (i.e. from ImageSource objects).
    Used by the global renderer_pool (a thread pool).
    """
    def __init__(self, fut, func, priority):
        super(PrioritizedTask, self).__init__(fut, func, [], {})
        self.priority = priority

    def __lt__(self, other):
        """
        Compare two PrioritizedTasks according to their priorities.
        Smaller priority values go to the front of the queue.
        """
        assert isinstance(self, PrioritizedTask) and isinstance(other, PrioritizedTask), \
            "Can't compare {} with {}".format( type(self), type(other) )
        return self.priority < other.priority

class PrioritizedThreadPoolExecutor(ThreadPoolExecutor):
    """
    The executor type for the render_pool
    (a thread pool for executing requests for layer data.)
    
    Differences from base class (ThreadPoolExecutor):
      - self._work_queue is a PriorityQueue, not a plain Queue.Queue
      - self.submit() creates a PrioritizedTask (which has a less-than operator
        and can therefore be prioritized), not a generic _WorkItem
    """
    def __init__(self, max_workers):
        super(PrioritizedThreadPoolExecutor, self).__init__(max_workers)
        self._work_queue = queue.PriorityQueue()

    def submit(self, func, priority):
        """
        Mostly copied from ThreadPoolExecutor.submit(), but here we replace '_WorkItem' with 'PrioritizedTask'.
        Also, we pass the 'prefetch' and 'timestamp' parameters.
        """
        with self._shutdown_lock:
            if self._shutdown:
                raise RuntimeError('cannot schedule new futures after shutdown')

            fut = concurrent.futures._base.Future()
            w = PrioritizedTask(fut, func, priority)

            self._work_queue.put(w)
            self._adjust_thread_count()
            return fut

