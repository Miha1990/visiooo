"""Fixed, fictional public examples. Never read customer cards or subscriptions."""
from copy import deepcopy

from django.conf import settings
from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from .vcard import render_vcard


EXAMPLES = [
    {'slug': 'designer', 'label': 'Для творческих профессий', 'style': 'Классика · оливковый',
     'content': {'name': 'Александра Ким', 'title': 'Бренд-дизайнер', 'company': 'Студия Форма',
                 'bio': 'Создаю айдентику с характером.\nПомогаю хорошим идеям стать заметными брендами.',
                 'template': 'classic', 'accent': '#526c50', 'email': 'hello@forma.example',
                 'links': [{'label': 'Портфолио и проекты', 'url': '#example-about'}],
                 'socials': {}, 'website': ''}},
    {'slug': 'photographer', 'label': 'Для личного бренда', 'style': 'Профиль · морской',
     'content': {'name': 'Марк Волков', 'title': 'Фотограф', 'company': 'Портреты · путешествия · истории',
                 'bio': 'Сохраняю свет, настроение и настоящие эмоции.\nОткрыт к съёмкам и новым маршрутам.',
                 'template': 'profile', 'accent': '#286b76', 'email': 'shoot@mark.example',
                 'links': [{'label': 'Посмотреть серии', 'url': '#example-about'}],
                 'socials': {}, 'website': ''}},
    {'slug': 'property', 'label': 'Для бизнеса и услуг', 'style': 'Минимализм · тёплый графит',
     'content': {'name': 'Елена Морозова', 'title': 'Консультант по недвижимости', 'company': 'Дома, в которых хочется жить',
                 'bio': 'Помогаю найти место для новой главы.\nОт первого просмотра до ключей от вашего дома.',
                 'template': 'minimal', 'accent': '#695b4b', 'email': 'home@elena.example',
                 'links': [{'label': 'Подбор недвижимости', 'url': '#example-about'}],
                 'socials': {}, 'website': ''}},
]


def example_cards():
    items = deepcopy(EXAMPLES)
    for item in items:
        slug = item['slug']
        item['assets'] = {'avatar': f'examples/{slug}-portrait.webp',
                          'header': f'examples/{slug}-cover.webp'}
        # Separate background and header photos demonstrate the independent slots.
        if slug == 'photographer':
            item['assets']['background'] = 'examples/designer-cover.webp'
        for slot in item['assets']:
            item['content'][{'avatar': 'avatarAssetId', 'header': 'headerAssetId',
                              'background': 'backgroundAssetId'}[slot]] = 'example'
        item['qr_url'] = f'/examples/{slug}/qr.png'
        item['vcard_url'] = f'/examples/{slug}/contact.vcf'
        about = f'{settings.PUBLIC_BASE_URL}/examples/{slug}#example-about'
        for link in item['content']['links']:
            link['url'] = about
        networks = ['telegram', 'instagram'] if slug != 'property' else ['telegram', 'avito', 'vk']
        item['content']['socials'] = {network: about for network in networks}
        item['content']['website'] = about
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
    response['Content-Disposition'] = 'attachment; filename="example-contact.vcf"'
    return response
