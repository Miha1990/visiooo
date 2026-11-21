"""Small HTTPS-only ЮKassa client. Never trust the browser or notification payload."""
import base64
import json
from urllib.error import URLError, HTTPError
from urllib.request import Request, build_opener, HTTPRedirectHandler
from django.conf import settings


class GatewayError(Exception):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def request(method, path, payload=None, key=None):
    credentials = f'{settings.YOOKASSA_SHOP_ID}:{settings.YOOKASSA_SECRET_KEY}'.encode()
    headers = {'Authorization': 'Basic ' + base64.b64encode(credentials).decode(),
               'Content-Type': 'application/json', 'Accept': 'application/json'}
    if key:
        headers['Idempotence-Key'] = str(key)
    data = json.dumps(payload).encode() if payload is not None else None
    req = Request('https://api.yookassa.ru/v3/' + path, data=data, headers=headers, method=method)
    try:
        with build_opener(NoRedirect()).open(req, timeout=12) as response:
            raw = response.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise ValueError
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise ValueError
        return result
    except (URLError, HTTPError, OSError, ValueError) as error:
        raise GatewayError('Платёжный сервис временно недоступен. Повторите проверку позже.') from error
