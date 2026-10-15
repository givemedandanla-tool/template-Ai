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
