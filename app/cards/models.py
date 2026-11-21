import secrets
import uuid
from django.db import models
from workspaces.models import Workspace


def public_id():
    return secrets.token_urlsafe(24)


def empty_content():
    return {'schemaVersion': 1, 'name': 'Новая визитка', 'template': 'classic', 'accent': '#2457DB', 'links': []}


class Card(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE)
    public_id = models.CharField(max_length=40, unique=True, default=public_id, editable=False)
    draft = models.JSONField(default=empty_content)
    draft_version = models.PositiveIntegerField(default=1)
    published_revision = models.ForeignKey('CardRevision', on_delete=models.SET_NULL, null=True,
                                           blank=True, related_name='+')
    status = models.CharField(max_length=12, choices=[('draft', 'Черновик'), ('published', 'Опубликовано'),
                                                    ('deleted', 'Удалено')], default='draft')
    blocked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=['workspace', '-updated_at'])]

    @property
    def has_changes(self):
        return self.published_revision_id and self.draft != self.published_revision.content

    def __str__(self):
        return self.draft.get('name', 'Визитка')


class CardRevision(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    card = models.ForeignKey(Card, on_delete=models.CASCADE, related_name='revisions')
    schema_version = models.PositiveSmallIntegerField(default=1)
    content = models.JSONField()
    publication_conditions = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError('Published revisions are immutable')
        return super().save(*args, **kwargs)


class Asset(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE)
    object_key = models.CharField(max_length=240, unique=True, editable=False)
    bytes = models.PositiveIntegerField()
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)


class PhysicalCard(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    public_id = models.CharField(max_length=40, unique=True, default=public_id, editable=False)
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE)
    card = models.ForeignKey(Card, on_delete=models.SET_NULL, null=True, blank=True)
    label = models.CharField(max_length=100)
    enabled = models.BooleanField(default=True)
    blocked = models.BooleanField(default=False)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.label


class PhysicalCardEvent(models.Model):
    physical_card = models.ForeignKey(PhysicalCard, on_delete=models.CASCADE, related_name='events')
    actor = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=20)
    target_card = models.ForeignKey(Card, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
