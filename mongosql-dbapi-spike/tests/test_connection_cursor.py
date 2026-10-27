"""Spike-specific cursor/connection behaviors beyond the ported CPython suite."""
from datetime import datetime

import pytest
from conftest import DB
from mongosql_dbapi.exceptions import NotSupportedError, ProgrammingError


def test_select_star_includes_all_catalog_fields(conn):
    cur = conn.execute("SELECT * FROM test ORDER BY id")
    names = [d[0] for d in cur.description]
    assert {"_id", "id", "name", "income", "unique_test"} <= set(names)
    assert all(len(d) == 7 for d in cur.description)


def test_refresh_catalog_picks_up_new_collections(conn, seeded_client):
    seeded_client[DB]["fresh"].insert_one({"x": 1})
    conn.refresh_catalog()
    cur = conn.execute("SELECT x FROM fresh")
    assert cur.fetchall() == [(1,)]


def test_execute_without_database_raises_programming_error(seeded_client):
    # review finding 4: no raw TypeError may leak from a missing database
    import mongosql_dbapi
    connection = mongosql_dbapi.connect(uri="mongodb://127.0.0.1:27217")
    try:
        with pytest.raises(ProgrammingError):
            connection.execute("SELECT 1")
    finally:
        connection.close()


def test_sampler_types_datetime_as_date(seeded_client):
    # review finding 6: BSON datetime must not fall into the string fallback
    from mongosql_dbapi.catalog import infer_schema
    schema = infer_schema([{"d": datetime(2024, 5, 6)}])["$jsonSchema"]
    assert schema["properties"]["d"] == {"bsonType": "date"}


def test_fetch_after_cursor_close(conn):
    cur = conn.execute("SELECT name FROM test")
    cur.close()
    with pytest.raises(ProgrammingError):
        cur.fetchone()
    with pytest.raises(ProgrammingError):
        cur.fetchall()


def test_unsupported_cursor_apis(conn):
    with pytest.raises(NotSupportedError):
        conn.cursor().callproc("proc")
    with pytest.raises(NotSupportedError):
        conn.cursor().nextset()
    with pytest.raises(NotSupportedError):
        conn.executescript("SELECT 1")
