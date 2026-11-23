"""Working hours and bounded primary actions shared by editor and public cards."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from django.core.exceptions import ValidationError

DAYS = ('Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье')
ZONES = (
    ('Europe/Kaliningrad', 'Калининград'), ('Europe/Moscow', 'Москва'),
    ('Europe/Samara', 'Самара'), ('Asia/Yekaterinburg', 'Екатеринбург'),
    ('Asia/Omsk', 'Омск'), ('Asia/Krasnoyarsk', 'Красноярск'),
    ('Asia/Irkutsk', 'Иркутск'), ('Asia/Yakutsk', 'Якутск'),
    ('Asia/Vladivostok', 'Владивосток'), ('Asia/Magadan', 'Магадан'),
    ('Asia/Kamchatka', 'Камчатка'),
)


def action_href(action):
    if not action:
        return ''
    from .button_builder import phone_number, web_target
    target = action['target']
    if action['kind'] == 'phone':
        number = phone_number(target)
        if not number:
            raise ValidationError('Укажите номер для главной кнопки.')
        return 'tel:' + number
    return web_target(target)


def validate_features(content):
    business = content.get('business', {})
    seen = set()
    for hours in business.get('hours', []):
        if hours['day'] in seen or hours['open'] == hours['close']:
            raise ValidationError('Проверьте график: дни не должны повторяться, время открытия и закрытия должно различаться.')
        seen.add(hours['day'])
    if any(ord(c) < 32 for c in business.get('status', '')):
        raise ValidationError('Статус должен быть одной строкой.')
    action = content.get('primaryAction')
    if action:
        href = action_href(action)
        canonical = href[4:] if action['kind'] == 'phone' else href
        if canonical != action['target'] or any(ord(c) < 32 for c in action['label']):
            raise ValidationError('Проверьте название и адрес главной кнопки.')


def business_display(business, now=None):
    zone = business.get('timezone', 'Europe/Moscow')
    now = (now or datetime.now(ZoneInfo(zone))).astimezone(ZoneInfo(zone))
    hours = {item['day']: item for item in business.get('hours', [])}
    automatic = ''
    if hours:
        automatic = 'Сейчас закрыто'
        for offset in (-1, 0):
            day = now.date() + timedelta(days=offset)
            item = hours.get(day.weekday())
            if not item:
                continue
            start = datetime.combine(day, datetime.strptime(item['open'], '%H:%M').time(), tzinfo=ZoneInfo(zone))
            end = datetime.combine(day, datetime.strptime(item['close'], '%H:%M').time(), tzinfo=ZoneInfo(zone))
            if end <= start:
                end += timedelta(days=1)
            if start <= now < end:
                automatic = 'Открыто до ' + item['close']
                break
    return {'status': business.get('status') or automatic,
            'zone': dict(ZONES).get(zone, zone), 'hours': [
                {'name': name, 'time': (hours[day]['open'] + '–' + hours[day]['close'] +
                    (' (следующий день)' if hours[day]['close'] < hours[day]['open'] else '')) if day in hours else 'Выходной'}
                for day, name in enumerate(DAYS)] if hours else []}
