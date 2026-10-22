"""Receipts for the actual installed source-only analysis pipeline, never typed labels."""
import copy
import os
import platform
import shutil
import subprocess
import sys
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

    def current_manifest(self,model_id=None,mapping_config=None,rule_versions=None,ocr_record=None):
        row,model=self.semantic(model_id);executable=inkscape_path()
        if not executable:raise ValueError('實際Inkscape解析器不可用，不接受自行輸入版本冒充執行證據')
        version=subprocess.run([executable,'--version'],capture_output=True,text=True,timeout=10)
        if version.returncode:raise ValueError('實際解析器版本讀回失敗')
        base=Path(__file__).parent;names=('quality_pipeline.py','quality_ocr.py','quality_rules.py','noise_review.py','noise.py','quality_mapping.py','customer_candidates.py','quality_logo.py','source_analysis.py','source_text_evidence.py','semantic_fields.py','importer.py','background.py','inkscape_runtime.py')
        from .quality_rules import snapshots
        active=snapshots(self.store,rule_versions)
        from .quality_mapping import catalog
        mapping_catalog=catalog(self.library,mapping_config)
        effective_model=digest(dict(counts={key:dict(value) for key,value in model.counts.items()},documents=dict(model.documents),vocabulary=sorted(model.vocabulary))) if model else None
        from .quality_ocr import verify
        verify(ocr_record)
        renderer_manifest=dict(executable=str(Path(executable).resolve()),sha256=file_digest(executable),version=version.stdout.strip()[:1000])
        if getattr(sys,'frozen',False):
            from .inkscape_runtime import runtime_identity
            renderer_manifest['bundled_runtime']=runtime_identity(executable)
        return dict(schema_version=1,effective_semantic_digest=effective_model,ocr=copy.deepcopy(ocr_record),mapping_catalog=mapping_catalog,mapping_configuration=mapping_config,analyser_version=ANALYSER_VERSION,source_modules={name:file_digest(base/name) for name in names},semantic_model_id=model_id,semantic_model_revision=row['revision'] if row else None,semantic_model_digest=digest(row) if row else None,semantic_weights_digest=row['weights_digest'] if row else None,model_training_scopes=[dict(source_hash=s['pins']['source_hash'],role=s['role'],work_id=s['work_id']) for s in row['plan']['scopes']] if row else [],renderer=renderer_manifest,rules=[dict(id=r['id'],revision=r['revision'],digest=digest(r)) for r in active],rule_selection=[dict(id=r['id'],revision=r['revision']) for r in active],rule_records=copy.deepcopy(active),rules_execution='ACTUAL_FROZEN_SCOPE_MATCHES_AND_SOURCE_PROTECTION_NO_GOLD',ocr_execution='ACTUAL_LOCAL_TESSERACT_SOURCE_IMAGE_ONLY' if ocr_record else 'NOT_EXECUTED_BY_VECTOR_SOURCE_PIPELINE',native_illustrator_mapping='UNVERIFIED_NOT_CERTIFIED',environment=dict(python=platform.python_version(),system=platform.platform(),qt=qt_version,networkx=networkx.__version__,fonts=font_environment()),prediction_inputs='ORIGINAL_SOURCE_AND_TRAINED_WEIGHTS_ONLY_NO_HOLDOUT_GOLD_LABELS')

    def freeze(self,name,model_id,actor,approved=False,*,mapping_config=None,rule_versions=None,ocr_config=None):
        if approved is not True:raise ValueError('需明確核對實際可執行pipeline範圍；不自動放行模型')
        text(name,'pipeline名稱',120);text(actor,'版本保存者',120)
        # Executable/model verification happens outside the SQLite write lock.
        from .quality_ocr import freeze as freeze_ocr
        ocr_record=freeze_ocr(self.library.assets,ocr_config)
        manifest=self.current_manifest(model_id,mapping_config,rule_versions,ocr_record)
        from .quality_engine import freeze
        manifest['engine']=freeze(self.library.assets,Path(__file__).parent)
        with self.store.transaction():
            if model_id and digest(self.store.get('SEMANTIC_MODEL',model_id))!=manifest['semantic_model_digest']:raise ValueError('模型版本已變更')
            return self.store._write(PIPELINE,new_id(),dict(name=name,manifest=manifest,manifest_digest=digest(manifest),actor=actor,created=time.time(),state='ACTUAL_SOURCE_ONLY_PIPELINE_FROZEN_NOT_QUALITY_APPROVED',quality_pass=False,immutable=True),0,'quality_actual_pipeline_frozen_not_quality_release')

    def validity(self,pipeline_id):
        record=self.store.get(PIPELINE,pipeline_id)
        if not record:return dict(valid=False,errors=['實際pipeline版本不存在'],pipeline=None)
        errors=[]
        try:
            current=self.current_manifest(record['manifest']['semantic_model_id'],record['manifest'].get('mapping_configuration'),record['manifest'].get('rule_selection'),record['manifest'].get('ocr'))
            from .quality_engine import verify
            verify(record['manifest']['engine'])
            for name,sha in record['manifest']['source_modules'].items():
                if record['manifest']['engine']['files'][name]['sha256']!=sha:raise ValueError('已記錄解析器版本與實際執行快照不一致')
            current.update(source_modules=record['manifest']['source_modules'],analyser_version=record['manifest']['analyser_version'],engine=record['manifest']['engine'])
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
        from .quality_engine import execute
        predictions=execute(pipeline['manifest']['engine'],source,self.library.assets,row,context,pipeline['manifest']['mapping_catalog'],pipeline['manifest']['rule_records'],pipeline['manifest'].get('ocr'))
        check_verified(proof,source['hash'])
        if digest(self.library.source(source_id))!=source_digest or cache_stamps(source)!=stamps or not self.validity(pipeline_id)['valid']:raise ValueError('推論期間來源／cache／實際pipeline依賴改變，未採用過期結果')
        return dict(pipeline_id=pipeline_id,pipeline_manifest_digest=pipeline['manifest_digest'],source_id=source_id,source_hash=source['hash'],source_page=source['page'],source_dependency_digest=source_digest,source_proof=dict(path=proof.path,hash=proof.hash,stat=list(proof.stat)),source_cache_stamps=stamps,prediction_origin='ACTUAL_EXECUTED_SOURCE_ANALYSIS_NO_GOLD_ARGUMENT',predictions=predictions,capabilities=dict(rule_processor_executed=True,rule_scope_checks_without_gold=True,ocr_executed=any(w.get('evidence',{}).get('ocr',{}).get('executed',False) for w in predictions),native_illustrator_mapping_verified=False,noise_rules_applied_using_holdout_gold=False),quality_pass=None)
