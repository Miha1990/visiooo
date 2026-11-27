from django.test import TestCase, Client
from accounts.models import User
from cards.services import create_card, publish_card
from workspaces.models import Workspace, Membership
from tests import test_visual_editor as fixtures


class ClientDashboardTests(TestCase):
    setUp = fixtures.VisualEditorTests.setUp

    def test_dashboard_has_cover_six_actions_and_bottom_navigation(self):
        response = self.client.get('/app/cards')
        self.assertContains(response, 'client-profile')
        for label in ('Показать<br>QR-код', 'Отправить<br>визитку', 'Редактировать<br>визитку',
                      'Посмотреть<br>визитку', 'Привязать<br>QR / NFC', 'Навигация кабинета'):
            self.assertContains(response, label)
        self.assertContains(response, f'/app/cards/{self.card.pk}/edit?view=preview')
        self.assertNotContains(response, '<footer class="footer">')
        self.assertNotContains(response, 'Основная навигация')

    def test_selection_is_scoped_to_account_and_qr_is_private(self):
        other = User.objects.create_user('another@example.test', 'Another-password-39!')
        space = Workspace.objects.create(owner=other)
        Membership.objects.create(workspace=space, user=other)
        foreign = create_card(other)
        response = self.client.get('/app/cards', {'card': foreign.pk})
        self.assertNotContains(response, str(foreign.pk))
        self.assertContains(response, f'/app/cards/{self.card.pk}/qr.png')
        self.assertEqual(self.client.get(f'/app/cards/{foreign.pk}/qr.png').status_code, 404)

    def test_published_card_opens_public_link_and_preview_mode_is_respected(self):
        publish_card(self.user, self.card.pk, self.card.draft_version)
        self.card.refresh_from_db()
        self.assertContains(self.client.get('/app/cards'), f'/c/{self.card.public_id}')
        self.assertContains(self.client.get(f'/app/cards/{self.card.pk}/edit?view=preview'), 'data-view="preview"')

    def test_menu_and_analytics_require_login_and_include_real_information(self):
        guest = Client()
        for path in ('/app/menu', '/app/analytics'):
            self.assertEqual(guest.get(path).status_code, 302)
        response = self.client.get('/app/menu')
        for value in ('Создать визитку', 'Тариф', 'Подписка', 'Мои визитки', 'Привязать свой домен',
                      'Поддержка', 'О приложении', '/legal/privacy', '/legal/offer', '/legal/cookies',
                      'mailto:', 'Выйти', 'method="post"'):
            self.assertContains(response, value)
        response = self.client.get('/app/analytics')
        self.assertEqual(response.context['card_count'], 1)
        self.assertContains(response, 'Просмотры визиток')

    def test_public_preview_has_home_arrow_only_for_card_owner(self):
        publish_card(self.user, self.card.pk, self.card.draft_version)
        url = f'/c/{self.card.public_id}'
        response = self.client.get(url)
        self.assertContains(response, '←</span> На главную')
        self.assertContains(response, f'/app/cards?card={self.card.pk}')
        self.assertNotContains(Client().get(url), 'owner-preview-nav')
        other = User.objects.create_user('viewer@example.test', 'Viewer-password-39!')
        visitor = Client()
        visitor.force_login(other)
        self.assertNotContains(visitor.get(url), 'owner-preview-nav')

    def test_empty_dashboard_still_allows_card_creation(self):
        self.card.status = 'deleted'; self.card.save()
        self.assertContains(self.client.get('/app/cards'), 'Ваша первая визитка')
        response = self.client.post('/app/cards')
        self.assertEqual(response.status_code, 303)

    def test_delete_confirmation_and_removal_keep_other_cards(self):
        other_card = create_card(self.user)
        publish_card(self.user, self.card.pk, self.card.draft_version)
        url = f'/app/cards/{self.card.pk}/delete'
        self.assertContains(self.client.get('/app/cards'), url)
        response = self.client.get(url)
        self.assertContains(response, 'Отмена, оставить визитку')
        self.assertContains(response, 'csrfmiddlewaretoken')
        self.card.refresh_from_db()
        self.assertEqual(self.card.status, 'published')
        self.assertEqual(self.client.post(url).status_code, 303)
        self.card.refresh_from_db()
        self.assertEqual(self.card.status, 'deleted')
        self.assertFalse(self.card.revisions.exists())
        self.assertFalse(self.card.draft)
        self.assertTrue(self.card.reserved_addresses.exists())
        self.assertEqual(self.client.get(f'/c/{self.card.public_id}').status_code, 404)
        self.assertNotContains(self.client.get('/app/cards'), url)
        other_card.refresh_from_db()
        self.assertEqual(other_card.status, 'draft')
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.status, 'active')

    def test_delete_is_private_and_requires_csrf(self):
        url = f'/app/cards/{self.card.pk}/delete'
        stranger = User.objects.create_user('delete-other@example.test', 'Another-password-39!')
        space = Workspace.objects.create(owner=stranger)
        Membership.objects.create(workspace=space, user=stranger)
        foreign_client = Client()
        foreign_client.force_login(stranger)
        for method in ('get', 'post'):
            self.assertEqual(getattr(foreign_client, method)(url).status_code, 404)
            self.assertEqual(getattr(Client(), method)(url).status_code, 302)
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.user)
        self.assertEqual(protected.post(url).status_code, 403)
        protected.get(url)
        self.assertEqual(protected.post(url, {'csrfmiddlewaretoken': protected.cookies['csrftoken'].value}).status_code, 303)
