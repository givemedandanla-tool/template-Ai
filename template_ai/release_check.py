"""Bounded local packaged-application acceptance, with explicitly authored fixtures.

Only invoked by the hidden release-check entry. No tools, tests, private corpus,
fonts or training database are distributed with the application.
"""
import hashlib
import json
from pathlib import Path
import time


def require(value, message):
    if not value:
        raise RuntimeError(message)


def run(spec_path):
    from .offline_runtime import assert_local_path
    assert_local_path(spec_path)
    spec_path = Path(spec_path).resolve()
    spec = json.loads(spec_path.read_text(encoding='utf-8'))
    require(spec.get('fixture') == 'AUTHORED_RELEASE_ACCEPTANCE_V1', '需要明確合成驗證資料')
    root = Path(spec['root']).resolve()
    require(root == spec_path.parent, '驗證資料必須與明確合成標記位於同一目錄')
    require((root / 'SYNTHETIC_ONLY').read_text() == 'NO_PRIVATE_DATA', '缺少合成資料標記')
    from PySide6.QtWidgets import QApplication, QDialog, QComboBox, QPushButton, QMessageBox
    from PySide6.QtCore import Qt, QPointF, QEvent, QTimer
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtTest import QTest
    from . import __version__
    from .gui import MainWindow
    from .design_learning import CrossWorkLearning
    from .input_graph import InputGraph
    from .input_graph_dialog import InputGraphDialog
    from .offline_support import OfflineJournal, save_support_bundle, read_support_bundle
    app = QApplication.instance() or QApplication([])
    app.setApplicationVersion(__version__)
    output = root / 'evidence'
    output.mkdir(exist_ok=True)
    checks = []
    unexpected_messages = []
    window = None
    closing = False

    def refuse_unexpected_message():
        dialog = app.activeModalWidget()
        if isinstance(dialog, QMessageBox):
            if closing and dialog.windowTitle() == '當次工作尚未安全保存':
                next(b for b in dialog.buttons() if b.text() == '明確放棄當次操作並關閉').click()
                return
            unexpected_messages.append(dialog.text())
            print('release-check unexpected synthetic-fixture message:', dialog.text(), flush=True)
            dialog.reject()
    watchdog = QTimer()
    watchdog.timeout.connect(refuse_unexpected_message)
    watchdog.start(250)

    def checked(name, condition=True):
        require(not unexpected_messages, '操作出現非預期提示，未視為通過')
        require(condition, name)
        checks.append(name)
        (output / 'progress.json').write_text(json.dumps(dict(checks=checks)), encoding='utf-8')
        print('release-check:', name, flush=True)

    def wait(predicate, seconds=30):
        deadline = time.monotonic() + seconds
        while not predicate() and time.monotonic() < deadline:
            QTest.qWait(25)
        require(predicate(), '背景操作未於限定時間完成')

    def capture(name):
        app.processEvents()
        require(window.grab().save(str(output / (name + '.png'))), '截圖未保存')

    def modal(action, handler):
        errors = []
        observed = []
        def interact():
            dialog = app.activeModalWidget()
            try:
                require(isinstance(dialog, QDialog), '未開啟原始操作視窗')
                handler(dialog)
                observed.append(True)
            except Exception as error:
                errors.append(error)
                if dialog:
                    dialog.reject()
        QTimer.singleShot(50, interact)
        action()
        if errors:
            raise errors[0]
        require(observed, '未驗證原始視窗操作')

    result = dict(status='FAIL', version=__version__, phase=spec['phase'], checks=checks,
                  resource_measurement='SYNTHETIC_FIXED_LOAD_NOT_HARDWARE_PERFORMANCE',
                  scope='ACTUAL_EXECUTABLE_AUTHORED_FIXTURES_NOT_REAL_CORPUS_QUALIFICATION')
    try:
        window = MainWindow(root / 'data')
        # Reproduce the established GUI contract fixture, not shared-runner load.
        # Real admission/pressure is separately tested; this grants no output rights.
        from .runtime_resources import ResourceSnapshot
        class FixedLoad:
            def __init__(self): self.sequence = 0
            def snapshot(self):
                self.sequence += 1
                return ResourceSnapshot(time.monotonic(), self.sequence, 8*1024**3, 6*1024**3,
                     5, 4, 4*1024**3, 64*1024**2, (), basis='SYNTHETIC_TEST_FIXTURE_NOT_MEASUREMENT')
            def close(self): pass
        window.runtime.monitor.close()
        window.runtime.monitor = FixedLoad()
        window.runtime.ready_after = 0
        window.runtime.gui_lag = lambda: 0
        window.navigate_mode(2)
        window.show()
        app.processEvents()
        checked('version_in_actual_window', __version__ in window.windowTitle())
        desk = window.desktop_workspace
        if spec['phase'] == 'exercise':
            learning = CrossWorkLearning(window.library)
            model = learning.train(spec['dataset_id'], 'Release Fixture Author', approved=True)
            checked('actual_executable_trains_frozen_synthetic_dataset', bool(model['id']))
            active = learning.store.get('DESIGN_ACTIVE', 'local-layout')
            learning.activate(model['id'], active['revision'] if active else 0, 'Release Fixture Author',
                              dict(version='release-fixture', approved=True, production=False,
                                   basis='Explicit authored release acceptance, never production qualification'), True)
            graph = InputGraph.from_legacy([dict(name='Alex Example', title='Designer',
                      phone='+1 202 555 0100', email='alex@example.test')], [])
            window.adopt_input_graph(graph.data)
            editor = desk.ensure_editor()
            editor.solve()
            desk.refresh()
            app.processEvents()
            checked('input_generate_embedded_preview', bool(editor.canvas.boxes) and
                    desk.preview_stack.currentWidget() is editor.canvas)
            capture('packaged-preview')
            QTest.mouseClick(desk.primary, Qt.LeftButton)
            checked('confirm_actual_preview', bool(editor.sessions.current(editor.session_id)['confirmation']))
            before_graph = editor.sessions.current(editor.session_id)['input_graph']
            box, target = editor.canvas.boxes[:2]
            start = editor.canvas.mapFromScene(box.sceneBoundingRect().center())
            end = editor.canvas.mapFromScene(target.sceneBoundingRect().center() + QPointF(0, 3))
            viewport = editor.canvas.viewport()
            QTest.mousePress(viewport, Qt.LeftButton, Qt.NoModifier, start)
            movement = QMouseEvent(QEvent.MouseMove, QPointF(end), QPointF(viewport.mapToGlobal(end)),
                                   Qt.NoButton, Qt.LeftButton, Qt.NoModifier)
            app.sendEvent(viewport, movement)
            QTest.mouseRelease(viewport, Qt.LeftButton, Qt.NoModifier, end)
            wait(lambda: bool(editor.sessions.current(editor.session_id)['intents']))
            wait(lambda: not window.busy)
            row = editor.sessions.current(editor.session_id)
            checked('real_pointer_drag_preserves_data_invalidates_confirmation',
                    row['input_graph'] == before_graph and not row.get('confirmation'))
            capture('packaged-drag')

            def correct(dialog):
                require(isinstance(dialog, InputGraphDialog), '不是原資料更正視窗')
                field = next(f for f in dialog.graph.data['fields'] if f['kind'] == 'phone')
                control = dialog.field_editors[field['id']]
                control.selectAll()
                QTest.keyClicks(control, '+1 202 555 0199')
                dialog.refresh_warnings()
                QTest.mouseClick(dialog.adopt_button, Qt.LeftButton)
            modal(window.graph_button.click, correct)
            desk.refresh()
            checked('content_correction_clears_stale_preview',
                    desk.preview_stack.currentWidget() is window.output_canvas and not window.preview_button.isEnabled())
            desk.generate()
            wait(lambda: editor.solve_worker is None or not editor.solve_worker.isRunning())
            desk.refresh()
            row, _, _ = editor.sessions.checked_result(editor.session_id)
            checked('regenerate_latest_input', any(f['value'] == '+1 202 555 0199' for f in row['input_graph']['fields']))
            editor.confirm_preview()
            artifact = editor.sessions.export(editor.session_id, root / 'PREVIEW-synthetic.png')
            checked('allowed_preview_export_matches_saved_bytes', not artifact['production'] and
                    artifact['sha256'] == hashlib.sha256((root / 'PREVIEW-synthetic.png').read_bytes()).hexdigest())
            refused = False
            try:
                editor.sessions.export(editor.session_id, root / 'NOT-QUALIFIED-FINAL.png', preview=False)
            except ValueError:
                refused = True
            checked('unqualified_formal_export_still_refused', refused and not (root / 'NOT-QUALIFIED-FINAL.png').exists())
            spec['session_id'] = editor.session_id
            spec['saved_graph'] = row['input_graph']
            spec['artifact_id'] = artifact['id']
            spec['artifact_sha256'] = artifact['sha256']
            from .coverage_command import run_command
            checked('frozen_json_pipe_worker', run_command(window.library.root, 'BATCHES', {})['total'] == 0)
            _pause_worker(spec, checked)
            spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding='utf-8')
        elif spec['phase'] == 'resume':
            def resume(dialog):
                choice = dialog.findChild(QComboBox, 'resumeDraftChoice')
                require(choice is not None and choice.findData(spec['session_id']) >= 0, '已保存稿件未找到')
                choice.setCurrentIndex(choice.findData(spec['session_id']))
                QTest.mouseClick(dialog.findChild(QPushButton, 'resumeDraftAccept'), Qt.LeftButton)
            modal(desk.resume_saved, resume)
            editor = desk.ensure_editor()
            row = editor.sessions.current(spec['session_id'])
            checked('new_executable_process_restores_same_graph_intents_confirmation',
                    editor.session_id == spec['session_id'] and row['input_graph'] == spec['saved_graph'] and
                    bool(row['intents']) and bool(row['confirmation']))
            checked('confirmed_export_replay_unchanged_after_restart',
                    editor.sessions.replay_artifact(spec['artifact_id'])['sha256'] == spec['artifact_sha256'])
            _resume_worker(spec, checked)
        else:
            raise ValueError('未知驗證階段')
        journal = OfflineJournal(root / 'data')
        journal.record('APPLICATION', 'APP_CLOSED')
        report = output / ('support-' + spec['phase'] + '.zip')
        save_support_bundle(report, journal.bundle())
        public = read_support_bundle(report.read_bytes())
        checked('safe_report_does_not_include_authored_content',
                all(private not in str(public) for private in ['alex@example.test', '+1 202 555 0199', 'Alex Example']))
        capture('packaged-' + spec['phase'])
        closing = True
        window.close()
        checked('actual_window_close_preserves_durable_session', window.library.closed)
        result['status'] = 'PASS'
    except Exception as error:
        result['failure_type'] = type(error).__name__
        # Synthetic acceptance only. No arbitrary payload, path or traceback persisted.
        result['failure_check'] = 'after:' + (checks[-1] if checks else 'startup')
    finally:
        watchdog.stop()
        if window:
            if window.desktop_workspace.editor:
                editor = window.desktop_workspace.editor
                if editor.solve_worker and editor.solve_worker.isRunning():
                    editor.cancel_solve()
                    editor.solve_worker.wait(10000)
            window.pool.waitForDone(10000)
            if not window.library.closed:
                window.input_timer.stop()
                window.execution_queue.cancel_event.set()
                window.font_manager.close()
                window.library.close()
                window.close()
            app.processEvents()
        (output / ('packaged-' + spec['phase'] + '.json')).write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return 0 if result['status'] == 'PASS' else 1


def _pause_worker(spec, checked):
    from .storage import Library
    from .automatic_training import AutomaticTraining
    from .runtime_worker import run_isolated
    from .runtime_resources import ResourceDecision
    library = Library(spec['worker_root'])
    try:
        service = AutomaticTraining(library)
        job = service.get(spec['job_id'])
        claimed = service.claim(job['id'], job['revision'], True)
        allow = ResourceDecision(True, 'READY', (), 0, 0, None)
        hold = ResourceDecision(False, 'PAUSED_RESOURCES', ('SYNTHETIC_RELEASE_PRESSURE',), 0, 0, None)
        paused = run_isolated(library.root, 'AUTO_JOB', job['id'], claimed['owner']['token'],
                              admission=lambda: hold if service.store.count('AUTO_UNIT') else allow)
        checked('actual_frozen_background_worker_pauses_at_saved_boundary',
                paused['phase'] == 'PAUSED_RESOURCES' and service.store.count('AUTO_UNIT') == 1)
        spec['paused_unit'] = service.store.records('AUTO_UNIT')[0]
    finally:
        library.close()


def _resume_worker(spec, checked):
    from .storage import Library
    from .automatic_training import AutomaticTraining
    from .runtime_worker import run_isolated
    from .runtime_resources import ResourceDecision
    library = Library(spec['worker_root'])
    try:
        service = AutomaticTraining(library)
        job = service.get(spec['job_id'])
        checked('restart_does_not_automatically_resume_worker', job['phase'] == 'PAUSED_RESOURCES')
        claimed = service.claim(job['id'], job['revision'], True)
        done = run_isolated(library.root, 'AUTO_JOB', job['id'], claimed['owner']['token'],
                            admission=lambda: ResourceDecision(True, 'READY', (), 0, 0, None))
        checked('explicit_restart_reuses_completed_unit_without_rewriting',
                done['phase'] == 'COMPLETED_WITH_EXCEPTIONS' and done['items'][0]['reused_units'] >= 1 and
                service.store.get('AUTO_UNIT', spec['paused_unit']['id']) == spec['paused_unit'])
    finally:
        library.close()
