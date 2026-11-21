import json
import re
import uuid
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.cache import cache
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from accounts.legal import record_acceptance
from accounts.views import redirect303
from cards.services import workspace_for
from workspaces.models import Workspace
from .models import Payment, Subscription
from . import services, gateway


@login_required
@never_cache
@require_GET
def index(request):
    workspace = workspace_for(request.user)
    plans = [{'period': period, 'price': price, 'label': 'Месяц' if period == 'month' else 'Год',
              'token': signing.dumps({'workspace': str(workspace.pk), 'period': period, 'id': str(uuid.uuid4())}, salt='checkout')}
             for period, price in services.PRICES.items()]
    return render(request, 'billing/index.html', {'plans': plans, 'payment_enabled': services.enabled(),
        'payment_test': settings.YOOKASSA_TEST_MODE, 'subscription': Subscription.objects.filter(workspace=workspace).first(),
        'payments': Payment.objects.filter(workspace=workspace)[:30]})


@login_required
@never_cache
@require_POST
def checkout(request):
    workspace = workspace_for(request.user)
    if not services.enabled():
        return HttpResponse('Подключение оплаты ещё не завершено.', status=503)
    if not request.user.email_verified_at:
        return HttpResponse('Перед оплатой подтвердите электронную почту.', status=422)
    if request.POST.get('offer') != 'yes' or request.POST.get('processing') != 'yes':
        return HttpResponse('Отдельно подтвердите оферту и согласие на обработку данных.', status=422)
    try:
        token = signing.loads(request.POST.get('token', ''), salt='checkout', max_age=23 * 3600)
        if token['workspace'] != str(workspace.pk) or token['period'] not in services.PRICES:
            raise ValueError
        payment_id = uuid.UUID(token['id'])
    except (signing.BadSignature, ValueError, KeyError, TypeError):
        return HttpResponse('Сессия оплаты устарела. Откройте страницу подписки заново.', status=422)
    with transaction.atomic():
        Workspace.objects.select_for_update().get(pk=workspace.pk)
        payment, created = Payment.objects.get_or_create(pk=payment_id, defaults={
            'workspace': workspace, 'user': request.user, 'period': token['period'],
            'amount': services.PRICES[token['period']], 'shop_id': settings.YOOKASSA_SHOP_ID,
            'test': settings.YOOKASSA_TEST_MODE})
        if payment.workspace_id != workspace.pk or payment.user_id != request.user.pk or payment.period != token['period']:
            return HttpResponse(status=403)
        if created:
            scope = {'payment': str(payment.pk), 'amount': str(payment.amount), 'period': payment.period}
            record_acceptance(request, 'offer', scope)
            record_acceptance(request, 'processing', scope)
    try:
        payment = services.create_or_resume(payment)
    except gateway.GatewayError as error:
        messages.error(request, str(error))
        return redirect303(f'/app/payments/{payment.pk}')
    if payment.status == 'pending' and payment.confirmation_url:
        return redirect303(services.safe_confirmation(payment.confirmation_url))
    return redirect303(f'/app/payments/{payment.pk}')


def own_payment(request, pk):
    return get_object_or_404(Payment, pk=pk, workspace=workspace_for(request.user))


@login_required
@never_cache
@require_GET
def detail(request, pk):
    payment = own_payment(request, pk)
    return render(request, 'billing/detail.html', {'payment': payment})


@login_required
@never_cache
@require_POST
def check(request, pk):
    payment = own_payment(request, pk)
    if not services.enabled():
        return HttpResponse('Проверка оплаты временно недоступна.', status=503)
    try:
        services.create_or_resume(payment)
    except gateway.GatewayError as error:
        messages.error(request, str(error))
    return redirect303(f'/app/payments/{pk}')


@login_required
@never_cache
@require_GET
def status(request, pk):
    payment = own_payment(request, pk)
    return JsonResponse({'status': payment.status})


@csrf_exempt
@require_POST
def notification(request):
    if not services.enabled():
        return HttpResponse(status=503)
    if len(request.body) > 65536:
        return HttpResponse(status=413)
    try:
        body = json.loads(request.body)
        if body.get('type') != 'notification':
            raise ValueError
        event, object_id = body['event'], body['object']['id']
        if not isinstance(object_id, str) or not re.fullmatch(r'[a-zA-Z0-9-]{1,64}', object_id):
            raise ValueError
    except (ValueError, KeyError, TypeError, AttributeError):
        return HttpResponse(status=400)
    if event not in ['payment.succeeded', 'payment.canceled', 'refund.succeeded']:
        return HttpResponse(status=200)
    # Claimed status/amount/metadata are never applied. Fetch the object with shop credentials.
    try:
        if event == 'refund.succeeded':
            refund = gateway.request('GET', 'refunds/' + object_id)
            if refund.get('id') != object_id or refund.get('status') != 'succeeded':
                return HttpResponse(status=400)
            object_id = refund.get('payment_id')
        if not isinstance(object_id, str) or not re.fullmatch(r'[a-zA-Z0-9-]{1,64}', object_id):
            return HttpResponse(status=400)
        verified = gateway.request('GET', 'payments/' + object_id)
        payment = Payment.objects.filter(provider_id=object_id).first()
        if not payment:
            # Recover an order even if the initial API response was lost before saving its ID.
            try:
                order_id = uuid.UUID(verified.get('metadata', {}).get('order_id', ''))
            except (ValueError, TypeError, AttributeError):
                return HttpResponse(status=200)
            payment = Payment.objects.filter(pk=order_id, provider_id=None).first()
        if payment:
            if cache.add('payment-sync:' + str(payment.pk), True, 2):
                try:
                    services.apply(payment.pk, verified)
                finally:
                    cache.delete('payment-sync:' + str(payment.pk))
            else:
                return HttpResponse(status=503)
    except gateway.GatewayError:
        return HttpResponse(status=503)
    return HttpResponse(status=200)
