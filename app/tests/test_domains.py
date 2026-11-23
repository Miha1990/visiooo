import hashlib
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch, Mock
import dns.resolver
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings, Client
from django.urls import reverse
from django.utils import timezone
from accounts.models import User
from workspaces.models import Workspace, Membership
from billing.models import Subscription
from cards.models import Card, Asset
from cards.services import create_card, publish_card
from cards.physical import create_physical
from domains.models import DomainBinding, DomainAudit, DomainWorker
from domains.validation import normalize_hostname
from domains.services import (add_domain, verify_domain, request_certificate, disable_domain,
                              remove_domain, worker_ready, change_target)
from domains.dns import check_dns
from domains.worker import process_one, inspect_active


@override_settings(CUSTOM_DOMAINS_ENABLED=True, DOMAIN_IPV4='8.8.8.8',
                   PUBLIC_BASE_URL='https://platform.example.com', ALLOWED_HOSTS=['testserver', 'localhost'])
class DomainTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('domain@example.test', 'DomainPassword-392!', email_verified_at=timezone.now())
        cls.space = Workspace.objects.create(owner=cls.user)
        Membership.objects.create(user=cls.user, workspace=cls.space)
        Subscription.objects.create(workspace=cls.space, status='active', paid_until=timezone.now() + timedelta(days=30))
        cls.card = create_card(cls.user)
        publish_card(cls.user, cls.card.pk, 1)
        cls.other = User.objects.create_user('other-domain@example.test', 'OtherDomain-294!', email_verified_at=timezone.now())
        cls.other_space = Workspace.objects.create(owner=cls.other)
        Membership.objects.create(user=cls.other, workspace=cls.other_space)
        Subscription.objects.create(workspace=cls.other_space, status='active', paid_until=timezone.now() + timedelta(days=30))
        cls.other_card = create_card(cls.other)
        publish_card(cls.other, cls.other_card.pk, 1)

    def setUp(self):
        self.client.force_login(self.user)

    def binding(self, live=False):
        binding = add_domain(self.user, 'anna.example.com', self.card)
        if live:
            binding.state = 'active'
            binding.verified_at = binding.checked_at = timezone.now()
            binding.certificate_expires_at = timezone.now() + timedelta(days=60)
            binding.save()
        return binding

    def test_normalization_idna_and_invalid_names(self):
        self.assertEqual(normalize_hostname(' Визитка.РФ. '), 'xn--80adpdbm9c.xn--p1ai')
        for value in ('https://example.com', 'example.com/a', 'example.com:443', '*.example.com',
                      'user@example.com', '127.0.0.1', '[::1]', 'localhost', 'foo.local',
                      'foo.invalid', 'bad_name.ru', 'example.com\n.evil.ru', 'foo;bar.com'):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                normalize_hostname(value)

    def test_unique_hostname_quota_and_platform_reserved(self):
        for host in ('platform.example.com', 'sub.platform.example.com'):
            with self.assertRaises(ValidationError):
                add_domain(self.user, host, self.card)
        self.binding()
        with self.assertRaises(ValidationError):
            add_domain(self.user, 'second.example.com', self.card)
        with self.assertRaises(ValidationError):
            add_domain(self.other, 'anna.example.com', self.other_card)

    def test_card_ownership_and_action_ownership(self):
        from django.http import Http404
        with self.assertRaises(Http404):
            add_domain(self.user, 'anna.example.com', self.other_card)
        binding = self.binding()
        self.client.force_login(self.other)
        for operation in ('verify', 'certificate', 'disable', 'remove'):
            self.assertEqual(self.client.post(reverse('domain_action', args=[binding.pk, operation])).status_code, 404)
        self.assertEqual(self.client.get(reverse('domain_qr', args=[binding.pk])).status_code, 404)

    def test_token_is_hashed_and_rotates_after_disable(self):
        binding = self.binding(live=True)
        token, digest = binding.verification_token, binding.verification_token_hash
        self.assertEqual(hashlib.sha256(token.encode()).hexdigest(), digest)
        self.assertNotIn(token, str(binding.__dict__))
        disable_domain(self.user, binding.pk)
        binding.refresh_from_db()
        self.assertNotEqual(binding.verification_token, token)
        self.assertIsNone(binding.verified_at)
        self.assertFalse(binding.routable)
        remove_domain(self.user, binding.pk)
        replacement = self.binding()
        self.assertNotEqual(replacement.verification_token, token)
        self.assertTrue(DomainAudit.objects.filter(action='removed').exists())

    def test_retarget_uses_only_own_card_and_preserves_dns_certificate(self):
        from django.http import Http404
        binding = self.binding(live=True)
        old_generation = binding.generation
        other_own = create_card(self.user)
        with self.assertRaises(Http404):
            change_target(self.user, binding.pk, self.other_card, old_generation)
        change_target(self.user, binding.pk, other_own, old_generation)
        binding.refresh_from_db()
        self.assertTrue(binding.routable)
        self.assertEqual(binding.root_card_id, other_own.pk)
        self.assertEqual(self.client.get('/', HTTP_HOST=binding.hostname).status_code, 404)
        publish_card(self.user, other_own.pk, 1)
        self.assertEqual(self.client.get('/', HTTP_HOST=binding.hostname).status_code, 200)
        with self.assertRaises(ValidationError):
            change_target(self.user, binding.pk, self.card, old_generation)

    def test_dns_requires_txt_all_a_and_no_aaaa_with_bounded_resolver(self):
        binding = self.binding()
        def answer(name, kind, **kwargs):
            if kind == 'TXT':
                token = binding.verification_token.encode()
                return [SimpleNamespace(strings=(token[:20], token[20:]))]
            if kind == 'A':
                return ['8.8.8.8']
            raise dns.resolver.NoAnswer
        resolver = Mock()
        resolver.resolve.side_effect = answer
        with patch('domains.dns.dns.resolver.Resolver', return_value=resolver):
            self.assertTrue(check_dns(binding))
            self.assertEqual(resolver.lifetime, 3)
            resolver.resolve.side_effect = lambda name, kind, **kw: (
                [SimpleNamespace(strings=(b'wrong-token',))] if kind == 'TXT' else ['8.8.8.8'])
            self.assertFalse(check_dns(binding))
            resolver.resolve.side_effect = dns.resolver.LifetimeTimeout
            self.assertFalse(check_dns(binding))

    def test_dns_rejects_extra_foreign_address_and_ipv6(self):
        binding = self.binding()
        for ipv4, ipv6 in ((['8.8.8.8', '1.1.1.1'], []), (['8.8.8.8'], ['2001:4860:4860::8888'])):
            def answer(name, kind, **kwargs):
                if kind == 'TXT':
                    return [SimpleNamespace(strings=(binding.verification_token.encode(),))]
                if kind == 'A':
                    return ipv4
                if ipv6:
                    return ipv6
                raise dns.resolver.NoAnswer
            resolver = Mock()
            resolver.resolve.side_effect = answer
            with patch('domains.dns.dns.resolver.Resolver', return_value=resolver):
                self.assertFalse(check_dns(binding))

    def test_failed_reverification_removes_public_access(self):
        binding = self.binding(live=True)
        DomainBinding.objects.filter(pk=binding.pk).update(checked_at=timezone.now() - timedelta(minutes=1))
        with patch('domains.services.check_dns', return_value=False):
            self.assertFalse(verify_domain(self.user, binding.pk))
        binding.refresh_from_db()
        self.assertIsNone(binding.verified_at)
        self.assertEqual(self.client.get('/', HTTP_HOST=binding.hostname).status_code, 404)

    def test_root_and_workspace_public_routes_only(self):
        binding = self.binding(live=True)
        response = self.client.get('/', HTTP_HOST=binding.hostname)
        self.assertEqual(response.status_code, 200)
        self.assertIn('no-store', response['Cache-Control'])
        for suffix in ('', '/contact.vcf', '/qr.png'):
            self.assertEqual(self.client.get(f'/c/{self.card.public_id}{suffix}', HTTP_HOST=binding.hostname).status_code, 200)
            self.assertEqual(self.client.get(f'/c/{self.other_card.public_id}{suffix}', HTTP_HOST=binding.hostname).status_code, 404)
        for path in ('/accounts/login', '/accounts/register', '/app/cards', '/app/domains', '/app/menu', '/app/analytics', '/admin/', '/health/ready'):
            self.assertEqual(self.client.get(path, HTTP_HOST=binding.hostname).status_code, 404)

    def test_physical_carriers_are_scoped_to_domain_workspace(self):
        binding = self.binding(live=True)
        own = create_physical(self.user, 'Own', self.card)
        foreign = create_physical(self.other, 'Foreign', self.other_card)
        self.assertEqual(self.client.get('/p/' + own.public_id, HTTP_HOST=binding.hostname).status_code, 302)
        self.assertEqual(self.client.get('/p/' + foreign.public_id, HTTP_HOST=binding.hostname).status_code, 404)

    def test_unknown_inactive_expired_and_blocked_domains(self):
        self.assertEqual(self.client.get('/', HTTP_HOST='unknown.example.com').status_code, 400)
        binding = self.binding()
        self.assertEqual(self.client.get('/', HTTP_HOST=binding.hostname).status_code, 404)
        binding.state = 'active'
        binding.verified_at = timezone.now()
        binding.certificate_expires_at = timezone.now() - timedelta(seconds=1)
        binding.save()
        self.assertFalse(binding.routable)
        binding.certificate_expires_at = timezone.now() + timedelta(days=1)
        binding.verified_at = timezone.now() - timedelta(days=3)
        binding.save()
        self.assertFalse(binding.routable)
        binding.verified_at = timezone.now()
        binding.blocked = True
        binding.save()
        self.assertEqual(self.client.get('/', HTTP_HOST=binding.hostname).status_code, 404)
        for fn in (verify_domain, disable_domain, remove_domain):
            with self.assertRaises(ValidationError):
                fn(self.user, binding.pk)

    def test_subscription_unpublish_and_delete_close_custom_domain(self):
        binding = self.binding(live=True)
        Subscription.objects.filter(workspace=self.space).update(paid_until=timezone.now() - timedelta(seconds=1))
        for suffix in ('', f'c/{self.card.public_id}/contact.vcf', f'c/{self.card.public_id}/qr.png'):
            self.assertEqual(self.client.get('/' + suffix, HTTP_HOST=binding.hostname).status_code, 404)
        Subscription.objects.filter(workspace=self.space).update(paid_until=timezone.now() + timedelta(days=1))
        Card.objects.filter(pk=self.card.pk).update(status='draft')
        self.assertEqual(self.client.get('/', HTTP_HOST=binding.hostname).status_code, 404)
        Card.objects.filter(pk=self.card.pk).update(status='deleted')
        self.assertEqual(self.client.get('/', HTTP_HOST=binding.hostname).status_code, 404)

    def test_certificate_requires_dns_worker_and_published_paid_card(self):
        binding = self.binding()
        with self.assertRaises(ValidationError):
            request_certificate(self.user, binding.pk)
        binding.verified_at = timezone.now()
        binding.state = 'verified'
        binding.save()
        with self.assertRaises(ValidationError):
            request_certificate(self.user, binding.pk)
        DomainWorker.objects.create(pk=1, heartbeat_at=timezone.now())
        request_certificate(self.user, binding.pk)
        binding.refresh_from_db()
        self.assertEqual(binding.state, 'queued')
        with self.assertRaises(ValidationError):
            request_certificate(self.user, binding.pk)

    def test_worker_success_and_disabled_during_issuance_not_reactivated(self):
        binding = self.binding()
        DomainBinding.objects.filter(pk=binding.pk).update(state='queued', requested_at=timezone.now())
        expiry = timezone.now() + timedelta(days=60)
        with patch('domains.worker.check_dns', return_value=True), patch('domains.worker.nginx.provision', return_value=expiry):
            process_one()
        binding.refresh_from_db()
        self.assertTrue(binding.routable)
        self.assertTrue(worker_ready())
        DomainBinding.objects.filter(pk=binding.pk).update(state='queued')
        def cancelled(job):
            disable_domain(self.user, job.pk)
            return expiry
        with patch('domains.worker.check_dns', return_value=True), patch('domains.worker.nginx.provision', side_effect=cancelled):
            process_one()
        binding.refresh_from_db()
        self.assertEqual(binding.state, 'disabled')
        self.assertFalse(binding.routable)

    def test_periodic_dns_or_tls_failure_closes_domain(self):
        binding = self.binding(live=True)
        DomainBinding.objects.filter(pk=binding.pk).update(checked_at=timezone.now() - timedelta(hours=7))
        with patch('domains.worker.check_dns', return_value=False), self.assertLogs('domains.worker', level='ERROR'):
            inspect_active()
        binding.refresh_from_db()
        self.assertEqual(binding.state, 'error')
        self.assertFalse(binding.routable)

    def test_forms_csrf_and_qr_use_custom_url(self):
        response = self.client.get('/app/domains')
        self.assertContains(response, 'Свой домен')
        browser = Client(enforce_csrf_checks=True)
        browser.force_login(self.user)
        self.assertEqual(browser.post('/app/domains', {}).status_code, 403)
        binding = self.binding(live=True)
        self.assertEqual(browser.post(reverse('domain_action', args=[binding.pk, 'disable']), {}).status_code, 403)
        response = self.client.get('/app/domains')
        self.assertContains(response, binding.verification_token)
        with patch('cards.views.qrcode.make') as make:
            self.client.get(reverse('domain_qr', args=[binding.pk]))
            self.assertEqual(make.call_args.args[0], f'https://{binding.hostname}/')
