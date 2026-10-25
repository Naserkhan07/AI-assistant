"""Command palette — quick fuzzy search over actions (Ctrl+K)."""
from __future__ import annotations

try:
    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem
    from PyQt6.QtCore import Qt, pyqtSignal
    HAS_QT = True
except ImportError:
    HAS_QT = False


class CommandPalette:
    def __init__(self, actions: list[dict] | None = None, on_selected=None, parent=None):
        self.actions = actions or []
        self.on_selected = on_selected
        self.parent = parent
        self._dialog = None
        if HAS_QT:
            self._build()

    def _build(self) -> None:
        from PyQt6.QtWidgets import QDialog
        d = QDialog(self.parent)
        d.setWindowTitle("Command Palette")
        d.resize(480, 340)
        layout = QVBoxLayout(d)
        self.input = QLineEdit()
        self.input.setPlaceholderText("Type a command...")
        layout.addWidget(self.input)
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)
        self._populate("")
        self.input.textChanged.connect(self._populate)
        self.input.returnPressed.connect(self._activate)
        self.list_widget.itemDoubleClicked.connect(lambda _: self._activate())
        self._dialog = d

    def _populate(self, query: str = "") -> None:
        if not HAS_QT:
            return
        q = (query or "").lower()
        self.list_widget.clear()
        for action in self.actions:
            label = action.get("label", action.get("name", ""))
            if q and q not in label.lower() and q not in action.get("description", "").lower():
                continue
            from PyQt6.QtWidgets import QListWidgetItem
            item = QListWidgetItem(f"{label}  —  {action.get('description','')}")
            item.setData(256, action)
            self.list_widget.addItem(item)

    def _activate(self) -> None:
        item = self.list_widget.currentItem()
        if not item:
            if self.list_widget.count() > 0:
                item = self.list_widget.item(0)
            else:
                return
        action = item.data(256)
        if self.on_selected:
            self.on_selected(action)
        if self._dialog:
            self._dialog.accept()

    def set_actions(self, actions: list[dict]) -> None:
        self.actions = actions
        if HAS_QT and self._dialog:
            self._populate(self.input.text() if hasattr(self, 'input') else "")

    def exec(self) -> int:
        if not HAS_QT or not self._dialog:
            return 0
        return self._dialog.exec()

    def show(self) -> None:
        if self._dialog:
            self._dialog.show()
