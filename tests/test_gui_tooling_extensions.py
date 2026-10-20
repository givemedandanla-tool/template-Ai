"""Prevent development skills from overwriting local work or accepting altered helpers."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1] / 'docs/dev/gui_tooling'
SPEC = importlib.util.spec_from_file_location('template_ai_gui_extensions', SOURCE / 'tooling_extensions.py')
EXTENSIONS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EXTENSIONS)


class GuiToolingIntegrityTests(unittest.TestCase):
    def copied_tools(self, root):
        tools = root / 'docs/dev/gui_tooling'
        tools.mkdir(parents=True)
        manifest = json.loads((SOURCE / 'EXTENSIONS.json').read_text())
        paths = ['EXTENSIONS.json', 'SKILL.md', *manifest['agent_roles'].values(),
                 *(entry['source'] + '/SKILL.md' for entry in manifest['entries']),
                 *(source['copied_to'] for source in manifest['sources'])]
        for relative in paths:
            target = tools / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(SOURCE / relative, target)
        return tools

    def test_altered_original_screenshot_helper_rejected_before_discovery(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tools = self.copied_tools(root)
            helper = tools / 'vendor/openai-screenshot/scripts/take_screenshot.py'
            helper.write_bytes(helper.read_bytes() + b'\n# altered helper\n')
            with self.assertRaisesRegex(RuntimeError, 'integrity check failed'):
                EXTENSIONS.verify_extensions(tools)
            self.assertFalse((root / '.agents').exists())

    def test_project_skill_discovery_is_repeatable_and_does_not_overwrite_user_work(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tools = self.copied_tools(root)
            manifest = EXTENSIONS.verify_extensions(tools)
            first = EXTENSIONS.discover_skills(root, tools, manifest)
            self.assertEqual(first, EXTENSIONS.discover_skills(root, tools, manifest))
            self.assertEqual(len(first), 4)
            entry = root / first[-1]
            entry.unlink()
            entry.mkdir()
            personal = entry / 'personal.txt'
            personal.write_text('retain user work')
            with self.assertRaisesRegex(RuntimeError, 'not overwritten'):
                EXTENSIONS.discover_skills(root, tools, manifest)
            self.assertEqual(personal.read_text(), 'retain user work')

    def test_manifest_cannot_read_files_outside_tool_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tools = self.copied_tools(root)
            manifest_path = tools / 'EXTENSIONS.json'
            manifest = json.loads(manifest_path.read_text())
            manifest['sources'][0]['copied_to'] = '../outside.txt'
            manifest_path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'stay inside'):
                EXTENSIONS.verify_extensions(tools)


if __name__ == '__main__':
    unittest.main()
