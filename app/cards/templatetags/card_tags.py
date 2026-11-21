from django import template
from cards.socials import social_links

register = template.Library()
register.filter('social_links', social_links)
