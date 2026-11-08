"""Sandbox-only transport. No secret values appear in responses or logs."""
import os,json,base64,urllib.request,urllib.error,re
BASE='https://api-m.sandbox.paypal.com'
class PayPal:
    def __init__(self):
        self.client=os.environ.get('PAYPAL_CLIENT_ID'); self.secret=os.environ.get('PAYPAL_CLIENT_SECRET'); self.merchant=os.environ.get('PAYPAL_MERCHANT_ID'); self.webhook=os.environ.get('PAYPAL_WEBHOOK_ID')
    @property
    def configured(self): return bool(self.client and self.secret and self.merchant)
    def _send(self,path,method,body,headers):
        req=urllib.request.Request(BASE+path,data=body,headers=headers,method=method)
        try:
            with urllib.request.urlopen(req,timeout=20) as r: return json.load(r)
        except urllib.error.HTTPError as e:
            # Never surface token-bearing request details or arbitrary provider text.
            raise RuntimeError('PayPal request rejected; reconcile before retrying') from None
        except (OSError,ValueError): raise RuntimeError('PayPal outcome uncertain; reconcile before retrying') from None
    def call(self,path,method='GET',body=None,key=None):
        if not self.configured: raise RuntimeError('PayPal sandbox connection is not configured')
        auth=base64.b64encode((self.client+':'+self.secret).encode()).decode()
        token=self._send('/v1/oauth2/token','POST',b'grant_type=client_credentials',{'Authorization':'Basic '+auth,'Content-Type':'application/x-www-form-urlencoded'})['access_token']
        headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'}
        if key: headers['PayPal-Request-Id']=key
        return self._send(path,method,None if body is None else json.dumps(body).encode(),headers)
    def order(self,oid):
        if not re.fullmatch('[A-Za-z0-9]+',oid): raise ValueError('Invalid order')
        return self.call('/v2/checkout/orders/'+oid)
    def create(self,quote,return_url,key=None):
        payload=quote.order_payload(); payload['purchase_units'][0]['payee']={'merchant_id':self.merchant}
        payload['payment_source']={'paypal':{'experience_context':{'return_url':return_url,'cancel_url':return_url,'user_action':'PAY_NOW'}}}
        return self.call('/v2/checkout/orders','POST',payload,key or 'create-'+quote.quote_id)
    def capture(self,oid,qid,key=None):
        if not re.fullmatch('[A-Za-z0-9]+',oid): raise ValueError('Invalid order')
        return self.call('/v2/checkout/orders/'+oid+'/capture','POST',{},key or 'capture-'+qid)
    def verify_webhook(self,event,headers):
        if not self.webhook: raise RuntimeError('Webhook verification is not configured')
        names={'auth_algo':'paypal-auth-algo','cert_url':'paypal-cert-url','transmission_id':'paypal-transmission-id','transmission_sig':'paypal-transmission-sig','transmission_time':'paypal-transmission-time'}
        body={k:headers.get(v) for k,v in names.items()}
        if not all(body.values()): raise ValueError('Missing signature headers')
        body.update(webhook_id=self.webhook,webhook_event=event)
        if self.call('/v1/notifications/verify-webhook-signature','POST',body).get('verification_status')!='SUCCESS': raise ValueError('Invalid webhook signature')
