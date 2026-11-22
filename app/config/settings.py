import os
from pathlib import Path
from urllib.parse import urlsplit, unquote

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')
DEBUG = os.getenv('DEBUG', 'true').lower() == 'true'
SECRET_KEY = os.getenv('SECRET_KEY', '')
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured('SECRET_KEY is required outside development')
    # Ephemeral local key; configure .env for persistent sessions.
    import secrets
    SECRET_KEY = secrets.token_urlsafe(64)
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1,[::1]').split(',')
PUBLIC_BASE_URL = os.getenv('PUBLIC_BASE_URL', 'http://127.0.0.1:8000').rstrip('/')
INSTALLED_APPS = [
    'django.contrib.admin', 'django.contrib.auth', 'django.contrib.contenttypes',
    'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles',
    'accounts', 'workspaces', 'cards', 'billing', 'domains',
]
MIDDLEWARE = [
    'domains.middleware.DomainRouting',
    'config.middleware.SensitiveRequestLimit',
    'django.middleware.security.SecurityMiddleware', 'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware', 'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware', 'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
ROOT_URLCONF = 'config.urls'
if os.getenv('SERVE_STATIC', 'false').lower() == 'true':
    MIDDLEWARE.insert(MIDDLEWARE.index('django.middleware.security.SecurityMiddleware') + 1,
                      'whitenoise.middleware.WhiteNoiseMiddleware')
    STORAGES = {
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
    }
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates',
              'DIRS': [BASE_DIR / 'templates'], 'APP_DIRS': True,
              'OPTIONS': {'context_processors': [
                  'django.template.context_processors.request', 'django.contrib.auth.context_processors.auth',
                  'django.contrib.messages.context_processors.messages']}}]
TEMPLATES[0]['OPTIONS']['context_processors'].append('config.public_context.public_context')
WSGI_APPLICATION = 'config.wsgi.application'
database_url = os.getenv('DATABASE_URL', '')
if database_url:
    db = urlsplit(database_url)
    if db.scheme not in ('postgres', 'postgresql'):
        raise ImproperlyConfigured('DATABASE_URL must use PostgreSQL')
    DATABASES = {'default': {'ENGINE': 'django.db.backends.postgresql', 'NAME': unquote(db.path.lstrip('/')),
        'USER': unquote(db.username or ''), 'PASSWORD': unquote(db.password or ''),
        'HOST': db.hostname, 'PORT': db.port or 5432, 'CONN_MAX_AGE': 60}}
elif DEBUG or os.getenv('ALLOW_SQLITE_TESTS') == '1':
    DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / 'db.sqlite3',
                             'OPTIONS': {'timeout': 20}}}
else:
    raise ImproperlyConfigured('DATABASE_URL is required outside development')
AUTH_USER_MODEL = 'accounts.User'
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
LANGUAGE_CODE = 'ru-ru'
TIME_ZONE = 'Europe/Moscow'
USE_I18N = True
USE_TZ = True
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LOGIN_URL = '/accounts/login'
LOGIN_REDIRECT_URL = '/app/cards'
LOGOUT_REDIRECT_URL = '/'
EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'no-reply@localhost')
EMAIL_HOST = os.getenv('EMAIL_HOST', '')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'true').lower() == 'true'
EMAIL_USE_SSL = os.getenv('EMAIL_USE_SSL', 'false').lower() == 'true'
EMAIL_TIMEOUT = 15
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = not DEBUG
SECURE_HSTS_SECONDS = 0 if DEBUG else 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
X_FRAME_OPTIONS = 'DENY'
DATA_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024
PRIVATE_MEDIA_ROOT = BASE_DIR / 'private-media'
PASSWORD_RESET_TIMEOUT = 3600
CUSTOM_DOMAINS_ENABLED = os.getenv('CUSTOM_DOMAINS_ENABLED', 'false').lower() == 'true'
DOMAIN_IPV4 = os.getenv('DOMAIN_IPV4', '')
DOMAIN_ACME_EMAIL = os.getenv('DOMAIN_ACME_EMAIL', '')
DOMAIN_UPSTREAM_PORT = int(os.getenv('DOMAIN_UPSTREAM_PORT', '8000'))
OPERATOR_NAME = 'Дворников Михаил Валериевич'
OPERATOR_PHONE = '+7 928 909-18-17'
OPERATOR_EMAIL = 'support@visiooo.ru'
OPERATOR_INN = os.getenv('OPERATOR_INN', '615308640848')
OPERATOR_ADDRESS = (os.getenv('OPERATOR_ADDRESS', '').strip()
                    or 'г. Ростов-на-Дону, ул. Зорге, д. 27, кв. 30')
DATA_HOSTING_PROVIDER = (os.getenv('DATA_HOSTING_PROVIDER', '').strip() or (
    'Общество с ограниченной ответственностью «АЙТИ БАЗИС» (ООО «АЙТИБ»), '
    'ИНН/КПП 9719026854/771901001, ОГРН 1227700345905; '
    'юридический и почтовый адрес: 107023, г. Москва, вн.тер.г. муниципальный округ '
    'Соколиная гора, пер. Барабанный, д. 4, стр. 3, этаж/офис 3/10. '
    'Страна местонахождения основной базы данных — Российская Федерация'
))
DATA_MAIL_PROVIDER = os.getenv('DATA_MAIL_PROVIDER', '')
LEGAL_LAUNCH_CONFIRMED = os.getenv('LEGAL_LAUNCH_CONFIRMED', 'false').lower() == 'true'
LEGAL_VERSION = '2026-11-22.5'
ANALYTICS_CONSENT_VERSION = '2026-11-22.1'
YANDEX_METRIKA_ID = os.getenv('YANDEX_METRIKA_ID', '').strip()
if YANDEX_METRIKA_ID and (len(YANDEX_METRIKA_ID) > 15 or not YANDEX_METRIKA_ID.isascii() or not YANDEX_METRIKA_ID.isdigit()
                         or not 0 < int(YANDEX_METRIKA_ID) < 10 ** 15):
    raise ImproperlyConfigured('YANDEX_METRIKA_ID must be a positive counter number or empty')
YOOKASSA_ENABLED = os.getenv('YOOKASSA_ENABLED', 'false').lower() == 'true'
YOOKASSA_SHOP_ID = os.getenv('YOOKASSA_SHOP_ID', '')
YOOKASSA_SECRET_KEY = os.getenv('YOOKASSA_SECRET_KEY', '')
YOOKASSA_TEST_MODE = os.getenv('YOOKASSA_TEST_MODE', 'true').lower() == 'true'
NPD_RECEIPTS_CONFIRMED = os.getenv('NPD_RECEIPTS_CONFIRMED', 'false').lower() == 'true'
TRUST_PROXY = os.getenv('TRUST_PROXY', 'false').lower() == 'true'
if TRUST_PROXY:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
