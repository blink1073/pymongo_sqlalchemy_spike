import datetime
import time

import mongosql_dbapi as sqlite


def test_type_objects_are_distinct():
    assert sqlite.STRING != sqlite.NUMBER != sqlite.BINARY != sqlite.DATETIME != sqlite.ROWID


def test_type_object_equality_by_value_type_name():
    assert "str" in sqlite.STRING and sqlite.STRING == "str"
    assert sqlite.NUMBER == "int" and sqlite.NUMBER == "float"
    assert sqlite.DATETIME == "datetime"
    assert sqlite.BINARY == "bytes"
    assert sqlite.ROWID == "ObjectId"


def test_constructors():
    assert sqlite.Date(2024, 5, 6) == datetime.date(2024, 5, 6)
    assert sqlite.Time(7, 8, 9) == datetime.time(7, 8, 9)
    assert sqlite.Timestamp(2024, 5, 6, 7, 8, 9) == datetime.datetime(2024, 5, 6, 7, 8, 9)


def test_from_ticks():
    ticks = 1714979289.0
    assert sqlite.DateFromTicks(ticks) == datetime.date(*time.localtime(ticks)[:3])
    assert sqlite.TimeFromTicks(ticks) == datetime.time(*time.localtime(ticks)[3:5])
    assert sqlite.TimestampFromTicks(ticks) == datetime.datetime(*time.localtime(ticks)[:6])


def test_binary():
    assert sqlite.Binary(b"\x00\x01") == b"\x00\x01"
