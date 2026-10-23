"""Small local context tokens for modal operations; never persisted as raw data."""
from dataclasses import asdict
import sqlite3
from .font_review import fingerprint
from .property_context import source_pin, pending_main


def capture(window, subject):
    try:
        if window.library.closed:return None
        view=window.tabs.currentIndex();root=str(window.library.root)
        if subject==2:return (subject,view,root,window.generation)
        if view!=subject or pending_main(window):return None
        pin=source_pin(window,subject)
        if pin is None:return None
        if subject==1:
            if window.template is None or window.template.state!='draft':return None
            current=window.library.object_snapshot('TEMPLATE',window.template.id)
            if current['revision']!=pin[3] or fingerprint(current['payload'])!=pin[4]:return None
            body=window.template.to_dict()
        elif subject==0:
            if not window.work or not window.source or window.work['source_id']!=window.source['id']:return None
            if window.library.artwork(window.work['id'])!=window.work:return None
            body=dict(work=window.work,crop=asdict(window.crop),slots=[asdict(s) for s in window.slots],
                      width=window.work_width,height=window.work_height,visual=window.visual.isChecked())
        else:return None
        return (subject,view,tuple(pin),fingerprint(body))
    except (ValueError,TypeError,KeyError,OSError,RuntimeError,sqlite3.Error):return None


def unchanged(window, token):
    return token is not None and capture(window,token[0])==token
