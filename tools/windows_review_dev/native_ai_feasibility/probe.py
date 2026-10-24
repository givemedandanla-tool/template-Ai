"""Synthetic-only native-AI acceptance probe. Exit 2 means NOT integration-ready.

Never accepts user documents. All inputs are constructed in a new output folder.
Code runs in the Inkscape Python subprocess; wheel imports do not install them.
"""
import argparse
from collections import Counter
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile

NATIVE = b'''%!PS-Adobe-3.0
%%Creator: Review synthetic fixture
%%BoundingBox: 0 0 180 90
%AI5_RulerUnits: 2
%AI3_TemplateBox: 0 0 180 90
%%EndComments
%%BeginProlog
%%EndProlog
%%BeginSetup
%%EndSetup
0 1 1 0 k
10 10 m
170 10 L
170 80 L
10 80 L
10 10 L
f
%%PageTrailer
%%Trailer
%%EOF
'''
TEXT = b'''0 To
1 0 0 1 20 30 0 Tp
/Helvetica 12 Tf
0 Tr
(SYNTHETIC NATIVE TEXT) Tx
TO
'''
CASES = ('plain_geometry', 'pdf_zlib_geometry', 'pdf_zstd_geometry',
         'plain_text', 'pdf_zlib_text', 'corrupt_native', 'no_private_data')
NOTICE = ('This is an Adobe Illustrator File that was saved without PDF Content. '
          'Re-saved from Adobe Illustrator with Create PDF Compatible File option turned on.')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def validate_source(root, lock):
    raw = (root / 'upstream.tar.gz').read_bytes()
    if digest(raw) != lock['archive_sha256']:
        raise ValueError('Archive hash mismatch')
    expected = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as archive:
        for entry in archive.getmembers():
            name = Path(*Path(entry.name).parts[1:])
            if entry.isfile() and name.parts[0] == 'inkai' and name.suffix == '.py':
                expected[name.as_posix()] = digest(archive.extractfile(entry).read())
    actual = {p.relative_to(root / 'source').as_posix(): digest(p.read_bytes())
              for p in (root / 'source/inkai').rglob('*.py')}
    if actual != expected:
        raise ValueError('Upstream Python source differs from fixed archive')
    for entry in lock['dependencies']:
        if digest((root / 'wheels' / entry['wheel']).read_bytes()) != entry['sha256']:
            raise ValueError('Wheel hash mismatch')
    return len(expected)


def child(args, lock):
    root = Path(args.runtime).resolve()
    sys.path[:0] = [str(root / 'source'), str(Path(args.inkscape) / 'share/inkscape/extensions'),
                   *[str(root / 'wheels' / item['wheel']) for item in lock['dependencies']]]
    # No network is needed for decoding; deny Python socket operations in child.
    def guard(event, values):
        if event in ('socket.connect', 'socket.connect_ex', 'socket.getaddrinfo', 'socket.bind'):
            raise PermissionError('Native AI feasibility process is offline')
    sys.addaudithook(guard)
    import warnings
    import zlib
    import zstandard
    import inkai
    import inkex
    import pypdf
    import pyparsing
    from lxml import etree
    from pypdf import PdfWriter, PdfReader
    from pypdf.generic import DictionaryObject as D, NameObject as N, NumberObject as I, DecodedStreamObject
    folder = Path(args.output)
    case = args.child
    payload = NATIVE.replace(b'%%PageTrailer', TEXT + b'%%PageTrailer') if case.endswith('_text') else NATIVE
    path = folder / (case + '.ai')
    if case == 'corrupt_native':
        path.write_bytes(b'%!PS-Adobe-3.0\nBROKEN SYNTHETIC INPUT')
    elif case.startswith('pdf_') or case == 'no_private_data':
        writer = PdfWriter(); page = writer.add_blank_page(width=180, height=90)
        font = writer._add_object(D({N('/Type'):N('/Font'),N('/Subtype'):N('/Type1'),N('/BaseFont'):N('/Helvetica')}))
        page[N('/Resources')] = D({N('/Font'):D({N('/F1'):font})})
        visible = DecodedStreamObject()
        lines = [NOTICE[i:i+32] for i in range(0, len(NOTICE), 32)]
        visible.set_data(('BT /F1 7 Tf 4 80 Td 10 TL '+''.join('('+line+') Tj T* ' for line in lines)+'ET').encode('ascii'))
        page[N('/Contents')] = writer._add_object(visible)
        if case != 'no_private_data':
            stream = DecodedStreamObject()
            stream.set_data(b'%AI24_ZStandard_Data'+zstandard.compress(payload) if 'zstd' in case
                            else b'%AI12_CompressedData'+zlib.compress(payload))
            private = D({N('/NumBlock'):I(1),N('/AIPrivateData1'):writer._add_object(stream)})
            page[N('/PieceInfo')] = D({N('/Illustrator'):D({N('/Private'):private})})
        with path.open('xb') as target: writer.write(target)
        assert 'savedwithoutPDFContent' in ''.join(PdfReader(str(path)).pages[0].extract_text().split())
    else:
        path.write_bytes(payload)
    before = digest(path.read_bytes())
    caught = []; error = None; svg = b''
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        try: svg = inkai.to_svg(str(path))
        except Exception as exc: error = type(exc).__name__
    item = dict(case=case,converted=bool(svg),error_type=error,source_unchanged=digest(path.read_bytes())==before,
                warning_count=len(caught),synthetic_input=True,private_input_used=False,
                runtime={'python':sys.version.split()[0], 'inkex':inkex.__version__, 'pypdf':pypdf.__version__,
                         'pyparsing':pyparsing.__version__, 'zstandard':zstandard.__version__})
    if svg:
        (folder / (case + '.svg')).write_bytes(svg)
        document = etree.fromstring(svg)
        paths = document.xpath('//*[local-name()="path"]')
        texts = document.xpath('//*[local-name()="text"]')
        item.update(path_count=len(paths),text_elements=len(texts),text_retained=b'SYNTHETIC NATIVE TEXT' in svg,
                    size_correct=document.get('width')=='180.0pt' and document.get('height')=='90.0pt',
                    rectangle_correct=len(paths)==1 and paths[0].get('d')=='M 10 80 L 170 80 L 170 10 L 10 10 L 10 80 Z'
                    and 'fill:#ff0000' in paths[0].get('style',''),notice_not_used=NOTICE.encode() not in svg)
    if case in ('corrupt_native', 'no_private_data'):
        item['acceptance_pass'] = error is not None and not svg and item['source_unchanged']
    else:
        item['acceptance_pass'] = bool(svg) and item['rectangle_correct'] and item['size_correct'] and item['source_unchanged'] and item['notice_not_used']
        if case.endswith('_text'):
            item['acceptance_pass'] = item['acceptance_pass'] and item['text_retained']
    print(json.dumps(item))


def main(args, lock):
    root = Path(args.runtime).resolve()
    files = validate_source(root, lock)
    output = Path(args.output).resolve(); output.mkdir(parents=True, exist_ok=False)
    python = Path(args.inkscape) / 'bin/python.exe'
    results=[]
    for case in CASES:
        process = subprocess.run([str(python), '-I', str(Path(__file__).resolve()), '--runtime', str(root),
                       '--inkscape', args.inkscape, '--output', str(output), '--child', case],
                       capture_output=True, timeout=45, creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        (output/(case+'.stdout.local.log')).write_bytes(process.stdout)
        (output/(case+'.stderr.local.log')).write_bytes(process.stderr)
        if process.returncode:
            raise RuntimeError('Synthetic probe harness failed; inspect local log: '+case)
        row=json.loads(process.stdout.decode('utf-8').splitlines()[-1]); results.append(row)
        print(json.dumps(row),flush=True)
    report=dict(upstream_commit=lock['commit'],platform='Windows',cases=results,
                acceptance_passed=sum(r['acceptance_pass'] for r in results),acceptance_failed=sum(not r['acceptance_pass'] for r in results),
                integration_ready=all(r['acceptance_pass'] for r in results),upstream_python_files_verified=files,
                private_files_used=False,fonts_uploaded=False,upstream_or_installed_files_modified=False,
                isolation='Inkscape bundled python -I; pinned source and pure-Python wheels; Python socket access denied; one bounded subprocess per case')
    (output/'summary.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return 0 if report['integration_ready'] else 2


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime',required=True)
    parser.add_argument('--inkscape',required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--child',choices=CASES)
    args=parser.parse_args()
    lock=json.loads(Path(__file__).with_name('upstream-lock.json').read_text(encoding='utf-8'))
    if args.child:child(args,lock)
    else:raise SystemExit(main(args,lock))
