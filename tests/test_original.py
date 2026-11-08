import copy
import unittest
from core import Quote, money


class PaymentControls(unittest.TestCase):
    def setUp(self):
        self.q = Quote('quote-1', 30, '18.99', approved=True)
        self.q.bind_order('order-1')
        self.receipt = {'id': 'order-1', 'status': 'COMPLETED', 'purchase_units': [{
            'custom_id': 'quote-1', 'payee': {'merchant_id': 'merchant-1'},
            'payments': {'captures': [{'id': 'capture-1', 'status': 'COMPLETED',
                'amount': {'currency_code': 'USD', 'value': '569.70'}}]}}]}

    def test_exact_total(self):
        self.assertEqual(self.q.total, '569.70')

    def test_requires_quote_approval(self):
        with self.assertRaises(ValueError): Quote('q', 1, '1').order_payload()

    def test_completed_payment_is_not_booking(self):
        self.q.reconcile(self.receipt, 'merchant-1')
        self.assertEqual(self.q.state, 'PAID_AWAITING_ACCEPTANCE')
        self.q.caterer_accepted = True
        self.assertEqual(self.q.state, 'BOOKED')

    def test_repeated_receipt_is_idempotent(self):
        self.q.reconcile(self.receipt, 'merchant-1')
        self.q.reconcile(self.receipt, 'merchant-1')
        self.assertEqual(self.q.capture_id, 'capture-1')

    def test_mismatched_and_pending_receipts_fail_closed(self):
        for target, key, value in [('root','id','wrong'), ('root','status','APPROVED'),
                ('unit','custom_id','wrong'), ('capture','status','PENDING'),
                ('amount','value','1.00'), ('amount','currency_code','EUR'),
                ('capture','id',None)]:
            with self.subTest(target=target, key=key):
                receipt = copy.deepcopy(self.receipt)
                unit = receipt['purchase_units'][0]
                capture = unit['payments']['captures'][0]
                obj = {'root':receipt,'unit':unit,'capture':capture,'amount':capture['amount']}[target]
                obj[key] = value
                with self.assertRaises(ValueError): self.q.reconcile(receipt, 'merchant-1')
                self.assertIsNone(self.q.capture_id)

    def test_wrong_merchant(self):
        with self.assertRaises(ValueError): self.q.reconcile(self.receipt, 'other')

    def test_invalid_money(self):
        for value in ['NaN','Infinity','-1','0','1.001','bad']:
            with self.subTest(value=value), self.assertRaises(ValueError): money(value)

    def test_invalid_guests(self):
        for count in [True,0,1001,1.5]:
            with self.subTest(count=count), self.assertRaises(ValueError): Quote('q',count,'1')


if __name__ == '__main__': unittest.main()
