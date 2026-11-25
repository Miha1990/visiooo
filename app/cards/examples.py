"""Fixed, fictional public examples. Never read customer cards or subscriptions."""
from copy import deepcopy

from django.conf import settings
from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from .vcard import render_vcard


EXAMPLES = [
    {'slug': 'designer', 'label': 'Для творческих профессий', 'style': 'Форма · светлый редакционный',
     'content': {'name': 'Александра Ким', 'title': 'Бренд-дизайнер', 'company': 'Студия Форма',
                 'bio': 'Айдентика и сайты для брендов с характером.', 'emailLabel':'Обсудить проект',
                 'template': 'classic', 'accent': '#526c50', 'email': 'hello@forma.example',
                 'links': [{'label': 'Портфолио', 'url': '#example-about'}],
                 'socials': {}, 'website': ''}},
    {'slug': 'photographer', 'label': 'Для личного бренда', 'style': 'Кадр · тёмный атмосферный',
     'content': {'name': 'Марк Волков', 'title': 'Портретный фотограф', 'company': '',
                 'bio': 'Живые портреты. Настоящие вы.', 'emailLabel':'Записаться',
                 'template': 'profile', 'accent': '#286b76', 'email': 'shoot@mark.example',
                 'links': [{'label': 'Смотреть съёмки', 'url': '#example-about'}],
                 'socials': {}, 'website': ''}},
    {'slug': 'property', 'label': 'Для бизнеса и услуг', 'style': 'Адрес · деловой минимализм',
     'content': {'name': 'Елена Морозова', 'title': 'Эксперт по недвижимости', 'company': 'Москва и область',
                 'bio': 'Найду ваш дом. Проведу сделку от просмотра до ключей.', 'emailLabel':'Обсудить покупку',
                 'template': 'minimal', 'accent': '#695b4b', 'email': 'home@elena.example',
                 'links': [{'label': 'Посмотреть объекты', 'url': '#example-about'}],
                 'socials': {}, 'website': ''}},
]


def example_cards():
    from .builtin_templates import definition
    items = deepcopy(EXAMPLES)
    for item in items:
        slug = item['slug']
        item['content']['design'] = definition(slug)
        item['content']['accent'] = item['content']['design']['accent']
        item['assets'] = {'avatar': f'examples/{slug}-portrait.webp',
                          'header': f'examples/{slug}-cover.webp'}
        for slot in item['assets']:
            item['content'][{'avatar': 'avatarAssetId', 'header': 'headerAssetId',
                              'background': 'backgroundAssetId'}[slot]] = 'example'
        item['qr_url'] = f'/examples/{slug}/qr.png'
        item['vcard_url'] = f'/examples/{slug}/contact.vcf'
        about = f'{settings.PUBLIC_BASE_URL}/examples/{slug}#example-about'
        for link in item['content']['links']:
            link['url'] = about
        networks = ['telegram', 'instagram'] if slug == 'designer' else ['telegram', 'vk'] if slug == 'photographer' else ['telegram', 'avito']
        item['content']['socials'] = {network: about for network in networks}
    return items


def get_example(slug):
    if slug == 'premium':
        from .premium import demo
        value = demo()
        return {'slug':'premium','label':'Все возможности в одном шаблоне','style':'Премиальный · молочный и бронза',
                'content':value['content'],'assets':value['example_assets'],
                'qr_url':value['example_qr_url'],'vcard_url':value['example_vcard_url'],
                'gallery':value['example_gallery'],'pdf_url':value['example_pdf_url']}
    for item in example_cards():
        if item['slug'] == slug:
            return item
    raise Http404


@require_GET
def detail(request, slug):
    from config.seo import metadata
    from django.templatetags.static import static
    example = get_example(slug)
    seo = metadata(request, title=f'{example["content"]["name"]} — пример визитки',
                   description=example['content']['title'] + '. Демонстрационный пример оформления электронной визитки.',
                   image=settings.PUBLIC_BASE_URL + static(example['assets']['header']))
    return render(request, 'cards/example.html', {'example': example, 'seo': seo,
        'example_gallery':example.get('gallery',[]),'example_pdf_url':example.get('pdf_url','')})


@require_GET
def qr(request, slug):
    from .views import qr_response
    get_example(slug)
    return qr_response(f'{settings.PUBLIC_BASE_URL}/examples/{slug}', 'example-qr.png')


@require_GET
def vcard(request, slug):
    example = get_example(slug)
    response = HttpResponse(render_vcard(example['content'], f'{settings.PUBLIC_BASE_URL}/examples/{slug}'),
                            content_type='text/vcard; charset=utf-8')
    disposition = 'attachment' if request.GET.get('download') == '1' else 'inline'
    response['Content-Disposition'] = f'{disposition}; filename="example-contact.vcf"'
    return response
