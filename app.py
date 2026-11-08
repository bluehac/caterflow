"""Loopback-only development server. Do not deploy the stdlib HTTP server."""
from http.server import HTTPServer,BaseHTTPRequestHandler
from http.cookies import SimpleCookie
from pathlib import Path
import json,secrets,time,os,sqlite3
from domain import Store
from paypal import PayPal
from payments import Payments
from ai import BedrockIntake
from webhooks import Webhooks
from sandbox_config import load_configured_secrets
from urllib.parse import urlsplit

load_configured_secrets()
ORIGIN=os.environ.get('CATERFLOW_PUBLIC_ORIGIN','http://127.0.0.1:8080')
parsed_origin=urlsplit(ORIGIN)
if ORIGIN!='http://127.0.0.1:8080' and (parsed_origin.scheme!='https' or not parsed_origin.hostname or parsed_origin.path or parsed_origin.query or parsed_origin.fragment or parsed_origin.username or parsed_origin.password):
    raise ValueError('An exact HTTPS public origin is required')
HOST=parsed_origin.netloc
SECURE_COOKIE='; Secure' if parsed_origin.scheme=='https' else ''
STATIC=Path(__file__).resolve().parent/'static'
store=Store(os.environ.get('CATERFLOW_DB','caterflow.db'))
attempts={}
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def reply(self,status,data,cookie=None,html=False):
        payload=data.encode() if html else json.dumps(data).encode()
        self.send_response(status); self.send_header('Content-Type','text/html; charset=utf-8' if html else 'application/json'); self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff'); self.send_header('X-Frame-Options','DENY'); self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'; img-src 'self' blob: data:")
        if cookie: self.send_header('Set-Cookie',cookie)
        self.send_header('Content-Length',str(len(payload))); self.end_headers(); self.wfile.write(payload)
    def token(self):
        c=SimpleCookie(self.headers.get('Cookie','')); sid=c.get('cf_session')
        return sid.value if sid else ''
    def user(self):
        return store.session(self.token())
    def do_GET(self):
        if self.headers.get('Host')!=HOST: return self.reply(403,{'error':'Host rejected'})
        if self.path in ('/','/catering'): return self.reply(200,(STATIC/('lbk.html' if self.path=='/catering' else 'index.html')).read_text(),html=True)
        try:
            s=self.user()
            if self.path=='/api/events': return self.reply(200,{'events':store.list(s['user']),'user':s['user'],'csrf':s['csrf'],'ai_drafting':os.environ.get('CATERFLOW_AI_ENABLED')=='true','photo_intake':os.environ.get('CATERFLOW_AI_ENABLED')=='true' and os.environ.get('CATERFLOW_PHOTO_ENABLED')=='true','sandbox_checkout':os.environ.get('CATERFLOW_PAYPAL_ENABLED')=='true' and PayPal().configured})
            self.reply(404,{'error':'Not found'})
        except PermissionError as e: self.reply(403,{'error':str(e)})
    def do_POST(self):
        try:
            if self.headers.get('Host')!=HOST: raise PermissionError('Host rejected')
            webhook=self.path=='/api/paypal/webhook'
            if not webhook and self.headers.get('Origin')!=ORIGIN: raise PermissionError('Origin rejected')
            size=int(self.headers.get('Content-Length','0'))
            limit=8192
            if self.path=='/api/ai/draft' and os.environ.get('CATERFLOW_PHOTO_ENABLED')=='true':
                # Authenticate BEFORE reading an expanded photo payload.
                pre=self.user()
                if pre['user']['role']!='customer' or not secrets.compare_digest(self.headers.get('X-CSRF-Token',''),pre['csrf']):raise PermissionError('Request verification failed')
                from vision import MAX_IMAGE_REQUEST
                limit=MAX_IMAGE_REQUEST
            if not 0<size<=limit: raise ValueError('Invalid request size')
            if self.headers.get('Content-Type')!='application/json': raise ValueError('JSON required')
            b=json.loads(self.rfile.read(size))
            if not isinstance(b,dict): raise ValueError('JSON object required')
            if webhook:
                if os.environ.get('CATERFLOW_PAYPAL_ENABLED')!='true': raise ValueError('Sandbox checkout disabled')
                return self.reply(200,Webhooks(store,PayPal()).handle(b,dict(self.headers)))
            if self.path=='/api/login':
                # Count failures only. Never trust client-supplied forwarded IPs.
                # Keep the existing 10-failure/60s policy; bound process memory.
                ip=self.client_address[0]; now=time.time()
                for key,values in list(attempts.items()):
                    recent=[t for t in values if now-t<60]
                    if recent:attempts[key]=recent
                    else:attempts.pop(key,None)
                recent=attempts.get(ip,[])
                if len(recent)>=10 or (ip not in attempts and len(attempts)>=1024): raise PermissionError('Wait a minute before trying again')
                u=store.login(str(b.get('id','')),str(b.get('password','')))
                if not u:
                    attempts[ip]=recent+[now]
                    raise PermissionError('Sign-in failed')
                sid,_=store.new_session(u)
                return self.reply(200,{'ok':True},'cf_session='+sid+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=3600'+SECURE_COOKIE)
            s=self.user()
            if not secrets.compare_digest(self.headers.get('X-CSRF-Token',''),s['csrf']): raise PermissionError('Request verification failed')
            u=s['user']
            if self.path in ('/api/payment/create','/api/payment/capture','/api/payment/reconcile'):
                if os.environ.get('CATERFLOW_PAYPAL_ENABLED')!='true': raise ValueError('Sandbox checkout disabled')
                service=Payments(store,PayPal())
                if self.path.endswith('/create'):
                    response=service.create(u,b['quote'],ORIGIN+'/')
                    links=[l.get('href','') for l in response.get('links',[]) if l.get('rel') in ('approve','payer-action')]
                    from urllib.parse import urlparse
                    if len(links)!=1 or urlparse(links[0]).scheme!='https' or urlparse(links[0]).hostname!='www.sandbox.paypal.com': raise ValueError('Invalid sandbox approval link')
                    result={'approval_url':links[0]}
                elif self.path.endswith('/capture'): result=service.capture(u,b['quote'])
                else: result=service.reconcile(u,b['quote'])
            elif self.path=='/api/ai/draft': result=BedrockIntake(store).draft(u,b.get('text',''),b.get('language','en'),photo=b.get('photo'))
            elif self.path=='/api/intake': result=store.intake(u,b,self.headers.get('Idempotency-Key'))
            elif self.path=='/api/inquiry': result=store.event(u,b['title'],b['guests'],b['notes'])
            elif self.path=='/api/quote': result=store.quote(u,b['event'],b['price'])
            elif self.path=='/api/approve': result=store.approve(u,b['quote'])
            elif self.path=='/api/book': result=store.book(u,b['quote'])
            elif self.path=='/api/logout':
                store.logout(self.token()); return self.reply(200,{'ok':True},'cf_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'+SECURE_COOKIE)
            else: return self.reply(404,{'error':'Not found'})
            self.reply(200,{'result':result})
        except PermissionError as e: self.reply(403,{'error':str(e)})
        except (ValueError,KeyError,TypeError,sqlite3.IntegrityError): self.reply(400,{'error':'Request could not be completed. Check details and current event state.'})
        except Exception: self.reply(500,{'error':'Request failed safely; review local state before retrying'})
if __name__=='__main__':
    if ORIGIN!='http://127.0.0.1:8080':raise RuntimeError('Use the WSGI candidate for HTTPS staging; do not expose the development server')
    print('Local development only: http://127.0.0.1:8080')
    HTTPServer(('127.0.0.1',8080),Handler).serve_forever()
