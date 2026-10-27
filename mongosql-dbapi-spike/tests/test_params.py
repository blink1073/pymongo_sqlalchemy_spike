import pytest

from mongosql_dbapi.exceptions import NotSupportedError, ProgrammingError
from mongosql_dbapi.params import render_literal, render_parameters, statement_kind


def test_none_params_passthrough():
    assert render_parameters("SELECT 1", None) == "SELECT 1"


def test_renders_scalars():
    assert render_parameters(
        "SELECT * FROM t WHERE a = %(a)s", {"a": 1}) == "SELECT * FROM t WHERE a = 1"
    assert render_parameters("x = %(f)s", {"f": 1.5}) == "x = 1.5"
    assert render_parameters("x = %(s)s", {"s": "o'brien"}) == "x = 'o''brien'"
    assert render_parameters("x = %(n)s", {"n": None}) == "x = NULL"
    assert render_parameters("x = %(t)s", {"t": True}) == "x = TRUE"


def test_skips_string_literals_and_comments():
    sql = "SELECT '%(a)s' AS literal -- %(a)s\nFROM t /* %(a)s */ WHERE a = %(a)s"
    assert render_parameters(sql, {"a": 7}) == (
        "SELECT '%(a)s' AS literal -- %(a)s\nFROM t /* %(a)s */ WHERE a = 7")


def test_percent_escape():
    assert render_parameters("x = 3 %% 2 AND y = %(v)s", {"v": 2}) == (
        "x = 3 % 2 AND y = 2")


def test_missing_param_raises_programming_error():
    with pytest.raises(ProgrammingError):
        render_parameters("SELECT %(nope)s", {"a": 1})


def test_non_dict_params_raise():
    with pytest.raises(ProgrammingError):
        render_parameters("SELECT 1", (1,))
    with pytest.raises(ProgrammingError):
        render_parameters("SELECT 1", 42)


def test_unsupported_param_type():
    with pytest.raises(NotSupportedError):
        render_literal(object())


def test_statement_kind():
    assert statement_kind("  SELECT 1") == "select"
    assert statement_kind("WITH q AS (SELECT 1) SELECT * FROM q") == "select"
    assert statement_kind("insert into t values (1)") == "dml"
    assert statement_kind("DROP TABLE t") == "dml"
    assert statement_kind("SELEC 1") == "other"


def test_statement_kind_skips_leading_comments():
    # review finding 2: comment-hidden DML must still classify as "dml"
    assert statement_kind("-- c\nDELETE FROM t") == "dml"
    assert statement_kind("/* x */ DROP TABLE t") == "dml"
    assert statement_kind("-- c\n/* x */\n UPDATE t SET a = 1") == "dml"


def test_backtick_quoted_identifiers_untouched():
    # review finding 3: MongoSQL delimited identifiers accept backticks too
    sql = "SELECT * FROM `%(a)s`"
    assert render_parameters(sql, {"a": "injected"}) == sql


def test_non_finite_floats_rejected():
    # review suggestion 8: bare inf/nan parse as identifiers and confuse
    with pytest.raises(NotSupportedError):
        render_literal(float("inf"))
    with pytest.raises(NotSupportedError):
        render_literal(float("nan"))
