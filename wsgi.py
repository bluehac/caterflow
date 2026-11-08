"""Undeployed single-instance staging candidate; run behind a buffering TLS proxy.

Reuses the existing request actions without constructing a socket server.
Never trust forwarded scheme, host or client-IP headers supplied by clients.
"""
import io
import os
from pathlib import Path
from email.message import Message
from http import HTTPStatus

if not os.environ.get('CATERFLOW_PUBLIC_ORIGIN','').startswith('https://'):
    raise RuntimeError('HTTPS staging origin required')
db=os.environ.get('CATERFLOW_DB','')
if not db or not Path(db).is_absolute() or not Path(db).parent.is_dir():
    raise RuntimeError('Absolute database path on an operator-provisioned persistent volume required')

from app import Handler

class WsgiHandler(Handler):
    def __init__(self,environ):
        self.path=environ.get('PATH_INFO','/')
        self.client_address=(environ.get('REMOTE_ADDR','unknown'),0)
        self.headers=Message()
        for key,value in environ.items():
            if key.startswith('HTTP_'):self.headers[key[5:].replace('_','-')]=value
        for key in ('CONTENT_LENGTH','CONTENT_TYPE'):
            if key in environ:self.headers[key.replace('_','-')]=environ[key]
        self.rfile=environ['wsgi.input'];self.wfile=io.BytesIO();self.response_headers=[]
    def send_response(self,status,message=None):self.response_status=status
    def send_header(self,key,value):self.response_headers.append((key,str(value)))
    def end_headers(self):pass

def application(environ,start_response):
    request=WsgiHandler(environ)
    method=environ.get('REQUEST_METHOD','')
    try:
        if method=='GET':request.do_GET()
        elif method=='POST':request.do_POST()
        else:request.reply(405,{'error':'Method not allowed'})
    except Exception:
        request.wfile=io.BytesIO();request.response_headers=[]
        request.reply(500,{'error':'Request failed safely'})
    start_response(str(request.response_status)+' '+HTTPStatus(request.response_status).phrase,request.response_headers)
    return [request.wfile.getvalue()]
