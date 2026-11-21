import hashlib
import secrets
from datetime import timedelta
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.db import transaction, IntegrityError
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST
from billing.models import Subscription
from workspaces.models import Workspace, Membership
from .forms import RegistrationForm
from .models import EmailToken


class SessionLoginView(LoginView):
    def form_valid(self, form):
        response = super().form_valid(form)
        response.status_code = 303
        return response


class SessionLogoutView(LogoutView):
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 302:
            response.status_code = 303
        return response


def redirect303(url):
    response = HttpResponse(status=303)
    response['Location'] = url
    return response


def issue_verification(user):
    token = secrets.token_urlsafe(32)
    EmailToken.objects.create(user=user, digest=hashlib.sha256(token.encode()).hexdigest(),
                              expires_at=timezone.now() + timedelta(hours=24))
    send_mail('Подтвердите электронную почту — Визитка',
              f'Для подтверждения электронной почты откройте {settings.PUBLIC_BASE_URL}/accounts/verify/{token}\n'
              'Ссылка действует 24 часа. Подтверждение выполняется кнопкой на странице.',
              settings.DEFAULT_FROM_EMAIL, [user.email])


@require_http_methods(['GET', 'POST'])
def register(request):
    if request.user.is_authenticated:
        return redirect303('/app/cards')
    form = RegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                user = form.save()
                workspace = Workspace.objects.create(owner=user)
                Membership.objects.create(user=user, workspace=workspace)
                Subscription.objects.create(workspace=workspace)
                from .legal import record_acceptance
                request.user = user
                record_acceptance(request, 'processing')
                record_acceptance(request, 'offer', {'action': 'registration'})
        except IntegrityError:
            form.add_error('email', 'Аккаунт с этим email уже существует.')
        else:
            login(request, user)
            try:
                issue_verification(user)
                messages.success(request, 'Аккаунт создан. Подтвердите электронную почту по ссылке из письма.')
            except OSError:
                messages.warning(request, 'Аккаунт создан, но письмо не отправлено. Повторите отправку в кабинете.')
            return redirect303('/app/cards')
    return render(request, 'accounts/register.html', {'form': form},
                  status=422 if request.method == 'POST' else 200)


@require_http_methods(['GET', 'POST'])
def verify(request, token):
    digest = hashlib.sha256(token.encode()).hexdigest()
    valid = EmailToken.objects.filter(digest=digest, used_at__isnull=True, expires_at__gt=timezone.now()).exists()
    if request.method == 'POST' and valid:
        with transaction.atomic():
            record = EmailToken.objects.select_for_update().get(digest=digest)
            if record.used_at or record.expires_at <= timezone.now():
                return render(request, 'accounts/verify.html', {'valid': False}, status=400)
            record.used_at = timezone.now()
            record.save(update_fields=['used_at'])
            record.user.email_verified_at = timezone.now()
            record.user.save(update_fields=['email_verified_at'])
        messages.success(request, 'Электронная почта подтверждена. Можно публиковать визитку с активным Профи.')
        return redirect303('/app/cards')
    return render(request, 'accounts/verify.html', {'valid': valid}, status=200 if valid else 400)


@login_required
@require_POST
def resend(request):
    if not request.user.email_verified_at:
        issue_verification(request.user)
    messages.success(request, 'Если электронная почта не подтверждён, отправлено новое письмо.')
    return redirect303('/app/cards')
