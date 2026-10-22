"""Resolve source-distribution gaps without reinstalling or re-auditing the engine."""
import concurrent.futures
import json
import os
from audit_inkscape_sources import OUT, download


def main():
    if os.name != 'nt' or os.environ.get('GITHUB_ACTIONS') != 'true':
        raise RuntimeError('Authorized Windows runner only')
    OUT.mkdir(parents=True, exist_ok=True)
    specs = [
        ('inkscape', 'https://gitlab.com/inkscape/inkscape/-/archive/ebf0e940d050842d608d57f6a04e6daaa5c65f37/inkscape-ebf0e940d050842d608d57f6a04e6daaa5c65f37.tar.gz'),
        ('extensions', 'https://gitlab.com/inkscape/extensions/-/archive/4f0376d82cc5f2feca21409f818d182b268af431/extensions-4f0376d82cc5f2feca21409f818d182b268af431.tar.gz'),
        ('themes', 'https://gitlab.com/inkscape/themes/-/archive/2fc6ece138323f905c9b475c3bcdef0d007eb233/themes-2fc6ece138323f905c9b475c3bcdef0d007eb233.tar.gz'),
        ('lib2geom', 'https://gitlab.com/inkscape/lib2geom/-/archive/23316118755def8156c268f767894c145130e07d/lib2geom-23316118755def8156c268f767894c145130e07d.tar.gz'),
        ('libcroco', 'https://gitlab.com/inkscape/libcroco/-/archive/ea3de62c70310d5aa09aa7e5c5e0f7298290a573/libcroco-ea3de62c70310d5aa09aa7e5c5e0f7298290a573.tar.gz'),
        ('GraphicsMagick-1.3.43', 'https://downloads.sourceforge.net/project/graphicsmagick/graphicsmagick/1.3.43/GraphicsMagick-1.3.43.tar.xz'),
    ]
    def probe(spec):
        name, url = spec
        try:
            return dict(name=name, **download(url))
        except Exception as error:
            return dict(name=name, url=url, status='UNRESOLVED', error=str(error)[:180])
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        records = list(pool.map(probe, specs))
    for name, version in [('mingw-w64-aspell-en', '2020.12.07-1'), ('mingw-w64-potrace', '1.16-2')]:
        attempts = []
        for extension in ['xz', 'gz', 'bz2']:
            item = probe((name, f'https://repo.msys2.org/mingw/sources/{name}-{version}.src.tar.{extension}'))
            attempts.append(item)
            if item['status'] == 'AVAILABLE':
                break
        records.append(dict(name=name, version=version, attempts=attempts,
                            **{k: v for k, v in attempts[-1].items() if k != 'name'}))
    result = dict(kind='CORRESPONDING_SOURCE_GAP_AUDIT_NOT_RELEASE', sources=records,
                  unresolved=sum(r['status'] != 'AVAILABLE' for r in records))
    (OUT/'source-gap-resolution.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(sources=len(records), unresolved=result['unresolved'])))


if __name__ == '__main__':
    main()
