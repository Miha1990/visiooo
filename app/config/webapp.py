from django.http import JsonResponse, HttpResponseRedirect
from django.templatetags.static import static
from django.views.decorators.http import require_safe


@require_safe
def manifest(request):
    icons = []
    for purpose, prefix in (('any', 'android-icon'), ('maskable', 'android-maskable')):
        for size in (192, 512):
            icons.append({'src': static(f'brand/{prefix}-{size}.png'), 'sizes': f'{size}x{size}',
                          'type': 'image/png', 'purpose': purpose})
    response = JsonResponse({'id': '/', 'name': 'Визитка — все контакты рядом', 'short_name': 'Визитка',
        'description': 'Ваши фотографии, контакты и социальные сети на одной красивой странице.',
        'lang': 'ru', 'dir': 'ltr', 'start_url': '/app/cards', 'scope': '/', 'display': 'standalone',
        'background_color': '#f7f8f5', 'theme_color': '#2457db', 'icons': icons,
        'categories': ['business', 'productivity'], 'prefer_related_applications': False},
        json_dumps_params={'ensure_ascii': False}, content_type='application/manifest+json')
    response['Cache-Control'] = 'public, max-age=3600'
    return response


@require_safe
def favicon(request):
    response = HttpResponseRedirect(static('brand/favicon.ico'))
    response['Cache-Control'] = 'public, max-age=86400'
    return response


@require_safe
def apple_touch_icon(request):
    response = HttpResponseRedirect(static('brand/apple-touch-icon-180.png'))
    response['Cache-Control'] = 'public, max-age=86400'
    return response
