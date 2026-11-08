import os,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from sandbox_config import KEYS,save_config,read_config,load_configured_secrets,check_connection

class SandboxConfigTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'sandbox.json'
  self.data={k:'synthetic-'+str(i) for i,k in enumerate(KEYS)}
 def tearDown(self):self.tmp.cleanup()
 def test_private_file_roundtrip_and_no_overwrite(self):
  save_config(self.path,self.data)
  self.assertEqual(read_config(self.path),self.data)
  with self.assertRaises(FileExistsError):save_config(self.path,self.data)
 def test_world_readable_and_symlink_rejected(self):
  save_config(self.path,self.data);self.path.chmod(0o644)
  with self.assertRaises(ValueError):read_config(self.path)
  self.path.chmod(0o600);link=Path(self.tmp.name)/'link';link.symlink_to(self.path)
  with self.assertRaises(OSError):read_config(link)
 def test_unknown_fields_rejected(self):
  save_config(self.path,dict(self.data,CATERFLOW_PAYPAL_ENABLED='true'))
  with self.assertRaises(ValueError):read_config(self.path)
 def test_load_does_not_enable_payments(self):
  save_config(self.path,self.data)
  with patch.dict(os.environ,{'CATERFLOW_SECRET_FILE':str(self.path)},clear=True):
   load_configured_secrets()
   self.assertNotIn('CATERFLOW_PAYPAL_ENABLED',os.environ)
 def test_conflicting_config_rejected(self):
  save_config(self.path,self.data)
  with patch.dict(os.environ,{'CATERFLOW_SECRET_FILE':str(self.path),'PAYPAL_CLIENT_ID':'different'},clear=True):
   with self.assertRaises(ValueError):load_configured_secrets()
 def test_auth_check_never_creates_payment_or_returns_token(self):
  provider=Mock();provider._send.return_value={'access_token':'synthetic-token'}
  result=check_connection(self.data,provider)
  self.assertNotIn('synthetic-token',str(result))
  self.assertEqual(provider._send.call_args.args[0],'/v1/oauth2/token')
  provider.create.assert_not_called();provider.capture.assert_not_called()
