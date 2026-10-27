# mongosql as a SQLAlchemy backend — feasibility spike

**Verdict: feasible for read-only SELECT workloads.** A PEP-249 (DB-API 2.0) driver plus a
SQLAlchemy 2.x dialect were implemented on top of the `py_mongosqltranslate` bindings and
PyMongo; a port of CPython's `test_sqlite3/test_dbapi.py` passes, and Core `select()` /
`text()` queries round-trip through SQLAlchemy with bound parameters and correct types.

## Architecture

```
MongoSQL text ──► py_mongosqltranslate.MongoSqlTranslator
                      │  translate_query(db, sql, catalog) -> Translation
                      │    (target_db, target_collection, pipeline,
                      │     result_set_schema, select_order)
                      ▼
              pymongo aggregate(pipeline)          ◄── catalog: {db: {coll: $jsonSchema}}
                      │                                derived by a pure-Python sampler
                      ▼                                (mongosql_dbapi/catalog.py)
              rows are namespaced ({"" or "coll": {field: …}})
                      │  flattened via Translation.select_order
                      ▼
              PEP-249 Connection/Cursor  ──►  SQLAlchemy MongoSQLDialect
```

- **Translation** is pure Rust via the bindings (built from the vendored sdist — see below).
- **Execution** is ordinary PyMongo: the pipeline runs on `client[target_db][target_collection]`,
  or database-level `client[db].aggregate(...)` when `target_collection is None` (e.g. `SELECT 1`).
- **Schema catalog**: `py_schema_builder_library` would normally derive it; this spike uses a
  ~70-line pure-Python sampler (`catalog.py`) that infers `$jsonSchema` from up to N sampled
  documents, avoiding a second (heavy) Rust build. It is cached per connection; call
  `Connection.refresh_catalog()` after creating new collections.
- **Parameters**: the MongoSQL grammar has no bind-parameter tokens, so the DBAPI renders
  `%(name)s` placeholders client-side into typed literals with a quote/comment-aware scanner
  (`params.py`). `paramstyle` is `"pyformat"`.
- **Read-only**: `commit()`/`rollback()` are no-ops; any INSERT/UPDATE/DELETE/DDL raises
  `NotSupportedError`. `rowcount` is `-1` for SELECTs, `lastrowid` is `None`.

## Running it

```sh
# 1. one-off prerequisites
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal --default-toolchain stable
mkdir -p vendor && unzip -j -o ../mongosql-pythonbindings.zip \
    'mongosql-pythonbindings/wheels/py_mongosqltranslate-0.1.0.tar.gz' \
    'mongosql-pythonbindings/wheels/py_schema_builder_library-0.1.0.tar.gz' -d vendor/
tar xzf vendor/py_mongosqltranslate-0.1.0.tar.gz -C vendor/

# 2. venv, bindings, spike package
python3 -m venv .venv && .venv/bin/pip install -U pip
.venv/bin/pip install maturin pymongo sqlalchemy pytest
bash scripts/build-bindings.sh   # maturin develop (dev profile)
.venv/bin/pip install -e '.[dev]'

# 3. tests (the fixture starts a scratch mongod on 127.0.0.1:27217)
.venv/bin/python -m pytest tests -v
```

Note: the release-profile build is OOM-killed on a 3 GB machine; the dev profile builds in
about a minute (`scripts/build-bindings.sh` encodes the working recipe). The provided wheels
are `cp313-macosx_11_0_arm64` — unusable on this Linux aarch64 sandbox; only the sdists are.

## PEP-249 coverage

| Element | Status |
| --- | --- |
| `apilevel`, `threadsafety`, `paramstyle` | `"2.0"`, `1`, `"pyformat"` |
| `connect()` | `connect(uri, database, catalog=None, sample_size=100, **client_kwargs)`; fails fast via `ping` → `OperationalError` |
| Exception hierarchy | full: `Warning`/`Error`/`InterfaceError`/`DatabaseError`/`DataError`/`OperationalError`/`IntegrityError`/`InternalError`/`ProgrammingError`/`NotSupportedError` |
| `Connection.close/commit/rollback/cursor` | yes; commit/rollback no-ops (read-only) |
| sqlite3-style conveniences | `Connection.execute/executemany/executescript/create_function`, `in_transaction` (always `False`), `total_changes` (always `0`), context manager |
| `Cursor.description` | 7-tuples with bare column names, `type_code=None` (matches sqlite3) |
| `Cursor.rowcount` | `-1` for SELECTs (sqlite semantics) |
| `Cursor.fetchone/fetchmany/fetchall`, iteration | yes; `arraysize` respected, sqlite-compatible validation (TypeError/ValueError/OverflowError, non-deletable) |
| `Cursor.executemany` | SELECT → `ProgrammingError`; writes → `NotSupportedError`; non-iterable → `TypeError` |
| `Cursor.lastrowid` | `None` |
| `setinputsizes/setoutputsize` | no-ops |
| `callproc/nextset` | `NotSupportedError` |
| Type API | `STRING/BINARY/NUMBER/DATETIME/ROWID`, `Date/Time/Timestamp/*FromTicks/Binary` |

## Test porting map (CPython `test_sqlite3/test_dbapi.py`)

- **Ported near-verbatim** (`tests/test_dbapi.py`, upstream test names kept):
  - `ModuleTests`: apilevel/threadsafety/paramstyle + full exception-hierarchy checks.
  - `ConnectionTests`: commit/rollback (no-op success, incl. "after no changes"), `test_cursor`,
    `test_close`, `test_use_after_close` (all 10 surface points), `test_exceptions`,
    `test_connection_exceptions`, `test_drop_unused_refs` (50 instead of 500 queries),
    `test_in_transaction` (adapted: always `False`), `test_in_transaction_ro`, `test_failed_open`
    (adapted: unreachable URI instead of unwritable file).
  - `CursorTests`: `test_execute_illegal_sql` (adapted: `"SELEC 1"` parse error → `ProgrammingError`),
    `test_execute_multiple_statements`, `test_execute_wrong_sql_arg`, `test_execute_non_iterable`,
    `test_execute_wrong_no_of_args1` (adapted: empty in the port — pyformat dict binding has no
    positional count; extra dict keys are ignored, matching sqlite3's named-parameter semantics),
    `test_execute_wrong_no_of_args2/3`, `test_execute_param_list` (qmark → pyformat dict),
    `test_execute_dict_mapping*` (incl. `__missing__` dict subclass and all error variants),
    `test_close`, `test_rowcount_select` (adapted: `ORDER BY` instead of `UNION`),
    `test_rowcount_prefixed_with_comment` (adapted: comment-prefixed SELECT), `test_total_changes`
    (adapted: always 0), `test_fetch_iter` (adapted: PyMongo-seeded rows + `refresh_catalog`),
    `test_fetchone`, `test_fetchone_no_statement`, `test_array_size`, `test_invalid_array_size`,
    `test_fetchmany`, `test_invalid_fetchmany`, `test_fetchmany_kw_arg`, `test_fetchall`,
    `test_setinputsizes`, `test_setoutputsize*`, `test_cursor_connection`,
    `test_wrong_cursor_callable`, `test_same_query_in_multiple_cursors` (exercises the
    database-level aggregate), `test_lastrowid_is_none` (adapted from the lastrowid-on-INSERT group).
  - `ReadOnlyTests` (new class, not upstream): every write verb through `conn.execute` —
    INSERT/UPDATE/DELETE/CREATE/DROP, including DML hidden behind leading comments — raises
    `NotSupportedError`.
- **New** (`tests/test_connection_cursor.py`): `SELECT *` column set (all catalog fields incl.
  `_id`), `refresh_catalog()` picks up new collections, fetch-after-cursor-close, `callproc`/
  `nextset`/`executescript` rejection.
- **Dropped** (sqlite-specific, no mongosql equivalent):
  `test_module_constants` (SQLITE_*), version objects, `test_error_code_on_exception*`,
  `test_disallow_instantiation`, `test_complete_statement`, connection limits (`getlimit`/
  `setlimit`), `getconfig/setconfig`, re-`__init__` tests, isolation-level tests, `OpenTests`
  (file/URI paths), `SerializeTests`, `BlobTests`, `ThreadTests` (stress helpers),
  `ClosedConTests` (adapted instead: commit()/rollback() after close are unconditional no-ops
  on this backend; the other closed-connection surface points are covered in
  `test_use_after_close`), `ExtensionTests` (script-* family), `test_interrupt*`,
  `test_connect_positional_arguments`, `test_connection_resource_warning`,
  `test_connection_signature`, `UninitialisedConnectionTests`,
  `ConstructorTests` (functionally covered by `tests/test_types.py`), backup/autocommit/
  trace/progress/authorizer, write-based `rowcount`/`total_changes`/`executemany` data
  variants, `test_column_count` (ALTER TABLE), `test_cursor_wrong_class` (module-level
  `Cursor` not exported), positional-placeholder tests (`?`, `?1`) — MongoSQL has no
  positional binds.

## Known limitations

1. **Read-only.** Writes are rejected client-side; there is no transactional semantics to
   preserve, so commit/rollback are no-ops. SQLAlchemy transactions work (autobegin + no-op hooks).
2. **Client-side parameter rendering.** MongoSQL has no bind parameters. The renderer supports
   `None`/`bool`/`int`/`float`/`str`/`bytes` (hex string). **No datetime literals yet** — filter on
   datetimes by other means. Query text is scanned so placeholders inside literals/comments are
   untouched and `%%` escapes outside literals.
3. **Type degradations inherited from the bindings' BSON bridge**: `ObjectId` → hex string and
   exotic BSON → string *for literals embedded in pipelines*; result documents come back typed
   through PyMongo.
4. **`SELECT *` includes `_id`** (namespace-ordered first) — a MongoDB-ism; prefer explicit
   select lists for stable column sets.
5. **Mixed-type fields** follow MongoDB's cross-type sort/comparison order.
6. **Catalog staleness**: schemas are sampled once per connection; call `refresh_catalog()`
   after DDL performed out-of-band (e.g. seeding via PyMongo in tests). The sampler's typing
   rules (see `catalog.py` module docstring) map datetime→`date`, ObjectId→`objectId`,
   Decimal128→`decimal`, and degrade unrecognized BSON to `string`.
7. **No reflection yet** (`get_table_names`/`get_columns`/`autoload_with`) — Core `select()`
   works against explicitly declared `Table` metadata; reflection is the natural next step.
8. **threadsafety = 1** (conservative; pymongo clients are thread-safe, catalog state is not locked).
9. **Cursor.description exposes bare field names** (the internal namespace key is a flattening
   artifact, deliberately omitted — this deviates from the plan's reference code, which
   prefixed namespaced columns).

## Files

- `src/mongosql_dbapi/` — PEP-249 driver (`exceptions`, `types`, `params`, `catalog`, `connection`, `cursor`)
- `src/mongosql_sqlalchemy/dialect.py` — SQLAlchemy 2.x dialect (entry point `sqlalchemy.dialects:mongosql`)
- `tests/` — ported suite + spike-specific suites (mongod fixture on `127.0.0.1:27217`)
- `scripts/build-bindings.sh` — builds `py_mongosqltranslate` from the vendored sdist
