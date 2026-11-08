"""Operator-configured estimates. No AI arithmetic, inferred rates, or booking authority."""
from decimal import Decimal,ROUND_HALF_UP
import hashlib,json
class EstimateUnavailable(ValueError):pass

def money(value):
    if not isinstance(value,str):raise ValueError('Configured decimals must be strings')
    n=Decimal(value)
    if not n.is_finite() or n<0 or n>1000000:raise ValueError('Invalid configured amount')
    return n

def estimate(policy,selection):
    # Price policy is operator-owned, never taken from the customer's request.
    if not isinstance(policy,dict) or policy.get('approved') is not True:raise EstimateUnavailable('Pricing is awaiting operator approval')
    if not policy.get('version') or not policy.get('tax_source') or not policy.get('valid_until'):raise EstimateUnavailable('A dated, sourced pricing policy is required')
    from datetime import date
    if date.fromisoformat(policy['valid_until'])<date.today():raise EstimateUnavailable('Pricing policy needs review')
    if not isinstance(selection,dict) or set(selection)-{'guests','package','service','tax_zone','addons'}:raise ValueError('Unknown selection fields')
    guests=selection.get('guests')
    if type(guests)!=int or not policy['min_guests']<=guests<=policy['max_guests']:raise ValueError('Check guest quantity')
    package=policy['packages'].get(selection.get('package'))
    service=policy['services'].get(selection.get('service'))
    zone=policy['tax_zones'].get(selection.get('tax_zone'))
    if package is None or service is None or zone is None:raise EstimateUnavailable('This menu, service or location requires a custom quote')
    if set(service)!={'fixed','rate','taxable'} or type(service['taxable'])!=bool:raise EstimateUnavailable('Service tax treatment must be explicit')
    cents=lambda n:n.quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
    food=cents(money(package['per_guest'])*guests)
    addons=selection.get('addons',[])
    if not isinstance(addons,list) or len(addons)>20 or any(not isinstance(k,str) for k in addons) or len(set(addons))!=len(addons):raise ValueError('Check add-ons')
    lines=[{'label':package['label'],'amount':str(food)}]
    for key in addons:
        item=policy['addons'].get(key)
        if item is None:raise EstimateUnavailable('Add-on requires a custom quote')
        amount=cents(money(item['per_guest'])*guests);food+=amount;lines.append({'label':item['label'],'amount':str(amount)})
    rate=money(service['rate'])
    taxrate=money(zone['rate'])
    if rate>1 or taxrate>1:raise ValueError('Rates must be fractions between zero and one')
    fee=cents(money(service['fixed'])+food*rate)
    taxable=food+(fee if service['taxable'] else Decimal('0'))
    tax=cents(taxable*taxrate);total=food+fee+tax
    return {'status':'ESTIMATE_ONLY','currency':'USD','policy_version':policy['version'],'policy_hash':hashlib.sha256(json.dumps(policy,sort_keys=True).encode()).hexdigest(),'food':str(cents(food)),'service_fee':str(fee),'taxable_base':str(cents(taxable)),'tax':str(tax),'total':str(cents(total)),'per_guest':str(cents(total/guests)),'line_items':lines,'tax_source':policy['tax_source'],'valid_until':policy['valid_until'],'requires_caterer_review':True,'booking_confirmed':False}
