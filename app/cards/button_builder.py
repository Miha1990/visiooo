"""Customer-defined contact buttons; layout stays bounded to two tiles plus rows."""
import json
import re
from urllib.parse import urlsplit, parse_qs
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

SOCIAL_INPUTS = {
    'telegram': {'prefix':'https://t.me/', 'pattern':r'[A-Za-z0-9_]{1,32}', 'hosts':['t.me','telegram.me']},
    'instagram': {'prefix':'https://www.instagram.com/', 'pattern':r'[A-Za-z0-9_.]{1,30}', 'hosts':['instagram.com']},
    'vk': {'prefix':'https://vk.com/', 'pattern':r'[A-Za-z0-9_.-]{1,64}', 'hosts':['vk.com','vk.ru']},
    'threads': {'prefix':'https://www.threads.net/@', 'pattern':r'[A-Za-z0-9_.]{1,30}', 'hosts':['threads.net','threads.com']},
    'youtube': {'prefix':'https://www.youtube.com/@', 'pattern':r'[\w.-]{3,30}', 'hosts':['youtube.com','youtu.be']},
    'dzen': {'prefix':'https://dzen.ru/', 'pattern':r'[A-Za-z0-9_-]{1,100}', 'hosts':['dzen.ru','zen.yandex.ru']},
    'ok': {'prefix':'https://ok.ru/', 'pattern':r'[A-Za-z0-9_.-]{1,64}', 'hosts':['ok.ru']},
    'max': {'hosts':['max.ru']},
    'avito': {'hosts':['avito.ru']},
    'viber': {'hosts':['invite.viber.com','vb.me']},
}
for _kind, _rules in SOCIAL_INPUTS.items():
    TYPES[_kind]['input'] = _rules


def web_target(value):
    from .forms import WebLinkField
    if re.search(r'\s|[\x00-\x1f\x7f]',value):
        raise ValidationError('В ссылке не должно быть пробелов или управляющих символов.')
    value = WebLinkField(max_length=2048).clean(value)
    url = urlsplit(value)
    if url.username or url.password:
        raise ValidationError('Ссылка не должна содержать логин и пароль.')
    return value


def social_target(kind, value):
    if kind == 'whatsapp':
        number = value
        if re.match(r'^(?:https?://)?(?:wa\.me|(?:api|web)\.whatsapp\.com)/',value,re.I):
            url = urlsplit(web_target(value))
            number = url.path.strip('/') if url.hostname == 'wa.me' else parse_qs(url.query).get('phone',[''])[0]
            if number.isascii() and number.isdigit(): number = '+'+number
        number = phone_number(number)
        if not number: raise ValidationError('Укажите номер WhatsApp.')
        return 'https://wa.me/'+number.lstrip('+')
    rules = SOCIAL_INPUTS.get(kind)
    if rules and rules.get('prefix'):
        username = value.lstrip('@')
        if re.fullmatch(rules['pattern'],username) and username.strip('.'):
            return rules['prefix']+username
    value = web_target(value)
    if rules:
        url = urlsplit(value); host = (url.hostname or '').lower()
        if kind == 'telegram' and host.endswith('.t.me') and url.path in ('','/'):
            username = host[:-5]
            if re.fullmatch(rules['pattern'],username): return rules['prefix']+username
        if not any(host == allowed or host.endswith('.'+allowed) for allowed in rules['hosts']):
            raise ValidationError('Укажите ссылку именно на '+TYPES[kind]['label']+'.')
        if url.path in ('','/'):
            raise ValidationError('Укажите ссылку на профиль, канал или сообщество, а не главную страницу соцсети.')
        if any(part in ('.','..') for part in url.path.split('/')):
            raise ValidationError('Проверьте адрес профиля соцсети.')
    return value


def phone_number(value):
    value = re.sub(r'[\s()\-]', '', value.strip())
    if len(value) == 11 and value.isascii() and value.isdigit() and value[0] in ('7','8'):
        value = '+7' + value[1:]
    if value and (not re.fullmatch(r'\+[1-9][0-9]{7,14}', value) or value.startswith('+7') and len(value) != 12):
        raise ValidationError('Укажите номер с кодом страны, например +79289091817, или российский номер 89289091817.')
    return value


def clean_buttons(value):
    from django.forms import EmailField
    if isinstance(value, str):
        try: value = json.loads(value)
        except (ValueError, TypeError, RecursionError): raise ValidationError('Не удалось прочитать кнопки. Обновите страницу и повторите сохранение.')
    if not isinstance(value, list) or len(value) > 30:
        raise ValidationError('Можно добавить до 30 кнопок.')
    result = []
    for item in value:
        if not isinstance(item, dict) or not {'kind','label','value'} <= set(item) or set(item)-{'kind','label','value','extension'} or not isinstance(item.get('kind'),str) or item['kind'] not in TYPES:
            raise ValidationError('Недопустимый тип кнопки.')
        if not isinstance(item['label'], str) or not isinstance(item['value'], str):
            raise ValidationError('Укажите название и адрес кнопки.')
        kind = item['kind']; label = item['label'].strip() or TYPES[kind]['label']; target = item['value'].strip()
        if re.search(r'[\x00-\x1f\x7f]',label): raise ValidationError('Название не должно содержать управляющие символы.')
        extension = item.get('extension','')
        if not isinstance(extension,str) or (extension and (kind not in ('phone','other_phone') or not re.fullmatch(r'[0-9]{1,8}',extension))):
            raise ValidationError('Добавочный номер — от 1 до 8 цифр, только для телефонного блока.')
        if len(label) > 80 or len(target) > 2048: raise ValidationError('Название — до 80 символов, ссылка — до 2048.')
        if kind in ('phone','other_phone'):
            target = phone_number(target)
            if not target: raise ValidationError('Укажите номер телефона для кнопки.')
        elif kind == 'email': target = EmailField(max_length=254).clean(target)
        elif kind != 'file' or target: target = social_target(kind,target)
        cleaned = {'kind':kind,'label':label,'value':target}
        if extension: cleaned['extension'] = extension
        result.append(cleaned)
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
