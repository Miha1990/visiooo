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
        self.assertContains(response, 'пока не собирается')

    def test_empty_dashboard_still_allows_card_creation(self):
        self.card.status = 'deleted'; self.card.save()
        self.assertContains(self.client.get('/app/cards'), 'Ваша первая визитка')
        response = self.client.post('/app/cards')
        self.assertEqual(response.status_code, 303)
