import time
import os
from fastapi import APIRouter, HTTPException
from .models import (
    Signal,
    SignalResponse,
    BulkSignalResponse,
    OrderType,
    IngestResponse,
)
from .signal_store import store, SUPPORTED_PAIRS, DEFAULT_SIGNAL

router = APIRouter(prefix="/api/v1")

MIN_SIGNAL_AGE_SEC = int(os.getenv("MIN_SIGNAL_AGE_SEC", "300"))


@router.post("/signal", response_model=IngestResponse)
async def ingest_signal(signal: Signal):
    """Accept a new signal from an upstream source."""
    pair_upper = signal.trade_pair.upper()
    if pair_upper not in SUPPORTED_PAIRS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported trade pair: {signal.trade_pair}. "
            f"Supported: {SUPPORTED_PAIRS}",
        )
    normalized_signal = Signal(
        trade_pair=pair_upper,
        order_type=signal.order_type,
        leverage=signal.leverage,
        confidence=signal.confidence,
        source=signal.source,
    )
    store.update(normalized_signal)
    return IngestResponse(status="ok", trade_pair=pair_upper)


@router.get("/signal/{trade_pair}", response_model=SignalResponse)
async def get_signal(trade_pair: str):
    """Get the current signal for a specific trade pair."""
    pair_upper = trade_pair.upper()
    age = store.get_age_seconds(pair_upper)
    if age is not None and age > MIN_SIGNAL_AGE_SEC:
        with store._lock:
            store._signals.pop(pair_upper, None)
            store._timestamps.pop(pair_upper, None)
    sig = store.get(pair_upper)
    return SignalResponse(
        trade_pair=pair_upper,
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
            1 for p in SUPPORTED_PAIRS if store.get_age_seconds(p) is not None
        ),
    }
