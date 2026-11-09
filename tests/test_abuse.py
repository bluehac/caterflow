import json,os,tempfile,unittest
from unittest.mock import Mock,patch
from domain import Store
from abuse import reserve,verify,public_config,RateLimited,VerificationUnavailable
class AbuseTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.store=Store(self.tmp.name+'/db')
 def tearDown(self):self.tmp.cleanup()
 def test_rate_limits_survive_new_instances_and_separate_accounts(self):
  for _ in range(3):reserve(self.store,'a','ai',1000)
  with self.assertRaises(RateLimited):reserve(Store(self.store.path),'a','ai',1001)
  reserve(self.store,'b','ai',1001);reserve(self.store,'a','ai',1061)
 def test_intake_window_and_bounded_storage(self):
  for _ in range(5):reserve(self.store,'a','intake',1000)
  with self.assertRaises(RateLimited):reserve(self.store,'a','intake',1001)
  reserve(self.store,'a','intake',1601)
  reserve(self.store,'b','intake',90000)
  with self.store.db() as d:self.assertEqual(d.execute('SELECT count(*) FROM abuse_attempts').fetchone()[0],1)
 def test_daily_cap_cannot_be_evaded_with_spacing(self):
  for i in range(10):reserve(self.store,'a','ai',1000+i*61)
  with self.assertRaises(RateLimited):reserve(self.store,'a','ai',2000)
 def verify_response(self,result):
  response=Mock();response.read.return_value=json.dumps(result).encode();context=Mock();context.__enter__=Mock(return_value=response);context.__exit__=Mock(return_value=False);return Mock(return_value=context)
 @patch.dict(os.environ,{'CATERFLOW_TURNSTILE_ENABLED':'true','CATERFLOW_TURNSTILE_SITEKEY':'public','CATERFLOW_TURNSTILE_SECRET':'synthetic-secret'})
 def test_validation_binds_action_hostname_and_success(self):
  for result in ({'success':False},{'success':True,'hostname':'evil.test','action':'intake'},{'success':True,'hostname':'safe.test','action':'login'},{'success':'true','hostname':'safe.test','action':'intake'}):
   with self.assertRaises(PermissionError):verify('token','intake','safe.test',self.verify_response(result))
  call=self.verify_response({'success':True,'hostname':'safe.test','action':'intake'});verify('token','intake','safe.test',call)
  payload=json.loads(call.call_args.args[0].data);self.assertEqual(set(payload),{'secret','response'})
  self.assertNotIn('synthetic-secret',str(public_config()))
 @patch.dict(os.environ,{'CATERFLOW_TURNSTILE_ENABLED':'true','CATERFLOW_TURNSTILE_SITEKEY':'public','CATERFLOW_TURNSTILE_SECRET':'synthetic-secret'})
 def test_missing_oversize_and_provider_failure_fail_closed(self):
  for token in ('','x'*2049,None):
   with self.assertRaises(PermissionError):verify(token,'ai','safe.test',Mock())
  with self.assertRaises(VerificationUnavailable):verify('token','ai','safe.test',Mock(side_effect=OSError()))
 @patch.dict(os.environ,{'CATERFLOW_TURNSTILE_ENABLED':'true','CATERFLOW_TURNSTILE_SECRET':''})
 def test_enabled_but_unconfigured_never_silently_bypasses(self):
  with self.assertRaises(VerificationUnavailable):verify('token','login','safe.test',Mock())
