"""A webhook hold must stop payment operations at the server, not just the UI."""
import os
import tempfile
import unittest
from unittest.mock import Mock

from domain import Store
from payments import Payments
from webhooks import Webhooks


class PaymentHoldAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(os.path.join(self.tmp.name, 'db'))
        self.customer = {'id': 'synthetic-customer', 'role': 'customer'}
        self.caterer = {'id': 'synthetic-caterer', 'role': 'caterer'}
        event = self.store.event(self.customer, 'Synthetic dinner', 20, 'Test only')
        self.quote = self.store.quote(self.caterer, event, '25.00')
        self.store.approve(self.customer, self.quote)
        self.store.bind(self.customer, self.quote, 'ORDER1')
        self.receipt = {
            'id': 'ORDER1', 'status': 'COMPLETED', 'purchase_units': [{
                'custom_id': self.quote, 'payee': {'merchant_id': 'MERCHANT1'},
                'payments': {'captures': [{
                    'id': 'CAPTURE1', 'status': 'COMPLETED',
                    'amount': {'currency_code': 'USD', 'value': '500.00'},
                }]},
            }],
        }
        self.provider = Mock(merchant='MERCHANT1', configured=True)
        self.provider.order.return_value = self.receipt
        self.payments = Payments(self.store, self.provider)

    def tearDown(self):
        self.tmp.cleanup()

    def hold(self, kind='PAYMENT.CAPTURE.PENDING'):
        Webhooks(self.store, self.provider).handle({
            'id': 'HOLD1', 'event_type': kind, 'resource': {
                'id': 'CAPTURE1',
                'supplementary_data': {'related_ids': {'order_id': 'ORDER1'}},
            },
        }, {})
        self.provider.reset_mock()

    def assert_held(self):
        quote = self.store.list(self.customer)[0]['quotes'][0]
        self.assertEqual(quote['payment_status'], 'REVIEW_REQUIRED')
        self.assertEqual(quote['booked'], 0)

    def test_pending_webhook_prevents_capture_before_provider_call(self):
        self.hold()
        with self.assertRaisesRegex(ValueError, 'operator review'):
            self.payments.capture(self.customer, self.quote)
        self.provider.capture.assert_not_called()
        self.provider.order.assert_not_called()
        with self.store.db() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM payment_operations').fetchone()[0], 0)
        self.assert_held()

    def test_held_quote_cannot_start_create_operation(self):
        self.hold('PAYMENT.CAPTURE.DENIED')
        with self.assertRaisesRegex(ValueError, 'operator review'):
            self.payments.create(self.customer, self.quote, 'https://example.invalid/')
        self.provider.create.assert_not_called()
        self.provider.order.assert_not_called()
        self.assert_held()

    def test_completed_create_replay_does_not_return_checkout_after_hold(self):
        self.store.begin_payment_operation(self.customer, self.quote, 'create')
        self.store.finish_payment_operation(self.customer, self.quote, 'create', 'ORDER1')
        self.hold()
        with self.assertRaisesRegex(ValueError, 'operator review'):
            self.payments.create(self.customer, self.quote, 'https://example.invalid/')
        self.provider.create.assert_not_called()
        self.provider.order.assert_not_called()
        with self.store.db() as db:
            self.assertEqual(db.execute('SELECT state FROM payment_operations').fetchone()[0], 'SUCCEEDED')
        self.assert_held()

    def test_completed_capture_replay_respects_later_refund_hold(self):
        self.store.begin_payment_operation(self.customer, self.quote, 'capture')
        self.store.finish_payment_operation(self.customer, self.quote, 'capture', 'ORDER1')
        self.hold('PAYMENT.CAPTURE.REFUNDED')
        with self.assertRaisesRegex(ValueError, 'operator review'):
            self.payments.capture(self.customer, self.quote)
        self.provider.capture.assert_not_called()
        self.provider.order.assert_not_called()
        self.assert_held()
