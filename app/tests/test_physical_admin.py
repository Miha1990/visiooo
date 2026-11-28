from django.contrib.admin.models import LogEntry, ADDITION
from django.contrib.auth.models import Permission
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from cards.models import PhysicalCard, PhysicalCardEvent
from cards.physical import physical_url


@override_settings(PUBLIC_BASE_URL='https://visiooo.ru')
class PhysicalCardAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser('physical-admin@example.test')
        cls.staff = User.objects.create_user('physical-staff@example.test', is_staff=True)

    def setUp(self):
        self.client.force_login(self.admin)
        self.add_url = reverse('admin:cards_physicalcard_add')

    def test_admin_home_and_card_list_link_to_native_batch_creation(self):
        response = self.client.get(reverse('admin:index'))
        self.assertContains(response, 'Выпустить карты NFC / QR')
        self.assertContains(response, self.add_url)
        response = self.client.get(reverse('admin:cards_physicalcard_changelist'))
        self.assertContains(response, 'Выпустить ссылки NFC / QR')
        self.assertContains(self.client.get(self.add_url), 'Количество карт')
        response = self.client.post(self.add_url, {'label': 'Партия NFC', 'count': 2})
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response['Location'], self.add_url)
        items = list(PhysicalCard.objects.all())
        self.assertEqual(len(items), 2)
        self.assertTrue(all(item.workspace_id is None and item.card_id is None for item in items))
        self.assertEqual(PhysicalCardEvent.objects.filter(action='issued', actor=self.admin).count(), 2)
        self.assertEqual(LogEntry.objects.filter(user=self.admin, action_flag=ADDITION).count(), 2)
        response = self.client.get(self.add_url)
        for item in items:
            self.assertContains(response, physical_url(item))
            self.assertContains(response, reverse('physical_stock_qr', args=[item.pk]))
        self.assertContains(response, reverse('physical_stock_csv'))
        response = self.client.get(reverse('admin:cards_physicalcard_changelist'))
        self.assertContains(response, 'Ожидает клиента')
        self.assertContains(response, physical_url(items[0]))

    def test_staff_needs_add_permission_and_can_issue_without_workspace(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(self.add_url).status_code, 403)
        self.assertEqual(self.client.post(self.add_url, {'label': 'Forbidden', 'count': 1}).status_code, 403)
        self.assertNotContains(self.client.get(reverse('admin:index')), 'Выпустить карты NFC / QR')
        self.staff.user_permissions.add(Permission.objects.get(content_type__app_label='cards', codename='add_physicalcard'))
        self.assertContains(self.client.get(reverse('admin:index')), 'Выпустить карты NFC / QR')
        self.assertEqual(self.client.post(self.add_url, {'label': 'Staff batch', 'count': 1}).status_code, 303)
        self.assertContains(self.client.get(self.add_url), 'https://visiooo.ru/p/')
        self.assertEqual(PhysicalCard.objects.count(), 1)

    def test_invalid_batch_and_missing_csrf_cannot_create_cards(self):
        self.assertEqual(self.client.post(self.add_url, {'label': 'Too many', 'count': 101}).status_code, 422)
        self.assertEqual(PhysicalCard.objects.count(), 0)
        browser = Client(enforce_csrf_checks=True)
        browser.force_login(self.admin)
        browser.get(self.add_url)
        self.assertEqual(browser.post(self.add_url, {'label': 'No token', 'count': 1}).status_code, 403)
        self.assertEqual(PhysicalCard.objects.count(), 0)
        response = browser.post(self.add_url, {'label': 'With token', 'count': 1,
            'csrfmiddlewaretoken': browser.cookies['csrftoken'].value})
        self.assertEqual(response.status_code, 303)
        self.assertEqual(PhysicalCard.objects.count(), 1)
