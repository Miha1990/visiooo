from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from cards.models import PhysicalCard, PhysicalCardEvent
from cards.physical import activate_physical, issue_physical, physical_url
from cards.services import Conflict, create_card
from workspaces.models import Membership, Workspace
from tests import test_physical as fixtures


@override_settings(PUBLIC_BASE_URL='https://cards.example.com')
class PhysicalActivationTests(TestCase):
    setUp = fixtures.PhysicalCardTests.setUp

    def stock(self):
        return PhysicalCard.objects.create(label='Новая карта')

    def other(self):
        user = User.objects.create_user('another@example.test', 'Another-Password-394!')
        workspace = Workspace.objects.create(owner=user)
        Membership.objects.create(user=user, workspace=workspace)
        return user, workspace

    def test_same_permanent_url_activates_then_opens_the_selected_card(self):
        stock = self.stock()
        permanent = physical_url(stock)
        public = reverse('physical_resolve', args=[stock.public_id])
        activate = reverse('physical_activate', args=[stock.public_id])
        browser = Client()
        response = browser.get(public)
        self.assertEqual(response['Location'], 'https://cards.example.com' + activate)
        response = browser.get(activate)
        self.assertContains(response, 'Войти и привязать карту')
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(browser.session['physical_activation'], stock.public_id)
        stock.refresh_from_db()
        self.assertIsNone(stock.workspace_id)
        self.assertContains(self.client.get(activate), 'Привязать карту')
        stock.refresh_from_db()
        self.assertIsNone(stock.workspace_id)
        response = self.client.post(activate, {'card': self.second.pk})
        self.assertEqual(response.status_code, 303)
        stock.refresh_from_db()
        self.assertEqual(stock.workspace_id, self.space.pk)
        self.assertEqual(stock.card_id, self.second.pk)
        self.assertEqual(physical_url(stock), permanent)
        self.assertEqual(browser.get(public)['Location'], reverse('public', args=[self.second.public_id]))
        self.assertEqual(stock.events.get(action='activated').actor, self.user)
        self.assertEqual(self.client.get(activate)['Location'], reverse('physical_edit', args=[stock.pk]))

    def test_another_customer_cannot_take_an_activated_card(self):
        stock = self.stock()
        activate_physical(self.user, stock.public_id, self.first)
        other, _ = self.other()
        foreign_card = create_card(other)
        self.client.force_login(other)
        url = reverse('physical_activate', args=[stock.public_id])
        response = self.client.post(url, {'card': foreign_card.pk})
        self.assertEqual(response.status_code, 409)
        with self.assertRaises(Conflict):
            activate_physical(other, stock.public_id, foreign_card)
        stock.refresh_from_db()
        self.assertEqual(stock.workspace_id, self.space.pk)
        self.assertEqual(stock.events.filter(action='activated').count(), 1)
        self.assertEqual(self.client.get(reverse('physical_edit', args=[stock.pk])).status_code, 404)

    def test_claim_requires_confirmation_csrf_and_an_owned_card(self):
        stock = self.stock()
        url = reverse('physical_activate', args=[stock.public_id])
        other, _ = self.other()
        foreign = create_card(other)
        self.assertEqual(self.client.post(url, {'card': foreign.pk}).status_code, 422)
        self.assertEqual(self.client.post(url, {}).status_code, 422)
        browser = Client(enforce_csrf_checks=True)
        browser.force_login(self.user)
        self.assertEqual(browser.post(url, {'card': self.first.pk}).status_code, 403)
        browser.get(url)
        self.assertEqual(browser.post(url, {'card': self.first.pk,
            'csrfmiddlewaretoken': browser.cookies['csrftoken'].value}).status_code, 303)
        stock.refresh_from_db()
        self.assertEqual(stock.card_id, self.first.pk)

    def test_new_customer_can_explicitly_create_a_draft_and_activate(self):
        stock = self.stock()
        other, workspace = self.other()
        self.client.force_login(other)
        url = reverse('physical_activate', args=[stock.public_id])
        self.assertContains(self.client.get(url), 'Создать визитку и привязать карту')
        self.assertEqual(workspace.card_set.count(), 0)
        self.assertEqual(self.client.post(url, {}).status_code, 303)
        stock.refresh_from_db()
        self.assertEqual(stock.workspace_id, workspace.pk)
        self.assertEqual(stock.card.status, 'draft')
        self.assertEqual(workspace.card_set.count(), 1)

    def test_disabled_blocked_missing_and_quota_full_cannot_activate(self):
        stock = self.stock()
        for field in ('blocked', 'enabled'):
            PhysicalCard.objects.filter(pk=stock.pk).update(**{field: field == 'blocked'})
            self.assertEqual(self.client.post(reverse('physical_activate', args=[stock.public_id]), {'card': self.first.pk}).status_code, 404)
            PhysicalCard.objects.filter(pk=stock.pk).update(blocked=False, enabled=True)
        self.assertEqual(self.client.get('/activate/not-a-card').status_code, 404)
        PhysicalCard.objects.bulk_create([PhysicalCard(label=f'Owned {i}', workspace=self.space) for i in range(19)])
        self.assertEqual(self.client.post(reverse('physical_activate', args=[stock.public_id]), {'card': self.first.pk}).status_code, 422)
        stock.refresh_from_db()
        self.assertIsNone(stock.workspace_id)

    def test_stock_issuance_exports_and_qr_are_staff_only(self):
        url = reverse('physical_issue')
        self.assertEqual(self.client.get(url).status_code, 403)
        with self.assertRaises(PermissionDenied):
            issue_physical(self.user, 'Партия', 1)
        self.user.is_staff = self.user.is_superuser = True
        self.user.save()
        response = self.client.post(url, {'label': 'Партия', 'count': 2})
        self.assertEqual(response.status_code, 303)
        items = list(PhysicalCard.objects.filter(workspace__isnull=True))
        self.assertEqual(len(items), 2)
        self.assertEqual(len({item.public_id for item in items}), 2)
        self.assertEqual(PhysicalCardEvent.objects.filter(action='issued', actor=self.user).count(), 2)
        response = self.client.get(reverse('physical_stock_csv'))
        self.assertContains(response, physical_url(items[0]))
        self.assertNotContains(response, physical_url(self.item))
        with patch('cards.views.qrcode.make') as make:
            self.client.get(reverse('physical_stock_qr', args=[items[0].pk]))
            self.assertEqual(make.call_args.args[0], physical_url(items[0]))
        self.assertContains(self.client.get(url), 'Ссылка для NFC и QR')
        self.user.is_staff = self.user.is_superuser = False
        self.user.save()
        self.assertEqual(self.client.get(reverse('physical_stock_csv')).status_code, 403)
        self.assertEqual(self.client.get(reverse('physical_stock_qr', args=[items[0].pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse('physical_qr', args=[items[0].pk])).status_code, 404)

    def test_invalid_batch_does_not_issue_cards(self):
        self.user.is_staff = self.user.is_superuser = True
        self.user.save()
        for count in (0, 101):
            self.assertEqual(self.client.post(reverse('physical_issue'), {'label': 'Batch', 'count': count}).status_code, 422)
        self.assertFalse(PhysicalCard.objects.filter(workspace__isnull=True).exists())
