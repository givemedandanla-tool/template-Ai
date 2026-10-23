"""Actual small-tool window acceptance; no substituted window or parser."""
import json
import hashlib
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from PySide6.QtCore import QEventLoop, QTimer, Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox


APP = QApplication.instance() or QApplication([])


def wait_until(predicate, milliseconds=90000):
    if predicate():
        return
    loop = QEventLoop()
    poll = QTimer()
    limit = QTimer()
    limit.setSingleShot(True)
    poll.timeout.connect(lambda: loop.quit() if predicate() else None)
    limit.timeout.connect(loop.quit)
    poll.start(20)
    limit.start(milliseconds)
    try:
        loop.exec()
    finally:
        poll.stop()
        limit.stop()
    if not predicate():
        raise AssertionError('Actual review operation did not finish within its bounded deadline')


class ReviewToolGuiTests(unittest.TestCase):
    def test_more_menu_adopts_only_new_works_and_preserves_human_corrections(self):
        """A compatible authored packet exercises the real More-menu slot."""
        from template_ai.review_tool.window import ReviewWindow
        with tempfile.TemporaryDirectory(prefix='review-adopt-new-works-') as raw:
            root = Path(raw)
            source = root / 'synthetic.svg'
            source.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="60mm" '
                              'height="30mm" viewBox="0 0 60 30"/>', encoding='utf-8')
            preview = root / 'preview.png'
            image = QImage(600, 300, QImage.Format.Format_RGB32)
            image.fill(Qt.GlobalColor.white)
            self.assertTrue(image.save(str(preview)))
            window = ReviewWindow(root / 'data')
            try:
                window.resize(1440, 1000)
                window.show()
                APP.processEvents()
                window.add_files([str(source)])
                source_id = window.store.sources()[0]['id']
                packet = {'schema_version': 1, 'analysis_version': 'AUTHORED_COMPATIBLE_V1',
                    'status': 'ANALYSED',
                    'source': {'id': source_id, 'path': str(source),
                               'hash': hashlib.sha256(source.read_bytes()).hexdigest()},
                    'pages': [{'id': 'same-page', 'page': 1, 'image': str(preview),
                               'image_hash': hashlib.sha256(preview.read_bytes()).hexdigest(),
                               'width_mm': 60., 'height_mm': 30., 'calibrated': True}],
                    'works': [{'id': 'original-work', 'page_id': 'same-page', 'page': 1,
                               'crop': {'x': 0., 'y': 0., 'w': 30., 'h': 30.},
                               'fields': [{'id': 'original-field', 'text': 'PREDICTED',
                                           'kind': 'name',
                                           'rect': {'x': 3., 'y': 5., 'w': 20., 'h': 5.}}]}],
                    'issues': [], 'capabilities': {'ocr_requested': False}}
                window.store.apply_analysis(source_id, packet)
                original_work = window.store.works(source_id)[0]
                work_id, field_id = original_work['id'], original_work['fields'][0]['id']
                window.select_work(work_id)
                window.select_field(field_id)
                window.text_edit.setPlainText('HUMAN_CORRECTION')
                window.review_combo.setCurrentIndex(window.review_combo.findData('REVIEWED'))
                APP.processEvents()
                self.assertFalse(window.apply_field_button.visibleRegion().isEmpty())
                QTest.mouseClick(window.apply_field_button, Qt.MouseButton.LeftButton)
                self.assertEqual(window.store.get_field(work_id, field_id)['text'], 'HUMAN_CORRECTION')
                protected_work = deepcopy(window.store.get_work(work_id))
                rerun = deepcopy(packet)
                rerun['works'][0]['fields'][0]['text'] = 'NEW_PREDICTION_MUST_NOT_OVERWRITE'
                rerun['works'].append({'id': 'newly-found-work', 'page_id': 'same-page', 'page': 1,
                                      'crop': {'x': 30., 'y': 0., 'w': 30., 'h': 30.},
                                      'fields': [{'id': 'newly-found-field', 'text': 'NEW WORK',
                                                  'kind': 'name',
                                                  'rect': {'x': 2., 'y': 4., 'w': 20., 'h': 5.}}]})
                window.store.apply_analysis(source_id, rerun)
                self.assertIsInstance(window.store.get_source(source_id)['pending_analysis_version'], str)
                self.assertEqual(len(window.store.works(source_id)), 1)
                action = next(action for action in window.more_button.menu().actions()
                              if action.text() == '加入重新判讀新找到的作品')
                action.trigger()
                APP.processEvents()
                self.assertEqual(len(window.store.works(source_id)), 2)
                self.assertEqual(window.store.get_work(work_id), protected_work)
                self.assertEqual(window.tree.topLevelItem(0).childCount(), 2)
                adopted_ids = [work['id'] for work in window.store.works(source_id)]
                action.trigger()
                APP.processEvents()
                self.assertEqual([work['id'] for work in window.store.works(source_id)], adopted_ids)
                self.assertEqual(window.store.get_work(work_id), protected_work)
                self.assertEqual(window.tree.topLevelItem(0).childCount(), 2)
                self.assertIn('0 份', window.notice.text())
            finally:
                window.save_progress()
                window.close()
                APP.processEvents()

    def test_first_window_is_visible_and_numeric_overview_is_hidden(self):
        from template_ai.review_tool.window import ReviewWindow
        with tempfile.TemporaryDirectory(prefix='review-first-window-') as raw:
            window = ReviewWindow(raw)
            try:
                window.show()
                APP.processEvents()
                self.assertTrue(window.isVisible())
                self.assertTrue(window.add_button.isVisible())
                self.assertTrue(window.canvas.isVisible())
                self.assertFalse(window.overview_tree.isVisible())
                self.assertEqual(window.store.sources(), [])
            finally:
                window.save_progress()
                window.close()
                APP.processEvents()

    def test_actual_window_worker_review_overview_save_and_reopen(self):
        from template_ai.review_tool.release_check import run
        with tempfile.TemporaryDirectory(prefix='review-real-gui-') as raw:
            report = Path(raw) / 'acceptance.json'
            exit_code = run(report)
            result = json.loads(report.read_text(encoding='utf-8'))
            self.assertEqual(exit_code, 0, result.get('error'))
            self.assertEqual(result['status'], 'PASS')
            self.assertFalse(result['actual_frozen_executable'])
            self.assertFalse(result['real_corpus_qualified'])
            self.assertTrue(result['source_unchanged'])
            self.assertIn('actual_qprocess_analysis_completes', result['checks'])
            self.assertIn('canvas_click_updates_actual_editor', result['checks'])
            self.assertIn('original_prediction_remains_separate', result['checks'])
            self.assertIn('actual_window_reopens_saved_corrections', result['checks'])
            self.assertIn('safe_diagnostic_excludes_private_content_and_paths', result['checks'])
            self.assertGreaterEqual(len(result['artifacts']), 4)

    def test_authored_uncalibrated_record_manual_annotation_does_not_become_verified_millimetres(self):
        """An explicit missing-metadata fixture, not a claimed PNG input route."""
        from template_ai.review_tool.window import ReviewWindow
        with tempfile.TemporaryDirectory(prefix='review-unscaled-raster-') as raw:
            root = Path(raw)
            preview = root / 'preview.png'
            image = QImage(400, 200, QImage.Format.Format_RGB32)
            image.fill(Qt.GlobalColor.white)
            self.assertTrue(image.save(str(preview)))
            source = root / 'synthetic.svg'
            source.write_text('<svg xmlns="http://www.w3.org/2000/svg" '
                              'viewBox="0 0 400 200"/>', encoding='utf-8')
            window = ReviewWindow(root / 'data')
            try:
                window.show()
                APP.processEvents()
                window.add_files([str(source)])
                registered = window.store.sources()[0]
                # This fixture deliberately withholds calibration. It verifies
                # the UI contract for an existing incomplete observation, not
                # the parser's interpretation of SVG/PDF physical units.
                packet = {'schema_version': 1, 'status': 'PARTIAL',
                    'source': {'id': registered['id'], 'path': str(source),
                               'hash': hashlib.sha256(source.read_bytes()).hexdigest()},
                    'pages': [{'id': 'fixture-page', 'page': 1, 'image': str(preview),
                               'width_mm': 100.0, 'height_mm': 50.0, 'calibrated': False}],
                    'works': [{'id': 'fixture-work', 'page_id': 'fixture-page', 'page': 1,
                               'name': '明確合成未標定資料',
                               'crop': {'x': 0., 'y': 0., 'w': 100., 'h': 50.},
                               'fields': [], 'relations': [],
                               'measurements': {'width_mm': {'status': 'UNKNOWN', 'value': None},
                                                'height_mm': {'status': 'UNKNOWN', 'value': None}}}],
                    'issues': [], 'capabilities': {}}
                window.store.apply_analysis(registered['id'], packet)
                work = window.store.works()[0]
                window.select_work(work['id'])
                # Actual user menu command plus a real drawing gesture.
                next(action for action in window.add_mark_button.menu().actions()
                     if action.text() == '文字欄位').trigger()
                start = window.canvas.mapFromScene(window.canvas.local_to_scene((10, 10)))
                end = window.canvas.mapFromScene(window.canvas.local_to_scene((30, 20)))
                QTest.mousePress(window.canvas.viewport(), Qt.MouseButton.LeftButton,
                                 Qt.KeyboardModifier.NoModifier, start)
                QTest.mouseMove(window.canvas.viewport(), end)
                QTest.mouseRelease(window.canvas.viewport(), Qt.MouseButton.LeftButton,
                                   Qt.KeyboardModifier.NoModifier, end)
                APP.processEvents()
                self.assertIsNotNone(window.current_field_id)
                window.show_overview()
                APP.processEvents()
                section = next(window.overview_tree.topLevelItem(index)
                               for index in range(window.overview_tree.topLevelItemCount())
                               if window.overview_tree.topLevelItem(index).text(0) == '尺寸與位置')
                self.assertIn('比例', section.text(1))
                width = next(section.child(index) for index in range(section.childCount())
                             if section.child(index).text(0) == '欄位寬度')
                self.assertFalse(width.text(1).endswith(' mm'))
                window.overview_tree.scrollToItem(width)
                QTest.mouseClick(window.overview_tree.viewport(), Qt.MouseButton.LeftButton,
                                 pos=window.overview_tree.visualItemRect(width).center())
                APP.processEvents()
                self.assertEqual(window.canvas.measurement_items, [])
            finally:
                window.save_progress()
                window.close()
                APP.processEvents()

    def test_close_return_keeps_unsaved_work_then_save_and_exit_preserves_it(self):
        from template_ai.review_tool.window import ReviewWindow
        with tempfile.TemporaryDirectory(prefix='review-close-flow-') as raw:
            root = Path(raw)
            source = root / 'synthetic.svg'
            source.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="60mm" '
                              'height="30mm" viewBox="0 0 60 30"/>', encoding='utf-8')
            window = ReviewWindow(root / 'data')
            failures = []

            def answer(text):
                dialog = APP.activeModalWidget()
                if not isinstance(dialog, QMessageBox):
                    failures.append('Expected the actual close confirmation dialog')
                    return
                button = next((button for button in dialog.buttons() if button.text() == text), None)
                if button is None:
                    failures.append('Expected close action missing: ' + text)
                    dialog.reject()
                    return
                QTest.mouseClick(button, Qt.MouseButton.LeftButton)

            try:
                window.show()
                APP.processEvents()
                window.add_files([str(source)])
                self.assertTrue(window.store.dirty)
                QTimer.singleShot(30, lambda: answer('返回繼續工作'))
                window.close()
                self.assertEqual(failures, [])
                self.assertTrue(window.isVisible())
                self.assertTrue(window.store.dirty)
                self.assertFalse(window.store.path.exists())
                QTimer.singleShot(30, lambda: answer('保存後離開'))
                window.close()
                self.assertEqual(failures, [])
                self.assertFalse(window.isVisible())
                reopened = ReviewWindow(root / 'data')
                try:
                    self.assertEqual(len(reopened.store.sources()), 1)
                    self.assertFalse(reopened.store.dirty)
                finally:
                    reopened.close()
            finally:
                if window.isVisible():
                    window.save_progress()
                    window.close()
                APP.processEvents()

    def test_discard_while_real_worker_runs_does_not_save_uncommitted_changes(self):
        from template_ai.review_tool.window import ReviewWindow
        from template_ai.review_tool.release_check import exercise_discard_close
        with tempfile.TemporaryDirectory(prefix='review-discard-flow-') as raw:
            root = Path(raw)
            source = root / 'synthetic.svg'
            source.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="60mm" '
                              'height="30mm" viewBox="0 0 60 30">'
                              '<text x="4" y="12" font-size="5">REVIEW DEMO</text></svg>', encoding='utf-8')
            window = ReviewWindow(root / 'data')
            previous = APP.quitOnLastWindowClosed()
            APP.setQuitOnLastWindowClosed(False)
            try:
                evidence = exercise_discard_close(
                    window, source, lambda predicate, seconds: wait_until(predicate, round(seconds * 1000)))
                self.assertTrue(evidence['saved_snapshot_byte_identical'])
                self.assertFalse(window.jobs.is_running())
                reopened = ReviewWindow(root / 'data')
                try:
                    self.assertEqual(reopened.store.data['owners'], [])
                    self.assertFalse(reopened.store.sources()[0].get('analysis'))
                finally:
                    reopened.close()
            finally:
                APP.setQuitOnLastWindowClosed(previous)
                if window.isVisible():
                    window.save_progress()
                    window.close()
                APP.processEvents()


if __name__ == '__main__':
    unittest.main()
