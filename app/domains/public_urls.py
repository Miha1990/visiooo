from django.urls import path
from cards import views, asset_views, physical_views
from config import webapp
from config import seo
from cards.studio_views import icon


def root(request):
    return views.public(request, request.domain_binding.root_card.public_id)


urlpatterns = [
    path('template-icons/<uuid:pk>.svg', icon, name='template_icon'),
    path('robots.txt', seo.robots),
    path('sitemap.xml', seo.sitemap),
    path('favicon.ico', webapp.favicon),
    path('apple-touch-icon.png', webapp.apple_touch_icon),
    path('apple-touch-icon-precomposed.png', webapp.apple_touch_icon),
    path('', root, name='domain_root'),
    path('c/<str:public_id>', views.public, name='public'),
    path('c/<str:public_id>/contact.vcf', views.vcard, name='vcard'),
    path('c/<str:public_id>/qr.png', views.public_qr, name='public_qr'),
    path('c/<str:public_id>/assets/<uuid:asset_id>', asset_views.public, name='public_asset'),
    path('p/<str:public_id>', physical_views.resolve, name='physical_resolve'),
]
