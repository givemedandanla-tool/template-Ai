"""複合 Logo 的整體、來源、版本、尺寸隔離與真實數位輸出。"""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication

from template_ai.customers import digest
from template_ai.importer import import_file
from template_ai.layout import generate
from template_ai.logo_assets import errors, geometry
from template_ai.logo_discovery import discover
from template_ai.logo_store import LogoStore
from template_ai.model import Rect, Slot, Template
from template_ai.render import draw_logo, export, render_image
from template_ai.storage import Library

APP = QApplication.instance() or QApplication([])
REVIEW = dict(identity_confirmed=True, whole_mark_confirmed=True, usage_authorized=True,
              digital_quality_confirmed=True, actor='SYNTHETIC_TEST',
              note='Synthetic entire graphic and text compared at the target digital size')


class LogoLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.library = Library(self.root / 'library')
        self.store = LogoStore(self.library)
        self.company = self.store.create_company('Synthetic Brand', 'Synthetic independent identity', True)
        self.path = self.root / 'synthetic-logo.svg'
        self.path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="20mm" height="10mm" viewBox="0 0 20 10">'
            '<g id="whole"><rect id="symbol" x="2" y="2" width="5" height="5" fill="red"/>'
            '<text id="brand" x="8" y="6" font-size="2">Example</text></g></svg>')
        converted = import_file(self.path, self.library.assets)
        self.payload = dict(image=converted['image'], svg=converted['svg'],
            source_width_mm=converted['width_mm'], source_height_mm=converted['height_mm'],
            source_hash=converted['hash'], crop=None)

    def tearDown(self):
        self.library.close()
        self.temp.cleanup()

    def proposal(self, width=90, height=54, base=None):
        return self.store.propose(self.payload, width, height, company_id=self.company['id'], family_base=base)

    def approve(self, proposal=None):
        proposal = proposal or self.proposal()
        return self.store.approve(proposal['id'], proposal['revision'], self.company['id'], REVIEW, True)

    def candidate(self, asset=None):
        template = Template('Synthetic compound logo', 90, 54,
            [Slot('name', 'p1', Rect(5, 4, 60, 8)), Slot('logo', 'c1', Rect(5, 20, 30, 15))],
            company_bindings={'p1': 'c1'})
        self.library.publish(template)
        return generate(template, [{'name': ['Alex'], 'company': 'c1'}],
                        [{'name': 'Synthetic Brand'}], {'c1': asset} if asset else {})

    def test_pending_rejection_and_incomplete_review_never_create_approved_logo(self):
        proposal = self.proposal()
        self.assertEqual(self.library.logos(), [])
        for key in ('identity_confirmed', 'whole_mark_confirmed', 'usage_authorized', 'digital_quality_confirmed'):
            review = {**REVIEW, key: False}
            with self.assertRaises(ValueError):
                self.store.approve(proposal['id'], proposal['revision'], self.company['id'], review, True)
        rejected = self.store.reject(proposal['id'], proposal['revision'], 'Synthetic incomplete mark', True)
        self.assertEqual(rejected['state'], 'REJECTED')
        with self.assertRaises(ValueError):
            self.approve(rejected)
        self.assertEqual(self.library.logos(), [])

    def test_contain_geometry_preserves_aspect_and_reports_blank_without_quality_threshold(self):
        fit = geometry(self.payload, Rect(10, 20, 30, 30))
        self.assertAlmostEqual(fit['scale'], 1.5)
        self.assertEqual(fit['actual'], dict(x=10, y=27.5, w=30, h=15))
        self.assertAlmostEqual(fit['occupied_fraction'], .5)
        self.assertEqual(fit['padding_mm']['top'], 7.5)
        self.assertIn('REQUIRES', fit['quality'])
        with self.assertRaises(ValueError):
            geometry({**self.payload, 'crop': dict(x=0, y=0, w=50, h=5)}, Rect(0, 0, 30, 30))

    def test_entire_graphic_and_text_render_transparency_and_three_real_formats(self):
        asset = self.approve()
        self.assertEqual(errors(asset), [])
        candidate = self.candidate(asset)
        self.assertTrue(candidate.valid, candidate.issues)
        self.assertEqual(candidate.items[-1].slot.kind, 'logo')
        self.assertEqual(len(candidate.items), 2)  # 內部品牌文字沒有拆成可變欄位。
        image = QImage(400, 200, QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.transparent)
        painter = QPainter(image)
        draw_logo(painter, QRectF(0, 0, 400, 200), asset)
        painter.end()
        self.assertEqual(image.pixelColor(0, 0).alpha(), 0)
        self.assertGreater(image.pixelColor(70, 70).red(), 200)
        for suffix in ('png', 'pdf', 'jpg'):
            target = self.root / ('Synthetic-FINAL.' + suffix)
            export(candidate, target, dpi=96)
            self.assertGreater(target.stat().st_size, 100)
        self.assertEqual([s.size_pt for s in candidate.template.slots], [10, 10])

    def test_hash_change_blocks_existing_candidate_and_does_not_leave_output(self):
        asset = self.approve()
        candidate = self.candidate(asset)
        svg = Path(asset['svg'])
        svg.write_bytes(svg.read_bytes() + b'\n')
        self.assertTrue(errors(asset))
        target = self.root / 'Synthetic-FINAL.png'
        with self.assertRaises(ValueError):
            export(candidate, target, dpi=96)
        self.assertFalse(target.exists())
        self.assertEqual(list(self.root.glob('.template-ai-*')), [])

    def test_revocation_invalidates_old_object_and_never_silently_selects_other_version(self):
        asset = self.approve()
        other = self.approve(self.proposal(base=asset['id']))
        self.store.bind('work-company', self.company['id'], self.company['name'], True)
        before = self.store.match('work-company', self.company['name'], 90, 54, selected_id=asset['id'])
        self.assertEqual(before['selected']['id'], asset['id'])
        candidate = self.candidate(asset)
        self.store.revoke(asset['id'], digest(asset), 'Synthetic withdrawn identity approval', True)
        self.assertTrue(errors(asset))
        after = self.store.match('work-company', self.company['name'], 90, 54, selected_id=asset['id'])
        self.assertEqual(after['state'], 'SELECTION_INVALID')
        self.assertIsNone(after['selected'])
        self.assertEqual([a['id'] for a in after['candidates']], [other['id']])
        with self.assertRaises(ValueError):
            export(candidate, self.root / 'Synthetic-FINAL.pdf')

    def test_version_is_new_immutable_id_and_unrelated_size_or_company_not_reused(self):
        first = self.approve()
        second = self.approve(self.proposal(base=first['id']))
        self.assertEqual(self.store.asset(first['id']), first)
        self.assertNotEqual(first['id'], second['id'])
        self.assertEqual(first['family_id'], second['family_id'])
        self.assertEqual(second['version'], 2)
        wrong_size = self.proposal(100, 60, first['id'])
        with self.assertRaisesRegex(ValueError, '同一卡片尺寸'):
            self.approve(wrong_size)
        independent = self.store.create_company('Synthetic Brand', 'A different verified identity', True)
        proposal = self.proposal(base=first['id'])
        with self.assertRaises(ValueError):
            self.store.approve(proposal['id'], proposal['revision'], independent['id'], REVIEW, True)

    def test_company_name_is_only_clue_single_multiple_and_explicit_selection_states(self):
        first = self.approve()
        unknown = self.store.match('new-company', self.company['name'], 90, 54)
        self.assertEqual(unknown['state'], 'IDENTITY_REVIEW_REQUIRED')
        self.assertIsNone(unknown['selected'])
        self.store.bind('new-company', self.company['id'], self.company['name'], True)
        self.assertEqual(self.store.match('new-company', self.company['name'], 90, 54)['state'], 'SINGLE_PREVIEW')
        second = self.approve()
        multiple = self.store.match('new-company', self.company['name'], 90, 54, Rect(0, 0, 20, 10))
        self.assertEqual(multiple['state'], 'MULTIPLE_REVIEW_REQUIRED')
        self.assertIsNone(multiple['selected'])
        exact = self.store.match('new-company', self.company['name'], 90, 54, selected_id=second['id'])
        self.assertEqual(exact['selected']['id'], second['id'])
        changed_name = self.store.match('new-company', 'Unverified changed brand', 90, 54)
        self.assertEqual(changed_name['state'], 'IDENTITY_REVIEW_REQUIRED')
        self.assertEqual(self.store.match('new-company', self.company['name'], 80, 40)['state'], 'MISSING')

    def test_new_size_prediction_is_pending_then_independently_approved_and_normal_mode_stays_isolated(self):
        original = self.approve()
        self.store.bind('company', self.company['id'], self.company['name'], True)
        predicted = self.store.predict_new_size(self.company['id'], 100, 60)
        self.assertEqual(len(predicted), 1)
        self.assertEqual(predicted[0]['state'], 'PENDING')
        self.assertEqual(predicted[0]['evidence']['prediction_source']['size_mm'], [90, 54])
        self.assertEqual(self.store.match('company', self.company['name'], 100, 60)['state'], 'MISSING')
        approved = self.approve(predicted[0])
        self.assertNotEqual(approved['family_id'], original['family_id'])
        self.assertEqual(self.store.match('company', self.company['name'], 100, 60)['selected']['id'], approved['id'])
        self.assertEqual(self.store.match('company', self.company['name'], 90, 54)['selected']['id'], original['id'])
        with self.assertRaisesRegex(ValueError, '已知尺寸'):
            self.store.predict_new_size(self.company['id'], 90, 54)

    def test_prediction_reference_revoked_before_target_approval_stays_pending(self):
        original = self.approve()
        predicted = self.store.predict_new_size(self.company['id'], 100, 60)[0]
        self.store.revoke(original['id'], digest(original), 'Synthetic revoked reference', True)
        with self.assertRaisesRegex(ValueError, '參考版本已變更'):
            self.approve(predicted)
        self.assertEqual(self.store.proposal(predicted['id'])['state'], 'PENDING')

    def test_approval_late_failure_rolls_back_and_cleans_approval_file(self):
        proposal = self.proposal()
        with patch.object(self.library, 'event', side_effect=OSError('simulated disk full')):
            with self.assertRaises(OSError):
                self.approve(proposal)
        self.assertEqual(self.library.logos(), [])
        self.assertEqual(self.store.proposal(proposal['id'])['state'], 'PENDING')
        self.assertEqual(list((self.library.assets / 'logo-approvals').glob('*.json')), [])

    def test_missing_logo_is_true_black_placeholder_without_formal_gate_bypass(self):
        candidate = self.candidate()
        self.assertFalse(candidate.valid)
        image = render_image(candidate, dpi=254, preview=True)
        self.assertEqual(image.pixelColor(55, 205).name(), '#000000')
        with self.assertRaises(ValueError):
            export(candidate, self.root / 'Synthetic-FINAL.png')
        export(candidate, self.root / 'Synthetic-PREVIEW.png', dpi=96, preview=True)

    def test_real_inkscape_transformed_group_candidate_uses_mm_and_keeps_text_with_graphic(self):
        path = self.root / 'source.svg'
        path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="90mm" height="54mm" viewBox="0 0 90 54">'
            '<g id="whole" transform="translate(10,20)"><rect id="icon" x="0" y="0" width="10" height="5"/>'
            '<text id="brand" x="12" y="5" font-size="3">Example</text></g></svg>')
        source = self.library.add_source(path, import_file(path, self.library.assets))
        work = self.library.create_artwork(source['id'], 'Synthetic complete artwork',
            dict(crop=dict(x=0,y=0,w=90,h=54),work_width=90,work_height=54,slots=[],visual_confirmed=True))
        rows = discover(self.store, source['id'], work['id'])
        self.assertEqual(len(rows), 1)
        candidate = rows[0]
        self.assertEqual(candidate['state'], 'PENDING')
        self.assertAlmostEqual(candidate['asset']['crop']['x'], 10, places=3)
        self.assertAlmostEqual(candidate['asset']['crop']['y'], 20, places=3)
        self.assertEqual(set(candidate['evidence']['object_ids']), {'icon', 'brand'})
        self.assertEqual(candidate['evidence']['source_evidence']['text_hints'], ['Example'])
        again = discover(self.store, source['id'], work['id'])
        self.assertEqual(again[0]['id'], candidate['id'])
        self.assertEqual(self.library.logos(), [])

    def test_source_candidate_revision_and_cross_artwork_region_are_protected(self):
        source = self.library.add_source(self.path, import_file(self.path, self.library.assets))
        work = self.library.create_artwork(source['id'], 'Synthetic', dict(crop=dict(x=0,y=0,w=20,h=10),
            work_width=90,work_height=54,slots=[],visual_confirmed=True))
        row = self.store.propose_source(source['id'], work['id'], dict(x=0,y=0,w=20,h=10),
            self.company['id'], ['symbol','brand'])
        corrected = self.store.revise(row['id'], row['revision'], dict(x=1,y=1,w=18,h=8),
            self.company['id'], ['symbol','brand'], 'Synthetic boundary correction with complete content')
        with self.assertRaises(ValueError):
            self.store.approve(row['id'], row['revision'], self.company['id'], REVIEW, True)
        self.assertEqual(corrected['asset']['crop'], dict(x=1,y=1,w=18,h=8))
        with self.assertRaises(ValueError):
            self.store.propose_source(source['id'], work['id'], dict(x=0,y=0,w=30,h=10))

    def test_nan_size_and_corrupt_approval_record_fail_closed(self):
        with self.assertRaises(ValueError):
            self.proposal(float('nan'), 54)
        asset = self.approve()
        Path(asset['approval_file']).write_text('[]')
        self.assertTrue(errors(asset))
