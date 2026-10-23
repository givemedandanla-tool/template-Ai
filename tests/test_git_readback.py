"""原生 Git 讀回的真實本機 bare remote 測試，不呼叫 GitHub／CI。"""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from git_readback import readback
from dev_checkpoint import prepare


class GitReadbackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.local, self.remote = self.root/'local', self.root/'remote.git'
        subprocess.run(['git','init','--bare',str(self.remote)], check=True, capture_output=True)
        subprocess.run(['git','init','-b','dev',str(self.local)], check=True, capture_output=True)
        self.git('config','user.name','Synthetic Test')
        self.git('config','user.email','synthetic@example.test')
        self.git('config','commit.gpgsign','false')
        self.git('remote','add','origin',str(self.remote))
        (self.local/'README.md').write_text('Synthetic checkpoint fixture\n')
        self.git('add','README.md')
        self.git('commit','-m','seed')
        self.git('push','origin','HEAD:refs/heads/dev')

    def tearDown(self):
        self.temp.cleanup()

    def git(self,*args):
        return subprocess.check_output(['git','-C',str(self.local),*args],stderr=subprocess.DEVNULL).decode().strip()

    def test_fresh_fetch_and_full_tree_match_real_remote_without_credentials(self):
        result = readback(self.local, ref='refs/heads/dev')
        self.assertEqual(result['commit'],self.git('rev-parse','HEAD'))
        self.assertEqual(result['tree'],self.git('rev-parse','HEAD^{tree}'))
        self.assertEqual(result['files'],1)
        self.assertEqual(result['method'],'NATIVE_GIT_FETCH_AND_EXACT_TREE_BLOB_READBACK')

    def test_unpushed_head_is_not_remote_verified(self):
        (self.local/'README.md').write_text('Synthetic unpushed change\n')
        self.git('commit','-am','local-only')
        with self.assertRaisesRegex(ValueError,'HEAD'):
            readback(self.local,ref='refs/heads/dev')

    def test_checkpoint_receipt_is_source_verified_and_immutable(self):
        sha=self.git('rev-parse','HEAD')
        prepare(self.local,'CP-SYNTHETIC',sha,'Synthetic scope','Next synthetic task',[])
        self.git('add','docs/checkpoints/CP-SYNTHETIC.json')
        self.git('commit','-m','checkpoint')
        self.git('push','origin','HEAD:refs/heads/dev')
        result=readback(self.local,ref='refs/heads/dev',checkpoint_id='CP-SYNTHETIC')
        self.assertEqual(result['receipt']['phase'],'REMOTE_VERIFIED')
        self.assertIn('Native Git',result['receipt']['verification'])
        self.assertIn('no REST API claim',result['receipt']['verification'])
        with self.assertRaises(FileExistsError):
            readback(self.local,ref='refs/heads/dev',checkpoint_id='CP-SYNTHETIC')

    def test_non_branch_or_url_input_rejected_before_network_operation(self):
        for arguments in ({'remote':'https://example.test/private'}, {'ref':'refs/tags/v1'}, {'remote':'--upload-pack'}):
            with self.assertRaises(ValueError):
                readback(self.local,**arguments)
