# Spike summary: mongosql as a SQLAlchemy backend

## Verdict

Feasible for read-only SELECT workloads. A DB-API 2.0 driver and a SQLAlchemy 2.x dialect were implemented against the `py_mongosqltranslate` bindings and exercised end to end. A port of CPython's sqlite3 DB-API test suite passes, and SQLAlchemy Core queries round-trip with bound parameters and correct result types. The reviewer approved the spike with no critical findings.

## What was proven

- SQL SELECT statements translate and execute against MongoDB, including filters, ordering, limits, and queries with no table source.
- SQLAlchemy works on top of the driver for Core queries. Writes are refused by design, since mongosql translates SELECT statements only.
- The bindings build from source on Linux ARM64. The provided wheels are macOS-only, and the release build needs more memory than a small machine has.

## Key findings

- **MongoSQL has no bind parameters.** The driver renders parameters into the SQL text before translation. This works, but escaping outside the database is the riskiest part of the design for production use.
- **Result rows are namespaced** and need flattening before they look like normal SQL rows.
- **Schemas come from sampling.** A small sampler derives the typed schema catalog that translation needs; a schema-builder library exists but was not built in this spike.

## Limitations

1. Read-only, with no transaction semantics.
2. Datetime parameter values are not supported yet.
3. No reflection, so SQLAlchemy needs declared table metadata rather than autoload.
4. Cached schemas go stale after out-of-band schema changes.
5. Not safe for sharing connections across threads.

## Recommendations

1. Land the work: run the prepared commit commands in `.opencode/NOTES.md` from the workstation, then open the draft fork PR.
2. Ask for Linux wheels on PR #219 and a PyPI release, so future users skip the local Rust build.
3. Add reflection, then probe the ORM layer as the next feasibility question.
4. Push for grammar-level bind parameters, or document a datetime literal syntax, to remove the client-side escaping risk.
5. Compare the sampled schemas against the schema-builder library on a larger machine before trusting either at scale.
6. Benchmark translation overhead with caching on a realistic workload before drawing performance conclusions.
7. Decide where the driver lives before investing in hardening.
