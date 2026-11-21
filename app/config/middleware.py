import hashlib
from ipaddress import ip_address
from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse
from django.utils.crypto import salted_hmac


class SensitiveRequestLimit:
    """Local single-process throttle. Use a shared cache before multiple workers."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == 'POST' and request.path.startswith('/accounts/'):
            remote = request.META.get('REMOTE_ADDR', '')
            if settings.TRUST_PROXY:
                # The loopback-only upstream accepts headers overwritten by our Nginx.
                try:
                    remote = str(ip_address(request.META.get('HTTP_X_REAL_IP', '')))
                except ValueError:
                    pass
            identity = salted_hmac('rate-limit', remote).hexdigest()
            key = 'auth-limit:' + hashlib.sha256((identity + request.path).encode()).hexdigest()
            cache.add(key, 0, 300)
            try:
                count = cache.incr(key)
            except ValueError:
                count = 1
            if count > 20:
                response = HttpResponse('Слишком много попыток. Повторите через 5 минут.', status=429)
                response['Retry-After'] = '300'
                return response
        return self.get_response(request)
