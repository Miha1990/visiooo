import uuid
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.db.models.functions import Lower


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email is required')
        user = self.model(email=email.strip().lower(), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.update(is_staff=True, is_superuser=True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = None
    email = models.EmailField(unique=True, verbose_name='Электронная почта')
    email_verified_at = models.DateTimeField(null=True, blank=True, verbose_name='Почта подтверждена')
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    objects = UserManager()

    class Meta:
        verbose_name = 'пользователь'
        verbose_name_plural = 'Пользователи'
        constraints = [models.UniqueConstraint(Lower('email'), name='user_email_case_unique')]

    def save(self, *args, **kwargs):
        self.email = self.email.strip().lower()
        super().save(*args, **kwargs)


class EmailToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    digest = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'подтверждение почты'
        verbose_name_plural = 'Подтверждения почты'


class PendingRegistration(models.Model):
    email = models.EmailField(unique=True)
    browser_token = models.UUIDField(default=uuid.uuid4, unique=True)
    password = models.CharField(max_length=128)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    legal_documents = models.JSONField(default=list)
    code_digest = models.CharField(max_length=64, blank=True)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    last_sent_at = models.DateTimeField(null=True)
    window_started_at = models.DateTimeField()
    send_count = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = 'заявка на регистрацию'
        verbose_name_plural = 'Заявки на регистрацию'


class PasswordResetToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    digest = models.CharField(max_length=64, unique=True)
    credential_digest = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'восстановление пароля'
        verbose_name_plural = 'Восстановления пароля'


class LegalAcceptance(models.Model):
    user = models.ForeignKey(User, on_delete=models.PROTECT, verbose_name='Пользователь')
    document = models.CharField(max_length=32, verbose_name='Документ', choices=[
        ('processing', 'Согласие на обработку данных'), ('offer', 'Публичная оферта'),
        ('publication', 'Согласие на распространение данных')])
    version = models.CharField(max_length=32, verbose_name='Редакция')
    document_sha256 = models.CharField(max_length=64, verbose_name='Контрольная сумма документа')
    document_text = models.TextField(verbose_name='Текст документа')
    accepted_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата подтверждения')
    scope = models.JSONField(default=dict, verbose_name='Подтверждённые условия')

    class Meta:
        verbose_name = 'подтверждение документа'
        verbose_name_plural = 'Подтверждения документов'

    def __str__(self):
        return f'Подтверждение — {self.get_document_display()}'
