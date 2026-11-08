"""Deterministic validation for customer-reviewed intake; no model authority."""
from datetime import date
import re
DETAIL_FIELDS={'event_time': 200, 'venue_address': 200, 'primary_protein': 200, 'second_protein': 200, 'extra_sides': 200, 'dessert': 200, 'beverages': 200, 'accessibility_notes': 500, 'organization': 200, 'phone': 200, 'budget_range': 200, 'referral_source': 200}
FIELDS=set(DETAIL_FIELDS)|{'title','guests','event_date','location','service','menu_notes','dietary_notes','contact_name','contact_email','language','consent'}
def validate_intake(data):
    if not isinstance(data,dict) or set(data)-FIELDS: raise ValueError('Unknown intake fields')
    result={}
    for k,limit in {'title':120,'location':240,'menu_notes':1500,'dietary_notes':1000,'contact_name':120,'contact_email':254}.items():
        v=data.get(k,'')
        if not isinstance(v,str) or len(v)>limit: raise ValueError('Invalid '+k)
        result[k]=v.strip()
    for k,limit in DETAIL_FIELDS.items():
        v=data.get(k,'')
        if not isinstance(v,str) or len(v)>limit: raise ValueError('Invalid '+k)
        if v.strip(): result[k]=v.strip()
    if not all(result[k] for k in ['title','location','contact_name','contact_email']): raise ValueError('Complete required fields')
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',result['contact_email']): raise ValueError('Check email')
    g=data.get('guests')
    if type(g)!=int or not 10<=g<=1000: raise ValueError('Guests must be 10–1000')
    result['guests']=g
    day=date.fromisoformat(data.get('event_date',''))
    if day<date.today(): raise ValueError('Choose a future event date')
    result['event_date']=day.isoformat()
    if data.get('service') not in ['delivery','pickup','staffed','unsure']: raise ValueError('Choose service')
    if data.get('language') not in ['en','es']: raise ValueError('Choose language')
    if data.get('consent') is not True: raise ValueError('Inquiry consent required')
    result.update(service=data['service'],language=data['language'],consent=True)
    return result

def validate_ai_draft(data):
    # AI may only suggest non-authoritative event fields. No price or state fields.
    allowed={'title','guests','event_date','location','menu_notes','dietary_notes','next_question'}
    if not isinstance(data,dict) or set(data)-allowed: raise ValueError('Prohibited AI fields')
    for k,v in data.items():
        if k=='guests':
            if v is not None and (type(v)!=int or not 1<=v<=1000): raise ValueError('Invalid AI guest count')
        elif v is not None and (not isinstance(v,str) or len(v)>1500): raise ValueError('Invalid AI field')
    return data
