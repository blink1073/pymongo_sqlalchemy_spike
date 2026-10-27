"""PEP-249 exception hierarchy for mongosql_dbapi."""


class Warning(Exception):
    """Important warning (e.g. type degradation during parameter rendering)."""


class Error(Exception):
    """Base class of all other DB-API exceptions."""


class InterfaceError(Error):
    """Error related to the database interface, not the database itself."""


class DatabaseError(Error):
    """Error related to the database server."""


class DataError(DatabaseError):
    """Error due to problems with processed data (out of range, divide by zero)."""


class OperationalError(DatabaseError):
    """Error related to the database's operation: connection lost, timeout, unreachable server."""


class IntegrityError(DatabaseError):
    """Relational integrity violation. Never raised by the read-only backend."""


class InternalError(DatabaseError):
    """Internal database error, e.g. an invalid cursor."""


class ProgrammingError(DatabaseError):
    """API misuse: bad SQL, wrong parameter count, operating on a closed connection."""


class NotSupportedError(DatabaseError):
    """An API or SQL feature is not supported — e.g. writes against a read-only backend."""
