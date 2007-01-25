#   Copyright (c) 2003-2006 Open Source Applications Foundation
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.


"""Extension Point for Application Startup"""

from application import schema
from repository.persistence.Repository import RepositoryThread
import threading, datetime, logging
from weakref import WeakValueDictionary

__all__ = [
    'Startup', 'Thread', 'TwistedTask', 'PeriodicTask',
    'run_startup', 'get_reactor_thread', 'run_reactor', 'stop_reactor',
]

logger = logging.getLogger(__name__)


# --------
# Startups
# --------

def run_startup(repositoryView):
    """
    Run all active startup items in `repositoryView`
    """
    started = set()
    attempted = set()
    for item in Startup.iterItems(repositoryView):
        item._start(attempted, started)


class Startup(schema.Item):
    """
    Subclass this & create parcel.xml instances for startup notifications
    """

    invoke = schema.One(schema.Text,
        doc="Full name of a class or function to import and run at startup"
    )

    active = schema.One(schema.Boolean,
        doc="Set to False to disable invocation of this item at startup",
        initialValue=True,
    )

    requires = schema.Sequence(
        doc="Startups that must run before this one",
        initialValue=[]
    )

    requiredBy = schema.Sequence(inverse=requires)

    def getTarget(self):
        """
        Import the object named by ``invoke`` and return it
        """
        return schema.importString(self.invoke)

    def invokeTarget(self, target):
        """
        Run the specified startup target in the current thread
        """
        target(self)

    def onStart(self):
        """
        Override this method in a subclass to receive the notification

        Note: you should *not* create or modify items in this method or code
        called from this method.  If you want to do that, you probably don't
        want to be using a Startup item.

        Also note that you should not call invoke this method via super()
        unless you want the default behavior (i.e., importing and running the
        ``invoke`` attribute) to occur.
        """
        self.invokeTarget(self.getTarget())

    def _start(self, attempted, started):
        """
        Handle inter-startup ordering and invoke onStart()
        """
        if self in started:
            return True
        elif not self.active or self in attempted:
            return False

        attempted.add(self)   # prevent multiple attempts to start this item
        canStart = True
        for item in self.requires:
            canStart = canStart and item._start(attempted, started)

        if canStart:
            try:
                self.onStart()
            except ImportError:
                logger.exception("Starting %s failed", self)
                return False
            else:
                started.add(self)
                return True

        return False


# -----------------
# Threads and Tasks
# -----------------

def fork_item(item_or_view, name=None, version=None):
    """
    Return a version of `item_or_view` that's in a new repository view

    This is a shortcut for creating a new view against the same repository
    as the original item or view, and then looking up the item or view by
    UUID in the new view.  It is typically used when starting a new thread or
    a task in Twisted, to ensure that it has its own logical view of the
    repository.  Note that you will usually want to commit() your existing
    view before calling this function, so the new view will see an up-to-date
    version of any items it loads.

    The optional `name` and `version` parameters are passed through to the
    repository's ``createView()`` method, so you can use them to give the
    view a name or set its target version.  Also, note that you can call
    ``fork_item()`` on a view just to create a new view for the same
    repository; you don't have to pass in an actual item.
    """
    view = item_or_view.itsView
    if view.repository is None:
        return item_or_view     # for NullRepositoryView, use old item

    new_view = view.repository.createView(
        name or getattr(item_or_view, 'itsName', None),
        version
        )
    item = new_view.findUUID(item_or_view.itsUUID)

    if item is None:
        raise ValueError(
            "%r not found in new view; commit() may be needed"
            % (item_or_view,)
        )
    return item


class Thread(Startup):
    """
    A Startup that runs its target in a new thread
    """

    def invokeTarget(self, target):
        """
        Run a target in a new RepositoryThread w/a new repository view
        """
        thread = RepositoryThread(
            name=str(self.itsPath), target=target, args=(fork_item(self),)
        )
        thread.setDaemon(True)   # main thread can exit even if this one hasn't
        thread.start()


class TwistedTask(Startup):
    """
    A Startup that runs its target in the reactor thread as a callback
    """

    def invokeTarget(self, target):
        """
        Run a target in the reactor thread w/a new repository view
        """
        run_reactor()
        reactor.callFromThread(target, fork_item(self))


class TaskRunner(object):
    """Manage a periodic task object

    All methods except ``_run()`` must be invoked from the reactor thread only!
    """

    _cache = WeakValueDictionary()     # global cache of runners by UUID
    pending = None
    running = True

    def __init__(self, item):
        self.uuid = item.itsUUID
        self._cache[self.uuid] = self
        self.subject = item.getTarget()(item)
        self.interval = item.interval
        self.runlock = threading.Lock()
        self.running = True

    def run_once(self, *args, **kwds):
        reactor.callInThread(self._run, *args, **kwds)

    def _run(self, *args, **kwds):
        """This should only be called from a pool thread"""
        self.runlock.acquire()
        try:
            if self.subject.run(*args, **kwds):  # task can stop by returning false
                reactor.callFromThread(self.reschedule_if_running)
        finally:
            self.runlock.release()

    def reschedule_if_running(self):
        if self.running:
            self.reschedule()

    def stop(self):
        self.running = False
        if self.pending and self.pending.active():
            self.pending.cancel()
        if TaskRunner._cache[self.uuid] is self:
            del TaskRunner._cache[self.uuid]

    def reschedule(self, interval=None):
        if interval is None:
            interval = self.interval
        else:
            self.interval = interval    # update the interval

        self.running = True

        if self.pending and self.pending.active():
            # cancel the pending call so we don't schedule multiples
            self.pending.cancel()

        self.pending = reactor.callLater(
            interval.days*86400 + interval.seconds + interval.microseconds/1e6,
            reactor.callInThread, self.run_once
        )



class PeriodicTask(TwistedTask):
    """
    A Startup that runs its target periodically
    """

    interval = schema.One(
        schema.TimeDelta,
        initialValue = datetime.timedelta(0),
    )

    run_at_startup = schema.One(
        schema.Boolean,
        initialValue = False
    )

    def onStart(self):
        """
        Start our wrapper in the reactor thread
        """
        run_at_startup = self.run_at_startup    # don't hold references to item
        interval = self.interval

        def start_running(runner):
            runner.reschedule(interval)
            if run_at_startup:
                runner.run_once()

        run_reactor()
        self._with_runner(start_running)

    def run_once(self, *args, **kwds):
        """Request to run the task once, immediately"""
        self._with_runner(lambda r: r.run_once(*args, **kwds))

    def stop(self):
        """Stop running the task until/unless reschedule() is called"""
        self._with_runner(lambda r: r.stop())

    def reschedule(self, interval=None):
        """Reschedule the next occurrence of the task"""
        if interval is None:
            interval = self.interval
        else:
            self.interval = interval
        self._with_runner(lambda r: r.reschedule(interval))

    def _with_runner(self, f):
        uuid = self.itsUUID
        def callback():
            try:
                runner = TaskRunner._cache[uuid]
            except KeyError:
                runner = TaskRunner(fork_item(self))
            f(runner)
        reactor.callFromThread(callback)





# ------------------
# Reactor Management
# ------------------

_reactor_thread = None


def get_reactor_thread():
    """
    Return the threading.thread running the Twisted reactor, or None
    """
    return _reactor_thread


def run_reactor(in_thread=True):
    """
    Safely run the Twisted reactor
    """
    global reactor
    global _reactor_thread

    from osaf.framework.twisted import TwistedThreadPool  # initializes threads
    from twisted.python import threadpool
    threadpool.ThreadPool = TwistedThreadPool.RepositoryThreadPool

    from twisted.internet import reactor

    if not in_thread:
        if reactor.running:
            raise AssertionError("Reactor is already running")
        # enable repeated reactor runs
        def _del_pool(): reactor.threadpool = None
        for evt in reactor.crash, reactor.disconnectAll, _del_pool:
            reactor.addSystemEventTrigger('during', 'shutdown', evt)
        reactor.run(0)
        return

    import sys

    if _reactor_thread is None:
        if threading.currentThread().getName() != "MainThread":
            raise AssertionError(
                "can't start reactor thread except from the main thread"
            )
        limbo = [1]
        reactor.addSystemEventTrigger('after', 'startup', limbo.pop)
        _reactor_thread = RepositoryThread(
            name="reactor", target=run_reactor, args=(False,)
        )
        _reactor_thread.setDaemon(True) # let main thread exit even if running
        _reactor_thread.start()

        while limbo and _reactor_thread.isAlive():
            pass   # wait for reactor to start or thread to die (e.g. w/error)

        if not _reactor_thread.isAlive():
            _reactor_thread = None


def stop_reactor():
    """
    Stop the Twisted reactor and wait for its thread to exit
    """

    global _reactor_thread
    from twisted.internet import reactor

    if reactor.running:
        reactor.callFromThread(reactor.stop)

    if _reactor_thread is not None:
        _reactor_thread.join()
        _reactor_thread = None


