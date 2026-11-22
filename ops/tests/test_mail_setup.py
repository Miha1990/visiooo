"""Sensitive setup checks: no secret disclosure, no overwrite, TLS before SMTP changes."""
from contextlib import redirect_stdout
import importlib.util
from io import StringIO
from pathlib import Path
import smtplib
import subprocess
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch


def module(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).resolve().parents[1]/'mail'/f'{name}.py')
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


initialize = module('init')
connect = module('connect')


class MailSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root/'ops/mail').mkdir(parents=True)
        (self.root/'app').mkdir()
        self.target = self.root/'app/.env'
        self.original = 'SECRET_KEY=keep-this-value\nEMAIL_HOST=old.example\nEMAIL_HOST=duplicate.example\nYOOKASSA_ENABLED=false\n'
        self.target.write_text(self.original, encoding='utf-8')

    def prepare(self):
        output = StringIO()
        with patch.object(initialize.subprocess, 'run', return_value=SimpleNamespace(stdout='$6$salt$hash\n')) as run:
            with redirect_stdout(output):
                initialize.main(self.root)
        values = connect.read_values(self.root/'ops/mail/.env')
        for call in run.call_args_list:
            self.assertEqual(call.args[0], ['openssl', 'passwd', '-6', '-stdin'])
            self.assertNotIn(call.kwargs['input'].strip(), output.getvalue())
        self.assertNotEqual(values['MAILBOX_PASSWORD'], values['SERVICE_MAILBOX_PASSWORD'])
        self.assertEqual(len(values['ROUNDCUBE_DES_KEY']), 24)
        return values

    def test_initialization_preserves_existing_credentials(self):
        self.prepare()
        secret_file = self.root/'ops/mail/.env'
        before = secret_file.read_bytes()
        with self.assertRaises(SystemExit):
            initialize.main(self.root)
        self.assertEqual(secret_file.read_bytes(), before)
        accounts = (self.root/'mail-data/config/postfix-accounts.cf').read_text()
        self.assertIn('support@visiooo.ru|{SHA512-CRYPT}$6$', accounts)

    def test_hash_failure_writes_no_partial_credentials(self):
        with patch.object(initialize.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, 'openssl')):
            with self.assertRaises(subprocess.CalledProcessError):
                initialize.main(self.root)
        self.assertFalse((self.root/'ops/mail/.env').exists())
        self.assertFalse((self.root/'mail-data/config/postfix-accounts.cf').exists())

    def test_failed_authentication_preserves_application_configuration(self):
        self.prepare()
        with patch.object(connect.smtplib, 'SMTP') as smtp:
            smtp.return_value.__enter__.return_value.login.side_effect = smtplib.SMTPAuthenticationError(535, b'no')
            with self.assertRaises(smtplib.SMTPAuthenticationError):
                connect.main(self.root)
        self.assertEqual(self.target.read_text(), self.original)
        self.assertFalse((self.root/'backups').exists())

    def test_success_uses_tls_before_auth_and_preserves_other_settings(self):
        values = self.prepare()
        with patch.object(connect.smtplib, 'SMTP') as smtp, redirect_stdout(StringIO()):
            session = smtp.return_value.__enter__.return_value
            connect.main(self.root)
            self.assertEqual([call[0] for call in session.method_calls], ['ehlo', 'starttls', 'ehlo', 'login'])
            context = session.starttls.call_args.kwargs['context']
            self.assertTrue(context.check_hostname)
        configured = connect.read_values(self.target)
        self.assertEqual(configured['SECRET_KEY'], 'keep-this-value')
        self.assertEqual(configured['YOOKASSA_ENABLED'], 'false')
        self.assertEqual(configured['EMAIL_HOST_PASSWORD'], values['SERVICE_MAILBOX_PASSWORD'])
        self.assertEqual(self.target.read_text(encoding='utf-8').count('EMAIL_HOST='), 1)
        backups = list((self.root/'backups').glob('*.bak'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), self.original)


if __name__ == '__main__':
    unittest.main()
