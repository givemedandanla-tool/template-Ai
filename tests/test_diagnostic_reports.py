from gui_wait import wait_layout
import copy
import errno
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import time
import unittest
from unittest.mock import patch
import zipfile
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QMessageBox
import test_seventy_ui as fixture
from training_fixture import source_work
from template_ai.diagnostic_bundle import (build_bundle,read_bundle,save_bundle,report_html,encoded,sha,MAX_BYTES)
from template_ai.diagnostic_snapshot import make_snapshot,locate,LocatorStore,TTL_SECONDS
from template_ai.diagnostic_dialog import DiagnosticReportDialog,open_saved_report
from template_ai.layout import generate
from template_ai.layout_session import LayoutSessionDialog


class DiagnosticReportTests(unittest.TestCase):
    def setUp(self):
        fixture.SeventyUiTests.setUp(self)
        p=patch.object(QMessageBox,'warning',return_value=QMessageBox.Ok);p.start();self.addCleanup(p.stop)
    def dialog(self,kind='input',**kwargs):
        d=DiagnosticReportDialog(self.w,kind,**kwargs);self.addCleanup(d.deleteLater);d.show()
        fixture.pump_until(lambda:d.raw is not None or d.status.text().startswith(('未產生','未完成')))
        self.assertFalse(d.running);return d
    def candidate(self):
        self.w.generate();wait_layout(self.w);self.assertTrue(self.w.candidates);return self.w.candidates[0]
    def write(self,snapshot,name='report.zip'):
        path=self.root/name;save_bundle(path,build_bundle(snapshot.data),lambda:snapshot.check(self.w));LocatorStore(self.w.library).remember(snapshot);return path
    def tampered(self,raw,transform):
        with zipfile.ZipFile(io.BytesIO(raw)) as z:entries={n:z.read(n) for n in z.namelist()}
        transform(entries)
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w') as z:
            for n,b in entries.items():z.writestr(n,b)
        return out.getvalue()
    def test_explicit_imported_font_keeps_real_metrics_private_and_report_nonformal(self):
        from template_ai.demo import demo_template
        from authored_font_fixture import bind_authored_fonts
        template=demo_template();template.name='Authored explicit font diagnostic';bind_authored_fonts(template,self.w.font_manager);self.w.library.publish(template);self.w.refresh_templates();self.w.reorder_template_id=template.id
        candidate=self.candidate();before=copy.deepcopy(candidate);gate=self.w.export_button.isEnabled();snapshot=make_snapshot(self.w,'candidate');body=encoded(snapshot.data)
        self.assertTrue(candidate.valid,candidate.issues);self.assertTrue(snapshot.data['measurements']);self.assertTrue(any(r['parameters'].get('text_width_mm') is not None for r in snapshot.data['measurements']))
        for slot in candidate.template.slots:
            if slot.font_asset:
                self.assertNotIn(slot.font_asset['path'].encode(),body);self.assertNotIn(slot.font_asset['hash'].encode(),body)
        self.assertTrue(snapshot.data['historical']);self.assertTrue(snapshot.data['nonformal']);self.assertEqual(snapshot.data['model_quality'],'NOT_VERIFIED');self.assertEqual(snapshot.data['physical_print'],'NOT_VERIFIED');self.assertEqual(candidate,before);self.assertEqual(self.w.export_button.isEnabled(),gate);self.assertEqual(read_bundle(build_bundle(snapshot.data)),snapshot.data)

    def test_current_layout_progress_projects_only_public_denominators_not_internal_version_pins(self):
        self.candidate();private='FORBIDDEN_INTERNAL_TEMPLATE_PIN_831'
        self.w.last_layout_summary.update(generation=self.w.generation,scope_template_pins={private:private},future_private={'raw_path':str(self.root)})
        before=copy.deepcopy(self.w.last_layout_summary);snapshot=make_snapshot(self.w,'candidate');raw=build_bundle(snapshot.data)
        self.assertEqual(set(snapshot.data['progress']),{'state','total','checked','calculated','failed','unstarted','global_unsolvable'})
        self.assertEqual(snapshot.data['progress']['total'],before['total']);self.assertFalse(snapshot.data['progress']['global_unsolvable'])
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            for name in z.namelist():
                content=z.read(name);self.assertNotIn(private.encode(),content);self.assertNotIn(str(self.root).encode(),content)
        self.assertEqual(read_bundle(raw),snapshot.data);self.assertEqual(self.w.last_layout_summary,before)

    def test_snapshot_html_json_have_same_facts_width_and_historical_scope(self):
        self.w.people.item(0,0).setText('X'*200);c=self.candidate();before=copy.deepcopy(c)
        s=make_snapshot(self.w,'candidate');self.assertEqual(s.data['status'],'BLOCKED')
        row=next(r for r in s.data['issues'] if r['code']=='WIDTH');p=row['parameters']
        self.assertAlmostEqual(p['required_scale'],p['width_mm']/p['text_width_mm']);self.assertEqual(p['size_pt'],18)
        self.assertEqual(read_bundle(build_bundle(s.data)),s.data);page=report_html(s.data).decode()
        self.assertIn('固定字級（pt）',page);self.assertIn('實測字寬（mm）',page);self.assertIn('所需水平比例',page)
        self.assertIn(f"{p['required_scale']:.2%}",page);self.assertNotIn('<pre>',page);self.assertIn('UTC+8',page)
        self.assertEqual(c,before);self.assertEqual(s.data['physical_print'],'NOT_VERIFIED');self.assertFalse(s.data['progress']['global_unsolvable'])
    def test_input_empty_invalid_company_no_candidate_and_unknown_not_pass(self):
        self.w.people.item(0,0).setText('');s=make_snapshot(self.w,'input')
        self.assertIn('MISSING_NAME',[r['code'] for r in s.data['issues']]);self.assertEqual(s.data['status'],'PENDING_LAYOUT')
        self.w.people.item(0,7).setText('not-a-company');s=make_snapshot(self.w,'input');self.assertIn('INVALID_INPUT',[r['code'] for r in s.data['issues']])
        s=make_snapshot(self.w,'candidate');self.assertIn('NO_CANDIDATE',[r['code'] for r in s.data['issues']])
        self.assertEqual(s.data['stages']['DATA_PROCESSING'],'NOT_CHECKED');self.assertEqual(s.data['model_quality'],'NOT_VERIFIED')
    def test_missing_font_width_is_unknown_not_zero_or_substitute(self):
        t=copy.deepcopy(self.t);t.slots[0].font='Synthetic Unavailable Font 54731'
        people,companies,logos=self.w.input_data();c=generate(t,people,companies,logos,self.w.generation)
        self.w.candidates=[c];self.w.candidate_list.addItem('candidate');self.w.candidate_list.setCurrentRow(0)
        s=make_snapshot(self.w,'candidate');r=next(r for r in s.data['measurements'] if r['code']=='FONT_UNVERIFIED')
        self.assertIsNone(r['parameters']['text_width_mm']);self.assertIn('FONT_UNVERIFIED',[r['code'] for r in s.data['issues']]);self.assertFalse(c.valid)
        self.assertEqual(read_bundle(build_bundle(s.data)),s.data)
    def test_all_payloads_omit_synthetic_personal_ids_paths_notes_and_unknown_errors(self):
        forbidden=['FORBIDDEN_SYNTHETIC_NAME','forbidden@example.test','+12025550999','FORBIDDEN_SYNTHETIC_NOTE','FORBIDDEN_SYNTHETIC_SESSION_VALUE']
        for col,value in zip((0,3,2,4,5),forbidden):self.w.people.item(0,col).setText(value)
        c=self.candidate();c.template.name=forbidden[3];c.issues.append(forbidden[4]);c.diagnostics.append({'code':forbidden[0],'reason':forbidden[1],'kind':forbidden[2],'parameters':{'note':forbidden[3]},'slot_ids':[forbidden[4]]})
        s=make_snapshot(self.w,'candidate');raw=build_bundle(s.data)
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            self.assertEqual(set(z.namelist()),{'report.html','report.json','manifest.json'})
            for value in forbidden+[c.template.id,c.template.slots[0].id,str(self.root)]:
                for b in [raw]+[z.read(n) for n in z.namelist()]:self.assertNotIn(value.encode(),b)
        self.assertIn('UNCLASSIFIED',[r['code'] for r in s.data['issues']]);self.assertNotIn('reason',s.data['issues'][-1])
    def test_privacy_allowlist_rejects_unknown_fields_types_and_unsafe_html(self):
        s=make_snapshot(self.w,'input')
        for change in [lambda d:d.update(customer='FORBIDDEN_SYNTHETIC_NAME'),lambda d:d.update(report_id='../../x'),lambda d:d['scope'].update(width_mm=float('nan')),lambda d:d.update(model_quality='PASS')]:
            data=copy.deepcopy(s.data);change(data)
            with self.assertRaises(ValueError):build_bundle(data)
        self.assertNotIn(b'<script',report_html(s.data));self.assertNotIn(b'<img',report_html(s.data))
    def test_anonymous_targets_dont_merge_same_names_and_exact_input_navigation(self):
        from PySide6.QtWidgets import QTableWidgetItem
        self.w.people.setRowCount(2)
        for i in range(2):self.w.people.setItem(i,0,QTableWidgetItem(''));self.w.people.setItem(i,3,QTableWidgetItem('same@example.test'))
        s=make_snapshot(self.w,'input');rows=[(i,r) for i,r in enumerate(s.data['issues']) if r['code']=='MISSING_NAME']
        self.assertEqual([r['target'] for _,r in rows],['人物1','人物2']);locate(self.w,s.data,rows[1][0],s)
        self.assertEqual((self.w.people.currentRow(),self.w.people.currentColumn()),(1,0));self.assertEqual(self.w.people.item(0,3).text(),'same@example.test')
    def test_safe_save_collision_permission_disk_full_and_cleanup(self):
        raw=build_bundle(make_snapshot(self.w,'input').data);path=self.root/'report.zip';path.write_bytes(b'older result')
        with self.assertRaises(FileExistsError):save_bundle(path,raw)
        self.assertEqual(path.read_bytes(),b'older result');path.unlink()
        for name,error in [('os.link',PermissionError('synthetic denied')),('os.fsync',OSError(errno.ENOSPC,'synthetic disk full'))]:
            with patch(name,side_effect=error),self.assertRaises(OSError):save_bundle(path,raw)
            self.assertFalse(path.exists());self.assertFalse(list(self.root.glob('.diagnostic-*')))
    def test_save_race_and_preview_change_never_overwrite_or_report_success(self):
        s=make_snapshot(self.w,'input');path=self.root/'race.zip';calls=[]
        def racing():
            calls.append(1)
            if len(calls)==3:path.write_bytes(b'intervening writer')
        with self.assertRaises(FileExistsError):save_bundle(path,build_bundle(s.data),racing)
        self.assertEqual(path.read_bytes(),b'intervening writer')
        self.w.people.item(0,0).setText('Changed Example')
        with self.assertRaises(ValueError):save_bundle(self.root/'stale.zip',build_bundle(s.data),lambda:s.check(self.w))
        self.assertFalse((self.root/'stale.zip').exists())
    def test_locator_saved_readback_changed_library_and_manual_clear(self):
        self.w.people.item(0,0).setText('');s=make_snapshot(self.w,'input');path=self.write(s)
        data=read_bundle(path.read_bytes());locate(self.w,data,0);self.assertEqual(self.w.people.currentColumn(),0)
        other=type(self.w)(self.root/'other');self.addCleanup(other.library.db.close)
        with self.assertRaises(ValueError):locate(other,data,0)
        LocatorStore(self.w.library).clear()
        with self.assertRaises(ValueError):locate(self.w,data,0)
        self.assertEqual(read_bundle(path.read_bytes()),data)
    def test_locator_expiry_keeps_report_and_rejects_changed_input(self):
        self.w.people.item(0,0).setText('');s=make_snapshot(self.w,'input');path=self.write(s)
        self.w.people.item(0,0).setText('Changed Example')
        with self.assertRaises(ValueError):locate(self.w,s.data,0)
        store=LocatorStore(self.w.library);store.cleanup(time.time()+TTL_SECONDS+1)
        self.assertFalse(list(store.root.glob('*.json')));self.assertTrue(path.is_file())
    def test_source_changed_and_missing_still_readable_no_wrong_location(self):
        source,work=source_work(self.w.library,self.root,visual=False)
        s=make_snapshot(self.w,'training',work['id']);self.assertEqual(s.data['source_health'],'OK')
        Path(source['original_path']).write_text('changed synthetic source')
        with self.assertRaises(ValueError):s.check(self.w)
        missing=make_snapshot(self.w,'training',work['id']);self.assertEqual(missing.data['source_health'],'CHANGED')
        Path(source['original_path']).unlink();missing=make_snapshot(self.w,'training',work['id']);self.assertEqual(missing.data['source_health'],'MISSING')
        self.assertEqual(read_bundle(build_bundle(missing.data)),missing.data);self.assertTrue(all(not r['locatable'] for r in missing.data['issues']))
    def test_exact_work_revision_duplicate_slots_and_dirty_navigation_are_protected(self):
        source,work=source_work(self.w.library,self.root,visual=False);p=copy.deepcopy(work['payload']);p['slots'][0]['rect']['x']=999;work=self.w.library.save_artwork(work['id'],p,work['revision'])
        s=make_snapshot(self.w,'training',work['id']);i=next(i for i,r in enumerate(s.data['issues']) if r['code']=='BOUNDS');locate(self.w,s.data,i,s)
        self.assertEqual(self.w.work['id'],work['id']);self.assertEqual(self.w.current_slot.id,p['slots'][0]['id'])
        self.w.coords[0].setValue(7)
        with self.assertRaises(ValueError):locate(self.w,s.data,i,s)
        self.assertEqual(self.w.coords[0].value(),7)
        p['slots'].append(copy.deepcopy(p['slots'][0]));self.w.library.save_artwork(work['id'],p,work['revision'])
        with self.assertRaises(ValueError):s.check(self.w)
        s=make_snapshot(self.w,'training',work['id']);r=next(r for r in s.data['issues'] if r['code']=='DUPLICATE_ID');self.assertFalse(r['locatable'])
    def test_font_file_and_template_changes_invalidate_snapshot_without_gate_mutation(self):
        c=self.candidate();font=self.root/'synthetic-font';font.write_bytes(b'first')
        c.template.slots[0].font_asset={'path':str(font)};s=make_snapshot(self.w,'candidate');enabled=self.w.export_button.isEnabled();font.write_bytes(b'second')
        with self.assertRaises(ValueError):s.check(self.w)
        self.assertEqual(self.w.export_button.isEnabled(),enabled)
        s=make_snapshot(self.w,'candidate');c.template.slots[0].size_pt+=1
        with self.assertRaises(ValueError):s.check(self.w)
    def test_each_size_and_candidate_readonly_scope_never_unlocks_output(self):
        self.candidate();self.w.export_button.setEnabled(False);before=self.w.library.templates()[0].to_dict();self.w.people.item(0,0).setText('X'*200);self.candidate()
        s=make_snapshot(self.w,'candidate');i=next(i for i,r in enumerate(s.data['issues']) if r['code']=='WIDTH');self.w.export_button.setEnabled(False)
        locate(self.w,s.data,i,s);self.assertFalse(self.w.export_button.isEnabled());self.assertEqual(self.w.library.templates()[0].to_dict(),before)
        self.assertEqual(s.data['scope']['candidates'],1);self.assertEqual(s.data['scope']['width_mm'],90)
        self.w.out_w.setValue(100)
        with self.assertRaises(ValueError):s.check(self.w)
        self.assertEqual(read_bundle(build_bundle(s.data))['scope']['width_mm'],90)
    def test_session_partial_cancel_failed_and_unstarted_counts_are_real(self):
        d=LayoutSessionDialog(self.w);self.addCleanup(d.deleteLater);d.worker=type('W',(),{'templates':[self.t,self.t,self.t]})();d.output_size_mm=(90,54);d.report_state='CANCELLED';d.generation=self.w.generation
        p,c,l=self.w.input_data();candidate=generate(self.t,p,c,l,self.w.generation)
        d.rows=[{'template_id':self.t.id,'candidate':candidate,'state':'CALCULATED_PENDING_ADOPTION'},{'template_id':self.t.id,'candidate':None,'state':'FAILED','error':'FORBIDDEN_SYNTHETIC_EXCEPTION'}]
        self.w.out_w.setValue(100)
        s=make_snapshot(self.w,'session',session=d);self.assertEqual((s.data['scope']['width_mm'],s.data['scope']['height_mm']),(90,54));self.assertTrue(callable(d.size));p=s.data['progress'];self.assertEqual((p['total'],p['checked'],p['calculated'],p['failed'],p['unstarted']),(3,2,1,1,1));self.assertEqual(p['state'],'CANCELLED');self.assertNotIn(b'FORBIDDEN_SYNTHETIC_EXCEPTION',build_bundle(s.data))
        d.rows=[];d.report_state='FAILED_SYSTEM';s=make_snapshot(self.w,'session',session=d);self.assertEqual(s.data['progress']['unstarted'],3);self.assertEqual(s.data['status'],'FAILED_SYSTEM')
    def test_oversized_problem_set_is_explicit_partial_not_silent_success(self):
        c=self.candidate();c.issues=['synthetic']*2002;c.diagnostics=[{'code':'UNCLASSIFIED','severity':'REVIEW'} for _ in range(2002)]
        s=make_snapshot(self.w,'candidate');self.assertEqual(len(s.data['issues']),2000);self.assertEqual(s.data['omitted_issues'],2);self.assertEqual(s.data['progress']['state'],'PARTIAL')
        self.assertEqual(read_bundle(build_bundle(s.data)),s.data)
    def test_zip_traversal_duplicate_symlink_extra_and_bombs_rejected(self):
        raw=build_bundle(make_snapshot(self.w,'input').data)
        for name in ('../report.json','/report.json','extra.png','report.json'):
            out=io.BytesIO(raw)
            with zipfile.ZipFile(out,'a') as z:z.writestr(name,b'x')
            with self.assertRaises(ValueError):read_bundle(out.getvalue())
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr('report.json',b'A'*(MAX_BYTES+1));z.writestr('report.html',b'');z.writestr('manifest.json',b'')
        with self.assertRaises(ValueError):read_bundle(out.getvalue())
        out=io.BytesIO(raw)
        with zipfile.ZipFile(out,'a') as z:z.comment=b'FORBIDDEN_SYNTHETIC_METADATA'
        for bad in (out.getvalue(),raw+b'FORBIDDEN_SYNTHETIC_TRAILING',raw[:40]):
            with self.assertRaises(ValueError):read_bundle(bad)
    def test_supplied_html_scripts_with_correct_checksum_are_never_loaded(self):
        raw=build_bundle(make_snapshot(self.w,'input').data)
        def change(entries):
            entries['report.html']=b'<script>fetch("https://example.test")</script>'
            m=json.loads(entries['manifest.json']);m['files']['report.html']={'bytes':len(entries['report.html']),'sha256':sha(entries['report.html'])};entries['manifest.json']=encoded(m)
        with self.assertRaises(ValueError):read_bundle(self.tampered(raw,change))
        out=io.BytesIO(raw)
        with zipfile.ZipFile(out,'a') as z:
            info=zipfile.ZipInfo('evil');info.create_system=3;info.external_attr=(stat.S_IFLNK|0o777)<<16;z.writestr(info,'/tmp/synthetic-target')
        with self.assertRaises(ValueError):read_bundle(out.getvalue())
    def test_gui_actual_preview_save_reopen_json_and_cancel_flow(self):
        self.w.people.item(0,0).setText('');d=self.dialog();self.assertIsNotNone(d.raw);self.assertEqual(json.loads(d.machine.toPlainText()),d.data);self.assertIn('歷史快照',d.human.toPlainText())
        path=self.root/'saved.zip'
        with patch('template_ai.diagnostic_dialog.QFileDialog.getSaveFileName',return_value=('', '')):QTest.mouseClick(d.save_button,Qt.LeftButton)
        self.assertIn('取消',d.status.text());self.assertFalse(path.exists())
        with patch('template_ai.diagnostic_dialog.QFileDialog.getSaveFileName',return_value=(str(path),'')):QTest.mouseClick(d.save_button,Qt.LeftButton)
        self.assertIn('已完整保存',d.status.text());loaded=self.dialog(loaded=path.read_bytes());self.assertEqual(loaded.data,d.data);self.assertFalse(loaded.refresh_button.isEnabled())
        QTest.mouseClick(loaded.locate_button,Qt.LeftButton);self.assertIn('已核對',loaded.status.text())
        with patch('template_ai.diagnostic_dialog.QFileDialog.getOpenFileName',return_value=(str(path),'')),patch.object(DiagnosticReportDialog,'exec',autospec=True) as entry:open_saved_report(self.w)
        self.assertEqual(entry.call_count,1)
    def test_gui_stale_during_save_dialog_refuses_publication_and_can_refresh(self):
        d=self.dialog();path=self.root/'stale.zip'
        def change(*args,**kwargs):self.w.people.item(0,0).setText('Changed Example');return str(path),''
        with patch('template_ai.diagnostic_dialog.QFileDialog.getSaveFileName',side_effect=change):QTest.mouseClick(d.save_button,Qt.LeftButton)
        self.assertFalse(path.exists());self.assertIn('異動',d.status.text());QTest.mouseClick(d.refresh_button,Qt.LeftButton);fixture.pump_until(lambda:not d.running);self.assertIsNotNone(d.raw)
    def test_gui_worker_start_encode_and_read_failures_restore_controls(self):
        with patch.object(self.w.pool,'start',side_effect=RuntimeError('synthetic start failure')):d=self.dialog()
        self.assertTrue(d.refresh_button.isEnabled());self.assertFalse(d.save_button.isEnabled())
        with patch('template_ai.diagnostic_dialog.build_bundle',side_effect=RuntimeError('synthetic encoding failure')):
            QTest.mouseClick(d.refresh_button,Qt.LeftButton);fixture.pump_until(lambda:not d.running)
        self.assertIn('封裝失敗',d.status.text());self.assertTrue(d.refresh_button.isEnabled());self.assertFalse(d.save_button.isEnabled())
        QTest.mouseClick(d.refresh_button,Qt.LeftButton);fixture.pump_until(lambda:not d.running);self.assertIsNotNone(d.raw);self.assertFalse(self.w.busy)
    def test_gui_original_entry_points_training_template_and_candidate(self):
        self.w.people.item(0,0).setText('X'*200);self.candidate();d=self.dialog('candidate');self.assertEqual(d.data['status'],'BLOCKED')
        self.w.template=self.t;d=self.dialog('template');self.assertEqual(d.data['stage'],'TEMPLATE_GENERATION');self.w.template=None
        _,work=source_work(self.w.library,self.root,visual=False);d=self.dialog('training',work_id=work['id']);self.assertEqual(d.data['stage'],'DATA_PROCESSING')
        from template_ai.training_quality_dialog import TrainingQualityDialog
        q=TrainingQualityDialog(self.w);self.addCleanup(q.deleteLater);q.table.selectRow(0)
        with patch.object(DiagnosticReportDialog,'exec',autospec=True) as run:QTest.mouseClick(q.report_button,Qt.LeftButton)
        self.assertEqual(run.call_count,1)
        with patch.object(DiagnosticReportDialog,'exec',autospec=True) as run:self.w.diagnostic_report('input')
        self.assertEqual(run.call_count,1)
    def test_missing_model_or_source_does_not_prevent_safe_text_report(self):
        d=self.dialog('candidate');self.assertIsNotNone(d.raw);self.assertEqual(d.data['model_quality'],'NOT_VERIFIED')
        self.assertFalse(self.w.export_button.isEnabled());self.assertIn('NO_CANDIDATE',[r['code'] for r in d.data['issues']])

    def test_saved_evaluation_metrics_share_same_denominators_but_no_model_pass(self):
        import test_quality_operations as q
        store=q.TrainingStore(self.w.library);source,work=source_work(self.w.library,self.root)
        q.confirmed(store,work);sample=q.admitted(store,work);dataset=q.frozen(store,[sample],'HOLDOUT')
        versions={k:'FORBIDDEN_SYNTHETIC_VERSION_'+k for k in q.VERSIONS}
        plan=q.evaluation_plan(store,dataset['id'],versions,[]);e=q.save_evaluation(store,plan,'Synthetic Reviewer',True)
        d=self.dialog('evaluation',work_id=e['id']);c=d.data['classification']
        self.assertEqual(c['gold_count'],4);self.assertEqual(c['predicted_count'],0);self.assertEqual(c['metrics'],e['metrics'])
        self.assertEqual(c['gate'],'EVIDENCE_INSUFFICIENT');self.assertEqual(d.data['model_quality'],'NOT_VERIFIED')
        for value in list(versions.values())+[dataset['id'],sample['id'],e['id']]:self.assertNotIn(value.encode(),d.raw)
        panel=q.EvaluationPanel(self.w);self.addCleanup(panel.deleteLater);panel.right.setCurrentIndex(panel.right.findData(e['id']))
        with patch.object(DiagnosticReportDialog,'exec',autospec=True) as run:panel.report()
        self.assertEqual(run.call_count,1)
        store.transition_sample(store.sample_transition_plan(sample['id'],'QUARANTINE'),'Synthetic Reviewer','synthetic changed context',True)
        with self.assertRaises(ValueError):d.snapshot.check(self.w)

    def test_source_and_free_note_privacy_all_zip_entries(self):
        source,work=source_work(self.w.library,self.root,'FORBIDDEN_SYNTHETIC_PATH.svg',visual=False)
        p=copy.deepcopy(work['payload']);p['private_note']='FORBIDDEN_SYNTHETIC_NOTE';work=self.w.library.save_artwork(work['id'],p,work['revision'])
        s=make_snapshot(self.w,'training',work['id']);raw=build_bundle(s.data)
        for value in [source['id'],source['hash'],work['id'],str(self.root),'FORBIDDEN_SYNTHETIC_PATH','FORBIDDEN_SYNTHETIC_NOTE']:
            self.assertNotIn(value.encode(),raw)

    def test_changed_font_since_generation_is_stale_without_mutating_candidate(self):
        c=self.candidate();c.template.slots[0].font_asset={'path':str(self.root/'missing-font')}
        before=copy.deepcopy(c);s=make_snapshot(self.w,'candidate')
        self.assertEqual(s.data['status'],'STALE_RESULT');self.assertIn('DEPENDENCY_CHANGED',[r['code'] for r in s.data['issues']]);self.assertEqual(c,before)

    def test_large_library_scope_and_bad_source_schema_fail_truthfully_recover(self):
        with patch('template_ai.diagnostic_snapshot.selected_templates',side_effect=ValueError('scope over budget')):d=self.dialog()
        self.assertTrue(d.refresh_button.isEnabled());self.assertIsNone(d.raw)
        QTest.mouseClick(d.refresh_button,Qt.LeftButton);fixture.pump_until(lambda:not d.running);self.assertIsNotNone(d.raw)

    def test_startup_cleans_expired_private_locator_without_deleting_saved_report(self):
        self.w.people.item(0,0).setText('');s=make_snapshot(self.w,'input');path=self.write(s);store=LocatorStore(self.w.library)
        index=store.root/(s.data['report_id']+'.json');value=json.loads(index.read_text());value['expires']=time.time()-1;index.write_text(json.dumps(value))
        reopened=type(self.w)(self.w.library.root);self.addCleanup(reopened.library.db.close)
        self.assertFalse(index.exists());self.assertTrue(path.exists());self.assertEqual(read_bundle(path.read_bytes()),s.data)

    def test_real_worker_report_records_completed_and_failed_candidates_without_fake_success(self):
        self.w.library.publish(fixture.demo_template());d=LayoutSessionDialog(self.w);self.addCleanup(d.deleteLater);d.show();calls=[]
        def actual(*args,**kwargs):
            calls.append(1)
            if len(calls)==2:raise RuntimeError('FORBIDDEN_SYNTHETIC_WORKER_ERROR')
            return generate(*args,**kwargs)
        with patch('template_ai.layout_session.generate',side_effect=actual):
            QTest.mouseClick(d.start_button,Qt.LeftButton);fixture.pump_until(lambda:not d.running)
        self.assertEqual(len(d.rows),2);report=self.dialog('session',session=d);p=report.data['progress']
        self.assertEqual((p['total'],p['checked'],p['calculated'],p['failed'],p['unstarted']),(2,2,1,1,0))
        self.assertIn('WORKER_FAILED',[i['code'] for i in report.data['issues']]);self.assertNotIn(b'FORBIDDEN_SYNTHETIC_WORKER_ERROR',report.raw)
        self.assertFalse(self.w.export_button.isEnabled());self.assertTrue(d.start_button.isEnabled())

