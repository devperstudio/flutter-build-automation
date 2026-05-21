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

```base
nano /etc/systemd/system/flutter-build-automation.service
```
```base
systemctl daemon-reload
```
```base
# Boot এ auto-start enable করুন
systemctl enable flutter-build-automation
```
```base
# Service start করুন
systemctl start flutter-build-automation
```
```base
systemctl status flutter-build-automation
```
```base
# Stop
systemctl stop flutter-build-automation

# Start
systemctl start flutter-build-automation

# Restart (code update করলে)
systemctl restart flutter-build-automation

# Disable auto-start
systemctl disable flutter-build-automation

# Enable auto-start
systemctl enable flutter-build-automation
```

```bash
[Unit]
Description=Flutter APK Build Automation Service
After=network-online.target redis-server.service
Wants=network-online.target
Requires=redis-server.service

[Service]
Type=simple
User=root
WorkingDirectory=/home/builder/flutter-build-automation

Environment="PATH=/home/builder/flutter-build-automation/venv/bin:/opt/flutter/bin:/opt/android-sdk/cmdline-tools/latest/bin:/opt/android-sdk/platform-tools:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64"
Environment="ANDROID_HOME=/opt/android-sdk"
Environment="ANDROID_SDK_ROOT=/opt/android-sdk"
Environment="PYTHONUNBUFFERED=1"

ExecStart=/home/builder/flutter-build-automation/venv/bin/python /home/builder/flutter-build-automation/main.py

# === Auto-restart Configuration ===
Restart=always
RestartSec=10
StartLimitIntervalSec=600
StartLimitBurst=20

# === Resource Limits ===
MemoryMax=6G
MemoryHigh=5G
TasksMax=512

# === Process Management ===
KillMode=mixed
KillSignal=SIGTERM
TimeoutStopSec=60
SendSIGKILL=yes
FinalKillSignal=SIGKILL

# === Logging ===
StandardOutput=append:/home/builder/flutter-build-automation/logs/service.log
StandardError=append:/home/builder/flutter-build-automation/logs/service-error.log

[Install]
WantedBy=multi-user.target
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
