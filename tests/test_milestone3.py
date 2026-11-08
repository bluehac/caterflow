import unittest,tempfile,os,sqlite3
from datetime import date,timedelta
from unittest.mock import Mock
from domain import Store
from intake import validate_intake,validate_ai_draft
from payments import Payments
class NewControls(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.path=os.path.join(self.tmp.name,'db');self.s=Store(self.path);self.c={'id':'c','role':'customer'};self.v={'id':'v','role':'caterer'}
  self.s.add_user('c','customer','synthetic-password-long')
  self.data={'title':'Synthetic event','guests':40,'event_date':(date.today()+timedelta(days=30)).isoformat(),'location':'Test venue','service':'delivery','menu_notes':'Demo menu','dietary_notes':'Review allergies','contact_name':'Demo Person','contact_email':'demo@example.com','language':'en','consent':True}
 def tearDown(self): self.tmp.cleanup()
 def quote(self):
  e=self.s.intake(self.c,self.data);q=self.s.quote(self.v,e,'25.00');self.s.approve(self.c,q);return q
 def test_reviewed_intake_is_durable(self):
  e=self.s.intake(self.c,self.data)
  with Store(self.path).db() as d:self.assertIsNotNone(d.execute('SELECT payload FROM intake_details WHERE event=?',(e,)).fetchone())
 def test_unknown_and_price_fields_rejected(self):
  for k in ['price','approved','payment_status','role']:
   with self.subTest(k=k):
    with self.assertRaises(ValueError):validate_intake(dict(self.data,**{k:'bad'}))
    with self.assertRaises(ValueError):validate_ai_draft({k:'bad'})
 def test_invalid_guest_and_consent(self):
  for patch in [{'guests':True},{'guests':0},{'consent':False},{'contact_email':'bad'},{'event_date':'2000-01-01'}]:
   with self.subTest(patch=patch):
    with self.assertRaises(ValueError):validate_intake(dict(self.data,**patch))
 def test_session_survives_restart_and_revocation(self):
  token,_=self.s.new_session(self.c);self.assertEqual(Store(self.path).session(token)['user'],self.c)
  with self.s.db() as d:d.execute("UPDATE users SET role='caterer' WHERE id='c'")
  self.assertEqual(self.s.session(token)['user']['role'],'caterer');self.s.logout(token)
  with self.assertRaises(PermissionError):self.s.session(token)
 def test_logout_only_own_session(self):
  a,_=self.s.new_session(self.c);b,_=self.s.new_session(self.c);self.s.logout(a);self.assertEqual(self.s.session(b)['user'],self.c)
 def test_session_expiration(self):
  token,_=self.s.new_session(self.c)
  with self.s.db() as d:d.execute('UPDATE sessions SET expires=0')
  with self.assertRaises(PermissionError):self.s.session(token)
 def test_journal_blocks_automatic_retry_after_restart(self):
  q=self.quote();a=self.s.begin_payment_operation(self.c,q,'create');self.assertEqual(a['state'],'IN_FLIGHT')
  with self.assertRaises(ValueError):Store(self.path).begin_payment_operation(self.c,q,'create')
 def test_uncertain_outcome_is_durable(self):
  q=self.quote();self.s.begin_payment_operation(self.c,q,'create');self.s.finish_payment_operation(self.c,q,'create')
  with self.assertRaises(ValueError):self.s.begin_payment_operation(self.c,q,'create')
 def test_create_timeout_no_second_provider_write(self):
  q=self.quote();p=Mock(configured=True);p.create.side_effect=TimeoutError();pay=Payments(self.s,p)
  with self.assertRaises(RuntimeError):pay.create(self.c,q,'http://127.0.0.1:8080/')
  with self.assertRaises(ValueError):pay.create(self.c,q,'http://127.0.0.1:8080/')
  self.assertEqual(p.create.call_count,1)
 def test_successful_create_is_reused(self):
  q=self.quote();p=Mock(configured=True);p.create.return_value={'id':'ORDER1'};p.order.return_value={'id':'ORDER1'};pay=Payments(self.s,p)
  pay.create(self.c,q,'http://127.0.0.1:8080/');pay.create(self.c,q,'http://127.0.0.1:8080/');self.assertEqual(p.create.call_count,1)
 def test_missing_provider_no_operation(self):
  q=self.quote();p=Mock(configured=False)
  with self.assertRaises(RuntimeError):Payments(self.s,p).create(self.c,q,'http://127.0.0.1:8080/')
  with self.s.db() as d:self.assertEqual(d.execute('SELECT count(*) FROM payment_operations').fetchone()[0],0)

 def test_intake_retry_deduplicated_after_restart(self):
  key='synthetic-request-key-0001';a=self.s.intake(self.c,self.data,key);b=Store(self.path).intake(self.c,self.data,key)
  self.assertEqual(a,b);self.assertEqual(len(self.s.list(self.c)),1)
 def test_changed_payload_rejects_reused_key(self):
  key='synthetic-request-key-0001';self.s.intake(self.c,self.data,key)
  with self.assertRaises(ValueError):self.s.intake(self.c,dict(self.data,guests=50),key)
