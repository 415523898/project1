"""Active experiment accounting shared by manual and conversation tasks."""

import contextlib
import functools
import threading


class ExperimentGate:
    def __init__(self):
        self.lock = threading.Lock()
        self.active = 0

    @contextlib.contextmanager
    def slot(self):
        with self.lock:
            self.active += 1
        try:
            yield
        finally:
            with self.lock:
                self.active -= 1


EXPERIMENTS = ExperimentGate()


def experiment(function):
    @functools.wraps(function)
    def guarded(*args, **kwargs):
        with EXPERIMENTS.slot():
            return function(*args, **kwargs)

    return guarded
