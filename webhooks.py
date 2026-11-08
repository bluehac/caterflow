"""Verify webhook signatures before lookup; use authenticated readback for state."""
class Webhooks:
    def __init__(self,store,provider):self.store=store;self.provider=provider
    def handle(self,event,headers):
        self.provider.verify_webhook(event,{k.lower():v for k,v in headers.items()})
        eid=event.get('id');kind=event.get('event_type');resource=event.get('resource',{})
        if not isinstance(eid,str) or not eid or len(eid)>200:raise ValueError('Invalid event id')
        allowed={'PAYMENT.CAPTURE.COMPLETED','PAYMENT.CAPTURE.PENDING','PAYMENT.CAPTURE.DENIED','PAYMENT.CAPTURE.REFUNDED','PAYMENT.CAPTURE.REVERSED'}
        if kind not in allowed:return {'ignored':True}
        oid=resource.get('supplementary_data',{}).get('related_ids',{}).get('order_id')
        # Some refund events omit an order id. Resolve by the known capture id.
        cid=resource.get('supplementary_data',{}).get('related_ids',{}).get('capture_id') or resource.get('id')
        with self.store.db() as d:
            if d.execute('SELECT 1 FROM webhook_events WHERE id=?',(eid,)).fetchone():return {'duplicate':True}
            q=d.execute('SELECT * FROM quotes WHERE order_id=?',(oid,)).fetchone() if oid else None
            if q is None and cid:q=d.execute('SELECT * FROM quotes WHERE capture_id=?',(cid,)).fetchone()
            if q is None:raise ValueError('Unknown payment; manual reconciliation required')
            q=dict(q); owner=d.execute('SELECT owner FROM events WHERE id=?',(q['event'],)).fetchone()[0]
        # Never accept webhook body payment claims as financial authority.
        response=self.provider.order(q['order_id'])
        actor={'id':owner,'role':'customer'}
        if kind=='PAYMENT.CAPTURE.COMPLETED':
            self.store.reconcile(actor,q['id'],response,self.provider.merchant,eid)
        else:
            # Conservative hold, including late/out-of-order events. Only an
            # operator recovery process may clear the hold after investigation.
            self.store.payment_hold(q['id'],eid,kind,response,self.provider.merchant)
        return {'accepted':True}
