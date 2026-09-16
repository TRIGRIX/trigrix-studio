from PySide6.QtCore import QEvent, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QGraphicsView


class GraphMinimap(QGraphicsView):
    """An independent view of the entire graph, anchored to the canvas viewport."""

    def __init__(self, scene, canvas):
        super().__init__(scene, canvas.viewport())
        self.canvas = canvas
        self.setInteractive(False)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setStyleSheet("border:1px solid #59627a; background:#151821;")
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setSingleShot(True)
        self.refresh_timer.timeout.connect(self.refresh)
        scene.changed.connect(self.schedule_refresh)
        canvas.viewport().installEventFilter(self)
        self.refresh()

    def schedule_refresh(self, *_):
        if not self.refresh_timer.isActive():
            self.refresh_timer.start(40)

    def eventFilter(self, watched, event):
        if event.type() in (QEvent.Type.Resize, QEvent.Type.Show):
            self.schedule_refresh()
        return super().eventFilter(watched, event)

    def refresh(self):
        viewport = self.canvas.viewport()
        width = min(190, max(80, viewport.width() - 32))
        self.setGeometry(max(0, viewport.width() - width - 16), 16, width, 125)
        bounds = self.scene().itemsBoundingRect()
        bounds = bounds.adjusted(-40, -40, 40, 40) if not bounds.isEmpty() else QRectF(-40, -40, 80, 80)
        # Override this view's scene rect: the editor's large workspace must not
        # dictate the overview's scroll range or centre.
        self.setSceneRect(bounds)
        self.fitInView(bounds, Qt.AspectRatioMode.KeepAspectRatio)
        self.centerOn(bounds.center())
        self.raise_()

    def drawBackground(self, painter, rect):
        painter.fillRect(rect, QColor("#151821"))
