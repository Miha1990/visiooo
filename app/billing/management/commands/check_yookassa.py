from urllib.parse import urlsplit

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from billing import gateway, services


class Command(BaseCommand):
    help = 'Проверить настройки ЮКассы без создания платежей и списаний. Секреты не выводятся.'
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument('--api', action='store_true', help='Дополнительно проверить ключ запросом GET /v3/me.')

    def handle(self, *args, **options):
        problems = []
        required = ['YOOKASSA_SHOP_ID', 'YOOKASSA_SECRET_KEY']
        if not settings.YOOKASSA_TEST_MODE:
            required += ['OPERATOR_INN', 'OPERATOR_ADDRESS', 'DATA_HOSTING_PROVIDER', 'DATA_MAIL_PROVIDER']
        for name in required:
            if not getattr(settings, name):
                problems.append(f'Не заполнено {name}.')
        if not settings.YOOKASSA_ENABLED:
            problems.append('Приём платежей выключен: YOOKASSA_ENABLED=false.')
        if settings.YOOKASSA_TEST_MODE:
            if not settings.DEBUG:
                problems.append('Тестовый магазин допускается только в отдельном окружении разработки.')
        else:
            if settings.DEBUG:
                problems.append('Для рабочего сайта требуется DEBUG=false.')
            if not settings.LEGAL_LAUNCH_CONFIRMED:
                problems.append('Не подтверждена готовность документов и обработки данных: LEGAL_LAUNCH_CONFIRMED=false.')
            if not settings.NPD_RECEIPTS_CONFIRMED:
                problems.append('Не подтверждён действующий порядок выдачи чеков НПД: NPD_RECEIPTS_CONFIRMED=false.')
            if urlsplit(settings.PUBLIC_BASE_URL).scheme != 'https':
                problems.append('PUBLIC_BASE_URL должен использовать HTTPS.')
        if options['api'] and settings.YOOKASSA_SHOP_ID and settings.YOOKASSA_SECRET_KEY:
            try:
                account = gateway.request('GET', 'me')
            except gateway.GatewayError:
                problems.append('Не удалось проверить доступ к API. Проверьте ключ, shopId и соединение с ЮКассой.')
            else:
                if account.get('account_id') != str(settings.YOOKASSA_SHOP_ID):
                    problems.append('API вернул другой идентификатор магазина.')
                elif account.get('test') is not settings.YOOKASSA_TEST_MODE:
                    problems.append('Режим магазина в API не совпадает с YOOKASSA_TEST_MODE.')
                elif account.get('status') == 'disabled':
                    problems.append('Магазин отключён на стороне ЮКассы.')
                else:
                    self.stdout.write('Доступ к API подтверждён. Идентификатор и режим магазина совпадают.')
        self.stdout.write('Уведомления: ' + settings.PUBLIC_BASE_URL.rstrip('/') + '/payments/yookassa/notification')
        self.stdout.write('События: payment.succeeded, payment.canceled, refund.succeeded.')
        self.stdout.write('Тарифы: 199 ₽ за месяц; 1490 ₽ за год. Автоматических списаний нет.')
        if problems:
            for problem in problems:
                self.stderr.write(problem)
            raise CommandError('Настройка не завершена. Изменения в настройки и платежи не вносились.')
        if not services.enabled():
            raise CommandError('Оплата недоступна: проверьте настройки запуска.')
        self.stdout.write('Настройки готовы. Создание, оплату и доставку чека нужно проверить отдельно.')
