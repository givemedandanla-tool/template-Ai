"""Bounded acceptance through the actual small-tool window and worker.

Only --release-check invokes this module. All sources below are authored,
synthetic fixtures. This is not private Illustrator/font/corpus qualification.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sys
import time


def _require(value, message):
    if not value:
        raise RuntimeError(message)


def _digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def authored_sources(root):
    """Calibrated text/outline SVG and a PDF-compatible AI, never native AI."""
    from PySide6.QtCore import QMarginsF, QSizeF
    from PySide6.QtGui import QFont, QPageSize, QPainter, QPainterPath, QPdfWriter, QPen, QColor

    root = Path(root)
    svg = root / 'DEMO-001.svg'
    svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="60mm" height="30mm" '
        'viewBox="0 0 600 300"><rect x="1" y="1" width="598" height="298" '
        'fill="white" stroke="#335577" stroke-width="1"/>'
        '<g font-family="sans-serif" font-size="25" fill="#17324d">'
        '<text x="35" y="52">Review Demo Company</text>'
        '<text x="35" y="105">Lin Example</text>'
        '<text x="35" y="160">0900-000-000</text>'
        '<text x="35" y="212">hello@example.com</text></g></svg>', encoding='utf-8')
    ai = root / '示例作品.ai'
    writer = QPdfWriter(str(ai))
    writer.setResolution(72)
    writer.setPageSize(QPageSize(QSizeF(60, 30), QPageSize.Unit.Millimeter))
    writer.setPageMargins(QMarginsF(0, 0, 0, 0))
    painter = QPainter(writer)
    _require(painter.isActive(), '無法建立明確合成 PDF-compatible AI 測試作品')
    painter.setPen(QPen(QColor('#335577'), .5))
    painter.drawRect(1, 1, 168, 83)
    painter.setFont(QFont('Arial', 7))
    for y, text in [(15, 'Review Demo Company'), (32, 'Lin Example'),
                    (49, '0900-000-000'), (66, 'hello@example.com')]:
        painter.drawText(9, y, text)
    painter.end()
    # Render font outlines into vector paths: the source deliberately has no
    # readable <text> node, just like a common outlined-text delivery.
    outlines = QPainterPath()
    font = QFont('Arial')
    font.setPixelSize(27)
    for y, text in [(65, 'HELLO REVIEW'), (125, '0900-000-000'), (190, 'hello@example.com')]:
        outlines.addText(35, y, font, text)
    commands = []
    index = 0
    while index < outlines.elementCount():
        element = outlines.elementAt(index)
        if element.isMoveTo():
            commands.append(f'M {element.x:.5f} {element.y:.5f}')
        elif element.isLineTo():
            commands.append(f'L {element.x:.5f} {element.y:.5f}')
        elif element.isCurveTo():
            second, third = outlines.elementAt(index + 1), outlines.elementAt(index + 2)
            commands.append(f'C {element.x:.5f} {element.y:.5f} {second.x:.5f} '
                            f'{second.y:.5f} {third.x:.5f} {third.y:.5f}')
            index += 2
        index += 1
    outline = root / 'DEMO-outline.svg'
    outline.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="60mm" height="30mm" '
                       'viewBox="0 0 600 300"><rect x="1" y="1" width="598" height="298" '
                       'fill="white" stroke="#335577" stroke-width="1"/>'
                       '<path fill="#111111" fill-rule="evenodd" d="' + ' '.join(commands)
                       + '"/></svg>', encoding='utf-8')
    return [svg, ai, outline]


def exercise_discard_close(window, source, wait):
    """Actual close dialog while a real owned worker is still running."""
    from PySide6.QtCore import QTimer, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QMessageBox

    app = QApplication.instance()
    window.show()
    app.processEvents()
    window.add_files([str(source)])
    QTest.mouseClick(window.save_button, Qt.MouseButton.LeftButton)
    _require(not window.store.dirty, 'Discard fixture baseline was not saved')
    baseline = window.store.path.read_bytes()
    QTest.mouseClick(window.start_button, Qt.MouseButton.LeftButton)
    wait(lambda: window.jobs.busy and window.jobs._process.processId() > 0, 5)
    window.store.add_owner('UNSAVED_DISCARD_SENTINEL', 'PERSON')
    window._update_save_state()
    handled, errors = [], []

    def choose_discard():
        dialog = app.activeModalWidget()
        try:
            _require(isinstance(dialog, QMessageBox), 'Expected actual close dialog')
            button = next(button for button in dialog.buttons()
                          if button.text() == '放棄未保存修改')
            handled.append(True)
            QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        except Exception as error:
            errors.append(str(error))
            if dialog is not None:
                dialog.reject()

    QTimer.singleShot(15, choose_discard)
    window.close()
    wait(lambda: not window.jobs.is_running(), 10)
    app.processEvents()
    _require(handled and not errors, 'Actual discard interaction failed: ' + '; '.join(errors))
    _require(not window.isVisible(), 'Discard action did not close the window')
    _require(window.store.path.read_bytes() == baseline,
             'Discarded changes were written by background worker stop/finished callbacks')
    return {'saved_snapshot_byte_identical': True, 'actual_owned_worker_stopped': True,
            'actual_close_dialog_used': True}


def run(output_path):
    """Write output JSON even on failure; return an executable exit status."""
    from PySide6.QtCore import QEventLoop, QTimer, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton, QScrollArea, QInputDialog
    from . import __version__

    output = Path(output_path).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    root = output.parent / (output.stem + '-synthetic')
    # Never reuse an earlier run and turn stale screenshots into new evidence.
    root.mkdir(exist_ok=False)
    (root / 'SYNTHETIC_ONLY').write_text('NO_PRIVATE_DATA', encoding='ascii')
    app = QApplication.instance() or QApplication([])
    quit_on_last = app.quitOnLastWindowClosed()
    app.setQuitOnLastWindowClosed(False)
    checks = []
    details = {}
    dialogs = []
    windows = []
    result = {
        'schema_version': 1, 'status': 'FAIL', 'version': __version__,
        'actual_frozen_executable': bool(getattr(sys, 'frozen', False)),
        'fixture': 'AUTHORED_REVIEW_ACCEPTANCE_V1',
        'fixture_types': ['CALIBRATED_SVG', 'PDF_COMPATIBLE_AI_SIMULATION', 'OUTLINED_TEXT_SVG'],
        'worker_mode': 'ACTUAL_QPROCESS', 'checks': checks,
        'check_details': details, 'artifacts': [], 'source_unchanged': False,
        'private_data_included': False, 'real_corpus_qualified': False,
        'native_illustrator_private_format_qualified': False,
        'os_native_file_picker_automated': False,
    }
    started = time.monotonic()

    def checked(name, value=True, **evidence):
        _require(not dialogs, '操作出現非預期提示：' + '; '.join(dialogs))
        _require(value, name)
        checks.append(name)
        details[name] = evidence or {'status': 'PASS'}
        (root / 'progress.json').write_text(
            json.dumps({'checks': checks}, ensure_ascii=False, indent=2), encoding='utf-8')
        print('review-release-check:', name, flush=True)

    def wait(predicate, seconds=30):
        if predicate():
            return
        loop = QEventLoop()
        poll = QTimer()
        deadline = QTimer()
        deadline.setSingleShot(True)
        poll.timeout.connect(lambda: loop.quit() if predicate() or dialogs else None)
        deadline.timeout.connect(loop.quit)
        poll.start(20)
        deadline.start(round(seconds * 1000))
        try:
            loop.exec()
        finally:
            poll.stop()
            deadline.stop()
        _require(not dialogs, '操作出現非預期提示：' + '; '.join(dialogs))
        _require(predicate(), '背景操作未於限定時間完成')

    def capture(window, name):
        app.processEvents()
        path = root / (name + '.png')
        _require(window.grab().save(str(path)), '真實視窗截圖未保存')
        result['artifacts'].append({'path': str(path.relative_to(output.parent)),
                                    'sha256': _digest(path), 'kind': 'ACTUAL_QT_WINDOW'})

    def click(widget):
        # QTest can deliver events to a clipped child directly. Scroll it into
        # the actual viewport first so the probe does not hide a layout bug.
        for scroll in widget.window().findChildren(QScrollArea):
            if scroll.isAncestorOf(widget):
                scroll.ensureWidgetVisible(widget)
        app.processEvents()
        _require(widget.isVisible() and not widget.visibleRegion().isEmpty(),
                 '操作按鈕不在可見畫面中：' + widget.text())
        QTest.mouseClick(widget, Qt.MouseButton.LeftButton)
        app.processEvents()

    def drag(canvas, start_local, end_local):
        start = canvas.mapFromScene(canvas.local_to_scene(start_local))
        end = canvas.mapFromScene(canvas.local_to_scene(end_local))
        _require(canvas.viewport().rect().contains(start)
                 and canvas.viewport().rect().contains(end), '標記操作超出可見原稿範圍')
        QTest.mousePress(canvas.viewport(), Qt.MouseButton.LeftButton,
                         Qt.KeyboardModifier.NoModifier, start)
        QTest.mouseMove(canvas.viewport(), end, delay=10)
        QTest.mouseRelease(canvas.viewport(), Qt.MouseButton.LeftButton,
                           Qt.KeyboardModifier.NoModifier, end)
        app.processEvents()

    def overview_item(tree, match):
        def walk(item):
            if match(item):
                return item
            for index in range(item.childCount()):
                found = walk(item.child(index))
                if found is not None:
                    return found
            return None
        for index in range(tree.topLevelItemCount()):
            found = walk(tree.topLevelItem(index))
            if found is not None:
                return found
        raise RuntimeError('總覽缺少可定位的資料列')

    def refuse_unexpected_modal():
        dialog = app.activeModalWidget()
        if isinstance(dialog, QMessageBox):
            if dialog.windowTitle() == '離開前保存工作' and getattr(dialog.parent(), '_acceptance_discard', False):
                return
            dialogs.append(dialog.windowTitle() + ': ' + dialog.text())
            dialog.reject()

    watchdog = QTimer()
    watchdog.timeout.connect(refuse_unexpected_modal)
    watchdog.start(150)
    try:
        from .window import ReviewWindow

        window = ReviewWindow(root / 'data')
        windows.append(window)
        window.show()
        wait(window.isVisible, 10)
        checked('actual_review_window_opens', window.canvas.isVisible())
        checked('technical_overview_hidden_initially', not window.overview_tree.isVisible())
        capture(window, '01-empty-window')

        sources = authored_sources(root)
        source_hashes = {path.name: _digest(path) for path in sources}
        # The public add-files controller receives actual local paths. The OS
        # native picker is explicitly outside this automated smoke scope.
        window.add_files([str(path) for path in sources])
        checked('actual_add_files_entry_registers_three_sources', len(window.store.sources()) == 3)
        finished = []
        window.analysisFinished.connect(lambda: finished.append(True))
        heartbeats = []
        responsiveness = QTimer()
        responsiveness.timeout.connect(lambda: heartbeats.append(time.monotonic()))
        responsiveness.start(100)
        click(window.start_button)
        wait(lambda: bool(finished), 230)
        responsiveness.stop()
        checked('actual_qprocess_analysis_completes', len(window.store.works()) >= 3,
                gui_timer_events=len(heartbeats))
        checked('gui_event_loop_remains_responsive', len(heartbeats) >= 2)

        all_sources = window.store.sources()
        checked('svg_and_pdf_compatible_ai_have_real_previews', all(
            source.get('analysis', {}).get('pages') and all(
                Path(page['image']).is_file() for page in source['analysis']['pages'])
            for source in all_sources))
        capabilities = [source['analysis'].get('capabilities', {}) for source in all_sources]
        details['worker_capabilities'] = capabilities
        checked('actual_vector_analysis_executes', any(
            cap.get('vector_analysis_executed') for cap in capabilities))
        if result['actual_frozen_executable']:
            checked('actual_worker_uses_bundled_inkscape', all(
                cap.get('inkscape_runtime', {}).get('origin') == 'BUNDLED'
                for cap in capabilities))

        outline_source = next(source for source in all_sources if source['name'] == sources[2].name)
        outline_cap = outline_source['analysis']['capabilities']
        if outline_cap.get('ocr_available'):
            checked('actual_ocr_reads_authored_outline_source',
                    outline_cap.get('ocr_executed') and any(work.get('fields')
                                                           for work in outline_source['works']))
            result['ocr_scope'] = 'ACTUAL_LOCAL_OCR_EXECUTED_ON_AUTHORED_OUTLINES'
        else:
            checked('missing_ocr_is_explicit_for_outline_source', any(
                issue.get('code') == 'OCR_UNAVAILABLE' for issue in outline_source.get('issues', [])))
            result['ocr_scope'] = 'OCR_UNAVAILABLE_EXPLICIT_MANUAL_FALLBACK_NOT_OCR_QUALIFICATION'

        # Exercise a genuinely missing executable in an owned local worker,
        # not a mocked capability function. Preserve caller configuration.
        no_ocr = ReviewWindow(root / 'no-ocr-data')
        windows.append(no_ocr)
        no_ocr.show()
        no_ocr.add_files([str(sources[2])])
        missing_finished = []
        no_ocr.analysisFinished.connect(lambda: missing_finished.append(True))
        old_tesseract = os.environ.get('TEMPLATE_AI_TESSERACT')
        os.environ['TEMPLATE_AI_TESSERACT'] = str(root / 'intentionally-unavailable-tesseract.exe')
        try:
            click(no_ocr.start_button)
            wait(lambda: bool(missing_finished), 90)
        finally:
            if old_tesseract is None:
                os.environ.pop('TEMPLATE_AI_TESSERACT', None)
            else:
                os.environ['TEMPLATE_AI_TESSERACT'] = old_tesseract
        missing_source = no_ocr.store.sources()[0]
        checked('real_missing_ocr_worker_preserves_explicit_fallback',
                missing_source['analysis']['capabilities'].get('ocr_available') is False
                and any(issue.get('code') == 'OCR_UNAVAILABLE'
                        for issue in missing_source.get('issues', []))
                and bool(missing_source.get('works')))
        missing_work = missing_source['works'][0]
        no_ocr.select_work(missing_work['id'])
        missing_count = len(missing_work['fields'])
        next(action for action in no_ocr.add_mark_button.menu().actions()
             if action.text() == '文字欄位').trigger()
        crop = missing_work['crop']
        drag(no_ocr.canvas, (crop['w'] * .1, crop['h'] * .1),
             (crop['w'] * .4, crop['h'] * .3))
        checked('manual_annotation_works_when_ocr_executable_is_missing',
                len(no_ocr.store.get_work(missing_work['id'])['fields']) == missing_count + 1)
        click(no_ocr.save_button)
        capture(no_ocr, '05-no-ocr-manual-fallback')
        no_ocr.close()
        app.processEvents()
        window.raise_()
        window.activateWindow()

        work = next(work for work in window.store.works() if work.get('fields'))
        work_id = work['id']
        field = next((item for item in work['fields'] if '0900' in item.get('text', '')),
                     work['fields'][0])
        field_id = field['id']
        original_prediction = deepcopy(field['prediction'])
        window.select_work(work_id)
        app.processEvents()
        QTest.mouseClick(window.canvas.viewport(), Qt.MouseButton.LeftButton,
                         pos=window.canvas.field_center(field_id))
        app.processEvents()
        checked('canvas_click_updates_actual_editor',
                window.text_edit.toPlainText() == field['text'])

        owner = window.store.add_owner('Synthetic Person', 'PERSON')
        shared = window.store.add_owner('Synthetic Shared Person', 'PERSON')
        window.select_field(field_id)
        app.processEvents()
        owner_index = window.owner_combo.findData(owner['id'])
        _require(owner_index >= 0, '人物資料未接入實際歸屬選單')
        window.owner_combo.setCurrentIndex(owner_index)
        desired_kind = 'mobile'
        kind_index = window.kind_combo.findData(desired_kind)
        _require(kind_index >= 0, '欄位種類選單缺少手機')
        window.kind_combo.setCurrentIndex(kind_index)
        private_marker = 'PRIVATE_REVIEW_SENTINEL_91'
        window.text_edit.setPlainText('0900-000-000 ' + private_marker)
        review_index = window.review_combo.findData('REVIEWED')
        _require(review_index >= 0, '缺少明確人工核對狀態')
        window.review_combo.setCurrentIndex(review_index)
        matched_shared = False
        for index in range(window.shared_list.count()):
            item = window.shared_list.item(index)
            if item.data(Qt.ItemDataRole.UserRole) == shared['id']:
                item.setCheckState(Qt.CheckState.Checked)
                matched_shared = True
        _require(matched_shared, '共享人物未接入實際核對面板')
        click(window.apply_field_button)
        changed = window.store.get_field(work_id, field_id)
        checked('actual_editor_applies_content_kind_owner_and_sharing',
                changed['kind'] == desired_kind and changed['owner'] == owner['id']
                and shared['id'] in changed['shared_with'] and private_marker in changed['text'])
        checked('original_prediction_remains_separate', changed['prediction'] == original_prediction)

        # Exercise the real menu action, drawing gesture and controller; no
        # substituted annotation handler or preconstructed fake window.
        before_ids = {part['id'] for part in window.store.get_work(work_id)['fields']}
        action = next(action for action in window.add_mark_button.menu().actions()
                      if action.text() == '文字欄位')
        action.trigger()
        work = window.store.get_work(work_id)
        width, height = work['crop']['w'], work['crop']['h']
        drag(window.canvas, (width * .70, height * .70), (width * .88, height * .82))
        after = window.store.get_work(work_id)['fields']
        new_fields = [part for part in after if part['id'] not in before_ids]
        checked('actual_canvas_draw_creates_manual_annotation', len(new_fields) == 1)
        added_id = new_fields[0]['id']
        before_rect = deepcopy(new_fields[0]['rect'])
        window.select_field(added_id)
        click(window.resize_button)
        drag(window.canvas,
             (before_rect['x'] + before_rect['w'], before_rect['y'] + before_rect['h']),
             (before_rect['x'] + before_rect['w'] + width * .025,
              before_rect['y'] + before_rect['h'] + height * .03))
        resized = window.store.get_field(work_id, added_id)['rect']
        checked('actual_canvas_resize_updates_annotation_only',
                resized['w'] > before_rect['w'] and resized['h'] > before_rect['h'])
        remove = next(button for button in window.findChildren(QPushButton)
                      if button.text() == '移除這個標記')
        click(remove)
        checked('actual_remove_button_removes_only_annotation',
                added_id not in {part['id'] for part in window.store.get_work(work_id)['fields']})
        click(window.undo_button)
        checked('actual_undo_button_restores_removed_annotation',
                window.store.get_field(work_id, added_id)['rect'] == resized)
        window.select_field(field_id)

        other_id = next(part['id'] for part in window.store.get_work(work_id)['fields']
                        if part['id'] not in (field_id, added_id))
        QTest.mouseClick(window.canvas.viewport(), Qt.MouseButton.LeftButton,
                         pos=window.canvas.field_center(field_id))
        QTest.mouseClick(window.canvas.viewport(), Qt.MouseButton.LeftButton,
                         Qt.KeyboardModifier.ControlModifier,
                         window.canvas.field_center(other_id))
        checked('actual_multiselection_retains_both_relation_endpoints',
                set(window.canvas.selected_fields()) == {field_id, other_id})
        modal_seen = []
        modal_errors = []

        def select_group_relation():
            dialog = app.activeModalWidget()
            try:
                _require(isinstance(dialog, QInputDialog), '未開啟真正的關係選擇視窗')
                dialog.setTextValue('同一組')
                modal_seen.append(True)
                dialog.accept()
            except Exception as error:
                modal_errors.append(str(error))
                if dialog is not None:
                    dialog.reject()

        QTimer.singleShot(60, select_group_relation)
        click(window.relation_button)
        _require(not modal_errors and modal_seen, '關係視窗未完成真實操作')
        checked('actual_relation_dialog_creates_group', any(
            relation.get('kind') == 'group' and set(relation.get('field_ids', [])) == {field_id, other_id}
            for relation in window.store.get_work(work_id)['relations']))
        window.select_field(field_id)

        click(window.overview_button)
        app.processEvents()
        checked('overview_preserves_visible_original',
                window.overview_tree.isVisible() and window.canvas.isVisible())
        # Click the actual overview data row so controller wiring is covered.
        size_row = overview_item(window.overview_tree, lambda item:
            item.data(0, Qt.ItemDataRole.UserRole) in [('metric', 'width'), ['metric', 'width']])
        window.overview_tree.scrollToItem(size_row)
        QTest.mouseClick(window.overview_tree.viewport(), Qt.MouseButton.LeftButton,
                         pos=window.overview_tree.visualItemRect(size_row).center())
        app.processEvents()
        checked('actual_overview_row_draws_linked_dimensions', bool(window.canvas.measurement_items))
        capture(window, '02-overview-dimensions')
        QTest.mouseClick(window.canvas.viewport(), Qt.MouseButton.LeftButton,
                         pos=window.canvas.field_center(other_id))
        app.processEvents()
        checked('canvas_selection_updates_overview_without_leaving_mode',
                window.overview_tree.isVisible() and window.current_field_id == other_id)
        window.show_review()

        unchecked_before = sum(item['review_state'] == 'UNCHECKED'
                               for item in window.store.get_work(work_id)['fields'])
        if unchecked_before:
            click(window.complete_button)
            checked('completion_does_not_silently_review_unchecked',
                    sum(item['review_state'] == 'UNCHECKED'
                        for item in window.store.get_work(work_id)['fields']) == unchecked_before
                    and window.store.get_work(work_id)['review_state'] == 'UNCHECKED')
        remaining = [item for item in window.store.get_work(work_id)['fields'] if item['id'] != field_id]
        for item in remaining:
            window.store.update_field(work_id, item['id'], {'review_state': 'REVIEWED'})
        unknown_id = added_id
        window.select_field(unknown_id)
        window.review_combo.setCurrentIndex(window.review_combo.findData('UNKNOWN'))
        click(window.apply_field_button)
        click(window.complete_button)
        checked('explicit_unknown_survives_human_completion',
                window.store.get_field(work_id, unknown_id)['review_state'] == 'UNKNOWN'
                and window.store.get_work(work_id)['review_state'] == 'REVIEWED_WITH_UNKNOWNS')

        window.select_field(field_id)
        click(window.save_button)
        checked('actual_save_button_persists_session', not window.store.dirty)
        capture(window, '03-saved-review')
        saved = deepcopy(window.store.data)
        window.close()
        app.processEvents()
        reopened = ReviewWindow(root / 'data')
        windows.append(reopened)
        reopened.show()
        app.processEvents()
        restored = reopened.store.get_field(work_id, field_id)
        checked('actual_window_reopens_saved_corrections', restored == changed or (
            restored['text'] == changed['text'] and restored['owner'] == changed['owner']
            and restored['shared_with'] == changed['shared_with']
            and restored['prediction'] == original_prediction))
        checked('unknown_is_not_replaced_by_defaults_after_reopen',
                reopened.store.get_field(work_id, unknown_id)['review_state'] == 'UNKNOWN')
        checked('source_ids_and_work_ids_survive_reopen',
                [s['id'] for s in reopened.store.sources()] == [s['id'] for s in saved['sources']])

        discarded = ReviewWindow(root / 'discard-data')
        discarded._acceptance_discard = True
        discard_evidence = exercise_discard_close(discarded, sources[0], wait)
        checked('actual_discard_does_not_save_draft_on_worker_stop', **discard_evidence)
        # The discarded window is deliberately not passed to finally's save
        # cleanup, which would undo the very behavior being verified.
        discarded.deleteLater()
        app.processEvents()

        report = root / 'safe-report.json'
        reopened.export_report(str(report))
        raw_report = report.read_bytes()
        report_data = json.loads(raw_report.decode('utf-8'))

        def strings(value):
            if isinstance(value, str):
                yield value
            elif isinstance(value, dict):
                for key, part in value.items():
                    yield str(key)
                    yield from strings(part)
            elif isinstance(value, list):
                for part in value:
                    yield from strings(part)

        decoded_report = '\n'.join(strings(report_data))
        normalized_report = decoded_report.replace('\\', '/').casefold()
        checked('safe_diagnostic_excludes_private_content_and_paths',
                private_marker not in decoded_report
                and str(root).replace('\\', '/').casefold() not in normalized_report
                and all(path.name not in decoded_report for path in sources))
        for path in sources:
            _require(_digest(path) == source_hashes[path.name], '原稿內容遭到修改')
        result['source_unchanged'] = True
        checked('all_authored_sources_remain_byte_identical')
        capture(reopened, '04-reopened-window')
        result['status'] = 'PASS'
    except Exception as error:
        result['error'] = {'type': type(error).__name__, 'message': str(error)[:1200]}
    finally:
        result['elapsed_seconds'] = round(time.monotonic() - started, 3)
        for window in windows:
            try:
                # Close through the real handler after an explicit save so a
                # failed probe does not strand a hidden modal dialog.
                window.save_progress()
                window.close()
            except Exception:
                pass
        app.processEvents()
        watchdog.stop()
        app.setQuitOnLastWindowClosed(quit_on_last)
        if dialogs:
            result['status'] = 'FAIL'
            result['unexpected_dialogs'] = dialogs
        temp = output.with_suffix(output.suffix + '.tmp')
        temp.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        os.replace(temp, output)
    return 0 if result['status'] == 'PASS' else 1
