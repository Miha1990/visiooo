#!/usr/bin/env bash
set -euo pipefail
if [[ " ${RENEWED_DOMAINS:-} " == *' mail.visiooo.ru '* ]]; then
  cd /opt/visiooo
  docker compose --env-file ops/mail/.env -f compose.mail.yaml up -d --no-deps --force-recreate --wait --wait-timeout 300 mailserver
  nginx -t
  systemctl reload nginx
fi
