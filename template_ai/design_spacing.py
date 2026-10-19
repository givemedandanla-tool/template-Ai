"""Explicit ASCII-word-boundary justification using actual Qt glyph positions.

Qt chooses line breaks and shapes glyphs. Only positions after reviewed word
boundaries move; this never expands CJK/letter boundaries implicitly.
"""
import re
import unicodedata
from PySide6.QtCore import QPointF
from PySide6.QtGui import QGlyphRun, QTextLayout


def word_justified_runs(layout,text,line_records,target_width,rule):
    if rule.get('justification')!='WORD_BOUNDARIES_ONLY':
        raise ValueError('Word-only justification needs an explicit reviewed boundary policy')
    if any(unicodedata.bidirectional(char) in ('R','AL','AN') for char in text):
        raise ValueError('RTL word justification needs a visual-order boundary policy')
    encoded=text.encode('utf-16-le');runs=[];details=[]
    for i,record in enumerate(line_records):
        line=layout.lineAt(i);start=record['start'];length=record['length']
        fragment=encoded[start*2:(start+length)*2].decode('utf-16-le')
        boundaries=[match.end() for match in re.finditer(r'(?<=\S) +(?=\S)',fragment)]
        paragraph_end=i==len(line_records)-1 or fragment.endswith(('\n','\u2028','\u2029'))
        expand=bool(boundaries) and (not paragraph_end or rule['last_line']=='DISTRIBUTE')
        delta=max(0.,target_width-line.naturalTextWidth())/len(boundaries) if expand else 0.
        details.append(dict(boundary_count=len(boundaries),extra_per_boundary_layout_units=delta,
            applied=bool(delta),last_line=paragraph_end))
        for original in layout.glyphRuns(start,length,QTextLayout.GlyphRunRetrievalFlag.RetrieveAll):
            indexes=list(original.stringIndexes());positions=list(original.positions())
            if len(indexes)!=len(positions):raise ValueError('Qt did not expose complete source glyph indexes')
            shifted=[]
            for index,position in zip(indexes,positions):
                logical=len(encoded[start*2:index*2].decode('utf-16-le'))
                count=sum(boundary<=logical for boundary in boundaries)
                shifted.append(QPointF(position.x()+delta*count,position.y()))
            result=QGlyphRun(original);result.setPositions(shifted);runs.append(result)
    return runs,details
