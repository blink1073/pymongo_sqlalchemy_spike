"""PEP-249 type objects and constructors for mongosql_dbapi."""
import datetime
import time


class DBAPITypeObject(frozenset):
    """PEP-249 singleton compared against the name of a value's type."""

    def __eq__(self, other):
        if isinstance(other, str):
            return other in self
        return frozenset.__eq__(self, other)

    def __ne__(self, other):
        return not self.__eq__(other)

    __hash__ = frozenset.__hash__


STRING = DBAPITypeObject(("str",))
BINARY = DBAPITypeObject(("bytes", "bytearray", "memoryview"))
NUMBER = DBAPITypeObject(("int", "float", "bool", "Decimal"))
DATETIME = DBAPITypeObject(("datetime", "date", "time", "timedelta"))
ROWID = DBAPITypeObject(("ObjectId",))

Date = datetime.date
Time = datetime.time
Timestamp = datetime.datetime


def DateFromTicks(ticks):
    return Date(*time.localtime(ticks)[:3])


def TimeFromTicks(ticks):
    return Time(*time.localtime(ticks)[3:5])


def TimestampFromTicks(ticks):
    return Timestamp(*time.localtime(ticks)[:6])


def Binary(value):
    return bytes(value)
