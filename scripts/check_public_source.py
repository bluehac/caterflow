"""Bounded public-source hygiene check. Not a complete credential detector."""
import pathlib,re,subprocess,sys
patterns={
 'private key':rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
 'AWS access identifier':rb'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b',
 'GitHub credential':rb'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})\b',
 'Bedrock API credential':rb'\bABSK[A-Za-z0-9+/=_-]{30,}',
 'provider credential':rb'\b(?:sk_live_|sk_test_|sk-proj-|xoxb-)[A-Za-z0-9_-]{16,}',
}
findings=[]
files=subprocess.check_output(['git','ls-files','-z']).decode().split('\0')
for name in filter(None,files):
 p=pathlib.PurePosixPath(name)
 if p.name=='.env' or p.name.startswith('.env.') or p.suffix in ('.db','.sqlite','.sqlite3','.pem','.key') or re.search(r'(?:secret|credential).*\.json$',p.name,re.I):
  findings.append((name,'private/runtime file type'))
objects=subprocess.check_output(['git','rev-list','--objects','--all']).decode().splitlines()
for record in objects:
 oid,_,name=record.partition(' ')
 info=subprocess.check_output(['git','cat-file','-s',oid]).strip()
 kind=subprocess.check_output(['git','cat-file','-t',oid]).strip()
 if kind!=b'blob':continue
 if int(info)>2_000_000:
  findings.append((name or oid,'blob exceeds scanner bound; review required'));continue
 data=subprocess.check_output(['git','cat-file','blob',oid])
 for label,pattern in patterns.items():
  if re.search(pattern,data):findings.append((name or oid,label))
if findings:
 for name,label in findings:print('REVIEW REQUIRED:',name,'-',label)
 sys.exit(1)
print('PASS: tracked-file hygiene and high-confidence credential patterns across reachable local Git history')
print('Limit: not a comprehensive secret detector; provider scanning and human review remain necessary.')
