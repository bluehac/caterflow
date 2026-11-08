import unittest,tempfile,os,sqlite3,copy
from domain import Store
class DurableTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.path=os.path.join(self.tmp.name,'db');self.s=Store(self.path);self.c={'id':'c','role':'customer'};self.v={'id':'v','role':'caterer'};self.other={'id':'other','role':'customer'}
  self.e=self.s.event(self.c,'Synthetic dinner',4,'No real customer data');self.q=self.s.quote(self.v,self.e,'25.00')
 def tearDown(self): self.tmp.cleanup()
 def ready(self): self.s.approve(self.c,self.q);self.s.bind(self.c,self.q,'ORDER1')
 def response(self): return {'id':'ORDER1','status':'COMPLETED','purchase_units':[{'custom_id':self.q,'payee':{'merchant_id':'MERCHANT'},'payments':{'captures':[{'id':'CAP1','status':'COMPLETED','amount':{'currency_code':'USD','value':'100.00'}}]}}]}
 def test_persist_restart(self): self.assertEqual(Store(self.path).list(self.c)[0]['quotes'][0]['total'],'100.00')
 def test_access(self):
  with self.assertRaises(PermissionError): self.s.approve(self.other,self.q)
  self.assertEqual(self.s.list(self.other),[])
 def test_no_customer_price_authority(self):
  with self.assertRaises(PermissionError): self.s.quote(self.c,self.e,'1')
 def test_immutable(self):
  with self.assertRaises(sqlite3.IntegrityError):
   with self.s.db() as d: d.execute('UPDATE quotes SET total=? WHERE id=?',('1.00',self.q))
 def test_stale_revision(self):
  self.s.quote(self.v,self.e,'26.00')
  with self.assertRaises(ValueError): self.s.approve(self.c,self.q)
 def test_no_order_without_approval(self):
  with self.assertRaises(PermissionError): self.s.bind(self.c,self.q,'ORDER1')
 def test_booking_gate(self):
  with self.assertRaises(ValueError): self.s.book(self.v,self.q)
 def test_full_verified_control_flow_and_duplicate(self):
  self.ready();r=self.response();self.s.reconcile(self.c,self.q,r,'MERCHANT','EV1');self.s.reconcile(self.c,self.q,r,'MERCHANT','EV1');self.s.book(self.v,self.q)
  self.assertEqual(self.s.list(self.c)[0]['quotes'][0]['booked'],1)
  with self.s.db() as d: self.assertEqual(d.execute("SELECT count(*) FROM audit WHERE action='PAYMENT_VERIFIED'").fetchone()[0],1)
 def test_pending_declined_cancelled_rejected(self):
  self.ready()
  for status in ['PENDING','DECLINED','CANCELLED','APPROVED']:
   with self.subTest(status=status):
    r=self.response();r['status']=status
    with self.assertRaises(ValueError): self.s.reconcile(self.c,self.q,r,'MERCHANT')
 def test_amount_currency_merchant_order_quote_capture_mismatch(self):
  self.ready()
  for kind in ['amount','currency','merchant','order','quote','capture']:
   with self.subTest(kind=kind):
    r=self.response();u=r['purchase_units'][0];c=u['payments']['captures'][0]
    if kind=='amount': c['amount']['value']='1.00'
    if kind=='currency': c['amount']['currency_code']='EUR'
    if kind=='merchant': u['payee']['merchant_id']='WRONG'
    if kind=='order': r['id']='WRONG'
    if kind=='quote': u['custom_id']='WRONG'
    if kind=='capture': c['status']='PENDING'
    with self.assertRaises(ValueError): self.s.reconcile(self.c,self.q,r,'MERCHANT')
 def test_password(self):
  self.s.add_user('test','customer','synthetic-password-long');self.assertIsNone(self.s.login('test','wrong'));self.assertEqual(self.s.login('test','synthetic-password-long')['role'],'customer')
 def test_audit_append_only(self):
  with self.assertRaises(sqlite3.IntegrityError):
   with self.s.db() as d: d.execute('DELETE FROM audit')
 def test_customer_cannot_book(self):
  with self.assertRaises(PermissionError): self.s.book(self.c,self.q)
 def test_no_revision_after_approval(self):
  self.ready()
  with self.assertRaises(ValueError): self.s.quote(self.v,self.e,'30.00')
