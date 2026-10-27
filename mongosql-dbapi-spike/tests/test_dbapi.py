"""Port of CPython Lib/test/test_sqlite3/test_dbapi.py for the read-only
mongosql backend.

Test names mirror upstream. Where the read-only nature or the mongosql
dialect forces a change, the adaptation is noted in a comment on the test;
sqlite-specific groups (SQLITE_* constants, limits, blobs, backup, serialize,
statement splitting, isolation levels, OpenTests) are dropped — the full
ported/adapted/dropped mapping lives in README.md.
"""
import pytest

import mongosql_dbapi as sqlite
from conftest import COLL, DB


# ---------------------------------------------------------------------------
# ModuleTests
# ---------------------------------------------------------------------------
class ModuleTests:
    def test_api_level(self):
        assert sqlite.apilevel == "2.0"

    def test_thread_safety(self):
        assert sqlite.threadsafety in {0, 1, 3}

    def test_param_style(self):
        assert sqlite.paramstyle == "pyformat"  # adapted: pyformat, not qmark

    def test_warning(self):
        assert issubclass(sqlite.Warning, Exception)

    def test_error(self):
        assert issubclass(sqlite.Error, Exception)

    def test_interface_error(self):
        assert issubclass(sqlite.InterfaceError, sqlite.Error)

    def test_database_error(self):
        assert issubclass(sqlite.DatabaseError, sqlite.Error)

    def test_data_error(self):
        assert issubclass(sqlite.DataError, sqlite.DatabaseError)

    def test_operational_error(self):
        assert issubclass(sqlite.OperationalError, sqlite.DatabaseError)

    def test_integrity_error(self):
        assert issubclass(sqlite.IntegrityError, sqlite.DatabaseError)

    def test_internal_error(self):
        assert issubclass(sqlite.InternalError, sqlite.DatabaseError)

    def test_programming_error(self):
        assert issubclass(sqlite.ProgrammingError, sqlite.DatabaseError)

    def test_not_supported_error(self):
        assert issubclass(sqlite.NotSupportedError, sqlite.DatabaseError)


# ---------------------------------------------------------------------------
# ConnectionTests
# ---------------------------------------------------------------------------
class ConnectionTests:
    def test_commit(self, conn):
        conn.commit()

    def test_commit_after_no_changes(self, conn):
        # A commit should also work when no changes were made to the database.
        conn.commit()
        conn.commit()

    def test_rollback(self, conn):
        conn.rollback()

    def test_rollback_after_no_changes(self, conn):
        # A rollback should also work when no changes were made to the database.
        conn.rollback()
        conn.rollback()

    def test_cursor(self, conn):
        conn.cursor()

    def test_failed_open(self):
        # adapted: unreachable server instead of an unwritable file path;
        # short timeouts keep the failure fast.
        with pytest.raises(sqlite.OperationalError):
            sqlite.connect(
                uri="mongodb://127.0.0.1:1/?serverSelectionTimeoutMS=250&connectTimeoutMS=250",
                database=DB)

    def test_close(self, conn):
        conn.close()

    def test_use_after_close(self, conn):
        cu = conn.cursor()
        res = cu.execute("SELECT 1")
        conn.close()
        with pytest.raises(sqlite.ProgrammingError):
            res.fetchall()
        with pytest.raises(sqlite.ProgrammingError):
            cu.execute("SELECT 1")
        with pytest.raises(sqlite.ProgrammingError):
            cu.executemany("SELECT 1", [])
        with pytest.raises(sqlite.ProgrammingError):
            conn.execute("SELECT 1")
        with pytest.raises(sqlite.ProgrammingError):
            conn.executemany("SELECT 1", [])
        with pytest.raises(sqlite.ProgrammingError):
            conn.executescript("SELECT 1")
        with pytest.raises(sqlite.ProgrammingError):
            conn.create_function("t", 1, lambda x: x)
        with pytest.raises(sqlite.ProgrammingError):
            conn.cursor()
        with pytest.raises(sqlite.ProgrammingError):
            with conn:
                pass

    def test_exceptions(self, conn):
        # Optional DB-API extension.
        assert conn.Warning is sqlite.Warning
        assert conn.Error is sqlite.Error
        assert conn.InterfaceError is sqlite.InterfaceError
        assert conn.DatabaseError is sqlite.DatabaseError
        assert conn.DataError is sqlite.DataError
        assert conn.OperationalError is sqlite.OperationalError
        assert conn.IntegrityError is sqlite.IntegrityError
        assert conn.InternalError is sqlite.InternalError
        assert conn.ProgrammingError is sqlite.ProgrammingError
        assert conn.NotSupportedError is sqlite.NotSupportedError

    def test_in_transaction(self, conn):
        # adapted: the read-only backend is never in a transaction
        cu = conn.cursor()
        assert conn.in_transaction is False
        cu.execute("SELECT name FROM test WHERE id = 1")
        cu.fetchone()
        assert conn.in_transaction is False
        conn.commit()
        assert conn.in_transaction is False

    def test_in_transaction_ro(self, conn):
        with pytest.raises(AttributeError):
            conn.in_transaction = True

    def test_connection_exceptions(self, conn):
        exceptions = [
            "DataError",
            "DatabaseError",
            "Error",
            "IntegrityError",
            "InterfaceError",
            "NotSupportedError",
            "OperationalError",
            "ProgrammingError",
            "Warning",
        ]
        for exc in exceptions:
            assert hasattr(conn, exc)
            assert getattr(sqlite, exc) is getattr(conn, exc)

    def test_drop_unused_refs(self, conn):
        # adapted: 50 (not 500) SELECTs to keep the suite quick
        for n in range(50):
            cu = conn.execute(f"SELECT {n}")
            assert cu.fetchone()[0] == n


# ---------------------------------------------------------------------------
# CursorTests
# ---------------------------------------------------------------------------
class CursorTests:
    def test_execute_illegal_sql(self, conn):
        # adapted: "SELEC 1" (parse error -> ProgrammingError); sqlite detects
        # an unknown column at prepare time, which mongosql cannot do up front.
        with pytest.raises(sqlite.ProgrammingError):
            conn.execute("SELEC 1")

    def test_execute_multiple_statements(self, conn):
        # adapted: mongosql has no multi-statement support; a syntax error
        # surfaces as ProgrammingError.
        with pytest.raises(sqlite.ProgrammingError):
            conn.execute("select 1; select 2")

    def test_execute_wrong_sql_arg(self, conn):
        with pytest.raises(TypeError):
            conn.execute(42)

    def test_execute_non_iterable(self, conn):
        with pytest.raises(sqlite.ProgrammingError) as cm:
            conn.execute("SELECT id FROM test WHERE id = %(id)s", 42)
        assert str(cm.value) == "parameters are of unsupported type"

    def test_execute_wrong_no_of_args1(self, conn):
        # adapted: dropped positional too-many-args case — pyformat dicts have
        # no positional count; extra dict keys are ignored like sqlite's named
        # parameters.
        pass

    def test_execute_wrong_no_of_args2(self, conn):
        # too little parameters
        with pytest.raises(sqlite.ProgrammingError):
            conn.execute("SELECT id FROM test WHERE id = %(id)s", {})

    def test_execute_wrong_no_of_args3(self, conn):
        # no parameters at all, parameters are needed
        with pytest.raises(sqlite.ProgrammingError):
            conn.execute("SELECT id FROM test WHERE id = %(id)s")

    def test_execute_param_list(self, conn):
        # adapted: qmark positional -> pyformat named
        cur = conn.execute("SELECT name FROM test WHERE id = %(id)s", {"id": 1})
        assert cur.fetchone()[0] == "foo"

    def test_execute_dict_mapping(self, conn):
        cur = conn.execute(
            "SELECT name FROM test WHERE name = %(name)s", {"name": "foo"})
        assert cur.fetchone()[0] == "foo"

    def test_execute_dict_mapping_mapping(self, conn):
        class D(dict):
            def __missing__(self, key):
                return "foo"

        cur = conn.execute(
            "SELECT name FROM test WHERE name = %(name)s", D())
        assert cur.fetchone()[0] == "foo"

    def test_execute_dict_mapping_too_little_args(self, conn):
        with pytest.raises(sqlite.ProgrammingError):
            conn.execute(
                "SELECT name FROM test WHERE name = %(name)s AND id = %(id)s",
                {"name": "foo"})

    def test_execute_dict_mapping_no_args(self, conn):
        with pytest.raises(sqlite.ProgrammingError):
            conn.execute("SELECT name FROM test WHERE name = %(name)s")

    def test_execute_dict_mapping_unnamed(self, conn):
        # mongosql has no positional placeholders; the parser rejects "?"
        with pytest.raises(sqlite.ProgrammingError):
            conn.execute("SELECT name FROM test WHERE name = ?", {"name": "foo"})

    def test_close(self, conn):
        conn.cursor().close()

    def test_rowcount_select(self, conn):
        # adapted: upstream uses "select 5 union select 6" — UNION support is
        # not assumed; SELECT rowcount is -1 either way.
        cur = conn.execute("SELECT id FROM test ORDER BY id")
        assert cur.rowcount == -1

    def test_rowcount_prefixed_with_comment(self, conn):
        # adapted: read-only — verify comments don't break execution
        cur = conn.execute("""
            -- foo
            SELECT id FROM test
        """)
        assert cur.rowcount == -1
        assert cur.fetchall() == [(1,), (2,), (3,)]

    def test_total_changes(self, conn):
        # adapted: the read-only backend never changes anything
        assert conn.total_changes == 0

    def test_execute_many_sequence(self, conn):
        # adapted: read-only backend refuses DML regardless of sequence shape
        with pytest.raises(sqlite.NotSupportedError):
            conn.executemany(
                "INSERT INTO test(id) VALUES (%(v)s)", [(x,) for x in range(3)])

    def test_execute_many_wrong_sql_arg(self, conn):
        with pytest.raises(TypeError):
            conn.executemany(42, [(3,)])

    def test_execute_many_select(self, conn):
        with pytest.raises(sqlite.ProgrammingError):
            conn.executemany("SELECT %(p)s", [(3,)])

    def test_execute_many_not_iterable(self, conn):
        with pytest.raises(TypeError):
            conn.executemany("INSERT INTO test(id) VALUES (%(v)s)", 42)

    def test_fetch_iter(self, conn, seeded_client):
        # Optional DB-API extension. adapted: extra rows seeded via PyMongo
        # (SQL is read-only) in a dedicated collection, requiring a catalog
        # refresh since the collection did not exist at connect time.
        seeded_client[DB]["itertest"].insert_many([{"id": 5}, {"id": 6}])
        conn.refresh_catalog()
        cur = conn.execute("SELECT id FROM itertest ORDER BY id")
        lst = [row[0] for row in cur]
        assert lst == [5, 6]

    def test_fetchone(self, conn):
        cur = conn.execute("SELECT name FROM test ORDER BY id")
        assert cur.fetchone()[0] == "foo"
        assert cur.fetchone()[0] == "bar"
        assert cur.fetchone()[0] == "baz"
        assert cur.fetchone() is None

    def test_fetchone_no_statement(self, conn):
        cur = conn.cursor()
        assert cur.fetchone() is None

    def test_array_size(self, conn):
        # must default to 1
        cur = conn.cursor()
        assert cur.arraysize == 1
        # now set to 2
        cur.arraysize = 2
        # now make the query return 2 rows from a table of 3 rows
        cur.execute("SELECT name FROM test")
        res = cur.fetchmany()
        assert len(res) == 2

    def test_invalid_array_size(self, conn):
        UINT32_MAX = (1 << 32) - 1

        def setter(value):
            conn.cursor().arraysize = value

        with pytest.raises(TypeError):
            setter(1.0)
        with pytest.raises(ValueError):
            setter(-3)
        with pytest.raises(OverflowError):
            setter(UINT32_MAX + 1)
        with pytest.raises(OverflowError):
            setter(2 ** 1000)
        with pytest.raises(ValueError):
            setter(-(2 ** 1000))
        with pytest.raises(AttributeError):
            delattr(conn.cursor(), "arraysize")

    def test_fetchmany(self, conn):
        # no active SQL statement
        cur = conn.cursor()
        assert cur.fetchmany() == []
        assert cur.fetchmany(1000) == []

        # test default parameter
        cur = conn.execute("SELECT name FROM test")
        assert len(cur.fetchmany()) == 1

        # test when the number of requested rows exceeds the actual count
        cur = conn.execute("SELECT name FROM test")
        assert len(cur.fetchmany(100)) == 3
        assert cur.fetchmany(100) == []

        # test when size = 0
        cur = conn.execute("SELECT name FROM test")
        assert cur.fetchmany(0) == []
        assert len(cur.fetchmany(100)) == 3

    def test_invalid_fetchmany(self, conn):
        UINT32_MAX = (1 << 32) - 1
        cur = conn.cursor()
        with pytest.raises(TypeError):
            cur.fetchmany(1.0)
        with pytest.raises(ValueError):
            cur.fetchmany(-3)
        with pytest.raises(OverflowError):
            cur.fetchmany(UINT32_MAX + 1)

    def test_fetchmany_kw_arg(self, conn):
        cur = conn.execute("SELECT name FROM test")
        assert len(cur.fetchmany(size=100)) == 3

    def test_fetchall(self, conn):
        cur = conn.execute("SELECT name FROM test")
        assert len(cur.fetchall()) == 3
        assert cur.fetchall() == []

    def test_setinputsizes(self, conn):
        conn.cursor().setinputsizes([3, 4, 5])

    def test_setoutputsize(self, conn):
        conn.cursor().setoutputsize(5, 0)

    def test_setoutputsize_no_column(self, conn):
        conn.cursor().setoutputsize(42)

    def test_cursor_connection(self, conn):
        # Optional DB-API extension.
        assert conn.cursor().connection is conn

    def test_wrong_cursor_callable(self, conn):
        with pytest.raises(TypeError):
            conn.cursor(lambda: None)

    def test_same_query_in_multiple_cursors(self, conn):
        # adapted: exercises the database-level aggregate (no collection)
        cursors = [conn.execute("SELECT 1") for _ in range(3)]
        for cu in cursors:
            assert cu.fetchall() == [(1,)]

    def test_lastrowid_is_none(self, conn):
        # adapted: the upstream lastrowid-on-INSERT group is write-based;
        # the read-only backend reports None.
        assert conn.execute("SELECT 1").lastrowid is None


# ---------------------------------------------------------------------------
# ReadOnlyTests — the spike's core invariant (plan Tasks 7/8): every write
# verb through the SQL surface is refused with NotSupportedError.
# ---------------------------------------------------------------------------
class ReadOnlyTests:
    def test_execute_write_verbs_raise_not_supported(self, conn):
        for sql in ("INSERT INTO test VALUES (1)",
                    "UPDATE test SET id = 2",
                    "DELETE FROM test",
                    "CREATE TABLE t (x int)",
                    "DROP TABLE test",
                    # review finding 2: DML hidden behind leading comments
                    "-- c\nDELETE FROM test",
                    "/* x */ DROP TABLE test"):
            with pytest.raises(sqlite.NotSupportedError):
                conn.execute(sql)
