"""Download pinned public code to a NEW isolated folder; never install packages."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import urllib.request


def prepare(output):
    lock = json.loads(Path(__file__).with_name('upstream-lock.json').read_text(encoding='utf-8'))
    root = Path(output).resolve()
    root.mkdir(parents=True, exist_ok=False)
    with urllib.request.urlopen(lock['archive_url'], timeout=90) as response:
        raw = response.read(100_000_001)
    if len(raw) > 100_000_000 or hashlib.sha256(raw).hexdigest() != lock['archive_sha256']:
        raise ValueError('Pinned upstream archive mismatch; keep environment unqualified')
    (root / 'upstream.tar.gz').write_bytes(raw)
    source = root / 'source'
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as archive:
        for member in archive.getmembers():
            target = (source / Path(*Path(member.name).parts[1:])).resolve()
            if not target.is_relative_to(source) or member.issym() or member.islnk() or member.size > 50_000_000:
                raise ValueError('Unsafe archive entry')
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.extractfile(member).read())
    subprocess.run([sys.executable, '-m', 'pip', 'download', '--only-binary=:all:', '--no-deps',
                    '--dest', str(root / 'wheels'), *[x['requirement'] for x in lock['dependencies']]],
                   check=True, timeout=180)
    for entry in lock['dependencies']:
        assert hashlib.sha256((root / 'wheels' / entry['wheel']).read_bytes()).hexdigest() == entry['sha256']
    print(json.dumps({'prepared': True, 'commit': lock['commit'], 'existing_installations_modified': False}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    prepare(parser.parse_args().output)
