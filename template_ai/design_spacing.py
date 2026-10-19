"""Reviewed word or shaped-cluster justification using actual Qt glyph positions."""
from bisect import bisect_right
import math
import re
import unicodedata
from PySide6.QtCore import QPointF, QTextBoundaryFinder
from PySide6.QtGui import QGlyphRun, QTextLayout


def word_justified_runs(layout,text,line_records,target_width,rule,mm_per_layout_unit=1.):
    mode=rule.get('mode')
    expected={'WORDS':'WORD_BOUNDARIES_ONLY','CHARACTERS':'SHAPED_CLUSTER_BOUNDARIES_ONLY'}
    if mode not in expected or rule.get('justification')!=expected[mode]:
        raise ValueError('Justification needs an explicit reviewed boundary policy')
    limit=rule.get('maximum_extra_gap_mm')
    if (mode=='CHARACTERS' and limit is None) or (limit is not None and
            (type(limit) not in (float,int) or not math.isfinite(limit) or not 0<=limit<=50)):
        raise ValueError('Character justification needs a reviewed physical extra-gap bound')
    if any(unicodedata.bidirectional(char) in ('R','AL','AN') for char in text):
        raise ValueError('RTL justification needs a visual-order boundary policy')
    encoded=text.encode('utf-16-le');runs=[];details=[]
    finder=QTextBoundaryFinder(QTextBoundaryFinder.Grapheme,text);finder.toStart();graphemes={0}
    while (boundary:=finder.toNextBoundary())!=-1:graphemes.add(boundary)
    for i,record in enumerate(line_records):
        line=layout.lineAt(i);start=record['start'];length=record['length']
        fragment=encoded[start*2:(start+length)*2].decode('utf-16-le')
        originals=list(layout.glyphRuns(start,length,QTextLayout.GlyphRunRetrievalFlag.RetrieveAll))
        if mode=='WORDS':
            boundaries=[start+len(fragment[:match.end()].encode('utf-16-le'))//2
                for match in re.finditer(r'(?<=\S) +(?=\S)',fragment)]
        else:
            clusters=sorted({index for run in originals for index in run.stringIndexes()
                if start<=index<start+length and index in graphemes
                and encoded[index*2:(index+1)*2] not in (b'\n\0',b'( ',b') ')})
            boundaries=clusters[1:]
        paragraph_end=i==len(line_records)-1 or fragment.endswith(('\n','\u2028','\u2029'))
        expand=bool(boundaries) and (not paragraph_end or rule['last_line']=='DISTRIBUTE')
        delta=max(0.,target_width-line.naturalTextWidth())/len(boundaries) if expand else 0.
        if limit is not None and delta*mm_per_layout_unit>limit+1e-9:
            raise ValueError('Justification exceeds reviewed extra-gap bound')
        details.append(dict(boundary_count=len(boundaries),extra_per_boundary_layout_units=delta,
            applied=bool(delta),last_line=paragraph_end,mode=mode))
        for original in originals:
            indexes=list(original.stringIndexes());positions=list(original.positions())
            if len(indexes)!=len(positions):raise ValueError('Qt did not expose complete source glyph indexes')
            shifted=[]
            for index,position in zip(indexes,positions):
                count=bisect_right(boundaries,index)
                shifted.append(QPointF(position.x()+delta*count,position.y()))
            result=QGlyphRun(original);result.setPositions(shifted);runs.append(result)
    return runs,details
