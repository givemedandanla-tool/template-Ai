"""Visible field warnings without changing editable values or stealing focus."""
from PySide6.QtCore import Qt,QRect
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QStyledItemDelegate,QStyleOptionViewItem
WARNING_ROLE=int(Qt.UserRole)+31

class InputWarningDelegate(QStyledItemDelegate):
    def paint(self,painter,option,index):
        warning=index.data(WARNING_ROLE)
        if not warning:return super().paint(painter,option,index)
        text_option=QStyleOptionViewItem(option);text_option.rect=option.rect.adjusted(0,0,0,-18);super().paint(painter,text_option,index)
        painter.save();painter.setPen(QColor('#9a3412'));font=painter.font();font.setPointSize(8);painter.setFont(font);rect=QRect(option.rect.left()+3,option.rect.bottom()-17,option.rect.width()-6,17);painter.drawText(rect,Qt.AlignLeft|Qt.AlignVCenter,'⚠ '+painter.fontMetrics().elidedText(warning,Qt.ElideRight,rect.width()-8));painter.restore()
    def updateEditorGeometry(self,editor,option,index):
        editor.setGeometry(option.rect.adjusted(0,0,0,-18) if index.data(WARNING_ROLE) else option.rect)
