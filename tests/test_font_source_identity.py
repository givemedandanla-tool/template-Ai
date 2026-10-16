"""Only actual current file/face evidence can establish byte identity."""
import hashlib,shutil,tempfile,unittest
from pathlib import Path
from fontTools.ttLib import TTFont,TTCollection
from template_ai.source_text_evidence import identity_match

FONT=Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
MONO=Path('/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf')

class FontSourceIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.source=self.root/'authored-reference.ttf';self.target=self.root/'selected-copy.ttf';shutil.copyfile(FONT,self.source);shutil.copyfile(FONT,self.target)
    def refs(self,path=None):
        source=path or self.source;target=path or self.target;sha=hashlib.sha256(source.read_bytes()).hexdigest()
        return dict(font_path=str(source),font_sha256=sha,face_index=0),dict(path=str(target),hash=sha,font_evidence=dict(index=0))
    def test_matching_declared_hash_without_actual_font_files_is_not_proof(self):
        value=identity_match(dict(font_sha256='a'*64),dict(hash='a'*64))
        self.assertNotEqual(value['state'],'PROVEN_SAME_BYTES')
    def test_actual_valid_same_file_and_face_remain_separate_from_native_editability(self):
        value=identity_match(*self.refs());self.assertEqual(value['state'],'PROVEN_SAME_BYTES');self.assertEqual(value['editable_source'],'UNKNOWN');self.assertEqual(value['original_ai_font_relation'],'UNVERIFIED')
    def test_source_changed_after_snapshot_cannot_reuse_declared_hash(self):
        reference,candidate=self.refs();shutil.copyfile(MONO,self.source);self.assertNotEqual(identity_match(reference,candidate)['state'],'PROVEN_SAME_BYTES')
    def test_corrupt_matching_bytes_cannot_be_promoted_to_a_font(self):
        self.source.write_bytes(b'authored-corrupt-font');self.target.write_bytes(self.source.read_bytes());self.assertNotEqual(identity_match(*self.refs())['state'],'PROVEN_SAME_BYTES')
    def test_collection_same_file_with_other_face_is_not_same_face(self):
        path=self.root/'authored-collection.ttc';collection=TTCollection();collection.fonts=[TTFont(FONT),TTFont(MONO)]
        try:collection.save(path)
        finally:
            for font in collection.fonts:font.close()
        reference,candidate=self.refs(path);candidate['font_evidence']['index']=1;self.assertNotEqual(identity_match(reference,candidate)['state'],'PROVEN_SAME_BYTES')
    def test_same_name_or_visual_similarity_only_remains_alias_or_unknown(self):
        self.assertEqual(identity_match(dict(family='Example'),dict(family='Example'))['state'],'POSSIBLE_ALIAS');self.assertEqual(identity_match(dict(visual_score=1),dict(visual_score=1))['state'],'UNIDENTIFIED')

if __name__=='__main__':unittest.main()
