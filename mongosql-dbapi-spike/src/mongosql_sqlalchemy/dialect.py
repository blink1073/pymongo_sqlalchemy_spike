"""Minimal SQLAlchemy 2.x dialect over mongosql_dbapi (read-only SELECTs).

The backend has no transactions and no writes: begin/commit/rollback are
no-ops, and any DML/DDL statement is rejected by the DBAPI with
NotSupportedError.
"""
from sqlalchemy.engine import default


class MongoSQLDialect(default.DefaultDialect):
    name = "mongosql"
    driver = "mongosql"

    paramstyle = "pyformat"
    supports_alter = False
    supports_sane_rowcount = False
    supports_sane_multi_rowcount = False
    supports_sequences = False
    supports_native_boolean = True
    supports_statement_cache = False
    max_identifier_length = 255

    @classmethod
    def import_dbapi(cls):
        import mongosql_dbapi
        return mongosql_dbapi

    def create_connect_args(self, url, _translate_kw=None):
        host = url.host or "localhost"
        port = url.port or 27017
        opts = dict(url.query)
        opts.setdefault("uri", f"mongodb://{host}:{port}")
        opts.setdefault("database", url.database or "")
        return ([], opts)

    def get_isolation_level(self, dbapi_conn):
        return None

    def get_server_version_info(self, connection):
        # The bindings expose no server version; a constant keeps
        # version-gated SQLAlchemy features stable.
        return (1, 0, 0)

    # read-only backend: SQLAlchemy's transaction hooks are no-ops
    def do_begin(self, dbapi_connection):
        pass

    def do_commit(self, dbapi_connection):
        pass

    def do_rollback(self, dbapi_connection):
        pass

    def do_close(self, dbapi_connection):
        dbapi_connection.close()
