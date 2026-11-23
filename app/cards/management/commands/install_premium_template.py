from django.core.management.base import BaseCommand
from django.db import transaction
from django.conf import settings
import json
from copy import deepcopy
from cards.designs import validate_design
from cards.models import CardTemplate, TemplatePhoto
from cards.premium import PREMIUM_ID, PHOTO_ASSETS, definition


class Command(BaseCommand):
    help = 'Добавить шаблоны из примеров сайта и премиальный шаблон, сохраняя правки администратора.'

    @transaction.atomic
    def handle(self, *args, **options):
        from cards.builtin_templates import EXAMPLE_TEMPLATES, definition as example_definition
        for position, (slug, (pk, name, description)) in enumerate(EXAMPLE_TEMPLATES.items(), 1):
            layout = example_definition(slug)
            CardTemplate.objects.get_or_create(pk=pk, defaults={
                'name': name, 'description': description, 'category': 'Примеры с сайта',
                'draft': layout, 'published': deepcopy(layout), 'published_version': 1,
                'status': 'published', 'position': position})
        design = validate_design(definition())
        for pk, filename in PHOTO_ASSETS.items():
            TemplatePhoto.objects.get_or_create(pk=pk, defaults={
                'name':'Премиальный образец · '+filename,
                'image':(settings.BASE_DIR/'static'/'examples'/filename).read_bytes()})
        item, created = CardTemplate.objects.get_or_create(pk=PREMIUM_ID, defaults={
            'name':'Тихая роскошь', 'description':'Молочная палитра, бронзовые акценты и выразительная типографика. Все блоки: карусель, видео, PDF, карта и контакты по кругу.',
            'category':'Премиальные', 'draft':design, 'published':design,
            'published_version':1,'status':'published','position':0})
        if not created:
            originals = [json.loads((settings.BASE_DIR/'cards'/'presets'/filename).read_text(encoding='utf-8'))
                         for filename in ('premium-v1.json', 'premium-v2.json')]
            item = CardTemplate.objects.select_for_update().get(pk=item.pk)
            if item.status == 'published' and item.draft == item.published and item.draft in originals:
                item.draft=deepcopy(design);item.published=deepcopy(design)
                item.version+=1;item.published_version+=1;item.save()
                self.stdout.write('Мобильное оформление премиального шаблона обновлено. Визитки клиентов сохраняют выбранную версию.')
                return
        self.stdout.write('Премиальный шаблон добавлен в каталог.' if created else 'Премиальный шаблон уже есть; ваши изменения сохранены.')
