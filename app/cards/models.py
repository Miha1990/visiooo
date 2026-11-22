import secrets
import uuid
from django.db import models
from workspaces.models import Workspace


def public_id():
    return secrets.token_urlsafe(24)


def empty_content():
    return {'schemaVersion': 1, 'name': 'Новая визитка', 'template': 'classic', 'accent': '#2457DB', 'links': []}


class Card(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, verbose_name='Идентификатор')
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, verbose_name='Личный кабинет')
    public_id = models.CharField(max_length=40, unique=True, default=public_id, editable=False, verbose_name='Публичный идентификатор')
    draft = models.JSONField(default=empty_content, verbose_name='Черновик')
    draft_version = models.PositiveIntegerField(default=1, verbose_name='Версия черновика')
    published_revision = models.ForeignKey('CardRevision', on_delete=models.SET_NULL, null=True,
                                           blank=True, related_name='+', verbose_name='Опубликованная версия')
    status = models.CharField(max_length=12, choices=[('draft', 'Черновик'), ('published', 'Опубликовано'),
                                                    ('deleted', 'Удалено')], default='draft', verbose_name='Статус')
    blocked = models.BooleanField(default=False, verbose_name='Заблокирована')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата изменения')

    class Meta:
        verbose_name = 'визитка'
        verbose_name_plural = 'Визитки'
        indexes = [models.Index(fields=['workspace', '-updated_at'])]

    @property
    def has_changes(self):
        return self.published_revision_id and self.draft != self.published_revision.content

    def __str__(self):
        return self.draft.get('name', 'Визитка')


class CardRevision(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, verbose_name='Идентификатор')
    card = models.ForeignKey(Card, on_delete=models.CASCADE, related_name='revisions', verbose_name='Визитка')
    schema_version = models.PositiveSmallIntegerField(default=1, verbose_name='Версия формата')
    content = models.JSONField(verbose_name='Содержимое')
    publication_conditions = models.TextField(blank=True, verbose_name='Условия публикации')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError('Опубликованные версии нельзя изменять.')
        return super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'версия визитки'
        verbose_name_plural = 'Версии визиток'

    def __str__(self):
        return f'Версия визитки {self.pk}'


class Asset(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, verbose_name='Идентификатор')
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, verbose_name='Личный кабинет')
    object_key = models.CharField(max_length=240, unique=True, editable=False, verbose_name='Путь в хранилище')
    bytes = models.PositiveIntegerField(verbose_name='Размер в байтах')
    width = models.PositiveIntegerField(verbose_name='Ширина')
    height = models.PositiveIntegerField(verbose_name='Высота')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата загрузки')

    class Meta:
        verbose_name = 'изображение'
        verbose_name_plural = 'Изображения'


class PhysicalCard(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, verbose_name='Идентификатор')
    public_id = models.CharField(max_length=40, unique=True, default=public_id, editable=False, verbose_name='Публичный идентификатор')
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, verbose_name='Личный кабинет')
    card = models.ForeignKey(Card, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Электронная визитка')
    label = models.CharField(max_length=100, verbose_name='Название')
    enabled = models.BooleanField(default=True, verbose_name='Включена')
    blocked = models.BooleanField(default=False, verbose_name='Заблокирована')
    version = models.PositiveIntegerField(default=1, verbose_name='Версия')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата изменения')

    def __str__(self):
        return self.label

    class Meta:
        verbose_name = 'физическая визитка'
        verbose_name_plural = 'Физические визитки'


class PhysicalCardEvent(models.Model):
    physical_card = models.ForeignKey(PhysicalCard, on_delete=models.CASCADE, related_name='events', verbose_name='Физическая визитка')
    actor = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, verbose_name='Пользователь')
    action = models.CharField(max_length=20, verbose_name='Действие', choices=[
        ('created', 'Создана'), ('bound', 'Привязана'), ('disabled', 'Отключена')])
    target_card = models.ForeignKey(Card, on_delete=models.SET_NULL, null=True, verbose_name='Электронная визитка')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата события')

    class Meta:
        verbose_name = 'событие физической визитки'
        verbose_name_plural = 'События физических визиток'

    def __str__(self):
        return f'{self.get_action_display()} — {self.physical_card}'
