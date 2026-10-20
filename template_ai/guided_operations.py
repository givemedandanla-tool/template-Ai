"""Guided local source, evaluation, capacity and qualification operations.

This view writes only through the existing learning services.  Draft cases are
local workspace state, not accepted evidence; every adoption gate remains in the
core.  No network client, duplicate model store or synthetic promotion path.
"""
from copy import deepcopy
import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QPushButton, QComboBox, QLineEdit, QCheckBox, QDoubleSpinBox,
    QSpinBox, QTabWidget, QWidget, QPlainTextEdit, QListWidget, QScrollArea)

from .design_learning import CrossWorkLearning
from .design_jobs import DesignJobs
from .design_evaluation import DesignEvaluation
from .design_capacity import LocalCapacityCalibration, joint_demand
from .design_qualification import DesignQualification, validate_certificate
from .design_session import _candidate
from .input_graph import InputGraph
from .model import new_id
from .training_store import digest
from .family_workspace import records


class GuidedOperationsDialog(QDialog):
    """An actual local workflow, opened with ``GuidedOperationsDialog(main)``."""
    def __init__(self, owner):
        super().__init__(owner)
        self.window = owner
        self.service_window = owner if hasattr(owner, 'run_job') else getattr(owner, 'service_window', None)
        self.library = owner.library
        self.learning = CrossWorkLearning(self.library)
        self.jobs = DesignJobs(self.library)
        self.store = self.jobs.store
        self.evaluation = DesignEvaluation(self.library)
        self.capacity = LocalCapacityCalibration(self.library)
        self.qualification = DesignQualification(self.library)
        self.worker = None
        self.close_after_worker = False
        self.children_dialogs = []
        self.cases = []
        self.case_model = None
        self.pending_certificate = None
        self.setWindowTitle('進階工作引導')
        self.resize(1120, 790)
        self.setMinimumSize(720, 520)
        box = QVBoxLayout(self)
        self.summary = QLabel('依序核對作品、準備獨立案例、檢查適合範圍，再審查正式啟用。所有資料留在本機。')
        self.summary.setWordWrap(True); self.summary.setTextFormat(Qt.PlainText)
        box.addWidget(self.summary)
        common = QFormLayout()
        self.actor = QLineEdit(); self.actor.setPlaceholderText('填寫本次核對人員')
        common.addRow('核對人員', self.actor); box.addLayout(common)
        self.tabs = QTabWidget(); box.addWidget(self.tabs, 1)
        self.build_preparation(); self.build_evaluation(); self.build_capacity(); self.build_qualification()
        self.details = QPlainTextEdit(); self.details.setReadOnly(True); self.details.setMaximumHeight(130)
        self.details.setVisible(False); box.addWidget(self.details)
        bottom = QHBoxLayout()
        self.detail_toggle = QCheckBox('顯示技術詳情'); self.detail_toggle.toggled.connect(self.details.setVisible)
        bottom.addWidget(self.detail_toggle)
        self.refresh_button = self.button(bottom, '重新讀取本機狀態', self.refresh)
        self.button(bottom, '關閉', self.close); box.addLayout(bottom)
        self.restore(); self.refresh()

    def page(self, title, description):
        host = QWidget(); layout = QVBoxLayout(host)
        note = QLabel(description); note.setWordWrap(True); layout.addWidget(note)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(host)
        self.tabs.addTab(scroll, title)
        return layout

    def button(self, layout, title, action):
        button = QPushButton(title); button.clicked.connect(lambda: self.attempt(action)); layout.addWidget(button)
        return button

    def say(self, summary, details=None):
        self.summary.setText(summary)
        if details is not None:
            self.details.setPlainText(details if isinstance(details, str) else json.dumps(details, ensure_ascii=False, indent=2))

    def attempt(self, action):
        try:
            return action()
        except (ValueError, KeyError, TypeError, OSError) as error:
            self.record_problem(str(error), error)
            from .production_report import explain_error
            report = explain_error(error)
            self.say(report['summary'] + ' ' + report['next_step'], report['details'])
            return None

    def record_problem(self, message, error=None):
        controller = getattr(self.window, 'offline_support', None)
        if controller is not None:
            # The controller classifies fixed codes and never persists this text.
            controller.record_problem(message, error=error)

    def worker_failed(self, message):
        self.record_problem(message, RuntimeError(message))
        self.say('本次驗證遇到問題；資料仍在，可查看詳情後接續。', message)

    def reviewer(self):
        value = self.actor.text().strip()
        if not value:
            raise ValueError('請先填寫核對人員，再保存審查結果。')
        return value

    def current_policy(self):
        # Preview-only canvases never emit edits or acquire production rights.
        return {}

    @staticmethod
    def evidence(widget):
        value = widget.text().strip()
        if not value:
            raise ValueError('請填寫實際核對依據，不能以空白或預設文字代替。')
        return value

    def build_preparation(self):
        layout = self.page('1 核對作品', '先確認作品的文字、字型與欄位來源。來源不完整時可保留待核對，不會自動視為正式合格。')
        self.local_state = QLabel(); self.local_state.setWordWrap(True); layout.addWidget(self.local_state)
        self.button(layout, '核對作品與字型', lambda: self.open_existing(0))
        self.button(layout, '建立或接續學習', lambda: self.open_existing(1))
        self.button(layout, '檢查模板群與共用規則', lambda: self.open_existing(3))
        layout.addWidget(QLabel('已確認的舊稿及固定版型保留原版本。核對與學習不會默默改寫它們。'))
        layout.addStretch()

    def open_existing(self, index):
        if self.worker and self.worker.isRunning():
            raise ValueError('請先等目前驗證完成，或暫停後再核對來源。')
        if getattr(self.window, 'busy', False):
            raise ValueError('目前有背景工作，請完成或暫停後再開啟。')
        from .design_learning_dialog import DesignLearningDialog
        dialog = DesignLearningDialog(self.window)
        dialog.tabs.setCurrentIndex(index)
        self.children_dialogs.append(dialog)
        # Keep the real tool alive; its own closeEvent protects pending workers.
        dialog.finished.connect(lambda _=0, item=dialog: self._child_finished(item))
        dialog.open()
        return dialog

    def _child_finished(self, dialog):
        if dialog in self.children_dialogs: self.children_dialogs.remove(dialog)
        dialog.deleteLater(); self.refresh()

    def build_evaluation(self):
        layout = self.page('2 準備驗證', '驗證案例須來自未參與擬合的資料。容量使用驗證集合；正式資格使用另行封存的保留集合。來源與對應依據都要人工核對。')
        form = QFormLayout(); self.models = QComboBox(); form.addRow('要檢查的規則版本', self.models)
        self.split = QComboBox(); self.split.addItem('驗證集合：學習適合範圍', 'VALIDATION'); self.split.addItem('封存保留集合：檢查正式資格', 'HOLDOUT')
        self.sample = QComboBox(); form.addRow('案例用途', self.split); form.addRow('對應的獨立作品', self.sample)
        self.origin = QComboBox(); self.origin.addItem('自製／合成測試資料', 'AUTHORED_SYNTHETIC'); self.origin.addItem('本機真實且已授權的作品', 'REAL_AUTHORIZED_CORPUS'); form.addRow('資料來源', self.origin)
        sizes = QHBoxLayout(); self.width = QDoubleSpinBox(); self.height = QDoubleSpinBox()
        # InputGraphDialog and Logo selection use this existing size contract.
        self.out_w = self.width; self.out_h = self.height
        for control, value in [(self.width, 90.), (self.height, 54.)]:
            control.setRange(1., 2000.); control.setDecimals(2); control.setValue(value); control.setSuffix(' mm'); sizes.addWidget(control)
        form.addRow('成品寬度／高度', sizes)
        self.case_basis = QLineEdit(); self.case_basis.setPlaceholderText('這份輸入與獨立作品相對應的實際依據'); form.addRow('案例核對依據', self.case_basis)
        layout.addLayout(form)
        self.button(layout, '填寫這個案例的資料', self.edit_case)
        self.case_summary = QLabel('尚未填寫案例資料。'); self.case_summary.setWordWrap(True); layout.addWidget(self.case_summary)
        self.button(layout, '加入待驗證案例', self.add_case)
        self.case_list = QListWidget(); self.case_list.setMinimumHeight(90); layout.addWidget(self.case_list)
        self.button(layout, '移除選取案例', self.remove_case)
        self.eval_approved = QCheckBox('已逐一核對來源、用途與獨立性；這些案例不會反過來參與本次模型擬合。'); layout.addWidget(self.eval_approved)
        self.start_button = self.button(layout, '保存並開始驗證', self.start_evaluation)
        self.pause_button = self.button(layout, '完成目前案例後暫停', self.pause)
        self.resume_jobs = QComboBox(); layout.addWidget(self.resume_jobs)
        self.button(layout, '接續這份驗證', self.resume)
        self.models.currentIndexChanged.connect(self.model_changed); self.split.currentIndexChanged.connect(self.load_samples)
        self.case_graph = None

    def model_changed(self):
        self.load_samples()
        if self.case_model and self.case_model != self.models.currentData():
            self.say('已改選規則版本。待驗證案例仍屬原版本；請切回原版本或先移除案例，避免誤配。')

    def load_samples(self):
        self.sample.clear()
        identity = self.models.currentData()
        if not identity: return
        try: _, dataset = self.learning.checked_model(identity)
        except (ValueError, KeyError): return
        for index, row in enumerate(dataset['entries']):
            if row['role'] == self.split.currentData():
                try: title = self.library.artwork(row['work_id'])['name']
                except (ValueError, KeyError): title = '獨立作品 ' + str(index + 1)
                self.sample.addItem(title + ' · 樣本版本 ' + str(row['sample_revision']), row['sample_id'])

    def edit_case(self):
        from .input_graph_dialog import InputGraphDialog
        graph = self.case_graph or InputGraph.from_legacy([dict(name='')], []).data
        dialog = InputGraphDialog(self, deepcopy(graph))
        try:
            if dialog.exec() == QDialog.Accepted:
                self.set_case_graph(dialog.graph.data)
        finally: dialog.deleteLater()

    def set_case_graph(self, graph):
        value = InputGraph(deepcopy(graph)); self.case_graph = value.data
        self.case_summary.setText('已填寫 ' + str(len(value.data['fields'])) + ' 項資料。尚未加入或採用為驗證證據。')

    def source_candidates(self):
        return []

    def input_data(self):
        return self.window.input_data()

    def add_case(self):
        model_id = self.models.currentData(); sample_id = self.sample.currentData()
        if not model_id or not sample_id: raise ValueError('請先選擇規則版本與對應的獨立作品。')
        if not self.case_graph: raise ValueError('請先填寫這個案例的資料。')
        if self.case_model and self.case_model != model_id: raise ValueError('待驗證案例屬於另一規則版本；請先移除或切回原版本。')
        if self.cases:
            _, dataset = self.learning.checked_model(model_id)
            roles = {row['sample_id']: row['role'] for row in dataset['entries']}
            if any(roles.get(row['sample_id']) != self.split.currentData() for row in self.cases):
                raise ValueError('適合範圍與正式資格使用不同集合。請先完成目前這批案例，再建立另一用途的工作。')
        basis = self.evidence(self.case_basis)
        self.cases.append(dict(id=new_id(), sample_id=sample_id, input_graph=deepcopy(self.case_graph),
            width_mm=self.width.value(), height_mm=self.height.value(), truth_refs=[basis]))
        self.case_model = model_id; self.case_graph = None; self.case_basis.clear()
        self.case_summary.setText('案例已加入。請填寫下一個案例，或核對後開始驗證。')
        self.render_cases(); self.remember()

    def render_cases(self):
        self.case_list.clear()
        for index, row in enumerate(self.cases):
            self.case_list.addItem('案例 ' + str(index + 1) + ' · ' + str(len(row['input_graph']['fields'])) + ' 項資料 · ' + str(row['width_mm']) + ' × ' + str(row['height_mm']) + ' mm')

    def remove_case(self):
        row = self.case_list.currentRow()
        if row < 0: raise ValueError('請先選擇要移除的待驗證案例。')
        self.cases.pop(row)
        if not self.cases: self.case_model = None
        self.render_cases(); self.remember()

    def start_evaluation(self):
        actor = self.reviewer()
        if not self.eval_approved.isChecked(): raise ValueError('請先逐一核對案例來源、用途與獨立性。')
        if not self.cases or self.case_model != self.models.currentData(): raise ValueError('請加入屬於目前規則版本的案例。')
        if self.worker and self.worker.isRunning(): raise ValueError('目前已在處理驗證工作。')
        job = self.evaluation.create(self.case_model, deepcopy(self.cases),
            dict(version='guided-local-evaluation-1', approved=True, candidate_budget=32), actor,
            origin=self.origin.currentData(), review_refs=sorted({x for row in self.cases for x in row['truth_refs']}), approved=True)
        self.cases = []; self.case_model = None; self.render_cases(); self.remember()
        self.start_job(job)
        return job

    def start_job(self, job):
        if self.worker and self.worker.isRunning(): raise ValueError('目前已有驗證正在執行。')
        from .design_learning_dialog import DesignWorker
        claimed = self.jobs.claim(job['id'], job['revision'])
        self.worker = DesignWorker(self.library.root, job['id'], claimed['owner']['token'], self)
        self.worker.progress.connect(lambda row: self.say('已保存 ' + str(row['done']) + '／' + str(row['total']) + ' 個驗證案例。'))
        self.worker.completed.connect(lambda row: self.say('驗證結果已保存，可接著核對適合範圍或正式資格。' if row['phase'] == 'COMPLETE' else '已暫停，已完成的案例仍在本機。'))
        self.worker.failed.connect(self.worker_failed)
        self.worker.finished.connect(self.worker_finished); self.start_button.setEnabled(False); self.worker.start()

    def pause(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel.set(); self.say('將在完成目前案例後暫停，已保存的結果不會遺失。')
        else: self.say('目前沒有正在執行的驗證。')

    def resume(self):
        identity = self.resume_jobs.currentData()
        if not identity: raise ValueError('目前沒有可以接續的驗證。')
        self.start_job(self.jobs.current(identity))

    def worker_finished(self):
        self.start_button.setEnabled(True); self.refresh()
        if self.close_after_worker: self.close()

    def build_capacity(self):
        layout = self.page('3 學習適合範圍', '逐份查看驗證稿，再記錄是否符合合格作品風格。範圍只適用於已驗證條件，不能推成所有作品的字數或欄位上限。')
        self.capacity_jobs = QComboBox(); self.capacity_cases = QComboBox()
        layout.addWidget(self.capacity_jobs); layout.addWidget(self.capacity_cases)
        from .design_learning_dialog import RelativeCanvas
        self.capacity_canvas = RelativeCanvas(self); self.capacity_canvas.setMinimumHeight(220); layout.addWidget(self.capacity_canvas)
        self.capacity_result = QLabel(); self.capacity_result.setWordWrap(True); layout.addWidget(self.capacity_result)
        form = QFormLayout(); self.style = QComboBox(); self.style.addItem('尚未決定', None); self.style.addItem('符合合格作品風格', True); self.style.addItem('不符合', False)
        self.style_basis = QLineEdit(); form.addRow('這份稿件', self.style); form.addRow('實際核對依據', self.style_basis); layout.addLayout(form)
        self.button(layout, '保存這份稿件的核對', self.review_style)
        self.capacity_minimum = QSpinBox(); self.capacity_minimum.setRange(5,10000); self.capacity_minimum.setValue(5)
        self.capacity_lower = QDoubleSpinBox(); self.capacity_lower.setRange(.01,.99); self.capacity_lower.setValue(.8); self.capacity_lower.setSingleStep(.01)
        self.capacity_alpha = QDoubleSpinBox(); self.capacity_alpha.setDecimals(3); self.capacity_alpha.setRange(.001,.499); self.capacity_alpha.setValue(.05)
        self.capacity_bins = QLineEdit(); self.capacity_bins.setPlaceholderText('每個聯合需求維度的分組寬度，以逗號分隔')
        form = QFormLayout(); form.addRow('至少幾組獨立作品', self.capacity_minimum); form.addRow('成功率下界至少', self.capacity_lower); form.addRow('單側錯誤機率', self.capacity_alpha); form.addRow('進階：聯合需求分組寬度', self.capacity_bins); layout.addLayout(form)
        self.capacity_approved = QCheckBox('已核對每份驗證稿及上述統計條件；只建立有證據的適合範圍。'); layout.addWidget(self.capacity_approved)
        note = QLabel('預填數值是待核對的統計起點，不是學到的字數或欄位上限。最低組數達標也不保證成功率下界達標。'); note.setWordWrap(True); layout.addWidget(note)
        self.button(layout, '建立適合範圍', self.calibrate)
        self.capacity_jobs.currentIndexChanged.connect(self.load_capacity_cases); self.capacity_cases.currentIndexChanged.connect(self.show_capacity_case)

    def completed_jobs(self):
        rows = records(self.store, 'DESIGN_JOB')
        return [self.jobs.current(row['id']) for row in rows if row.get('kind') == 'EVALUATE_LAYOUTS']

    def load_capacity_cases(self):
        self.capacity_cases.clear(); self.capacity_bins.clear()
        identity = self.capacity_jobs.currentData()
        if not identity: self.capacity_result.setText('尚無已完成的驗證集合稿件。請先到「準備驗證」建立並完成案例。'); return
        for index, row in enumerate(self.jobs.results(identity)):
            if row['role'] == 'VALIDATION': self.capacity_cases.addItem('驗證稿 ' + str(index + 1), index)

    def chosen_result(self, choices, cases):
        identity = choices.currentData(); index = cases.currentData()
        if not identity or index is None: raise ValueError('請先選擇已完成的稿件。')
        job = self.jobs.current(identity); rows = self.jobs.results(identity)
        if not 0 <= index < len(rows): raise ValueError('稿件已改變，請重新讀取狀態。')
        return job, index, rows[index]

    def show_capacity_case(self):
        self.style.setCurrentIndex(0); self.style_basis.clear()
        if self.capacity_cases.currentData() is None: return
        job, index, row = self.chosen_result(self.capacity_jobs, self.capacity_cases)
        serialized = row['learned'].get('serialized')
        self.capacity_canvas.scene().clear()
        if serialized:
            candidate = _candidate(serialized); self.capacity_canvas.show_candidate(candidate, editable=False)
            try:
                context, demand = joint_demand(candidate, InputGraph(job['plan']['items'][index]['input_graph']), job['plan']['items'][index]['width_mm'], job['plan']['items'][index]['height_mm'])
                if not self.capacity_bins.text(): self.capacity_bins.setText(', '.join(str(4. if i%2 == 0 else .5) for i in range(len(demand))))
            except (ValueError, KeyError, TypeError):
                self.capacity_bins.clear()
                self.say('這份稿件的完整文字量測仍有缺項。可以查看與核對，但目前不能用它建立適合範圍。')
        saved = self.store.get('DESIGN_JOB_ITEM', self.jobs.item_key(job['id'], index))
        review = self.store.get('DESIGN_STYLE_REVIEW', digest([job['id'], index, saved['result_digest']]))
        self.capacity_result.setText(('已保存風格核對，不能覆寫。' if review else '尚未核對風格。') + (' 這份結果可供檢查。' if serialized else ' 這份案例未取得可排版結果，不會當成合格。'))

    def review_style(self):
        job, index, row = self.chosen_result(self.capacity_jobs, self.capacity_cases)
        selected = self.style.currentData()
        if type(selected) is not bool: raise ValueError('請先選擇是否符合合格作品風格。')
        result = self.capacity.review_case(job['id'], index, selected, self.reviewer(), self.evidence(self.style_basis), approved=True)
        self.say('這份稿件的核對已保存。它仍不代表正式模型資格。'); self.show_capacity_case(); return result

    def calibrate(self):
        if not self.capacity_approved.isChecked(): raise ValueError('請先核對每份驗證稿及統計條件。')
        identity = self.capacity_jobs.currentData()
        if not identity: raise ValueError('目前沒有可建立適合範圍的驗證工作。')
        try: bins = [float(v.strip()) for v in self.capacity_bins.text().split(',')]
        except ValueError: raise ValueError('聯合需求分組寬度須為以逗號分隔的正數。')
        result = self.capacity.from_evaluation(identity, dict(version='guided-local-capacity-1', minimum_independent_groups=self.capacity_minimum.value(),
            minimum_success_lower_bound=self.capacity_lower.value(), alpha=self.capacity_alpha.value(), bin_widths=bins), self.reviewer(), approved=True)
        eligible = sum(cell['status'] == 'VALIDATED_EMPIRICAL_REGION' for cell in result['artifact']['cells'])
        self.say('已保存適合範圍；目前有 ' + str(eligible) + ' 個條件區域符合所選證據門檻。其餘保持未知，不會當作硬上限。', dict(record_id=result['id'], scope=result['scope']))
        return result

    def build_qualification(self):
        layout = self.page('4 審查正式啟用', '只有本機真實授權資料、獨立封存作品及完整審查，才可能取得正式資格。自製測試資料可驗證流程，不能轉成生產證書。')
        self.qualification_jobs = QComboBox(); self.qualification_cases = QComboBox(); layout.addWidget(self.qualification_jobs); layout.addWidget(self.qualification_cases)
        self.qualification_state = QLabel(); self.qualification_state.setWordWrap(True); layout.addWidget(self.qualification_state)
        from .design_learning_dialog import RelativeCanvas
        pair = QHBoxLayout(); self.learned_canvas = RelativeCanvas(self); self.baseline_canvas = RelativeCanvas(self)
        for title, canvas in [('新規則稿', self.learned_canvas), ('基準稿', self.baseline_canvas)]:
            pane = QVBoxLayout(); pane.addWidget(QLabel(title)); canvas.setMinimumHeight(180); pane.addWidget(canvas); pair.addLayout(pane)
        layout.addLayout(pair)
        self.preference_state = QLabel(); self.preference_state.setWordWrap(True); layout.addWidget(self.preference_state)
        self.preference = QComboBox()
        for title, code in [('尚未決定',None),('新規則稿較適合','LEARNED'),('兩份相當','TIE'),('基準稿較適合','BASELINE'),('兩份都不適合','NEITHER')]: self.preference.addItem(title, code)
        self.preference_basis = QLineEdit(); form = QFormLayout(); form.addRow('逐稿比較', self.preference); form.addRow('比較依據', self.preference_basis); layout.addLayout(form)
        self.button(layout, '保存這份稿件的比較', self.review_preference)
        self.corpus_basis = QLineEdit(); form = QFormLayout(); form.addRow('來源及獨立性核對依據', self.corpus_basis); layout.addLayout(form)
        self.real_authorized = QCheckBox('已核對這批是真實且已授權的本機作品。'); layout.addWidget(self.real_authorized)
        self.lineage_reviewed = QCheckBox('已核對近似重複來源及作品分組的獨立性。'); layout.addWidget(self.lineage_reviewed)
        self.button(layout, '保存本機來源審查', self.review_corpus)
        self.corpus_reviews = QComboBox(); layout.addWidget(self.corpus_reviews)
        self.qual_minimum = QSpinBox(); self.qual_minimum.setRange(5,10000); self.qual_minimum.setValue(5)
        self.qual_feasible = QDoubleSpinBox(); self.qual_feasible.setRange(.5,1.); self.qual_feasible.setValue(.9)
        self.qual_preference = QDoubleSpinBox(); self.qual_preference.setRange(.5,1.); self.qual_preference.setValue(.8)
        self.qual_basis = QLineEdit(); form = QFormLayout(); form.addRow('至少幾組封存作品', self.qual_minimum); form.addRow('可排版比例至少', self.qual_feasible); form.addRow('新稿勝出或相當比例至少', self.qual_preference); form.addRow('採用這些門檻的依據', self.qual_basis); layout.addLayout(form)
        self.qual_approved = QCheckBox('已審查上述結果與門檻；同意檢查並保存目前數位排版範圍的資格。'); layout.addWidget(self.qual_approved)
        self.button(layout, '檢查並保存資格', self.approve_qualification)
        self.button(layout, '啟用已通過資格的規則', self.activate_qualified)
        self.qualification_jobs.currentIndexChanged.connect(self.load_qualification_cases); self.qualification_cases.currentIndexChanged.connect(self.show_qualification_case)

    def load_qualification_cases(self):
        self.pending_certificate = None; self.qualification_cases.clear(); self.corpus_reviews.clear()
        identity = self.qualification_jobs.currentData()
        if not identity:
            self.qualification_state.setText('尚無已完成的封存稿件。可先到「準備驗證」建立封存案例；真實資格不影響自製案例的流程測試。')
            return
        job = self.jobs.current(identity)
        self.qualification_state.setText('這批是自製／合成測試，只能檢查流程；不能保存真實來源資格。' if job['plan']['origin'] != 'REAL_AUTHORIZED_CORPUS' else '這批標記為本機真實作品，仍需逐稿比較、來源審查及全部核心資格檢查。')
        for index, row in enumerate(self.jobs.results(identity)):
            if row['role'] == 'HOLDOUT': self.qualification_cases.addItem('封存稿 ' + str(index + 1), index)
        for row in records(self.store, 'DESIGN_CORPUS_REVIEW'):
            if row['job_id'] == identity: self.corpus_reviews.addItem('已保存的來源審查 · ' + row['id'][:8], row['id'])

    def show_qualification_case(self):
        self.preference.setCurrentIndex(0); self.preference_basis.clear()
        if self.qualification_cases.currentData() is None: return
        _, _, row = self.chosen_result(self.qualification_jobs, self.qualification_cases)
        for canvas, key in [(self.learned_canvas, 'learned'), (self.baseline_canvas, 'baseline')]:
            canvas.scene().clear(); serialized = row[key].get('serialized')
            if serialized: canvas.show_candidate(_candidate(serialized), editable=False)
        both = all(row[key].get('placement_digest') for key in ['learned', 'baseline'])
        self.preference_state.setText('請對照兩份實際稿件，再保存比較依據。' if both else '尚未同時取得兩份可比較稿件。請查看技術詳情及來源問題；目前不能保存美感比較。')

    def review_preference(self):
        job, index, _ = self.chosen_result(self.qualification_jobs, self.qualification_cases)
        if self.preference.currentData() is None: raise ValueError('請先比較兩份實際稿件。')
        if any(row['job_id'] == job['id'] and row['index'] == index for row in records(self.store, 'DESIGN_PREFERENCE_REVIEW')):
            raise ValueError('這份稿件已有保存的比較結果。不可重複建立衝突證據；請改以新的獨立驗證工作重審。')
        result = self.evaluation.review_preference(job['id'], index, self.preference.currentData(), self.reviewer(), self.evidence(self.preference_basis), scope='REVIEWED_STYLE')
        self.say('比較結果已保存；不會修改本次已凍結的模型。'); return result

    def review_corpus(self):
        identity = self.qualification_jobs.currentData()
        if not identity: raise ValueError('請先完成封存集合驗證，再選擇要審查的工作。')
        result = self.qualification.review_corpus(identity, self.reviewer(), self.evidence(self.corpus_basis),
            real_authorized=self.real_authorized.isChecked(), lineage_independence_reviewed=self.lineage_reviewed.isChecked(), approved=True)
        self.load_qualification_cases(); self.say('來源審查已保存；仍須通過逐稿比較與全部正式檢查。'); return result

    def approve_qualification(self):
        if not self.qual_approved.isChecked(): raise ValueError('請先審查結果與門檻，再保存資格。')
        identity = self.qualification_jobs.currentData(); review = self.corpus_reviews.currentData()
        if not identity or not review: raise ValueError('目前缺少已完成的封存驗證或來源審查。')
        policy = dict(version='guided-local-qualification-1', basis=self.evidence(self.qual_basis), minimum_independent_groups=self.qual_minimum.value(),
            minimum_feasible_rate=self.qual_feasible.value(), minimum_preference_win_or_tie_rate=self.qual_preference.value())
        plan = self.qualification.plan(identity, review, policy)
        result = self.qualification.approve(plan, self.reviewer(), approved=True)
        self.pending_certificate = result['id']; self.say('已保存數位排版範圍的資格，尚未啟用。既有稿件保持原版本。', dict(certificate_id=result['id'], scope=plan['scope']))
        return result

    def activate_qualified(self):
        identity = self.qualification_jobs.currentData()
        if not identity: raise ValueError('請先選擇已有正式資格的驗證工作。')
        job = self.jobs.current(identity); model, _ = self.learning.checked_model(job['plan']['model_id'])
        certificate = validate_certificate(self.library, model)
        active = self.store.get('DESIGN_ACTIVE', 'local-layout')
        policy = dict(certificate['plan']['layout_policy'], production=True, basis='本機核對人員明確啟用已驗證規則')
        result = self.learning.activate(model['id'], active['revision'] if active else 0, self.reviewer(), policy, True)
        self.say('已啟用通過資格的規則。新稿可使用；舊定稿與已確認輸出保持原版本。'); return result

    def refresh(self):
        selected = self.models.currentData(); self.models.blockSignals(True); self.models.clear()
        models = list(records(self.store, 'DESIGN_MODEL'))
        for index, row in enumerate(models):
            self.models.addItem('規則版本 ' + str(index + 1) + ' · ' + row['id'][:8], row['id'])
        preferred = self.case_model or selected
        index = self.models.findData(preferred)
        if index >= 0: self.models.setCurrentIndex(index)
        self.models.blockSignals(False); self.load_samples()
        self.local_state.setText('本機目前有 ' + str(len(models)) + ' 個規則版本。核對原稿、字型及規則後，才能知道哪些用途可被支持。')
        selected_capacity = self.capacity_jobs.currentData(); selected_qual = self.qualification_jobs.currentData()
        for choices in [self.capacity_jobs, self.qualification_jobs, self.resume_jobs]: choices.blockSignals(True); choices.clear()
        for index, job in enumerate(self.completed_jobs()):
            title = '驗證工作 ' + str(index + 1) + ' · ' + job['id'][:8]
            if job['phase'] == 'COMPLETE':
                roles = {row['role'] for row in self.jobs.results(job['id'])}
                if 'VALIDATION' in roles: self.capacity_jobs.addItem(title, job['id'])
                if 'HOLDOUT' in roles: self.qualification_jobs.addItem(title + (' · 自製測試，不能取得正式資格' if job['plan']['origin'] != 'REAL_AUTHORIZED_CORPUS' else ' · 真實資料待審查'), job['id'])
            elif self.jobs.state(job['id']) in ('QUEUED', 'PAUSED', 'FAILED', 'WAITING_RESOURCE', 'INTERRUPTED'):
                self.resume_jobs.addItem(title + ' · ' + job['phase'], job['id'])
        for choices, value in [(self.capacity_jobs, selected_capacity), (self.qualification_jobs, selected_qual)]:
            index = choices.findData(value)
            if index >= 0: choices.setCurrentIndex(index)
        for choices in [self.capacity_jobs, self.qualification_jobs, self.resume_jobs]: choices.blockSignals(False)
        self.load_capacity_cases(); self.load_qualification_cases()

    def remember(self):
        current = self.store.get('GUIDED_WORKSPACE', 'desktop')
        with self.store.transaction():
            self.store._write('GUIDED_WORKSPACE', 'desktop', dict(cases=deepcopy(self.cases), case_model=self.case_model, actor=self.actor.text(), page=self.tabs.currentIndex()),
                current['revision'] if current else 0, 'guided_local_workspace_saved_not_evidence')

    def restore(self):
        current = self.store.get('GUIDED_WORKSPACE', 'desktop')
        if not current: return
        self.cases = deepcopy(current.get('cases', [])); self.case_model = current.get('case_model')
        self.actor.setText(current.get('actor', '')); self.tabs.setCurrentIndex(min(max(current.get('page', 0), 0), 3)); self.render_cases()

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.close_after_worker = True; self.worker.cancel.set(); self.say('將保存目前完整案例後關閉；可稍後接續。'); event.ignore(); return
        if self.children_dialogs:
            self.say('請先關閉已開啟的來源或規則工具，再關閉引導。'); event.ignore(); return
        self.remember(); super().closeEvent(event)
