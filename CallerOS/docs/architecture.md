# CallerOS — Stage 1 Architecture

## Overview

CallerOS Stage 1 implements the **Core** of the application: the minimal
foundation required to boot the system, load configuration, initialise
logging, manage service dependencies, and shut down cleanly.

No AI logic, no domain logic, and no business rules exist in this layer.
Stage 1 is a platform, not a product.

---

## Guiding Principles

All decisions in this stage reflect the Canonical Development Guide:

| Principle | Application |
|-----------|------------|
| Simplicity first | No third-party IoC framework; plain dict registry |
| Build only what is needed | No event loop, no HTTP server, no DB |
| One responsibility per class | Each class has one clearly defined job |
| Modular everything | Every module is independently importable and testable |
| No premature optimisation | No thread-safety in registry (single-threaded in Stage 1) |

---

## Component Responsibilities

### `core/exceptions.py`
Custom exception hierarchy rooted at `CallerOSError`.  All application errors
are subtypes, so callers can catch broadly or narrowly without importing
low-level Python exceptions.

### `config/settings.py`
Single, frozen, strongly-typed configuration object (`Settings`).  Loaded
from environment variables (optionally via a `.env` file).  All values are
validated at load time — the application fails immediately with a clear error
rather than silently using a bad value later.

### `logging/logger.py`
One entry point: `setup_logging(settings)`.  Configures the Python standard-
library root logger with a console handler and a 5 MB rotating file handler.
`reset_logging()` is provided for test isolation only.

### `core/service_registry.py`
Lightweight dict-backed registry.  Services are identified by string name.
Duplicate registrations are rejected immediately.  Missing services raise
`ServiceNotFoundError` with a helpful message listing registered names.

### `core/lifecycle.py`
Ordered startup and LIFO shutdown of services that implement the
`LifecycleService` protocol (`start()` / `stop()`).  All shutdown errors
are collected before re-raising so that every service gets a chance to clean
up.

### `core/health.py`
Startup health validator.  Checks that configuration is loaded, logging has
handlers, and the registry is operational.  Returns a `HealthReport` with
status `READY` or `FAILED` and a list of human-readable issues.

### `core/application.py`
Top-level orchestrator.  Owns the startup sequence, shutdown sequence, signal
handler registration, and application state machine.  Does not contain any
domain logic.

### `main.py`
Minimal entry point.  Calls `Application.startup()`, parks in a sleep loop
until interrupted, then calls `Application.shutdown()`.

---

## Startup Sequence

```
main.py
  └─ Application.startup()
       ├─ 1. Settings.from_env()          — load & validate configuration
       ├─ 2. setup_logging(settings)      — initialise logging
       ├─ 3. ServiceRegistry()            — create service registry
       ├─ 4. LifecycleManager()           — create lifecycle manager
       ├─ 5. HealthValidator.validate()   — confirm system is ready
       └─ 6. LifecycleManager.startup()   — start registered services
              └─ (no services in Stage 1)
```

---

## Shutdown Sequence

```
main.py  (Ctrl-C / SIGTERM / context manager __exit__)
  └─ Application.shutdown()
       └─ LifecycleManager.shutdown()    — stop services in LIFO order
              └─ (no services in Stage 1)
```

---

## Application State Machine

```
CREATED ──startup()──► STARTING ──success──► RUNNING
                            │                    │
                         failure              shutdown()
                            │                    │
                          FAILED             STOPPING ──► STOPPED
```

Illegal transitions (e.g. calling `startup()` twice) raise `StartupError`.

---

## Dependency Diagram

```
main.py
  └── Application
        ├── Settings           (no deps on other CallerOS modules)
        ├── setup_logging()    (depends on Settings)
        ├── ServiceRegistry    (depends on exceptions)
        ├── LifecycleManager   (depends on exceptions)
        └── HealthValidator
              ├── Settings
              └── ServiceRegistry

All modules depend on:
  └── core/exceptions.py      (leaf — no CallerOS imports)
```

---

## Architectural Decisions

### ADR-001  No IoC framework
**Decision:** Use a plain `dict` for the service registry.  
**Reason:** The guide explicitly forbids IoC frameworks and Stage 1 has fewer
than five services.  A dict is sufficient and removes a dependency.

### ADR-002  Frozen dataclass for Settings
**Decision:** `Settings` is a `@dataclass(frozen=True)`.  
**Reason:** Configuration must not change at runtime.  Immutability catches
accidental mutation at type-check time and at runtime.

### ADR-003  Standard-library logging only
**Decision:** Use `logging` + `logging.handlers` from the standard library.  
**Reason:** Third-party logging libraries (structlog, loguru) add value for
structured JSON logs but are unnecessary for Stage 1.  The interface can be
extended later without changing consumer code.

### ADR-004  LIFO shutdown order
**Decision:** Services are stopped in reverse registration order.  
**Reason:** LIFO ensures that services with dependencies are torn down before
the services they depend on — the conventional teardown pattern.

### ADR-005  Collect-all-errors shutdown
**Decision:** `LifecycleManager.shutdown()` collects stop errors rather than
aborting on the first one.  
**Reason:** Aborting early risks leaving services in a partially stopped state,
which is harder to diagnose and recover from.

### ADR-006  Logging package renamed to `app_logging`
**Decision:** The project's logging package is named `app_logging/` (not
`logging/`).  
**Reason:** Naming it `logging/` shadows Python's stdlib `logging` module,
which prevents pytest and other tooling from importing `logging.LogRecord`.
Renaming to `app_logging` eliminates the conflict entirely with no downside.

---

## File Index

| File | Lines | Purpose |
|------|-------|---------|
| `main.py` | ~40 | Entry point |
| `core/exceptions.py` | ~60 | Exception hierarchy |
| `core/application.py` | ~210 | Application lifecycle |
| `core/lifecycle.py` | ~155 | Service start/stop ordering |
| `core/service_registry.py` | ~120 | Dependency registry |
| `core/health.py` | ~120 | Startup health checks |
| `config/settings.py` | ~110 | Configuration |
| `app_logging/logger.py` | ~95 | Logging setup |
| `tests/conftest.py` | ~25 | Shared fixtures |
| `tests/test_settings.py` | ~70 | Settings tests |
| `tests/test_service_registry.py` | ~95 | Registry tests |
| `tests/test_lifecycle.py` | ~115 | Lifecycle tests |
| `tests/test_health.py` | ~100 | Health tests |
| `tests/test_application.py` | ~110 | Application tests |

---

## Backlog

The following are **not implemented** in Stage 1 but are recommended for
consideration in later stages:

- **Thread-safety in ServiceRegistry** — add `threading.Lock` if concurrent
  access is needed.
- **Rename `logging/` package** — avoid shadowing the stdlib `logging` module.
- **Structured (JSON) logging** — useful for log aggregation pipelines.
- **Health check endpoint** — expose health status over HTTP once FastAPI is
  introduced.
- **Graceful timeout on shutdown** — enforce a maximum wait time per service.
