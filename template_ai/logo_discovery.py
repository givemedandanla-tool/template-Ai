"""以 Inkscape 的實際變換後 bounds 提出完整群組候選，不拆出 Logo 內文字。

CLI query-all 回傳 CSS px；以 25.4/96 換算毫米。本機合成含 mm/viewBox
及 transform 案例驗證座標，避免自行重寫 SVG 幾何／字型／群組引擎。
"""
import csv
from dataclasses import asdict
import os
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

from .background import file_digest
from .importer import inkscape_path
from .model import Rect
from .source_links import verify_source


def discover(store, source_id, work_id):
    source = store.library.source(source_id)
    work = store.library.artwork(work_id)
    if work['source_id'] != source_id:
        raise ValueError('作品與來源不符')
    verify_source(source['current_path'], source['hash'])
    svg = source.get('svg')
    if not svg or not inkscape_path():
        raise ValueError('此來源無可查詢的向量群組；請使用原工作台框選完整 Logo 候選，未假稱已解析')
    path = Path(svg)
    if not path.is_file() or path.stat().st_size > 2_000_000 or path.is_symlink():
        raise ValueError('自動結構分析需2MB內的可信向量快取；較大來源可人工框選')
    expected = source.get('file_hashes', {}).get('svg')
    if not expected or file_digest(path) != expected:
        raise ValueError('向量快取與已匯入來源不符')
    root = ET.parse(path).getroot()
    elements = list(root.iter())
    if len(elements) > 4000:
        raise ValueError('向量物件超出本次結構預算，請按作品縮小範圍')
    environment = os.environ.copy()
    environment['INKSCAPE_PROFILE_DIR'] = str(store.library.assets / 'inkscape-logo-query')
    process = subprocess.run([inkscape_path(), '--query-all', str(path)], capture_output=True,
        text=True, timeout=30, env=environment, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if process.returncode:
        raise ValueError('Inkscape 來源幾何查詢失敗，沒有建立 Logo 候選')
    if len(process.stdout) > 1_048_576:
        raise ValueError('幾何輸出超出預算，請縮小作品')
    bounds = {}
    for row in csv.reader(process.stdout.splitlines()):
        if len(row) == 5:
            try:
                bounds[row[0]] = Rect(*(float(v)*25.4/96 for v in row[1:]))
            except ValueError:
                continue
    area = Rect(**work['payload']['crop'])
    result = []
    drawable = {'text', 'path', 'rect', 'circle', 'ellipse', 'polygon', 'polyline', 'line', 'image', 'use'}
    for node in elements:
        if node.tag.rsplit('}', 1)[-1] != 'g' or node.get('id') not in bounds:
            continue
        children = [e for e in node.iter() if e is not node and e.tag.rsplit('}', 1)[-1] in drawable]
        if len(children) < 2:
            continue
        rect = bounds[node.get('id')]
        if not rect.valid() or rect.x < area.x-1e-4 or rect.y < area.y-1e-4 \
                or rect.x+rect.w > area.x+area.w+1e-4 or rect.y+rect.h > area.y+area.h+1e-4:
            continue
        hints = []
        for element in node.iter():
            label = ''.join(element.itertext()) if element.tag.rsplit('}', 1)[-1] == 'text' else element.get('aria-label', '')
            if label:
                hints.append(label[:256])  # 轉曲後的 aria-label 仍只是身分線索。
        result.append(store.propose_source(source_id, work_id, asdict(rect),
            object_ids=[e.get('id') for e in children if e.get('id')],
            evidence=dict(method='INKSCAPE_QUERY_ALL_CSS_PX_TO_MM', group_id=node.get('id'),
                text_hints=hints, native_editability='UNKNOWN',
                uncertainty='完整群組只是待核對 Logo 候選；文字線索不確認公司身分')))
        if len(result) >= 100:
            break
    # 來源在查詢途中變更時不以新結果核准；已存的待審候選仍被 pins 阻擋。
    verify_source(source['current_path'], source['hash'])
    if file_digest(path) != expected:
        raise ValueError('幾何查詢期間來源快取改變，候選不可核准')
    return result
