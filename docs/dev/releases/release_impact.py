"""Conservative executable release scope; unknown edges never mean no tests."""
import argparse
import ast
from collections import defaultdict, deque
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
FLOOR = {'test_frozen_launch', 'test_release_authorization', 'test_release_download',
         'test_windows_release_safety', 'test_bundled_inkscape', 'test_bundled_release_guard',
         'test_inkscape_cache_identity', 'test_offline_support'}
CRITICAL = ('storage', 'design_', 'learning', 'semantic', 'runtime_', 'input_', 'render',
            'source_', 'font', 'confirm', 'export', 'output', 'logo', 'identity', 'inkscape')


def snapshot(root, ref):
    names = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', ref], cwd=root, text=True).splitlines()
    selected = [p for p in names if p.endswith('.py') and
                (p == 'app.py' or p.startswith(('template_ai/', 'tests/')))]
    return {p: subprocess.check_output(['git', 'show', ref+':'+p], cwd=root).decode('utf-8-sig') for p in selected}


def dependency_graph(files, contracts=None):
    modules = {p: p[:-3].replace('/', '.') for p in files}
    reverse = defaultdict(set)
    unknown = []
    for path, text in files.items():
        caller = modules[path]
        try:
            tree = ast.parse(text, filename=path)
        except SyntaxError:
            unknown.append(path+':syntax')
            continue
        for node in ast.walk(tree):
            imports = []
            if isinstance(node, ast.Import):
                imports = [n.name for n in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    package = caller.rsplit('.', 1)[0].split('.')
                    prefix = '.'.join(package[:len(package)-node.level+1])
                    base = '.'.join(x for x in (prefix, node.module) if x)
                else:
                    base = node.module or ''
                imports = [base]+[base+'.'+n.name for n in node.names]
            elif isinstance(node, ast.Call):
                name = (node.func.id if isinstance(node.func, ast.Name) else
                        node.func.attr if isinstance(node.func, ast.Attribute) else '')
                if name in {'import_module', '__import__'}:
                    if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                        imports = [node.args[0].value]
                    else:
                        contract = (contracts or {}).get(path, {})
                        if contract.get('sha256') == hashlib.sha256(text.encode()).hexdigest():
                            imports = contract['imports']
                        else:
                            unknown.append(path+':dynamic_import')
            for dependency in imports:
                reverse[dependency].add(caller)
                reverse[dependency+'.__init__'].add(caller)
                # Parent-package side effects must stay reachable.
                pieces = dependency.split('.')
                for index in range(1, len(pieces)):
                    reverse['.'.join(pieces[:index])+'.__init__'].add(caller)
    return reverse, unknown


def plan_changes(changed, base_files, head_files, windows_modules, *, force_build=False, contracts=None):
    changed = sorted(set(changed))
    known = set(windows_modules)
    if not FLOOR <= known:
        raise ValueError('The approved Windows scope is missing a mandatory floor module')
    reverse = defaultdict(set)
    unknown = []
    for files in (base_files, head_files):
        edges, problems = dependency_graph(files, contracts)
        unknown += problems
        for dependency, callers in edges.items():
            reverse[dependency].update(callers)
    affected = {p[:-3].replace('/', '.') for p in changed if p.endswith('.py')}
    queue = deque(affected)
    while queue:
        for caller in reverse[queue.popleft()]:
            if caller not in affected:
                affected.add(caller)
                queue.append(caller)
    documentation = bool(changed) and all(p.endswith(('.md', '.png', '.jpg')) and
                        not p.startswith(('template_ai/', '.github/', 'tests/')) for p in changed)
    reasons = []
    product = [p for p in changed if p == 'app.py' or p.startswith('template_ai/')]
    if not changed:
        reasons.append('NO_CHANGE_STILL_REQUIRES_EXPLICIT_BUILD_IF_REQUESTED')
    for p in changed:
        if p == 'app.py' or (p.startswith('template_ai/') and any(x in Path(p).stem for x in CRITICAL)):
            reasons.append('CRITICAL_PRODUCT_CONTRACT:'+p)
        elif p.startswith(('.github/', 'tools/', 'docs/dev/releases/')) and not p.endswith(('.md', '.png', '.json')):
            reasons.append('BUILD_OR_EXECUTABLE_TOOLING:'+p)
        elif p.startswith('.github/') or p.startswith('requirements') or p.startswith('tests/'):
            reasons.append('BUILD_CONFIG_DEPENDENCY_OR_TEST_CHANGE:'+p)
        elif not (p.startswith(('template_ai/', 'docs/')) or p in {'README.md', 'AGENTS.md'}):
            reasons.append('UNCLASSIFIED_PATH:'+p)
    if product and unknown:
        reasons.append('UNKNOWN_DYNAMIC_OR_UNPARSEABLE_PRODUCT_GRAPH')
    if product and any(p not in base_files or p not in head_files for p in product):
        reasons.append('ADDED_REMOVED_OR_RENAMED_PRODUCT_MODULE')
    source_tests = sorted(x.removeprefix('tests.') for x in affected if x.startswith('tests.test_'))
    selected = FLOOR | (set(source_tests) & known)
    if product and not source_tests:
        reasons.append('NO_PROVEN_TEST_DEPENDENCY')
    if reasons or force_build and documentation:
        selected = known
        tier = 'FULL_WINDOWS'
    elif documentation:
        selected = set()
        tier = 'DOCUMENTATION_NO_EXE'
    elif product:
        tier = 'IMPACTED_PLUS_FLOOR'
    else:
        # Nothing confidently classified as documentation/product: conservative.
        selected = known
        tier = 'FULL_WINDOWS'
        reasons.append('UNKNOWN_CHANGE_CATEGORY')
    return dict(schema_version=1, tier=tier, changed_paths=changed, reasons=sorted(set(reasons)),
                selected_windows_modules=sorted(selected), mandatory_floor=sorted(FLOOR),
                affected_source_modules=source_tests, unknown_graph_edges=sorted(set(unknown)),
                graph_policy='REVERSE_REACHABILITY_UNION_OF_BASE_AND_HEAD',
                source_qualification='CURRENT_FULL_SOURCE_GATE_UNCHANGED',
                required_actual_exe_checks=21 if selected else 0,
                required_engine_scenarios=5 if selected else 0,
                public_download_verification_required=bool(selected))


def make_plan(base, output, *, root=ROOT, force_build=False):
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    if base == 'auto':
        state = json.loads((root/'docs/dev/STATE.json').read_text())
        base = 'v'+state['windows_release']['version']
    base = subprocess.check_output(['git', 'rev-parse', '--verify', base+'^{commit}'], cwd=root, text=True).strip()
    subprocess.run(['git', 'merge-base', '--is-ancestor', base, head], cwd=root, check=True)
    changed = subprocess.check_output(['git', 'diff', '--name-only', '--no-renames', base, head], cwd=root, text=True).splitlines()
    scope = json.loads((root/'.github/windows-release-test-scope.json').read_text())
    contracts = json.loads((root/'.github/release-impact-contracts.json').read_text())['dynamic_imports']
    result = plan_changes(changed, snapshot(root, base), snapshot(root, head), scope['modules'], force_build=force_build, contracts=contracts)
    result.update(base_commit=base, source_commit=head)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--force-build', action='store_true')
    args = parser.parse_args()
    result = make_plan(args.base, args.output, force_build=args.force_build)
    print(json.dumps(dict(tier=result['tier'], windows_modules=len(result['selected_windows_modules']),
                         reasons=result['reasons']), ensure_ascii=False))
