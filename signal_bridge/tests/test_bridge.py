import pytest
from fastapi.testclient import TestClient
from signal_bridge.main import app
from signal_bridge.signal_store import store, SUPPORTED_PAIRS, DEFAULT_SIGNAL


client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_store():
    store._signals.clear()
    store._timestamps.clear()


def test_health_ok():
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "supported_pairs" in data
    assert "active_signals" in data


def test_ingest_valid():
    payload = {
        "trade_pair": "BTCUSD",
        "order_type": "LONG",
        "leverage": 0.5,
        "confidence": 0.9,
    }
    resp = client.post("/api/v1/signal", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["trade_pair"] == "BTCUSD"


def test_ingest_invalid_pair():
    payload = {"trade_pair": "FAKEPAIR", "order_type": "LONG", "leverage": 0.5}
    resp = client.post("/api/v1/signal", json=payload)
    assert resp.status_code == 400


def test_leverage_above_max():
    payload = {"trade_pair": "BTCUSD", "order_type": "LONG", "leverage": 3.0}
    resp = client.post("/api/v1/signal", json=payload)
    assert resp.status_code == 422


def test_leverage_below_min():
    payload = {"trade_pair": "BTCUSD", "order_type": "LONG", "leverage": -0.1}
    resp = client.post("/api/v1/signal", json=payload)
    assert resp.status_code == 422


def test_get_signal_defaults_flat():
    resp = client.get("/api/v1/signal/ETHUSD")
    assert resp.status_code == 200
    data = resp.json()
    assert data["order_type"] == "FLAT"
    assert data["leverage"] == 0.0


def test_get_signal_after_update():
    client.post(
        "/api/v1/signal",
        json={"trade_pair": "ETHUSD", "order_type": "SHORT", "leverage": 0.3},
    )
    resp = client.get("/api/v1/signal/ETHUSD")
    assert resp.status_code == 200
    data = resp.json()
    assert data["order_type"] == "SHORT"
    assert data["leverage"] == 0.3


def test_get_signal_case_insensitive():
    client.post(
        "/api/v1/signal",
        json={"trade_pair": "btcusd", "order_type": "LONG", "leverage": 0.5},
    )
    resp = client.get("/api/v1/signal/BTCUSD")
    assert resp.status_code == 200
    data = resp.json()
    assert data["order_type"] == "LONG"
    assert data["trade_pair"] == "BTCUSD"


def test_bulk_contains_all_pairs():
    resp = client.get("/api/v1/signals")
    assert resp.status_code == 200
    data = resp.json()
    assert "signals" in data
    assert "timestamp" in data
    for pair in SUPPORTED_PAIRS:
        assert pair in data["signals"]


def test_stale_signal_returns_flat(monkeypatch):
    import signal_bridge.router as router_module

    store._signals.clear()
    store._timestamps.clear()

    store._signals["BTCUSD"] = DEFAULT_SIGNAL
    store._timestamps["BTCUSD"] = 0

    monkeypatch.setattr(router_module, "MIN_SIGNAL_AGE_SEC", 10)

    resp = client.get("/api/v1/signal/BTCUSD")
    assert resp.status_code == 200
    data = resp.json()
    assert data["order_type"] == "FLAT"
