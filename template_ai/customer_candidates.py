"""由來源／作品事實提出客戶候選；身分核對與入庫是獨立動作。

沿用 SQLite 與 TrainingStore 的版本化事實。檔名規則只產生候選編號，
SHA-256 只重用內容；兩者都不構成客戶身分證明。
"""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from .customer_entities import clone_for_master, insert_graph
from .customers import digest
from .input_graph import InputGraph
from .model import new_id, company_ports
from .source_links import verify_source
from .training_store import TrainingStore


class CustomerCandidates:
    def __init__(self, store):
        self.store, self.library, self.db = store, store.library, store.db
        self.training = TrainingStore(self.library)
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS customer_import_candidates(
            id TEXT PRIMARY KEY, revision INTEGER NOT NULL, state TEXT NOT NULL, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS customer_source_associations(
            id TEXT PRIMARY KEY, customer_id TEXT NOT NULL REFERENCES customers(id),
            source_id TEXT NOT NULL REFERENCES sources(id), artwork_id TEXT NOT NULL REFERENCES artworks(id),
            template_id TEXT NOT NULL REFERENCES templates(id), source_hash TEXT NOT NULL,
            artwork_revision INTEGER NOT NULL, template_hash TEXT NOT NULL, person_scope TEXT NOT NULL,
            candidate_id TEXT NOT NULL UNIQUE REFERENCES customer_import_candidates(id));
        ''')
        self.db.commit()

    def get(self, identity):
        row = self.db.execute('SELECT revision,state,payload FROM customer_import_candidates WHERE id=?',
                              (identity,)).fetchone()
        if row is None:
            raise ValueError('客戶候選不存在')
        return dict(id=identity, revision=row[0], state=row[1], **json.loads(row[2]))

    def list(self, offset=0, limit=100):
        if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError('候選查詢需有效分頁，每頁最多100筆')
        return [self.get(r[0]) for r in self.db.execute(
            'SELECT id FROM customer_import_candidates ORDER BY rowid LIMIT ? OFFSET ?', (limit, offset))]

    def _save(self, identity, payload, state, revision):
        row = self.db.execute('SELECT revision FROM customer_import_candidates WHERE id=?', (identity,)).fetchone()
        if (row[0] if row else 0) != revision:
            raise ValueError('候選版本已更新，請重新檢視')
        raw = json.dumps(payload, ensure_ascii=False, allow_nan=False)
        if len(raw.encode()) > 1_048_576:
            raise ValueError('單筆候選超過1MiB，請縮小作品範圍')
        self.db.execute('INSERT INTO customer_import_candidates VALUES(?,?,?,?) '
            'ON CONFLICT(id) DO UPDATE SET revision=excluded.revision,state=excluded.state,payload=excluded.payload',
            (identity, revision + 1, state, raw))
        return self.get(identity)

    def _source_graph(self, work, template):
        facts = self.training.facts(work['id'])
        confirmed = set((facts.get('confirmation') or {}).get('observation_ids', []))
        by_slot = {o['slot_id']: o for o in facts['observations']
                   if o['id'] in confirmed and o['classification'] in ('FIELD', 'LOGO')}
        people = [{'name': [], 'companies': company_ports(template.company_bindings.get(f'p{i+1}', []))}
                  for i in range(template.capacity)]
        owners = sorted({s.owner for s in template.slots if s.owner.startswith('c')},
                        key=lambda value: int(value[1:]))
        if owners and owners != [f'c{i+1}' for i in range(len(owners))]:
            raise ValueError('來源公司位置埠不連續，需要先校正作品歸屬')
        companies = [{'name': ''} for _ in owners]
        issues = []
        if self.training.facts_state(work['id']) != 'CONFIRMED':
            issues.append('作品文字／歸屬事實尚未完整人工確認')
        for slot in template.slots:
            observation = by_slot.get(slot.id)
            if slot.kind == 'logo':
                continue  # Logo 內文字永遠不拆成可變公司名稱。
            if observation is None:
                issues.append('未確認來源欄位：' + slot.id)
                continue
            target = companies[int(slot.owner[1:]) - 1] if slot.owner.startswith('c') else people[int(slot.owner[1:]) - 1]
            kind = 'name' if slot.kind == 'company' else slot.kind
            if slot.owner.startswith('c') and kind == 'name':
                target['name'] = observation['text']
            else:
                values = target.setdefault(kind, [])
                while len(values) <= slot.index:
                    values.append('')
                values[slot.index] = observation['text']
        graph = InputGraph.from_legacy(people, companies).data
        g = InputGraph(graph)
        if any(g.label(e['id']) == '未命名／待補' for e in graph['people'] + graph['companies']):
            issues.append('人物／公司名稱需依來源人工核對，不從 Logo OCR 猜定')
        return graph, facts, issues

    def propose(self, source_id, pattern=r'(?P<code>.+)'):
        """預設明示規則＝完整檔名去副檔名；正則需完整匹配與具名 code 群。"""
        if pattern not in (r'(?P<code>.+)', r'(?P<code>[0-9]+)',
                           r'(?P<code>[^_]+)_.+', r'(?P<code>[A-Za-z0-9-]+)'):
            raise ValueError('請選擇已支援的完整檔名規則；不執行任意正則表達式')
        rule = re.compile(pattern)
        if 'code' not in rule.groupindex:
            raise ValueError('規則需要具名 code 群，且匹配完整檔名')
        source = self.library.source(source_id)
        verify_source(source['current_path'], source['hash'])
        stem = Path(source['original_path']).stem
        match = rule.fullmatch(stem)
        code = match.group('code') if match else ''
        if len(code) > 64:
            code = ''
        templates = self.library.templates()
        rows = []
        for work in self.library.artworks(source_id):
            associated = [t for t in templates if t.source_work_id == work['id'] and
                          t.source_work_revision == work['revision']]
            for template in associated:
                self.library._template_provenance(template)
                graph, facts, issues = self._source_graph(work, template)
                if not code:
                    issues.append('檔名無明確客戶編號候選，需人工指定')
                collisions = [r[0] for r in self.db.execute('SELECT id FROM customers WHERE code=?', (code,))]
                if collisions:
                    issues.append('客戶編號已存在；僅可明確新增別號或選定既有客戶關聯，不覆寫')
                same_content = [r[0] for r in self.db.execute(
                    'SELECT id FROM sources WHERE hash=? AND id<>? ORDER BY id LIMIT 101',
                    (source['hash'], source_id))]
                if same_content:
                    issues.append('異名同內容來源：需獨立核對各來源客戶身分')
                pins = dict(source_id=source_id, source_hash=source['hash'],
                    source_link_revision=source['link_revision'], artwork_id=work['id'],
                    artwork_revision=work['revision'], artwork_digest=digest(work['payload']),
                    facts_revision=facts['revision'], facts_digest=digest(facts),
                    template_id=template.id, template_hash=digest(template.to_dict()))
                identity = digest([source_id, work['id'], template.id, pattern])
                old = self.db.execute('SELECT revision,state FROM customer_import_candidates WHERE id=?', (identity,)).fetchone()
                if old and old[1] == 'COMMITTED':
                    rows.append(self.get(identity))
                    continue
                payload = dict(code_candidate=code, filename=Path(source['original_path']).name,
                    naming_rule=pattern, graph=graph, pins=pins, size_mm=[template.width_mm, template.height_mm],
                    source_page=source.get('page', 1), same_content_sources=same_content,
                    issues=issues, existing_code_ids=collisions, review=None)
                with self.db:
                    rows.append(self._save(identity, payload, 'PENDING_REVIEW', old[0] if old else 0))
        return rows

    def _fresh(self, candidate):
        pins = candidate['pins']
        source = self.library.source(pins['source_id'])
        work = self.library.artwork(pins['artwork_id'])
        template = next((t for t in self.library.templates() if t.id == pins['template_id']), None)
        facts = self.training.facts(work['id'])
        if (source['hash'] != pins['source_hash'] or source['link_revision'] != pins['source_link_revision']
                or work['revision'] != pins['artwork_revision'] or digest(work['payload']) != pins['artwork_digest']
                or facts['revision'] != pins['facts_revision'] or digest(facts) != pins['facts_digest']
                or template is None or digest(template.to_dict()) != pins['template_hash']):
            raise ValueError('來源／作品／事實／確切版型已更新，候選須重新核對')
        verify_source(source['current_path'], pins['source_hash'])
        self.library._template_provenance(template)
        return template

    def review(self, identity, expected_revision, graph, code, decision, actor, note,
               target_snapshot=None, person_scope=None, approved=False):
        if not approved or decision not in ('NEW_SEPARATE', 'LINK_EXISTING', 'REJECT', 'DEFER'):
            raise ValueError('需明確核對候選、選擇新增／關聯／拒絕／暫緩')
        if not all(isinstance(x, str) and x.strip() and len(x) <= 512 for x in (actor, note)):
            raise ValueError('需核對者及不含不必要個資的衝突處置理由')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            candidate = self.get(identity)
            if candidate['revision'] != expected_revision or candidate['state'] == 'COMMITTED':
                raise ValueError('候選已更新或已入庫')
            if decision in ('REJECT', 'DEFER'):
                payload = {k: deepcopy(v) for k, v in candidate.items() if k not in ('id', 'revision', 'state')}
                payload['review'] = dict(decision=decision, actor=actor, note=note,
                    reviewed_source_pins=deepcopy(candidate['pins']),
                    created_utc=datetime.now(timezone.utc).isoformat())
                result = self._save(identity, payload, decision, expected_revision)
                self.library.event(identity, 'customer_source_candidate_' + decision.lower())
                self.db.commit()
                return result
            template = self._fresh(candidate)
            InputGraph.validate(graph)
            g = InputGraph(graph)
            if not graph['people'] or len(graph['people']) != template.capacity or any(
                    g.label(e['id']) == '未命名／待補' for e in graph['people'] + graph['companies']):
                raise ValueError('人物／公司名稱及版型容量仍待人工校正')
            if any(c['logo_id'] for c in graph['companies']):
                raise ValueError('客戶候選不核准 Logo；入庫後由尺寸資產流程選擇')
            if not isinstance(code, str) or not code.strip() or len(code) > 64:
                raise ValueError('客戶編號需明確文字，保留前導0')
            target_digest = None
            if decision == 'LINK_EXISTING':
                if target_snapshot is None or digest(self.store.get(target_snapshot['id'])) != digest(target_snapshot):
                    raise ValueError('既有客戶快照已更新或未明確選定')
                if target_snapshot['code'] != code:
                    raise ValueError('客戶編號與明確選定的身分不符')
                owners = {e['id'] for e in (target_snapshot.get('graph') or {}).get('people', [])}
                if not person_scope or len(set(person_scope)) != len(person_scope) or set(person_scope) - owners:
                    raise ValueError('關聯需明確選取此客戶的穩定人物範圍')
                target_digest = digest(target_snapshot)
            payload = {k: deepcopy(v) for k, v in candidate.items() if k not in ('id', 'revision', 'state')}
            payload['review'] = dict(code=code, decision=decision, actor=actor, note=note,
                graph=deepcopy(graph), reviewed_source_pins=deepcopy(candidate['pins']),
                target_customer_id=target_snapshot['id'] if target_snapshot else None,
                target_digest=target_digest, person_scope=list(person_scope or []),
                created_utc=datetime.now(timezone.utc).isoformat())
            result = self._save(identity, payload, 'REVIEWED' if decision in ('NEW_SEPARATE', 'LINK_EXISTING')
                                else decision, expected_revision)
            self.library.event(identity, 'customer_source_candidate_' + decision.lower())
            self.db.commit()
            return result
        except BaseException:
            self.db.rollback()
            raise

    def commit(self, selections, approved=False):
        if not approved or not selections or len(selections) > 100 or len({x['id'] for x in selections}) != len(selections):
            raise ValueError('需確認1至100筆確切且不重複的已審候選')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            rows = []
            existing_targets = {}
            for selection in selections:
                candidate = self.get(selection['id'])
                if candidate['revision'] != selection['revision'] or candidate['state'] != 'REVIEWED':
                    raise ValueError('候選未完成審核／過期／已入庫，整批未套用')
                self._fresh(candidate)
                review = candidate['review']
                if review['decision'] == 'LINK_EXISTING':
                    cid = review['target_customer_id']
                    current_digest = digest(self.store.get(cid))
                    if current_digest != review['target_digest']:
                        raise ValueError('既有客戶已更新；整批不覆寫、不建立錯誤關聯')
                    existing_targets[cid] = current_digest
                rows.append(candidate)
            output = []
            for candidate in rows:
                review = candidate['review']
                pins = candidate['pins']
                if review['decision'] == 'NEW_SEPARATE':
                    if self.db.execute('SELECT 1 FROM customers WHERE code=?', (review['code'],)).fetchone():
                        raise ValueError('同編號衝突；請逐筆核對，不自動合併，整批未入庫')
                    graph = clone_for_master(review['graph'])
                    cid = new_id()
                    self.db.execute('INSERT INTO customers VALUES(?,?,?,1)',
                        (cid, review['code'], InputGraph(graph).label(graph['people'][0]['id'])))
                    insert_graph(self.db, cid, graph, write_fields=True)
                    scope = [p['id'] for p in graph['people']]
                else:
                    cid = review['target_customer_id']
                    scope = review['person_scope']
                template = next(t for t in self.library.templates() if t.id == pins['template_id'])
                self.db.execute('INSERT OR IGNORE INTO customer_styles VALUES(?,?,?,?,?,?)',
                    (new_id(), cid, template.id, pins['template_hash'], template.width_mm, template.height_mm))
                self.db.execute('INSERT INTO customer_source_associations VALUES(?,?,?,?,?,?,?,?,?,?)',
                    (new_id(), cid, pins['source_id'], pins['artwork_id'], template.id,
                     pins['source_hash'], pins['artwork_revision'], pins['template_hash'],
                     json.dumps(scope), candidate['id']))
                payload = {k: deepcopy(v) for k, v in candidate.items() if k not in ('id', 'revision', 'state')}
                payload['committed_customer_id'] = cid
                self._save(candidate['id'], payload, 'COMMITTED', candidate['revision'])
                self.library.event(cid, 'customer_source_association_manually_confirmed')
                output.append(dict(candidate_id=candidate['id'], customer_id=cid, status='COMMITTED'))
            for cid in existing_targets:
                self.db.execute('UPDATE customers SET revision=revision+1 WHERE id=?', (cid,))
            self.db.commit()
            return output
        except BaseException:
            self.db.rollback()
            raise
