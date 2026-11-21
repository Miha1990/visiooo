from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
import uuid
from django.test import SimpleTestCase, override_settings
from domains import nginx


@override_settings(DOMAIN_UPSTREAM_PORT=8000, STATIC_ROOT='/opt/myqr/app/staticfiles',
                   DOMAIN_ACME_EMAIL='admin@example.com')
class DomainNginxTests(SimpleTestCase):
    def setUp(self):
        self.binding = SimpleNamespace(pk=uuid.uuid4(), hostname='anna.example.com')

    def test_configs_are_isolated_and_use_bounded_trusted_paths(self):
        config = nginx.config(self.binding, https=True)
        self.assertIn('server_name anna.example.com;', config)
        self.assertIn('proxy_pass http://127.0.0.1:8000;', config)
        self.assertIn(f'myqr-{self.binding.pk}/fullchain.pem', config)
        self.assertIn('location ^~ /.well-known/acme-challenge/', config)
        self.assertNotIn('spch', config.lower())
        self.binding.hostname = 'x.example.com; include /etc/passwd'
        with self.assertRaises(Exception):
            nginx.config(self.binding)

    def test_conflicting_spch_or_unmanaged_host_is_detected(self):
        dump = '# configuration file /etc/nginx/conf.d/spch-existing.conf:\nserver_name anna.example.com;\n'
        self.assertTrue(nginx.conflicting_config(dump, 'anna.example.com', '/etc/nginx/conf.d/myqr-domain.conf'))
        self.assertFalse(nginx.conflicting_config(dump, 'other.example.com', '/etc/nginx/conf.d/myqr-domain.conf'))
        multiline = '# configuration file /etc/nginx/conf.d/spch.conf:\nserver_name\n  www.example.com\n  *.example.com;\n'
        self.assertTrue(nginx.conflicting_config(multiline, 'anna.example.com', '/etc/nginx/conf.d/myqr-domain.conf'))

    def test_failed_nginx_test_restores_previous_file(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'myqr.conf'
            previous = nginx.MARKER + 'old config'
            path.write_text(previous, encoding='utf-8')
            with patch('domains.nginx.command', side_effect=[RuntimeError('invalid'), '', '']):
                with self.assertRaises(RuntimeError):
                    nginx.apply_config(path, nginx.MARKER + 'new config')
            self.assertEqual(path.read_text(encoding='utf-8'), previous)

    def test_unmanaged_file_is_not_overwritten(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'other.conf'
            path.write_text('# maintained by SPCh', encoding='utf-8')
            with patch('domains.nginx.command') as command, self.assertRaises(RuntimeError):
                nginx.apply_config(path, nginx.MARKER + 'new')
            command.assert_not_called()
            self.assertEqual(path.read_text(encoding='utf-8'), '# maintained by SPCh')

    def test_certbot_uses_argument_array_and_separate_certificate_name(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(nginx, 'NGINX_DIR', root), patch.object(nginx, 'WEBROOT', root / 'acme'), \
                 patch('domains.nginx.command', return_value='') as command, \
                 patch('domains.nginx.apply_config') as apply, \
                 patch('domains.nginx.certificate_expiry', return_value='expiry'):
                self.assertEqual(nginx.provision(self.binding), 'expiry')
            args = next(call.args[0] for call in command.call_args_list if call.args[0][0] == 'certbot')
            self.assertEqual(args[:3], ['certbot', 'certonly', '--webroot'])
            self.assertIn(f'myqr-{self.binding.pk}', args)
            self.assertEqual(args[args.index('-d') + 1], self.binding.hostname)
            self.assertEqual(apply.call_count, 2)
