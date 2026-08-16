# Production deployment

This runbook uses one Linux VPS, long polling, local Redis and local SQLite.
It does not require Docker, a public HTTP port or a webhook.

## 1. Server prerequisites

Install Python 3.13+, Git, Redis and systemd. Create a dedicated unprivileged
user, for example `smm-bot`, then put the project in a private directory such
as `/opt/smm-bot` owned by that user.

```bash
sudo adduser --system --group --home /opt/smm-bot smm-bot
sudo -u smm-bot git clone <REPOSITORY_URL> /opt/smm-bot
sudo -u smm-bot python3 -m venv /opt/smm-bot/.venv
sudo -u smm-bot /opt/smm-bot/.venv/bin/pip install -r /opt/smm-bot/requirements.txt
```

## 2. Environment

Create `/etc/smm-bot/smm-bot.env`, owned by root and readable by the bot
service group only. Copy names from `.env.example`; do not commit this file.

Required values:

```text
TELEGRAM_BOT_TOKEN=<token>
FSM_REDIS_URL=redis://127.0.0.1:6379/0
LOG_LEVEL=INFO
BACKUP_DIRECTORY=backups
```

`OPENAI_API_KEY`, `GEMINI_API_KEY` and `GROQ_API_KEY` are optional. They are
needed only when the matching AI provider is selected.

```bash
sudo install -d -m 0750 /etc/smm-bot
sudoedit /etc/smm-bot/smm-bot.env
sudo chown root:smm-bot /etc/smm-bot/smm-bot.env
sudo chmod 0640 /etc/smm-bot/smm-bot.env
```

## 3. Redis

Install and enable Redis locally. Keep it bound to localhost; do not expose
port 6379 publicly.

```bash
sudo systemctl enable --now redis-server
sudo systemctl status redis-server
```

The configured `FSM_REDIS_URL` must match this local service. A password is
not required for a localhost-only MVP setup; do not put credentials in Git.

## 4. Health check

Run before starting the bot and after upgrades:

```bash
sudo -u smm-bot /opt/smm-bot/.venv/bin/python /opt/smm-bot/scripts/check_health.py
```

It validates required configuration, Redis connectivity and `PRAGMA
integrity_check` for each existing SQLite database. Missing optional databases
are skipped and never created by the check.

## 5. systemd bot service

Copy `deploy/smm-bot.service.example` to `/etc/systemd/system/smm-bot.service`.
Replace only `<BOT_USER>`, `<BOT_GROUP>`, `<PROJECT_DIRECTORY>` and
`<ENVIRONMENT_FILE>` with server-specific paths; never put secrets in the unit.

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now smm-bot
sudo systemctl status smm-bot
sudo journalctl -u smm-bot -f
```

The unit restarts the process after failure with a five-second delay. Logs are
available through journald. Stop it with `sudo systemctl stop smm-bot`.

## 6. Daily SQLite backup

Copy both backup templates to `/etc/systemd/system/` as
`smm-bot-backup.service` and `smm-bot-backup.timer`, replacing the same
placeholders. Then enable the timer:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now smm-bot-backup.timer
sudo systemctl list-timers smm-bot-backup.timer
sudo systemctl start smm-bot-backup.service
sudo journalctl -u smm-bot-backup.service
```

Backups use SQLite's backup API and validate integrity. They are stored in
`BACKUP_DIRECTORY`, must remain private to the bot user, and are not uploaded
or restored automatically.

## 7. Update and rollback

Before an update, run a backup and health check. Then:

```bash
sudo systemctl stop smm-bot
sudo -u smm-bot git -C /opt/smm-bot pull
sudo -u smm-bot /opt/smm-bot/.venv/bin/pip install -r /opt/smm-bot/requirements.txt
sudo -u smm-bot /opt/smm-bot/.venv/bin/python /opt/smm-bot/scripts/check_health.py
sudo systemctl start smm-bot
```

To roll back code, stop the service, check out the known previous Git commit,
run the health check, then start it again. SQLite restore remains a deliberate
manual operation after verifying the chosen backup.
