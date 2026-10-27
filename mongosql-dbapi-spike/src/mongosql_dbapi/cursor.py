"""PEP-249 Cursor: translates MongoSQL and streams flattened result rows."""
from itertools import islice

from . import exceptions as exc
from .params import render_parameters, statement_kind


def _dig(doc, path):
    """Walk a dotted field path inside a namespaced result document."""
    cur = doc
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


class Cursor:
    def __init__(self, connection):
        self._conn = connection
        self._pymongo_cursor = None
        self._select_order = None
        self._description = None
        self.rowcount = -1
        self._arraysize = 1
        self._closed = False

    # -- attributes ---------------------------------------------------
    @property
    def arraysize(self):
        return self._arraysize

    @arraysize.setter
    def arraysize(self, value):
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError("arraysize must be an integer")
        if value < 0:
            raise ValueError("arraysize must be non-negative")
        if value >= 1 << 32:
            raise OverflowError("arraysize too large")
        self._arraysize = value

    @arraysize.deleter
    def arraysize(self):
        raise AttributeError("arraysize attribute cannot be deleted")

    @property
    def description(self):
        return self._description

    @property
    def connection(self):
        return self._conn

    @property
    def lastrowid(self):
        return None  # read-only backend: no inserts

    # -- lifecycle -----------------------------------------------------
    def close(self):
        self._closed = True
        self._pymongo_cursor = None

    def _check_open(self):
        if self._closed:
            raise exc.ProgrammingError("Cannot operate on a closed cursor.")
        # A cursor created before its connection closed must also fail
        # (pymongo buffers aggregate results, so iteration would otherwise
        # happily serve data from a closed connection).
        self._conn._check_open()

    # -- execution ------------------------------------------------------
    def execute(self, sql, parameters=None):
        self._conn._check_open()
        self._check_open()
        if not isinstance(sql, str):
            raise TypeError("operation must be a string")
        rendered = render_parameters(sql, parameters)
        kind = statement_kind(rendered)
        if kind == "dml":
            verb = rendered.lstrip(" (").split(None, 1)[0].upper()
            raise exc.NotSupportedError(
                f"mongosql is read-only: {verb} statements are not supported")
        try:
            translation = self._conn._translate(rendered)
        except ValueError as err:
            raise exc.ProgrammingError(str(err)) from err
        self._pymongo_cursor = self._conn._run(translation)
        self._select_order = translation.select_order
        self._description = [
            (field, None, None, None, None, None, None)
            for _, field in self._select_order
        ]
        self.rowcount = -1
        return self

    def executemany(self, sql, seq_of_parameters):
        self._conn._check_open()
        self._check_open()
        if not isinstance(sql, str):
            raise TypeError("operation must be a string")
        try:
            iter(seq_of_parameters)
        except TypeError:
            raise TypeError("seq_of_parameters must be iterable") from None
        kind = statement_kind(sql)
        if kind == "select":
            raise exc.ProgrammingError(
                "executemany() cannot execute SELECT statements")
        raise exc.NotSupportedError(
            "mongosql is read-only: executemany() of write statements is not supported")

    # -- results --------------------------------------------------------
    def _flatten(self, doc):
        return tuple(_dig(doc.get(ns, {}), field)
                     for ns, field in self._select_order)

    def fetchone(self):
        self._check_open()
        if self._pymongo_cursor is None:
            return None
        for doc in self._pymongo_cursor:
            return self._flatten(doc)
        return None

    def fetchmany(self, size=None):
        self._check_open()
        if size is None:
            size = self._arraysize
        if isinstance(size, bool) or not isinstance(size, int):
            raise TypeError("size must be an integer")
        if size < 0:
            raise ValueError("size must be non-negative")
        if size >= 1 << 32:
            raise OverflowError("size too large")
        if self._pymongo_cursor is None:
            return []
        return [self._flatten(d) for d in islice(self._pymongo_cursor, size)]

    def fetchall(self):
        self._check_open()
        if self._pymongo_cursor is None:
            return []
        return [self._flatten(d) for d in self._pymongo_cursor]

    def __iter__(self):
        self._check_open()
        return self

    def __next__(self):
        self._check_open()
        row = self.fetchone()
        if row is None:
            raise StopIteration
        return row

    # -- PEP-249 optional/unsupported ------------------------------------
    def setinputsizes(self, sizes):
        pass

    def setoutputsize(self, size, column=None):
        pass

    def callproc(self, procname, parameters=None):
        raise exc.NotSupportedError("callproc() is not supported by mongosql")

    def nextset(self):
        raise exc.NotSupportedError("nextset() is not supported by mongosql")
