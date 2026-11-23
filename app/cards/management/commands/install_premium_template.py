from django.core.management.base import BaseCommand
from django.db import transaction
from django.conf import settings
from cards.designs import validate_design
from cards.models import CardTemplate, TemplatePhoto
from cards.premium import PREMIUM_ID, PHOTO_ASSETS, definition


class Command(BaseCommand):
    help = 'Добавить премиальный шаблон со всеми блоками, сохраняя последующие правки администратора.'

    @transaction.atomic
    def handle(self, *args, **options):
        design = validate_design(definition())
        for pk, filename in PHOTO_ASSETS.items():
            TemplatePhoto.objects.get_or_create(pk=pk, defaults={
                'name':'Премиальный образец · '+filename,
                'image':(settings.BASE_DIR/'static'/'examples'/filename).read_bytes()})
        item, created = CardTemplate.objects.get_or_create(pk=PREMIUM_ID, defaults={
            'name':'Тихая роскошь', 'description':'Молочная палитра, бронзовые акценты и выразительная типографика. Все блоки: карусель, видео, PDF, карта и контакты по кругу.',
            'category':'Премиальные', 'draft':design, 'published':design,
            'published_version':1,'status':'published','position':0})
        self.stdout.write('Премиальный шаблон добавлен в каталог.' if created else 'Премиальный шаблон уже есть; ваши изменения сохранены.')
