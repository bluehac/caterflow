"""Execute the real workspace script with a minimal DOM and server fixtures."""
import json, subprocess, unittest
from pathlib import Path

class PaymentUiTests(unittest.TestCase):
 def render(self, role, payment_status, booked=0):
  script=Path('static/index.html').read_text().split('<script>')[1].split('</script>')[0]
  fixture={'csrf':'test','user':{'id':'demo','role':role},'sandbox_checkout':True,'events':[{'title':'Synthetic event','guests':4,'notes':'test','quotes':[{'id':'q','revision':1,'total':'100.00','customer_approved':1,'capture_id':'CAP1','order_id':'ORDER1','payment_status':payment_status,'booked':booked}]}]}
  harness="""
class Node {
 constructor(tag,text=''){this.tag=tag;this.textContent=text;this.children=[]}
 append(...items){this.children.push(...items)}
 replaceChildren(...items){this.children=items}
}
const roots={root:new Node('div'),notice:new Node('p')};
global.document={getElementById:id=>roots[id],createElement:tag=>new Node(tag)};
global.fetch=async()=>({ok:true,json:async()=>(FIXTURE)});
""".replace('FIXTURE',json.dumps(fixture))
  end="\nsetImmediate(()=>{function flatten(n){return [n.textContent,...n.children.flatMap(flatten)]};console.log(JSON.stringify(flatten(roots.root)))})"
  return json.loads(subprocess.check_output(['node','-e',harness+script+end],text=True))
 def test_reversal_hold_hides_verified_and_booking_actions(self):
  for role in ['customer','caterer']:
   for booked in [0,1]:
    text=self.render(role,'REVIEW_REQUIRED',booked)
    self.assertIn('Payment needs review',text)
    for forbidden in ['Booking confirmed','Payment verified. Awaiting caterer confirmation.','Confirm booking','Verify and complete sandbox payment','Continue to PayPal sandbox']:
     self.assertNotIn(forbidden,text)
 def test_completed_payment_allows_caterer_confirmation(self):
  text=self.render('caterer','COMPLETED')
  self.assertIn('Confirm booking',text)
  self.assertNotIn('Booking confirmed',text)
 def test_customer_cannot_confirm_booking(self):
  self.assertNotIn('Confirm booking',self.render('customer','COMPLETED'))
