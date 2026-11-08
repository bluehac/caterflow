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
