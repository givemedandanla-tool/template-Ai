"""Bounded independent postconditions on real core services and authored fixtures.

Not an alternative layout engine and not a real-corpus qualification runner.
Uses production services; no patched window, solver or qualification boundary.
"""
from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import unittest

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT),str(ROOT/'tests'),str(ROOT/'tools')]
from dev_common import manifest,manifest_digest
from template_ai.design_capacity import fit_capacity,LocalCapacityCalibration
from template_ai.design_synthesis import synthesize,input_facts
from template_ai.training_store import digest
import test_design_session as sessions_fixture
import test_design_synthesis as synthesis_fixture


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    folder=args.output
    folder.mkdir(exist_ok=False)
    before=manifest_digest(manifest(ROOT,code_only=True));started=time.monotonic();results=[]

    def probe(identity,action):
        begin=time.monotonic()
        try:
            details=action();status='PASS'
        except Exception as error:
            import traceback
            details=dict(error_type=type(error).__name__,traceback=traceback.format_exc());status='FAIL'
        results.append(dict(id=identity,status=status,seconds=time.monotonic()-begin,details=details))
        (folder/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')

    class SessionCase(unittest.TestCase):pass
    sessions_fixture.DesignSessionTests.setUpClass.__func__(SessionCase)
    case=SessionCase();sessions_fixture.DesignSessionTests.setUp(case)
    try:
        sessions=case.sessions;identity=case.session['id']
        sessions.solve(identity,case.session['revision'])
        _,_,candidate=sessions.checked_result(identity)
        initial=sessions.current(identity)
        original_input=deepcopy(initial['input_graph'])
        by_kind={item.slot.kind:item for item in candidate.items}

        def relative_protection():
            first,second=by_kind['name'].slot.rect,by_kind['title'].slot.rect
            relations=[]
            if first.y+first.h<=second.y+1e-8:relations.append('ABOVE')
            if second.y+second.h<=first.y+1e-8:relations.append('BELOW')
            if first.x+first.w<=second.x+1e-8:relations.append('LEFT_OF')
            if second.x+second.w<=first.x+1e-8:relations.append('RIGHT_OF')
            assert relations,'Fixture has no independently observable protected separation.'
            facts={row['kind']:row['render_id'] for row in input_facts(case.graph)}
            row=sessions.current(identity)
            sessions.set_relation(identity,row['revision'],'protected-pair-'+identity,
                                  facts['phone'],'BELOW',facts['email'])
            row=sessions.current(identity);answer=sessions.solve(identity,row['revision'])
            assert answer['status']=='FEASIBLE_PREVIEW'
            _,_,new=sessions.checked_result(identity);items={i.slot.kind:i for i in new.items}
            a,b=items['name'].slot.rect,items['title'].slot.rect
            checks=dict(ABOVE=a.y+a.h<=b.y+1e-8,BELOW=b.y+b.h<=a.y+1e-8,
                        LEFT_OF=a.x+a.w<=b.x+1e-8,RIGHT_OF=b.x+b.w<=a.x+1e-8)
            assert all(checks[r] for r in relations)
            phone,email=items['phone'].slot.rect,items['email'].slot.rect
            assert phone.y+1e-8>=email.y+email.h
            assert sessions.current(identity)['input_graph']==original_input
            assert new.template.family_id==candidate.template.family_id
            return dict(protected_relations=relations,all_retained=True,requested_relation='PHONE_BELOW_EMAIL',
                        input_graph_unchanged=True,same_family=True)
        probe('PROBE-RELATIVE-PROTECTED-PAIR',relative_protection)

        def protected_role_command():
            facts={r['kind']:r['render_id'] for r in input_facts(case.graph)}
            row=sessions.current(identity)
            try:sessions.set_relation(identity,row['revision'],'reject-name-'+identity,facts['name'],'BELOW',facts['phone'])
            except ValueError:pass
            else:raise AssertionError('Protected name role was movable by contact policy.')
            assert sessions.current(identity)==row
            return dict(rejected=True,original_session_unchanged=True)
        probe('PROBE-PROTECTED-ROLE-NEGATIVE',protected_role_command)

        def legacy_calibration():
            service=LocalCapacityCalibration(case.library)
            context=dict(family_id=candidate.template.family_id,font_signature='authored-legacy',field_count=4,width_mm=90.,height_mm=54.)
            policy=dict(version='authored-legacy-record',minimum_independent_groups=5,
                        minimum_success_lower_bound=.8,alpha=.05,bin_widths=[20.,10.])
            records=[dict(id='case-'+str(i),lineage_group='independent-'+str(i),role='VALIDATION',
                          context=context,demand=[2.,2.],layout_pass=True,qualified_style=True,
                          evidence_refs=['Authored historical calibration fixture']) for i in range(30)]
            artifact=fit_capacity(records,policy);artifact['version']='conditional-capacity-calibration-1'
            for cell in artifact['cells']:
                for key in ('negative_joint_support','positive_case_ids','negative_case_ids'):cell.pop(key,None)
            artifact['digest']=digest({k:v for k,v in artifact.items() if k!='digest'})
            with service.store.transaction():
                saved=service.store._write('DESIGN_CAPACITY','legacy-'+identity,
                    dict(model_id=case.model['id'],weights_digest=case.model['weights_digest'],
                         manifest_digest=case.model['manifest_digest'],artifact=artifact),0,'authored_legacy_fixture')
            try:service.checked(saved['id'])
            except ValueError as error:assert 'recalibration' in str(error)
            else:raise AssertionError('Legacy calibration silently retained current validity.')
            assert service.store.get('DESIGN_CAPACITY',saved['id'])==saved
            current=sessions.current(identity);sessions.confirm(identity,current['revision'],'Synthetic author')
            output=case.root/('legacy-cache-preview-'+identity+'.png')
            result=sessions.export(identity,output)
            assert output.is_file() and not result['production']
            assert result['sha256']==hashlib.sha256(output.read_bytes()).hexdigest()
            return dict(old_cache_retained=True,recalibration_required=True,preview_still_works=True,
                        exported_bytes_verified=True,no_production_qualification_claim=True)
        probe('PROBE-LEGACY-CALIBRATION-AND-PREVIEW',legacy_calibration)
    finally:
        case.doCleanups();SessionCase.temp.cleanup()

    class SynthesisCase(unittest.TestCase):pass
    authored=SynthesisCase();synthesis_fixture.DesignSynthesisTests.setUp(authored)
    try:
        def no_old_background():
            result=synthesize(authored.profile,authored.graph,90,54,authored.policy)
            assert result['status']=='FEASIBLE_PREVIEW'
            candidate=result['candidates'][0]['candidate']
            assert candidate.template.background is None
            expected=['0123456789','0987654321','Alex Example']
            assert sorted(item.text for item in candidate.items)==expected
            assert all('Person ' not in item.text and 'Number ' not in item.text for item in candidate.items)
            return dict(source_page_not_copied_as_background=True,exact_new_values=True,
                        old_authored_training_text_not_in_dynamic_output=True,
                        scope='Authored learned-core fixture;not arbitrary private raster detection.')
        probe('PROBE-NEW-VALUES-NO-SOURCE-PAGE-BACKGROUND',no_old_background)
    finally:authored.doCleanups()
    unchanged=manifest_digest(manifest(ROOT,code_only=True))==before
    summary=dict(status='PASS' if unchanged and all(x['status']=='PASS' for x in results) else 'FAIL',
        source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        code_manifest_sha256=before,code_unchanged=unchanged,probes=len(results),
        passed=sum(x['status']=='PASS' for x in results),seconds=time.monotonic()-started,
        driver_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        qualification='LOCAL_SYNTHETIC_MECHANISM_ONLY_NOT_REAL_CORPUS_OR_REMOTE_PUBLICATION')
    (folder/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(summary));return 0 if summary['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
