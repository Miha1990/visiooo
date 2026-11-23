import hashlib
import secrets
import uuid
from datetime import timedelta
from smtplib import SMTPException

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from django.views.decorators.http import require_http_methods, require_POST

from billing.models import Subscription
from workspaces.models import Membership, Workspace
from .forms import RegistrationCodeForm, RegistrationForm
from .models import LegalAcceptance, PendingRegistration, User

SESSION_KEY = 'pending_registration'
CODE_URL = '/accounts/registration-code'


def redirect(url):
    return HttpResponseRedirect(url, status=303)


def digest(pending, code):
    return salted_hmac('registration-code', f'{pending.browser_token}:{code}', algorithm='sha256').hexdigest()


def snapshot_documents(request):
    result = []
    for document in ('processing', 'offer'):
        text = render_to_string(f'legal/texts/{document}.html', request=request)
        result.append({'document': document, 'version': settings.LEGAL_VERSION,
                       'document_text': text, 'document_sha256': hashlib.sha256(text.encode()).hexdigest(),
                       'scope': {'action': 'registration', 'submitted_at': timezone.now().isoformat()}})
    return result


def send_limit_error(pending, now):
    if pending.last_sent_at and now < pending.last_sent_at + timedelta(seconds=60):
        return 'Повторная отправка доступна через минуту после предыдущей.'
    if now < pending.window_started_at + timedelta(hours=1) and pending.send_count >= 5:
        return 'Лимит отправок исчерпан. Попробуйте через час.'
    if now < pending.window_started_at + timedelta(hours=1) and pending.attempts >= 5:
        return 'Слишком много попыток ввода кода. Попробуйте через час.'
    return ''


@sensitive_variables('code')
def send_code(pending):
    """Called under a row lock; limits survive workers, browser changes and restarts."""
    now = timezone.now()
    error = send_limit_error(pending, now)
    if error:
        return error
    if now >= pending.window_started_at + timedelta(hours=1):
        pending.window_started_at, pending.send_count, pending.attempts = now, 0, 0
    code = f'{secrets.randbelow(1000000):06d}'
    while pending.code_digest and constant_time_compare(pending.code_digest, digest(pending, code)):
        code = f'{secrets.randbelow(1000000):06d}'
    pending.code_digest = digest(pending, code)
    pending.expires_at = now + timedelta(minutes=10)
    pending.last_sent_at = now
    pending.send_count += 1
    # Attempts are cumulative for this browser challenge, including resends.
    error = ''
    try:
        sent = send_mail('Код подтверждения регистрации — Визитка',
            f'Ваш код подтверждения: {code}\n\nВведите его на странице регистрации {settings.PUBLIC_BASE_URL}.'
            '\nКод действует 10 минут. Никому не сообщайте его.'
            '\nЕсли вы не регистрировались, просто проигнорируйте это письмо.',
            settings.DEFAULT_FROM_EMAIL, [pending.email])
        if not sent:
            error = 'Не удалось отправить письмо. Повторите отправку через минуту.'
    except (OSError, SMTPException):
        error = 'Не удалось отправить письмо. Повторите отправку через минуту.'
    if error:
        pending.code_digest = ''
    pending.save()
    return error


@never_cache
@sensitive_post_parameters('password1', 'password2')
@require_http_methods(['GET', 'POST'])
def start(request):
    if request.user.is_authenticated:
        return redirect('/app/cards')
    form = RegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        PendingRegistration.objects.filter(expires_at__lt=timezone.now() - timedelta(days=1)).delete()
        try:
            with transaction.atomic():
                now = timezone.now()
                pending, created = PendingRegistration.objects.select_for_update().get_or_create(
                    email=form.cleaned_data['email'], defaults={'expires_at': now, 'window_started_at': now})
                owned = str(pending.browser_token) == request.session.get(SESSION_KEY)
                error = send_limit_error(pending, now)
                # Another browser must receive a fresh code before it can replace
                # the pending password/session. Never reuse the previous browser's code.
                if not created and not owned and error:
                    form.add_error(None, error)
                else:
                    if not owned:
                        pending.browser_token = uuid.uuid4()
                    pending.password = form.save(commit=False).password
                    pending.first_name = form.cleaned_data['first_name']
                    pending.last_name = form.cleaned_data['last_name']
                    pending.legal_documents = snapshot_documents(request)
                    # Keep the last valid code during the one-minute cooldown.
                    # Submitting the form again must not send repeated emails or
                    # silently reset the verification-attempt limit.
                    if (owned and pending.code_digest and pending.expires_at > now
                            and pending.attempts < 5 and pending.last_sent_at
                            and now < pending.last_sent_at + timedelta(seconds=60)):
                        pending.save(update_fields=['password', 'first_name', 'last_name', 'legal_documents'])
                        messages.info(request, 'Код уже отправлен. Введите последний полученный код или запросите новый через минуту.')
                        return redirect(CODE_URL)
                    pending.save(update_fields=['browser_token', 'password', 'first_name', 'last_name', 'legal_documents'])
                    error = send_code(pending)
                    request.session[SESSION_KEY] = str(pending.browser_token)
                    if error:
                        messages.error(request, error)
                    else:
                        messages.success(request, 'Код отправлен на вашу почту.' if created else
                            'Новый код отправлен. Используйте код из последнего письма.')
                    return redirect(CODE_URL)
        except IntegrityError:
            form.add_error('email', 'Регистрация уже начата. Попробуйте ещё раз.')
    return render(request, 'accounts/register.html', {'form': form}, status=422 if request.method == 'POST' else 200)


def pending_token(request):
    try:
        return uuid.UUID(request.session.get(SESSION_KEY, ''))
    except (ValueError, TypeError, AttributeError):
        return None


@never_cache
@sensitive_post_parameters('code')
@require_http_methods(['GET', 'POST'])
def confirm(request):
    if request.user.is_authenticated:
        return redirect('/app/cards')
    token = pending_token(request)
    if not token:
        return redirect('/accounts/register')
    form = RegistrationCodeForm(request.POST or None)
    user = None
    with transaction.atomic():
        pending = PendingRegistration.objects.select_for_update().filter(browser_token=token).first()
        if not pending:
            request.session.pop(SESSION_KEY, None)
            return redirect('/accounts/register')
        if request.method == 'POST':
            if pending.attempts >= 5:
                form.add_error(None, 'Слишком много попыток. Начните регистрацию заново через час.')
            elif pending.expires_at <= timezone.now() or not pending.code_digest:
                form.add_error(None, 'Код недействителен или срок истёк. Запросите новый код.')
            else:
                pending.attempts += 1
                pending.save(update_fields=['attempts'])
                if form.is_valid():
                    if not constant_time_compare(pending.code_digest, digest(pending, form.cleaned_data['code'])):
                        form.add_error('code', 'Неверный код. Проверьте письмо.')
                    else:
                        try:
                            with transaction.atomic():
                                user = User.objects.create(email=pending.email, password=pending.password,
                                    first_name=pending.first_name, last_name=pending.last_name, email_verified_at=timezone.now())
                                workspace = Workspace.objects.create(owner=user)
                                Membership.objects.create(user=user, workspace=workspace)
                                Subscription.objects.create(workspace=workspace)
                                for document in pending.legal_documents:
                                    LegalAcceptance.objects.create(user=user, **document)
                        except IntegrityError:
                            user = None
                            form.add_error(None, 'Аккаунт с этой почтой уже существует. Войдите в него.')
                        else:
                            pending.delete()
    if user:
        request.session.pop(SESSION_KEY, None)
        login(request, user)
        messages.success(request, 'Почта подтверждена. Регистрация завершена.')
        return redirect('/app/cards')
    return render(request, 'accounts/registration_code.html', {'form': form, 'pending': pending},
                  status=422 if request.method == 'POST' else 200)


@never_cache
@require_POST
def resend(request):
    token = pending_token(request)
    with transaction.atomic():
        pending = PendingRegistration.objects.select_for_update().filter(browser_token=token).first() if token else None
        if not pending:
            return redirect('/accounts/register')
        error = send_code(pending)
    if error:
        messages.error(request, error)
    else:
        messages.success(request, 'Новый код отправлен. Предыдущий код больше не действует.')
    return redirect(CODE_URL)
