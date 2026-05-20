# Flutter APK Build Automation

Production automation script that polls a backend API for pending APK build jobs,
injects the requested base URL into a Flutter project, builds a signed release APK,
and reports completion back to the API.

## Architecture

```
   API Server                  VPS
  ┌──────────┐    poll       ┌──────────────┐
  │ pending  │ ◄──────────── │   Poller     │
  │ jobs     │                │              │
  └──────────┘                └──────┬───────┘
        ▲                            │ enqueue
        │ complete                   ▼
        │                     ┌──────────────┐
        └─────────────────────│  Redis Queue │
                              └──────┬───────┘
                                     │ dequeue
                                     ▼
                              ┌──────────────┐
                              │ Build Worker │
                              │              │
                              │ git pull     │
                              │ inject URL   │
                              │ flutter build│
                              └──────────────┘
```

## Prerequisites

- Python 3.10+
- Redis server running (default: localhost:6379)
- Flutter SDK installed and in PATH
- Android SDK installed
- Git installed
- Flutter project cloned at `PROJECT_PATH` with the keystore configured

## Installation

```bash
cd /home/builder/automation
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API URL, BOT key, and paths
nano .env
```

## Manual Run

```bash
# Combined (both poller and builder in one process)
python main.py

# Or as separate processes
python -m workers.poller   # Terminal 1
python -m workers.builder  # Terminal 2
```

## Configuration

All configuration lives in `.env`. See `.env.example` for the full list.

Key settings:
- `API_BASE_URL` – your backend's URL
- `BOT_API_KEY` – the X-BOT-KEY header value
- `PROJECT_PATH` – path to the cloned Flutter project
- `POLL_INTERVAL_SECONDS` – how often to check for pending jobs (default 10)

## How URL Injection Works

For each job, the bot receives `full_domain` (e.g. `mars.bkserver.tech`) and
constructs `https://mars.bkserver.tech/api/v1`. That URL replaces the value of:

- `baseUrl` in `lib/utils/constants.dart`
- `BASE_URL` in `android/app/src/main/kotlin/com/example/login_app/api/JobApiService.kt`

Both files are backed up before modification. If anything fails, originals are
restored automatically.

## Logs

Logs are written to `LOG_DIR` (default: `./logs/automation.log`) with rotation
(5 MB per file, 5 backups). Console output mirrors the file logs.

## Built APKs

Each successful build produces a file at:

```
APK_OUTPUT_DIR/build_{job_id}_{safe_domain}.apk
```

For example: `/home/builder/apk-outputs/build_28_mars_bkserver_tech.apk`
