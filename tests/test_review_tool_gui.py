"""Actual small-tool window acceptance; no substituted window or parser."""
import json
import hashlib
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtCore import QEventLoop, QTimer, Qt
from PySide6.QtGui import QColor, QImage, QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox, QWidget


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
    def test_popup_menus_remain_readable_with_dark_system_palette(self):
        """Render both real menus, including selected and unavailable items."""
        from template_ai.review_tool.window import ReviewWindow

        def luminance(color):
            channels = [channel / 255 for channel in color.getRgb()[:3]]
            channels = [c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4
                        for c in channels]
            return sum(c * weight for c, weight in zip(channels, [.2126, .7152, .0722]))

        def contrast(first, second):
            light, dark = sorted([luminance(first), luminance(second)], reverse=True)
            return (light + .05) / (dark + .05)

        def rendered_contrast(menu, action, expected_background):
            rect = menu.actionGeometry(action)
            self.assertFalse(rect.isEmpty())
            snapshot = menu.grab()
            ratio = snapshot.devicePixelRatio()
            image = snapshot.toImage()
            background = image.pixelColor(round((rect.left() + 4) * ratio),
                                          round(rect.center().y() * ratio))
            self.assertEqual(background.name(), expected_background)
            colors = {image.pixelColor(x, y).rgba()
                      for x in range(round((rect.left() + 14) * ratio),
                                     round((rect.right() - 14) * ratio))
                      for y in range(round((rect.top() + 4) * ratio),
                                     round((rect.bottom() - 4) * ratio))}
            return max(contrast(QColor.fromRgba(color), background) for color in colors)

        original_palette = QPalette(APP.palette())
        dark_palette = QPalette(original_palette)
        for group in (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive,
                      QPalette.ColorGroup.Disabled):
            for role in (QPalette.ColorRole.Window, QPalette.ColorRole.Base,
                         QPalette.ColorRole.Button):
                dark_palette.setColor(group, role, QColor('#111111'))
            for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text,
                         QPalette.ColorRole.ButtonText):
                dark_palette.setColor(group, role, QColor('#eeeeee'))
        APP.setPalette(dark_palette)
        try:
            with tempfile.TemporaryDirectory(prefix='review-dark-menu-') as raw:
                window = ReviewWindow(Path(raw))
                try:
                    window.show()
                    APP.processEvents()
                    form=window.findChild(QWidget,'reviewForm')
                    self.assertIsNotNone(form)
                    self.assertEqual(form.grab().toImage().pixelColor(1,1).name(),'#ffffff')
                    for button in (window.more_button, window.add_mark_button):
                        with self.subTest(menu=button.text()):
                            menu = button.menu()
                            original_actions = [(action, action.isEnabled())
                                                for action in menu.actions()]
                            separator = menu.addSeparator()
                            unavailable = menu.addAction('Unavailable synthetic action')
                            unavailable.setEnabled(False)
                            menu.popup(button.mapToGlobal(button.rect().bottomLeft()))
                            APP.processEvents()
                            menu.setActiveAction(None)
                            self.assertGreaterEqual(rendered_contrast(
                                menu, menu.actions()[0], '#ffffff'), 7)
                            self.assertGreaterEqual(rendered_contrast(
                                menu, unavailable, '#ffffff'), 4.5)
                            menu.setActiveAction(menu.actions()[0])
                            APP.processEvents()
                            self.assertGreaterEqual(rendered_contrast(
                                menu, menu.actions()[0], '#e8f0ff'), 7)
                            rect = menu.actionGeometry(separator)
                            self.assertFalse(rect.isEmpty())
                            snapshot = menu.grab()
                            ratio = snapshot.devicePixelRatio()
                            image = snapshot.toImage()
                            separator_colors = {
                                image.pixelColor(round(rect.center().x() * ratio), y).name()
                                for y in range(round(rect.top() * ratio),
                                               round((rect.bottom() + 1) * ratio))}
                            self.assertIn('#dfe5ed', separator_colors)
                            self.assertFalse(unavailable.isEnabled())
                            self.assertEqual(original_actions,
                                             [(action, action.isEnabled())
                                              for action, _ in original_actions])
                            menu.hide()
                finally:
                    window.close()
                    APP.processEvents()
        finally:
            APP.setPalette(original_palette)

    def test_add_button_rejects_invalid_batches_without_losing_existing_review(self):
        """Only the OS picker is patched; the actual Add button and slot run."""
        from template_ai.review_tool.window import ReviewWindow
        with tempfile.TemporaryDirectory(prefix='review-add-errors-') as raw:
            root = Path(raw)
            svg_text = ('<svg xmlns="http://www.w3.org/2000/svg" width="60mm" '
                        'height="30mm" viewBox="0 0 60 30"/>')
            existing, valid_a, valid_b = [root / name for name in ('existing.svg', 'valid-a.svg', 'valid-b.svg')]
            for source in (existing, valid_a, valid_b):
                source.write_text(svg_text, encoding='utf-8')
            unsupported = root / 'unsupported.txt'
            unsupported.write_text('AUTHORED SYNTHETIC INPUT', encoding='utf-8')
            missing = root / 'deleted-source.svg'
            window = ReviewWindow(root / 'data')
            uncaught = []
            try:
                window.show()
                APP.processEvents()
                window.add_files([str(existing)])
                registered = window.store.sources()[0]
                packet = {'schema_version': 1, 'status': 'ANALYSED',
                    'source': {'id': registered['id'], 'path': str(existing),
                               'hash': hashlib.sha256(existing.read_bytes()).hexdigest()},
                    'pages': [],
                    'works': [{'id': 'existing-work', 'page': 1,
                               'crop': {'x': 0., 'y': 0., 'w': 60., 'h': 30.},
                               'fields': [{'id': 'existing-field', 'text': 'PREDICTED',
                                           'kind': 'name',
                                           'rect': {'x': 5., 'y': 10., 'w': 25., 'h': 5.}}]}],
                    'issues': [], 'capabilities': {}}
                window.store.apply_analysis(registered['id'], packet)
                work = window.store.works()[0]
                field = work['fields'][0]
                window.select_work(work['id'])
                window.select_field(field['id'])
                window.text_edit.setPlainText('HUMAN_REVIEW_TO_KEEP')
                window.review_combo.setCurrentIndex(window.review_combo.findData('REVIEWED'))
                QTest.mouseClick(window.apply_field_button, Qt.MouseButton.LeftButton)
                baseline = deepcopy(window.store.data)
                with patch('sys.excepthook', side_effect=lambda *error: uncaught.append(error)):
                    for batch in ([str(valid_a), str(unsupported)], [str(valid_b), str(missing)]):
                        with self.subTest(invalid_source=Path(batch[1]).name):
                            with patch('template_ai.review_tool.window.QFileDialog.getOpenFileNames',
                                       return_value=(batch, '')) as picker:
                                QTest.mouseClick(window.add_button, Qt.MouseButton.LeftButton)
                                APP.processEvents()
                                picker.assert_called_once()
                            self.assertEqual(uncaught, [])
                            self.assertEqual(window.store.data, baseline)
                            self.assertEqual(window.text_edit.toPlainText(), 'HUMAN_REVIEW_TO_KEEP')
                            self.assertEqual(window.review_combo.currentData(), 'REVIEWED')
                            self.assertFalse(window.notice.visibleRegion().isEmpty())
                            self.assertIn('這批尚未加入', window.notice.text())
                            self.assertEqual(window.tree.topLevelItemCount(), 1)
                    with patch('template_ai.review_tool.window.QFileDialog.getOpenFileNames',
                               return_value=([str(valid_a), str(valid_b)], '')):
                        QTest.mouseClick(window.add_button, Qt.MouseButton.LeftButton)
                        APP.processEvents()
                self.assertEqual(uncaught, [])
                self.assertEqual(len(window.store.sources()), 3)
                self.assertEqual(window.tree.topLevelItemCount(), 3)
                self.assertEqual(window.store.get_field(work['id'], field['id'])['text'], 'HUMAN_REVIEW_TO_KEEP')
                self.assertEqual(window.store.get_field(work['id'], field['id'])['review_state'], 'REVIEWED')
                self.assertIn('已加入 2 個檔案', window.notice.text())
            finally:
                window.save_progress()
                window.close()
                APP.processEvents()

    def test_small_window_keeps_review_actions_visible_and_hides_them_in_overview(self):
        """No scrolling is needed to set review state or apply a correction."""
        from template_ai.review_tool.window import ReviewWindow
        with tempfile.TemporaryDirectory(prefix='review-small-window-') as raw:
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
                window.resize(980, 720)
                window.show()
                APP.processEvents()
                self.assertFalse(window.field_actions.isVisible())
                window.add_files([str(source)])
                registered = window.store.sources()[0]
                packet = {'schema_version': 1, 'status': 'ANALYSED',
                    'source': {'id': registered['id'], 'path': str(source),
                               'hash': hashlib.sha256(source.read_bytes()).hexdigest()},
                    'pages': [{'id': 'small-page', 'page': 1, 'image': str(preview),
                               'width_mm': 60., 'height_mm': 30., 'calibrated': True}],
                    'works': [{'id': 'small-work', 'page_id': 'small-page', 'page': 1,
                               'crop': {'x': 0., 'y': 0., 'w': 60., 'h': 30.},
                               'fields': [{'id': 'small-field', 'text': '0900-000-000',
                                           'kind': 'mobile',
                                           'rect': {'x': 5., 'y': 10., 'w': 25., 'h': 5.}}]}],
                    'issues': [], 'capabilities': {}}
                window.store.apply_analysis(registered['id'], packet)
                work = window.store.works()[0]
                field = work['fields'][0]
                window.select_work(work['id'])
                window.select_field(field['id'])
                APP.processEvents()
                self.assertEqual(window.size().toTuple(), (980, 720))
                for widget in (window.review_combo, window.apply_field_button):
                    self.assertTrue(widget.isVisible())
                    self.assertFalse(widget.visibleRegion().isEmpty())
                    self.assertEqual(widget.visibleRegion().boundingRect(), widget.rect())
                window.review_combo.setCurrentIndex(window.review_combo.findData('REVIEWED'))
                QTest.mouseClick(window.apply_field_button, Qt.MouseButton.LeftButton)
                self.assertEqual(window.store.get_field(work['id'], field['id'])['review_state'], 'REVIEWED')
                QTest.mouseClick(window.overview_button, Qt.MouseButton.LeftButton)
                APP.processEvents()
                self.assertTrue(window.overview_tree.isVisible())
                self.assertFalse(window.field_actions.isVisible())
                self.assertFalse(window.review_combo.isVisible())
                self.assertFalse(window.apply_field_button.isVisible())
                window.show_review()
                APP.processEvents()
                self.assertFalse(window.apply_field_button.visibleRegion().isEmpty())
                self.assertFalse(window.review_combo.visibleRegion().isEmpty())
            finally:
                window.save_progress()
                window.close()
                APP.processEvents()

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
