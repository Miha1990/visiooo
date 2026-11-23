from django import template
from cards.socials import social_links

register = template.Library()
register.filter('social_links', social_links)

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
