"""PEP-249 Connection over PyMongo + the mongosql translator (read-only)."""
from pymongo import MongoClient
from pymongo.errors import (AutoReconnect, ConnectionFailure, NetworkTimeout,
                            OperationFailure, ServerSelectionTimeoutError)

from . import exceptions as exc
from .catalog import build_catalog
from .cursor import Cursor

_CONNECT_ERRORS = (ConnectionFailure, ServerSelectionTimeoutError, AutoReconnect,
                   NetworkTimeout)


class Connection:
    """Read-only connection: commit()/rollback() are documented no-ops."""

    def __init__(self, uri="mongodb://localhost:27017", database=None,
                 catalog=None, sample_size=100, ping=True, **client_kwargs):
        try:
            self._client = MongoClient(uri, **client_kwargs)
            if ping:
                self._client.admin.command("ping")
        except _CONNECT_ERRORS as err:
            raise exc.OperationalError(f"cannot connect to {uri}: {err}") from err
        except ValueError as err:  # malformed URI string
            raise exc.OperationalError(f"invalid MongoDB URI {uri!r}: {err}") from err
        self._uri = uri
        self._database = database
        self._sample_size = sample_size
        self._catalog = ({db: dict(colls) for db, colls in catalog.items()}
                         if catalog else {})
        self._closed = False
        self._translator = None

    # -- PEP-249 surface --------------------------------------------
    def close(self):
        self._closed = True
        self._client.close()

    def commit(self):
        pass  # read-only backend: nothing to commit

    def rollback(self):
        pass  # read-only backend: nothing to roll back

    def cursor(self):
        self._check_open()
        return Cursor(self)

    # -- sqlite3-style conveniences (ported tests rely on them) ------
    def execute(self, sql, parameters=None):
        cur = self.cursor()
        return cur.execute(sql, parameters)

    def executemany(self, sql, seq):
        cur = self.cursor()
        return cur.executemany(sql, seq)

    def executescript(self, sql):
        self._check_open()
        raise exc.NotSupportedError("executescript() is not supported by mongosql")

    def create_function(self, *args, **kwargs):
        self._check_open()
        raise exc.NotSupportedError("create_function() is not supported by mongosql")

    @property
    def in_transaction(self):
        return False

    @property
    def total_changes(self):
        return 0

    def __enter__(self):
        self._check_open()
        return self

    def __exit__(self, *args):
        return None

    # exception attributes mirror the module (sqlite3-compatible)
    Warning = exc.Warning
    Error = exc.Error
    InterfaceError = exc.InterfaceError
    DatabaseError = exc.DatabaseError
    DataError = exc.DataError
    OperationalError = exc.OperationalError
    IntegrityError = exc.IntegrityError
    InternalError = exc.InternalError
    ProgrammingError = exc.ProgrammingError
    NotSupportedError = exc.NotSupportedError

    # -- internals used by Cursor ------------------------------------
    def _check_open(self):
        if self._closed:
            raise exc.ProgrammingError("Cannot operate on a closed connection.")

    def refresh_catalog(self):
        """Re-sample every collection in the current database."""
        self._catalog[self._database] = build_catalog(
            self._client, self._database, sample_size=self._sample_size)[
                self._database]

    def _translate(self, sql):
        self._check_open()
        if self._translator is None:
            from py_mongosqltranslate import MongoSqlTranslator
            self._translator = MongoSqlTranslator()
        if not self._database:
            raise exc.ProgrammingError(
                "no database was provided to connect(); pass database=...")
        db = self._database
        if db not in self._catalog:
            self._catalog[db] = build_catalog(
                self._client, db, sample_size=self._sample_size)[db]
        try:
            return self._translator.translate_query(db, sql, self._catalog)
        except (TypeError, KeyError) as err:  # malformed catalog edge cases
            raise exc.ProgrammingError(str(err)) from err

    def _run(self, translation):
        try:
            if translation.target_collection is None:
                return self._client[translation.target_db].aggregate(
                    translation.pipeline)
            return self._client[translation.target_db][
                translation.target_collection].aggregate(translation.pipeline)
        except _CONNECT_ERRORS as err:
            raise exc.OperationalError(str(err)) from err
        except OperationFailure as err:
            raise exc.DatabaseError(str(err)) from err


def connect(uri="mongodb://localhost:27017", database=None, catalog=None,
            sample_size=100, **client_kwargs):
    """Connect to MongoDB and return a PEP-249 Connection."""
    return Connection(uri=uri, database=database, catalog=catalog,
                      sample_size=sample_size, **client_kwargs)
