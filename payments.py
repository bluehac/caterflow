"""Server-only orchestration. Never accepts provider receipts from the browser."""
from core import Quote
class Payments:
    def __init__(self,store,provider): self.store=store;self.provider=provider
    def snapshot(self,u,qid):
        with self.store.db() as d: return dict(self.store.get_quote(d,u,qid))
    def create(self,u,qid,return_url):
        if not self.provider.configured: raise RuntimeError('Sandbox connection required')
        op=self.store.begin_payment_operation(u,qid,'create')
        if op['state']=='SUCCEEDED': return self.provider.order(op['provider_id'])
        q=self.snapshot(u,qid)
        try:
            response=self.provider.create(Quote(qid,q['guests'],q['price'],True),return_url,key=op['request_id'])
            oid=response.get('id')
            if not isinstance(oid,str) or not oid: raise ValueError('Provider did not acknowledge order')
            self.store.bind(u,qid,oid)
        except Exception:
            self.store.finish_payment_operation(u,qid,'create')
            raise RuntimeError('Order outcome needs reconciliation; do not retry automatically') from None
        self.store.finish_payment_operation(u,qid,'create',oid)
        return response
    def capture(self,u,qid):
        if not self.provider.configured: raise RuntimeError('Sandbox connection required')
        op=self.store.begin_payment_operation(u,qid,'capture');q=self.snapshot(u,qid)
        if op['state']=='SUCCEEDED': return self.reconcile(u,qid)
        try:
            self.provider.capture(q['order_id'],qid,key=op['request_id'])
            # Authenticated fresh readback is authoritative, not browser callbacks.
            response=self.provider.order(q['order_id'])
            self.store.reconcile(u,qid,response,self.provider.merchant)
        except Exception:
            self.store.finish_payment_operation(u,qid,'capture')
            raise RuntimeError('Payment is not verified; reconciliation required') from None
        self.store.finish_payment_operation(u,qid,'capture',q['order_id'])
        return {'payment_status':'COMPLETED','booking_status':'AWAITING_CATERER'}
    def reconcile(self,u,qid):
        q=self.snapshot(u,qid)
        if not q['order_id']: raise ValueError('No known order; manual provider investigation required')
        response=self.provider.order(q['order_id'])
        self.store.reconcile(u,qid,response,self.provider.merchant)
        return {'payment_status':'COMPLETED','booking_status':'BOOKED' if q['booked'] else 'AWAITING_CATERER'}
