"""Only actual current file/face evidence can establish byte identity."""
import hashlib,shutil,tempfile,unittest
from pathlib import Path
from fontTools.ttLib import TTFont,TTCollection
from template_ai.source_text_evidence import identity_match
from template_ai.font_evidence import face_bytes

FONT=next((p for p in map(Path,('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf','/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf',r'C:\Windows\Fonts\arial.ttf')) if p.is_file()),None)
MONO=next((p for p in map(Path,('/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf',r'C:\Windows\Fonts\consola.ttf')) if p.is_file()),FONT)

class FontSourceIdentityTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(FONT,'Actual local test reference font is unavailable; not a qualified run')
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
        reference,candidate=self.refs();self.source.write_bytes(self.source.read_bytes()+b'authored-change');self.assertNotEqual(identity_match(reference,candidate)['state'],'PROVEN_SAME_BYTES')
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

    def test_extracted_current_face_is_proved_from_exact_source_collection_index(self):
        source=self.root/'authored-source.ttc';collection=TTCollection();collection.fonts=[TTFont(FONT),TTFont(MONO)]
        try:collection.save(source)
        finally:
            for font in collection.fonts:font.close()
        extracted=self.root/'extracted-face.ttf';extracted.write_bytes(face_bytes(source,1));reference=dict(font_path=str(source),font_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),face_index=1);candidate=dict(path=str(extracted),hash=hashlib.sha256(extracted.read_bytes()).hexdigest(),font_evidence=dict(index=1))
        value=identity_match(reference,candidate);self.assertEqual(value['state'],'PROVEN_SAME_EXTRACTED_FACE');self.assertEqual(value['source_face_index'],1);self.assertEqual(value['physical_face_index'],0);self.assertEqual(value['original_ai_font_relation'],'UNVERIFIED')

if __name__=='__main__':unittest.main()
