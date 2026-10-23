"""Build-only policy: omit public dependency test data before EXE acceptance."""
import hashlib
import json
from pathlib import Path, PurePosixPath

DEPENDENCY_ROOTS = frozenset({'sklearn', 'numpy', 'scipy'})


def filter_payload(entries, report):
    """Preserve runtime assets; the original final inventory remains authoritative."""
    kept, removed = [], []
    for entry in entries:
        if len(entry) != 3:
            raise ValueError('Unexpected PyInstaller data TOC shape')
        destination = PurePosixPath(str(entry[0]).replace('\\', '/'))
        if (destination.parts and destination.parts[0] in DEPENDENCY_ROOTS
                and 'tests' in destination.parts[1:]):
            removed.append(destination.as_posix())
        else:
            kept.append(entry)
    if not removed:
        raise ValueError('Pinned dependency test-data policy matched no files; inspect hook changes')
    record = dict(status='PASS', policy='OMIT_KNOWN_PUBLIC_DEPENDENCY_TEST_DATA_BEFORE_FREEZE',
                  policy_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  input_files=len(entries), kept_files=len(kept), removed_files=len(removed),
                  removed_relative_paths=sorted(removed),
                  final_inventory_guard='UNCHANGED', runtime_acceptance='REQUIRED_AFTER_THIS_FILTER')
    Path(report).parent.mkdir(parents=True, exist_ok=True)
    Path(report).write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return kept
