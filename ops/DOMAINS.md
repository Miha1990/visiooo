# Свой домен в myQR

За основу взят проект SPCh: `docs/landing-domains.md`, DNS-проверки сервиса лендингов и отдельные virtual host Nginx/Certbot. В SPCh ничего не изменено; его домены, IP, секреты и сертификаты не переносятся.

## Для владельца визитки

1. Откройте **Мои визитки → Свой домен** или ссылку в редакторе. Укажите принадлежащий вам домен без `https://`, порта и пути, выберите электронную визитку. Доступен один домен на рабочее пространство.
2. В DNS у регистратора добавьте показанный TXT `_myqr-verification.<ваш-домен>` и A на публичный IPv4 myQR. Имя записи и её значение — разные поля. Если панель приписывает домен зоны автоматически, укажите только оставшуюся левую часть имени; например, `_myqr-verification.card` для `card.example.ru` в зоне `example.ru`. Для A поддоменом будет `card`, для корня зоны — обычно `@`.
3. Уберите конфликтующие A/AAAA/CNAME только для подключаемого адреса, не меняйте почтовые MX. Отключите проксирование CDN. Текущая версия использует IPv4. Дождитесь обновления DNS и нажмите **Проверить DNS**; TXT нужно сохранить после подключения.
4. Опубликуйте визитку с активным Pro и нажмите **Выпустить HTTPS**. Статус очереди обновляется автоматически. Нажмите **Открыть мой домен** после появления «HTTPS подключён».

Домен открывает выбранную визитку на `/` без перехода на основной домен. Можно поменять назначенную визитку внутри своего пространства. Старый адрес платформы и QR/NFC продолжают работать. QR со своим доменом скачивается отдельно после активации; он зависит от владения этим доменом. Вход, кабинет, оплата и админка доступны только на основном адресе.

Отключение закрывает доступ и меняет TXT-токен. После отключения привязку можно удалить; новое подключение требует нового подтверждения. Серверные файлы старого HTTPS не удаляются автоматически. Если тот же домен подключают заново с другим ID, администратор должен проверить и убрать старый `myqr-domain-<старый UUID>.conf`, чтобы исключить конфликт virtual host; чужие конфигурации сервис не перезаписывает. `www` и имя без `www` считаются разными доменами.

## Однократная настройка сервера

Нужен Linux-сервер с публичным IPv4, Nginx, Certbot, systemd и уже развёрнутым myQR с PostgreSQL. Порты 80/443 доступны из интернета. Приложение слушает только loopback, например `127.0.0.1:8000`, через production WSGI-сервер. `runserver` не используется для публичного размещения. Код, виртуальное окружение и `.env` принадлежат администратору, недоступны для записи процессу веб-приложения; отдельная директория `private-media` доступна для загрузок. Worker выполняется с правами на Nginx/Certbot, отдельно от веб-процесса.

В `app/.env` задайте реальные значения:

```dotenv
DEBUG=false
ENVIRONMENT=production
SECRET_KEY=<постоянный случайный секрет>
DATABASE_URL=postgresql://<пользователь>:<пароль>@127.0.0.1/<база>
ALLOWED_HOSTS=<основной-домен-платформы>
PUBLIC_BASE_URL=https://<основной-домен-платформы>
CUSTOM_DOMAINS_ENABLED=true
DOMAIN_IPV4=<публичный IPv4 именно сервера myQR>
DOMAIN_ACME_EMAIL=<email администратора для ACME>
DOMAIN_UPSTREAM_PORT=8000
TRUST_PROXY=true
```

Основные адреса/старые алиасы платформы перечисляются в ALLOWED_HOSTS через запятую, без wildcard. Клиентские домены добавлять туда не надо: их проверяет отдельный middleware по реестру. `TRUST_PROXY` включают только при закрытом внешнем доступе к WSGI; Nginx должен сам устанавливать `X-Forwarded-Proto`. Нельзя направлять клиентский домен на процесс с публично доступным HTTP-портом приложения.

Примените миграции и соберите static:

```bash
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python app/manage.py migrate
.venv/bin/python app/manage.py collectstatic --noinput
.venv/bin/python app/manage.py check --deploy --fail-level WARNING
sudo nginx -t
```

Файлы `ops/myqr-domains*.service.example` рассчитаны на `/opt/myQR`. Измените абсолютные пути, если развёртывание находится в другом каталоге. Worker использует тот же `app/.env` и ту же БД, что и приложение.

```bash
sudo install -m 644 ops/myqr-domains.service.example /etc/systemd/system/myqr-domains.service
sudo install -m 644 ops/myqr-domains.timer /etc/systemd/system/myqr-domains.timer
sudo install -m 644 ops/myqr-domains-renew.service.example /etc/systemd/system/myqr-domains-renew.service
sudo install -m 644 ops/myqr-domains-renew.timer /etc/systemd/system/myqr-domains-renew.timer
sudo systemctl daemon-reload
sudo systemctl enable --now myqr-domains.timer myqr-domains-renew.timer
```

Серверный сервис отправляет heartbeat в БД. Без живого сервиса кнопка HTTPS недоступна. Каждые 15 секунд обрабатывается один запрос сертификата, а также один активный домен с просроченной шестичасовой проверкой DNS/TLS. Если проверки не выполнялись больше двух суток, приложение само закрывает маршрут. Продление сертификатов запускается ежедневно отдельным таймером; фактический срок сертификата проверяется в приложении при каждом запросе.

```bash
sudo systemctl status myqr-domains.timer
sudo journalctl -u myqr-domains.service -n 80 --no-pager
sudo journalctl -u myqr-domains-renew.service -n 80 --no-pager
```

Сервис создаёт только `/etc/nginx/conf.d/myqr-domain-<UUID>.conf`, сертификаты `myqr-<UUID>` и webroot `/var/lib/myqr-acme`. Команды запускаются массивами аргументов, без shell. Перед reload выполняется `nginx -t`, при ошибке собственный файл восстанавливается. Совпадение с virtual host SPCh или любого другого сайта считается конфликтом и не перезаписывается. Настройки остальных сайтов и SPCh не меняются. Глобальная блокировка `/run/lock/myqr-domains.lock` не допускает одновременный запуск двух обработчиков myQR.

Документация: [Certbot webroot](https://eff-certbot.readthedocs.io/en/stable/using.html#webroot), [продление](https://eff-certbot.readthedocs.io/en/stable/using.html#renewing-certificates). На этой Windows-машине сервис не устанавливался, реальные DNS и сертификаты не менялись. Для приёмки на сервере нужен ваш тестовый домен: TXT + A → DNS → HTTPS → открытие → смена визитки → отключение/истечение Pro. Смена основного домена всей платформы через админку остаётся отдельной задачей; сейчас он задаётся конфигурацией.
