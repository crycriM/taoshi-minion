// pm2.config.js
// NOTE: pm2 must be started from the project root (~/taoshi-miner) so that
// signal_bridge is importable (relative imports require the parent dir on sys.path).
//
// Copy .env.example to .env and fill in your values before starting.
// PM2 will load .env automatically via dotenv if present.

const path = require("path");

// Load .env without requiring dotenv as a hard dependency
try {
  require("dotenv").config({ path: path.join(__dirname, ".env") });
} catch (_) {
  // dotenv not installed — rely on shell environment variables
}

const ROOT = __dirname;
const VENV_PYTHON = path.join(ROOT, "venv", "bin", "python");

const WALLET_NAME = process.env.WALLET_NAME || "miner_cold";
const WALLET_HOTKEY = process.env.WALLET_HOTKEY || "miner_hot";
const SUBTENSOR_NETWORK = process.env.SUBTENSOR_NETWORK || "finney";
const NETUID = process.env.NETUID || "8";
const AXON_PORT = process.env.AXON_PORT || "8091";
const SIGNAL_BRIDGE_HOST = process.env.SIGNAL_BRIDGE_HOST || "127.0.0.1";
const SIGNAL_BRIDGE_PORT = process.env.SIGNAL_BRIDGE_PORT || "8000";

module.exports = {
  apps: [
    {
      name: "signal-bridge",
      script: path.join(ROOT, "signal_bridge", "main.py"),
      interpreter: VENV_PYTHON,
      cwd: ROOT,
      args: `--host ${SIGNAL_BRIDGE_HOST} --port ${SIGNAL_BRIDGE_PORT}`,
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
      script: path.join(ROOT, "ptn", "neurons", "miner.py"),
      interpreter: VENV_PYTHON,
      args: [
        `--wallet.name ${WALLET_NAME}`,
        `--wallet.hotkey ${WALLET_HOTKEY}`,
        `--subtensor.network ${SUBTENSOR_NETWORK}`,
        `--netuid ${NETUID}`,
        `--axon.port ${AXON_PORT}`,
        "--logging.info",
      ].join(" "),
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
