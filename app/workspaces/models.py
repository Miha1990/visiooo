import uuid
from django.conf import settings
from django.db import models


class Workspace(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name='Владелец')
    name = models.CharField(max_length=160, default='Мои визитки', verbose_name='Название')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'личный кабинет'
        verbose_name_plural = 'Личные кабинеты'


class Membership(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name='Пользователь')
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, verbose_name='Личный кабинет')
    role = models.CharField(max_length=10, choices=[('owner', 'Владелец')], default='owner', verbose_name='Роль')

    class Meta:
        verbose_name = 'участник кабинета'
        verbose_name_plural = 'Участники кабинетов'
        constraints = [models.UniqueConstraint(fields=['user', 'workspace'], name='unique_membership')]
