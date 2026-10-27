"""mongosql_dbapi — PEP-249 (DB-API 2.0) driver for read-only MongoSQL over MongoDB."""
from .connection import Connection, connect
from .exceptions import (DatabaseError, DataError, Error, InterfaceError,
                         IntegrityError, InternalError, NotSupportedError,
                         OperationalError, ProgrammingError, Warning)
from .types import (BINARY, DATETIME, NUMBER, ROWID, STRING, Binary, Date,
                    DateFromTicks, Time, TimeFromTicks, Timestamp,
                    TimestampFromTicks)

apilevel = "2.0"
threadsafety = 1  # module shareable; connections are not guaranteed shareable
paramstyle = "pyformat"

__all__ = [
    "apilevel", "threadsafety", "paramstyle", "connect", "Connection",
    "Warning", "Error", "InterfaceError", "DatabaseError", "DataError",
    "OperationalError", "IntegrityError", "InternalError",
    "ProgrammingError", "NotSupportedError",
    "STRING", "BINARY", "NUMBER", "DATETIME", "ROWID",
    "Date", "Time", "Timestamp", "DateFromTicks", "TimeFromTicks",
    "TimestampFromTicks", "Binary",
]
