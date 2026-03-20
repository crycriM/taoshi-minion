# Taoshi Miner Deployment Plan

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Prerequisites](#prerequisites)
3. [Step-by-Step Setup](#step-by-step-setup)
4. [Signal Bridge Code](#signal-bridge-code)
5. [Configuration Files](#configuration-files)
6. [Testing Strategy](#testing-strategy)
7. [Deployment Checklist](#deployment-checklist)
8. [Monitoring](#monitoring)

---

## 1. Architecture Overview

### System Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        Signal Sources                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  Custom ML   │  │  External    │  │  Manual/Rule-    │  │
│  │  Models      │  │  Signal Feed │  │  Based Signals   │  │
│  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘  │
└─────────┼─────────────────┼───────────────────┼────────────┘
          │                 │                   │
          └─────────────────┴───────────────────┘
                            │
                    ┌───────▼────────┐
                    │  Signal Bridge │  (FastAPI / local HTTP)
                    │  (port 8000)   │
                    └───────┬────────┘
                            │  HTTP POST /api/v1/signal
                            │
              ┌─────────────▼──────────────┐
              │      Taoshi Miner Process   │
              │  (neurons/miner.py)         │
              │  - Receives validator reqs  │
              │  - Calls signal bridge      │
              │  - Returns predictions      │
              └─────────────┬──────────────┘
                            │  Bittensor Axon (port 8091)
                            │
              ┌─────────────▼──────────────┐
              │    Bittensor Network        │
              │    Subnet 8 (SN8)           │
              │    Validators               │
              └────────────────────────────┘
```

### Component Roles

| Component | Role | Default Port |
|-----------|------|-------------|
| Signal Bridge | Translates custom signals into Taoshi-compatible predictions | 8000 |
| Taoshi Miner | Bittensor neuron that serves predictions to validators | 8091 |
| Subtensor Node | Local or remote Bittensor blockchain node | 9944 |
| Wallet | Coldkey + hotkey pair for on-chain identity | — |

### Trade Pair Coverage

The miner must provide predictions for all active trade pairs on SN8. Key pairs include:

- Forex: EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD, NZDUSD, USDCHF
- Crypto: BTCUSD, ETHUSD
- Indices: SPX, NDX, DJI

---

## 2. Prerequisites

### Hardware Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| CPU | 4 cores | 8+ cores |
| RAM | 8 GB | 16 GB |
| Disk | 50 GB SSD | 100 GB NVMe SSD |
| Network | 100 Mbps | 1 Gbps, static IP preferred |

### Software Requirements

- Ubuntu 22.04 LTS (or Debian 12)
- Python 3.10 or 3.11
- Git
- `pm2` (process manager) or `systemd`
- `ufw` or equivalent firewall

### Bittensor Requirements

- TAO tokens for registration fee (check current cost: `btcli s list`)
- A registered hotkey on SN8
- Coldkey with sufficient TAO balance

### Accounts & Keys

- Bittensor coldkey (generated locally, never share)
- Bittensor hotkey registered on subnet 8
- (Optional) WandB account for remote logging
- (Optional) API keys for external signal providers

---

## 3. Step-by-Step Setup

### 3.1 System Preparation

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y \
    git curl wget build-essential \
    python3.11 python3.11-venv python3.11-dev \
    python3-pip libssl-dev pkg-config \
    npm

# Install pm2 globally
sudo npm install -g pm2

# Configure firewall
sudo ufw allow ssh
sudo ufw allow 8091/tcp   # Bittensor axon
# NOTE: Do NOT open port 8000 externally. The signal bridge binds to 127.0.0.1 only.
# If you need external signal ingestion, use the Nginx reverse proxy (Section 5.4).
sudo ufw enable
```

### 3.2 Bittensor Installation

```bash
# Create project directory
mkdir -p ~/taoshi-miner
cd ~/taoshi-miner

# Create and activate virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install Bittensor
pip install bittensor==8.5.1   # pin to a known-good version

# Verify installation
btcli --version
```

### 3.3 Wallet Setup

```bash
# Create coldkey (do this on a secure, offline machine if possible)
btcli wallet new_coldkey --wallet.name miner_cold

# Create hotkey
btcli wallet new_hotkey \
    --wallet.name miner_cold \
    --wallet.hotkey miner_hot

# Verify wallet
btcli wallet overview --wallet.name miner_cold

# Check balance
btcli wallet balance --wallet.name miner_cold
```

> **Security note:** Back up `~/.bittensor/wallets/miner_cold/coldkeypub.txt` and the
> encrypted coldkey file offline. Never store the mnemonic on the server.

### 3.4 Register on Subnet 8

```bash
# Check current registration cost
btcli s list --subtensor.network finney

# Register hotkey on SN8
btcli s register \
    --wallet.name miner_cold \
    --wallet.hotkey miner_hot \
    --subtensor.network finney \
    --netuid 8

# Verify registration
btcli s metagraph --netuid 8 --subtensor.network finney | grep <YOUR_HOTKEY_SS58>
```

### 3.5 Clone Taoshi Repository

```bash
cd ~/taoshi-miner

git clone https://github.com/taoshidev/proprietary-trading-network.git ptn
cd ptn

pip install -r requirements.txt
pip install -e .
```

### 3.6 Install Signal Bridge

```bash
cd ~/taoshi-miner

# Create signal bridge package
mkdir -p signal_bridge
# (see Section 4 for the full source code)

# Install signal bridge dependencies
pip install fastapi uvicorn httpx pydantic
```

### 3.7 Configure Environment

```bash
# Copy and edit environment file
cp ~/taoshi-miner/ptn/.env.example ~/taoshi-miner/.env
# (see Section 5 for full config)
```

### 3.8 Start Services with pm2

```bash
cd ~/taoshi-miner

# Start signal bridge
pm2 start signal_bridge/main.py \
    --name signal-bridge \
    --interpreter ~/taoshi-miner/venv/bin/python \
    -- --host 127.0.0.1 --port 8000

# Start miner
pm2 start ptn/neurons/miner.py \
    --name taoshi-miner \
    --interpreter ~/taoshi-miner/venv/bin/python \
    -- \
    --wallet.name miner_cold \
    --wallet.hotkey miner_hot \
    --subtensor.network finney \
    --netuid 8 \
    --axon.port 8091 \
    --logging.debug

# Save pm2 process list and set up auto-start
pm2 save
pm2 startup
# Run the command that pm2 prints
```

---

## 4. Signal Bridge Code

The Signal Bridge is a lightweight HTTP service that sits between your signal sources and the Taoshi miner. The miner calls it to get the latest predictions for each trade pair.

### 4.1 Directory Structure

```
signal_bridge/
├── __init__.py
├── main.py          # FastAPI app entry point
├── router.py        # API routes
├── models.py        # Pydantic schemas
├── signal_store.py  # In-memory signal state
├── providers/
│   ├── __init__.py
│   ├── base.py      # Abstract provider interface
│   └── example.py  # Example custom provider
└── tests/
    └── test_bridge.py
```

### 4.2 `signal_bridge/models.py`

```python
from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class OrderType(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    FLAT = "FLAT"


class Signal(BaseModel):
    trade_pair: str = Field(..., description="e.g. BTCUSD, EURUSD")
    order_type: OrderType
    leverage: float = Field(default=0.5, ge=0.0, le=1.0)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source: Optional[str] = None


class SignalResponse(BaseModel):
    trade_pair: str
    order_type: OrderType
    leverage: float
    confidence: float


class BulkSignalResponse(BaseModel):
    signals: dict[str, SignalResponse]
    timestamp: float
```

### 4.3 `signal_bridge/signal_store.py`

```python
import time
import threading
from typing import Optional
from .models import Signal, OrderType


# Default flat signal for any pair not explicitly set
DEFAULT_SIGNAL = Signal(
    trade_pair="",
    order_type=OrderType.FLAT,
    leverage=0.0,
    confidence=1.0,
    source="default",
)

SUPPORTED_PAIRS = [
    "BTCUSD", "ETHUSD",
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD",
    "USDCAD", "NZDUSD", "USDCHF",
    "SPX", "NDX", "DJI",
]


class SignalStore:
    """Thread-safe in-memory store for the latest signal per trade pair."""

    def __init__(self):
        self._lock = threading.RLock()
        self._signals: dict[str, Signal] = {}
        self._timestamps: dict[str, float] = {}

    def update(self, signal: Signal) -> None:
        with self._lock:
            self._signals[signal.trade_pair] = signal
            self._timestamps[signal.trade_pair] = time.time()

    def get(self, trade_pair: str) -> Signal:
        with self._lock:
            return self._signals.get(trade_pair, DEFAULT_SIGNAL)

    def get_all(self) -> dict[str, Signal]:
        with self._lock:
            result = {}
            for pair in SUPPORTED_PAIRS:
                result[pair] = self._signals.get(pair, DEFAULT_SIGNAL)
            return result

    def get_age_seconds(self, trade_pair: str) -> Optional[float]:
        with self._lock:
            ts = self._timestamps.get(trade_pair)
            return (time.time() - ts) if ts else None


# Module-level singleton
store = SignalStore()
```

### 4.4 `signal_bridge/router.py`

```python
import time
from fastapi import APIRouter, HTTPException
from .models import Signal, SignalResponse, BulkSignalResponse, OrderType
from .signal_store import store, SUPPORTED_PAIRS

router = APIRouter(prefix="/api/v1")


# NOTE: response_model=dict is too loose. A typed response model is preferred.
# Consider defining an IngestResponse(BaseModel) with status and trade_pair fields.
@router.post("/signal", response_model=dict)
async def ingest_signal(signal: Signal):
    """Accept a new signal from an upstream source."""
    if signal.trade_pair not in SUPPORTED_PAIRS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported trade pair: {signal.trade_pair}. "
                   f"Supported: {SUPPORTED_PAIRS}",
        )
    store.update(signal)
    return {"status": "ok", "trade_pair": signal.trade_pair}


@router.get("/signal/{trade_pair}", response_model=SignalResponse)
async def get_signal(trade_pair: str):
    """Get the current signal for a specific trade pair."""
    sig = store.get(trade_pair.upper())
    return SignalResponse(
        trade_pair=trade_pair.upper(),
        order_type=sig.order_type,
        leverage=sig.leverage,
        confidence=sig.confidence,
    )


@router.get("/signals", response_model=BulkSignalResponse)
async def get_all_signals():
    """Get current signals for all supported trade pairs (used by the miner)."""
    all_sigs = store.get_all()
    return BulkSignalResponse(
        signals={
            pair: SignalResponse(
                trade_pair=pair,
                order_type=sig.order_type,
                leverage=sig.leverage,
                confidence=sig.confidence,
            )
            for pair, sig in all_sigs.items()
        },
        timestamp=time.time(),
    )


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "supported_pairs": SUPPORTED_PAIRS,
        "active_signals": sum(
            1 for p in SUPPORTED_PAIRS
            if store.get_age_seconds(p) is not None
        ),
    }
```

### 4.5 `signal_bridge/main.py`

```python
import argparse
import uvicorn
from fastapi import FastAPI
from .router import router

app = FastAPI(title="Taoshi Signal Bridge", version="1.0.0")
app.include_router(router)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    uvicorn.run(
        "signal_bridge.main:app",
        host=args.host,
        port=args.port,
        reload=False,
        log_level="info",
    )
```

### 4.6 `signal_bridge/providers/base.py`

```python
from abc import ABC, abstractmethod
from ..models import Signal
from typing import List


class BaseProvider(ABC):
    """Extend this to plug in any signal source."""

    @abstractmethod
    def fetch_signals(self) -> List[Signal]:
        """Return the latest signals from this provider."""
        ...
```

### 4.7 Miner Integration Patch

In `ptn/neurons/miner.py` (or a subclass), override `forward()` to query the signal bridge:

```python
import httpx
from vali_objects.vali_dataclasses.order import Order
from vali_objects.position_request import PositionRequest

SIGNAL_BRIDGE_URL = "http://127.0.0.1:8000/api/v1/signals"


async def forward(self, synapse: PositionRequest) -> PositionRequest:
    trade_pair = synapse.trade_pair.trade_pair_id

    # NOTE: Fetching all signals for every single request is wasteful.
    # Prefer GET /api/v1/signal/{trade_pair} to fetch only the needed pair.
    async with httpx.AsyncClient(timeout=2.0) as client:
        try:
            resp = await client.get(SIGNAL_BRIDGE_URL)
            resp.raise_for_status()
            signals = resp.json()["signals"]
            sig = signals.get(trade_pair, {"order_type": "FLAT", "leverage": 0.0})
        except Exception:
            # Fail safe: return FLAT on any bridge error
            sig = {"order_type": "FLAT", "leverage": 0.0}

    synapse.order = Order(
        trade_pair=synapse.trade_pair,
        order_type=sig["order_type"],
        leverage=float(sig["leverage"]),
    )
    return synapse
```

---

## 5. Configuration Files

### 5.1 `.env`

```dotenv
# Bittensor
WALLET_NAME=miner_cold
WALLET_HOTKEY=miner_hot
SUBTENSOR_NETWORK=finney
NETUID=8
AXON_PORT=8091

# Signal Bridge
SIGNAL_BRIDGE_HOST=127.0.0.1
SIGNAL_BRIDGE_PORT=8000
SIGNAL_BRIDGE_TIMEOUT_SEC=2

# Logging
LOG_LEVEL=INFO
WANDB_API_KEY=              # optional

# Safety limits
MAX_LEVERAGE=1.0
MIN_SIGNAL_AGE_SEC=300      # reject signals older than 5 min (must be enforced in router.py — not yet wired)
```

### 5.2 `pm2.config.js`

```javascript
// NOTE: pm2 must be started from ~/taoshi-miner so that signal_bridge is a
// importable package (relative imports require the parent dir on sys.path).
// Add cwd: "/home/cricri/taoshi-miner" to each app entry.
module.exports = {
  apps: [
    {
      name: "signal-bridge",
      script: "/home/cricri/taoshi-miner/signal_bridge/main.py",
      interpreter: "/home/cricri/taoshi-miner/venv/bin/python",
      cwd: "/home/cricri/taoshi-miner",
      args: "--host 127.0.0.1 --port 8000",
      watch: false,
      autorestart: true,
      max_restarts: 20,
      restart_delay: 5000,
      log_date_format: "YYYY-MM-DD HH:mm:ss",
      env: {
        PYTHONUNBUFFERED: "1",
      },
    },
    {
      name: "taoshi-miner",
      script: "/home/cricri/taoshi-miner/ptn/neurons/miner.py",
      interpreter: "/home/cricri/taoshi-miner/venv/bin/python",
      // NOTE: .join(" ") collapses the array to one string; pm2 may not split
      // it correctly. Pass args as a plain space-separated string instead.
      args: "--wallet.name miner_cold --wallet.hotkey miner_hot --subtensor.network finney --netuid 8 --axon.port 8091 --logging.info",
      watch: false,
      autorestart: true,
      max_restarts: 20,
      restart_delay: 10000,
      log_date_format: "YYYY-MM-DD HH:mm:ss",
      env: {
        PYTHONUNBUFFERED: "1",
      },
    },
  ],
};
```

### 5.3 Systemd Alternative: `taoshi-miner.service`

```ini
[Unit]
Description=Taoshi Miner (SN8)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=cricri
WorkingDirectory=/home/cricri/taoshi-miner/ptn
Environment=PYTHONUNBUFFERED=1
ExecStart=/home/cricri/taoshi-miner/venv/bin/python neurons/miner.py \
    --wallet.name miner_cold \
    --wallet.hotkey miner_hot \
    --subtensor.network finney \
    --netuid 8 \
    --axon.port 8091 \
    --logging.info
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 5.4 Nginx Reverse Proxy (optional, for external signal ingestion)

```nginx
server {
    listen 443 ssl;
    server_name signals.yourdomain.com;

    ssl_certificate     /etc/letsencrypt/live/signals.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/signals.yourdomain.com/privkey.pem;

    # Restrict ingestion endpoint to known IPs
    location /api/v1/signal {
        allow 1.2.3.4;    # your signal source IP
        deny all;

        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
    }

    # Health endpoint is public
    location /api/v1/health {
        proxy_pass http://127.0.0.1:8000;
    }
}
```

---

## 6. Testing Strategy

### 6.1 Unit Tests: Signal Bridge

```python
# signal_bridge/tests/test_bridge.py
import pytest
from fastapi.testclient import TestClient
from signal_bridge.main import app
from signal_bridge.signal_store import store, SUPPORTED_PAIRS

client = TestClient(app)


def setup_function():
    # Reset store before each test by replacing signals dict
    store._signals.clear()
    store._timestamps.clear()


def test_health_endpoint():
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_ingest_valid_signal():
    payload = {
        "trade_pair": "BTCUSD",
        "order_type": "LONG",
        "leverage": 0.5,
        "confidence": 0.9,
    }
    resp = client.post("/api/v1/signal", json=payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_ingest_invalid_pair():
    payload = {"trade_pair": "FAKEPAIR", "order_type": "LONG", "leverage": 0.5}
    resp = client.post("/api/v1/signal", json=payload)
    assert resp.status_code == 400


def test_get_signal_defaults_to_flat():
    resp = client.get("/api/v1/signal/EURUSD")
    assert resp.status_code == 200
    assert resp.json()["order_type"] == "FLAT"


def test_get_signal_after_update():
    client.post("/api/v1/signal", json={
        "trade_pair": "EURUSD", "order_type": "SHORT", "leverage": 0.3
    })
    resp = client.get("/api/v1/signal/EURUSD")
    assert resp.json()["order_type"] == "SHORT"
    assert resp.json()["leverage"] == pytest.approx(0.3)


def test_all_pairs_returned():
    resp = client.get("/api/v1/signals")
    assert resp.status_code == 200
    data = resp.json()
    for pair in SUPPORTED_PAIRS:
        assert pair in data["signals"]


def test_leverage_bounds():
    # Leverage > 1.0 should be rejected
    resp = client.post("/api/v1/signal", json={
        "trade_pair": "BTCUSD", "order_type": "LONG", "leverage": 1.5
    })
    assert resp.status_code == 422
```

### 6.2 Integration Test: End-to-End Signal Flow

```bash
#!/usr/bin/env bash
# scripts/test_e2e.sh

set -euo pipefail

BRIDGE="http://127.0.0.1:8000"

echo "[1] Health check..."
curl -sf "$BRIDGE/api/v1/health" | python3 -m json.tool

echo "[2] Ingest a LONG signal for BTCUSD..."
curl -sf -X POST "$BRIDGE/api/v1/signal" \
  -H "Content-Type: application/json" \
  -d '{"trade_pair":"BTCUSD","order_type":"LONG","leverage":0.5}' \
  | python3 -m json.tool

echo "[3] Read it back..."
curl -sf "$BRIDGE/api/v1/signal/BTCUSD" | python3 -m json.tool

echo "[4] Confirm it appears in bulk endpoint..."
curl -sf "$BRIDGE/api/v1/signals" | python3 -c "
import sys, json
d = json.load(sys.stdin)
sig = d['signals']['BTCUSD']
assert sig['order_type'] == 'LONG', f'Expected LONG, got {sig}'
print('PASS: BTCUSD signal is LONG')
"

echo "All integration tests passed."
```

### 6.3 Validator Request Simulation

```python
# scripts/simulate_validator.py
"""Send a mock PositionRequest to the local axon to verify the miner responds."""

import asyncio
import bittensor as bt
from ptn.vali_objects.position_request import PositionRequest
from ptn.vali_objects.vali_dataclasses.trade_pair import TradePair


async def main():
    wallet = bt.wallet(name="miner_cold", hotkey="miner_hot")
    dendrite = bt.dendrite(wallet=wallet)

    axon_info = bt.AxonInfo(
        ip="127.0.0.1",
        port=8091,
        hotkey=wallet.hotkey.ss58_address,
        coldkey=wallet.coldkeypub.ss58_address,
        version=1,
        ip_type=4,
    )

    synapse = PositionRequest(trade_pair=TradePair.get_trade_pair_from_trade_pair_id("BTCUSD"))

    response = await dendrite.forward(
        axons=[axon_info],
        synapse=synapse,
        timeout=12,
    )
    print(f"Response: {response}")


if __name__ == "__main__":
    asyncio.run(main())
```

### 6.4 Test Execution

```bash
# Unit tests
cd ~/taoshi-miner
source venv/bin/activate
pytest signal_bridge/tests/ -v --tb=short

# Integration tests (signal bridge must be running)
bash scripts/test_e2e.sh

# Validator simulation (miner must be running)
python scripts/simulate_validator.py
```

---

## 7. Deployment Checklist

### Pre-Deployment

- [ ] Ubuntu 22.04 server provisioned with static IP
- [ ] Firewall configured (ports 22, 8091 open; 8000 localhost-only)
- [ ] Python 3.11 virtual environment created
- [ ] Bittensor installed and `btcli --version` succeeds
- [ ] Coldkey created and backed up offline
- [ ] Hotkey created
- [ ] Wallet funded with enough TAO for registration
- [ ] Registered on SN8 (`btcli s metagraph` shows your UID)
- [ ] PTN repository cloned and dependencies installed
- [ ] Signal bridge code in place and unit tests passing
- [ ] `.env` file configured with correct wallet names and ports
- [ ] `pm2.config.js` reviewed and paths verified

### Launch

- [ ] Signal bridge started (`pm2 start signal-bridge`)
- [ ] Signal bridge health check returns `"status": "ok"`
- [ ] Taoshi miner started (`pm2 start taoshi-miner`)
- [ ] Miner logs show `Axon started on port 8091`
- [ ] Miner logs show `Registered on subnet 8`
- [ ] End-to-end integration test passes (`bash scripts/test_e2e.sh`)
- [ ] Validator simulation returns a valid response
- [ ] `pm2 save` + `pm2 startup` run so services survive reboots

### Post-Launch (first 24 hours)

- [ ] Miner appears in `btcli s metagraph` with non-zero emission
- [ ] No `TimeoutError` or `ConnectionRefusedError` in miner logs
- [ ] Signal bridge processing signals without errors
- [ ] Incentive / vtrust score trending upward (check after ~1 epoch)
- [ ] Disk usage within bounds (`df -h`)
- [ ] Memory usage stable (`free -h`)
- [ ] Alerts configured (see Section 8)

---

## 8. Monitoring

### 8.1 Log Locations

| Service | Log Command |
|---------|------------|
| Signal Bridge | `pm2 logs signal-bridge` |
| Taoshi Miner | `pm2 logs taoshi-miner` |
| System | `journalctl -u taoshi-miner -f` (if using systemd) |

### 8.2 Key Metrics to Watch

| Metric | How to Check | Alert Threshold |
|--------|-------------|----------------|
| Miner vtrust | `btcli s metagraph --netuid 8` | < 0.5 for >2 epochs |
| Axon uptime | `pm2 status` | Process not `online` |
| Signal bridge lag | `/api/v1/health` `active_signals` | 0 active signals |
| Signal age | `store.get_age_seconds(pair)` | > 300 s |
| RAM | `free -h` | > 80% used |
| Disk | `df -h /` | > 85% used |

### 8.3 Monitoring Script

```python
#!/usr/bin/env python3
# scripts/monitor.py
"""Lightweight monitor — run via cron every 5 minutes."""

import subprocess
import httpx
import time
import logging
import json

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

BRIDGE_URL = "http://127.0.0.1:8000/api/v1/health"
ALERT_CMD = None   # Set to e.g. ["curl", "-X", "POST", "<slack-webhook>", ...]


def check_bridge() -> bool:
    try:
        r = httpx.get(BRIDGE_URL, timeout=3)
        data = r.json()
        log.info(f"Bridge OK | active_signals={data.get('active_signals')}")
        return True
    except Exception as e:
        log.error(f"Bridge UNREACHABLE: {e}")
        return False


def check_pm2_process(name: str) -> bool:
    result = subprocess.run(
        ["pm2", "jlist"], capture_output=True, text=True
    )
    processes = json.loads(result.stdout)
    for proc in processes:
        if proc["name"] == name:
            status = proc["pm2_env"]["status"]
            log.info(f"pm2 {name}: {status}")
            return status == "online"
    log.error(f"pm2 process '{name}' not found")
    return False


def alert(message: str):
    log.warning(f"ALERT: {message}")
    if ALERT_CMD:
        # NOTE: use json.dumps to safely serialize message; raw f-string breaks on
        # special characters (quotes, newlines) and is a minor injection risk.
        import json as _json
        subprocess.run(ALERT_CMD + ["-d", _json.dumps({"text": message})])


if __name__ == "__main__":
    issues = []

    if not check_bridge():
        issues.append("Signal bridge is down")

    if not check_pm2_process("taoshi-miner"):
        issues.append("Taoshi miner process is not online")

    if not check_pm2_process("signal-bridge"):
        issues.append("Signal bridge process is not online")

    for issue in issues:
        alert(issue)

    if not issues:
        log.info("All checks passed.")
```

### 8.4 Cron Job for Monitor

```bash
# Add to crontab: crontab -e
*/5 * * * * /home/cricri/taoshi-miner/venv/bin/python \
    /home/cricri/taoshi-miner/scripts/monitor.py \
    >> /var/log/taoshi-monitor.log 2>&1
```

### 8.5 WandB Integration (optional)

```python
# In miner.py, add after imports:
import wandb

wandb.init(
    project="taoshi-miner-sn8",
    config={
        "netuid": 8,
        "wallet": "miner_cold/miner_hot",
    },
)

# Log per-response metrics in forward():
wandb.log({
    "trade_pair": trade_pair,
    "order_type": sig["order_type"],
    "leverage": sig["leverage"],
    "response_latency_ms": latency_ms,
})
```

### 8.6 Quick Health Check Commands

```bash
# Overall status
pm2 status

# Live miner logs
pm2 logs taoshi-miner --lines 50

# Subnet position
btcli s metagraph --netuid 8 --subtensor.network finney | grep $(btcli wallet overview --wallet.name miner_cold | grep miner_hot | awk '{print $3}')

# Signal bridge health
curl -s http://127.0.0.1:8000/api/v1/health | python3 -m json.tool

# Check current signal for BTCUSD
curl -s http://127.0.0.1:8000/api/v1/signal/BTCUSD | python3 -m json.tool
```

---

*Last updated: 2026-03-20*
