import time
import threading
from .base import BaseProvider
from ..models import Signal, OrderType
from ..signal_store import store, SUPPORTED_PAIRS, DEFAULT_SIGNAL


class ExampleProvider(BaseProvider):
    """Example provider that returns fixed signals for testing."""

    def __init__(self, update_interval: float = 60.0):
        self.update_interval = update_interval
        self._thread = None
        self._running = False

    def fetch_signals(self) -> list[Signal]:
        """Return the latest signals from this provider."""
        signals = []
        for pair in SUPPORTED_PAIRS:
            if pair == "BTCUSD":
                signals.append(
                    Signal(
                        trade_pair=pair,
                        order_type=OrderType.LONG,
                        leverage=0.5,
                        confidence=1.0,
                        source="example",
                    )
                )
            else:
                signals.append(
                    Signal(
                        trade_pair=pair,
                        order_type=OrderType.FLAT,
                        leverage=0.0,
                        confidence=1.0,
                        source="example",
                    )
                )
        return signals

    def start(self) -> None:
        """Start the background thread that updates the store."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the background thread."""
        self._running = False
        if self._thread:
            self._thread.join()

    def _run_loop(self) -> None:
        """Background loop that updates the store at intervals."""
        while self._running:
            signals = self.fetch_signals()
            for signal in signals:
                store.update(signal)
            time.sleep(self.update_interval)
