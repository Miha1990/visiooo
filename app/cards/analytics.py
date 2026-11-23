"""First-party daily counters. No visitor identifiers or raw request data are stored."""
from datetime import timedelta
import logging
from zoneinfo import ZoneInfo
from django.db import DatabaseError, transaction
from django.db.models import F, Sum
from django.utils import timezone
from .models import CardDailyViews

MOSCOW = ZoneInfo('Europe/Moscow')
logger = logging.getLogger(__name__)
BOT_MARKERS = ('bot', 'crawler', 'spider', 'preview', 'facebookexternalhit', 'vkshare', 'whatsapp')
MONTHS = ('Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
          'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь')


def record_view(request, card):
    if request.method != 'GET' or (request.user.is_authenticated and request.user.pk == card.workspace.owner_id):
        return
    agent = request.META.get('HTTP_USER_AGENT', '').lower()
    purpose = (request.META.get('HTTP_SEC_PURPOSE', '') + request.META.get('HTTP_PURPOSE', '')).lower()
    if any(marker in agent for marker in BOT_MARKERS) or 'prefetch' in purpose:
        return
    try:
        with transaction.atomic():
            row, created = CardDailyViews.objects.get_or_create(
                card=card, day=timezone.localdate(timezone=MOSCOW), defaults={'views': 1})
            if not created:
                CardDailyViews.objects.filter(pk=row.pk).update(views=F('views') + 1)
    except DatabaseError:
        # Statistics must not make an otherwise available public card fail.
        logger.warning('Не удалось обновить счётчик просмотров визитки.')


def month_shift(day, offset):
    number = day.year * 12 + day.month - 1 + offset
    return day.replace(year=number // 12, month=number % 12 + 1, day=1)


def report(cards, period='day', today=None):
    today = today or timezone.localdate(timezone=MOSCOW)
    period = period if period in ('day', 'week', 'month') else 'day'
    if period == 'month':
        start = month_shift(today, -11)
        keys = [month_shift(start, index) for index in range(12)]
        bucket = lambda day: day.replace(day=1)
    elif period == 'week':
        monday = today - timedelta(days=today.weekday())
        start = monday - timedelta(weeks=11)
        keys = [start + timedelta(weeks=index) for index in range(12)]
        bucket = lambda day: day - timedelta(days=day.weekday())
    else:
        start = today - timedelta(days=29)
        keys = [start + timedelta(days=index) for index in range(30)]
        bucket = lambda day: day
    counters = dict.fromkeys(keys, 0)
    daily = CardDailyViews.objects.filter(card__in=cards, day__gte=start, day__lte=today).values('day').annotate(total=Sum('views'))
    for item in daily:
        counters[bucket(item['day'])] += item['total']
    maximum = max(counters.values(), default=0)
    rows = []
    for day, count in counters.items():
        if period == 'month':
            label = f'{MONTHS[day.month - 1]} {day.year}'
        elif period == 'week':
            end = min(day + timedelta(days=6), today)
            label = f'{day:%d.%m.%Y} — {end:%d.%m.%Y}'
        else:
            label = f'{day:%d.%m.%Y}'
        rows.append({'label': label, 'views': count, 'percent': max(2, round(count * 100 / maximum)) if count else 0})
    return {'period': period, 'rows': rows, 'total_views': sum(counters.values()), 'start': start, 'end': today,
            'period_title': {'day': 'Последние 30 дней', 'week': 'Последние 12 недель', 'month': 'Последние 12 месяцев'}[period]}
