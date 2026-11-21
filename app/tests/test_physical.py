from datetime import timedelta
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.http import Http404
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from billing.models import Subscription
from workspaces.models import Workspace, Membership
from cards.models import Card, PhysicalCard, PhysicalCardEvent
from cards.physical import create_physical, update_physical, physical_url
from cards.services import create_card, publish_card, Conflict


@override_settings(PUBLIC_BASE_URL='https://cards.example.com')
class PhysicalCardTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('physical@example.test', 'PhysicalPassword-294!', email_verified_at=timezone.now())
        self.space = Workspace.objects.create(owner=self.user)
        Membership.objects.create(user=self.user, workspace=self.space)
        self.sub = Subscription.objects.create(workspace=self.space, status='active',
                                               paid_until=timezone.now() + timedelta(days=1))
        self.first = create_card(self.user)
        self.second = create_card(self.user)
        publish_card(self.user, self.first.pk, 1)
        publish_card(self.user, self.second.pk, 1)
        self.client.force_login(self.user)
        self.item = create_physical(self.user, 'Моя NFC-карточка', self.first)
        self.url = reverse('physical_resolve', args=[self.item.public_id])

    def test_resolve_rebind_stable_qr_and_event_history(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('public', args=[self.first.public_id]))
        self.assertIn('no-store', response['Cache-Control'])
        before = self.client.get(reverse('physical_qr', args=[self.item.pk])).content
        fixed_url = physical_url(self.item)
        update_physical(self.user, self.item.pk, 1, 'Другая подпись', self.second)
        self.item.refresh_from_db()
        self.assertEqual(physical_url(self.item), fixed_url)
        self.assertEqual(self.client.get(self.url)['Location'], reverse('public', args=[self.second.public_id]))
        self.assertEqual(self.client.get(reverse('physical_qr', args=[self.item.pk])).content, before)
        self.assertEqual(PhysicalCardEvent.objects.filter(physical_card=self.item).count(), 2)

    def test_disabled_unbound_blocked_and_expired_cannot_resolve(self):
        for change in ({'enabled': False}, {'card': None}, {'blocked': True}):
            PhysicalCard.objects.filter(pk=self.item.pk).update(**change)
            self.assertEqual(self.client.get(self.url).status_code, 404)
            PhysicalCard.objects.filter(pk=self.item.pk).update(enabled=True, blocked=False, card=self.first)
        self.sub.paid_until = timezone.now() - timedelta(seconds=1)
        self.sub.save()
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_target_hidden_deleted_or_blocked_cannot_resolve(self):
        for change in ({'status': 'draft'}, {'status': 'deleted'}, {'blocked': True}):
            Card.objects.filter(pk=self.first.pk).update(**change)
            self.assertEqual(self.client.get(self.url).status_code, 404)
            Card.objects.filter(pk=self.first.pk).update(status='published', blocked=False)

    def test_ownership_and_foreign_card_assignment(self):
        other = User.objects.create_user('physical-other@example.test', 'OtherPhysical-284!')
        space = Workspace.objects.create(owner=other)
        Membership.objects.create(user=other, workspace=space)
        Subscription.objects.create(workspace=space)
        foreign = create_card(other)
        with self.assertRaises(Http404):
            update_physical(self.user, self.item.pk, 1, 'Bad', foreign)
        response = self.client.post(reverse('physical_edit', args=[self.item.pk]), {
            'version': 1, 'label': 'Bad', 'card': foreign.pk, 'enabled': 'on'})
        self.assertEqual(response.status_code, 422)
        self.client.force_login(other)
        for path in (reverse('physical_edit', args=[self.item.pk]), reverse('physical_qr', args=[self.item.pk])):
            self.assertEqual(self.client.get(path).status_code, 404)
        self.assertEqual(self.client.post(reverse('physical_edit', args=[self.item.pk]), {}).status_code, 404)
        # Even inconsistent privileged data must never expose another workspace.
        PhysicalCard.objects.filter(pk=self.item.pk).update(card=foreign)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_stale_bind_does_not_overwrite_and_admin_block_is_not_bypassed(self):
        update_physical(self.user, self.item.pk, 1, 'New', self.second)
        with self.assertRaises(Conflict):
            update_physical(self.user, self.item.pk, 1, 'Old', self.first)
        response = self.client.post(reverse('physical_edit', args=[self.item.pk]), {
            'version': 1, 'label': 'Old', 'card': self.first.pk, 'enabled': 'on'})
        self.assertEqual(response.status_code, 409)
        PhysicalCard.objects.filter(pk=self.item.pk).update(blocked=True)
        with self.assertRaises(ValidationError):
            update_physical(self.user, self.item.pk, 2, 'New', self.first)

    def test_csrf_and_get_do_not_bind(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(reverse('physical_edit', args=[self.item.pk]), {}).status_code, 403)
        self.assertEqual(client.post(reverse('physical_index'), {}).status_code, 403)
        self.assertEqual(self.client.get(reverse('physical_edit', args=[self.item.pk])).status_code, 200)
        self.item.refresh_from_db()
        self.assertEqual(self.item.version, 1)

    def test_create_and_unbind_via_owner_forms(self):
        response = self.client.post(reverse('physical_index'), {
            'label': 'Новая карточка', 'card': self.first.pk, 'enabled': 'on'})
        self.assertEqual(response.status_code, 303)
        item = PhysicalCard.objects.get(label='Новая карточка')
        response = self.client.post(reverse('physical_edit', args=[item.pk]), {
            'label': item.label, 'card': '', 'enabled': 'on', 'version': item.version})
        self.assertEqual(response.status_code, 303)
        self.assertEqual(self.client.get(reverse('physical_resolve', args=[item.public_id])).status_code, 404)

    def test_public_qr_only_published_and_same_url_as_owner_qr(self):
        url = reverse('public_qr', args=[self.first.public_id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(response.content, self.client.get(reverse('qr', args=[self.first.pk])).content)
        Card.objects.filter(pk=self.first.pk).update(status='draft')
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_photo_toggle_is_on_public_card_and_owner_preview(self):
        for url in (reverse('public', args=[self.first.public_id]), reverse('edit', args=[self.first.pk])):
            response = self.client.get(url)
            self.assertContains(response, 'data-avatar-toggle')
            self.assertContains(response, 'aria-pressed="false"')
            self.assertContains(response, 'card-interactions.js')

    def test_qr_uses_canonical_physical_url_and_ui_warns_for_local_only(self):
        with patch('cards.views.qrcode.make') as make:
            self.client.get(reverse('physical_qr', args=[self.item.pk]))
            self.assertEqual(make.call_args.args[0], physical_url(self.item))
        with override_settings(PUBLIC_BASE_URL='http://127.0.0.1:8000'):
            response = self.client.get(reverse('physical_edit', args=[self.item.pk]))
            self.assertContains(response, 'data-local-only="true"')
        self.assertContains(self.client.get(reverse('physical_edit', args=[self.item.pk])), 'data-local-only="false"')
