# Persistence — Choosing and Using Stores

DinarLedger ships three repository implementations behind a common
`Repository[T]` abstract interface.  This guide explains when to use each,
how migrations work, and how the Unit of Work pattern ensures atomicity.

---

## Repository Interface

Every store implements the same `Repository[T]` ABC from
`dinarledger.storage.base`:

| Method | Description |
|--------|-------------|
| `get(id)` | Fetch by primary key; returns `None` if missing |
| `get_all()` | Return every entity |
| `add(entity)` | Persist a new entity |
| `update(entity)` | Replace an existing entity |
| `delete(id)` | Remove by ID; returns `bool` |
| `find(filter)` | Equality-based lookup (e.g. `{"status": "active"}`) |

Additional features on `MemoryRepository`:
- `find_with_conditions(conditions)` — advanced filtering with `FilterCondition`
- `count()` — entity count
- `clear()` — wipe the store (useful between tests)

---

## MemoryRepository

**Location:** `dinarledger.storage.memory`

**When to use:**
- Unit tests and property-based tests
- Prototyping / REPL exploration
- Short-lived batch scripts that don't need persistence

**Characteristics:**
- Thread-safe via `threading.Lock`
- Zero setup — `MemoryRepository(MyEntity)`
- Auto-generates UUID-based IDs for entities without a primary key
- Data lives only in-process; lost on exit

**Example:**

```python
from dinarledger.storage.memory import MemoryRepository
from dinarledger.core.types import Plan

repo = MemoryRepository(Plan)
repo.add(plan)
retrieved = repo.get("pro-monthly")
```

---

## JsonRepository

**Location:** `dinarledger.storage.json_store`

**When to use:**
- Single-instance deployments (one process at a time)
- Development environments that need persistence between runs
- Small-to-medium datasets (< 10,000 entities per collection)

**Characteristics:**
- Stores each entity type in a separate JSON file
- Lazy loading — file is read on first access
- Auto-save after every write (configurable via `auto_save=False`)
- Not safe for concurrent writers (no file locking)

**Example:**

```python
from dinarledger.storage.json_store import JsonRepository
from dinarledger.core.types import Invoice

repo = JsonRepository(Invoice, path="data/invoices.json")
```

---

## SqliteRepository

**Location:** `dinarledger.storage.sqlite_store`

**When to use:**
- Production workloads
- Concurrent access (SQLite handles writer serialization)
- Larger datasets
- When you need real ACID transactions

**Characteristics:**
- Full transaction support (`begin()`, `commit()`, `rollback()`)
- Entities serialised as JSON blobs in a single `entities` table
- Thread-safe (SQLite serialises writes)
- Supports the Unit of Work pattern with real rollbacks

**Example:**

```python
from dinarledger.storage.sqlite_store import SqliteRepository
from dinarledger.core.types import Customer

repo = SqliteRepository(Customer, db_path="dinarledger.db")
```

---

## Migration System

**Location:** `dinarledger.storage.migrations`

Migrations are versioned Python modules that create or alter the database
schema:

| Migration | Description |
|-----------|-------------|
| `v001_initial` | Creates the core `entities` table |
| `v002_add_fx_rates` | Adds FX rate storage |
| `v003_add_payments` | Adds payment tracking |

Migrations run automatically when a `SqliteRepository` is opened against a
database that hasn't been brought to the latest version.  Each migration
records its version in a `_schema_version` table.

To add a new migration:

1. Create `v00N_description.py` with an `up(conn)` function.
2. Optionally add a `down(conn)` function for rollback.
3. Register it in `dinarledger.storage.migrations.__init__.py`.

---

## Unit of Work

**Location:** `dinarledger.storage.unit_of_work`

Groups multiple repository operations into a single logical transaction:

```python
from dinarledger.storage.unit_of_work import UnitOfWork

with UnitOfWork(customer_repo, invoice_repo) as uow:
    customer_repo.add(customer)
    invoice_repo.add(invoice)
    # If either add() raises, both repos are rolled back
```

**Behaviour per repository type:**

| Repo | Begin | Commit | Rollback |
|------|-------|--------|----------|
| `SqliteRepository` | `begin()` (real DB transaction) | `commit()` | `rollback()` |
| `MemoryRepository` | Snapshot via `copy.deepcopy` | No-op | Restore snapshot |
| `JsonRepository` | Snapshot + force load | No-op | Restore + save snapshot |

You can also call `uow.rollback()` explicitly inside the context.

---

## Decision Matrix

| Criteria | Memory | JSON | SQLite |
|----------|--------|------|--------|
| Persistence | No | Yes | Yes |
| Concurrent writers | Safe (lock) | **Not safe** | Safe |
| ACID transactions | Simulated | Simulated | **Real** |
| Setup cost | None | Directory | DB file + migrations |
| Best for | Tests, REPL | Dev, single-process | Production |
