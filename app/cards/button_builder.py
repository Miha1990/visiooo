"""Customer-defined contact buttons; layout stays bounded to two tiles plus rows."""
import json
import re
from django.core.exceptions import ValidationError

BUTTON_TYPES = [
    {'kind':'phone','label':'Мобильный телефон','icon':'phone','group':'Реквизиты'},
    {'kind':'email','label':'Электронная почта','icon':'email','group':'Реквизиты'},
    {'kind':'other_phone','label':'Другой телефон','icon':'phone','group':'Реквизиты'},
    {'kind':'file','label':'Файл','icon':'file','group':'Дополнительный контент'},
    {'kind':'link','label':'Ссылка','icon':'link','group':'Дополнительный контент'},
    *[{'kind':kind,'label':label,'icon':kind,'group':'Соцсети и мессенджеры'} for kind,label in (
        ('vk','VK'),('instagram','Instagram'),('telegram','Telegram'),('dzen','Дзен'),('youtube','Канал YouTube'),
        ('ok','ОК'),('whatsapp','WhatsApp'),('viber','Viber'),('max','MAX'),('other_social','Другая соцсеть'),
        ('threads','Тредс'),('avito','Авито'),('website','Сайт'))],
]
TYPES = {item['kind']:item for item in BUTTON_TYPES}
TYPES['other_social']['icon'] = 'website'


def phone_number(value):
    value = re.sub(r'[\s()\-]', '', value.strip())
    if len(value) == 11 and value.isascii() and value.isdigit() and value[0] in ('7','8'):
        value = '+7' + value[1:]
    if value and not re.fullmatch(r'\+[1-9][0-9]{7,14}', value):
        raise ValidationError('Укажите номер с кодом страны, например +79289091817, или российский номер 89289091817.')
    return value


def clean_buttons(value):
    from .forms import WebLinkField
    from django.forms import EmailField
    if isinstance(value, str):
        try: value = json.loads(value)
        except (ValueError, TypeError, RecursionError): raise ValidationError('Не удалось прочитать кнопки. Обновите страницу и повторите сохранение.')
    if not isinstance(value, list) or len(value) > 30:
        raise ValidationError('Можно добавить до 30 кнопок.')
    result = []
    for item in value:
        if not isinstance(item, dict) or set(item) != {'kind','label','value'} or not isinstance(item.get('kind'),str) or item['kind'] not in TYPES:
            raise ValidationError('Недопустимый тип кнопки.')
        if not isinstance(item['label'], str) or not isinstance(item['value'], str):
            raise ValidationError('Укажите название и адрес кнопки.')
        kind = item['kind']; label = item['label'].strip() or TYPES[kind]['label']; target = item['value'].strip()
        if len(label) > 80 or len(target) > 2048: raise ValidationError('Название — до 80 символов, ссылка — до 2048.')
        if kind in ('phone','other_phone'):
            target = phone_number(target)
            if not target: raise ValidationError('Укажите номер телефона для кнопки.')
        elif kind == 'email': target = EmailField(max_length=254).clean(target)
        elif kind != 'file' or target: target = WebLinkField(max_length=2048).clean(target)
        result.append({'kind':kind,'label':label,'value':target})
    return result


def initial_buttons(content):
    if content.get('buttonLayout') == 'tiles': return content.get('buttons', [])
    result = []
    design = content.get('design', {})
    for kind in ('phone','email'):
        if content.get(kind): result.append({'kind':kind,'label':content.get(kind+'Label') or design.get(kind+'Label') or TYPES[kind]['label'],'value':content[kind]})
    result += [{'kind':'link','label':link['label'],'value':link['url']} for link in content.get('links', [])]
    result += [{'kind':kind,'label':TYPES[kind]['label'],'value':url} for kind,url in content.get('socials', {}).items() if kind in TYPES]
    if content.get('website'): result.append({'kind':'website','label':'Сайт','value':content['website']})
    if content.get('document', {}).get('assetId'): result.append({'kind':'file','label':content['document'].get('label') or 'Скачать файл','value':''})
    return result


def apply_buttons(content, buttons):
    content.update(buttonLayout='tiles', buttons=buttons, links=[])
    for key in ('phone','email','phoneLabel','emailLabel','website','socials'): content.pop(key, None)
    from .socials import SOCIAL_NETWORKS
    networks = {key for key,_,_ in SOCIAL_NETWORKS}
    for item in buttons:
        kind = item['kind']
        if kind in ('phone','other_phone','email'):
            field = 'phone' if kind in ('phone','other_phone') else 'email'
            if field not in content: content[field] = item['value']; content[field+'Label'] = item['label']
        elif kind == 'website': content.setdefault('website',item['value'])
        elif kind in networks: content.setdefault('socials',{}).setdefault(kind,item['value'])
    local_file = next((item for item in buttons if item['kind']=='file' and not item['value']), None)
    if local_file: content.setdefault('document', {})['label'] = local_file['label']
    else: content.pop('document', None)
    return content
