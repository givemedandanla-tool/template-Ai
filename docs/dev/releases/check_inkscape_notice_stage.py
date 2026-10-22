"""Targeted public-license assembly check; not a product/EXE qualification."""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools'))
import bundled_inkscape_build as build


def main():
    lock=json.loads(build.LOCK.read_text(encoding='utf-8'))
    build.install(lock)
    folder=ROOT/'dist/TemplateAI'
    pin=json.loads((ROOT/'build/release/inkscape-runtime-pin.json').read_text())
    build.write(folder/'_internal/release-info.json',dict(inkscape_runtime=pin))
    actual=build.vendor_inventory(folder)
    notices=json.loads((build.STAGED/'TEMPLATE_AI_DEPENDENCY_LICENSES/SOURCE.json').read_text())
    if len(actual)!=pin['files']+1 or notices['files']<200:
        raise RuntimeError('Incomplete staged public-runtime/license inventory')
    build.write(ROOT/'artifacts/inkscape-audit/license-stage.json',dict(
        status='PASS',kind='TARGETED_PUBLIC_LICENSE_AND_MANIFEST_ASSEMBLY_NOT_PRODUCT_EXE_QUALIFICATION',
        runtime_files=pin['files'],original_license_files=notices['files'],
        manifest_sha256=pin['manifest_sha256'],all_vendor_hashes_match=True,product_executable_test=False))
    print(json.dumps(dict(status='PASS',files=pin['files'],licenses=notices['files'])))


if __name__=='__main__':main()
