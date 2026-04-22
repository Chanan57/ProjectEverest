# OpenClaw 🦅

OpenClaw is a modular, high-performance quantitative trading bot designed for precision execution and robust risk management. It serves as the refined successor to the Project Everest suite, focusing on a clean, decoupled architecture for algorithmic trading.

## 🚀 Current Status: Project Reset & Migration

**Last Update: April 22, 2026**

The project has undergone a significant architectural reset to transition from the legacy "Project Everest" codebase to the streamlined "OpenClaw" engine.

### Recent Updates:
- **Repository Cleanse**: Wiped legacy "Project Everest" files to establish a high-signal-to-noise codebase.
- **Architecture Initialization**:
    - **`/core-engine`**: Centralized logic for strategy execution and MetaTrader 5 interaction.
    - **`/data-bridge`**: Node.js layer for real-time market data ingestion.
    - **`/telemetry`**: Asynchronous notification and system health monitoring pipeline.
    - **`/infrastructure`**: Automated setup and environmental orchestration scripts.
- **Execution Layer**: Integrated the initial `mt5_executor` for raw order routing and account state telemetry.

## 🛠 Project Structure

```text
/
├── core-engine/         # Primary Python execution engine
├── data-bridge/         # Real-time data processing layer (Node.js)
├── infrastructure/      # System setup and monitoring
├── telemetry/           # Telegram and system notifications
├── config.yaml          # Global bot configuration
└── .env (Local Only)    # MetaTrader 5 credentials and API keys
```

## 🔒 Security Note
This repository excludes local secrets (`.env`), virtual environments (`venv`), and package dependencies (`node_modules`) to maintain security and performance. Ensure you configure your local `.env` using the provided architecture.

---
*OpenClaw — Precision in every trade.*
