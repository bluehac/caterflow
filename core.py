"""CaterFlow development core. No network calls or real payments."""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


def money(value):
    try:
        amount = Decimal(str(value))
    except InvalidOperation:
        raise ValueError('Invalid amount') from None
    if not amount.is_finite() or amount <= 0 or amount != amount.quantize(Decimal('.01')):
        raise ValueError('Amount must be positive with at most two decimal places')
    return amount


@dataclass
class Quote:
    quote_id: str
    guests: int
    unit_price: str
    approved: bool = False
    order_id: str | None = None
    capture_id: str | None = None
    caterer_accepted: bool = False

    def __post_init__(self):
        if type(self.guests) is not int or not 1 <= self.guests <= 1000:
            raise ValueError('Guest count must be 1–1000')
        self.unit_price = str(money(self.unit_price))

    @property
    def total(self):
        return f'{money(self.unit_price) * self.guests:.2f}'

    @property
    def state(self):
        if self.capture_id:
            return 'BOOKED' if self.caterer_accepted else 'PAID_AWAITING_ACCEPTANCE'
        return 'AWAITING_PAYMENT' if self.order_id else 'QUOTE_READY'

    def order_payload(self):
        if not self.approved:
            raise ValueError('Caterer must approve the quote first')
        return {'intent': 'CAPTURE', 'purchase_units': [{
            'custom_id': self.quote_id,
            'amount': {'currency_code': 'USD', 'value': self.total}}]}

    def bind_order(self, order_id):
        self.order_payload()
        if not isinstance(order_id, str) or not order_id or self.order_id not in (None, order_id):
            raise ValueError('Invalid or conflicting order')
        self.order_id = order_id

    def reconcile(self, response, expected_merchant):
        """Only pass authenticated server-side PayPal order responses here.

        This pure validator does NOT authenticate browser input or webhooks.
        """
        if not self.order_id or response.get('id') != self.order_id:
            raise ValueError('Order mismatch')
        if response.get('status') != 'COMPLETED':
            raise ValueError('Payment is not completed')
        units = response.get('purchase_units', [])
        if len(units) != 1:
            raise ValueError('Expected one purchase unit')
        unit = units[0]
        if unit.get('custom_id') != self.quote_id or not expected_merchant or unit.get('payee', {}).get('merchant_id') != expected_merchant:
            raise ValueError('Quote or merchant mismatch')
        captures = unit.get('payments', {}).get('captures', [])
        if len(captures) != 1:
            raise ValueError('Expected one capture')
        capture = captures[0]
        amount = capture.get('amount', {})
        if capture.get('status') != 'COMPLETED' or amount.get('currency_code') != 'USD' or money(amount.get('value')) != money(self.total):
            raise ValueError('Capture status or amount mismatch')
        capture_id = capture.get('id')
        if not capture_id or self.capture_id not in (None, capture_id):
            raise ValueError('Missing or conflicting capture')
        self.capture_id = capture_id
