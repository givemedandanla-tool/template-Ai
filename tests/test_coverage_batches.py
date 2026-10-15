import copy
import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from template_ai.coverage_batches import CoverageBatches, BATCH, MEMBER
from template_ai.storage import Library
from template_ai.training_store import TrainingStore


class CoverageBatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.library = Library(self.root/'data')
        self.addCleanup(self.library.close); self.store = TrainingStore(self.library)
        self.service = CoverageBatches(self.library)

    def source(self, name='one.svg', page=1, content=b'<svg/>'):
        path = self.root/name; path.write_bytes(content)
        return self.library.add_source(path, dict(hash=hashlib.sha256(content).hexdigest(), page=page, page_count=2, files={}))

    def batch(self, sources):
        return self.service.create(self.service.plan_registered_sources([s['id'] for s in sources]), 'Reviewer', True)

    def work_member(self):
        source = self.source()
        payload = dict(source, page_count=1, width_mm=90, height_mm=54)
        with self.library.db: self.library.db.execute('UPDATE sources SET payload=? WHERE id=?', (json.dumps(payload), source['id']))
        work = self.library.create_artwork(source['id'], 'One real bounded work', dict(crop=dict(x=0,y=0,w=90,h=54),work_width=90,work_height=54,slots=[]))
        batch = self.batch([source]); member = self.service.members(batch['id'])['rows'][0]
        return source, work, batch, member

    def review_all(self, member, work):
        from template_ai.coverage_evidence import LAYERS
        segmentation = self.service.segmentation_plan(member['id'], [work['id']], 'Viewed full page and bounded actual work')
        self.service.confirm_segmentation(segmentation, 'Reviewer', True)
        for layer in LAYERS:
            plan = self.service.layer_plan(member['id'],work['id'],layer,'CONFIRMED','Individually inspected this source layer','Page1 source visual / exact selected work')
            self.service.confirm_layer(plan,'Reviewer',True)

    def test_file_page_and_equal_content_aliases_are_independent(self):
        a = self.source(); a2 = self.source(page=2); b = self.source('alias.svg')
        batch = self.batch([a, a2, b]); summary = self.service.boundary_summary(batch['id'])
        self.assertEqual((summary['declared_files'], summary['declared_source_pages']), (2, 3))
        self.assertIsNone(summary['source_coverage_rate']); self.assertIsNone(summary['actual_all_source_work_count'])
        self.assertFalse(summary['closure_allowed']); self.assertFalse(summary['whole_directory_complete'])
        self.assertEqual(self.service.members(batch['id'])['total'], 2)

    def test_600_files_paged_and_global_search_before_limit(self):
        sources = [self.source(f'file-{i:04}.svg') for i in range(600)]
        with patch.object(self.library, 'list_sources', side_effect=AssertionError('unbounded source enumeration')):
            batch = self.batch(sources)
            first = self.service.members(batch['id']); last = self.service.members(batch['id'], 550)
            found = self.service.members(batch['id'], query='FILE-0599')
        self.assertEqual((first['total'], len(first['rows']), len(last['rows'])), (600, 50, 50))
        self.assertEqual(found['total'], 1); self.assertTrue(found['rows'][0]['frozen']['original_path'].endswith('0599.svg'))
        self.assertFalse({r['id'] for r in first['rows']} & {r['id'] for r in last['rows']})

    def test_requires_approval_and_rejects_tampered_or_empty_preview(self):
        source = self.source(); plan = self.service.plan_registered_sources([source['id']])
        with self.assertRaises(ValueError): self.service.create(plan, 'Reviewer')
        plan['file_count'] = 0
        with self.assertRaises(ValueError): self.service.create(plan, 'Reviewer', True)
        with self.assertRaises(ValueError): self.service.plan_registered_sources([])
        self.assertEqual(self.store.count(BATCH), 0)

    def test_source_or_work_membership_changed_after_preview_is_rejected(self):
        source = self.source(); plan = self.service.plan_registered_sources([source['id']])
        # A real SQL version mutation simulates another editor without rendering fixtures.
        payload = json.loads(self.library.db.execute('SELECT payload FROM sources WHERE id=?', (source['id'],)).fetchone()[0])
        payload['page'] = 3
        with self.library.db: self.library.db.execute('UPDATE sources SET payload=? WHERE id=?', (json.dumps(payload), source['id']))
        with self.assertRaisesRegex(ValueError, '已改變'): self.service.create(plan, 'Reviewer', True)
        self.assertEqual(self.store.count(MEMBER), 0)

    def test_audit_failure_rolls_back_entire_batch(self):
        source = self.source(); plan = self.service.plan_registered_sources([source['id']]); before = self.store.epoch
        with patch.object(self.library, 'event', side_effect=sqlite3.OperationalError('disk full')):
            with self.assertRaises(sqlite3.OperationalError): self.service.create(plan, 'Reviewer', True)
        self.assertEqual(self.store.count(BATCH), 0); self.assertEqual(self.store.count(MEMBER), 0)
        self.assertEqual(self.store.epoch, before)

    def test_actual_bytes_check_never_approves_review_and_cas_blocks_second_writer(self):
        source = self.source(); batch = self.batch([source]); member = self.service.members(batch['id'])['rows'][0]
        saved = self.service.check_member_sources(member['id'], member['revision'])
        self.assertEqual(saved['check_state'], 'SOURCE_BYTES_VERIFIED_AWAITING_REVIEW')
        self.assertEqual(saved['review_state'], 'UNKNOWN_NOT_YET_REVIEWED')
        self.assertTrue(saved['last_check']['does_not_approve_segmentation_facts_customer_or_style'])
        with self.assertRaises(ValueError): CoverageBatches(self.library).check_member_sources(member['id'], member['revision'])
        self.assertFalse(self.service.boundary_summary(batch['id'])['closure_allowed'])

    def test_changed_and_missing_files_remain_in_denominator(self):
        sources = [self.source(), self.source('missing.svg')]; batch = self.batch(sources)
        Path(sources[0]['original_path']).write_text('changed'); Path(sources[1]['original_path']).unlink()
        for member in self.service.members(batch['id'])['rows']:
            self.assertEqual(self.service.check_member_sources(member['id'], member['revision'])['check_state'], 'SOURCE_UNRESOLVED')
        summary = self.service.boundary_summary(batch['id'])
        self.assertEqual(summary['declared_files'], 2); self.assertEqual(summary['check_record_counts'], {'SOURCE_UNRESOLVED': 2})

    def test_conflicting_versions_same_original_path_are_not_content_reuse(self):
        a = self.source(); b = self.source(content=b'<svg>new</svg>'); batch = self.batch([a, b])
        member = self.service.members(batch['id'])['rows'][0]
        result = self.service.check_member_sources(member['id'], member['revision'])
        self.assertEqual(result['check_state'], 'SOURCE_VERSION_CONFLICT')
        self.assertEqual(result['frozen']['source_page_count'], 2)

    def test_segmentation_does_not_complete_seven_semantic_layers(self):
        source,work,batch,member = self.work_member()
        plan = self.service.segmentation_plan(member['id'],[work['id']],'Inspected actual source boundaries')
        self.service.confirm_segmentation(plan,'Reviewer',True)
        evidence = self.service.member_evidence(member['id'])
        self.assertEqual(evidence['actual_work_count'],1); self.assertFalse(evidence['closure_allowed'])
        self.assertEqual(len([b for b in evidence['blockers'] if b['code']=='REQUIRED_LAYER_UNREVIEWED']),7)

    def test_all_individually_reviewed_layers_have_traceable_current_evidence(self):
        source,work,batch,member = self.work_member(); self.review_all(member,work)
        evidence=self.service.member_evidence(member['id'])
        self.assertTrue(evidence['closure_allowed']); self.assertEqual(evidence['disposition'],'ALL_REQUIRED_LAYERS_REVIEWED')
        self.assertEqual(len(evidence['review_pins']),7)
        self.assertTrue(all(v==dict(required=1,current_reviewed=1) for v in evidence['layer_counts'].values()))
        self.assertFalse(evidence['works'][0]['context']['automated_analysis_is_review'])

    def test_manual_review_needs_explicit_approval_and_failed_audit_saves_nothing(self):
        source,work,batch,member = self.work_member()
        plan=self.service.layer_plan(member['id'],work['id'],'people','VERIFIED_ABSENT','No person on inspected source','Full page1')
        with self.assertRaises(ValueError):self.service.confirm_layer(plan,'Reviewer')
        with patch.object(self.library,'event',side_effect=sqlite3.OperationalError('disk full')):
            with self.assertRaises(sqlite3.OperationalError):self.service.confirm_layer(plan,'Reviewer',True)
        self.assertIsNone(self.store.get('COVERAGE_REVIEW',plan['review_id']))

    def test_exact_review_cannot_apply_to_another_alias_work(self):
        source,work,batch,member=self.work_member(); alias=self.source('other.svg')
        with self.assertRaises(ValueError):self.service.layer_plan(member['id'],'unrelated-work','people','CONFIRMED','Check','Page1')

    def test_model_or_rule_version_change_invalidates_prior_review_without_deleting_it(self):
        source,work,batch,member=self.work_member();self.review_all(member,work)
        with self.store.transaction():self.store._write('SEMANTIC_ACTIVE','local-text',dict(model_id='new-model'),0,'test_active_model_changed')
        evidence=self.service.member_evidence(member['id'])
        self.assertFalse(evidence['closure_allowed']);self.assertEqual(len(evidence['review_pins']),7)
        self.assertTrue(all(layer['state']=='STALE_REVIEW' for layer in evidence['works'][0]['layers'].values()))

    def test_exclusion_is_separate_from_review_learning_and_style_approval(self):
        source,work,batch,member=self.work_member()
        self.service.confirm_segmentation(self.service.segmentation_plan(member['id'],[work['id']],'Full page actual work reviewed'),'Reviewer',True)
        plan=self.service.exclusion_plan(member['id'],'Out of approved review scope, known source','Original file page1 inspected')
        saved=self.service.confirm_exclusion(plan,'Reviewer',True);evidence=self.service.member_evidence(member['id'])
        self.assertEqual(evidence['disposition'],'APPROVED_EXCLUSION');self.assertTrue(evidence['closure_allowed'])
        self.assertFalse(saved['impact']['counts_as_successful_learning']);self.assertFalse(saved['impact']['counts_as_approved_style'])
        self.assertEqual(evidence['actual_work_count'],1)

    def test_unparsed_source_cannot_be_excluded_even_when_bytes_are_readable(self):
        source=self.source();batch=self.batch([source]);member=self.service.members(batch['id'])['rows'][0]
        with self.assertRaisesRegex(ValueError,'未讀取／未解析'):self.service.exclusion_plan(member['id'],'Skip','Readable bytes but no parsed works')

    def test_unreadable_source_cannot_be_hidden_by_exclusion(self):
        source=self.source();batch=self.batch([source]);member=self.service.members(batch['id'])['rows'][0]
        Path(source['original_path']).unlink()
        with self.assertRaises(OSError):self.service.exclusion_plan(member['id'],'No longer wanted','Missing source is not valid evidence')
        evidence=self.service.member_evidence(member['id']);self.assertFalse(evidence['closure_allowed']);self.assertEqual(evidence['file_count'],1)

    def test_missing_source_pages_block_complete_source_segmentation(self):
        source,work,batch,member=self.work_member()
        # Two-page source with only one registered page remains a source-file gap.
        frozen=copy.deepcopy(member['frozen']);frozen['source_pins'][0]['page_count']=2
        with self.store.transaction():
            changed=copy.deepcopy(member);changed['frozen']=frozen;self.store._write(MEMBER,member['id'],changed,member['revision'],'test_two_page_boundary')
        with self.assertRaisesRegex(ValueError,'缺少原稿頁面'):self.service.segmentation_plan(member['id'],[work['id']],'One page inspected')

    def test_closed_receipt_requires_all_layers_and_does_not_publish(self):
        source,work,batch,member=self.work_member()
        pending=self.service.closure_plan(batch['id']);self.assertFalse(pending['closure_allowed'])
        with self.assertRaises(ValueError):self.service.close(pending,'Reviewer',True)
        self.review_all(member,work);plan=self.service.closure_plan(batch['id'])
        self.assertEqual((plan['file_count'],plan['actual_work_count'],plan['unresolved_files']),(1,1,0))
        receipt=self.service.close(plan,'Reviewer',True)
        self.assertTrue(receipt['immutable']);self.assertFalse(receipt['publication_authorized']);self.assertFalse(receipt['output_authorized'])
        self.assertTrue(self.service.closure_status(batch['id'])['current_complete'])
        with self.assertRaises(ValueError):self.service.close(plan,'Reviewer',True)

    def test_changed_bytes_stale_closure_and_explicit_reopen_preserves_old_receipt(self):
        source,work,batch,member=self.work_member();self.review_all(member,work)
        receipt=self.service.close(self.service.closure_plan(batch['id']),'Reviewer',True)
        Path(source['original_path']).write_text('<svg>changed</svg>')
        self.assertFalse(self.service.closure_status(batch['id'])['current_complete'])
        current=self.service.batch(batch['id']);new_scope=self.service.plan_registered_sources([source['id']])
        reopened=self.service.reopen(batch['id'],current['revision'],new_scope,'Reviewer','Actual source bytes changed; original receipt retained',True)
        self.assertEqual(reopened['previous_batch_id'],batch['id']);self.assertIsNone(reopened['closure_receipt'])
        self.assertEqual(self.store.get('COVERAGE_CLOSURE',receipt['id']),receipt)
        self.assertEqual(self.service.batch(batch['id'])['state'],'REOPENED')
        self.assertFalse(self.service.closure_plan(reopened['id'])['closure_allowed'])

    def test_closure_disk_failure_rolls_back_receipt_and_closed_state(self):
        source,work,batch,member=self.work_member();self.review_all(member,work);plan=self.service.closure_plan(batch['id'])
        original=self.library.event
        def fail_link(entity,action):
            if 'receipt_linked' in action:raise sqlite3.OperationalError('disk full after receipt insertion')
            original(entity,action)
        with patch.object(self.library,'event',side_effect=fail_link):
            with self.assertRaises(sqlite3.OperationalError):self.service.close(plan,'Reviewer',True)
        self.assertEqual(self.store.count('COVERAGE_CLOSURE'),0)
        self.assertIsNone(self.service.batch(batch['id'])['closure_receipt'])
        self.assertFalse(self.service.closure_status(batch['id'])['current_complete'])

    def test_concurrent_review_update_invalidates_closure_preview(self):
        source,work,batch,member=self.work_member();self.review_all(member,work);plan=self.service.closure_plan(batch['id'])
        newer=self.service.layer_plan(member['id'],work['id'],'customer','VERIFIED_ABSENT','Individually checked no assignment','Page1 no association')
        self.service.confirm_layer(newer,'Second reviewer',True)
        with self.assertRaisesRegex(ValueError,'依賴已改變'):self.service.close(plan,'Reviewer',True)
        self.assertEqual(self.store.count('COVERAGE_CLOSURE'),0)

    def test_missing_receipt_fails_closed_and_does_not_auto_reanalyse(self):
        source,work,batch,member=self.work_member();self.review_all(member,work)
        receipt=self.service.close(self.service.closure_plan(batch['id']),'Reviewer',True)
        with self.library.db:self.library.db.execute('DELETE FROM training_records WHERE kind=? AND id=?',('COVERAGE_CLOSURE',receipt['id']))
        self.assertEqual(self.service.closure_status(batch['id'])['state'],'MISSING_RECEIPT')
        self.assertEqual(self.store.count('AUTO_JOB'),0)

    def test_explicit_unregistered_files_stay_in_denominator_and_block_closure(self):
        source=self.source();unknown=self.root/'unregistered.ai';unknown.write_bytes(b'not yet parsed')
        batch=self.service.create(self.service.plan_source_files([source['original_path'],str(unknown)]),'Reviewer',True)
        plan=self.service.closure_plan(batch['id'])
        self.assertEqual((plan['file_count'],plan['source_page_count'],plan['unresolved_files']),(2,1,2))
        self.assertIsNone(plan['actual_work_count']);self.assertFalse(plan['closure_allowed'])
        unknown_member=next(row for row in self.service.members(batch['id'])['rows'] if not row['frozen']['source_pins'])
        checked=self.service.check_member_sources(unknown_member['id'],unknown_member['revision'])
        self.assertEqual(checked['check_state'],'SOURCE_UNREGISTERED');self.assertEqual(self.store.count('AUTO_JOB'),0)

    def test_missing_explicit_file_can_be_persisted_as_unresolved_not_dropped(self):
        missing=str(self.root/'missing.ai');batch=self.service.create(self.service.plan_source_files([missing]),'Reviewer',True)
        self.assertEqual(self.service.members(batch['id'])['total'],1)
        self.assertFalse(self.service.closure_plan(batch['id'])['closure_allowed'])

    def test_registered_page_appearing_after_file_preview_invalidates_creation(self):
        path=self.root/'later.svg';path.write_bytes(b'<svg/>');plan=self.service.plan_source_files([str(path)])
        self.source('later.svg')
        with self.assertRaisesRegex(ValueError,'已改變'):self.service.create(plan,'Reviewer',True)
        self.assertEqual(self.store.count(BATCH),0)

    def test_root_snapshot_new_file_before_create_is_rejected(self):
        folder=self.root/'inputs';folder.mkdir();self.source('inputs/one.svg')
        plan=self.service.plan_directory(folder);(folder/'new.ai').write_text('new file')
        with self.assertRaisesRegex(ValueError,'成員已變更'):self.service.create(plan,'Reviewer',True)
        self.assertEqual(self.store.count(BATCH),0)

    def test_root_snapshot_new_file_invalidates_closed_receipt_without_mutating_it(self):
        source,work,unused,unused_member=self.work_member()
        # An isolated source root excludes the application's live database directory.
        folder=self.root/'inputs';folder.mkdir();path=folder/'one.svg';path.write_bytes(Path(source['original_path']).read_bytes())
        with self.library.db:
            payload=dict(source,original_path=str(path),page_count=1,width_mm=90,height_mm=54)
            self.library.db.execute('UPDATE sources SET original_path=?,payload=? WHERE id=?',(str(path),json.dumps(payload),source['id']))
        batch=self.service.create(self.service.plan_directory(folder),'Reviewer',True);member=self.service.members(batch['id'])['rows'][0]
        self.review_all(member,work);receipt=self.service.close(self.service.closure_plan(batch['id']),'Reviewer',True)
        (folder/'new.ai').write_text('unparsed new source')
        status=self.service.closure_status(batch['id']);self.assertFalse(status['current_complete']);self.assertEqual(status['state'],'STALE_REOPEN_REQUIRED')
        self.assertEqual(self.store.get('COVERAGE_CLOSURE',receipt['id']),receipt)

    def test_partial_root_scan_is_persisted_but_never_closable(self):
        folder=self.root/'inputs';folder.mkdir();self.source('inputs/one.svg');(folder/'linked.ai').symlink_to(folder/'one.svg')
        plan=self.service.plan_directory(folder);self.assertFalse(plan['root_snapshot']['scan_complete'])
        batch=self.service.create(plan,'Reviewer',True);closure=self.service.closure_plan(batch['id'])
        self.assertFalse(closure['closure_allowed']);self.assertTrue(closure['scope_blockers'])
        self.assertIsNone(plan['root_snapshot']['unscanned_entries'])

    def test_exact_source_version_selection_never_drops_declared_unknown_files(self):
        a=self.source();b=self.source(content=b'<svg>new</svg>');unknown=str(self.root/'unknown.ai')
        plan=self.service.plan_source_files([a['original_path'],unknown],[b['id']])
        self.assertEqual(plan['file_count'],2);self.assertEqual(plan['source_ids'],[b['id']]);self.assertEqual(len(plan['members'][0]['expected_hashes']),1)
        with self.assertRaises(ValueError):self.service.plan_source_files([unknown],[b['id']])

    def test_pending_source_observation_blocks_semantic_layer_confirmation(self):
        source,work,batch,member=self.work_member()
        observation=dict(id='note',slot_id=None,text='已校稿',object_type='ANNOTATION',classification='ANNOTATION',region=dict(x=0,y=0,w=1,h=1))
        self.store.save_facts(work['id'],[observation],0,work['revision'])
        with self.assertRaisesRegex(ValueError,'未確認／過期'):self.service.layer_plan(member['id'],work['id'],'fields','CONFIRMED','Not a substitute for facts review','Page1')

    def test_same_bytes_alias_keeps_independent_seven_layer_and_customer_obligations(self):
        source,work,old_batch,old_member=self.work_member();alias_path=self.root/'another-customer.svg';alias_path.write_bytes(Path(source['original_path']).read_bytes())
        alias=self.library.add_source(alias_path,self.library.source(source['id']));alias_work=self.library.create_artwork(alias['id'],'Independent alias work',work['payload'])
        batch=self.batch([source,alias]);members=self.service.members(batch['id'])['rows'];first=next(m for m in members if any(p['source_id']==source['id'] for p in m['frozen']['source_pins']))
        self.review_all(first,work);plan=self.service.closure_plan(batch['id'])
        self.assertEqual((plan['file_count'],plan['individually_reviewed_files'],plan['unresolved_files']),(2,1,1))
        self.assertEqual(plan['file_disposition_rate'],.5);self.assertFalse(plan['closure_allowed']);self.assertIsNone(plan['layer_rates']['customer']['review_rate'])
        other=next(m for m in members if m['id']!=first['id']);self.assertEqual(self.service.member_evidence(other['id'])['layer_counts']['customer']['current_reviewed'],0)

    def test_excluded_files_have_separate_disposition_and_zero_human_review_rate(self):
        source,work,batch,member=self.work_member();self.service.confirm_segmentation(self.service.segmentation_plan(member['id'],[work['id']],'Full source reviewed'),'Reviewer',True)
        self.service.confirm_exclusion(self.service.exclusion_plan(member['id'],'Not applicable to this learning scope','Full page inspected'),'Reviewer',True)
        plan=self.service.closure_plan(batch['id']);self.assertEqual(plan['file_disposition_rate'],1);self.assertEqual(plan['file_human_review_rate'],0)
        self.assertEqual(plan['approved_excluded_files'],1);self.assertEqual(plan['layer_rates']['styles']['review_rate'],0)
        with self.store.transaction():self.store._write('SEMANTIC_ACTIVE','local-text',dict(model_id='changed'),0,'test_changed_dependency')
        self.assertFalse(self.service.member_evidence(member['id'])['closure_allowed'])

    def test_same_page_overlapping_work_crops_cannot_be_confirmed_as_independent_works(self):
        source,work,batch,member=self.work_member();other=self.library.create_artwork(source['id'],'Overlapping alternative',work['payload'])
        fresh=self.batch([source]);member=self.service.members(fresh['id'])['rows'][0]
        with self.assertRaisesRegex(ValueError,'切分框重複'):self.service.segmentation_plan(member['id'],[work['id'],other['id']],'Cannot assert duplicated full-page crops')

    def test_actual_relink_after_closure_preview_invalidates_old_scope(self):
        from template_ai.source_links import verify_source
        source,work,batch,member=self.work_member();self.review_all(member,work);plan=self.service.closure_plan(batch['id'])
        target=self.root/'relocated.svg';target.write_bytes(Path(source['original_path']).read_bytes())
        self.library.relink_source(source['id'],verify_source(target,source['hash']),0)
        with self.assertRaises(ValueError):self.service.close(plan,'Reviewer',True)
        self.assertFalse(self.service.closure_plan(batch['id'])['closure_allowed']);self.assertEqual(self.store.count('COVERAGE_CLOSURE'),0)

    def test_restart_reads_actual_committed_closure_and_second_connection_cannot_overwrite(self):
        source,work,batch,member=self.work_member();self.review_all(member,work);plan=self.service.closure_plan(batch['id'])
        other=Library(self.library.root)
        try:
            TrainingStore(other);service=CoverageBatches(other);second=service.closure_plan(batch['id'])
            receipt=self.service.close(plan,'Reviewer',True)
            with self.assertRaises(ValueError):service.close(second,'Other reviewer',True)
            self.assertTrue(service.closure_status(batch['id'])['current_complete']);self.assertEqual(service.store.get('COVERAGE_CLOSURE',receipt['id']),receipt)
        finally:other.close()

    def test_unresolved_customer_candidate_blocks_layer_closure_and_exclusion(self):
        from template_ai.customers import CustomerStore
        from template_ai.customer_candidates import CustomerCandidates
        source,work,batch,member=self.work_member();candidates=CustomerCandidates(CustomerStore(self.library))
        with self.library.db:candidates._save('synthetic-customer-candidate',dict(pins=dict(artwork_id=work['id'],source_id=source['id']),issues=['ambiguous identity']), 'PENDING_REVIEW',0)
        with self.assertRaisesRegex(ValueError,'客戶來源候選'):self.service.layer_plan(member['id'],work['id'],'customer','CONFIRMED','Cannot bypass identity review','Page1')
        self.service.confirm_segmentation(self.service.segmentation_plan(member['id'],[work['id']],'Full source inspected'),'Reviewer',True)
        with self.assertRaisesRegex(ValueError,'客戶歸屬'):self.service.exclusion_plan(member['id'],'Cannot hide unresolved identity','Source proof')
        self.assertIn('CUSTOMER_IDENTITY_UNRESOLVED',{b['code'] for b in self.service.member_evidence(member['id'])['blockers']})
