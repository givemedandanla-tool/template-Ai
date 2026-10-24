"""Choose an installed interface font; never change artwork font evidence."""
from __future__ import annotations


def configure_ui_font(application):
    from PySide6.QtGui import QFont, QFontDatabase

    installed = {family.casefold(): family for family in QFontDatabase.families()}
    preferred = ('Microsoft JhengHei UI', 'Microsoft JhengHei', 'Segoe UI',
                 'Noto Sans CJK TC', 'Noto Sans', 'Arial')
    family = next((installed[name.casefold()] for name in preferred
                   if name.casefold() in installed), None)
    font = QFont(family, 10) if family else QFont(application.font())
    font.setPointSize(10)
    application.setFont(font)
    return font.family()
