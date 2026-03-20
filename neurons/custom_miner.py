import os
import httpx
from vali_objects.vali_dataclasses.order import Order
from template.protocol import SendSignal


SIGNAL_BRIDGE_URL = os.getenv("SIGNAL_BRIDGE_URL", "http://127.0.0.1:8000")
SIGNAL_BRIDGE_TIMEOUT_SEC = int(os.getenv("SIGNAL_BRIDGE_TIMEOUT_SEC", "2"))


async def forward(self, synapse: SendSignal) -> SendSignal:
    """
    Override forward to fetch signals from the signal bridge.

    This method fetches the current signal for the trade pair from the signal bridge
    and constructs an Order to return in the response.
    """
    try:
        trade_pair = synapse.signal.get("trade_pair", "")

        if not trade_pair:
            synapse.error_message = "No trade_pair in signal"
            synapse.successfully_processed = False
            return synapse

        async with httpx.AsyncClient(timeout=SIGNAL_BRIDGE_TIMEOUT_SEC) as client:
            resp = await client.get(f"{SIGNAL_BRIDGE_URL}/api/v1/signal/{trade_pair}")
            resp.raise_for_status()
            data = resp.json()

            order_type = data.get("order_type", "FLAT")
            leverage = float(data.get("leverage", 0.0))

            synapse.order_json = Order(
                trade_pair=trade_pair,
                order_type=order_type,
                leverage=leverage,
            ).model_dump_json()
            synapse.successfully_processed = True

    except Exception as e:
        synapse.error_message = f"Signal bridge error: {str(e)}"
        synapse.successfully_processed = False
        synapse.order_json = Order(
            trade_pair=synapse.signal.get("trade_pair", ""),
            order_type="FLAT",
            leverage=0.0,
        ).model_dump_json()

    return synapse
