from datetime import date, datetime, timezone as datetime_timezone
from unittest.mock import patch
from django.db import DatabaseError
from django.test import Client, TestCase
from django.utils import timezone
from accounts.models import User
from billing.models import Subscription
from cards.analytics import report
from cards.models import CardDailyViews
from cards.services import create_card, publish_card
from workspaces.models import Workspace, Membership
from tests import test_visual_editor as fixtures


class CardAnalyticsTests(TestCase):
    setUp = fixtures.VisualEditorTests.setUp

    def publish(self):
        publish_card(self.user, self.card.pk, self.card.draft_version)
        self.card.refresh_from_db()
        return f'/c/{self.card.public_id}'

    def test_only_public_page_openings_are_counted_and_owner_is_excluded(self):
        url = self.publish()
        visitor = Client()
        self.assertEqual(visitor.get(url).status_code, 200)
        visitor.get(url)
        self.client.get(url)
        visitor.get(url + '/qr.png')
        visitor.get(url + '/contact.vcf')
        self.client.get(f'/app/cards/{self.card.pk}/edit?view=preview')
        self.assertEqual(CardDailyViews.objects.get(card=self.card).views, 2)

    def test_bots_prefetch_and_unavailable_cards_are_not_counted(self):
        url = self.publish(); visitor = Client()
        visitor.get(url, HTTP_USER_AGENT='TelegramBot (like TwitterBot)')
        visitor.get(url, HTTP_SEC_PURPOSE='prefetch;prerender')
        visitor.get(url, HTTP_PURPOSE='prefetch')
        self.card.blocked = True; self.card.save()
        self.assertEqual(visitor.get(url).status_code, 404)
        self.assertFalse(CardDailyViews.objects.exists())

    def test_counter_failure_does_not_break_card(self):
        url = self.publish()
        with patch('cards.analytics.CardDailyViews.objects.get_or_create', side_effect=DatabaseError), self.assertLogs('cards.analytics', level='WARNING'):
            self.assertEqual(Client().get(url).status_code, 200)

    def test_counter_uses_moscow_day_even_with_another_active_timezone(self):
        url = self.publish()
        Subscription.objects.filter(workspace=self.space).update(paid_until=datetime(2030, 1, 1, tzinfo=datetime_timezone.utc))
        with timezone.override('UTC'), patch('django.utils.timezone.now', return_value=datetime(2026, 11, 23, 21, 15, tzinfo=datetime_timezone.utc)):
            Client().get(url)
        self.assertEqual(CardDailyViews.objects.get().day, date(2026, 11, 24))

    def test_daily_and_weekly_reports_include_zeros_and_cross_year_boundary(self):
        CardDailyViews.objects.create(card=self.card, day=date(2025, 12, 31), views=4)
        CardDailyViews.objects.create(card=self.card, day=date(2026, 1, 1), views=6)
        CardDailyViews.objects.create(card=self.card, day=date(2026, 1, 2), views=500)
        days = report([self.card], 'day', date(2026, 1, 1))
        self.assertEqual(len(days['rows']), 30)
        self.assertEqual(days['total_views'], 10)
        self.assertEqual(days['rows'][-1]['views'], 6)
        self.assertEqual(days['rows'][0]['views'], 0)
        weeks = report([self.card], 'week', date(2026, 1, 1))
        self.assertEqual(len(weeks['rows']), 12)
        self.assertEqual(weeks['rows'][-1]['views'], 10)
        self.assertEqual(weeks['rows'][-1]['label'], '29.12.2025 — 01.01.2026')

    def test_monthly_report_sums_cards_and_handles_leap_year(self):
        second = create_card(self.user)
        CardDailyViews.objects.create(card=self.card, day=date(2024, 2, 29), views=2)
        CardDailyViews.objects.create(card=second, day=date(2024, 2, 1), views=3)
        CardDailyViews.objects.create(card=self.card, day=date(2023, 2, 1), views=999)
        months = report([self.card, second], 'month', date(2024, 2, 29))
        self.assertEqual(len(months['rows']), 12)
        self.assertEqual(months['start'], date(2023, 3, 1))
        self.assertEqual(months['rows'][-1]['views'], 5)
        self.assertEqual(months['total_views'], 5)

    def test_statistics_and_card_filter_are_private(self):
        other = User.objects.create_user('stats-other@example.test', 'Stats-Password-39!')
        space = Workspace.objects.create(owner=other); Membership.objects.create(workspace=space, user=other)
        foreign = create_card(other)
        CardDailyViews.objects.create(card=foreign, day=timezone.localdate(), views=999)
        response = self.client.get('/app/analytics')
        self.assertEqual(response.context['total_views'], 0)
        self.assertEqual(self.client.get('/app/analytics', {'card': foreign.pk}).status_code, 404)
        self.assertEqual(self.client.get('/app/analytics', {'card': 'broken'}).status_code, 404)
        self.assertEqual(Client().get('/app/analytics').status_code, 302)
        self.assertEqual(self.client.get('/app/analytics', {'period': 'broken'}).context['period'], 'day')

    def test_single_card_filter_excludes_other_owned_cards(self):
        second = create_card(self.user)
        CardDailyViews.objects.create(card=self.card, day=timezone.localdate(), views=2)
        CardDailyViews.objects.create(card=second, day=timezone.localdate(), views=3)
        self.assertEqual(self.client.get('/app/analytics').context['total_views'], 5)
        response = self.client.get('/app/analytics', {'card': self.card.pk, 'period': 'month'})
        self.assertEqual(response.context['total_views'], 2)
        self.assertContains(response, 'Дни')
        self.assertContains(response, 'Месяцы')
