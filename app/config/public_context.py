from django.conf import settings


def public_context(request):
    from billing.services import enabled
    from .seo import metadata
    from .analytics import configuration
    return {'analytics': configuration(request), 'seo': metadata(request), 'operator': {'name': settings.OPERATOR_NAME, 'phone': settings.OPERATOR_PHONE,
                         'email': settings.OPERATOR_EMAIL, 'inn': settings.OPERATOR_INN,
                         'address': settings.OPERATOR_ADDRESS},
            'legal_version': settings.LEGAL_VERSION,
            'legal_ready': settings.LEGAL_LAUNCH_CONFIRMED,
            'hosting_provider': settings.DATA_HOSTING_PROVIDER,
            'mail_provider': settings.DATA_MAIL_PROVIDER,
            'service_url': settings.PUBLIC_BASE_URL, 'payment_enabled': enabled(),
            'payment_test': settings.YOOKASSA_TEST_MODE}
