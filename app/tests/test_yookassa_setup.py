from io import StringIO
from unittest.mock import patch
from django.core.management import call_command, CommandError
from django.test import SimpleTestCase, override_settings
from billing.gateway import GatewayError


@override_settings(DEBUG=False, YOOKASSA_ENABLED=True, YOOKASSA_TEST_MODE=False,
    YOOKASSA_SHOP_ID='1537652', YOOKASSA_SECRET_KEY='secret-must-not-appear',
    LEGAL_LAUNCH_CONFIRMED=True, NPD_RECEIPTS_CONFIRMED=True, PUBLIC_BASE_URL='https://visiooo.ru',
    OPERATOR_INN='615308640848', OPERATOR_ADDRESS='address', DATA_HOSTING_PROVIDER='hosting', DATA_MAIL_PROVIDER='mail')
class YooKassaSetupTests(SimpleTestCase):
    def run_check(self, **options):
        output, errors = StringIO(), StringIO()
        try:
            call_command('check_yookassa', stdout=output, stderr=errors, **options)
        except CommandError as error:
            return False, output.getvalue() + errors.getvalue() + str(error)
        return True, output.getvalue() + errors.getvalue()

    @patch('billing.gateway.request')
    def test_offline_check_does_not_access_api_or_print_secret(self, api):
        ok, text = self.run_check()
        self.assertTrue(ok)
        api.assert_not_called()
        self.assertNotIn('secret-must-not-appear', text)

    @patch('billing.gateway.request', return_value={'account_id': '1537652', 'test': False, 'status': 'enabled'})
    def test_api_check_only_reads_settings(self, api):
        self.assertTrue(self.run_check(api=True)[0])
        api.assert_called_once_with('GET', 'me')

    @patch('billing.gateway.request')
    def test_rejects_wrong_shop_mode_and_disabled_shop(self, api):
        for account in ({'account_id': 'other', 'test': False}, {'account_id': '1537652', 'test': True},
                        {'account_id': '1537652', 'test': False, 'status': 'disabled'}):
            api.return_value = account
            self.assertFalse(self.run_check(api=True)[0])

    @override_settings(YOOKASSA_SECRET_KEY='')
    @patch('billing.gateway.request')
    def test_missing_key_never_calls_api(self, api):
        ok, text = self.run_check(api=True)
        self.assertFalse(ok)
        self.assertIn('YOOKASSA_SECRET_KEY', text)
        api.assert_not_called()

    @patch('billing.gateway.request', side_effect=GatewayError('secret-must-not-appear'))
    def test_api_failure_does_not_expose_exception_content(self, api):
        ok, text = self.run_check(api=True)
        self.assertFalse(ok)
        self.assertNotIn('secret-must-not-appear', text)

    @override_settings(LEGAL_LAUNCH_CONFIRMED=False, NPD_RECEIPTS_CONFIRMED=False, YOOKASSA_ENABLED=False)
    @patch('billing.gateway.request', return_value={'account_id': '1537652', 'test': False})
    def test_can_check_key_before_enabling_real_payments(self, api):
        ok, text = self.run_check(api=True)
        self.assertFalse(ok)
        self.assertIn('LEGAL_LAUNCH_CONFIRMED', text)
        self.assertIn('NPD_RECEIPTS_CONFIRMED', text)
        api.assert_called_once_with('GET', 'me')

    @override_settings(DEBUG=False, YOOKASSA_TEST_MODE=True)
    def test_test_mode_is_rejected_on_public_production(self):
        self.assertFalse(self.run_check()[0])
