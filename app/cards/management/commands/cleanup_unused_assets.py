from django.core.management.base import BaseCommand, CommandError
from cards.asset_cleanup import cleanup_unused_assets
from cards.models import Asset


class Command(BaseCommand):
    help = 'Удалить изображения, не используемые черновиками и текущими опубликованными версиями.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Показать объём без удаления файлов.')

    def handle(self, *args, **options):
        total = {'deleted': 0, 'bytes': 0, 'failed': 0}
        workspaces = list(Asset.objects.order_by().values_list('workspace_id', flat=True).distinct())
        for workspace_id in workspaces:
            result = cleanup_unused_assets(workspace_id, dry_run=options['dry_run'])
            for key in total:
                total[key] += result[key]
        label = 'Найдено' if options['dry_run'] else 'Удалено'
        self.stdout.write(f'{label} файлов: {total["deleted"]}; объём: {total["bytes"]} байт; ошибок: {total["failed"]}.')
        if total['failed']:
            raise CommandError('Не все файлы удалены. Исправьте доступ к хранилищу и повторите очистку.')
