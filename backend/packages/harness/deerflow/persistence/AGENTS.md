# Persistence lifecycle

Postgres bootstrap owns its session-scoped advisory lock until `pg_advisory_unlock` completes. Drain that unlock across host cancellation before leaving the SQLAlchemy connection context; repeated cancellation must not return a pooled session while it still holds the bootstrap mutex. Ordinary database errors remain best-effort and are logged.

Acquire that lock by polling `pg_try_advisory_lock`, never with a blocking `pg_advisory_lock`: the app engine's asyncpg `command_timeout` bounds every statement, so a blocking acquire fails a second instance's startup whenever a peer's migration outlasts it.

When `database.postgres_schema` is configured, both async ORM connections and the synchronous SQLAlchemy connections used by DB-backed custom agents and managed subagents must use the same `search_path`; preserve this invariant when adding another persistence entry point.

Alembic stamp/upgrade workers started inside `bootstrap_schema()` remain owned by the bootstrap critical section until the worker finishes. Drain those `asyncio.to_thread()` calls across host cancellation before releasing the in-process SQLite bootstrap lock or PostgreSQL advisory lock; otherwise another bootstrap can overlap a still-running migration worker.

On SQLite, `BEGIN IMMEDIATE` takes the database-wide write lock, so every unrelated writer (run status, thread metadata, the scheduler) waits for the transaction and fails with `database is locked` after `busy_timeout` (30s). Do slow work such as document conversion before opening a locked transaction; lock only to revalidate and publish, as `ProjectDocumentRepository.publish_under_live_lock` does. `tests/test_project_document_tools.py::TestConversionSerialization` pins this.

## JSON numeric filters

Stored JSON integers are not bounded by the signed-64-bit filter input contract.
SQLite predicates must check the extracted SQL value's `typeof`, not only JSON
`json_type`, to exclude oversized integers decoded as REAL. PostgreSQL predicates
compare integer text (including `-0` for zero) without casting arbitrary stored
numbers to BIGINT or NUMERIC. Preserve integer/float/boolean/string distinctions.

Float filters cast stored numbers to DOUBLE PRECISION. PostgreSQL raises SQLSTATE
22003 on spellings outside that range (overflow such as `1e400` and underflow to
zero such as `1e-400`). The float8 cast sits inside a CASE that first rejects
non-numbers, exact-zero spellings (matched without a numeric cast), strings
longer than 10,000 characters, exponents with six or more digits, and NUMERIC
values outside float8's finite range. Do not move the float8 cast into an `AND`
(no evaluation-order guarantee), and do not use `pg_input_is_valid` (PostgreSQL
16+ only). CAST AS NUMERIC itself raises on ~1e140000 / 131073 nines, which is
why exponent length and `char_length` run first. Such values never match on
PostgreSQL, while SQLite's REAL cast saturates them to +/-inf or +/-0.0 — zero
and infinite float filters are the only ones whose results differ by backend.
The CASE uses only SQL that exists in PostgreSQL 14.
`tests/test_json_integer_matching.py` exercises both dialects; PostgreSQL opts in
with `DEERFLOW_TEST_POSTGRES_URL` and uses connection-local temporary tables.
