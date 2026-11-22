"""Collect files only after committed card changes, under the workspace write lock."""
import logging

from django.db import transaction
from workspaces.models import Workspace
from .image_slots import IMAGE_FIELDS
from .models import Asset, Card

logger = logging.getLogger(__name__)


def referenced_asset_ids(workspace_id, replacement=None):
    """Historical revisions are evidence, not live file references.

    Keep the current publication even when blocked, unpaid or unpublished.
    A replacement is used to calculate the quota for the prospective draft.
    """
    referenced = set()
    cards = Card.objects.filter(workspace_id=workspace_id).exclude(status='deleted').select_related('published_revision')
    for card in cards:
        draft = replacement[1] if replacement and card.pk == replacement[0] else card.draft
        contents = [draft]
        if card.published_revision_id:
            contents.append(card.published_revision.content)
        for content in contents:
            referenced.update(str(content[field]) for field in IMAGE_FIELDS.values() if content.get(field))
    return referenced


@transaction.atomic
def cleanup_unused_assets(workspace_id, dry_run=False):
    Workspace.objects.select_for_update().get(pk=workspace_id)
    referenced = referenced_asset_ids(workspace_id)
    assets = Asset.objects.filter(workspace_id=workspace_id).exclude(pk__in=referenced)
    result = {'deleted': 0, 'bytes': 0, 'failed': 0}
    from .images import private_storage
    storage = private_storage()
    for asset in assets.iterator():
        if not dry_run:
            try:
                storage.delete(asset.object_key)
            except OSError:
                # Keep the database row so the command or the next edit can retry.
                logger.warning('Unused image deletion failed: %s', asset.pk, exc_info=True)
                result['failed'] += 1
                continue
            asset.delete()
        result['deleted'] += 1
        result['bytes'] += asset.bytes
    return result


def schedule_cleanup(workspace_id):
    # Rollback must never remove images still used by the committed card version.
    transaction.on_commit(lambda: cleanup_unused_assets(workspace_id), robust=True)
