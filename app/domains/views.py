from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST, require_GET
from accounts.views import redirect303
from cards.services import workspace_for, public_card
from cards.views import qr_response
from .models import DomainBinding
from .forms import DomainForm, DomainTargetForm
from .dns import configured, ingress_addresses
from .services import add_domain, verify_domain, request_certificate, disable_domain, remove_domain, owned, worker_ready, change_target


@login_required
@never_cache
@require_http_methods(['GET', 'POST'])
def index(request):
    workspace = workspace_for(request.user)
    form = DomainForm(request.POST if request.method == 'POST' else None,
        workspace=workspace, initial={'card': request.GET.get('card')})
    if request.method == 'POST' and form.is_valid():
        try:
            add_domain(request.user, form.cleaned_data['hostname'], form.cleaned_data['card'])
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, 'Домен добавлен. Настройте записи DNS по инструкции ниже.')
            return redirect303('/app/domains')
    binding = DomainBinding.objects.filter(workspace=workspace).select_related('root_card').first()
    return render(request, 'domains/index.html', {'form': form, 'binding': binding,
        'target_form': DomainTargetForm(workspace=workspace, initial={'card': binding.root_card_id,
            'generation': binding.generation}) if binding else None,
        'configured': configured(), 'addresses': ingress_addresses(), 'worker_ready': worker_ready()},
        status=422 if request.method == 'POST' else 200)


@login_required
@require_POST
def action(request, pk, operation):
    handlers = {'verify': verify_domain, 'certificate': request_certificate,
                'disable': disable_domain, 'remove': remove_domain}
    if operation not in handlers:
        raise Http404
    try:
        result = handlers[operation](request.user, pk)
    except ValidationError as error:
        messages.error(request, ' '.join(error.messages))
    except Http404:
        # Ownership errors remain 404; an unpublished own root card is explained.
        binding = owned(request.user, pk)
        messages.error(request, 'Для HTTPS нужна опубликованная визитка с активным Pro.')
    else:
        messages.success(request, {'verify': 'DNS подтверждён.' if result else 'DNS пока не подтверждён. Проверьте записи.',
            'certificate': 'Запрос HTTPS добавлен в очередь. Статус обновится автоматически.',
            'disable': 'Домен отключён. Для повторного подключения требуется новая TXT-запись.',
            'remove': 'Привязка удалена.'}[operation])
    return redirect303('/app/domains')


@login_required
@require_POST
def target(request, pk):
    binding = owned(request.user, pk)
    form = DomainTargetForm(request.POST, workspace=binding.workspace)
    if form.is_valid():
        try:
            change_target(request.user, pk, form.cleaned_data['card'], form.cleaned_data['generation'])
        except ValidationError as error:
            messages.error(request, ' '.join(error.messages))
        else:
            messages.success(request, 'Домен привязан к выбранной визитке.')
    else:
        messages.error(request, 'Выберите свою визитку и обновите страницу перед повторной попыткой.')
    return redirect303('/app/domains')


@login_required
@never_cache
@require_GET
def qr(request, pk):
    binding = owned(request.user, pk)
    if not binding.routable:
        raise Http404
    public_card(binding.root_card.public_id, workspace=binding.workspace)
    return qr_response(f'https://{binding.hostname}/', 'custom-domain-qr.png')
