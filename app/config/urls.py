from django.contrib import admin
from django.urls import path
from django.views.generic import TemplateView
from accounts import views as accounts
from accounts.forms import LoginForm
from accounts import password_reset
from accounts import registration
from cards import views
from cards import asset_views
from cards import physical_views
from cards import examples
from domains import views as domain_views
from billing import views as billing
from . import legal_views
from . import webapp

urlpatterns = [
    path('favicon.ico', webapp.favicon, name='favicon'),
    path('apple-touch-icon.png', webapp.apple_touch_icon, name='apple_touch_icon'),
    path('apple-touch-icon-precomposed.png', webapp.apple_touch_icon),
    path('manifest.webmanifest', webapp.manifest, name='webapp_manifest'),
    path('', views.home, name='home'),
    path('pricing', TemplateView.as_view(template_name='pricing.html'), name='pricing'),
    path('contacts', TemplateView.as_view(template_name='contacts.html'), name='contacts'),
    path('legal/<slug:slug>', legal_views.document, name='legal_document'),
    path('examples/<slug:slug>', examples.detail, name='example'),
    path('examples/<slug:slug>/qr.png', examples.qr, name='example_qr'),
    path('examples/<slug:slug>/contact.vcf', examples.vcard, name='example_vcard'),
    path('admin/', admin.site.urls),
    path('accounts/register', registration.start, name='register'),
    path('accounts/registration-code', registration.confirm, name='registration_code'),
    path('accounts/registration-code/resend', registration.resend, name='registration_code_resend'),
    path('accounts/login', accounts.SessionLoginView.as_view(template_name='accounts/login.html', authentication_form=LoginForm), name='login'),
    path('accounts/logout', accounts.SessionLogoutView.as_view(), name='logout'),
    path('accounts/verify/<str:token>', accounts.verify, name='verify'),
    path('accounts/resend', accounts.resend, name='resend'),
    path('accounts/password-reset', password_reset.request_reset, name='password_reset'),
    path('accounts/password-reset/sent', TemplateView.as_view(template_name='accounts/password_reset_sent.html'), name='password_reset_sent'),
    path('accounts/password-reset/<str:token>', password_reset.confirm_reset, name='password_reset_confirm'),
    path('app/cards', views.dashboard, name='dashboard'),
    path('app/subscription', billing.index, name='subscription'),
    path('app/subscription/checkout', billing.checkout, name='checkout'),
    path('app/subscription/promo', billing.redeem_promo, name='redeem_promo'),
    path('app/payments/<uuid:pk>', billing.detail, name='payment_detail'),
    path('app/payments/<uuid:pk>/check', billing.check, name='payment_check'),
    path('app/payments/<uuid:pk>/status', billing.status, name='payment_status'),
    path('payments/yookassa/notification', billing.notification, name='payment_notification'),
    path('app/domains', domain_views.index, name='domains'),
    path('app/domains/<uuid:pk>/qr.png', domain_views.qr, name='domain_qr'),
    path('app/domains/<uuid:pk>/target', domain_views.target, name='domain_target'),
    path('app/domains/<uuid:pk>/<str:operation>', domain_views.action, name='domain_action'),
    path('app/physical-cards', physical_views.index, name='physical_index'),
    path('app/physical-cards/<uuid:pk>', physical_views.edit, name='physical_edit'),
    path('app/physical-cards/<uuid:pk>/qr.png', physical_views.qr, name='physical_qr'),
    path('p/<str:public_id>', physical_views.resolve, name='physical_resolve'),
    path('app/cards/<uuid:pk>/edit', views.edit, name='edit'),
    path('app/cards/<uuid:pk>/publish', views.publish, name='publish'),
    path('app/cards/<uuid:pk>/unpublish', views.unpublish, name='unpublish'),
    path('app/cards/<uuid:pk>/delete', views.delete, name='delete'),
    path('app/cards/<uuid:pk>/qr.png', views.qr, name='qr'),
    path('app/assets', asset_views.upload, name='upload_asset'),
    path('app/cards/<uuid:pk>/avatar/remove', asset_views.remove, name='remove_avatar'),
    path('app/cards/<uuid:pk>/assets/<uuid:asset_id>', asset_views.preview, name='preview_asset'),
    path('c/<str:public_id>', views.public, name='public'),
    path('c/<str:public_id>/contact.vcf', views.vcard, name='vcard'),
    path('c/<str:public_id>/qr.png', views.public_qr, name='public_qr'),
    path('c/<str:public_id>/assets/<uuid:asset_id>', asset_views.public, name='public_asset'),
    path('health/live', views.live), path('health/ready', views.ready),
]
