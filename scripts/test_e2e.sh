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

echo "[5] POST a FLAT signal and assert it overwrites..."
curl -sf -X POST "$BRIDGE/api/v1/signal" \
  -H "Content-Type: application/json" \
  -d '{"trade_pair":"BTCUSD","order_type":"FLAT","leverage":0.0}' \
  | python3 -m json.tool

echo "[6] Verify FLAT signal..."
curl -sf "$BRIDGE/api/v1/signal/BTCUSD" | python3 -c "
import sys, json
d = json.load(sys.stdin)
assert d['order_type'] == 'FLAT', f'Expected FLAT, got {d}'
print('PASS: BTCUSD signal is now FLAT')
"

echo "All integration tests passed."
