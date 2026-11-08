"""Owner-operated local secret setup; never prints credential values."""
import argparse
import base64
import getpass
import json
import os
from pathlib import Path
import stat

KEYS=('PAYPAL_CLIENT_ID','PAYPAL_CLIENT_SECRET','PAYPAL_MERCHANT_ID','PAYPAL_WEBHOOK_ID')

def read_config(path):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd) as stream:
        info=os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or stat.S_IMODE(info.st_mode)!=0o600:
            raise ValueError('Configuration must be an owner-only regular file with mode 600')
        if info.st_size>8192:raise ValueError('Configuration too large')
        data=json.load(stream)
    if not isinstance(data,dict) or set(data)!=set(KEYS):raise ValueError('Invalid configuration fields')
    if any(not isinstance(v,str) or not v or len(v)>2000 or any(c.isspace() for c in v) for v in data.values()):
        raise ValueError('Invalid configuration values')
    return data

def load_configured_secrets():
    path=os.environ.get('CATERFLOW_SECRET_FILE')
    if path:
        data=read_config(path)
        if any(k in os.environ and os.environ[k]!=v for k,v in data.items()):
            raise ValueError('Conflicting sandbox configuration')
        os.environ.update(data)

def save_config(path,data):
    # Exclusive create prevents accidental replacement; never follow a symlink.
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'w') as stream:
        json.dump(data,stream)
        stream.flush()
        os.fsync(stream.fileno())

def check_connection(data,provider=None):
    # OAuth checks client authentication only, not merchant ownership or webhooks.
    if provider is None:
        from paypal import PayPal
        provider=PayPal()
    auth=base64.b64encode((data['PAYPAL_CLIENT_ID']+':'+data['PAYPAL_CLIENT_SECRET']).encode()).decode()
    response=provider._send('/v1/oauth2/token','POST',b'grant_type=client_credentials',{'Authorization':'Basic '+auth,'Content-Type':'application/x-www-form-urlencoded'})
    if not isinstance(response.get('access_token'),str) or not response['access_token']:
        raise ValueError('Sandbox authentication not verified')
    return {'sandbox_client_authentication':'verified','merchant_ownership':'unverified','webhook_delivery':'unverified','payments':'untested'}

def main():
    parser=argparse.ArgumentParser(description='Local sandbox configuration; no credentials in chat or command arguments.')
    parser.add_argument('action',choices=['configure','check'])
    parser.add_argument('--file',required=True,help='Absolute configuration file outside the source directory')
    args=parser.parse_args()
    try:
        path=Path(args.file)
        if not path.is_absolute() or path.resolve().is_relative_to(Path(__file__).resolve().parent):
            raise ValueError('Choose an absolute path outside the source directory')
        if args.action=='configure':
            data={key:getpass.getpass(key+' (sandbox only, hidden): ').strip() for key in KEYS}
            if any(not value or any(c.isspace() for c in value) or len(value)>2000 for value in data.values()):
                raise ValueError('All four valid sandbox values are required')
            save_config(path,data)
            print('Sandbox configuration saved privately. Payment routes remain disabled.')
        else:print(json.dumps(check_connection(read_config(path))))
        return 0
    except Exception:
        print('Setup/check failed. Verify the sandbox values, file permissions and connection locally. No payment was created or captured.')
        return 1

if __name__=='__main__':raise SystemExit(main())
