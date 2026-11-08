import argparse,getpass,os
from domain import Store
p=argparse.ArgumentParser();p.add_argument('role',choices=['customer','caterer']);p.add_argument('id');a=p.parse_args()
Store(os.environ.get('CATERFLOW_DB','caterflow.db')).add_user(a.id,a.role,getpass.getpass('Local account password (12+ characters): '))
print('Local account created')
