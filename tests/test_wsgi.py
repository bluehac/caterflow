import io,json,os,sys,tempfile,unittest
from unittest.mock import patch

class WsgiTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory()
  cls.env=patch.dict(os.environ,{'CATERFLOW_PUBLIC_ORIGIN':'https://caterflow.example.test','CATERFLOW_DB':cls.tmp.name+'/db','CATERFLOW_AI_ENABLED':'false','CATERFLOW_PAYPAL_ENABLED':'false'})
  cls.env.start()
  import wsgi
  cls.wsgi=wsgi
  import app
  cls.app=app
  app.store.add_user('demo','customer','synthetic-password-long')
 @classmethod
 def tearDownClass(cls):
  cls.env.stop();cls.tmp.cleanup()
  sys.modules.pop('app',None);sys.modules.pop('wsgi',None)
 def request(self,path='/',method='GET',body=None,**headers):
  payload=b'' if body is None else json.dumps(body).encode()
  env={'PATH_INFO':path,'REQUEST_METHOD':method,'HTTP_HOST':'caterflow.example.test','HTTP_ORIGIN':'https://caterflow.example.test','CONTENT_TYPE':'application/json','CONTENT_LENGTH':str(len(payload)),'wsgi.input':io.BytesIO(payload),'REMOTE_ADDR':'127.0.0.1'}
  env.update(headers);result={}
  def start(status,h):result.update(status=status,headers=dict(h))
  result['body']=b''.join(self.wsgi.application(env,start))
  return result
 def test_page_served_with_security_headers(self):
  r=self.request('/catering');self.assertTrue(r['status'].startswith('200'))
  self.assertIn(b'LA BANDERA KITCHEN',r['body'])
  self.assertEqual(r['headers']['Cache-Control'],'no-store')
 def test_untrusted_host_and_origin_rejected(self):
  self.assertTrue(self.request(HTTP_HOST='attacker.example')['status'].startswith('403'))
  r=self.request('/api/login','POST',{'id':'demo','password':'synthetic-password-long'},HTTP_ORIGIN='https://attacker.example')
  self.assertTrue(r['status'].startswith('403'))
 def test_secure_cookie_and_authenticated_readback(self):
  r=self.request('/api/login','POST',{'id':'demo','password':'synthetic-password-long'})
  self.assertTrue(r['status'].startswith('200'));cookie=r['headers']['Set-Cookie']
  for flag in ['Secure','HttpOnly','SameSite=Strict']:self.assertIn(flag,cookie)
  r=self.request('/api/events',HTTP_COOKIE=cookie.split(';')[0])
  self.assertEqual(json.loads(r['body'])['user']['id'],'demo')
 def test_no_forwarded_host_bypass(self):
  r=self.request(HTTP_HOST='attacker.example',HTTP_X_FORWARDED_HOST='caterflow.example.test')
  self.assertTrue(r['status'].startswith('403'))
 def test_oversized_request_and_unsupported_method(self):
  r=self.request('/api/login','POST',{},CONTENT_LENGTH='99999')
  self.assertTrue(r['status'].startswith('400'))
  self.assertTrue(self.request(method='PUT')['status'].startswith('405'))
 def test_expanded_photo_body_requires_authentication_before_read(self):
  class Unread(io.BytesIO):
   def read(self,*args):raise AssertionError('Unauthenticated photo body was read')
  env={'PATH_INFO':'/api/ai/draft','REQUEST_METHOD':'POST','HTTP_HOST':'caterflow.example.test','HTTP_ORIGIN':'https://caterflow.example.test','CONTENT_TYPE':'application/json','CONTENT_LENGTH':'500000','wsgi.input':Unread(b''),'REMOTE_ADDR':'127.0.0.1'}
  response={}
  with patch.dict(os.environ,{'CATERFLOW_PHOTO_ENABLED':'true'}):
   b''.join(self.wsgi.application(env,lambda status,headers:response.update(status=status)))
  self.assertTrue(response['status'].startswith('403'))
 def test_photo_route_authenticates_and_keeps_other_route_size_limits(self):
  login=self.request('/api/login','POST',{'id':'demo','password':'synthetic-password-long'})
  cookie=login['headers']['Set-Cookie'].split(';')[0]
  session=json.loads(self.request('/api/events',HTTP_COOKIE=cookie)['body'])
  with patch.dict(os.environ,{'CATERFLOW_PHOTO_ENABLED':'true'}),patch.object(self.app,'BedrockIntake') as adapter:
   adapter.return_value.draft.return_value={'requires_customer_review':True}
   bad=self.request('/api/ai/draft','POST',{'text':'x'*20000},HTTP_COOKIE=cookie,HTTP_X_CSRF_TOKEN='wrong')
   self.assertTrue(bad['status'].startswith('403'));adapter.assert_not_called()
   good=self.request('/api/ai/draft','POST',{'text':'x'*20000},HTTP_COOKIE=cookie,HTTP_X_CSRF_TOKEN=session['csrf'])
   self.assertTrue(good['status'].startswith('200'));adapter.return_value.draft.assert_called_once()
   self.assertTrue(self.request('/api/login','POST',{'text':'x'*20000})['status'].startswith('400'))
 def test_successful_logins_do_not_exhaust_failure_allowance(self):
  with patch.dict(self.app.attempts,{},clear=True):
   for _ in range(15):
    response=self.request('/api/login','POST',{'id':'demo','password':'synthetic-password-long'})
    self.assertTrue(response['status'].startswith('200'))
   self.assertEqual(self.app.attempts,{})
 def test_failed_login_limit_is_preserved_and_blocked_requests_do_not_extend_it(self):
  with patch.dict(self.app.attempts,{},clear=True),patch.object(self.app.time,'time',return_value=1000):
   for _ in range(10):
    self.assertTrue(self.request('/api/login','POST',{'id':'demo','password':'wrong'})['status'].startswith('403'))
   before=list(self.app.attempts['127.0.0.1'])
   blocked=self.request('/api/login','POST',{'id':'demo','password':'synthetic-password-long'})
   self.assertIn(b'Wait a minute',blocked['body']);self.assertEqual(self.app.attempts['127.0.0.1'],before)
  with patch.dict(self.app.attempts,{'127.0.0.1':[1000]*10},clear=True),patch.object(self.app.time,'time',return_value=1061):
   self.assertTrue(self.request('/api/login','POST',{'id':'demo','password':'synthetic-password-long'})['status'].startswith('200'))
 def test_success_does_not_clear_prior_failure_history(self):
  with patch.dict(self.app.attempts,{'127.0.0.1':[1000]*3},clear=True),patch.object(self.app.time,'time',return_value=1001):
   self.assertTrue(self.request('/api/login','POST',{'id':'demo','password':'synthetic-password-long'})['status'].startswith('200'))
   self.assertEqual(self.app.attempts['127.0.0.1'],[1000]*3)
 def test_limiter_memory_is_bounded_without_evicting_active_failures(self):
  full={str(i):[1000] for i in range(1024)}
  with patch.dict(self.app.attempts,full,clear=True),patch.object(self.app.time,'time',return_value=1001):
   self.assertTrue(self.request('/api/login','POST',{'id':'demo','password':'wrong'})['status'].startswith('403'))
   self.assertEqual(len(self.app.attempts),1024)
 def test_turnstile_failure_prevents_login_and_sensitive_actions(self):
  from abuse import VerificationUnavailable
  with patch.object(self.app,'verify',side_effect=VerificationUnavailable('Unavailable')),patch.object(self.app.store,'login') as login:
   response=self.request('/api/login','POST',{'id':'demo','password':'synthetic-password-long'})
   self.assertTrue(response['status'].startswith('503'));login.assert_not_called()
  login=self.request('/api/login','POST',{'id':'demo','password':'synthetic-password-long'})
  cookie=login['headers']['Set-Cookie'].split(';')[0]
  session=json.loads(self.request('/api/events',HTTP_COOKIE=cookie)['body'])
  with patch.object(self.app,'verify',side_effect=PermissionError('Verification failed')),patch.object(self.app,'BedrockIntake') as ai,patch.object(self.app.store,'intake') as intake:
   for path in ('/api/ai/draft','/api/intake'):
    response=self.request(path,'POST',{},HTTP_COOKIE=cookie,HTTP_X_CSRF_TOKEN=session['csrf'])
    self.assertTrue(response['status'].startswith('403'))
   ai.assert_not_called();intake.assert_not_called()
 def test_abuse_limit_blocks_before_provider_call_and_returns_429(self):
  from abuse import RateLimited
  login=self.request('/api/login','POST',{'id':'demo','password':'synthetic-password-long'})
  cookie=login['headers']['Set-Cookie'].split(';')[0]
  session=json.loads(self.request('/api/events',HTTP_COOKIE=cookie)['body'])
  with patch.object(self.app,'reserve',side_effect=RateLimited('Wait')),patch.object(self.app,'BedrockIntake') as ai:
   response=self.request('/api/ai/draft','POST',{'text':'Synthetic event'},HTTP_COOKIE=cookie,HTTP_X_CSRF_TOKEN=session['csrf'])
   self.assertTrue(response['status'].startswith('429'));ai.assert_not_called()
