"""Spike-specific cursor/connection behaviors beyond the ported CPython suite."""
from datetime import datetime

import pytest
from conftest import DB, MONGO_URI
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


def test_injected_catalog_skips_sampling(seeded_client, monkeypatch):
    # A catalog handed to connect() must be used as-is: sampling per
    # connection is exactly what injection exists to avoid.
    import mongosql_dbapi
    from mongosql_dbapi import connection as connection_module
    from mongosql_dbapi.catalog import build_catalog

    catalog = build_catalog(seeded_client, DB)

    def _no_sampling(*args, **kwargs):
        raise AssertionError("sampling ran although a catalog was injected")

    monkeypatch.setattr(connection_module, "build_catalog", _no_sampling)

    conn = mongosql_dbapi.connect(uri=MONGO_URI, database=DB, catalog=catalog)
    try:
        cur = conn.execute("SELECT name FROM test WHERE id = 1")
        assert cur.fetchall() == [("foo",)]
    finally:
        conn.close()


def test_injected_catalog_updates_stay_on_the_connection(seeded_client):
    # Contract: refresh_catalog() updates the connection's own catalog and
    # must not leak new collections into the caller's injected dict.
    import mongosql_dbapi
    from mongosql_dbapi.catalog import build_catalog

    catalog = build_catalog(seeded_client, DB)
    conn = mongosql_dbapi.connect(uri=MONGO_URI, database=DB, catalog=catalog)
    try:
        seeded_client[DB]["injected_catalog_fresh"].insert_one({"x": 1})
        conn.refresh_catalog()
        assert conn.execute(
            "SELECT x FROM injected_catalog_fresh").fetchall() == [(1,)]
        assert "injected_catalog_fresh" not in catalog[DB]
    finally:
        seeded_client[DB].drop_collection("injected_catalog_fresh")
        conn.close()


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
