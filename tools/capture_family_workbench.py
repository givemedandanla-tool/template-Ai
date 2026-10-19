"""Capture actual native family tools using owned fixtures only; no user library."""
import argparse
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tests'))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--folder',type=Path,required=True);args=parser.parse_args()
    args.folder.mkdir(parents=True,exist_ok=True)
    from PySide6.QtWidgets import QApplication
    from test_family_workbench import FamilyWorkbenchTests
    from test_family_source_forms import FamilySourceFormTests
    from template_ai.family_compare import FamilyComparisonDialog
    from template_ai.family_workspace import reference
    app=QApplication.instance() or QApplication([])
    def capture(widget,name):
        app.processEvents();assert widget.grab().save(str(args.folder/name)),name
    FamilyWorkbenchTests.setUpClass()
    case=FamilyWorkbenchTests('test_saved_case_runs_in_worker_and_renders_actual_preview')
    try:
        case.setUp();pane=case.pane
        pane.apply_operation(case.reorder());pane.details.setCurrentIndex(0)
        capture(case.dialog,'family-workbench-overview.png')
        for tab,name in [(1,'compatibility'),(3,'variants'),(4,'joint-style')]:
            pane.details.setCurrentIndex(tab);capture(case.dialog,'family-workbench-'+name+'.png')
        case.test_saved_case_runs_in_worker_and_renders_actual_preview()
        pane.details.setCurrentIndex(6);capture(case.dialog,'family-workbench-case.png')
        candidate=pane.rules.create_candidate(pane.draft['id'],pane.draft['revision'],'OWNED_CAPTURE_AUTHOR',True)
        new_ref=reference(candidate,candidate['artifact']['profile_model']['families'][0])
        comparison=FamilyComparisonDialog(case.parent,[pane.ref,new_ref],case.dialog)
        try:
            comparison.show();capture(comparison,'family-workbench-source-comparison.png')
        finally:comparison.close()
        pane.details.setCurrentIndex(7);pane.show_impact();capture(case.dialog,'family-workbench-impact.png')
    finally:
        case.doCleanups();FamilyWorkbenchTests.tearDownClass()
    source=FamilySourceFormTests('test_actual_composite_form_preserves_complete_runs_and_two_local_faces')
    try:
        source.setUp();source.add_runs();source.dialog.prepare();source.dialog.show()
        capture(source.dialog,'family-workbench-composite-source.png')
    finally:source.doCleanups()
    from tools.benchmark_family_index import benchmark
    import json
    (args.folder/'family-workbench-index-benchmark.json').write_text(json.dumps(benchmark(),indent=2)+'\n')
    print('8 actual native family screenshots and3000metadata descriptors;owned sources;no real-corpus/device/prepress qualification')


if __name__=='__main__':main()
