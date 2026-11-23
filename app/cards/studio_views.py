from copy import deepcopy
from uuid import UUID
from functools import wraps
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST, require_safe
from accounts.views import redirect303
from .models import CardTemplate, TemplateIcon
from .designs import BLOCKS, DEFAULT, from_content, validate_design, validate_resources, icon_ids
from .studio_forms import TemplateForm, IconForm
from .examples import get_example
from .services import own_card, save_card, Conflict


def manager(view):
    @wraps(view)
    @staff_member_required(login_url='/accounts/login')
    def wrapped(request, *args, **kwargs):
        if not request.user.has_perm('cards.change_cardtemplate'):
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return never_cache(wrapped)


def demo(design, preset_id=None):
    from .premium import PREMIUM_ID, demo as premium_demo
    if str(preset_id) == PREMIUM_ID:
        return premium_demo(design)
    from .builtin_templates import EXAMPLE_TEMPLATES
    slug = next((slug for slug, entry in EXAMPLE_TEMPLATES.items() if entry[0] == str(preset_id)), 'designer')
    example = get_example(slug)
    content = deepcopy(example['content'])
    content.update(design=deepcopy(design), accent=design['accent'], phone='+79990000000')
    return {'content': content, 'example_assets': example['assets'],
            'example_qr_url': example['qr_url'], 'example_vcard_url': example['vcard_url']}


@manager
@require_http_methods(['GET','POST'])
def index(request):
    if request.method == 'POST':
        if not request.user.has_perm('cards.add_cardtemplate'):
            raise PermissionDenied
        item = CardTemplate.objects.create(name='Новый шаблон', draft=deepcopy(DEFAULT))
        return redirect303(f'/control/templates/{item.pk}')
    return render(request, 'studio/index.html', {'items': CardTemplate.objects.all()})


@manager
@require_http_methods(['GET','POST'])
def edit(request, pk):
    item = get_object_or_404(CardTemplate, pk=pk)
    form = TemplateForm(request.POST if request.method == 'POST' else None, item=item)
    status = 200
    if request.method == 'POST':
        status = 422
        if form.is_valid():
            try:
                validate_resources(form.design, request.user)
                from .blocks import validate_gallery_limit
                validate_gallery_limit({'design':form.design}, {'design':item.draft})
            except ValidationError as error:
                form.add_error(None,error)
        if not form.errors:
            with transaction.atomic():
                locked = CardTemplate.objects.select_for_update().get(pk=pk)
                if locked.version != form.cleaned_data['version']:
                    form.add_error(None, 'Шаблон изменён в другой вкладке. Обновите страницу перед сохранением.')
                    status = 409
                else:
                    for field in ('name','description','category','position'):
                        setattr(locked, field, form.cleaned_data[field])
                    locked.draft = form.design
                    locked.version += 1
                    if request.POST.get('operation') == 'publish':
                        # Explicit publication promotes the author's own icons to
                        # immutable shared copies; customer-private icons stay private.
                        for custom in TemplateIcon.objects.filter(pk__in=icon_ids(form.design),owner=request.user):
                            shared=TemplateIcon.objects.create(name=custom.name,svg=custom.svg)
                            for role, value in locked.draft.get('icons',{}).items():
                                if value == str(custom.pk): locked.draft['icons'][role]=str(shared.pk)
                            for settings in locked.draft.get('blockStyles',{}).values():
                                if settings.get('icon') == str(custom.pk): settings['icon']=str(shared.pk)
                        locked.published = deepcopy(form.design)
                        locked.published_version += 1
                        locked.status = 'published'
                    locked.save()
                    if request.headers.get('Accept') == 'application/json':
                        return JsonResponse({'version':locked.version,'design':locked.draft,
                            'published':request.POST.get('operation') == 'publish',
                            'icons':[{'id':str(icon.pk),'name':icon.name} for icon in TemplateIcon.objects.filter(pk__in=icon_ids(locked.draft))]})
                    messages.success(request, 'Шаблон опубликован в каталоге.' if request.POST.get('operation') == 'publish' else 'Черновик шаблона сохранён.')
                    return redirect303(f'/control/templates/{pk}')
        if request.headers.get('Accept') == 'application/json':
            return JsonResponse({'error':' '.join(str(error) for errors in form.errors.values() for error in errors)},status=status)
    design = form.design if hasattr(form, 'design') else (item.draft or deepcopy(DEFAULT))
    context = {'item': item, 'form': form, **demo(design, item.pk),
               'blocks': [{'key': key, 'label': dict(BLOCKS)[key]} for key in design['blocks']]}
    from .visual_views import editor_context
    context.update(editor_context(context['content'],request.user,template=True,example_pdf_url=context.get('example_pdf_url','')))
    return render(request, 'studio/edit.html', context, status=status)


@manager
@require_POST
def archive(request, pk):
    with transaction.atomic():
        item = get_object_or_404(CardTemplate.objects.select_for_update(), pk=pk)
        try:
            version = int(request.POST.get('version','0'))
        except ValueError:
            version = 0
        if item.version != version:
            return HttpResponse('Шаблон изменён. Обновите страницу.', status=409)
        item.status = 'archived'
        item.version += 1
        item.save()
    messages.success(request, 'Шаблон убран из каталога. Визитки клиентов сохранят своё оформление.')
    return redirect303('/control/templates')


@manager
@require_POST
def from_card(request, pk):
    if not request.user.has_perm('cards.add_cardtemplate'):
        raise PermissionDenied
    card = own_card(request.user, pk)
    definition = from_content(card.draft)
    for field in ('sourceId','sourceVersion','sourceName'):
        definition.pop(field, None)
    item = CardTemplate.objects.create(name='Оформление моей визитки', draft=definition)
    messages.success(request, 'Скопировано только оформление. Контакты, личные фотографии и ссылки в шаблон не переносятся.')
    return redirect303(f'/control/templates/{item.pk}')


@manager
@require_http_methods(['GET','POST'])
def icons(request):
    form = IconForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        if not request.user.has_perm('cards.add_templateicon'):
            raise PermissionDenied
        TemplateIcon.objects.create(name=form.cleaned_data['name'], svg=form.cleaned_data['image'])
        messages.success(request, 'Значок добавлен. Теперь его можно выбрать в настройках шаблона.')
        return redirect303('/control/icons')
    return render(request, 'studio/icons.html', {'form': form, 'icons': TemplateIcon.objects.all()},
                  status=422 if request.method == 'POST' else 200)


@require_safe
def icon(request, pk):
    item = get_object_or_404(TemplateIcon, pk=pk)
    from .visual_views import can_read_icon
    if not can_read_icon(request,item):
        from django.http import Http404
        raise Http404
    response = HttpResponse(item.svg, content_type='image/svg+xml')
    response['Content-Security-Policy'] = "default-src 'none'; sandbox"
    response['Cache-Control'] = 'private, no-store' if item.owner_id else 'public, max-age=86400, immutable'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@never_cache
@require_http_methods(['GET','POST'])
def catalog(request, pk):
    if not request.user.is_authenticated:
        return redirect303('/accounts/login')
    card = own_card(request.user, pk)
    if request.method == 'POST':
        try:
            template_id = UUID(request.POST.get('template_id', ''))
        except (ValueError, TypeError):
            from django.http import Http404
            raise Http404
        item = get_object_or_404(CardTemplate, pk=template_id, status='published')
        try:
            definition = deepcopy(validate_design(item.published))
            from .premium import PREMIUM_ID
            if str(item.pk) == PREMIUM_ID:
                # Portfolio photos are examples, never the customer's own work.
                definition.get('carousel', {})['photos'] = []
            definition.update(sourceId=str(item.pk), sourceVersion=item.published_version, sourceName=item.name)
            content = deepcopy(card.draft)
            content.update(design=definition, accent=definition['accent'])
            save_card(request.user, pk, int(request.POST.get('draft_version','0')), content)
        except (ValueError, ValidationError, Conflict) as error:
            messages.error(request, ' '.join(error.messages) if isinstance(error, ValidationError) else 'Черновик изменён. Обновите страницу и повторите выбор.')
        else:
            messages.success(request, 'Шаблон применён к черновику. Опубликуйте визитку, чтобы обновить её для посетителей.')
        return redirect303(f'/app/cards/{pk}/edit')
    items = [{'item': item, **demo(item.published, item.pk)} for item in CardTemplate.objects.filter(status='published')]
    return render(request, 'studio/catalog.html', {'items': items, 'card': card})
