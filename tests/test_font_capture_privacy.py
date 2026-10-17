"""Actual repository ignore policy must prevent raw fonts/private capture staging."""
import subprocess,unittest
from pathlib import Path

class FontCapturePrivacyTests(unittest.TestCase):
    def test_raw_font_formats_and_private_capture_libraries_are_ignored_by_actual_git(self):
        root=Path(__file__).resolve().parents[1];paths=['docs/qa/targeted/synthetic/fonts/authored.ttf','docs/qa/targeted/synthetic/fonts/authored.otf','docs/qa/targeted/synthetic/fonts/authored.ttc','docs/qa/targeted/synthetic/fonts/authored.woff2','docs/qa/targeted/synthetic/.private/raw-audit.json','docs/qa/targeted/synthetic/anonymous-smoke-data-test/source.json','docs/qa/targeted/synthetic/ten-package-data/source.json']
        paths.extend(['docs/qa/targeted/synthetic/fonts/AUTHORED.TTF','docs/qa/targeted/synthetic/fonts/AUTHORED.OTF','docs/qa/targeted/synthetic/fonts/AUTHORED.TTC','docs/qa/targeted/synthetic/fonts/AUTHORED.WOFF2'])
        result=subprocess.run(['git','check-ignore','--no-index','--stdin'],input='\n'.join(paths)+'\n',capture_output=True,text=True,cwd=root,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(result.stdout.splitlines(),paths)

if __name__=='__main__':unittest.main()
