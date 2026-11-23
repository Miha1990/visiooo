#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
  echo 'Есть изменения файлов проекта. Сначала сохраните их в Git.' >&2
  exit 1
fi
test -f app/.env || { echo 'Сначала выполните python3 ops/init_production_env.py' >&2; exit 1; }
git pull --ff-only origin main
dc=(docker compose --env-file app/.env -f compose.production.yaml)
"${dc[@]}" config --quiet
"${dc[@]}" build --pull web
"${dc[@]}" up -d --wait db
umask 077
mkdir -p backups
backup="backups/database-$(date -u +%Y%m%dT%H%M%SZ)-$$.dump"
"${dc[@]}" exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$backup"
test -s "$backup"
"${dc[@]}" run --rm --no-deps web python manage.py check --deploy --fail-level WARNING
"${dc[@]}" run --rm --no-deps web python manage.py migrate --noinput
"${dc[@]}" run --rm --no-deps web python manage.py install_premium_template
"${dc[@]}" up -d --wait --wait-timeout 120 web notifications
"${dc[@]}" exec -T web python manage.py cleanup_unused_assets
"${dc[@]}" exec -T web python manage.py cleanup_analytics_consents
"${dc[@]}" ps
echo "Обновление завершено. Резервная копия базы: $backup"
