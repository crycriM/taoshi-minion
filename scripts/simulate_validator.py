#!/usr/bin/env python3
"""Send a mock SendSignal to the local axon to verify the miner responds."""

import asyncio
import bittensor as bt
import os
import argparse
from template.protocol import SendSignal


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--miner_ip", default=os.getenv("MINER_IP", "127.0.0.1"))
    parser.add_argument(
        "--miner_port", type=int, default=int(os.getenv("MINER_PORT", "8091"))
    )
    parser.add_argument("--trade_pair", default=os.getenv("TRADE_PAIR", "BTCUSD"))
    args = parser.parse_args()

    wallet = bt.wallet(
        name=os.getenv("WALLET_NAME", "miner_cold"),
        hotkey=os.getenv("WALLET_HOTKEY", "miner_hot"),
    )
    dendrite = bt.dendrite(wallet=wallet)

    axon_info = bt.AxonInfo(
        ip=args.miner_ip,
        port=args.miner_port,
        hotkey=wallet.hotkey.ss58_address,
        coldkey=wallet.coldkeypub.ss58_address,
        version=1,
        ip_type=4,
    )

    signal = {
        "trade_pair": args.trade_pair,
        "order_type": "LONG",
        "leverage": 0.5,
    }

    synapse = SendSignal(signal=signal)

    response = await dendrite.forward(
        axons=[axon_info],
        synapse=synapse,
        timeout=12,
    )

    print(f"Response status: {response.successfully_processed}")
    print(f"Error message: {response.error_message}")
    print(f"Order JSON: {response.order_json}")

    if response.order_json:
        import json

        order = json.loads(response.order_json)
        print(f"Order type: {order.get('order_type')}")
        print(f"Order leverage: {order.get('leverage')}")


if __name__ == "__main__":
    asyncio.run(main())
