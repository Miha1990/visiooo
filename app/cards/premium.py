"""Editable premium preset. Demonstration data is never copied to a customer's card."""
from copy import deepcopy
from pathlib import Path
import json
from django.conf import settings
from django.templatetags.static import static
from django.urls import reverse

PREMIUM_ID = '75d4fb3d-5668-4a4f-92c2-a8070a95eb01'
PRESET_PATH = Path(__file__).with_name('presets') / 'premium-v1.json'
PHOTO_ASSETS = {
    '75d4fb3d-5668-4a4f-92c2-a8070a95eb11':'property-cover.webp',
    '75d4fb3d-5668-4a4f-92c2-a8070a95eb12':'designer-cover.webp',
    '75d4fb3d-5668-4a4f-92c2-a8070a95eb13':'photographer-cover.webp',
}


def definition():
    return deepcopy(json.loads(PRESET_PATH.read_text(encoding='utf-8')))


def demo(design=None):
    design = deepcopy(design) if design is not None else definition()
    about = settings.PUBLIC_BASE_URL + '/examples/premium#example-about'
    return {
        'content': {'schemaVersion':1,'name':'Елена Морозова','title':'Дизайнер частных интерьеров',
            'company':'Тихая роскошь. Продуманные детали.',
            'bio':'Создаю пространства, в которых хочется оставаться.\nСопровождаю проект от первой идеи до последней детали.',
            'template':'classic','accent':design['accent'],'design':design,
            'avatarAssetId':'example','headerAssetId':'example','backgroundAssetId':'example',
            'phone':'+79990000000','email':'studio@example.test','website':about,
            'links':[{'label':'Обсудить мой проект','url':about},{'label':'Коллекция проектов','url':about}],
            'socials':{key:about for key in ('telegram','vk','instagram','threads','ok','max','avito')},
            'video':{'url':'https://www.youtube.com/watch?v=aqz-KE-bpKQ','title':'Пример видеоплеера · открытый фильм Blender'},
            'document':{'label':'Коллекция услуг · пример PDF'},
            'map':{'address':'Пример точки на карте · Ростов-на-Дону','latitude':47.2253,'longitude':39.7447}},
        'example_assets':{'avatar':'examples/property-portrait.webp','header':'examples/property-cover.webp','background':'examples/designer-cover.webp'},
        'example_gallery':[{'id':pk,'url':static('examples/'+PHOTO_ASSETS[pk]) if pk in PHOTO_ASSETS else reverse('template_photo',args=[pk])}
                           for pk in design.get('carousel',{}).get('photos',[])],
        'example_pdf_url':static('examples/premium-example.pdf'),
        'example_qr_url':'/examples/premium/qr.png','example_vcard_url':'/examples/premium/contact.vcf',
    }
