import unittest,tempfile,subprocess,os,sys,time,json,urllib.request,urllib.error,http.cookiejar
from domain import Store
class HttpTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();path=os.path.join(cls.tmp.name,'db');Store(path).add_user('customer','customer','synthetic-password-long')
  cls.proc=subprocess.Popen([sys.executable,'app.py'],env=dict(os.environ,CATERFLOW_DB=path),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  cls.opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
  for _ in range(50):
   try: urllib.request.urlopen('http://127.0.0.1:8080/',timeout=.2);break
   except OSError: time.sleep(.05)
  else: raise RuntimeError('Local app did not start')
 @classmethod
 def tearDownClass(cls): cls.proc.terminate();cls.proc.wait(timeout=5);cls.tmp.cleanup()
 def request(self,path,body=None,csrf=None,origin='http://127.0.0.1:8080'):
  headers={'Origin':origin,'Content-Type':'application/json'}
  if csrf: headers['X-CSRF-Token']=csrf
  req=urllib.request.Request('http://127.0.0.1:8080'+path,data=None if body is None else json.dumps(body).encode(),headers=headers)
  return self.opener.open(req,timeout=3)
 def test_http_workflow_and_csrf(self):
  with self.request('/api/login',{'id':'customer','password':'synthetic-password-long'}) as r: self.assertIn('HttpOnly',r.headers['Set-Cookie'])
  with self.request('/api/events') as r: csrf=json.load(r)['csrf']
  with self.assertRaises(urllib.error.HTTPError) as e: self.request('/api/inquiry',{'title':'Synthetic','guests':4,'notes':'test'})
  self.assertEqual(e.exception.code,403)
  with self.request('/api/inquiry',{'title':'Synthetic','guests':4,'notes':'test'},csrf) as r: self.assertEqual(r.status,200)
  with self.request('/api/events') as r: self.assertEqual(json.load(r)['events'][0]['title'],'Synthetic')
  with self.assertRaises(urllib.error.HTTPError): self.request('/api/inquiry',{},csrf,'https://attacker.example')
 def test_receipt_endpoint_absent(self):
  with self.request('/api/login',{'id':'customer','password':'synthetic-password-long'}): pass
  with self.request('/api/events') as r: csrf=json.load(r)['csrf']
  with self.assertRaises(urllib.error.HTTPError) as e: self.request('/api/reconcile',{'status':'COMPLETED'},csrf)
  self.assertEqual(e.exception.code,404)

 def test_lbk_page_and_persisted_intake(self):
  with self.request('/catering') as r: self.assertIn('LA BANDERA KITCHEN',r.read().decode())
  with self.request('/api/login',{'id':'customer','password':'synthetic-password-long'}): pass
  with self.request('/api/events') as r: csrf=json.load(r)['csrf']
  from datetime import date,timedelta
  data={'title':'Synthetic LBK intake','guests':40,'event_date':(date.today()+timedelta(days=30)).isoformat(),'location':'Synthetic venue','service':'delivery','menu_notes':'Demo','dietary_notes':'Review required','contact_name':'Demo Person','contact_email':'demo@example.com','language':'es','consent':True}
  with self.request('/api/intake',data,csrf) as r:self.assertEqual(r.status,200)
  with self.request('/api/events') as r:self.assertTrue(any(e['title']=='Synthetic LBK intake' for e in json.load(r)['events']))
