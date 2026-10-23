"""Exact explicit files/root snapshots using the existing bounded source walker."""
import os
from pathlib import Path
from .source_discovery import discover_sources
from .source_links import fingerprint
from .training_store import digest


def norm(value):return os.path.normcase(os.path.normpath(str(value)))


def directory_snapshot(root, recursive=True, extensions=None):
    from .source_scan import options
    formats,_=options(extensions,[]);paths=[]
    report=discover_sources([],root,max_entries=10000,recursive=recursive,visit=lambda path,stat:paths.append(str(path)) if path.suffix.lower() in formats else None)
    directories=[]
    for path in report.get('directories',[]):
        try:directories.append(dict(path=path,stat=list(fingerprint(Path(path).stat()))))
        except OSError as error:report['errors'].append(dict(path=path,reason=str(error)))
    directories.sort(key=lambda value:value['path']);report['errors'].sort(key=lambda value:(value.get('path',''),value.get('reason','')))
    result=dict(root=str(Path(root).resolve()),recursive=bool(recursive),extensions=formats,paths=sorted(paths),directories=directories,scan_status=report['status'],scan_errors=report['errors'],scan_complete=report['status']=='COMPLETE' and not report['errors'],scanned_entries=report['entries'],unscanned_entries=None if report['status']!='COMPLETE' or report['errors'] else 0,algorithm='EXISTING_DISCOVER_SOURCES_VISITOR_V1',excluded_extensions_explicit=True)
    return result


def check_directory_stats(snapshot,require_complete=True):
    if not snapshot or require_complete and not snapshot['scan_complete']:raise ValueError('目錄範圍掃描不完整／有無法讀取項，未知不得當100%')
    for directory in snapshot['directories']:
        if list(fingerprint(Path(directory['path']).stat()))!=directory['stat']:raise ValueError('批次目錄成員已變更，需重新掃描及重開')


class CoverageScopeMixin:
    def plan_source_files(self,paths,selected_source_ids=None,*,root_snapshot=None):
        if not isinstance(paths,list) or not 1<=len(paths)<=10000 or any(not isinstance(p,str) or not p.strip() for p in paths):raise ValueError('明列1～10000個來源檔案位置')
        paths=sorted({norm(Path(p).absolute()) for p in paths})
        if selected_source_ids is not None and (not isinstance(selected_source_ids,list) or len(set(selected_source_ids))!=len(selected_source_ids) or len(selected_source_ids)>10000):raise ValueError('來源版本選擇需不重複且有界ID清單')
        selected=set(selected_source_ids) if selected_source_ids is not None else None
        self.db.create_function('coverage_normpath',1,norm,deterministic=True)
        members=[];source_ids=[];groups={}
        for path in paths:
            ids=[r[0] for r in self.db.execute('SELECT s.id FROM sources s LEFT JOIN source_links l ON l.source_id=s.id WHERE coverage_normpath(COALESCE(l.current_path,s.original_path))=? ORDER BY s.id LIMIT 10001',(path,))]
            if len(ids)>10000:raise ValueError('單檔來源頁版本超過支援範圍，未靜默截斷')
            if selected is not None:ids=[identity for identity in ids if identity in selected]
            pins=[self.source_pin(identity) for identity in ids];source_ids+=ids
            if len(source_ids)>10000:raise ValueError('批次來源頁超過10000，請明確分組')
            if not pins:
                try:raw_state=dict(stat=list(fingerprint(Path(path).stat())),content_hash_verified=False)
                except OSError as error:raw_state=dict(stat=None,error=str(error),content_hash_verified=False)
                groups['UNREGISTERED_PATH:'+path]=dict(logical_file_key='UNREGISTERED_PATH:'+path,original_path=path,declared_physical_paths=[path],unregistered_file_snapshot=raw_state,source_pins=[])
            for pin in pins:
                key='REGISTERED_ORIGINAL:'+norm(pin['original_path']);member=groups.setdefault(key,dict(logical_file_key=key,original_path=pin['original_path'],declared_physical_paths=[],source_pins=[]))
                if path not in member['declared_physical_paths']:member['declared_physical_paths'].append(path)
                member['source_pins'].append(pin)
        for key,member in sorted(groups.items()):
            pins=member['source_pins'];member.update(expected_hashes=sorted({pin['source_hash'] for pin in pins}),source_page_count=len(pins),recorded_work_count=sum(len(pin['works']) for pin in pins),registration_state='REGISTERED_PAGES' if pins else 'UNREGISTERED_OR_UNPARSED_REMAINS_IN_FILE_DENOMINATOR')
            member['member_scope_digest']=digest(member);members.append(member)
        if selected is not None and selected!=set(source_ids):raise ValueError('選擇的來源頁不屬明列檔案位置，未跨來源混配')
        result=dict(schema_version=1,scope_kind='EXACT_ROOT_FILTERED_SNAPSHOT' if root_snapshot else 'EXACT_DECLARED_SOURCE_FILES',declared_paths=paths,physical_path_count=len(paths),selected_source_ids=sorted(selected) if selected is not None else None,root_snapshot=root_snapshot,source_ids=sorted(source_ids),source_page_count=len(source_ids),file_count=len(members),members=members,whole_directory_claim=False,all_file_work_coverage_verified=False)
        import json
        if len(json.dumps(result,ensure_ascii=False).encode())>32*1024*1024 or any(len(json.dumps(member,ensure_ascii=False).encode())>900000 for member in members):raise ValueError('範圍metadata過大，請明確分組；未靜默截斷')
        result['scope_digest']=digest(result);return result

    def plan_directory(self,root,recursive=True,extensions=None,selected_source_ids=None):
        # Two bounded enumerations catch changes during traversal; originals are not opened.
        first=directory_snapshot(root,recursive,extensions);second=directory_snapshot(root,recursive,extensions)
        if first!=second:raise ValueError('目錄在掃描期間變更，未建立不一致範圍')
        return self.plan_source_files(second['paths'],selected_source_ids,root_snapshot=second)

    def rebuild_scope_plan(self,plan):
        if plan['scope_kind']=='EXACT_REGISTERED_SOURCE_PAGES':return self.plan_registered_sources(plan['source_ids'])
        snapshot=plan.get('root_snapshot')
        if snapshot:check_directory_stats(snapshot,require_complete=False)
        return self.plan_source_files(plan['declared_paths'],plan.get('selected_source_ids'),root_snapshot=snapshot)

    def check_root_scope(self,batch,*,enumerate_files=True):
        snapshot=batch.get('scope_details',{}).get('root_snapshot')
        if not snapshot:return
        check_directory_stats(snapshot)
        if enumerate_files:
            current=directory_snapshot(snapshot['root'],snapshot['recursive'],snapshot['extensions'])
            if current!=snapshot:raise ValueError('指定根目錄新增／刪除／改名或無法掃描，舊批次不可結案')
