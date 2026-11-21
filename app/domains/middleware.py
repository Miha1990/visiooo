from django.conf import settings
from django.core.exceptions import DisallowedHost
from django.http import HttpResponse
from django.http.request import split_domain_port, validate_host
from .models import DomainBinding


class DomainRouting:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Read the original Host, never X-Forwarded-Host. No global wildcard ALLOWED_HOSTS.
        raw = request.META.get('HTTP_HOST')
        if not raw:
            raw = request.META.get('SERVER_NAME', '')
            port = request.META.get('SERVER_PORT', '')
            if port and port not in ('80', '443'):
                raw += ':' + port
        domain, port = split_domain_port(raw.lower())
        if not domain or '*' in settings.ALLOWED_HOSTS:
            raise DisallowedHost('Invalid Host configuration or header')
        if validate_host(domain, settings.ALLOWED_HOSTS):
            return self.get_response(request)
        binding = DomainBinding.objects.select_related('workspace', 'root_card').filter(hostname=domain).first()
        if not binding:
            raise DisallowedHost('Unknown Host')
        if not binding.routable:
            response = HttpResponse('Страница недоступна', status=404)
            response['Cache-Control'] = 'no-store'
            return response
        # Subsequent Django middleware may use get_host() for HTTPS redirects. This
        # per-request override is installed only after syntax + registry validation.
        request.get_host = lambda: raw
        request.domain_binding = binding
        request.domain_workspace = binding.workspace
        request.urlconf = 'domains.public_urls'
        return self.get_response(request)
