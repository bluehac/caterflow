"""Single-instance staging only. TLS proxy and persistent volume are prerequisites."""
bind='127.0.0.1:8000'
workers=1
worker_class='sync'
threads=1
timeout=60
limit_request_line=4094
limit_request_fields=40
limit_request_field_size=4096
accesslog=None
errorlog='-'
capture_output=False
forwarded_allow_ips=''
forwarder_headers=''
secure_scheme_headers={}
