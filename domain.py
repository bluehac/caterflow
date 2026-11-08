"""Durable local development workflow; no production provider operations."""
import sqlite3, json, uuid, hashlib, secrets, time
from intake import validate_intake
from contextlib import contextmanager
from core import Quote

class Store:
    def __init__(self,path):
        self.path=path
        with self.db() as d:
            d.executescript('''
CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, role TEXT NOT NULL, salt TEXT NOT NULL, password TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY, owner TEXT NOT NULL, title TEXT NOT NULL, guests INTEGER NOT NULL, notes TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS quotes(id TEXT PRIMARY KEY, event TEXT NOT NULL, revision INTEGER NOT NULL, guests INTEGER NOT NULL, price TEXT NOT NULL, total TEXT NOT NULL, approved INTEGER NOT NULL DEFAULT 0, customer_approved INTEGER NOT NULL DEFAULT 0, order_id TEXT UNIQUE, capture_id TEXT UNIQUE, booked INTEGER NOT NULL DEFAULT 0, payment_status TEXT NOT NULL DEFAULT 'UNPAID', UNIQUE(event,revision));
CREATE TABLE IF NOT EXISTS audit(seq INTEGER PRIMARY KEY AUTOINCREMENT, actor TEXT NOT NULL, action TEXT NOT NULL, resource TEXT NOT NULL, at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS inquiry_requests(owner TEXT NOT NULL, request_key TEXT NOT NULL, payload_hash TEXT NOT NULL, event TEXT NOT NULL REFERENCES events(id), PRIMARY KEY(owner,request_key));
CREATE TABLE IF NOT EXISTS intake_details(event TEXT PRIMARY KEY REFERENCES events(id), payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), csrf TEXT NOT NULL, expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS payment_operations(quote TEXT NOT NULL REFERENCES quotes(id), kind TEXT NOT NULL CHECK(kind IN ('create','capture')), request_id TEXT NOT NULL UNIQUE, state TEXT NOT NULL CHECK(state IN ('NEW','IN_FLIGHT','SUCCEEDED','UNCERTAIN')), provider_id TEXT, created REAL NOT NULL, updated REAL NOT NULL, PRIMARY KEY(quote,kind));
CREATE TABLE IF NOT EXISTS webhook_events(id TEXT PRIMARY KEY, at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TRIGGER IF NOT EXISTS freeze_quote BEFORE UPDATE OF guests,price,total,event,revision ON quotes WHEN OLD.approved=1 BEGIN SELECT RAISE(ABORT,'Approved quotes are immutable'); END;
CREATE TRIGGER IF NOT EXISTS protect_audit_update BEFORE UPDATE ON audit BEGIN SELECT RAISE(ABORT,'Audit is append only'); END;
CREATE TRIGGER IF NOT EXISTS protect_audit_delete BEFORE DELETE ON audit BEGIN SELECT RAISE(ABORT,'Audit is append only'); END;
''')
    @contextmanager
    def db(self):
        d=sqlite3.connect(self.path,timeout=15); d.row_factory=sqlite3.Row
        try:
            d.execute('PRAGMA foreign_keys=ON'); d.execute('BEGIN IMMEDIATE'); yield d; d.commit()
        except: d.rollback(); raise
        finally: d.close()
    def add_user(self,uid,role,password):
        if role not in ('customer','caterer') or len(password)<12: raise ValueError('Invalid account configuration')
        salt=secrets.token_hex(16); digest=hashlib.scrypt(password.encode(),salt=salt.encode(),n=16384,r=8,p=1).hex()
        with self.db() as d: d.execute('INSERT INTO users VALUES(?,?,?,?)',(uid,role,salt,digest))
    def login(self,uid,password):
        with self.db() as d: u=d.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()
        if not u: return None
        h=hashlib.scrypt(password.encode(),salt=u['salt'].encode(),n=16384,r=8,p=1).hex()
        return {'id':uid,'role':u['role']} if secrets.compare_digest(h,u['password']) else None
    def log(self,d,u,a,r): d.execute('INSERT INTO audit(actor,action,resource) VALUES(?,?,?)',(u['id'],a,r))
    def event(self,u,title,guests,notes):
        if u['role']!='customer': raise PermissionError('Customer access required')
        if type(guests)!=int or not 1<=guests<=1000 or not title.strip() or len(title)>120 or len(notes)>4000: raise ValueError('Check event details')
        eid=uuid.uuid4().hex
        with self.db() as d:
            d.execute('INSERT INTO events VALUES(?,?,?,?,?)',(eid,u['id'],title,guests,notes)); self.log(d,u,'INQUIRY_CREATED',eid)
        return eid
    def allowed(self,d,u,eid):
        e=d.execute('SELECT * FROM events WHERE id=?',(eid,)).fetchone()
        if not e or (u['role']!='caterer' and e['owner']!=u['id']): raise PermissionError('Event unavailable')
        return e
    def quote(self,u,eid,price):
        if u['role']!='caterer': raise PermissionError('Caterer access required')
        qid=uuid.uuid4().hex
        with self.db() as d:
            e=self.allowed(d,u,eid); q=Quote(qid,e['guests'],price)
            if d.execute('SELECT 1 FROM quotes WHERE event=? AND (order_id IS NOT NULL OR customer_approved=1)',(eid,)).fetchone(): raise ValueError('Payment or customer approval already started; reconcile first')
            rev=d.execute('SELECT coalesce(max(revision),0)+1 FROM quotes WHERE event=?',(eid,)).fetchone()[0]
            d.execute('INSERT INTO quotes(id,event,revision,guests,price,total,approved) VALUES(?,?,?,?,?,?,1)',(qid,eid,rev,q.guests,q.unit_price,q.total)); self.log(d,u,'QUOTE_APPROVED',qid)
        return qid
    def get_quote(self,d,u,qid):
        q=d.execute('SELECT * FROM quotes WHERE id=?',(qid,)).fetchone()
        if not q: raise ValueError('Quote unavailable')
        self.allowed(d,u,q['event']); return q
    def approve(self,u,qid):
        if u['role']!='customer': raise PermissionError('Customer access required')
        with self.db() as d:
            q=self.get_quote(d,u,qid)
            if d.execute('SELECT max(revision) FROM quotes WHERE event=?',(q['event'],)).fetchone()[0]!=q['revision']: raise ValueError('Quote superseded')
            d.execute('UPDATE quotes SET customer_approved=1 WHERE id=?',(qid,)); self.log(d,u,'CUSTOMER_APPROVED',qid)
    def bind(self,u,qid,order):
        with self.db() as d:
            q=self.get_quote(d,u,qid)
            if u['role']!='customer' or not q['customer_approved'] or not q['approved']: raise PermissionError('Customer approval required')
            if not order or (q['order_id'] and q['order_id']!=order): raise ValueError('Conflicting order')
            d.execute('UPDATE quotes SET order_id=? WHERE id=?',(order,qid)); self.log(d,u,'ORDER_BOUND',qid)
    def reconcile(self,u,qid,response,merchant,event_id=None):
        # Only call with an authenticated provider response, never browser JSON.
        with self.db() as d:
            q=self.get_quote(d,u,qid)
            if event_id and d.execute('SELECT 1 FROM webhook_events WHERE id=?',(event_id,)).fetchone(): return dict(q)
            if q['payment_status']=='REVIEW_REQUIRED': raise ValueError('Payment hold requires operator review')
            model=Quote(qid,q['guests'],q['price'],True,q['order_id'],q['capture_id'])
            model.reconcile(response,merchant)
            if not q['customer_approved']: raise ValueError('Customer approval missing')
            operations=d.execute('SELECT * FROM payment_operations WHERE quote=?',(qid,)).fetchall()
            for operation in operations:
                if operation['provider_id'] not in (None,q['order_id']):
                    raise ValueError('Conflicting payment operation requires operator review')
            d.execute("UPDATE quotes SET capture_id=?,payment_status='COMPLETED' WHERE id=?",(model.capture_id,qid))
            # Only a fully validated COMPLETED receipt can resolve uncertainty.
            # Preserve original request IDs and never clear a payment hold here.
            for operation in operations:
                if operation['state'] in ('IN_FLIGHT','UNCERTAIN'):
                    d.execute("UPDATE payment_operations SET state='SUCCEEDED',provider_id=?,updated=? WHERE quote=? AND kind=?",
                              (q['order_id'],time.time(),qid,operation['kind']))
                    self.log(d,u,'PAYMENT_OPERATION_RECONCILED_'+operation['kind'].upper(),qid)
            if event_id: d.execute('INSERT INTO webhook_events(id) VALUES(?)',(event_id,))
            self.log(d,u,'PAYMENT_VERIFIED',qid)
            return dict(d.execute('SELECT * FROM quotes WHERE id=?',(qid,)).fetchone())
    def book(self,u,qid):
        if u['role']!='caterer': raise PermissionError('Caterer confirmation required')
        with self.db() as d:
            q=self.get_quote(d,u,qid)
            if not q['capture_id'] or q['payment_status']!='COMPLETED': raise ValueError('Verified completed payment required')
            d.execute('UPDATE quotes SET booked=1 WHERE id=?',(qid,)); self.log(d,u,'BOOKING_CONFIRMED',qid)
    def list(self,u):
        with self.db() as d:
            es=d.execute('SELECT * FROM events'+('' if u['role']=='caterer' else ' WHERE owner=?'),() if u['role']=='caterer' else (u['id'],)).fetchall()
            return [dict(e,quotes=[dict(q) for q in d.execute('SELECT * FROM quotes WHERE event=? ORDER BY revision DESC',(e['id'],))]) for e in es]

    def intake(self,u,data,request_key=None):
        if u['role']!='customer': raise PermissionError('Customer access required')
        data=validate_intake(data); eid=uuid.uuid4().hex
        if request_key is not None and (not isinstance(request_key,str) or not 16<=len(request_key)<=100 or not all(c.isalnum() or c=='-' for c in request_key)): raise ValueError('Invalid request key')
        payload_hash=hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()
        notes='Event date: '+data['event_date']+' | Location: '+data['location']+' | Service: '+data['service']+' | Menu: '+data['menu_notes']+' | Dietary requests (require review): '+data['dietary_notes']
        for key in ['event_time', 'venue_address', 'primary_protein', 'second_protein', 'extra_sides', 'dessert', 'beverages', 'accessibility_notes', 'organization', 'phone', 'budget_range', 'referral_source']:
            if data.get(key): notes+=' | '+key.replace('_',' ').capitalize()+': '+data[key]
        with self.db() as d:
            if request_key:
                prior=d.execute('SELECT * FROM inquiry_requests WHERE owner=? AND request_key=?',(u['id'],request_key)).fetchone()
                if prior:
                    if prior['payload_hash']!=payload_hash: raise ValueError('Request key already used for different details')
                    return prior['event']
            d.execute('INSERT INTO events VALUES(?,?,?,?,?)',(eid,u['id'],data['title'],data['guests'],notes))
            if request_key:d.execute('INSERT INTO inquiry_requests VALUES(?,?,?,?)',(u['id'],request_key,payload_hash,eid))
            d.execute('INSERT INTO intake_details VALUES(?,?)',(eid,json.dumps(data)))
            self.log(d,u,'REVIEWED_INTAKE_CREATED',eid)
        return eid
    def new_session(self,u):
        token=secrets.token_urlsafe(32); csrf=secrets.token_urlsafe(32)
        with self.db() as d:
            d.execute('DELETE FROM sessions WHERE expires<?',(time.time(),))
            d.execute('INSERT INTO sessions VALUES(?,?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),u['id'],csrf,time.time()+3600))
        return token,csrf
    def session(self,token):
        with self.db() as d:
            row=d.execute('SELECT s.csrf,s.expires,u.id,u.role FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires>?',(hashlib.sha256(token.encode()).hexdigest(),time.time())).fetchone()
        if not row: raise PermissionError('Please sign in')
        return {'user':{'id':row['id'],'role':row['role']},'csrf':row['csrf'],'expires':row['expires']}
    def logout(self,token):
        with self.db() as d: d.execute('DELETE FROM sessions WHERE token_hash=?',(hashlib.sha256(token.encode()).hexdigest(),))
    def begin_payment_operation(self,u,qid,kind):
        if u['role']!='customer' or kind not in ('create','capture'): raise PermissionError('Customer payment authority required')
        with self.db() as d:
            q=self.get_quote(d,u,qid)
            if not q['approved'] or not q['customer_approved']: raise PermissionError('Both quote approvals required')
            # Enforce webhook holds before any provider call or successful-operation
            # replay. Hiding checkout in the UI is not payment authorization.
            if q['payment_status']=='REVIEW_REQUIRED': raise ValueError('Payment hold requires operator review')
            if kind=='capture' and not q['order_id']: raise ValueError('Missing order')
            if kind=='capture' and (q['capture_id'] or q['payment_status']=='COMPLETED'):
                raise ValueError('Recorded payment requires authenticated reconciliation')
            row=d.execute('SELECT * FROM payment_operations WHERE quote=? AND kind=?',(qid,kind)).fetchone()
            if row:
                # Uncertain operations never retry automatically, even after restart.
                if row['state']!='SUCCEEDED': raise ValueError('Existing operation requires authenticated reconciliation')
                return dict(row)
            now=time.time(); key=uuid.uuid4().hex
            d.execute('INSERT INTO payment_operations VALUES(?,?,?,?,?,?,?)',(qid,kind,key,'IN_FLIGHT',None,now,now))
            self.log(d,u,'PAYMENT_OPERATION_STARTED',qid)
            return {'quote':qid,'kind':kind,'request_id':key,'state':'IN_FLIGHT','provider_id':None}
    def finish_payment_operation(self,u,qid,kind,provider_id=None):
        with self.db() as d:
            self.get_quote(d,u,qid)
            existing=d.execute('SELECT * FROM payment_operations WHERE quote=? AND kind=?',(qid,kind)).fetchone()
            if existing and existing['state']=='SUCCEEDED':
                # A webhook/readback may finish the operation before its request
                # returns or times out. Never downgrade that verified success.
                if provider_id and provider_id!=existing['provider_id']:
                    raise ValueError('Conflicting provider operation')
                return
            if not provider_id: state='UNCERTAIN'
            else: state='SUCCEEDED'
            changed=d.execute("UPDATE payment_operations SET state=?,provider_id=?,updated=? WHERE quote=? AND kind=? AND state='IN_FLIGHT'",(state,provider_id,time.time(),qid,kind)).rowcount
            if not changed: raise ValueError('Operation is not in flight')
            self.log(d,u,'PAYMENT_OPERATION_'+state,qid)
    def payment_hold(self,qid,event_id,reason,response,merchant):
        with self.db() as d:
            q=d.execute('SELECT * FROM quotes WHERE id=?',(qid,)).fetchone()
            if not q or response.get('id')!=q['order_id']:raise ValueError('Order mismatch')
            units=response.get('purchase_units',[])
            if len(units)!=1 or units[0].get('custom_id')!=qid or units[0].get('payee',{}).get('merchant_id')!=merchant or not merchant:raise ValueError('Payment context mismatch')
            if d.execute('SELECT 1 FROM webhook_events WHERE id=?',(event_id,)).fetchone():return
            d.execute("UPDATE quotes SET payment_status='REVIEW_REQUIRED',booked=0 WHERE id=?",(qid,))
            d.execute('INSERT INTO webhook_events(id) VALUES(?)',(event_id,))
            self.log(d,{'id':'paypal-webhook'},reason,qid)
