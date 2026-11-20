# Email Automation – Google Account Signup

A **backend‑focused** Python project that automates the Google account creation flow using **FastAPI**, **async SQLAlchemy**, and **Playwright**. The service exposes a clean REST API to start, monitor, and resume signup jobs, handling human‑intervention stages (phone & selfie verification) without compromising architecture.

## Features
- **Async FastAPI endpoints** for starting, checking status, and resuming jobs.
- **State‑machine driven workflow** with explicit steps: `NAME → BIRTHDAY_GENDER → USERNAME → PASSWORD → PHONE_VERIFICATION → … → COMPLETED`.
- **Playwright** automation that interacts with realistic mock pages and can be swapped for the live Google UI.
- **Robust error handling** – detailed logs, validation of each field before clicking *Next*, and graceful fallback to manual intervention.
- **Persistence** using SQLite via SQLAlchemy `asyncio` engine (`aiosqlite`).
- **Full test suite** (`pytest‑asyncio`) covering detection, step execution, validation errors, and pause/resume logic.

## Quick start (Windows)
```powershell
# 1. Clone the repo (or copy the project folder)
git clone https://github.com/vansh-mak/Email-Automation.git
cd Email-Automation

# 2. Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt
# (or use the generated requirements.txt in the repo)

# 4. Run the FastAPI server
venv\Scripts\python.exe run_app.bat   # custom launcher that activates venv and runs main.py
# Server starts on http://127.0.0.1:8000
```

## API Overview
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/automation/start` | Starts a new signup job. Accepts either a full `SignupInput` payload or top‑level fields (first/last name, password, etc.). |
| `GET`  | `/automation/status/{job_id}` | Returns job status, current step, and any error messages. |
| `POST` | `/automation/resume/{job_id}` | Resumes a job that is waiting for user interaction (phone or selfie verification). |
| `DELETE`| `/automation/credentials/{username}` | Deletes stored credentials for a given username. |

## Core design components
- **`automation/signup.py`** – step detection (`detect_page_step`) and individual step handlers (`handle_name_step`, `handle_birthday_gender_step`, …). Each handler validates input values and logs detailed diagnostics.
- **`services/orchestrator.py`** – coordinates the workflow, updates job status, and triggers pause/resume events.
- **`services/job_registry.py`** – in‑memory registry of active jobs, exposing thread‑safe status updates.
- **Database layer** (`database/session.py`, `database/crud.py`) – async SQLite engine, schema migrations, and helper functions for persisting job records.
- **Tests** (`tests/`) – mock HTML site reproducing the Google signup flow, plus extensive unit tests for every step.

## Development & testing notes
- The mock site lives under `tests/mock_site/` and is served by `tests/mock_site/mock_app.py`. It mimics the essential UI components (name, DOB, gender, username, password, etc.).
- Run the full test suite with:
```powershell
venv\Scripts\python.exe -m pytest -q
```
- Playwright browsers are installed in the venv (`playwright install`). The first run may download browser binaries.

## Contributing
1. Fork the repository.
2. Create a feature branch.
3. Add/modify code and tests.
4. Ensure `pytest` passes.
5. Open a pull request.

## License
MIT – feel free to use, modify, and ship the automation in your own projects.
