"""Client-side rendering of pyformat bind parameters into MongoSQL text.

MongoSQL has no bind-parameter syntax, so ``%(name)s`` placeholders are
rendered into typed SQL literals before translation. The scanner only
replaces placeholders outside string literals, quoted identifiers, and
comments.
"""
import re

from .exceptions import NotSupportedError, ProgrammingError

_TOKEN = re.compile(r"%(?:\(([^)]*)\)s|%)")
_DML_PREFIXES = frozenset((
    "INSERT", "UPDATE", "DELETE", "REPLACE", "MERGE", "TRUNCATE", "CREATE",
    "DROP", "ALTER", "GRANT", "REVOKE", "CALL", "EXECUTE", "VACUUM", "ATTACH",
    "DETACH",
))
_FIRST_WORD = re.compile(r"\s*\(?\s*([A-Za-z]+)")


def _skip_leading_comments(sql):
    """Return `sql` with any leading -- or /* */ comments stripped."""
    i = 0
    while True:
        if sql.startswith("--", i):
            end = sql.find("\n", i)
            i = len(sql) if end == -1 else end + 1
        elif sql.startswith("/*", i):
            end = sql.find("*/", i + 2)
            i = len(sql) if end == -1 else end + 2
        else:
            return sql[i:]


def statement_kind(sql):
    """Classify rendered SQL: 'select', 'dml' (writes/DDL), or 'other'."""
    match = _FIRST_WORD.match(_skip_leading_comments(sql))
    if not match:
        return "other"
    word = match.group(1).upper()
    if word in ("SELECT", "WITH"):
        return "select"
    if word in _DML_PREFIXES:
        return "dml"
    return "other"


def render_parameters(sql, parameters):
    """Return `sql` with every %(name)s outside quotes/comments rendered."""
    if parameters is None:
        return sql
    if isinstance(parameters, (tuple, list)):
        raise ProgrammingError("pyformat paramstyle takes a dict of parameters")
    if not isinstance(parameters, dict):
        raise ProgrammingError("parameters are of unsupported type")
    out = []
    i, n = 0, len(sql)
    while i < n:
        ch = sql[i]
        if ch in ("'", '"', '`'):  # literals, quoted identifiers, backtick
            # identifiers — MongoSQL delimited identifiers accept both
            # double quotes and backticks; doubled quote escapes a quote
            j = i + 1
            while j < n:
                if sql[j] == ch:
                    if j + 1 < n and sql[j + 1] == ch:
                        j += 2
                        continue
                    break
                j += 1
            out.append(sql[i:j + 1])
            i = j + 1
        elif sql.startswith("--", i):
            j = sql.find("\n", i)
            j = n if j == -1 else j
            out.append(sql[i:j])
            i = j
        elif sql.startswith("/*", i):
            j = sql.find("*/", i + 2)
            j = n if j == -1 else j + 2
            out.append(sql[i:j])
            i = j
        elif ch == "%":
            m = _TOKEN.match(sql, i)
            if m is None:  # stray % — let the parser reject it
                out.append(ch)
                i += 1
            elif m.group(1) is None:  # %% escape
                out.append("%")
                i += 2
            else:
                name = m.group(1)
                try:
                    value = parameters[name]  # honors dict subclasses' __missing__
                except KeyError:
                    raise ProgrammingError(
                        f"missing parameter {name!r}") from None
                out.append(render_literal(value))
                i = m.end()
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def render_literal(value):
    """Render one Python value as a MongoSQL literal."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise NotSupportedError(
                "cannot render non-finite float as a MongoSQL literal")
        return repr(value)
    if isinstance(value, str):
        return "'" + value.replace("'", "''") + "'"
    if isinstance(value, bytes):
        return "'" + value.hex() + "'"  # compared as a string; documented limitation
    raise NotSupportedError(
        f"cannot render parameter of type {type(value).__name__} as a MongoSQL literal")
