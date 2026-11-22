#!/usr/bin/env bash
set -euo pipefail
if [[ " ${RENEWED_DOMAINS:-} " == *' mail.visiooo.ru '* ]]; then
  cd /opt/visiooo
  docker compose --env-file ops/mail/.env -f compose.mail.yaml restart mailserver
  nginx -t
  systemctl reload nginx
fi
