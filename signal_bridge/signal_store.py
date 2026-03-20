import time
import threading
from typing import Optional
from .models import Signal, OrderType


DEFAULT_SIGNAL = Signal(
    trade_pair="",
    order_type=OrderType.FLAT,
    leverage=0.0,
    confidence=1.0,
    source="default",
)

SUPPORTED_PAIRS = [
    "BTCUSD",
    "ETHUSD",
    "SOLUSD",
    "XRPUSD",
    "DOGEUSD",
    "ADAUSD",
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


store = SignalStore()


__all__ = [
    "DEFAULT_SIGNAL",
    "SUPPORTED_PAIRS",
    "SignalStore",
    "store",
]
