import unittest,tempfile,os
from unittest.mock import Mock
from domain import Store
from webhooks import Webhooks
class WebhookTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.s=Store(os.path.join(self.tmp.name,'db'));self.c={'id':'c','role':'customer'};self.v={'id':'v','role':'caterer'}
  e=self.s.event(self.c,'Demo',4,'synthetic');self.q=self.s.quote(self.v,e,'25.00');self.s.approve(self.c,self.q);self.s.bind(self.c,self.q,'ORDER1')
  self.r={'id':'ORDER1','status':'COMPLETED','purchase_units':[{'custom_id':self.q,'payee':{'merchant_id':'M'},'payments':{'captures':[{'id':'CAP1','status':'COMPLETED','amount':{'currency_code':'USD','value':'100.00'}}]}}]}
  self.p=Mock(merchant='M');self.p.order.return_value=self.r;self.w=Webhooks(self.s,self.p)
 def tearDown(self):self.tmp.cleanup()
 def event(self,kind='PAYMENT.CAPTURE.COMPLETED',eid='EV1'):return {'id':eid,'event_type':kind,'resource':{'id':'CAP1','supplementary_data':{'related_ids':{'order_id':'ORDER1'}}}}
 def test_signature_before_lookup(self):
  self.p.verify_webhook.side_effect=ValueError('forged')
  with self.assertRaises(ValueError):self.w.handle(self.event(),{})
  self.p.order.assert_not_called();self.assertIsNone(self.s.list(self.c)[0]['quotes'][0]['capture_id'])
 def test_completion_uses_readback_and_deduplicates(self):
  self.w.handle(self.event(),{});self.assertTrue(self.w.handle(self.event(),{})['duplicate']);self.assertEqual(self.p.order.call_count,1)
 def test_signed_body_cannot_override_readback(self):
  self.r['status']='PENDING'
  with self.assertRaises(ValueError):self.w.handle(self.event(),{})
 def test_reversal_holds_and_unbooks(self):
  self.w.handle(self.event(),{});self.s.book(self.v,self.q);self.w.handle(self.event('PAYMENT.CAPTURE.REVERSED','EV2'),{})
  q=self.s.list(self.c)[0]['quotes'][0];self.assertEqual(q['booked'],0);self.assertEqual(q['payment_status'],'REVIEW_REQUIRED')
  with self.assertRaises(ValueError):self.s.book(self.v,self.q)
  with self.assertRaises(ValueError):self.w.handle(self.event(eid='EV3'),{})
 def test_wrong_merchant_cannot_hold_record(self):
  self.r['purchase_units'][0]['payee']['merchant_id']='wrong'
  with self.assertRaises(ValueError):self.w.handle(self.event('PAYMENT.CAPTURE.REFUNDED'),{})
 def test_unknown_order_rejected(self):
  e=self.event();e['resource']['supplementary_data']['related_ids']['order_id']='unknown'
  with self.assertRaises(ValueError):self.w.handle(e,{})
