"""Qt glyph ink envelope alongside advance width; never fit by advance alone."""
from PySide6.QtGui import QFontMetricsF


def ink_metrics(font,text):
    metrics=QFontMetricsF(font);advance=metrics.horizontalAdvance(text);ink=metrics.tightBoundingRect(text)
    left=min(0.,ink.left());right=max(advance,ink.right());ascent=max(metrics.ascent(),-ink.top());height=max(metrics.height(),ascent+max(metrics.descent(),ink.bottom()))
    return dict(metrics=metrics,advance=advance,left=left,width=right-left,ascent=ascent,height=height)
