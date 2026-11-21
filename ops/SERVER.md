# Развёртывание через GitHub

Домен — `visiooo.ru`, ожидаемый IPv4 — `31.192.110.184`. Предполагается Linux с Docker Engine, Compose v2 с поддержкой `up --wait`, Git, Python 3, Nginx и Certbot. Установка пакетов зависит от дистрибутива. Работать из учётной записи с доступом к Docker; файлы Nginx устанавливать через sudo.

## Первый запуск

Проверить, что `/opt/visiooo` свободен, а существующие сайты не обслуживают `visiooo.ru`. Не заменять конфигурации других проектов.

```bash
git clone https://github.com/Miha1990/visiooo.git /opt/visiooo
cd /opt/visiooo
python3 ops/init_production_env.py
nano app/.env
bash ops/deploy.sh
```

Генератор создаёт уникальные секрет приложения и пароль PostgreSQL. Повторный запуск не перезаписывает файл. Не менять пароль существующей базы простым редактированием `.env`: пароль внутри PostgreSQL меняется отдельно. Для писем заполнить `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`; TLS/SSL выбрать по требованиям почтового сервиса. Не включать платежи до выполнения [инструкции](PAYMENTS_AND_LEGAL.md).

База не публикует порт наружу, приложение доступно только по `127.0.0.1:18080`. Статика встроена в образ и обслуживается WhiteNoise. Приватные изображения выдаёт Django с проверкой доступа. Один процесс Gunicorn с четырьмя потоками: текущий ограничитель попыток входа хранится в памяти процесса.

## Nginx и HTTPS

Проверить A-запись, доступность портов 80/443 и отсутствие конфликтующего виртуального хоста. Установить начальную конфигурацию, если файл назначения ещё не занят:

```bash
sudo install -d /var/lib/myqr-acme
sudo cp ops/visiooo-http.conf.example /etc/nginx/conf.d/myqr-platform.conf
sudo nginx -t
sudo systemctl reload nginx
sudo certbot certonly --webroot -w /var/lib/myqr-acme -d visiooo.ru --email m@ros100.ru --agree-tos --non-interactive
sudo cp ops/visiooo-https.conf.example /etc/nginx/conf.d/myqr-platform.conf
sudo nginx -t
sudo systemctl reload nginx
curl --fail https://visiooo.ru/health/ready
sudo certbot renew --dry-run
```

Проверить расписание продления сертификатов. Пользовательские домены пока выключены: обработчик из `DOMAINS.md` нужно отдельно адаптировать к контейнерному запуску и порту 18080. Не включать до проверки.

## Обновления

Проверить изменения локально и отправить в `main`. GitHub используется только для хранения кода, без автоматических тестов и сборок. На сервере:

```bash
cd /opt/visiooo
bash ops/deploy.sh
```

Сценарий останавливается при изменённых отслеживаемых файлах, расходящихся ветках, ошибке сборки, резервирования, проверок либо миграций. Во время миграций старый процесс может обслуживать запросы: несовместимые изменения схемы требуют окна обслуживания. Автоматического отката схемы нет. При ошибке после миграций исправить причину и повторить запуск; не возвращать старую схему вслепую.

Копия PostgreSQL создаётся в `backups/` до миграций. Хранить копии вне сервера по своему расписанию, отдельно сохранять фотографии из тома `visiooo_private_media` и `app/.env`. Копия базы не содержит фотографий. Не выполнять `docker compose down -v`: это удаляет данные. Ограничить доступ к каталогу проекта и копиям.

## Диагностика и администратор

```bash
docker compose --env-file app/.env -f compose.production.yaml ps
docker compose --env-file app/.env -f compose.production.yaml logs --tail 100 web
docker compose --env-file app/.env -f compose.production.yaml exec web python manage.py createsuperuser
```

Периодическая сверка оплат: `exec -T web python manage.py reconcile_payments` с тем же префиксом Compose после включения ЮКассы; добавить в расписание сервера. Проверить регистрацию, письма, редактор, фото, публикацию, QR и уведомления оплаты. Первая серверная база пуста; локальные данные автоматически не импортируются.
