"""示範只使用合成資訊；不會載入或提交客戶原稿。"""
from PySide6.QtGui import QFontDatabase
from .model import Rect, Slot, Template


def default_font():
    families = QFontDatabase.families()
    if not families:
        raise ValueError("Qt 未取得任何字型；Windows 請使用原生 windows 平台，或載入合法字型後再量測")
    for family in ["Noto Sans CJK TC", "Microsoft JhengHei", "Microsoft YaHei", "Arial"]:
        if family in families:
            return family
    return families[0]


def demo_template():
    font = default_font()
    return Template("匿名示範 · 單人矩形", 90, 54, [
        Slot("name", "p1", Rect(8, 6, 70, 11), font=font, size_pt=18),
        Slot("title", "p1", Rect(8, 19, 70, 7), font=font, size_pt=11),
        Slot("phone", "p1", Rect(8, 31, 70, 7), font=font, size_pt=10),
        Slot("email", "p1", Rect(8, 40, 70, 7), font=font, size_pt=10),
    ], reasons=["合成示範，非歷史 AI 訓練成果", "固定字級；本模板字寬下限 85% 為示範設計值，非通用印刷標準"])
