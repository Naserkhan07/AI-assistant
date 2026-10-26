"""Small task-center dialog for active and recent Nixi operations."""
from __future__ import annotations

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout


class TaskCenterDialog(QDialog):
    def __init__(self, provider, cancel_callback, parent=None):
        super().__init__(parent)
        self.provider = provider
        self.cancel_callback = cancel_callback
        self.setWindowTitle("Nixi Task Center")
        self.setMinimumSize(470, 340)
        layout = QVBoxLayout(self)
        self.summary = QLabel("Active and recent operations")
        layout.addWidget(self.summary)
        self.list = QListWidget()
        layout.addWidget(self.list, 1)
        buttons = QHBoxLayout()
        cancel = QPushButton("Cancel selected task")
        cancel.clicked.connect(self.cancel_selected)
        buttons.addWidget(cancel)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh)
        buttons.addWidget(refresh)
        buttons.addStretch(1)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        buttons.addWidget(close)
        layout.addLayout(buttons)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(750)
        self.refresh()

    def refresh(self):
        try:
            tasks = self.provider() or []
        except Exception:
            tasks = []
        self.list.clear()
        active = 0
        for task in tasks:
            state = task.get("state", "unknown")
            active += state == "active"
            text = f"{state.upper():10}  {task.get('title', 'Task')}\n{task.get('detail', '')}"
            if task.get("result") and state != "active":
                text += f"\n{task['result'][:240]}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, task.get("task_id"))
            self.list.addItem(item)
        self.summary.setText(f"{active} active · {len(tasks) - active} recent")

    def cancel_selected(self):
        item = self.list.currentItem()
        task_id = item.data(Qt.ItemDataRole.UserRole) if item else None
        if task_id:
            self.cancel_callback(task_id)
            self.refresh()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            item = self.list.currentItem()
            task_id = item.data(Qt.ItemDataRole.UserRole) if item else None
            if task_id:
                self.cancel_callback(task_id)
                self.refresh()
                return
        super().keyPressEvent(event)
