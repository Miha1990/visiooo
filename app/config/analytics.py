"""Optional analytics: explicit consent, signed browser receipt, server-side evidence."""
import hashlib
import json
from uuid import UUID

from django.conf import settings
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.template.loader import render_to_string
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from accounts.models import AnalyticsConsent

COOKIE = 'visiooo_analytics'
SALT = 'analytics-consent-v1'
MAX_AGE = 180 * 24 * 60 * 60
MARKETING_PATHS = {'/', '/pricing', '/contacts'}


def configuration(request):
    configured = bool(settings.YANDEX_METRIKA_ID) and not hasattr(request, 'domain_binding')
    return {'configured': configured, 'eligible': configured and request.path in MARKETING_PATHS,
            'counter_id': settings.YANDEX_METRIKA_ID if configured else '',
            'page_url': settings.PUBLIC_BASE_URL + request.path,
            'version': settings.ANALYTICS_CONSENT_VERSION}


def document(request):
    text = render_to_string('legal/texts/analytics.html', request=request)
    return text, hashlib.sha256(text.encode()).hexdigest()


def receipt(request, digest):
    try:
        value = json.loads(request.get_signed_cookie(COOKIE, default='', salt=SALT, max_age=MAX_AGE))
        UUID(value['id'])
        if (value['choice'] in ('granted', 'denied', 'withdrawn')
                and value['version'] == settings.ANALYTICS_CONSENT_VERSION
                and value['counter_id'] == settings.YANDEX_METRIKA_ID and value['digest'] == digest):
            return value
    except (ValueError, KeyError, TypeError):
        pass
    return None


@never_cache
@csrf_protect
@require_http_methods(['GET', 'POST'])
def consent(request):
    if not configuration(request)['configured']:
        return JsonResponse({'enabled': False, 'choice': None})
    text, digest = document(request)
    previous = receipt(request, digest)
    if request.method == 'GET':
        return JsonResponse({'enabled': True, 'choice': previous['choice'] if previous else None,
                             'csrf_token': get_token(request)})
    choice = request.POST.get('choice')
    if choice not in ('granted', 'denied'):
        return JsonResponse({'error': 'Выберите, разрешить аналитику или отказаться.'}, status=400)
    if request.POST.get('version') != settings.ANALYTICS_CONSENT_VERSION:
        return JsonResponse({'error': 'Текст согласия обновился. Перезагрузите страницу.'}, status=409)
    if choice == 'denied' and previous and previous['choice'] == 'granted':
        choice = 'withdrawn'
    event = AnalyticsConsent.objects.create(choice=choice, counter_id=settings.YANDEX_METRIKA_ID,
        version=settings.ANALYTICS_CONSENT_VERSION, document_sha256=digest, document_text=text,
        previous_receipt=previous['id'] if previous else None)
    value = {'id': str(event.pk), 'choice': choice, 'version': settings.ANALYTICS_CONSENT_VERSION,
             'counter_id': settings.YANDEX_METRIKA_ID, 'digest': digest}
    response = JsonResponse({'enabled': True, 'choice': choice})
    response.set_signed_cookie(COOKIE, json.dumps(value), salt=SALT, max_age=MAX_AGE,
                               secure=settings.SESSION_COOKIE_SECURE, httponly=True, samesite='Lax')
    return response
