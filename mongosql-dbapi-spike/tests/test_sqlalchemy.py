"""Feasibility tests for the SQLAlchemy 2.x mongosql dialect."""
import datetime

import pytest
import sqlalchemy.exc
from sqlalchemy import (Column, Float, Integer, MetaData, String, Table,
                        create_engine, select, text)

from conftest import DB, MONGO_PORT


@pytest.fixture(scope="module")
def engine(seeded_client):
    return create_engine(f"mongosql://127.0.0.1:{MONGO_PORT}/{DB}")


def test_text_select_roundtrip(engine):
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT name FROM test WHERE id = 1")).fetchall()
    assert rows == [("foo",)]


def test_core_select_with_bound_parameters(engine):
    metadata = MetaData()
    test = Table("test", metadata, Column("id", Integer),
                 Column("name", String), Column("income", Float))
    stmt = (select(test.c.name)
            .where(test.c.income > 100)
            .order_by(test.c.name)
            .limit(2))
    with engine.connect() as conn:
        rows = conn.execute(stmt).fetchall()
    assert [r[0] for r in rows] == ["bar", "foo"]


def test_type_fidelity(engine):
    with engine.connect() as conn:
        row = conn.execute(text("SELECT i, f, s, b, n, d FROM types")).one()
    assert row == (42, 1.5, "text", True, None,
                   datetime.datetime(2024, 5, 6, 7, 8, 9))


def test_read_only_guard(engine):
    with engine.connect() as conn:
        with pytest.raises(sqlalchemy.exc.NotSupportedError):
            conn.execute(text("INSERT INTO test VALUES (1)"))


def test_transactions_are_noops(engine):
    # commit/rollback on the read-only backend must not raise
    with engine.connect() as conn:
        conn.commit()
        conn.rollback()
        rows = conn.execute(text("SELECT id FROM test WHERE id = 3")).fetchall()
    assert rows == [(3,)]
