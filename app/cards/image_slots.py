# The order is also the order of the styling controls in the editor.
IMAGE_FIELDS = {
    'background': 'backgroundAssetId',
    'avatar': 'avatarAssetId',
    'header': 'headerAssetId',
}


def content_asset_ids(content):
    return {str(content[field]) for field in IMAGE_FIELDS.values() if content.get(field)} | set(content.get('galleryAssetIds', [])) | ({content['document']['assetId']} if content.get('document', {}).get('assetId') else set())
