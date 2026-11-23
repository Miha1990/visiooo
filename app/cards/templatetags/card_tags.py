from django import template
from cards.socials import social_links

register = template.Library()
register.filter('social_links', social_links)


@register.simple_tag(takes_context=True)
def card_buttons(context):
    from django.templatetags.static import static
    from cards.button_builder import TYPES
    result = []
    for item in context['content'].get('buttons', []):
        kind = item['kind']; value = item['value']; external = kind not in ('phone','other_phone','email')
        if kind in ('phone','other_phone'): href = 'tel:' + value
        elif kind == 'email': href = 'mailto:' + value
        elif kind == 'file' and not value: href = document_url(context); external = False
        else: href = value
        if href:
            result.append({**item, 'href':href, 'icon':static('icons/'+TYPES[kind]['icon']+'.svg'),
                           'external':external, 'download':kind == 'file'})
    return result


@register.simple_tag
def block_visible(content, key):
    from cards.client_content import block_has_content
    return block_has_content(content, key)

@register.filter
def design_style(value):
    from cards.designs import css
    return css(value)

@register.simple_tag
def design_icon(design, role):
    from django.urls import reverse
    from django.templatetags.static import static
    pk = design.get('icons', {}).get(role)
    return reverse('template_icon', args=[pk]) if pk else static(f'icons/{role}.svg')

@register.filter
def design_icons(design):
    import json
    from cards.designs import ICON_ROLES
    return json.dumps({key: design_icon(design, key) for key, _ in ICON_ROLES})

@register.simple_tag
def design_block(design, key):
    from cards.designs import block_settings
    return block_settings(design, key)


@register.simple_tag
def frame_style(design, key):
    from cards.designs import frame_css
    return frame_css(design,key)


@register.filter
def corner_style(corners):
    return ' '.join(f'{int(v)}px' for v in corners) if corners else ''


@register.simple_tag(takes_context=True)
def card_image(context, slot):
    from cards.image_slots import IMAGE_FIELDS
    from django.urls import reverse
    from django.templatetags.static import static
    content=context['content']; examples=context.get('example_assets')
    pk=content.get(IMAGE_FIELDS[slot]); card=context.get('card')
    if pk and not examples and card:
        return reverse('preview_asset',args=[card.pk,pk]) if context.get('preview') else reverse('public_asset',args=[card.public_id,pk])
    shared=content.get('design',{}).get('images',{}).get(slot)
    if shared:return reverse('template_photo',args=[shared])
    return static(examples[slot]) if examples and examples.get(slot) else ''


@register.simple_tag(takes_context=True)
def gallery_images(context):
    from django.urls import reverse
    content=context['content']; card=context.get('card')
    if context.get('example_gallery'):
        return context['example_gallery']
    if 'galleryAssetIds' in content and card and not context.get('example_assets'):
        return [{'id':pk,'url':reverse('preview_asset',args=[card.pk,pk]) if context.get('preview') else reverse('public_asset',args=[card.public_id,pk])} for pk in content['galleryAssetIds']]
    return [{'id':pk,'url':reverse('template_photo',args=[pk])} for pk in content.get('design',{}).get('carousel',{}).get('photos',[])]


@register.simple_tag
def video_player(content):
    from cards.blocks import video_embed
    video = content.get('video', {})
    return video_embed(video['url'], video.get('embedUrl', '')) if video.get('url') else ''


@register.simple_tag
def address_map(content):
    from cards.blocks import map_embed
    return map_embed(content.get('map', {}))


@register.simple_tag(takes_context=True)
def document_url(context):
    from django.urls import reverse
    if context.get('example_pdf_url'):
        return context['example_pdf_url']
    pk = context['content'].get('document', {}).get('assetId')
    card = context.get('card')
    if not pk or not card: return ''
    return reverse('preview_asset', args=[card.pk, pk]) if context.get('preview') else reverse('public_asset', args=[card.public_id, pk])
