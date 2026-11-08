import unittest
from estimates import estimate,EstimateUnavailable
class EstimateTests(unittest.TestCase):
 def setUp(self):
  self.policy={'approved':True,'version':'SYNTHETIC_TEST_ONLY','valid_until':'2099-01-01','tax_source':'Synthetic fixture, not a jurisdiction rate','min_guests':25,'max_guests':1000,'packages':{'test':{'label':'Synthetic package','per_guest':'24.99'}},'services':{'pickup':{'fixed':'0','rate':'0','taxable':True},'service':{'fixed':'50','rate':'.18','taxable':True}},'tax_zones':{'synthetic':{'rate':'.10'}},'addons':{'dessert':{'label':'Synthetic dessert','per_guest':'2.50'}}}
  self.selection={'guests':25,'package':'test','service':'pickup','tax_zone':'synthetic'}
 def test_exact_rounding_itemization_and_nonbooking(self):
  r=estimate(self.policy,self.selection);self.assertEqual((r['food'],r['tax'],r['total']),('624.75','62.48','687.23'));self.assertFalse(r['booking_confirmed'])
 def test_fee_tax_base_and_addons(self):
  r=estimate(self.policy,dict(self.selection,service='service',addons=['dessert']));self.assertEqual((r['food'],r['service_fee'],r['taxable_base'],r['tax'],r['total']),('687.25','173.71','860.96','86.10','947.06'))
 def test_missing_unapproved_expired_policy_blocks(self):
  for patch in ({'approved':False},{'tax_source':''},{'valid_until':'2000-01-01'}):
   with self.assertRaises(EstimateUnavailable):estimate(dict(self.policy,**patch),self.selection)
 def test_unknown_location_and_price_injection_block(self):
  for patch in ({'tax_zone':'unknown'},{'total':'1'},{'guests':True},{'guests':24}):
   with self.assertRaises(ValueError):estimate(self.policy,dict(self.selection,**patch))
 def test_no_silent_free_unknown_addon_or_duplicate(self):
  for addons in (['unknown'],['dessert','dessert']):
   with self.assertRaises(ValueError):estimate(self.policy,dict(self.selection,addons=addons))
