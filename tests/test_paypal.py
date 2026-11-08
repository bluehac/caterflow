import unittest,os
from unittest.mock import patch
from paypal import PayPal,BASE
from core import Quote
class TransportTests(unittest.TestCase):
 def setUp(self):
  self.env=patch.dict(os.environ,{'PAYPAL_CLIENT_ID':'synthetic','PAYPAL_CLIENT_SECRET':'synthetic','PAYPAL_MERCHANT_ID':'merchant','PAYPAL_WEBHOOK_ID':'webhook'});self.env.start();self.p=PayPal()
 def tearDown(self): self.env.stop()
 def test_sandbox_only(self): self.assertEqual(BASE,'https://api-m.sandbox.paypal.com')
 def test_create_stable_idempotency_and_exact_quote(self):
  with patch.object(self.p,'call',return_value={'id':'ORDER'}) as c:
   self.p.create(Quote('q1',4,'25.00',True),'http://127.0.0.1:8080/')
   args=c.call_args.args;self.assertEqual(args[3],'create-q1');self.assertEqual(args[2]['purchase_units'][0]['amount']['value'],'100.00');self.assertEqual(args[2]['purchase_units'][0]['payee']['merchant_id'],'merchant')
 def test_capture_stable_key(self):
  with patch.object(self.p,'call') as c:
   self.p.capture('ORDER1','q1');self.assertEqual(c.call_args.args[3],'capture-q1')
 def test_order_path_injection(self):
  with self.assertRaises(ValueError): self.p.order('../oauth2/token')
 def test_missing_webhook_headers(self):
  with self.assertRaises(ValueError): self.p.verify_webhook({}, {})
 def test_forged_webhook_rejected(self):
  with patch.object(self.p,'call',return_value={'verification_status':'FAILURE'}):
   with self.assertRaises(ValueError): self.p.verify_webhook({}, {k:'synthetic' for k in ['paypal-auth-algo','paypal-cert-url','paypal-transmission-id','paypal-transmission-sig','paypal-transmission-time']})
 def test_missing_configuration_fails_closed(self):
  with patch.dict(os.environ,{},clear=True):
   with self.assertRaises(RuntimeError): PayPal().call('/v2/checkout/orders')
