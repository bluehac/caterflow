"""Synthetic receipts only. Recovery must never blindly repeat a provider write."""
import copy
import os
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

from domain import Store
from payments import Payments
from webhooks import Webhooks


class PaymentRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, 'db')
        self.store = Store(self.path)
        self.customer = {'id': 'synthetic-customer', 'role': 'customer'}
        self.caterer = {'id': 'synthetic-caterer', 'role': 'caterer'}
        event = self.store.event(self.customer, 'Synthetic event', 20, 'Test only')
        self.quote = self.store.quote(self.caterer, event, '25.00')
        self.store.approve(self.customer, self.quote)
        self.store.bind(self.customer, self.quote, 'ORDER1')
        self.approved = {
            'id': 'ORDER1', 'status': 'APPROVED', 'intent': 'CAPTURE',
            'purchase_units': [{
                'custom_id': self.quote, 'payee': {'merchant_id': 'MERCHANT1'},
                'amount': {'currency_code': 'USD', 'value': '500.00'},
            }],
        }
        self.completed = copy.deepcopy(self.approved)
        self.completed['status'] = 'COMPLETED'
        self.completed['purchase_units'][0]['payments'] = {'captures': [{
            'id': 'CAPTURE1', 'status': 'COMPLETED',
            'amount': {'currency_code': 'USD', 'value': '500.00'},
        }]}
        self.provider = Mock(configured=True, merchant='MERCHANT1')
        self.provider.order.return_value = self.completed
        self.payments = Payments(self.store, self.provider)

    def tearDown(self):
        self.tmp.cleanup()

    def operations(self):
        with self.store.db() as db:
            return {r['kind']: dict(r) for r in db.execute('SELECT * FROM payment_operations')}

    def state(self):
        return self.store.list(self.customer)[0]['quotes'][0]

    def start(self, kind='capture', uncertain=False):
        operation = self.store.begin_payment_operation(self.customer, self.quote, kind)
        if uncertain:
            self.store.finish_payment_operation(self.customer, self.quote, kind)
        return operation

    def event(self, kind='PAYMENT.CAPTURE.COMPLETED', event_id='EVENT1'):
        return {'id': event_id, 'event_type': kind, 'resource': {
            'id': 'CAPTURE1', 'supplementary_data': {'related_ids': {'order_id': 'ORDER1'}},
        }}

    def hold(self):
        self.store.payment_hold(self.quote, 'HOLD1', 'PAYMENT.CAPTURE.PENDING', self.approved, 'MERCHANT1')

    def test_early_click_then_buyer_approval_can_capture_once(self):
        early = copy.deepcopy(self.approved)
        early['status'] = 'CREATED'
        self.provider.order.side_effect = [early, self.approved, self.completed]
        with self.assertRaises(ValueError):
            self.payments.capture(self.customer, self.quote)
        self.assertEqual(self.operations(), {})
        self.provider.capture.assert_not_called()
        result = self.payments.capture(self.customer, self.quote)
        self.assertEqual(result, {'payment_status': 'COMPLETED', 'booking_status': 'AWAITING_CATERER'})
        self.assertEqual(self.provider.capture.call_count, 1)
        self.assertEqual(self.operations()['capture']['state'], 'SUCCEEDED')

    def test_nonapproved_preflight_never_admits_operation(self):
        for status in ['CREATED', 'PAYER_ACTION_REQUIRED', 'VOIDED', 'PENDING', 'DECLINED', 'CANCELLED']:
            with self.subTest(status=status):
                response = copy.deepcopy(self.approved)
                response['status'] = status
                self.provider.order.return_value = response
                with self.assertRaises(ValueError):
                    self.payments.capture(self.customer, self.quote)
                self.assertEqual(self.operations(), {})
                self.provider.capture.assert_not_called()

    def test_preflight_failure_does_not_poison_journal(self):
        self.provider.order.side_effect = TimeoutError('synthetic read timeout')
        with self.assertRaises(TimeoutError):
            self.payments.capture(self.customer, self.quote)
        self.assertEqual(self.operations(), {})
        self.provider.capture.assert_not_called()

    def test_approved_context_mismatches_prevent_capture(self):
        for mismatch in ['order', 'quote', 'merchant', 'amount', 'currency', 'intent', 'extra_unit', 'capture', 'authorization']:
            with self.subTest(mismatch=mismatch):
                response = copy.deepcopy(self.approved)
                unit = response['purchase_units'][0]
                if mismatch == 'order': response['id'] = 'OTHER'
                if mismatch == 'quote': unit['custom_id'] = 'OTHER'
                if mismatch == 'merchant': unit['payee']['merchant_id'] = 'OTHER'
                if mismatch == 'amount': unit['amount']['value'] = '1.00'
                if mismatch == 'currency': unit['amount']['currency_code'] = 'EUR'
                if mismatch == 'intent': response['intent'] = 'AUTHORIZE'
                if mismatch == 'extra_unit': response['purchase_units'].append(copy.deepcopy(unit))
                if mismatch == 'capture': unit['payments'] = {'captures': [{'id': 'PENDING1', 'status': 'PENDING'}]}
                if mismatch == 'authorization': unit['payments'] = {'authorizations': [{'id': 'AUTH1'}]}
                self.provider.order.return_value = response
                with self.assertRaises(ValueError):
                    self.payments.capture(self.customer, self.quote)
                self.assertEqual(self.operations(), {})
                self.provider.capture.assert_not_called()

    def test_completed_read_reconciles_without_inventing_operation_or_capture(self):
        result = self.payments.capture(self.customer, self.quote)
        self.assertEqual(result['payment_status'], 'COMPLETED')
        self.assertEqual(result['booking_status'], 'AWAITING_CATERER')
        self.provider.capture.assert_not_called()
        self.assertEqual(self.operations(), {})

    def test_uncertain_capture_recovers_across_restart_with_original_request_id(self):
        original = self.start(uncertain=True)
        service = Payments(Store(self.path), self.provider)
        result = service.reconcile(self.customer, self.quote)
        self.assertEqual(result['payment_status'], 'COMPLETED')
        operation = self.operations()['capture']
        self.assertEqual(operation['state'], 'SUCCEEDED')
        self.assertEqual(operation['request_id'], original['request_id'])
        self.assertEqual(operation['provider_id'], 'ORDER1')
        service.capture(self.customer, self.quote)
        self.provider.capture.assert_not_called()

    def test_known_create_and_capture_crash_windows_recover_atomically(self):
        create = self.start('create')
        capture = self.start('capture')
        self.payments.reconcile(self.customer, self.quote)
        for operation in [create, capture]:
            recovered = self.operations()[operation['kind']]
            self.assertEqual(recovered['state'], 'SUCCEEDED')
            self.assertEqual(recovered['request_id'], operation['request_id'])
        with self.store.db() as db:
            actions = [r[0] for r in db.execute("SELECT action FROM audit WHERE action LIKE 'PAYMENT_OPERATION_RECONCILED_%'")]
        self.assertEqual(set(actions), {'PAYMENT_OPERATION_RECONCILED_CREATE', 'PAYMENT_OPERATION_RECONCILED_CAPTURE'})
        self.provider.create.assert_not_called()
        self.provider.capture.assert_not_called()

    def test_approved_read_does_not_reset_uncertain_or_inflight_write(self):
        original = self.start(uncertain=True)
        self.provider.order.return_value = self.approved
        for state in ['UNCERTAIN', 'IN_FLIGHT']:
            with self.store.db() as db:
                db.execute('UPDATE payment_operations SET state=?', (state,))
            with self.assertRaises(ValueError):
                self.payments.capture(self.customer, self.quote)
            self.assertEqual(self.operations()['capture']['state'], state)
            self.assertEqual(self.operations()['capture']['request_id'], original['request_id'])
            self.provider.capture.assert_not_called()

    def test_unknown_order_still_requires_operator_investigation(self):
        with self.store.db() as db:
            db.execute('UPDATE quotes SET order_id=NULL WHERE id=?', (self.quote,))
        original = self.start('create', uncertain=True)
        with self.assertRaises(ValueError):
            self.payments.reconcile(self.customer, self.quote)
        self.provider.order.assert_not_called()
        self.assertEqual(self.operations()['create']['state'], 'UNCERTAIN')
        self.assertEqual(self.operations()['create']['request_id'], original['request_id'])

    def test_invalid_completed_receipt_cannot_resolve_uncertainty(self):
        self.start(uncertain=True)
        wrong = copy.deepcopy(self.completed)
        wrong['purchase_units'][0]['payments']['captures'][0]['amount']['value'] = '1.00'
        self.provider.order.return_value = wrong
        with self.assertRaises(ValueError):
            self.payments.reconcile(self.customer, self.quote)
        self.assertEqual(self.operations()['capture']['state'], 'UNCERTAIN')
        self.assertIsNone(self.state()['capture_id'])

    def test_conflicting_provider_id_rolls_back_payment_and_journal(self):
        self.start(uncertain=True)
        with self.store.db() as db:
            db.execute("UPDATE payment_operations SET provider_id='OTHER'")
        with self.assertRaises(ValueError):
            self.payments.reconcile(self.customer, self.quote)
        self.assertEqual(self.operations()['capture']['provider_id'], 'OTHER')
        self.assertEqual(self.operations()['capture']['state'], 'UNCERTAIN')
        self.assertIsNone(self.state()['capture_id'])

    def test_hold_existing_before_capture_prevents_provider_read(self):
        self.start(uncertain=True)
        self.hold()
        with self.assertRaises(ValueError):
            self.payments.capture(self.customer, self.quote)
        self.provider.order.assert_not_called()
        self.assertEqual(self.operations()['capture']['state'], 'UNCERTAIN')

    def test_hold_during_preflight_prevents_operation_admission(self):
        def read(_):
            self.hold()
            return self.approved
        self.provider.order.side_effect = read
        with self.assertRaises(ValueError):
            self.payments.capture(self.customer, self.quote)
        self.assertEqual(self.operations(), {})
        self.provider.capture.assert_not_called()

    def test_hold_after_admission_is_preserved_when_capture_completes(self):
        self.provider.order.side_effect = [self.approved, self.completed]
        self.provider.capture.side_effect = lambda *a, **kw: self.hold()
        with self.assertRaises(RuntimeError):
            self.payments.capture(self.customer, self.quote)
        self.assertEqual(self.provider.capture.call_count, 1)
        self.assertEqual(self.state()['payment_status'], 'REVIEW_REQUIRED')
        self.assertEqual(self.state()['booked'], 0)
        self.assertEqual(self.operations()['capture']['state'], 'UNCERTAIN')

    def test_webhook_completion_during_capture_is_idempotent(self):
        self.provider.order.side_effect = [self.approved, self.completed, self.completed]
        self.provider.capture.side_effect = lambda *a, **kw: Webhooks(self.store, self.provider).handle(self.event(), {})
        result = self.payments.capture(self.customer, self.quote)
        self.assertEqual(result['payment_status'], 'COMPLETED')
        self.assertEqual(self.operations()['capture']['state'], 'SUCCEEDED')
        self.assertEqual(self.provider.capture.call_count, 1)
        with self.store.db() as db:
            count = db.execute("SELECT count(*) FROM audit WHERE action='PAYMENT_OPERATION_RECONCILED_CAPTURE'").fetchone()[0]
        self.assertEqual(count, 1)

    def test_late_timeout_cannot_downgrade_webhook_verified_success(self):
        self.provider.order.side_effect = [self.approved, self.completed]
        def timeout_after_webhook(*args, **kwargs):
            Webhooks(self.store, self.provider).handle(self.event(), {})
            raise TimeoutError('Synthetic acknowledgement loss')
        self.provider.capture.side_effect = timeout_after_webhook
        with self.assertRaises(RuntimeError):
            self.payments.capture(self.customer, self.quote)
        self.assertEqual(self.operations()['capture']['state'], 'SUCCEEDED')
        self.assertEqual(self.state()['payment_status'], 'COMPLETED')

    def test_finish_success_replay_is_noop_but_conflicting_order_rejected(self):
        self.start()
        self.store.finish_payment_operation(self.customer, self.quote, 'capture', 'ORDER1')
        before = self.operations()['capture']
        self.store.finish_payment_operation(self.customer, self.quote, 'capture', 'ORDER1')
        self.store.finish_payment_operation(self.customer, self.quote, 'capture')
        self.assertEqual(self.operations()['capture'], before)
        with self.assertRaises(ValueError):
            self.store.finish_payment_operation(self.customer, self.quote, 'capture', 'OTHER')

    def test_return_uses_reconciled_booking_state_not_stale_snapshot(self):
        self.store.reconcile(self.customer, self.quote, self.completed, 'MERCHANT1')
        def read(_):
            self.store.book(self.caterer, self.quote)
            return self.completed
        self.provider.order.side_effect = read
        self.assertEqual(self.payments.reconcile(self.customer, self.quote)['booking_status'], 'BOOKED')

    def test_webhook_first_payment_never_recaptures_on_inconsistent_approved_read(self):
        Webhooks(self.store, self.provider).handle(self.event(), {})
        self.provider.order.return_value = self.approved
        with self.assertRaises(ValueError):
            self.payments.capture(self.customer, self.quote)
        self.provider.capture.assert_not_called()
        self.assertEqual(self.operations(), {})

    def test_payment_completed_during_preflight_prevents_new_capture(self):
        def read(_):
            self.store.reconcile(self.customer, self.quote, self.completed, 'MERCHANT1')
            return self.approved
        self.provider.order.side_effect = read
        with self.assertRaises(ValueError):
            self.payments.capture(self.customer, self.quote)
        self.provider.capture.assert_not_called()
        self.assertEqual(self.operations(), {})

    def test_unauthorized_actors_cannot_trigger_preflight_reads(self):
        for actor in [self.caterer, {'id': 'other-customer', 'role': 'customer'}]:
            with self.subTest(actor=actor):
                with self.assertRaises(PermissionError):
                    self.payments.capture(actor, self.quote)
                self.provider.order.assert_not_called()
                self.provider.capture.assert_not_called()

    def test_missing_approval_prevents_preflight(self):
        with self.store.db() as db:
            db.execute('UPDATE quotes SET customer_approved=0 WHERE id=?', (self.quote,))
        with self.assertRaises(PermissionError):
            self.payments.capture(self.customer, self.quote)
        self.provider.order.assert_not_called()

    def test_duplicate_webhook_does_not_duplicate_recovery_audit(self):
        self.start(uncertain=True)
        handler = Webhooks(self.store, self.provider)
        handler.handle(self.event(), {})
        self.assertTrue(handler.handle(self.event(), {})['duplicate'])
        with self.store.db() as db:
            count = db.execute("SELECT count(*) FROM audit WHERE action='PAYMENT_OPERATION_RECONCILED_CAPTURE'").fetchone()[0]
        self.assertEqual(count, 1)
        self.assertEqual(self.provider.order.call_count, 1)

    def test_concurrent_preflights_allow_only_one_capture_write(self):
        barrier = threading.Barrier(2)
        lock = threading.Lock()
        reads = 0
        def read(_):
            nonlocal reads
            with lock:
                reads += 1
                number = reads
            if number <= 2:
                barrier.wait(timeout=5)
                return copy.deepcopy(self.approved)
            return copy.deepcopy(self.completed)
        self.provider.order.side_effect = read
        def capture():
            try:
                return self.payments.capture(self.customer, self.quote)
            except ValueError:
                return 'blocked'
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: capture(), range(2)))
        self.assertEqual(results.count('blocked'), 1)
        self.assertEqual(self.provider.capture.call_count, 1)
        self.assertEqual(self.operations()['capture']['state'], 'SUCCEEDED')

    def test_recovery_audit_failure_rolls_back_receipt_and_journal(self):
        self.start(uncertain=True)
        before = self.operations()['capture']
        original_log = self.store.log
        def fail_recovery_audit(db, user, action, resource):
            if action == 'PAYMENT_OPERATION_RECONCILED_CAPTURE':
                raise RuntimeError('Synthetic audit write failure')
            return original_log(db, user, action, resource)
        self.store.log = fail_recovery_audit
        with self.assertRaises(RuntimeError):
            self.payments.reconcile(self.customer, self.quote)
        self.assertEqual(self.operations()['capture'], before)
        self.assertIsNone(self.state()['capture_id'])
        self.assertEqual(self.state()['payment_status'], 'UNPAID')
