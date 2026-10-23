"""Keep a bounded multi-query metadata view on one SQLite read snapshot.

Savepoints nest inside a caller transaction without committing its pending work.
WAL readers do not block another connection from committing a newer version.
This is for read views; confirmation must still validate current revisions.
"""
from contextlib import contextmanager
from functools import wraps
from collections.abc import Callable, Iterator
from sqlite3 import Connection
from typing import ParamSpec, TypeVar

P = ParamSpec('P')
R = TypeVar('R')


@contextmanager
def read_snapshot(database: Connection) -> Iterator[None]:
    database.execute('SAVEPOINT template_ai_metadata_read')
    try:
        yield
    except BaseException:
        database.execute('ROLLBACK TO SAVEPOINT template_ai_metadata_read')
        raise
    finally:
        database.execute('RELEASE SAVEPOINT template_ai_metadata_read')


def snapshot_read(connection: Callable[..., Connection]) -> Callable[[Callable[P, R]], Callable[P, R]]:
    def decorate(function: Callable[P, R]) -> Callable[P, R]:
        @wraps(function)
        def run(*args: P.args, **kwargs: P.kwargs) -> R:
            with read_snapshot(connection(*args, **kwargs)):
                return function(*args, **kwargs)
        return run
    return decorate
