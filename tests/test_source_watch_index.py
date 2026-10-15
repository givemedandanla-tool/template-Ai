import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from template_ai.storage import Library
from template_ai.training_store import TrainingStore
from template_ai.source_scan import register_root,configure_root,scan_files,save_scan,candidate_page,active_roots


class SourceWatchIndexTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.library=Library(self.root/'data');self.addCleanup(lambda:self.library.close());self.store=TrainingStore(self.library)
        self.directory=self.root/'sources';self.directory.mkdir();self.a=self.directory/'A001.svg';self.b=self.directory/'B002.svg';self.a.write_bytes(b'<svg>synthetic</svg>');self.b.write_bytes(self.a.read_bytes());self.watch=register_root(self.store,self.directory)

    def enable(self):self.watch=configure_root(self.store,self.watch,mode='AUTO_PRECHECK',enabled=True)
    def scan(self):return scan_files(self.watch,{},stable_wait=.05)
    def save(self,automatic=True):self.watch=save_scan(self.store,self.watch,self.scan(),automatic=automatic);return candidate_page(self.store,self.watch['id'])

    def test_explicit_configuration_cas_formats_exclusions_and_archive_keep_all_existing_records(self):
        with self.assertRaises(ValueError):configure_root(self.store,self.watch,extensions=[])
        with self.assertRaises(ValueError):configure_root(self.store,self.watch,excludes=['../private'])
        with self.assertRaises(ValueError):register_root(self.store,self.library.root)
        old=self.watch;self.enable()
        with self.assertRaisesRegex(ValueError,'版本'):configure_root(self.store,old,enabled=False)
        self.save();before=candidate_page(self.store);self.watch=configure_root(self.store,self.watch,archive=True)
        self.assertEqual(active_roots(self.store),[]);self.assertEqual(candidate_page(self.store),before);self.assertTrue(self.a.exists())

    def test_alias_candidate_index_is_persistent_idempotent_and_never_starts_training_or_merges_customers(self):
        self.enable();first=self.save();self.assertEqual(len(first),2);self.assertEqual({x['state'] for x in first},{'QUEUED_FOR_UI003_PREFLIGHT'})
        self.assertEqual(len({x['id'] for x in first}),2);self.assertEqual(len({x['source_hash'] for x in first}),1)
        self.library.close();self.library=Library(self.root/'data');self.store=TrainingStore(self.library);self.watch=self.store.get('SCAN_ROOT',self.watch['id'])
        second=self.save();self.assertEqual(second,first);self.assertEqual(self.library.list_sources(),[]);self.assertEqual(self.store.count('AUTO_JOB'),0)

    def test_manual_discovery_enters_auto_queue_only_after_explicit_enable(self):
        first=self.save(False);self.assertEqual({x['state'] for x in first},{'FOUND_NOT_QUEUED'})
        self.enable();second=self.save();self.assertEqual({x['id'] for x in second},{x['id'] for x in first});self.assertEqual({x['state'] for x in second},{'QUEUED_FOR_UI003_PREFLIGHT'})

    def test_changed_content_preserves_old_evidence_and_invalidates_only_that_pending_candidate(self):
        self.enable();first=self.save();original=next(c for c in first if c['path']==str(self.a));other=next(c for c in first if c['path']==str(self.b));self.a.write_bytes(b'<svg>changed version</svg>')
        second=self.save();old=self.store.get('SCAN_CANDIDATE',original['id']);new=next(c for c in second if c['path']==str(self.a) and c['id']!=old['id'])
        self.assertEqual(old['state'],'STALE_SOURCE_CHANGED');self.assertEqual(old['source_hash'],original['source_hash']);self.assertEqual(new['state'],'REVIEW_REQUIRED');self.assertEqual(self.store.get('SCAN_CANDIDATE',other['id']),other)
        self.assertEqual(self.store.count('AUTO_JOB'),0);self.assertEqual(self.library.list_sources(),[])

    def test_root_pause_or_audit_failure_cannot_partially_commit_candidates_or_a_fake_success(self):
        self.enable();report=self.scan();before=self.watch
        with patch.object(self.library,'event',side_effect=RuntimeError('disk audit failure')):
            with self.assertRaises(RuntimeError):save_scan(self.store,self.watch,report,automatic=True)
        self.assertEqual(candidate_page(self.store),[]);self.assertEqual(self.store.get('SCAN_ROOT',before['id']),before)
        self.watch=configure_root(self.store,self.watch,enabled=False)
        with self.assertRaises(ValueError):save_scan(self.store,before,report,automatic=True)
        self.assertEqual(candidate_page(self.store),[])

    def test_offline_and_missing_are_unresolved_and_keep_last_effective_index(self):
        self.enable();first=self.save();last=self.watch['last_scan'];self.directory.rename(self.root/'offline');result=self.scan();self.watch=save_scan(self.store,self.watch,result,automatic=True)
        self.assertEqual(result['state'],'ROOT_OFFLINE');self.assertEqual(self.watch['last_scan'],last);self.assertEqual(candidate_page(self.store),first)
        (self.root/'offline').rename(self.directory);self.a.unlink();result=self.scan();self.assertFalse(result['complete']);self.assertEqual(next(r for r in result['entries'] if r['path']==str(self.a))['state'],'MISSING_OR_MOVED_REVIEW_REQUIRED');self.assertFalse(result['deletions_inferred'])

    def test_temporary_files_are_excluded_and_directory_work_is_bounded_without_silent_completion(self):
        (self.directory/'~Illustrator.svg').write_bytes(b'partial temporary');result=self.scan();self.assertEqual(len(result['entries']),2);self.assertGreater(result['excluded_entries'],0)
        for i in range(505):(self.directory/f'ignored-{i}.txt').write_text('not a source')
        result=self.scan();self.assertEqual(result['state'],'PARTIAL');self.assertLessEqual(result['scanned_entries'],500);self.assertFalse(result['enumeration_complete'])

    def test_changed_registered_source_keeps_customer_templates_other_source_and_training_evidence(self):
        import test_customer_candidates as fixture
        from template_ai.source_scan import known_sources
        from template_ai.source_links import verify_source
        c=fixture.CustomerCandidateTests('test_filename_full_rule_and_actual_facts_propose_only_without_master_writes');c.setUp();self.addCleanup(c.tearDown)
        first=c.commit([c.reviewed(c.candidates.propose(c.source['id'])[0])])[0]
        second,work,template=c.make_source('00002.svg');other=c.commit([c.reviewed(c.candidates.propose(second['id'])[0])])[0]
        store=TrainingStore(c.library);root=register_root(store,c.root);known,index=known_sources(c.library,root);initial=scan_files(root,known,stable_wait=.05)
        self.assertEqual({r['artwork_count'] for r in initial['entries']},{1});self.assertTrue(all(r['registered'] for r in initial['entries']));root=save_scan(store,root,initial)
        sources=c.library.list_sources();templates=c.library.template_snapshots();customers=[c.store.get(item['customer_id']) for item in [first,other]]
        evidence=c.library.db.execute("SELECT kind,id,revision,payload FROM training_records WHERE kind NOT LIKE 'SCAN_%' ORDER BY kind,id").fetchall()
        path=Path(c.source['original_path']);path.write_bytes(path.read_bytes()+b'\n<!-- synthetic user new version -->')
        known,index=known_sources(c.library,root);result=scan_files(root,known,stable_wait=.05);save_scan(store,root,result)
        changed=next(r for r in result['entries'] if r['path']==str(path));self.assertEqual(changed['state'],'CONTENT_CHANGED_REVIEW_REQUIRED');self.assertEqual(changed['affected_source_ids'],[c.source['id']])
        self.assertEqual(candidate_page(store,root['id'])[0]['state'],'REVIEW_REQUIRED');self.assertEqual(c.library.list_sources(),sources);self.assertEqual(c.library.template_snapshots(),templates);self.assertEqual([c.store.get(item['customer_id']) for item in [first,other]],customers)
        self.assertEqual(c.library.db.execute("SELECT kind,id,revision,payload FROM training_records WHERE kind NOT LIKE 'SCAN_%' ORDER BY kind,id").fetchall(),evidence)
        with self.assertRaisesRegex(ValueError,'內容已變更'):verify_source(path,c.source['hash'])
        self.assertEqual(verify_source(second['original_path'],second['hash']).hash,second['hash'])

    def test_changed_version_review_requires_live_proof_and_dispatch_requires_an_actual_job(self):
        from template_ai.source_scan import review_candidate,record_dispatch
        from template_ai.source_links import verify_source
        self.enable();self.save();self.a.write_bytes(b'<svg>new version</svg>');values=self.save();candidate=next(c for c in values if c['path']==str(self.a) and c['state']=='REVIEW_REQUIRED');proof=verify_source(self.a,candidate['source_hash'])
        with self.assertRaises(ValueError):review_candidate(self.store,candidate,proof,'synthetic',False)
        self.a.write_bytes(self.a.read_bytes()+b' ')
        with self.assertRaises(ValueError):review_candidate(self.store,candidate,proof,'synthetic',True)
        with self.assertRaisesRegex(ValueError,'實際UI003'):record_dispatch(self.store,[candidate],'absent-job')
        self.assertEqual(self.store.get('SCAN_CANDIDATE',candidate['id']),candidate);self.assertEqual(self.store.count('AUTO_JOB'),0)

    def test_temporary_read_failure_preserves_last_verified_hash_for_later_modified_version_review(self):
        from template_ai.source_links import hash_source
        self.enable();self.save();old_hash=next(c['source_hash'] for c in candidate_page(self.store) if c['path']==str(self.a))
        def denied(path,**kwargs):
            if Path(path)==self.a:raise PermissionError('synthetic sharing violation')
            return hash_source(path,**kwargs)
        with patch('template_ai.source_scan.hash_source',side_effect=denied):failed=self.scan()
        self.assertFalse(failed['complete']);self.watch=save_scan(self.store,self.watch,failed,automatic=True)
        self.a.write_bytes(b'<svg>later modified source</svg>');changed=self.scan();entry=next(r for r in changed['entries'] if r['path']==str(self.a))
        self.assertEqual(entry['previous_hash'],old_hash);self.assertEqual(entry['state'],'CONTENT_CHANGED_REVIEW_REQUIRED')
        self.watch=save_scan(self.store,self.watch,changed,automatic=True);self.assertTrue(any(c['state']=='REVIEW_REQUIRED' and c['path']==str(self.a) for c in candidate_page(self.store)))

    def test_actual_sqlite_full_rolls_back_whole_candidate_index_without_losing_existing_root(self):
        import sqlite3
        self.enable()
        for i in range(48):(self.directory/f'new-{i}.svg').write_bytes(self.a.read_bytes())
        report=self.scan();before=self.store.get('SCAN_ROOT',self.watch['id']);page_count=self.library.db.execute('PRAGMA page_count').fetchone()[0];old_limit=self.library.db.execute('PRAGMA max_page_count').fetchone()[0]
        self.library.db.execute('PRAGMA max_page_count='+str(page_count))
        try:
            with self.assertRaisesRegex(sqlite3.OperationalError,'full'):save_scan(self.store,self.watch,report,automatic=True)
        finally:self.library.db.execute('PRAGMA max_page_count='+str(old_limit))
        self.assertEqual(self.store.get('SCAN_ROOT',self.watch['id']),before);self.assertEqual(candidate_page(self.store),[]);self.assertEqual(len(list(self.directory.glob('*.svg'))),50)
