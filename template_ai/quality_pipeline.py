"""Receipts for the actual installed source-only analysis pipeline, never typed labels."""
import copy
import os
import platform
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
import networkx
from PySide6 import __version__ as qt_version
from .training_store import TrainingStore,digest,text
from .source_analysis import ANALYSER_VERSION,analyse_source
from .importer import inkscape_path
from .background import file_digest
from .source_links import fingerprint
from .model import new_id

PIPELINE='QUALITY_PIPELINE'


def font_environment():
    executable=shutil.which('fc-list')
    if not executable:return dict(complete=False,reason='無可核對的字型檔環境清單，不宣稱相同字型條件')
    try:
        with tempfile.TemporaryFile() as output:
            result=subprocess.run([executable,'--format','%{file}\n'],stdout=output,stderr=subprocess.DEVNULL,timeout=10)
            output.seek(0);raw=output.read(2*1024*1024+1)
        if result.returncode or len(raw)>2*1024*1024:raise ValueError('字型清單未完成或超過有界metadata')
        paths=sorted(set(raw.decode('utf-8').splitlines()))
        if len(paths)>10000:raise ValueError('字型環境超過10000檔，未截斷當完整')
        values=[dict(path=str(Path(p).resolve()),stat=list(fingerprint(Path(p).stat()))) for p in paths]
        return dict(complete=bool(values),file_count=len(values),stat_manifest_digest=digest(values),basis='ACTUAL_FONTCONFIG_FILE_LIST_AND_STAT_NOT_FONT_CONTENT_UPLOAD')
    except (OSError,ValueError,subprocess.TimeoutExpired) as error:return dict(complete=False,reason=str(error))


class QualityPipelines:
    def __init__(self,library):self.library=library;self.store=TrainingStore.bind(library)

    def semantic(self,model_id):
        if model_id is None:return None,None
        from .semantic_learning import SemanticLearning
        service=object.__new__(SemanticLearning);service.library=self.library;service.store=self.store
        return service.checked_model(model_id)

    def current_manifest(self,model_id=None):
        row,model=self.semantic(model_id);executable=inkscape_path()
        if not executable:raise ValueError('實際Inkscape解析器不可用，不接受自行輸入版本冒充執行證據')
        version=subprocess.run([executable,'--version'],capture_output=True,text=True,timeout=10)
        if version.returncode:raise ValueError('實際解析器版本讀回失敗')
        base=Path(__file__).parent;names=('quality_pipeline.py','source_analysis.py','source_text_evidence.py','semantic_fields.py','importer.py','background.py')
        active,invalid=self.store.active_noise_rules()
        if invalid:raise ValueError('目前正式規則支持／反例證據失效；不保存可疑版本為已核實pipeline')
        return dict(schema_version=1,analyser_version=ANALYSER_VERSION,source_modules={name:file_digest(base/name) for name in names},semantic_model_id=model_id,semantic_model_revision=row['revision'] if row else None,semantic_model_digest=digest(row) if row else None,semantic_weights_digest=row['weights_digest'] if row else None,model_training_scopes=[dict(source_hash=s['pins']['source_hash'],role=s['role'],work_id=s['work_id']) for s in row['plan']['scopes']] if row else [],renderer=dict(executable=str(Path(executable).resolve()),sha256=file_digest(executable),version=version.stdout.strip()[:1000]),rules=[dict(id=r['id'],revision=r['revision'],digest=digest(r)) for r in active],rules_execution='NOT_APPLIED_WITHOUT_GOLD_FREE_HUMAN_CONTEXT',ocr_execution='NOT_EXECUTED_BY_VECTOR_SOURCE_PIPELINE',native_illustrator_mapping='UNVERIFIED_NOT_CERTIFIED',environment=dict(python=platform.python_version(),system=platform.platform(),qt=qt_version,networkx=networkx.__version__,fonts=font_environment()),prediction_inputs='ORIGINAL_SOURCE_AND_TRAINED_WEIGHTS_ONLY_NO_HOLDOUT_GOLD_LABELS')

    def freeze(self,name,model_id,actor,approved=False):
        if approved is not True:raise ValueError('需明確核對實際可執行pipeline範圍；不自動放行模型')
        text(name,'pipeline名稱',120);text(actor,'版本保存者',120)
        # Executable/model verification happens outside the SQLite write lock.
        manifest=self.current_manifest(model_id)
        with self.store.transaction():
            if model_id and digest(self.store.get('SEMANTIC_MODEL',model_id))!=manifest['semantic_model_digest']:raise ValueError('模型版本已變更')
            return self.store._write(PIPELINE,new_id(),dict(name=name,manifest=manifest,manifest_digest=digest(manifest),actor=actor,created=time.time(),state='ACTUAL_SOURCE_ONLY_PIPELINE_FROZEN_NOT_QUALITY_APPROVED',quality_pass=False,immutable=True),0,'quality_actual_pipeline_frozen_not_quality_release')

    def validity(self,pipeline_id):
        record=self.store.get(PIPELINE,pipeline_id)
        if not record:return dict(valid=False,errors=['實際pipeline版本不存在'],pipeline=None)
        errors=[]
        try:
            current=self.current_manifest(record['manifest']['semantic_model_id'])
            if digest(current)!=record['manifest_digest'] or digest(record['manifest'])!=record['manifest_digest']:errors.append('實際模型／程式／解析器／規則／字型或環境版本已變更')
        except (OSError,ValueError,subprocess.TimeoutExpired) as error:errors.append(str(error))
        return dict(valid=not errors,errors=errors,pipeline=record)

    def predict_source(self,pipeline_id,source_id):
        checked=self.validity(pipeline_id)
        if not checked['valid']:raise ValueError('；'.join(checked['errors']))
        pipeline=checked['pipeline'];row,model=self.semantic(pipeline['manifest']['semantic_model_id']);source=self.library.source(source_id)
        from .batch_import import healthy_source
        if not healthy_source(source):raise ValueError('來源／cache不完整，仍須留在評估檔案分母，不當空預測成功')
        from .source_links import verify_source,check_verified
        from .trusted_samples import cache_stamps
        proof=verify_source(source['current_path'],source['hash']);stamps=cache_stamps(source);source_digest=digest(source)
        context=dict(state='FROZEN_EVALUATION_MODEL',model_id=row['id'],model_revision=row['revision'],weights_digest=row['weights_digest']) if row else None
        predictions=analyse_source(source,self.library.assets,model,context)
        check_verified(proof,source['hash'])
        if digest(self.library.source(source_id))!=source_digest or cache_stamps(source)!=stamps or not self.validity(pipeline_id)['valid']:raise ValueError('推論期間來源／cache／實際pipeline依賴改變，未採用過期結果')
        return dict(pipeline_id=pipeline_id,pipeline_manifest_digest=pipeline['manifest_digest'],source_id=source_id,source_hash=source['hash'],source_page=source['page'],source_dependency_digest=source_digest,source_proof=dict(path=proof.path,hash=proof.hash,stat=list(proof.stat)),source_cache_stamps=stamps,prediction_origin='ACTUAL_EXECUTED_SOURCE_ANALYSIS_NO_GOLD_ARGUMENT',predictions=predictions,capabilities=dict(ocr_executed=False,native_illustrator_mapping_verified=False,noise_rules_applied_using_holdout_gold=False),quality_pass=None)
