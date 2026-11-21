from django.urls import path
from cards import views, asset_views, physical_views


def root(request):
    return views.public(request, request.domain_binding.root_card.public_id)


urlpatterns = [
    path('', root, name='domain_root'),
    path('c/<str:public_id>', views.public, name='public'),
    path('c/<str:public_id>/contact.vcf', views.vcard, name='vcard'),
    path('c/<str:public_id>/qr.png', views.public_qr, name='public_qr'),
    path('c/<str:public_id>/assets/<uuid:asset_id>', asset_views.public, name='public_asset'),
    path('p/<str:public_id>', physical_views.resolve, name='physical_resolve'),
]
