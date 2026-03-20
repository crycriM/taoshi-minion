// pm2.config.js
// NOTE: pm2 must be started from ~/taoshi-miner so that signal_bridge is a
// importable package (relative imports require the parent dir on sys.path).
// Add cwd: "/home/cricri/projects/taoshi-miner" to each app entry.

module.exports = {
  apps: [
    {
      name: "signal-bridge",
      script: "/home/cricri/projects/taoshi-miner/signal_bridge/main.py",
      interpreter: "/home/cricri/projects/taoshi-miner/venv/bin/python",
      cwd: "/home/cricri/projects/taoshi-miner",
      args: "--host 127.0.0.1 --port 8000",
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
      script: "/home/cricri/projects/taoshi-miner/ptn/neurons/miner.py",
      interpreter: "/home/cricri/projects/taoshi-miner/venv/bin/python",
      args: "--wallet.name miner_cold --wallet.hotkey miner_hot --subtensor.network finney --netuid 8 --axon.port 8091 --logging.info",
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
