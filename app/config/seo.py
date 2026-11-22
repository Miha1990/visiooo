"""Public discovery and link previews, without enumerating customer cards."""
from xml.etree.ElementTree import Element, SubElement, tostring

from django.conf import settings
from django.http import HttpResponse
from django.templatetags.static import static
from django.views.decorators.http import require_safe


PUBLIC_PAGES = {
    '/': ('Визитка — ваши контакты в одном касании',
          'Создайте красивую электронную визитку с фото, контактами и соцсетями. Делитесь ссылкой, QR-кодом или NFC и сохраняйте контакт в телефон.'),
    '/pricing': ('Тарифы электронной визитки — Визитка',
                 'Все возможности электронной визитки за 199 ₽ в месяц или 1490 ₽ в год. Оформление с фото, QR-код, NFC и собственный домен.'),
    '/contacts': ('Контакты и реквизиты — Визитка',
                  'Поддержка сервиса Визитка: support@visiooo.ru. Контакты и реквизиты самозанятого Дворникова Михаила Валериевича.'),
    '/legal/offer': ('Публичная оферта — Визитка', 'Условия оплаты, предоставления доступа к сервису электронной визитки и возврата денежных средств.'),
    '/legal/privacy': ('Политика обработки персональных данных — Визитка', 'Цели, условия и порядок обработки персональных данных пользователей сервиса Визитка.'),
    '/legal/processing': ('Согласие на обработку персональных данных — Визитка', 'Условия согласия на обработку персональных данных в сервисе Визитка.'),
    '/legal/publication': ('Согласие на распространение персональных данных — Визитка', 'Условия публикации данных в электронной визитке и управления публичным доступом.'),
}


def metadata(request, *, title=None, description=None, image=None):
    page = PUBLIC_PAGES.get(request.path)
    custom_domain = hasattr(request, 'domain_binding')
    return {
        'title': title or (page[0] if page else 'Визитка — ваши контакты в одном касании'),
        'description': description or (page[1] if page else PUBLIC_PAGES['/'][1]),
        'url': (request.build_absolute_uri(request.path) if custom_domain
                else settings.PUBLIC_BASE_URL + request.path),
        'image': image or settings.PUBLIC_BASE_URL + static('brand/share-cover.png'),
        'image_alt': title or 'Визитка — все контакты в одном касании',
        'default_image': not image,
        'indexable': bool(page) and not custom_domain,
    }


def card_metadata(request, card):
    # Read only the published snapshot. Asset URLs retain the existing access checks.
    content = card.published_revision.content
    asset_id = content.get('avatarAssetId') or content.get('headerAssetId')
    image = request.build_absolute_uri(f'/c/{card.public_id}/assets/{asset_id}') if asset_id else None
    description = ' · '.join(str(content.get(key, '')).strip() for key in ('title', 'company') if content.get(key))
    return metadata(request, title=f'{content["name"]} — визитка',
                    description=description or 'Контакты и социальные сети. Сохраните визитку в телефон.', image=image)


@require_safe
def robots(request):
    lines = ['User-agent: *', 'Allow: /', 'Disallow: /admin/', 'Disallow: /accounts/',
             'Disallow: /app/', 'Disallow: /payments/', 'Disallow: /health/']
    if not hasattr(request, 'domain_binding'):
        lines += ['', f'Sitemap: {settings.PUBLIC_BASE_URL}/sitemap.xml']
    response = HttpResponse('\n'.join(lines) + '\n', content_type='text/plain; charset=utf-8')
    response['Cache-Control'] = 'public, max-age=3600'
    return response


@require_safe
def sitemap(request):
    root = Element('urlset', xmlns='http://www.sitemaps.org/schemas/sitemap/0.9')
    if not hasattr(request, 'domain_binding'):
        for path in PUBLIC_PAGES:
            SubElement(SubElement(root, 'url'), 'loc').text = settings.PUBLIC_BASE_URL + path
    response = HttpResponse(tostring(root, encoding='utf-8', xml_declaration=True),
                            content_type='application/xml; charset=utf-8')
    response['Cache-Control'] = 'public, max-age=3600'
    return response
