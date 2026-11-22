#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
test -f ops/mail/.env || { echo 'First run python3 ops/mail/init.py' >&2; exit 1; }
test -f /etc/letsencrypt/live/mail.visiooo.ru/fullchain.pem || { echo 'Issue the mail.visiooo.ru certificate first (ops/MAIL.md)' >&2; exit 1; }
dc=(docker compose --env-file ops/mail/.env -f compose.mail.yaml)
"${dc[@]}" config --quiet
"${dc[@]}" pull
"${dc[@]}" up -d --wait webmail_db
"${dc[@]}" up -d --no-deps --force-recreate --wait --wait-timeout 300 mailserver
"${dc[@]}" up -d webmail
"${dc[@]}" ps
echo 'Generate DKIM once if not done, publish DNS, then test incoming and outgoing delivery. See ops/MAIL.md.'
