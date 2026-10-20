"""Keep a bounded multi-query metadata view on one SQLite read snapshot.

Savepoints nest inside a caller transaction without committing its pending work.
WAL readers do not block another connection from committing a newer version.
This is for read views; confirmation must still validate current revisions.
"""
from contextlib import contextmanager
from functools import wraps


@contextmanager
def read_snapshot(database):
    database.execute('SAVEPOINT template_ai_metadata_read')
    try:
        yield
    except BaseException:
        database.execute('ROLLBACK TO SAVEPOINT template_ai_metadata_read')
        raise
    finally:
        database.execute('RELEASE SAVEPOINT template_ai_metadata_read')


def snapshot_read(connection):
    def decorate(function):
        @wraps(function)
        def run(*args, **kwargs):
            with read_snapshot(connection(*args, **kwargs)):
                return function(*args, **kwargs)
        return run
    return decorate
