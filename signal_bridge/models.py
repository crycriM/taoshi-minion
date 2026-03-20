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
    leverage: float = Field(default=0.5, ge=0.0, le=10.0)
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


class IngestResponse(BaseModel):
    status: str
    trade_pair: str


__all__ = [
    "OrderType",
    "Signal",
    "SignalResponse",
    "BulkSignalResponse",
    "IngestResponse",
]
