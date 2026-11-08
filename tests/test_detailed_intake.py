import json,sqlite3,tempfile,unittest
from datetime import date,timedelta
from domain import Store
from intake import validate_intake

class DetailedIntake(unittest.TestCase):
 def payload(self):
  return dict(title='Synthetic gathering',guests=10,event_date=(date.today()+timedelta(days=30)).isoformat(),location='Test city',service='pickup',menu_notes='',dietary_notes='',contact_name='Test',contact_email='test@example.com',language='en',consent=True)
 def test_guest_minimum(self):
  for guests in (1,9,True):
   with self.assertRaises(ValueError):validate_intake(dict(self.payload(),guests=guests))
  self.assertEqual(validate_intake(self.payload())['guests'],10)
 def test_details_survive_handoff_and_restart(self):
  with tempfile.TemporaryDirectory() as d:
   path=d+'/db';s=Store(path);s.add_user('test','customer','synthetic-password-long')
   p=dict(self.payload(),primary_protein='Pernil request',budget_range='Undecided',accessibility_notes='Elevator access',phone='Synthetic phone')
   e=s.intake({'id':'test','role':'customer'},p)
   with Store(path).db() as db:
    saved=json.loads(db.execute('select payload from intake_details where event=?',(e,)).fetchone()[0]);notes=db.execute('select notes from events where id=?',(e,)).fetchone()[0]
   for k in ('primary_protein','budget_range','accessibility_notes','phone'):
    self.assertEqual(saved[k],p[k]);self.assertIn(p[k],notes)
 def test_detail_types_lengths_and_price_injection(self):
  for patch in ({'phone':{}},{'accessibility_notes':'x'*501},{'budget_range':100},{'approved_price':'1'}):
   with self.assertRaises(ValueError):validate_intake(dict(self.payload(),**patch))
 def test_blank_details_do_not_change_existing_payload(self):
  self.assertEqual(validate_intake(self.payload()),validate_intake(dict(self.payload(),phone='',organization='  ')))
