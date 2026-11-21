import hashlib
from django.conf import settings
from django.template.loader import render_to_string
from .models import LegalAcceptance


def record_acceptance(request, document, scope=None):
    text = render_to_string(f'legal/texts/{document}.html', request=request)
    return LegalAcceptance.objects.create(user=request.user, document=document,
        version=settings.LEGAL_VERSION, document_sha256=hashlib.sha256(text.encode()).hexdigest(), document_text=text,
        scope=scope or {})
