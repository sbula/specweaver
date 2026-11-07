# SQLite WAL & Concurrency

Parallel SpecWeaver tasks read and write the same SQLite files. One opener,
`infrastructure/database/`, keeps them from failing with `database is locked` (`TECH-090`).

## The one opener

Every connection, sync or async, gets three settings in this order (`apply_pragmas`):

1. **A lock wait** (`busy_timeout`): a writer that finds the file locked waits instead of failing.
   30 s by default; a door can set its own with `set_lock_wait(seconds)`.
2. **WAL mode**: readers do not block the writer, and the writer does not block readers.
   The switch is retried while another process holds the lock on a new file.
3. **Foreign keys on**: cascades run. SQLite ignores this setting inside a transaction, so it is
   set before the first one.

| Entry point | Gives |
|---|---|
| `open_sqlite(path)` | a `sqlite3` connection |
| `create_sqlite_engine(path)` | an async SQLAlchemy engine (`aiosqlite`, `NullPool`) |
| `Database(path)` | `connect()`, `async_session_scope()`, `sync_engine()` on one file |

## Sessions

- `session_scope(engine)` commits on success and rolls back on error.
- An `asyncio.Semaphore` per event loop caps open sessions at 500 by default, to avoid
  file-descriptor exhaustion.
- Async engines use `NullPool`, so a session never holds a pooled connection that keeps a lock.

## Writes

Writes go straight through a session or a connection; the lock wait serialises them. An async
write queue (`CQRSQueueManager`) existed until `TECH-090` and was deleted: nothing ever enqueued
a write.

## Rules

- Open a SpecWeaver file only through `infrastructure/database/`.
  `tests/unit/infrastructure/database/test_only_the_opener_opens.py` fails any other opener in `src/`.
- A test that builds its own in-memory engine uses `tests/fixtures/db_utils.create_async_engine`,
  which turns foreign keys on the same way.
- Schema versions: [`database_migrations.md`](../03_system_topology/database_migrations.md).
