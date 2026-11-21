import hashlib
import logging
import secrets
from datetime import timedelta
from smtplib import SMTPException

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.forms import SetPasswordForm
from django.core.mail import send_mail
from django.db import transaction
from django.shortcuts import render
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods

from .models import User, PasswordResetToken
from .views import redirect303

logger = logging.getLogger(__name__)


class ResetRequestForm(forms.Form):
    email = forms.EmailField(label='Электронная почта аккаунта', max_length=254)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def issue_password_reset(user):
    raw_token = secrets.token_urlsafe(32)
    PasswordResetToken.objects.create(user=user, digest=digest(raw_token),
        credential_digest=digest(user.password),
        expires_at=timezone.now() + timedelta(seconds=settings.PASSWORD_RESET_TIMEOUT))
    send_mail('Восстановление доступа — Визитка',
        f'Чтобы задать новый пароль, откройте {settings.PUBLIC_BASE_URL}/accounts/password-reset/{raw_token}\n'
        'Ссылка действует один час. Если вы не запрашивали письмо, просто проигнорируйте его.',
        settings.DEFAULT_FROM_EMAIL, [user.email])


@never_cache
@require_http_methods(['GET', 'POST'])
def request_reset(request):
    form = ResetRequestForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        email = form.cleaned_data['email'].strip().lower()
        user = User.objects.filter(email=email, is_active=True).first()
        if user and user.has_usable_password():
            try:
                issue_password_reset(user)
            except (OSError, SMTPException):
                logger.warning('Password reset email could not be sent.')
        return redirect303('/accounts/password-reset/sent')
    return render(request, 'accounts/password_reset_request.html', {'form': form},
                  status=422 if request.method == 'POST' else 200)


def token_is_valid(token):
    return bool(token and not token.used_at and token.expires_at > timezone.now()
                and token.user.is_active
                and constant_time_compare(token.credential_digest, digest(token.user.password)))


@sensitive_post_parameters('new_password1', 'new_password2')
@never_cache
@require_http_methods(['GET', 'POST'])
def confirm_reset(request, token):
    record = PasswordResetToken.objects.select_related('user').filter(digest=digest(token)).first()
    valid = token_is_valid(record)
    form = SetPasswordForm(record.user, data=request.POST if request.method == 'POST' else None) if valid else None
    if request.method == 'POST' and valid and form.is_valid():
        with transaction.atomic():
            # Serialize changes across all reset tokens belonging to the same user.
            user = User.objects.select_for_update().get(pk=record.user_id)
            record = PasswordResetToken.objects.select_for_update().get(pk=record.pk)
            record.user = user
            if not token_is_valid(record):
                return render(request, 'accounts/password_reset_confirm.html', {'valid': False}, status=400)
            form = SetPasswordForm(user, data=request.POST)
            if form.is_valid():
                form.save()
                record.used_at = timezone.now()
                record.save(update_fields=['used_at'])
        messages.success(request, 'Пароль обновлён. Войдите с новым паролем.')
        return redirect303('/accounts/login')
    return render(request, 'accounts/password_reset_confirm.html', {'form': form, 'valid': valid},
                  status=400 if not valid else (422 if request.method == 'POST' else 200))
