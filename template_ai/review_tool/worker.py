"""Owned analysis subprocess entry; stdout is a JSON-line local IPC stream."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys


def _emit(value):
    print(json.dumps(value, ensure_ascii=False), flush=True)


def main(request_path) -> int:
    """Called by review_app.py --analysis-worker; never opens the main window."""
    from ..offline_runtime import assert_local_document, assert_local_path, enable_offline_guard
    enable_offline_guard()
    diagnostics = None
    try:
        from .diagnostics import start_diagnostics
        diagnostics = start_diagnostics(role='worker')
        path=Path(request_path).resolve();assert_local_path(path)
        if not path.is_file() or path.is_symlink() or path.stat().st_size>65536:
            raise ValueError('工作參數不存在或超出支援範圍')
        request=json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(request,dict) or not {'path','cache_dir'}<=set(request):
            raise ValueError('工作參數不完整')
        assert_local_document(request['path']);assert_local_path(request['cache_dir'])
        runtime_root=Path(sys.executable).resolve().parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parents[2]
        models=runtime_root/'engines/ocr-models'
        if models.is_dir():
            os.environ['TEMPLATE_AI_TESSDATA']=str(models)
        _emit(dict(type='progress',stage='validate',message='正在啟動本機判讀工具',phase_timeout=90))
        # QApplication is created inside this child, keeping source conversion
        # and font/Qt initialization outside the responsive main UI process.
        from PySide6.QtWidgets import QApplication
        application=QApplication.instance() or QApplication(['TemplateAI-Review-Worker'])
        from .ui_font import configure_ui_font
        configure_ui_font(application)
        from .analysis import analyse_file
        result=analyse_file(request['path'],request['cache_dir'],
                            progress_callback=lambda event:_emit(dict(type='progress',**event)),
                            ocr=bool(request.get('ocr',True)))
        _emit(dict(type='result',result=result))
        return 0
    except Exception as error:
        # Raw exception text can contain customer strings or paths. Keep it in
        # local logs only if a caller separately opts in; safe IPC has a code.
        from .source_compatibility import ReviewSourceCompatibilityError
        if isinstance(error, ReviewSourceCompatibilityError):
            _emit(dict(type='error', code=error.code, message=error.safe_message))
        else:
            _emit(dict(type='error',code=type(error).__name__,
                       message='這個檔案尚未完成判讀；原稿保持不變，可重試或匯出問題報告。'))
        return 1
    finally:
        if diagnostics:
            diagnostics.close()


if __name__=='__main__':
    raise SystemExit(main(sys.argv[1]))
