"""Bounded abuse controls. Tokens and customer content are never logged."""
import hashlib,json,os,time
from urllib.request import Request,urlopen

class RateLimited(Exception):pass
class VerificationUnavailable(Exception):pass

def reserve(store,owner,kind,now=None):
    """Cross-worker rolling limits, including rejected/provider-failed attempts."""
    limits={'ai':((60,3),(86400,10)),'intake':((600,5),(86400,20))}
    if kind not in limits:raise ValueError('Unknown guarded action')
    at=time.time() if now is None else now
    key=hashlib.sha256(owner.encode()).hexdigest()
    with store.db() as d:
        d.execute('CREATE TABLE IF NOT EXISTS abuse_attempts(owner TEXT NOT NULL,kind TEXT NOT NULL,at REAL NOT NULL)')
        d.execute('CREATE INDEX IF NOT EXISTS abuse_recent ON abuse_attempts(owner,kind,at)')
        d.execute('DELETE FROM abuse_attempts WHERE at<=?',(at-86400,))
        for window,cap in limits[kind]:
            if d.execute('SELECT count(*) FROM abuse_attempts WHERE owner=? AND kind=? AND at>?',(key,kind,at-window)).fetchone()[0]>=cap:
                raise RateLimited('Too many requests. Wait before trying again; your draft is still available.')
        if d.execute('SELECT count(*) FROM abuse_attempts').fetchone()[0]>=10000:
            raise RateLimited('Request capacity reached. Please try later.')
        d.execute('INSERT INTO abuse_attempts VALUES(?,?,?)',(key,kind,at))

def public_config():
    enabled=os.environ.get('CATERFLOW_TURNSTILE_ENABLED')=='true'
    return {'enabled':enabled,'sitekey':os.environ.get('CATERFLOW_TURNSTILE_SITEKEY','') if enabled else ''}

def verify(token,action,hostname,opener=urlopen):
    if os.environ.get('CATERFLOW_TURNSTILE_ENABLED')!='true':return
    secret=os.environ.get('CATERFLOW_TURNSTILE_SECRET','')
    sitekey=os.environ.get('CATERFLOW_TURNSTILE_SITEKEY','')
    if not secret or not sitekey:raise VerificationUnavailable('Secure verification is not configured. Please try later.')
    if not isinstance(token,str) or not 1<=len(token)<=2048:raise PermissionError('Complete secure verification and try again')
    payload=json.dumps({'secret':secret,'response':token}).encode()
    request=Request('https://challenges.cloudflare.com/turnstile/v0/siteverify',data=payload,headers={'Content-Type':'application/json'},method='POST')
    try:
        with opener(request,timeout=5) as response:
            data=json.loads(response.read(16385))
    except Exception:raise VerificationUnavailable('Secure verification is unavailable. Your draft is still available.') from None
    if not isinstance(data,dict) or data.get('success') is not True or data.get('hostname')!=hostname or data.get('action')!=action:
        raise PermissionError('Secure verification failed. Please try again')
