"""Generate local review-tool launchers without overwriting existing files."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess


def configuration(root, inkscape=None, git=None, code=None):
    env = {'PYTHONUTF8': '1', 'PYTHONNOUSERSITE': '1'}
    search = ['${workspaceFolder}\\.venv\\Scripts', '${env:PATH}']
    if inkscape:
        env['TEMPLATE_AI_INKSCAPE'] = str(inkscape)
        search.insert(1, str(Path(inkscape).parent))
    env['PATH'] = ';'.join(search)
    settings = {
        'python.defaultInterpreterPath': '${workspaceFolder}/.venv/Scripts/python.exe',
        'python.testing.unittestEnabled': True,
        'python.testing.pytestEnabled': False,
        'python.testing.unittestArgs': ['-v', '-s', 'tests', '-p', 'test_review_*.py'],
        'python.testing.autoTestDiscoverOnSaveEnabled': False,
        'terminal.integrated.env.windows': env,
    }
    if git:
        settings['git.path'] = str(git)
    launch = {
        'name': 'Review tool: native Windows debug', 'type': 'debugpy',
        'request': 'launch', 'program': '${workspaceFolder}/review_app.py',
        'python': '${workspaceFolder}/.venv/Scripts/python.exe',
        'pythonArgs': ['-Xfrozen_modules=off'], 'cwd': '${workspaceFolder}',
        'args': ['--data-dir', '${workspaceFolder}/local-data/review-debug'],
        'console': 'integratedTerminal', 'justMyCode': True, 'subProcess': False,
        'env': env, 'preLaunchTask': 'Review: check environment',
    }
    workspace = {'folders': [{'path': '.'}], 'settings': settings,
        'extensions': {'recommendations': ['ms-python.python', 'ms-python.debugpy']},
        'launch': {'version': '0.2.0', 'configurations': [launch,
            {'name': 'Review tool: attach localhost 5678', 'type': 'debugpy',
             'request': 'attach', 'connect': {'host': '127.0.0.1', 'port': 5678},
             'justMyCode': True, 'subProcess': False}]},
        'tasks': {'version': '2.0.0', 'tasks': [
            {'label': 'Review: check environment', 'type': 'process',
             'command': '${workspaceFolder}/.venv/Scripts/python.exe',
             'args': ['tools/local_start.py', '--check'],
             'options': {'cwd': '${workspaceFolder}', 'env': env}, 'problemMatcher': []}]}}
    prefix = '@echo off\nsetlocal\nchcp 65001 >nul\ncd /d "%~dp0"\nset "PYTHONUTF8=1"\nset "PYTHONNOUSERSITE=1"\n'
    if inkscape:
        prefix += f'set "TEMPLATE_AI_INKSCAPE={inkscape}"\nset "PATH={Path(inkscape).parent};%PATH%"\n'
    check = '".venv\\Scripts\\python.exe" tools\\local_start.py --check\nif errorlevel 1 exit /b 1\n'
    files = {
        'review-dev.code-workspace': json.dumps(workspace, ensure_ascii=False, indent=2)+'\n',
        'START_REVIEW_DEV.cmd': prefix + check +
            'start "" ".venv\\Scripts\\pythonw.exe" review_app.py --data-dir "%~dp0local-data\\review-debug" %*\nexit /b %errorlevel%\n',
        'CHECK_REVIEW_DEV.cmd': prefix + check +
            '".venv\\Scripts\\python.exe" -m pip check\nexit /b %errorlevel%\n',
        'DEBUG_REVIEW_DEV.cmd': prefix + check +
            '".venv\\Scripts\\python.exe" -Xfrozen_modules=off -m debugpy --listen 127.0.0.1:5678 --wait-for-client --configure-subProcess false review_app.py --data-dir "%~dp0local-data\\review-debug" %*\nexit /b %errorlevel%\n',
        'TEST_REVIEW_DEV.cmd': prefix +
            '".venv\\Scripts\\python.exe" tools\\windows_review_dev\\run_checks.py\nexit /b %errorlevel%\n',
    }
    if code:
        files['OPEN_REVIEW_DEV.cmd'] = prefix + f'call "{code}" --new-window "%~dp0review-dev.code-workspace"\nexit /b %errorlevel%\n'
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--inkscape', type=Path)
    parser.add_argument('--git', type=Path)
    parser.add_argument('--code', type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    if not (root/'review_app.py').is_file() or not (root/'.venv/Scripts/python.exe').is_file():
        parser.error('Select the review-tool checkout and prepare .venv first. See README.md.')
    inkscape = args.inkscape or os.environ.get('TEMPLATE_AI_INKSCAPE') or shutil.which('inkscape.com') or shutil.which('inkscape')
    if not inkscape and (Path(os.environ.get('ProgramFiles', r'C:\Program Files'))/'Inkscape/bin/inkscape.com').is_file():
        inkscape = Path(os.environ.get('ProgramFiles', r'C:\Program Files'))/'Inkscape/bin/inkscape.com'
    git = args.git or shutil.which('git')
    code = args.code or (root/'.tools/vscode/bin/code.cmd' if (root/'.tools/vscode/bin/code.cmd').is_file() else shutil.which('code'))
    for name, value in [('inkscape', inkscape), ('git', git), ('code', code)]:
        if value and (not Path(value).is_file() or any(c in str(value) for c in '\n\r%"&|<>^!')):
            parser.error(f'Invalid {name} executable path')
    files = configuration(root, inkscape, git, code)
    # Validate all collisions before creating anything. Never replace the user's settings.
    conflicts = [name for name in files if (root/name).exists()]
    if conflicts:
        parser.error('Existing files preserved; choose a fresh checkout or review these files: '+', '.join(conflicts))
    if not git:
        parser.error('Git is required to keep generated machine settings out of commits; pass --git.')
    exclude = Path(subprocess.check_output([str(git), '-C', str(root), 'rev-parse', '--path-format=absolute', '--git-path', 'info/exclude'], text=True).strip())
    existing = exclude.read_text(encoding='utf-8') if exclude.exists() else ''
    patterns = ['/review-dev.code-workspace', '/*_REVIEW_DEV.cmd', '/.tools/', '/.local-dev/']
    missing = [p for p in patterns if p not in existing.splitlines()]
    if missing:
        exclude.parent.mkdir(parents=True, exist_ok=True)
        with exclude.open('a', encoding='utf-8', newline='\n') as stream:
            stream.write('\n# Local Windows review development environment\n'+'\n'.join(missing)+'\n')
    for name, text in files.items():
        with (root/name).open('x', encoding='utf-8', newline='\r\n' if name.endswith('.cmd') else '\n') as stream:
            stream.write(text)
    print(json.dumps({'generated': list(files), 'inkscape_configured': bool(inkscape), 'product_source_modified': False}))


if __name__ == '__main__':
    main()
