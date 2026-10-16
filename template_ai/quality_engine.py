"""Immutable local Python engine versions, without project data or credentials."""
import importlib
import importlib.abc
import importlib.machinery
import importlib.util
import os
from pathlib import Path
import shutil
import sys
import tempfile
from .background import file_digest
from .training_store import digest


def source_manifest(package):
    files={};total=0
    for path in sorted(Path(package).glob('*.py')):
        if path.is_symlink() or not path.is_file():raise ValueError('解析器程式不得使用符號連結')
        size=path.stat().st_size;total+=size
        if len(files)>=400 or size>1048576 or total>8*1048576:raise ValueError('解析器快照超過400檔／單檔1MiB／總8MiB，不截斷')
        files[path.name]=dict(sha256=file_digest(path),bytes=size)
    if '__init__.py' not in files or 'source_analysis.py' not in files:raise ValueError('解析器來源套件不完整')
    return files


def freeze(assets,package):
    files=source_manifest(package);identity=digest(files)
    target=Path(assets)/'quality-engines'/identity
    target.parent.mkdir(parents=True,exist_ok=True)
    if not target.exists():
        temporary=Path(tempfile.mkdtemp(prefix='quality-engine-',dir=target.parent))
        try:
            for name in files:shutil.copyfile(Path(package)/name,temporary/name)
            if source_manifest(temporary)!=files or source_manifest(package)!=files:raise ValueError('快照期間解析器程式已變更')
            try:os.rename(temporary,target)
            except OSError:
                if not target.is_dir():raise
        finally:
            if temporary.exists():shutil.rmtree(temporary)
    record=dict(code_digest=identity,files={name:dict(value,path=str(target/name)) for name,value in files.items()},
                input_scope='PYTHON_APPLICATION_SOURCE_ONLY_NO_DATABASE_GOLD_CREDENTIALS')
    verify(record)
    return record


def verify(record):
    files=record['files'];expected={name:{key:value[key] for key in ('sha256','bytes')} for name,value in files.items()}
    if digest(expected)!=record['code_digest']:raise ValueError('解析器快照清單指紋不符')
    root=Path(files['__init__.py']['path']).parent
    if root.is_symlink() or source_manifest(root)!=expected:raise ValueError('解析器快照檔案失聯／新增／內容已變更')
    if any(Path(value['path'])!=root/name for name,value in files.items()):raise ValueError('解析器快照路徑不一致')
    return root


class ReadOnlyLoader(importlib.machinery.SourceFileLoader):
    def set_data(self,path,data,**kwargs):
        pass  # Executable snapshots remain immutable; no __pycache__ assets.


class SnapshotFinder(importlib.abc.MetaPathFinder):
    def __init__(self,prefix,root):self.prefix=prefix;self.root=root
    def find_spec(self,fullname,path=None,target=None):
        if not fullname.startswith(self.prefix+'.'):return None
        suffix=fullname[len(self.prefix)+1:]
        if '.' in suffix:return None
        file=self.root/(suffix+'.py')
        if not file.is_file():return None
        return importlib.util.spec_from_file_location(fullname,file,loader=ReadOnlyLoader(fullname,str(file)))


def load(record):
    root=verify(record);prefix='_template_ai_quality_'+digest([str(root),record['code_digest']])[:24]
    if prefix not in sys.modules:
        loader=ReadOnlyLoader(prefix,str(root/'__init__.py'))
        spec=importlib.util.spec_from_file_location(prefix,root/'__init__.py',loader=loader,submodule_search_locations=[str(root)])
        module=importlib.util.module_from_spec(spec);sys.modules[prefix]=module
        sys.meta_path.insert(0,SnapshotFinder(prefix,root))
        try:loader.exec_module(module)
        except BaseException:
            sys.modules.pop(prefix,None);raise
    return importlib.import_module(prefix+'.source_analysis')


def execute(record,source,assets,model_record,context,mapping_catalog=None):
    module=load(record);model=None
    prefix=module.__package__
    try:
        if model_record:
            fields=importlib.import_module(prefix+'.semantic_fields')
            model=fields.CharacterModel([e for e in model_record['plan']['examples'] if e['role']=='TRAIN'])
            if digest({key:dict(value) for key,value in model.counts.items()})!=model_record['weights_digest']:raise ValueError('凍結版本實際模型權重不一致')
        result=module.analyse_source(source,assets,model,context)
        mapping=importlib.import_module(prefix+'.quality_mapping')
        for work in result:work['mapping_prediction']=mapping.predict(source,work,mapping_catalog)
        verify(record)
        return result
    finally:
        # Units return only plain dictionaries. Do not retain a module graph per
        # library/version during a long, low-memory desktop session.
        for name in list(sys.modules):
            if name==prefix or name.startswith(prefix+'.'):sys.modules.pop(name,None)
        sys.meta_path[:]=[finder for finder in sys.meta_path if not isinstance(finder,SnapshotFinder) or finder.prefix!=prefix]
