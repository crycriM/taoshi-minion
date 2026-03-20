# Taoshi Miner — Remaining Tasks

## Status Summary

| Task | Status |
|------|--------|
| TASK-16 · Rewrite signal forwarder | ⏳ Pending |
| TASK-17 · Configure miner API key | ⏳ Pending |
| TASK-14 · Set up cron for monitor | 🔜 Deferred (testnet) |

---

## Architecture Correction

The original plan assumed validators call the miner via a Bittensor axon and the miner
responds with predictions. The actual PTN flow is the **opposite**:

```
External signal source
        │
        ▼
Signal Bridge  (port 8000)       ← already built
        │
        │  poll for changes
        ▼
Signal Forwarder                 ← TASK-16 (replaces custom_miner.py)
        │
        │  POST /api/submit-order
        ▼
Miner REST API  (port 8088)      ← built into PTN, requires API key
        │
        │  SendSignal synapse
        ▼
Bittensor Validators
```

`neurons/custom_miner.py` as currently written defines a standalone `forward()` function
patching the wrong side of the protocol. It must be replaced.

---

## TASK-16 · Rewrite signal forwarder

**File:** `neurons/signal_forwarder.py`

**Goal:** Replace `custom_miner.py` with a polling loop that reads from the signal bridge
and submits changed signals to the miner's REST API.

### How it works

1. On startup, fetch all pairs from `GET http://127.0.0.1:8000/api/v1/signals`.
2. Every `POLL_INTERVAL_SEC` seconds, fetch again.
3. For each pair where `order_type` or `leverage` changed from the last seen value,
   POST to `http://127.0.0.1:8088/api/submit-order`.
4. On any bridge or miner API error, log and continue — do not crash.

### Miner REST API contract

`POST http://127.0.0.1:8088/api/submit-order`

Headers:
```
X-API-Key: <MINER_API_KEY>
Content-Type: application/json
```

Body:
```json
{
  "trade_pair": "BTCUSD",
  "order_type": "LONG",
  "leverage": 0.5,
  "execution_type": "MARKET"
}
```

Note: `trade_pair` must be the PTN trade pair ID (e.g. `"BTCUSD"`, not `"BTC/USD"`).
The miner REST server calls `TradePair.from_trade_pair_id()` internally.

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SIGNAL_BRIDGE_URL` | `http://127.0.0.1:8000` | Signal bridge base URL |
| `MINER_API_URL` | `http://127.0.0.1:8088` | Miner REST API base URL |
| `MINER_API_KEY` | — | **Required.** API key for the miner REST server |
| `POLL_INTERVAL_SEC` | `30` | Seconds between bridge polls |
| `SIGNAL_BRIDGE_TIMEOUT_SEC` | `2` | HTTP timeout for bridge calls |
| `MINER_API_TIMEOUT_SEC` | `10` | HTTP timeout for miner API calls |

### Done when

- `python neurons/signal_forwarder.py` runs without error.
- After POSTing a LONG signal to the bridge, a log line confirms the order was
  submitted to the miner API within one poll interval.
- On bridge outage: forwarder logs an error and keeps running.
- On miner API outage: forwarder logs an error and keeps running.

### Notes

- Delete `neurons/custom_miner.py` once this task is complete.
- Add `neurons/signal_forwarder.py` to `pm2.config.js` as a third process
  (`name: "signal-forwarder"`) so pm2 manages its lifecycle.
- Only submit an order when a signal **changes** — do not re-submit the same
  order every poll cycle or the miner will generate duplicate UUID errors.

---

## TASK-17 · Configure miner API key

**Goal:** Obtain and configure the API key required by the miner REST server.

### Steps

1. Locate the API keys file used by the miner.
   ```bash
   grep -r "api_keys_file\|api_keys\|API_KEY" ptn/miner_config.py ptn/vanta_api/miner_api_manager.py
   ```

2. Generate a strong random key:
   ```bash
   python3 -c "import secrets; print(secrets.token_hex(32))"
   ```

3. Write the key to the miner's API key store (format TBD from step 1).

4. Add the same key to `.env`:
   ```dotenv
   MINER_API_KEY=<generated-key>
   ```

5. Verify:
   ```bash
   curl -s -X POST http://127.0.0.1:8088/api/submit-order \
     -H "X-API-Key: $MINER_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"trade_pair":"BTCUSD","order_type":"FLAT","leverage":0.0,"execution_type":"MARKET"}' \
     | python3 -m json.tool
   ```

### Done when

- The curl above returns `"success": true` (or a meaningful domain error, not 401).

---

## TASK-14 · Set up cron for monitor (deferred)

**Blocked on:** testnet wallet and network configuration.

When ready, add the crontab entry:

```bash
(crontab -l; echo "*/5 * * * * /home/cricri/projects/taoshi-miner/venv/bin/python \
    /home/cricri/projects/taoshi-miner/scripts/monitor.py \
    >> /home/cricri/projects/taoshi-miner/logs/monitor.log 2>&1") | crontab -

mkdir -p /home/cricri/projects/taoshi-miner/logs
```

Also add a `check_pm2_process("signal-forwarder")` call in `scripts/monitor.py` once
TASK-16 is complete and the forwarder is registered in pm2.

### Done when

- `crontab -l` shows the entry.
- A log line appears in `logs/monitor.log` within 5 minutes.

---

## Dependency Order

```
TASK-17 (API key) → TASK-16 (forwarder) → TASK-14 (cron)
```

---

*Last updated: 2026-03-20*
