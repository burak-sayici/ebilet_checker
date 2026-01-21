# PROJECT MEMORY BANK & AI CONTEXT
> **⚠️ SYSTEM INSTRUCTION FOR AI AGENTS:**
> **Any changes, refactors, or new features added to this codebase MUST be logged in the "Recent Changes History" section at the bottom of this file.**
> **Read this file at the start of every session to understand the project architecture and state.**

## 1. Project Overview
**Name:** TCDD E-Bilet Checker Bot
**Type:** Asynchronous Telegram Bot
**Purpose:** Monitors train ticket availability on the Turkish State Railways (TCDD) API.
**Core Features:** Multi-threading monitoring, User Authentication (SQLite), Dynamic Token Scraping, Advanced Filtering (Business class, Seat count, Time range).

## 2. Architecture & Tech Stack
The project follows a **Modular Layered Architecture**.

**Root Directory:** `src/`
**Entry Point:** `src/main.py` -> `src/interfaces/telegram/bot.py`

### 2.1. Modules
*   **`src/api/`**: Handles external communication.
    *   `token_manager.py`: Scrapes the web page to extract the dynamic Bearer token (JWT) hidden in JS files. Handles caching.
    *   `tcdd_client.py`: Uses `requests` to call TCDD endpoints (`train-availability`, `station-pairs`).
*   **`src/models/`**: `dataclass` definitions for type safety.
    *   `station.py`, `train.py`: Domain entities.
    *   `monitor_config.py`: Configuration for a single monitoring job (filters, dates, stations, UUID `job_id`).
*   **`src/services/`**: Core Business Logic (Platform Agnostic).
    *   `auth_service.py`: SQLite-based auth. Checks `chat_id` against `users.db`.
    *   `station_service.py`: Caches stations, handles search normalization (Turkish chars).
    *   `monitor_service.py`: Manages monitoring threads. Stores jobs in `_jobs` (dict) mapped by UUID. Handles `stop_monitor` logic.
    *   `ticket_service.py`: bridges API and Models, parses complex JSON responses from TCDD.
*   **`src/interfaces/telegram/`**: Frontend Layer.
    *   `bot.py`: Dependency Injection container. Initializes services and starts the App.
    *   `handlers.py`: Contains `@auth_required` decorator, CommandHandlers (`/start`, `/monitor`, `/status`), and CallbackQueryHandlers.
    *   `session.py`: Manages ephemeral user state (wizard steps) during setup.

### 2.2. Key Technologies
*   **Python 3.10+**
*   **python-telegram-bot (v20+ async):** ApplicationBuilder pattern.
*   **SQLite3:** For persisting authorized users.
*   **Threading:** Standard `threading` library for concurrent monitoring jobs.
*   **Docker:** Containerization support.

## 3. Critical Implementation Details

### 3.1. Authentication Flow
1.  User sends message.
2.  `@auth_required` decorator checks `AuthService`.
3.  If not authorized, bot asks for password.
4.  If password matches `BOT_PASSWORD` (env), `chat_id` is saved to `users.db`.

### 3.2. Monitoring Flow
1.  User completes the wizard (Station -> Date -> Time -> Filters).
2.  `MonitorService.start_monitor` creates a new `Thread` with a unique UUID (`job_id`).
3.  The thread runs `_monitoring_loop`, checking API every 30s.
4.  State changes (New seats) trigger `on_change` callback, sending Telegram message.
5.  Users can manage jobs via `/status`, which lists active jobs with "Stop" buttons.

### 3.3. Multi-Monitor Logic
*   Unlike typical bots, this bot allows **N tasks per user**.
*   `MonitorService` maps `chat_id -> [job_id_1, job_id_2]`.
*   Each task runs independently.

### 3.4. Environment Variables (.env)
*   `TELEGRAM_API_TOKEN`: Bot token.
*   `BOT_PASSWORD`: Static password for user access.

## 4. Recent Changes History (Log)

*   **[2026-01-21] Initial Refactor to Version 3.0 (Modular OOP):**
    *   Converted single-file script to `src/` directory structure.
    *   Implemented proper Service/Repo pattern.
    *   Added `TokenManager` for dynamic auth token scraping.
*   **[2026-01-21] Feature: Advanced Monitor Filters:**
    *   Added Time Selection (Checkbox style inline keyboard).
    *   Added Business Class toggle and Minimum Seat Count.
*   **[2026-01-21] Feature: Authentication & DB:**
    *   Added SQLite `users.db`.
    *   Added `BOT_PASSWORD` logic.
    *   Removed hardcoded admin IDs.
*   **[2026-01-21] Feature: Multi-Tasking & Management:**
    *   Refactored `MonitorService` to use UUIDs.
    *   Added `/status` command to list and kill specific jobs.
    *   Updated Dockerfile for new structure.
    *   Cleaned up `TELEGRAM_CHAT_ID` from config.
