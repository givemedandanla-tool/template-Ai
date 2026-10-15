"""Explicit, source-bound user publication exceptions; never waive code or test failures."""
from pathlib import Path
from dev_common import read_json, safe_path


def waived_attachments(root, run_path, run):
    root = Path(root)
    folder = str(Path(run_path).parent).replace('\\', '/')
    candidates = []
    policies = []
    legacy = root / 'docs/dev/EVIDENCE_PUBLICATION_EXCEPTIONS.json'
    if legacy.exists():
        policy = read_json(legacy)
        if policy.get('policy') == 'USER_AUTHORIZED_SKIP_EVIDENCE_ATTACHMENT_UPLOAD':
            candidates += [(r['path'], r) for r in policy['excluded_original_files']
                           if r['path'].startswith(folder + '/')]
            if candidates:
                policies.append(str(legacy.relative_to(root)))
    for policy_path, policy_id in (('docs/dev/TEN_PACKAGES_PUBLICATION.json', 'USER_AUTHORIZED_METADATA_FIRST_TEN_PACKAGES'), ('docs/dev/SEVENTY_PARENTS_PUBLICATION.json', 'USER_AUTHORIZED_METADATA_FIRST_SEVENTY'), ('docs/dev/DIAGNOSTIC_REPORTS_PUBLICATION.json','USER_AUTHORIZED_METADATA_FIRST_DIAGNOSTICS'), ('docs/dev/FULL70_PUBLICATION.json','USER_AUTHORIZED_METADATA_FIRST_FULL70')):
        path = root / policy_path
        if path.exists():
            policy = read_json(path)
            if policy.get('policy') != policy_id:
                raise ValueError('未知的證據保存例外policy')
            if '如果這只是證明文件就略過' not in policy.get('user_instruction', ''):
                raise ValueError('證據保存例外缺少明確使用者決策')
            safe_path(root, policy['contract']).read_text(encoding='utf-8')
            item = policy.get('runs', {}).get(run['id'])
            if item:
                if item['source_commit'] != run['source_commit']:
                    raise ValueError('上傳例外與測試來源版本不符')
                candidates += [(folder + '/' + name, r) for name, r in item['attachments'].items()]
                policies.append(str(path.relative_to(root)))
    result = {}
    for path, row in candidates:
        safe_path(root, path)
        name = path[len(folder) + 1:]
        if '/' in name or Path(name).suffix not in ('.png', '.jpg', '.pdf'):
            raise ValueError('只可略過具體GUI／數位二進位證明，不能略過code/tests/metadata')
        expected = run['attachments'].get(name)
        if not expected or (row['bytes'], row['sha256']) != (expected['bytes'], expected['sha256']):
            raise ValueError('上傳例外的附件身份／hash與原證據不符')
        result[path] = row
    return result, policies
