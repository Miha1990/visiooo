from django.http import Http404
from django.shortcuts import render
from django.views.decorators.http import require_GET

DOCUMENTS = {'privacy': 'Политика обработки персональных данных', 'offer': 'Публичная оферта',
             'cookies': 'Файлы cookie и Яндекс Метрика',
             'analytics': 'Согласие на обработку данных для аналитики',
             'processing': 'Согласие на обработку персональных данных',
             'publication': 'Согласие на распространение персональных данных'}


@require_GET
def document(request, slug):
    if slug not in DOCUMENTS:
        raise Http404
    return render(request, 'legal/document.html', {'document_title': DOCUMENTS[slug],
                   'document_template': f'legal/texts/{slug}.html'})
