# Taoshi Miner — Implementation Tasks

Each task is self-contained and testable. Work through phases in order; tasks
within a phase can usually be done in parallel.

---

## Phase 1 — Signal Bridge Core

### TASK-01 · Create package skeleton
**Goal:** Lay out the `signal_bridge/` directory with empty/stub files so
imports resolve from the start.

Files to create:
```
signal_bridge/__init__.py
signal_bridge/main.py
signal_bridge/router.py
signal_bridge/models.py
signal_bridge/signal_store.py
signal_bridge/providers/__init__.py
signal_bridge/providers/base.py
signal_bridge/providers/example.py
signal_bridge/tests/__init__.py
signal_bridge/tests/test_bridge.py
```

**Done when:** `python -c "from signal_bridge.main import app"` succeeds from
`~/projects/taoshi-miner/`.

---

### TASK-02 · Implement `models.py`
**Goal:** Define Pydantic schemas used across the bridge.

Implement:
- `OrderType` enum (`LONG`, `SHORT`, `FLAT`)
- `Signal` — inbound model (trade_pair, order_type, leverage 0–1, confidence
  0–1, optional source)
- `SignalResponse` — outbound model per pair
- `BulkSignalResponse` — wraps `dict[str, SignalResponse]` + timestamp
- `IngestResponse` — typed response for `POST /signal` (`status: str`,
  `trade_pair: str`) replacing the loose `dict`

**Done when:** `pytest signal_bridge/tests/test_models.py -v` passes (write
basic construction + validation tests alongside the model).

---

### TASK-03 · Implement `signal_store.py`
**Goal:** Thread-safe in-memory store for the latest signal per pair.

Implement `SignalStore` with:
- `update(signal)` — store signal + record timestamp
- `get(trade_pair)` → returns stored signal or `DEFAULT_SIGNAL`
- `get_all()` → returns a dict covering all `SUPPORTED_PAIRS`
- `get_age_seconds(trade_pair)` → seconds since last update, or `None`

`DEFAULT_SIGNAL` must have `trade_pair=""`, `order_type=FLAT`, `leverage=0.0`.

**Done when:** unit tests cover thread-safety (two concurrent writers) and
all four methods.

---

### TASK-04 · Implement `router.py`
**Goal:** Expose four HTTP endpoints.

| Method | Path | Notes |
|--------|------|-------|
| POST | `/api/v1/signal` | Validate pair in `SUPPORTED_PAIRS`; use `IngestResponse` as `response_model` |
| GET | `/api/v1/signal/{trade_pair}` | Case-insensitive lookup |
| GET | `/api/v1/signals` | Bulk; used by miner |
| GET | `/api/v1/health` | Returns status + supported_pairs + active_signals count |

Also enforce `MIN_SIGNAL_AGE_SEC` (read from env via `os.getenv`, default 300):
if `get_age_seconds(pair)` is not None and exceeds the limit, reset that pair
to `DEFAULT_SIGNAL` before returning.

**Done when:** all unit tests in TASK-06 pass.

---

### TASK-05 · Implement `main.py` and `providers/base.py`
**Goal:** Wire FastAPI app and define the provider interface.

`main.py`:
- Create `app = FastAPI(...)` and `app.include_router(router)`
- Accept `--host` / `--port` CLI args and pass to `uvicorn.run()`
- Ensure the module is importable without side-effects (guard under
  `if __name__ == "__main__"`)

`providers/base.py`:
- Abstract `BaseProvider` with `fetch_signals() -> List[Signal]`

**Done when:** `uvicorn signal_bridge.main:app --reload` starts without error
from `~/projects/taoshi-miner/`.

---

## Phase 2 — Signal Bridge Tests

### TASK-06 · Unit tests for the HTTP API
**File:** `signal_bridge/tests/test_bridge.py`

Write pytest tests using `TestClient(app)`:

| Test | Assertion |
|------|-----------|
| `test_health_ok` | 200, `status == "ok"` |
| `test_ingest_valid` | 200, `status == "ok"` for BTCUSD LONG |
| `test_ingest_invalid_pair` | 400 |
| `test_leverage_above_max` | 422 |
| `test_leverage_below_min` | 422 |
| `test_get_signal_defaults_flat` | order_type == FLAT before any ingest |
| `test_get_signal_after_update` | reflects posted value |
| `test_get_signal_case_insensitive` | `btcusd` resolves same as `BTCUSD` |
| `test_bulk_contains_all_pairs` | all SUPPORTED_PAIRS present |
| `test_stale_signal_returns_flat` | after monkeypatching age > MIN_SIGNAL_AGE_SEC |

Use a pytest `autouse` fixture to reset `store._signals` and
`store._timestamps` before each test.

**Done when:** `pytest signal_bridge/tests/ -v` passes with 0 failures.

---

### TASK-07 · Integration test script
**File:** `scripts/test_e2e.sh`

Bash script (set -euo pipefail) that:
1. Health-checks the running bridge
2. POSTs a LONG signal for BTCUSD
3. GETs it back and asserts `order_type == LONG`
4. Calls bulk endpoint and asserts BTCUSD is LONG in the response
5. POSTs a FLAT signal and asserts it overwrites

**Done when:** `bash scripts/test_e2e.sh` exits 0 against a running bridge.

---

## Phase 3 — Miner Integration

### TASK-08 · Confirm PTN import paths
**Goal:** Before writing the integration patch, verify the actual module paths
in the cloned PTN repo.

Steps:
1. Clone PTN (`git clone ... ptn`)
2. Grep for `class PositionRequest`, `class Order`, `class TradePair`
3. Record the real import paths
4. Update the integration patch in PLAN.md §4.7 if they differ

**Done when:** import paths are confirmed and patch compiles without
`ModuleNotFoundError`.

---

### TASK-09 · Write miner `forward()` integration patch
**Goal:** Override `forward()` in a subclass (do not edit PTN source directly).

File: `neurons/custom_miner.py`

Requirements:
- Fetch `GET /api/v1/signal/{trade_pair}` (single-pair endpoint, not bulk)
- 2-second timeout; on any exception fall back to FLAT / 0.0 leverage
- Read `SIGNAL_BRIDGE_HOST` and `SIGNAL_BRIDGE_PORT` from env (default
  `127.0.0.1:8000`)
- Construct and return the `Order` using the confirmed import paths from
  TASK-08

**Done when:** `scripts/simulate_validator.py` returns a valid response and
miner logs show no exceptions.

---

### TASK-10 · Validator simulation script
**File:** `scripts/simulate_validator.py`

Implement the script from PLAN.md §6.3, updated with:
- Correct import paths (from TASK-08)
- Configurable axon IP/port via CLI args or env
- Print full synapse response including `order_type` and `leverage`

**Done when:** script runs end-to-end against a locally running miner and
prints a non-empty response.

---

## Phase 4 — Configuration & Process Management

### TASK-11 · Write `.env` file
**File:** `~/projects/taoshi-miner/.env`

Based on PLAN.md §5.1. Populate all fields; leave `WANDB_API_KEY` blank.
Verify `MIN_SIGNAL_AGE_SEC` is read correctly by the router (TASK-04).

**Done when:** `python -c "import os; from dotenv import load_dotenv;
load_dotenv(); assert os.getenv('SIGNAL_BRIDGE_PORT') == '8000'"` passes.

---

### TASK-12 · Write `pm2.config.js`
**File:** `~/projects/taoshi-miner/pm2.config.js`

Based on PLAN.md §5.2 with corrections applied:
- Add `cwd: "/home/cricri/projects/taoshi-miner"` to `signal-bridge` app entry
- Use flat string for `args` (not `.join(" ")` on an array)
- `autorestart: true`, `max_restarts: 20`, `restart_delay` values as in plan

**Done when:** `pm2 start pm2.config.js` starts both processes with status
`online` and `pm2 save` persists them.

---

## Phase 5 — Monitoring

### TASK-13 · Implement `scripts/monitor.py`
**File:** `scripts/monitor.py`

Based on PLAN.md §8.3 with fix applied:
- Use `json.dumps({"text": message})` in `alert()` — not an f-string
- `ALERT_CMD` wired to a Slack/Telegram webhook URL from env
  (`ALERT_WEBHOOK_URL`); skip alerting if env var unset
- Add a third check: call `/api/v1/health` and alert if
  `active_signals == 0`

**Done when:** script exits 0 when all services are healthy and logs an ALERT
line when the bridge is stopped.

---

### TASK-14 · Set up cron for monitor
**Goal:** Schedule `monitor.py` to run every 5 minutes.

```bash
*/5 * * * * /home/cricri/projects/taoshi-miner/venv/bin/python \
    /home/cricri/projects/taoshi-miner/scripts/monitor.py \
    >> /var/log/taoshi-monitor.log 2>&1
```

Ensure `/var/log/taoshi-monitor.log` is writable by the `cricri` user (or
redirect to `~/projects/taoshi-miner/logs/monitor.log`).

**Done when:** `crontab -l` shows the entry and a log line appears within 5
minutes.

---

## Phase 6 — Example Provider (Optional)

### TASK-15 · Implement `providers/example.py`
**Goal:** Provide a working reference implementation of `BaseProvider`.

`ExampleProvider`:
- Returns a fixed `LONG 0.5` signal for BTCUSD and `FLAT 0.0` for all others
- Can be driven by a background thread that calls `store.update()` on a
  configurable interval

**Done when:** running `ExampleProvider` in isolation (no bridge running)
produces signals that can be verified in a short unit test.

---

## Dependency Order

```
TASK-01
  ├── TASK-02 → TASK-03 → TASK-04 → TASK-06
  │                                   └── TASK-07
  └── TASK-05
         └── TASK-11 → TASK-12
TASK-08 → TASK-09 → TASK-10
TASK-13 → TASK-14
TASK-15  (independent)
```

---

*Last updated: 2026-03-20*
