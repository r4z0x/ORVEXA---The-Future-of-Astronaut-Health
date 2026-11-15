"""Native Qt components: icons, metric cards, orbital hero and painted charts."""
from pathlib import Path
from functools import lru_cache
from PySide6.QtCore import Qt, QSize, QRectF, QPointF, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap, QIcon, QLinearGradient, QFont, QBrush
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QWidget, QLabel, QFrame, QPushButton, QHBoxLayout, QVBoxLayout, QSizePolicy
from .charts import plot_samples

ASSETS = Path(__file__).resolve().parent.parent / 'assets'
CYAN = '#54d8f4'
ICONS = {
 'grid': '<rect x="3" y="3" width="7" height="7" rx="1.4"/><rect x="14" y="3" width="7" height="7" rx="1.4"/><rect x="3" y="14" width="7" height="7" rx="1.4"/><rect x="14" y="14" width="7" height="7" rx="1.4"/>',
 'pulse': '<path d="M2 12h5l3-8 4 16 3-8h5"/>',
 'spark': '<path d="m12 3 2.4 6.6L21 12l-6.6 2.4L12 21l-2.4-6.6L3 12l6.6-2.4L12 3ZM20 2v4m-2-2h4"/>',
 'dumbbell': '<path d="m7 7 10 10M4 11l7-7M13 20l7-7M2 8l6-6m8 20 6-6M3 6l3-3m12 18 3-3"/>',
 'file': '<path d="M14 3H5v18h14V8l-5-5Zm0 0v6h5M8 13h8m-8 4h6"/>',
 'gear': '<path d="m9 3-1 3-3 1-2 4 2 2 1 4 3 1 2 3 4-1 1-3 3-1 2-4-2-2-1-4-3-1-2-3-4 1Z"/><circle cx="12" cy="12" r="3"/>',
 'heart': '<path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z"/>',
 'drop': '<path d="M12 2S4 11 4 15a8 8 0 0 0 16 0c0-4-8-13-8-13Z"/><path d="M8 15a4 4 0 0 0 4 4"/>',
 'temp': '<path d="M9 14.5V5a3 3 0 0 1 6 0v9.5a5 5 0 1 1-6 0Z"/><path d="M12 8v10"/>',
 'moon': '<path d="M21 13a9 9 0 0 1-10-10A9 9 0 1 0 21 13Z"/>',
 'check': '<path d="m5 12 4 4L19 6"/>',
 'clock': '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
 'plus': '<path d="M12 5v14M5 12h14"/>',
 'arrow': '<path d="M4 12h16m-6-6 6 6-6 6"/>',
 'play': '<path d="m8 4 12 8-12 8V4Z"/>',
 'pause': '<path d="M8 4v16M16 4v16"/>',
 'shield': '<path d="m12 2 8 4v6c0 5-8 10-8 10S4 17 4 12V6l8-4Z"/><path d="m8 12 3 3 5-6"/>',
 'cycle': '<circle cx="5" cy="17" r="4"/><circle cx="19" cy="17" r="4"/><path d="m5 17 5-9 9 9H5l8-12h3M7 5h5"/>',
 'move': '<circle cx="14" cy="4" r="2"/><path d="m10 9 5-2 2 5 4 1M4 13l5-2 4 3-3 7m3-7 5 5M9 11l1-2"/>',
 'download': '<path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/>',
 'help': '<circle cx="12" cy="12" r="9"/><path d="M9 9a3 3 0 0 1 6 0c0 2-3 2-3 5m0 3h.01"/>',
}

@lru_cache(maxsize=128)
def make_icon(name, color='#8b9eb5', size=24):
    markup = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round">{ICONS.get(name, ICONS["spark"])}</svg>'
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    QSvgRenderer(markup.encode()).render(painter)
    painter.end()
    return QIcon(pix)

@lru_cache(maxsize=4)
def asset_pixmap(name):
    return QPixmap(str(ASSETS / name))

def label(text, size=12, color='#d7e4f1', bold=False, wrap=False):
    widget = QLabel(str(text))
    widget.setTextFormat(Qt.TextFormat.PlainText)
    widget.setWordWrap(wrap)
    widget.setStyleSheet(f'color:{color};font-size:{size}px;font-weight:{600 if bold else 400};background:transparent;border:none;')
    return widget

def button(text, callback=None, icon=None, primary=False, secondary=False):
    widget = QPushButton(text)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    widget.setMinimumHeight(35)
    if primary:
        widget.setProperty('kind', 'primary')
    if secondary:
        widget.setProperty('kind', 'secondary')
    if icon:
        widget.setIcon(make_icon(icon, '#08212d' if primary else '#9cb5cb', 18))
        widget.setIconSize(QSize(16, 16))
    if callback:
        widget.clicked.connect(lambda checked=False: callback())
    return widget

def row(*widgets, spacing=12):
    layout = QHBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(spacing)
    for widget in widgets:
        if widget is None:
            layout.addStretch()
        elif isinstance(widget, (QHBoxLayout, QVBoxLayout)):
            layout.addLayout(widget)
        else:
            layout.addWidget(widget)
    return layout

class Card(QFrame):
    def __init__(self, parent=None, padding=20):
        super().__init__(parent)
        self.setObjectName('Card')
        self.box = QVBoxLayout(self)
        self.box.setContentsMargins(padding, padding, padding, padding)
        self.box.setSpacing(12)

class Hero(QWidget):
    def __init__(self, name, concerns=False, parent=None):
        super().__init__(parent)
        self.setFixedHeight(212)
        self.image = asset_pixmap('earth.jpg')
        self.scaled_image = None
        self.scaled_size = None
        box = QVBoxLayout(self)
        box.setContentsMargins(29, 23, 29, 23)
        box.setSpacing(7)
        box.addWidget(label('ISS  /  EXPEDITION 84  /  DAY 143 · SAMPLE MISSION', 9, '#86c5df'))
        box.addSpacing(4)
        box.addWidget(label('Welcome aboard,', 25, '#f0f8ff'))
        box.addWidget(label((name.split()[0] if name.split() else 'Crew Member') + '.', 25, '#f0f8ff'))
        box.addWidget(label('Every great mission begins with taking care of yourself.', 11, '#9db4cc'))
        box.addSpacing(4)
        self.pill = label('●  MEDICAL REVIEW REQUIRED' if concerns else '●  PERSONALIZED ORBITAL SUPPORT', 9, '#e4bd86' if concerns else '#6bdcba')
        self.pill.setStyleSheet(self.pill.styleSheet() + 'padding:6px 10px;border:1px solid #2b5a51;border-radius:12px;background:#102d2ba0;')
        self.pill.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        box.addWidget(self.pill)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(.5, .5, -.5, -.5)
        path = QPainterPath()
        path.addRoundedRect(rect, 12, 12)
        p.setClipPath(path)
        p.fillPath(path, QColor('#0c2035'))
        if not self.image.isNull():
            if self.scaled_size != self.size():
                self.scaled_image = self.image.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                self.scaled_size = self.size()
            p.drawPixmap(0, (self.height() - self.scaled_image.height()) // 2, self.scaled_image)
        grad = QLinearGradient(0, 0, self.width(), 0)
        grad.setColorAt(0, QColor('#0e2034'))
        grad.setColorAt(.35, QColor(14, 32, 52, 235))
        grad.setColorAt(.75, QColor(14, 32, 52, 40))
        grad.setColorAt(1, QColor(14, 32, 52, 10))
        p.fillRect(self.rect(), grad)
        p.setPen(QPen(QColor(150, 210, 240, 45), 1))
        orbit = QRectF(self.width()-230, 16, 180, 180)
        p.drawEllipse(orbit)
        p.setPen(QPen(QColor(150, 210, 240, 60), 1, Qt.PenStyle.DashLine))
        p.drawEllipse(orbit.adjusted(17, 17, -17, -17))
        p.setBrush(QColor('#96e7ff'))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(self.width()-80, 40), 3.5, 3.5)
        p.setPen(QColor('#bad4e6'))
        p.setFont(QFont('Golos Text', 7))
        p.drawText(QRectF(self.width()-220, self.height()-43, 195, 30), Qt.AlignmentFlag.AlignRight, '408 KM ABOVE EARTH\nLOW EARTH ORBIT')
        p.setClipping(False)
        p.setPen(QPen(QColor('#294052'), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect, 12, 12)

class Sparkline(QWidget):
    def __init__(self, values, color=CYAN, parent=None):
        super().__init__(parent)
        self.samples = plot_samples(values, limit=80)
        self.values = [value for _, value in self.samples]
        self.color = color
        self.setMinimumSize(55, 30)
        self.setMaximumHeight(36)

    def paintEvent(self, event):
        if not self.values:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        low, high = min(self.values), max(self.values)
        span = max(high-low, .1)
        pts = [QPointF(3+x*(self.width()-6), self.height()-6-(v-low)/span*(self.height()-13)) for x,v in self.samples]
        path = QPainterPath(pts[0])
        for point in pts[1:]:
            path.lineTo(point)
        p.setPen(QPen(QColor(self.color), 1.5))
        p.drawPath(path)
        p.setBrush(QColor(self.color))
        p.drawEllipse(pts[-1], 2, 2)

class MetricCard(Card):
    clicked = Signal()
    def __init__(self, title, value, unit, baseline, icon_name, color, values, note, warning=False):
        super().__init__(padding=17)
        self.setMinimumHeight(153)
        self.setMinimumWidth(160)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.box.setSpacing(9)
        ic = QLabel()
        ic.setPixmap(make_icon(icon_name, color, 21).pixmap(21,21))
        status = label('●  '+note, 8, '#d8b47a' if warning else '#5ccba9')
        self.box.addLayout(row(ic, None, status))
        self.box.addWidget(label(title, 10, '#92a5bb'))
        values_row = QHBoxLayout()
        values_row.setContentsMargins(0,0,0,0)
        values_row.setSpacing(4)
        values_row.addWidget(label(value, 29, '#edf6ff'))
        values_row.addWidget(label(unit, 10, '#8fa4b9'), alignment=Qt.AlignmentFlag.AlignBottom)
        values_row.addStretch()
        spark = Sparkline(values, color)
        spark.setFixedWidth(65)
        values_row.addWidget(spark)
        self.box.addLayout(values_row)
        self.box.addWidget(label(baseline, 8, '#71879e'))

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)

class HealthChart(QWidget):
    def __init__(self, values, labels, baseline=61, unit='bpm', demo=True, parent=None, timestamps=None):
        super().__init__(parent)
        self.values = values
        self.labels = labels
        self.baseline = baseline
        self.unit = unit
        self.demo = demo
        self.samples = plot_samples(values, timestamps, limit=600)
        spread = max(max(values)-min(values), 4 if unit=='bpm' else .5) if values else 4
        self.low = min(min(values), baseline) - spread*.45 if values else baseline-spread
        self.high = max(max(values), baseline) + spread*.45 if values else baseline+spread
        self.setMinimumHeight(175)
        self.setMinimumWidth(320)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Expanding)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        left, top, right, bottom = 34, 16, self.width()-13, self.height()-30
        low, high = self.low, self.high
        y = lambda v: bottom-(v-low)/(high-low)*(bottom-top)
        p.setFont(QFont('Golos Text', 7))
        for i in range(4):
            yy = top+i*(bottom-top)/3
            p.setPen(QPen(QColor('#223348'),1,Qt.PenStyle.DotLine))
            p.drawLine(QPointF(left,yy),QPointF(right,yy))
            p.setPen(QColor('#71859c'))
            val = high-i*(high-low)/3
            p.drawText(QRectF(0, yy-6, 29, 14), Qt.AlignmentFlag.AlignRight, f'{val:.0f}' if self.unit in ('bpm','%') else f'{val:.1f}')
        p.setPen(QPen(QColor('#496779'),1,Qt.PenStyle.DashLine))
        p.drawLine(QPointF(left,y(self.baseline)),QPointF(right,y(self.baseline)))
        if not self.samples:
            p.setPen(QColor('#829fb6'))
            p.drawText(QRectF(left,top,right-left,bottom-top),Qt.AlignmentFlag.AlignCenter,'No measurements for the selected period')
            return
        points = [QPointF(left+x*(right-left),y(value)) for x,value in self.samples]
        path = QPainterPath(points[0])
        for point in points[1:]:
            path.lineTo(point)
        if len(points)>1:
            area = QPainterPath(path)
            area.lineTo(points[-1].x(),bottom)
            area.lineTo(points[0].x(),bottom)
            area.closeSubpath()
            gradient=QLinearGradient(0,top,0,bottom)
            gradient.setColorAt(0,QColor(61,200,232,50))
            gradient.setColorAt(1,QColor(61,200,232,0))
            p.fillPath(area,QBrush(gradient))
        p.setPen(QPen(QColor(CYAN),2))
        p.drawPath(path)
        p.setBrush(QColor('#91e9ff'))
        p.drawEllipse(points[-1],3,3)
        p.setPen(QColor('#698299'))
        labels = self.labels
        for i,tick in enumerate(labels):
            position,text = tick if isinstance(tick,tuple) else (i/max(1,len(labels)-1),tick)
            xx = left+position*(right-left) if len(labels)>1 else (left+right)/2
            alignment = Qt.AlignmentFlag.AlignCenter
            xx = max(35,min(xx,self.width()-40))
            p.drawText(QRectF(xx-38,bottom+10,76,15),alignment,str(text))
