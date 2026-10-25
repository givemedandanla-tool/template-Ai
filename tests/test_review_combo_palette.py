"""Render real review dropdowns; exercise selection without opening user data."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QComboBox

APP = QApplication.instance() or QApplication([])


def contrast(a, b):
    def lum(c):
        values = [v / 255 for v in c.getRgb()[:3]]
        return sum((v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4) * w
                   for v, w in zip(values, (.2126, .7152, .0722)))
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + .05) / (lo + .05)


class ReviewComboPaletteTests(unittest.TestCase):
    def check_palette(self, dark):
        from template_ai.review_tool.window import ReviewWindow
        from template_ai.review_tool.font_dialog import FontReviewDialog
        original = QPalette(APP.palette())
        palette = QPalette(original)
        for group in (QPalette.Active, QPalette.Inactive, QPalette.Disabled):
            for role in (QPalette.Window, QPalette.Base, QPalette.Button):
                palette.setColor(group, role, QColor('#111111' if dark else '#ffffff'))
            for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
                palette.setColor(group, role, QColor('#eeeeee' if dark else '#172033'))
            palette.setColor(group, QPalette.Highlight, QColor('#334155'))
            palette.setColor(group, QPalette.HighlightedText, QColor('#eeeeee'))
        APP.setPalette(palette)
        try:
            with tempfile.TemporaryDirectory(prefix='review-combo-') as raw, \
                    patch.object(FontReviewDialog, 'load_families'):
                window = ReviewWindow(Path(raw))
                dialog = FontReviewDialog({}, {}, {'text': 'SYNTHETIC'}, window)
                try:
                    window.show()
                    window.activateWindow()
                    self.assertTrue(QTest.qWaitForWindowExposed(window))
                    QTest.qWait(200)
                    window.detail_stack.setCurrentIndex(1)
                    window.owner_combo.addItems(['合成人物甲', '合成人物乙'])
                    dialog.style_combo.addItems(['一般', '粗體'])
                    expected = [window.kind_combo, window.owner_combo, window.review_combo,
                                dialog.style_combo]
                    self.assertEqual(set(window.findChildren(QComboBox)), set(expected))
                    for name, combo in zip(('kind', 'owner', 'review', 'font'), expected):
                        with self.subTest(combo=name, dark=dark):
                            if name == 'font':
                                dialog.show()
                                dialog.activateWindow()
                                self.assertTrue(QTest.qWaitForWindowExposed(dialog))
                                QTest.qWait(200)
                            combo.setEnabled(True)
                            combo.setCurrentIndex(0)
                            combo.addItem('不可用合成項目', 'disabled-synthetic')
                            disabled = combo.model().item(combo.count() - 1)
                            disabled.setEnabled(False)
                            APP.processEvents()
                            combo.showPopup()
                            QTest.qWait(300)
                            view = combo.view()
                            self.assertTrue(view.isVisible())
                            selected = combo.model().index(1, 0)
                            view.setCurrentIndex(selected)
                            view.scrollTo(selected)
                            APP.processEvents()
                            self.check_row(view, 0, '#ffffff', 7)
                            self.check_row(view, 1, '#e8f0ff', 7)
                            last = combo.model().index(combo.count() - 1, 0)
                            view.scrollTo(last)
                            APP.processEvents()
                            self.check_row(view, last.row(), '#ffffff', 4.5)
                            view.scrollTo(selected)
                            APP.processEvents()
                            output = os.environ.get('REVIEW_COMBO_CAPTURE_DIR')
                            if output:
                                target = Path(output)
                                target.mkdir(parents=True, exist_ok=True)
                                self.assertTrue(view.window().grab().save(str(
                                    target / f'{"dark" if dark else "light"}-{name}.png')))
                            value = combo.itemData(1)
                            QTest.mouseClick(view.viewport(), Qt.LeftButton,
                                             pos=view.visualRect(selected).center())
                            self.assertEqual(combo.currentIndex(), 1)
                            self.assertEqual(combo.currentData(), value)
                            combo.showPopup()
                            APP.processEvents()
                            QTest.keyClick(view, Qt.Key_Up)
                            QTest.keyClick(view, Qt.Key_Return)
                            self.assertEqual(combo.currentIndex(), 0)
                            self.assertFalse(disabled.isEnabled())
                            combo.hidePopup()
                finally:
                    dialog.reject()
                    window.close()
                    APP.processEvents()
        finally:
            APP.setPalette(original)

    def check_row(self, view, row, expected, threshold):
        rect = view.visualRect(view.model().index(row, 0))
        self.assertTrue(view.viewport().rect().contains(rect.center()))
        pixmap = view.viewport().grab()
        ratio = pixmap.devicePixelRatio()
        image = pixmap.toImage()
        background = image.pixelColor(round((rect.right() - 5) * ratio),
                                      round(rect.center().y() * ratio))
        self.assertEqual(background.name(), expected)
        # Inspect glyph pixels within the row, excluding the selection border.
        colors = {image.pixelColor(x, y).rgba()
                  for x in range(round((rect.left() + 5) * ratio),
                                 round((rect.right() - 10) * ratio))
                  for y in range(round((rect.top() + 3) * ratio),
                                 round((rect.bottom() - 3) * ratio))}
        self.assertGreaterEqual(max(contrast(QColor.fromRgba(c), background)
                                    for c in colors), threshold)

    def test_dark_palette_dropdowns(self):
        self.check_palette(True)

    def test_light_palette_dropdowns(self):
        self.check_palette(False)


if __name__ == '__main__':
    unittest.main()
