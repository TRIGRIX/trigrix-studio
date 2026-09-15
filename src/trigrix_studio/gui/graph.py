from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QByteArray, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QDrag, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QAbstractItemView, QGraphicsEllipseItem, QGraphicsItem, QGraphicsPathItem,
    QGraphicsRectItem, QGraphicsScene, QGraphicsTextItem, QGraphicsView,
    QTreeWidget, QTreeWidgetItem,
)

from trigrix_studio.nodes import NODE_REGISTRY
from trigrix_studio.i18n import tr, template_text
from trigrix_studio.project.models import BotProject, Edge, Node

NODE_MIME = "application/x-trigrix-node"

CATEGORY_KEYS = {
    'Triggers.': "triggers", 'Communications': "messages", 'Buttons and menus': "buttons",
    'User input': "input", 'Logic.': "logic", "Variables": "variables",
    "Telegram": "telegram", "Integrations": "integrations",
    'Service blocks': "service", 'Applications': "leads",
}


def node_title(node_type: str, locale: str, fallback: str) -> str:
    return tr(f"node.{node_type}", locale) if NODE_REGISTRY.get(node_type) else fallback


def localized_defaults(value, locale: str):
    if isinstance(value, dict):
        return {key: localized_defaults(item, locale) for key, item in value.items()}
    if isinstance(value, list):
        return [localized_defaults(item, locale) for item in value]
    if isinstance(value, str):
        return template_text(value, locale)
    return value


class NodeLibrary(QTreeWidget):
    def __init__(self, locale: str = "en-US") -> None:
        super().__init__()
        self.locale = locale
        self.setHeaderHidden(True)
        self.setDragEnabled(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setToolTip(tr("graph.drag_block", locale))
        for category, definitions in NODE_REGISTRY.categories().items():
            parent = QTreeWidgetItem([tr(f"node.category.{CATEGORY_KEYS.get(category, category)}", locale)])
            parent.setFlags(parent.flags() & ~Qt.ItemFlag.ItemIsDragEnabled)
            self.addTopLevelItem(parent)
            for definition in definitions:
                title = node_title(definition.type, locale, definition.title)
                child = QTreeWidgetItem([title])
                child.setData(0, Qt.ItemDataRole.UserRole, definition.type)
                child.setToolTip(0, tr("graph.drag_named", locale, title=title))
                parent.addChild(child)
            parent.setExpanded(True)

    def startDrag(self, supported_actions: Qt.DropAction) -> None:
        item = self.currentItem()
        if not item or not item.data(0, Qt.ItemDataRole.UserRole):
            return
        drag = QDrag(self)
        mime = self.mimeData([item])
        mime.setData(NODE_MIME, QByteArray(str(item.data(0, Qt.ItemDataRole.UserRole)).encode()))
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.CopyAction)


class PortItem(QGraphicsEllipseItem):
    SIZE = 13.0

    def __init__(self, parent: "NodeItem", port: str, label: str, *, input_port: bool = False) -> None:
        super().__init__(-self.SIZE / 2, -self.SIZE / 2, self.SIZE, self.SIZE, parent)
        self.node_item, self.port, self.label, self.input_port = parent, port, label, input_port
        self.setZValue(5)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.CrossCursor if not input_port else Qt.CursorShape.PointingHandCursor)
        self.setBrush(QColor("#8B93A8") if input_port else parent.color)
        self.setPen(QPen(QColor("#E9ECF4"), 1.2))
        locale = parent.locale
        self.setToolTip(tr("graph.input", locale) if input_port else tr("graph.drag_output", locale, label=label))

    def mousePressEvent(self, event) -> None:
        if not self.input_port and isinstance(self.scene(), GraphScene):
            self.scene().begin_connection(self, event.scenePos()); event.accept(); return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if not self.input_port and isinstance(self.scene(), GraphScene):
            self.scene().move_connection(event.scenePos()); event.accept(); return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if not self.input_port and isinstance(self.scene(), GraphScene):
            self.scene().finish_connection(event.scenePos()); event.accept(); return
        super().mouseReleaseEvent(event)


class AddOptionItem(QGraphicsRectItem):
    def __init__(self, parent: "NodeItem", y: float) -> None:
        super().__init__(12, y, parent.WIDTH - 24, 25, parent)
        self.node_item = parent
        self.setBrush(QColor("#202534")); self.setPen(QPen(QColor("#414A62"), 1, Qt.PenStyle.DashLine))
        self.setCursor(Qt.CursorShape.PointingHandCursor); self.setToolTip(tr("graph.add_option", parent.locale))
        text = QGraphicsTextItem("＋ " + tr("graph.add_option", parent.locale), self)
        text.setDefaultTextColor(QColor("#C9CEE0")); text.setPos(8, 1)

    def mousePressEvent(self, event) -> None:
        if isinstance(self.scene(), GraphScene):
            self.scene().request_add_option(self.node_item.node)
        event.accept()


class EdgeItem(QGraphicsPathItem):
    def __init__(self, edge: Edge, source: "NodeItem", target: "NodeItem") -> None:
        super().__init__()
        self.edge, self.source, self.target = edge, source, target
        self.setZValue(-2)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.update_path()

    def update_path(self) -> None:
        start = self.source.output_scene_position(self.edge.source_port)
        end = self.target.input_scene_position()
        path = QPainterPath(start)
        dx = max(70.0, abs(end.x() - start.x()) * 0.5)
        path.cubicTo(start + QPointF(dx, 0), end - QPointF(dx, 0), end)
        self.setPath(path)
        self.setPen(QPen(QColor("#FF637D" if self.isSelected() else "#66708A"), 3 if self.isSelected() else 2))
        self.setToolTip(f"{self.source.node.title}: {self.edge.source_port} → {self.target.node.title}")


class NodeItem(QGraphicsRectItem):
    WIDTH, HEADER, ROW = 282.0, 64.0, 26.0

    def __init__(self, node: Node, project: BotProject, on_change: Callable[[Node], None], locale: str = "en-US") -> None:
        self.node, self.project, self.on_change, self.locale = node, project, on_change, locale
        definition = NODE_REGISTRY.get(node.type)
        self.color = QColor(definition.color if definition else "#6C63FF")
        self.output_ports: dict[str, PortItem] = {}
        rows = self._rows()
        height = max(94.0, self.HEADER + len(rows) * self.ROW + (35 if node.type == "menu" else 10))
        super().__init__(0, 0, self.WIDTH, height)
        self.setPos(node.position.x, node.position.y)
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)
        self.title_item = QGraphicsTextItem(node.title, self)
        self.title_item.setDefaultTextColor(QColor("white")); font = QFont(); font.setBold(True); self.title_item.setFont(font)
        self.title_item.setTextWidth(self.WIDTH - 34); self.title_item.setPos(14, 8)
        self.type_item = QGraphicsTextItem(node_title(node.type, locale, definition.title if definition else node.type), self)
        self.type_item.setDefaultTextColor(QColor("#AEB6CA")); self.type_item.setPos(14, 35)
        self.port_in = PortItem(self, "in", tr("graph.input", locale), input_port=True); self.port_in.setPos(0, self.HEADER / 2)
        self._build_rows(rows)

    def _rows(self) -> list[tuple[str | None, str, bool]]:
        settings = self.node.settings
        if self.node.type == "menu":
            return [(str(b.get("id", f"option_{i + 1}")), str(b.get("text", 'Option')), b.get("type", "transition") != "url") for i, b in enumerate(settings.get("buttons", []))]
        if self.node.type == "switch":
            return [(str(case), str(case), True) for case in settings.get("cases", [])] + [("default", tr("graph.otherwise", self.locale), True)]
        if self.node.type == "condition":
            return [("true", tr("graph.yes", self.locale), True), ("false", tr("graph.no", self.locale), True)]
        if self.node.type == "dictionary_select":
            dictionary = self.project.dictionary(str(settings.get("dictionary", "")))
            return [(None, record.title, False) for record in (dictionary.records if dictionary else [])] + [("next", tr("graph.after_choice", self.locale), True)]
        definition = NODE_REGISTRY.get(self.node.type)
        return [(port, tr("graph.next", self.locale) if port == "next" else port, True) for port in (definition.output_ports if definition else ("next",))]

    def _build_rows(self, rows: list[tuple[str | None, str, bool]]) -> None:
        for index, (port, label, connectable) in enumerate(rows):
            y = self.HEADER + index * self.ROW
            row = QGraphicsTextItem(("↳ " if connectable else "• ") + label, self)
            row.setDefaultTextColor(QColor("#E3E7F1") if connectable else QColor("#AEB6CA"))
            row.setTextWidth(self.WIDTH - 38); row.setPos(17, y + 1)
            if port and connectable:
                item = PortItem(self, port, label); item.setPos(self.WIDTH, y + self.ROW / 2)
                self.output_ports[port] = item
        if self.node.type == "menu":
            AddOptionItem(self, self.HEADER + len(rows) * self.ROW + 3)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor("#303650" if self.isSelected() else "#252A39"))
        painter.setPen(QPen(self.color, 3 if self.isSelected() else 1.5)); painter.drawRoundedRect(self.rect(), 9, 9)
        painter.fillRect(QRectF(0, 0, 7, self.rect().height()), self.color)
        painter.setPen(QPen(QColor("#3B4257"), 1)); painter.drawLine(9, int(self.HEADER), int(self.WIDTH - 9), int(self.HEADER))

    def input_scene_position(self) -> QPointF:
        return self.port_in.mapToScene(QPointF(0, 0))

    def output_scene_position(self, port: str) -> QPointF:
        item = self.output_ports.get(port)
        return item.mapToScene(QPointF(0, 0)) if item else self.scenePos() + QPointF(self.WIDTH, self.HEADER + self.ROW / 2)

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self.node.position.x, self.node.position.y = self.pos().x(), self.pos().y()
            self.on_change(self.node)
            if self.scene():
                for item in self.scene().items():
                    if isinstance(item, EdgeItem) and (item.source is self or item.target is self): item.update_path()
        return super().itemChange(change, value)


class GraphScene(QGraphicsScene):
    selection_node_changed = Signal(object)
    project_changed = Signal()
    add_option_requested = Signal(object)

    def __init__(self, locale: str = "en-US") -> None:
        super().__init__()
        self.locale = locale
        self.project: BotProject | None = None
        self.node_items: dict[str, NodeItem] = {}
        self._connection_port: PortItem | None = None
        self._connection_preview: QGraphicsPathItem | None = None
        self.selectionChanged.connect(self._selection_changed)
        self.setSceneRect(-1000, -1000, 8000, 5000)

    def set_project(self, project: BotProject, select_node_id: str | None = None) -> None:
        self.clear(); self.project = project; self.node_items = {}
        for node in project.nodes:
            item = NodeItem(node, project, self._node_moved, self.locale); self.node_items[node.id] = item; self.addItem(item)
        for edge in project.edges:
            source, target = self.node_items.get(edge.source), self.node_items.get(edge.target)
            if source and target: self.addItem(EdgeItem(edge, source, target))
        if select_node_id in self.node_items: self.node_items[select_node_id].setSelected(True)

    def add_node(self, node_type: str, position: QPointF) -> Node:
        if self.project is None: raise RuntimeError("Project is not set")
        definition = NODE_REGISTRY.get(node_type)
        if definition is None: raise KeyError(node_type)
        node = Node(type=node_type, title=node_title(node_type, self.locale, definition.title), position={"x": position.x(), "y": position.y()}, settings=localized_defaults(definition.default_settings(), self.locale))
        self.project.nodes.append(node)
        item = NodeItem(node, self.project, self._node_moved, self.locale); self.node_items[node.id] = item; self.addItem(item); item.setSelected(True)
        self.project_changed.emit(); return node

    def add_edge(self, source_id: str, target_id: str, port: str = "next") -> Edge:
        if self.project is None: raise RuntimeError("Project is not set")
        edge = Edge(source=source_id, source_port=port, target=target_id)
        replaced = [e for e in self.project.edges if e.source == source_id and e.source_port == port]
        self.project.edges = [e for e in self.project.edges if e not in replaced]
        for item in list(self.items()):
            if isinstance(item, EdgeItem) and item.edge in replaced: self.removeItem(item)
        self.project.edges.append(edge)
        self.addItem(EdgeItem(edge, self.node_items[source_id], self.node_items[target_id]))
        self.project_changed.emit(); return edge

    def begin_connection(self, port: PortItem, position: QPointF) -> None:
        self._connection_port = port; self._connection_preview = QGraphicsPathItem(); self._connection_preview.setZValue(-1)
        self._connection_preview.setPen(QPen(QColor("#FF637D"), 2, Qt.PenStyle.DashLine)); self.addItem(self._connection_preview); self.move_connection(position)

    def move_connection(self, position: QPointF) -> None:
        if not self._connection_port or not self._connection_preview: return
        start = self._connection_port.mapToScene(QPointF(0, 0)); path = QPainterPath(start); dx = max(60.0, abs(position.x() - start.x()) / 2)
        path.cubicTo(start + QPointF(dx, 0), position - QPointF(dx, 0), position); self._connection_preview.setPath(path)

    def finish_connection(self, position: QPointF) -> None:
        source, target = self._connection_port, None
        for item in self.items(position):
            if isinstance(item, PortItem) and item.input_port: target = item.node_item; break
            if isinstance(item, NodeItem): target = item; break
        if self._connection_preview: self.removeItem(self._connection_preview)
        self._connection_preview = None; self._connection_port = None
        if source and target and source.node_item is not target: self.add_edge(source.node_item.node.id, target.node.id, source.port)

    def request_add_option(self, node: Node) -> None: self.add_option_requested.emit(node)

    def remove_selected(self) -> None:
        if self.project is None: return
        node_ids = {item.node.id for item in self.selectedItems() if isinstance(item, NodeItem)}
        edge_ids = {item.edge.id for item in self.selectedItems() if isinstance(item, EdgeItem)}
        self.project.nodes = [node for node in self.project.nodes if node.id not in node_ids]
        self.project.edges = [edge for edge in self.project.edges if edge.id not in edge_ids and edge.source not in node_ids and edge.target not in node_ids]
        self.set_project(self.project); self.project_changed.emit()

    def selected_nodes(self) -> list[Node]: return [item.node for item in self.selectedItems() if isinstance(item, NodeItem)]
    def refresh_node(self, node_id: str) -> None:
        if self.project: self.set_project(self.project, node_id)
    def _node_moved(self, node: Node) -> None: self.project_changed.emit()
    def _selection_changed(self) -> None:
        nodes = self.selected_nodes(); self.selection_node_changed.emit(nodes[0] if len(nodes) == 1 else None)


class GraphView(QGraphicsView):
    node_dropped = Signal(str, QPointF)

    def __init__(self, scene: GraphScene) -> None:
        super().__init__(scene); self._panning = False; self._pan_start = None
        self.setAcceptDrops(True); self.setRenderHint(QPainter.RenderHint.Antialiasing); self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse); self.setBackgroundBrush(QColor("#10121A"))

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasFormat(NODE_MIME): event.acceptProposedAction()
    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasFormat(NODE_MIME): event.acceptProposedAction()
    def dropEvent(self, event) -> None:
        if event.mimeData().hasFormat(NODE_MIME):
            self.node_dropped.emit(bytes(event.mimeData().data(NODE_MIME)).decode(), self.mapToScene(event.position().toPoint())); event.acceptProposedAction()
    def wheelEvent(self, event) -> None:
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        if 0.2 < self.transform().m11() * factor < 3.0: self.scale(factor, factor)
    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = True; self._pan_start = event.position(); self.setCursor(Qt.CursorShape.ClosedHandCursor); event.accept(); return
        super().mousePressEvent(event)
    def mouseMoveEvent(self, event) -> None:
        if self._panning and self._pan_start is not None:
            delta = event.position() - self._pan_start; self._pan_start = event.position()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - int(delta.x())); self.verticalScrollBar().setValue(self.verticalScrollBar().value() - int(delta.y())); event.accept(); return
        super().mouseMoveEvent(event)
    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.MiddleButton and self._panning:
            self._panning = False; self._pan_start = None; self.unsetCursor(); event.accept(); return
        super().mouseReleaseEvent(event)
    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:
        painter.fillRect(rect, self.backgroundBrush()); step = 32
        left, top = int(rect.left()) - int(rect.left()) % step, int(rect.top()) - int(rect.top()) % step
        painter.setPen(QPen(QColor("#202432"), 1))
        for x in range(left, int(rect.right()), step): painter.drawLine(x, int(rect.top()), x, int(rect.bottom()))
        for y in range(top, int(rect.bottom()), step): painter.drawLine(int(rect.left()), y, int(rect.right()), y)
