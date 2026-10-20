"""Real input/clipboard/pointer captures using authored local fixture sources."""
import argparse
import os
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT)]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--folder',type=Path,required=True);args=parser.parse_args()
    args.folder.mkdir(parents=True,exist_ok=True);os.environ['TEMPLATE_AI_INPUT_CAPTURE_DIR']=str(args.folder)
    from test_input_learning_integration import InputLearningIntegrationTests
    suite=unittest.TestSuite(InputLearningIntegrationTests(name) for name in (
        'test_real_new_input_modal_keeps_data_and_does_not_require_main_candidates',
        'test_real_clipboard_over_limit_keeps_all_text_and_blocks_adoption_without_loss',
        'test_actual_pointer_drag_creates_relation_and_preserves_unaffected_structure',
        'test_real_learned_input_logo_library_keeps_size_and_uses_main_background_services',
        'test_main_legacy_table_enters_real_learned_preview_and_exports_exact_confirmed_data'))
    result=unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful():return 1
    expected=['real-data-entry','long-paste-retained','dragged-preview','legacy-to-learned-preview','main-preview','logo-library']
    if any(not (args.folder/('input-integration-'+name+'.png')).is_file() for name in expected):return 1
    print('Actual input/clipboard/drag/logo/main-preview captures:6 verified');return 0

if __name__=='__main__':raise SystemExit(main())
