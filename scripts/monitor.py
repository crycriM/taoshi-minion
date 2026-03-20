#!/usr/bin/env python3
# scripts/monitor.py
"""Lightweight monitor — run via cron every 5 minutes."""

import subprocess
import httpx
import time
import logging
import json
import os

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

BRIDGE_URL = "http://127.0.0.1:8000/api/v1/health"
ALERT_WEBHOOK_URL = os.getenv("ALERT_WEBHOOK_URL")


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
    result = subprocess.run(["pm2", "jlist"], capture_output=True, text=True)
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
    if ALERT_WEBHOOK_URL:
        subprocess.run(
            [
                "curl",
                "-X",
                "POST",
                "-H",
                "Content-Type: application/json",
                "-d",
                json.dumps({"text": message}),
                ALERT_WEBHOOK_URL,
            ]
        )


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
