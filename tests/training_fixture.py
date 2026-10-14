from dataclasses import asdict
from pathlib import Path
from template_ai.demo import demo_template
from template_ai.importer import import_file
from template_ai.model import Rect


def source_work(library, root, name='example.svg', visual=True):
    path = Path(root) / name
    path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="90mm" height="54mm"><rect width="90" height="54" fill="white"/><text x="8" y="16">Alex Example</text><text x="8" y="22">已校稿</text></svg>')
    source = library.add_source(path, import_file(path, library.assets))
    template = demo_template()
    payload = {'crop': asdict(Rect(0, 0, 90, 54)), 'work_width': 90, 'work_height': 54,
               'slots': [asdict(s) for s in template.slots], 'visual_confirmed': visual}
    work = library.create_artwork(source['id'], 'Synthetic Example', payload)
    return source, work
