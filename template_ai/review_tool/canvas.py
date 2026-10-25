"""Original artwork with local-millimetre annotations and linked measurements.

The source image is never edited. Scene coordinates are page millimetres; field
rectangles and emitted annotations are work-local millimetres (crop offset).
"""
from __future__ import annotations

from copy import deepcopy
import math
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen, QPixmap, QTransform
from PySide6.QtWidgets import (
    QGraphicsItem, QGraphicsRectItem, QGraphicsScene,
    QGraphicsSimpleTextItem, QGraphicsView,
)


def _number(value):
    if isinstance(value, dict):
        if value.get('status') == 'UNKNOWN':
            return None
        value = value.get('value')
    return float(value) if type(value) in (int, float) and math.isfinite(value) else None


def _rect(value):
    if not isinstance(value, dict) or value.get('status') == 'UNKNOWN':
        return None
    if value.get('unit', 'mm') != 'mm':
        return None
    if isinstance(value.get('value'), dict):
        value = value['value']
    for key in ('x', 'y', 'w', 'h'):
        component = value.get(key)
        if isinstance(component, dict) and component.get('unit', 'mm') != 'mm':
            return None
    vals = [_number(value.get(k)) for k in ('x', 'y', 'w', 'h')]
    if any(v is None for v in vals) or vals[2] <= 0 or vals[3] <= 0:
        return None
    return QRectF(*vals)


def _as_dict(rect):
    return dict(x=rect.x(), y=rect.y(), w=rect.width(), h=rect.height())


def _pen(color, width=1.5, dashed=False):
    pen = QPen(QColor(color), width)
    pen.setCosmetic(True)
    if dashed:
        pen.setStyle(Qt.PenStyle.DashLine)
    return pen


class ReviewCanvas(QGraphicsView):
    fieldSelected = Signal(str)
    fieldsSelected = Signal(list)
    annotationAdded = Signal(dict)
    annotationResized = Signal(str, dict)
    statusMessage = Signal(str)
    zoomChanged = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('reviewCanvas')
        self.setScene(QGraphicsScene(self))
        self.setBackgroundBrush(QColor('#edf1f5'))
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        self.setFrameShape(QGraphicsView.Shape.NoFrame)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setMinimumSize(280, 220)
        self.image_item = None
        self.field_items = {}
        self.measurement_items = []
        self.selected_id = None
        self._selected_ids = []
        self.work = None
        self._fields = {}
        self._labels = {}
        self._label_backgrounds = {}
        self._handles = []
        self._work_item = None
        self._page = QRectF()
        self._crop = QRectF()
        self._mode = 'select'
        self._visible = True
        self._start = None
        self._rubber = None
        self._resize_id = None
        self._opposite = None
        self._fit_scale = 1.0
        self._auto_fit = True
        self._source_calibrated = None

    def set_source(self, image_path, width_mm, height_mm, *, calibrated=None):
        width, height = _number(width_mm), _number(height_mm)
        if width is None or height is None or width <= 0 or height <= 0:
            raise ValueError('原稿缺少可靠的實體尺寸，無法對應毫米座標。')
        pixmap = QPixmap(str(Path(image_path)))
        if pixmap.isNull():
            raise ValueError('原稿預覽尚未建立或無法讀取。')
        self.scene().clear()
        self.field_items.clear()
        self.measurement_items.clear()
        self._fields.clear()
        self._labels.clear()
        self._label_backgrounds.clear()
        self._handles.clear()
        self._work_item = None
        self._rubber = None
        self._start = None
        self._resize_id = None
        self._opposite = None
        self.selected_id = None
        self._selected_ids = []
        self.work = None
        self._page = QRectF(0, 0, width, height)
        self._source_calibrated = calibrated
        self._crop = QRectF(self._page)
        self.image_item = self.scene().addPixmap(pixmap)
        self.image_item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        self.image_item.setTransform(QTransform.fromScale(width / pixmap.width(), height / pixmap.height()))
        self.image_item.setZValue(-100)
        self.scene().setSceneRect(self._page.adjusted(-width*.1, -height*.1, width*.1, height*.1))
        self.fit_work()

    def set_work(self, work):
        crop = _rect(work.get('crop', {}))
        if crop is None:
            raise ValueError('作品範圍缺失，請先標記作品範圍。')
        self.clear_measurement()
        self.work = deepcopy(work)
        self._crop = crop
        if self._work_item is not None:
            self.scene().removeItem(self._work_item)
        self._work_item = self.scene().addRect(crop, _pen('#a6b3c4', 1, True))
        self._work_item.setZValue(1)
        self.set_fields(work.get('fields', []))
        self.fit_work()

    def local_to_scene(self, point):
        if not isinstance(point, QPointF):
            point = QPointF(*point)
        return point + self._crop.topLeft()

    def scene_to_local(self, point):
        return point - self._crop.topLeft()

    def local_rect_to_scene(self, value):
        rect = value if isinstance(value, QRectF) else _rect(value)
        return rect.translated(self._crop.topLeft()) if rect is not None else None

    def set_fields(self, fields):
        previous = self.selected_id
        previous_many = list(self._selected_ids)
        self.clear_measurement()
        self._clear_handles()
        for item in [*self.field_items.values(), *self._label_backgrounds.values()]:
            self.scene().removeItem(item)
        self.field_items.clear()
        self._labels.clear()
        self._label_backgrounds.clear()
        self._fields = {}
        for field in fields:
            key = str(field.get('id', ''))
            rect = self.local_rect_to_scene(field.get('rect'))
            if not key or rect is None:
                continue
            self._fields[key] = deepcopy(field)
            unknown = field.get('review_state') == 'UNKNOWN' or field.get('kind') == 'UNKNOWN'
            item = self.scene().addRect(rect, _pen('#748fac', 1.2, unknown), QColor(37, 99, 235, 8))
            item.setData(0, key)
            item.setZValue(10)
            item.setVisible(self._visible)
            self.field_items[key] = item
            fallback = {'mobile':'手機','landline':'市內電話','phone':'電話','email':'電子郵件',
                        'social_id':'社群帳號','address':'地址','title':'職稱','name':'姓名',
                        'company':'公司','logo':'Logo','annotation':'旁註','unknown':'待核對'}
            caption = field.get('label') or field.get('name') or fallback.get(str(field.get('kind','')).lower(),'欄位')
            background = QGraphicsRectItem()
            background.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
            background.setPen(_pen('#b9cbea',.8))
            background.setBrush(QColor(255,255,255,247))
            background.setZValue(20)
            self.scene().addItem(background)
            label = QGraphicsSimpleTextItem(background)
            label_font=QFont(self.font());label_font.setPointSize(10)
            label.setFont(label_font)
            label.setText(QFontMetrics(label.font()).elidedText(str(caption),Qt.TextElideMode.ElideRight,180))
            label.setToolTip(str(caption))
            label.setBrush(QColor('#1e4fa6'))
            label.setPos(4,2)
            bounds=label.boundingRect()
            background.setRect(0,0,bounds.width()+8,bounds.height()+4)
            background.hide()
            self._labels[key] = label
            self._label_backgrounds[key] = background
        self.selected_id = previous if previous in self.field_items else None
        self._selected_ids = [key for key in previous_many if key in self.field_items]
        self._style_selection()

    def select_field(self, field_id):
        field_id = str(field_id)
        if field_id not in self.field_items:
            return False
        self.clear_measurement()
        self.selected_id = field_id
        if field_id not in self._selected_ids:
            self._selected_ids = [field_id]
        self._style_selection()
        return True

    def selected_fields(self):
        return list(self._selected_ids)

    def selected_field_ids(self):
        return self.selected_fields()

    def _style_selection(self):
        self._clear_handles()
        for key, item in self.field_items.items():
            field = self._fields[key]
            unknown = field.get('review_state') == 'UNKNOWN' or field.get('kind') == 'UNKNOWN'
            selected = key in self._selected_ids
            item.setPen(_pen('#2563eb' if selected else '#748fac', 2.5 if selected else 1.2, unknown))
            item.setBrush(QColor(37, 99, 235, 20 if selected else 5))
            item.setVisible(self._visible)
            self._label_backgrounds[key].setVisible(selected and self._visible)
            self._labels[key].setVisible(selected and self._visible)
        self._position_labels()
        if self._mode == 'resize' and self.selected_id in self.field_items and self._visible:
            rect = self.field_items[self.selected_id].rect()
            for point in [rect.topLeft(), rect.topRight(), rect.bottomLeft(), rect.bottomRight()]:
                handle = QGraphicsRectItem(-4, -4, 8, 8)
                handle.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
                handle.setPos(point)
                handle.setPen(_pen('#2563eb', 1.3))
                handle.setBrush(QColor('white'))
                handle.setZValue(30)
                self.scene().addItem(handle)
                self._handles.append(handle)

    def _position_labels(self):
        scale=abs(self.transform().m22()) or 1.0
        for key,background in self._label_backgrounds.items():
            rect=self.field_items[key].rect()
            # The caption is fixed logical pixels; its page anchor must account
            # for the view scale so it stays fully above the annotated content.
            background.setPos(rect.topLeft()-QPointF(0,(background.rect().height()+4)/scale))
        self._position_range_captions()

    def _clear_handles(self):
        for item in self._handles:
            self.scene().removeItem(item)
        self._handles.clear()

    def set_mode(self, mode):
        if mode not in ('select', 'add', 'resize'):
            raise ValueError('未知的標記操作模式。')
        self._mode = mode
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag if mode == 'select' else QGraphicsView.DragMode.NoDrag)
        self.viewport().setCursor(Qt.CursorShape.CrossCursor if mode == 'add' else Qt.CursorShape.ArrowCursor)
        self._style_selection()

    def set_overlays_visible(self, visible):
        self._visible = bool(visible)
        if self._work_item is not None:
            self._work_item.setVisible(self._visible)
        self._style_selection()
        if not visible:
            self.clear_measurement()

    def fit_work(self):
        if self._crop.isEmpty():
            return
        margin = max(self._crop.width(), self._crop.height()) * .07
        self.fitInView(self._crop.adjusted(-margin, -margin, margin, margin), Qt.AspectRatioMode.KeepAspectRatio)
        self._fit_scale = abs(self.transform().m11()) or 1.0
        self._auto_fit = True
        self._position_labels()
        self.zoomChanged.emit(100.0)

    def zoom(self, factor):
        factor = _number(factor)
        if factor is None or factor <= 0:
            return
        current = abs(self.transform().m11()) or 1
        limited = min(max(current * factor, self._fit_scale * .1), self._fit_scale * 20)
        self.scale(limited / current, limited / current)
        self._auto_fit = False
        self._position_labels()
        self.zoomChanged.emit(100 * limited / self._fit_scale)

    def locate_field(self, field_id):
        if not self.select_field(field_id):
            return False
        rect = self.field_items[str(field_id)].rect()
        viewport = self.mapToScene(self.viewport().rect()).boundingRect()
        if not viewport.contains(rect):
            self.centerOn(rect.center())
        return True

    def field_center(self, field_id):
        return self.mapFromScene(self.field_items[str(field_id)].rect().center())

    def clear_measurement(self):
        for item in self.measurement_items:
            if item.scene() is self.scene():
                self.scene().removeItem(item)
        self.measurement_items.clear()

    def _measurement_rect(self, rect, label, color='#7c3aed', dashed=False):
        item = self.scene().addRect(rect, _pen(color, 2, dashed))
        item.setZValue(40)
        item.setData(1, 'measurement')
        self.measurement_items.append(item)
        if label:
            caption=self._text(label,rect.topLeft(),color)
            caption.setData(2,'range_caption')
            caption.setData(3,QRectF(rect))
            self._position_range_captions()

    def _position_range_captions(self):
        """Keep range captions outside artwork fields in actual view pixels.

        Only range captions move; measurement endpoints, dimension lines and
        physical calibration remain unchanged. If the view is too crowded,
        place the caption outside the original page rather than over its ink.
        """
        transform=self.viewportTransform()
        inverse,invertible=transform.inverted()
        if not invertible:
            return
        viewport=QRectF(self.viewport().rect()).adjusted(2,2,-2,-2)
        fields=[transform.mapRect(item.rect()).adjusted(-4,-4,4,4) for item in self.field_items.values()]
        badges=[item.deviceTransform(transform).mapRect(item.boundingRect()).adjusted(-3,-3,3,3)
                for item in self._label_backgrounds.values() if item.isVisible()]
        captions=[item for item in self.measurement_items
                  if isinstance(item,QGraphicsSimpleTextItem) and item.data(2)=='range_caption']
        for item in captions:
            local=item.boundingRect()
            width,height=local.width(),local.height()
            rect=transform.mapRect(item.data(3))
            occupied=fields+badges+[
                other.deviceTransform(transform).mapRect(other.boundingRect()).adjusted(-3,-3,3,3)
                for other in self.measurement_items
                if other is not item and isinstance(other,QGraphicsSimpleTextItem) and other.text()]
            gap=6
            positions=[QPointF(rect.left(),rect.top()-height-gap),
                       QPointF(rect.left()-width-gap,rect.center().y()-height/2),
                       QPointF(rect.right()+gap,rect.center().y()-height/2),
                       QPointF(rect.left(),rect.bottom()+gap),
                       QPointF(rect.right()-width,rect.top()-height-gap),
                       QPointF(rect.left(),rect.top()-2*(height+gap))]
            chosen=None
            for point in positions:
                box=QRectF(point.x(),point.y(),width,height)
                if viewport.contains(box) and not any(box.intersects(other) for other in occupied):
                    chosen=point
                    break
            if chosen is None:
                page=transform.mapRect(self._page)
                # The last resort is outside the complete source image and
                # below other labels, even when no free gutter is in view.
                bottom=max([page.bottom(),*[other.bottom() for other in occupied]])
                chosen=QPointF(page.left(),bottom+gap)
            item.setPos(inverse.map(chosen-local.topLeft()))

    def _text(self, text, point, color='#6d28d9'):
        item = QGraphicsSimpleTextItem(text)
        item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
        label_font=QFont(self.font());label_font.setPointSize(10)
        item.setFont(label_font)
        item.setBrush(QColor(color))
        item.setPos(point)
        item.setZValue(45)
        item.setData(1, 'measurement')
        self.scene().addItem(item)
        self.measurement_items.append(item)
        return item

    def _line(self, a, b, color='#7c3aed', dashed=False):
        item = self.scene().addLine(a.x(), a.y(), b.x(), b.y(), _pen(color, 1.5, dashed))
        item.setZValue(42)
        item.setData(1, 'measurement')
        self.measurement_items.append(item)

    def _dimension(self, a, b, label):
        self._line(a, b)
        scale = abs(self.transform().m11()) or 1
        size = 5 / scale
        direction = b - a
        length = math.hypot(direction.x(), direction.y())
        if length:
            normal = QPointF(-direction.y()/length*size, direction.x()/length*size)
            for point in (a, b):
                self._line(point-normal, point+normal)
        self._text(label, (a+b)/2)
        self._position_range_captions()

    def _physical_scale_verified(self, field):
        if self._source_calibrated is False or (self.work or {}).get('calibrated') is False:
            return False
        for key in ('width_mm','height_mm'):
            value = (self.work or {}).get('measurements',{}).get(key)
            if isinstance(value,dict) and value.get('status') == 'UNKNOWN':
                return False
        measurements = field.get('measurements',{})
        frame = measurements.get('frame',{})
        if isinstance(frame,dict) and frame.get('coordinate') == 'UNVERIFIED_PREVIEW_MM':
            return False
        if field.get('evidence',{}).get('physical_scale') == 'UNKNOWN':
            return False
        return True

    def show_measurement(self, metric, field=None, related=None):
        """Show only supported geometry. Return False and explain unknown data.

        ``metric`` is a name or a relation dict (kind/alignment/axis/field_ids).
        Supported names include frame, width, height, ink_bounds,
        container_bounds, baseline, gap, alignment, group, owner, distribution.
        """
        self.clear_measurement()
        spec = metric if isinstance(metric, dict) else {'kind': metric}
        name = str(spec.get('kind', spec.get('key', 'frame'))).lower()
        if isinstance(field, str):
            field = self._fields.get(field)
        field = field or self._fields.get(self.selected_id)
        if not isinstance(field, dict):
            self.statusMessage.emit('請先選取要查看的欄位。')
            return False
        rect = self.local_rect_to_scene(field.get('rect'))
        if rect is None:
            self.statusMessage.emit('這個欄位的範圍尚未取得。')
            return False
        measurements = field.get('measurements', {})
        physical_metrics = {'frame','rect','size','dimensions','width','height','width_mm','height_mm','position',
                            'ink','ink_bounds','container','container_bounds','baseline','baseline_with',
                            'gap','gap_to','alignment','aligned_to','distribution','distributed'}
        if name in physical_metrics and not self._physical_scale_verified(field):
            self.statusMessage.emit('這份原稿的實體比例尚未確認；可定位標記，但不能顯示確定的毫米量測。')
            return False
        offset = max(.3, 12 / (abs(self.transform().m11()) or 1))
        if name in ('frame', 'rect', 'size', 'dimensions', 'width', 'height', 'width_mm', 'height_mm', 'position'):
            self._measurement_rect(rect, '欄位範圍')
            if name not in ('height', 'height_mm'):
                self._dimension(rect.topLeft()-QPointF(0, offset), rect.topRight()-QPointF(0, offset), f'{rect.width():.4g} mm')
            if name not in ('width', 'width_mm'):
                self._dimension(rect.topRight()+QPointF(offset, 0), rect.bottomRight()+QPointF(offset, 0), f'{rect.height():.4g} mm')
            return True
        if name in ('ink', 'ink_bounds', 'container', 'container_bounds'):
            key = 'ink_bounds' if name.startswith('ink') else 'container_bounds'
            known = self.local_rect_to_scene(measurements.get(key))
            if known is not None:
                self._measurement_rect(known, '文字墨跡' if key == 'ink_bounds' else '容器範圍', '#9333ea' if key == 'ink_bounds' else '#526174', True)
                self._dimension(known.topLeft()-QPointF(0, offset), known.topRight()-QPointF(0, offset), f'{known.width():.4g} mm')
                self._dimension(known.topRight()+QPointF(offset, 0), known.bottomRight()+QPointF(offset, 0), f'{known.height():.4g} mm')
                return True
            self.statusMessage.emit(('文字墨跡' if key == 'ink_bounds' else '容器範圍')+'尚未取得，沒有可顯示的確定範圍。')
            return False
        if name in ('baseline', 'baseline_with'):
            peers = related if related is not None else spec.get('field_ids', [])
            if isinstance(peers, dict):
                peers = [peers]
            baseline_fields = [field]+[self._fields.get(p) if isinstance(p,str) else p for p in (peers or [])]
            seen = set()
            lines = []
            for part in baseline_fields:
                if not isinstance(part,dict) or part.get('id') in seen:
                    continue
                seen.add(part.get('id'))
                part_rect = self.local_rect_to_scene(part.get('rect'))
                observed = part.get('measurements',{})
                value = observed.get('baseline_y',observed.get('baseline'))
                baseline = _number(value)
                if isinstance(value,dict) and value.get('unit','mm') != 'mm':
                    baseline = None
                if baseline is None or part_rect is None:
                    self.statusMessage.emit('文字基線尚未取得或單位未換算，不能以墨跡底邊代替。')
                    return False
                lines.append((part_rect,self._crop.y()+baseline))
            for part_rect,y in lines:
                self._line(QPointF(part_rect.left(),y),QPointF(part_rect.right(),y),'#0f766e')
                self._text('文字基線',QPointF(part_rect.left(),y),'#0f766e')
            if len(lines)>1:
                values=[y for _,y in lines]
                self._text(f'基線差 {max(values)-min(values):.4g} mm',rect.topLeft()-QPointF(0,offset),'#0f766e')
            return True
        if related is None:
            keys = spec.get('field_ids', [])
            if not keys:
                keys = [spec.get('source'), spec.get('target')]
            related = [self._fields[k] for k in keys if k in self._fields and k != field.get('id')]
        if isinstance(related, dict):
            related = [related]
        others = [self._fields.get(f) if isinstance(f, str) else f for f in (related or [])]
        others = [f for f in others if isinstance(f, dict) and f.get('id') != field.get('id')]
        rects = [rect]+[r for f in others if (r := self.local_rect_to_scene(f.get('rect'))) is not None]
        if name in ('group', 'contains', 'owner', 'owned_by', 'shares_reference','relative_position') and len(rects) > 1:
            union = QRectF(rect)
            for r in rects:
                union = union.united(r)
                self._measurement_rect(r, '', '#2563eb')
            caption = '群組範圍（量測）' if name in ('group','contains') else '相對位置候選（不代表規則）' if name=='relative_position' else '共同歸屬／共享'
            self._measurement_rect(union,caption,'#7c3aed',True)
            return True
        if name in ('gap', 'gap_to') and len(rects) > 1:
            a, b = rects[:2]
            if a.right() <= b.left() or b.right() <= a.left():
                a, b = sorted([a,b], key=lambda r:r.left())
                y = (a.center().y()+b.center().y())/2
                self._dimension(QPointF(a.right(), y), QPointF(b.left(), y), f'水平間距 {b.left()-a.right():.4g} mm')
            elif a.bottom() <= b.top() or b.bottom() <= a.top():
                a, b = sorted([a,b], key=lambda r:r.top())
                x = (a.center().x()+b.center().x())/2
                self._dimension(QPointF(x,a.bottom()), QPointF(x,b.top()), f'垂直間距 {b.top()-a.bottom():.4g} mm')
            else:
                self.statusMessage.emit('這兩個範圍相交，沒有分離的邊界間距。')
                return False
            for r in rects[:2]:
                self._measurement_rect(r, '', '#2563eb')
            return True
        if name in ('alignment', 'aligned_to') and len(rects) > 1:
            alignment = spec.get('alignment', spec.get('anchor'))
            if alignment in ('left', 'right', 'center'):
                values = [r.left() if alignment=='left' else r.right() if alignment=='right' else r.center().x() for r in rects]
                x = values[0]
                self._line(QPointF(x,min(r.top() for r in rects)-offset), QPointF(x,max(r.bottom() for r in rects)+offset), '#0f766e', True)
            elif alignment in ('top', 'bottom', 'middle'):
                values = [r.top() if alignment=='top' else r.bottom() if alignment=='bottom' else r.center().y() for r in rects]
                y = values[0]
                self._line(QPointF(min(r.left() for r in rects)-offset,y), QPointF(max(r.right() for r in rects)+offset,y), '#0f766e', True)
            else:
                self.statusMessage.emit('尚未指定切齊錨點，請先核對關係。')
                return False
            for r in rects:
                self._measurement_rect(r, '', '#2563eb')
            self._text(f'切齊偏差 {max(values)-min(values):.4g} mm', rect.topLeft()-QPointF(0,offset), '#0f766e')
            return True
        if name in ('distribution', 'distributed'):
            distribution = measurements.get('distribution', {})
            if isinstance(distribution, dict) and distribution.get('status') != 'UNKNOWN':
                units = distribution.get('units', [])
                known = [r for unit in units if (r := self.local_rect_to_scene(unit.get('rect'))) is not None]
                if len(known) >= 2:
                    known.sort(key=lambda r:r.left())
                    for r in known:
                        self._measurement_rect(r, '', '#0f766e')
                    for a,b in zip(known,known[1:]):
                        self._dimension(QPointF(a.right(),a.bottom()+offset),QPointF(b.left(),a.bottom()+offset),f'{b.left()-a.right():.4g} mm')
                    self._text('分散單位與實際間隙',known[0].topLeft()-QPointF(0,offset),'#0f766e')
                    return True
            self.statusMessage.emit('分散單位與間隙尚未取得，不能由總寬猜測。')
            return False
        self.statusMessage.emit('這項關係缺少對象或量測依據，請先核對。')
        return False

    def _bounded(self, point):
        return QPointF(min(max(point.x(),self._crop.left()),self._crop.right()), min(max(point.y(),self._crop.top()),self._crop.bottom()))

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton or self.image_item is None:
            return super().mousePressEvent(event)
        point = self.mapToScene(event.position().toPoint())
        if self._mode == 'add' and self._crop.contains(point):
            self._start = self._bounded(point)
            self._rubber = self.scene().addRect(QRectF(point,point),_pen('#2563eb',2,True),QColor(37,99,235,15))
            self._rubber.setZValue(50)
            event.accept()
            return
        if self._mode == 'resize' and self.selected_id in self.field_items and self._visible:
            rect = self.field_items[self.selected_id].rect()
            pairs = [(rect.topLeft(),rect.bottomRight()),(rect.topRight(),rect.bottomLeft()),(rect.bottomLeft(),rect.topRight()),(rect.bottomRight(),rect.topLeft())]
            for corner,opposite in pairs:
                delta = self.mapFromScene(corner)-event.position().toPoint()
                if abs(delta.x()) <= 12 and abs(delta.y()) <= 12:
                    self._resize_id = self.selected_id
                    self._opposite = opposite
                    event.accept()
                    return
        if self._visible:
            # View hit-testing supplies the device transform. Scene-only
            # hit-testing incorrectly treats fixed-pixel captions as mm-wide.
            for item in self.items(event.position().toPoint()):
                field_id = item.data(0)
                if field_id in self.field_items:
                    multi = bool(event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier))
                    if multi:
                        if field_id in self._selected_ids:
                            self._selected_ids.remove(field_id)
                        else:
                            self._selected_ids.append(field_id)
                        self.selected_id = self._selected_ids[-1] if self._selected_ids else None
                        self.clear_measurement()
                        self._style_selection()
                    else:
                        self._selected_ids = [field_id]
                        self.select_field(field_id)
                    self.fieldsSelected.emit(self.selected_fields())
                    if self.selected_id is not None:
                        self.fieldSelected.emit(self.selected_id)
                    event.accept()
                    return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        point = self._bounded(self.mapToScene(event.position().toPoint()))
        if self._rubber is not None and self._start is not None:
            self._rubber.setRect(QRectF(self._start,point).normalized())
            event.accept()
            return
        if self._resize_id is not None:
            rect = QRectF(self._opposite,point).normalized()
            self.field_items[self._resize_id].setRect(rect)
            for handle,corner in zip(self._handles,[rect.topLeft(),rect.topRight(),rect.bottomLeft(),rect.bottomRight()]):
                handle.setPos(corner)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._rubber is not None:
            point = self._bounded(self.mapToScene(event.position().toPoint()))
            rect = QRectF(self._start,point).normalized()
            self.scene().removeItem(self._rubber)
            self._rubber = None
            self._start = None
            if rect.width() >= .05 and rect.height() >= .05:
                self.annotationAdded.emit(_as_dict(rect.translated(-self._crop.topLeft())))
            event.accept()
            return
        if self._resize_id is not None:
            key = self._resize_id
            point = self._bounded(self.mapToScene(event.position().toPoint()))
            rect = QRectF(self._opposite,point).normalized()
            self.field_items[key].setRect(rect)
            self._resize_id = None
            self._opposite = None
            if rect.width() >= .05 and rect.height() >= .05:
                local = _as_dict(rect.translated(-self._crop.topLeft()))
                self._fields[key]['rect'] = local
                self.annotationResized.emit(key,local)
            else:
                self.field_items[key].setRect(self.local_rect_to_scene(self._fields[key]['rect']))
            self._style_selection()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        self.zoom(1.15 if event.angleDelta().y()>0 else 1/1.15)
        event.accept()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._auto_fit and not self._crop.isEmpty():
            self.fit_work()
