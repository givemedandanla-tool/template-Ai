from dataclasses import asdict
from pathlib import Path
from template_ai.demo import demo_template
from template_ai.importer import import_file
from template_ai.model import Rect


def source_work(library, root, name='example.svg', visual=True):
    path = Path(root) / name
    path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="90mm" height="54mm" viewBox="0 0 90 54"><rect width="90" height="54" fill="white"/><g fill="black" font-family="sans-serif"><text x="8" y="14" font-size="6.35">Alex Example</text><text x="8" y="24" font-size="3.88">Designer</text><text x="8" y="36" font-size="3.52">+1 202 555 0100</text><text x="8" y="45" font-size="3.52">alex@example.test</text><text x="8" y="51" font-size="2">已校稿</text></g></svg>')
    source = library.add_source(path, import_file(path, library.assets))
    template = demo_template()
    payload = {'crop': asdict(Rect(0, 0, 90, 54)), 'work_width': 90, 'work_height': 54,
               'slots': [asdict(s) for s in template.slots], 'visual_confirmed': visual}
    work = library.create_artwork(source['id'], 'Synthetic Example', payload)
    return source, work


def observations(work):
    strings = ['Alex Example', 'Designer', '+1 202 555 0100', 'alex@example.test']
    rows = [{'id': 'observation-'+str(i), 'slot_id': s['id'], 'text': value, 'object_type': 'TEXT', 'classification': 'FIELD', 'region': dict(s['rect'])}
            for i, (s, value) in enumerate(zip(work['payload']['slots'], strings))]
    return rows+[{'id': 'note', 'slot_id': None, 'text': '已校稿', 'object_type': 'ANNOTATION', 'classification': 'ANNOTATION', 'region': {'x': 8, 'y': 48, 'w': 20, 'h': 5}}]
