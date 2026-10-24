"""
Nixi Chat Drawer — Ultra-Glassmorphism Edition
Slide-down glassmorphism panel with native Windows Acrylic blur,
deep drop shadows, translucent message bubbles, and rich typography.
"""
from __future__ import annotations

import os
from typing import Optional
from PyQt6.QtCore import Qt, QPoint, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QFrame, QGraphicsDropShadowEffect
)
from .styles import DRAWER_STYLE
from .blur_effect import apply_glassmorphism

class ChatBubble(QFrame):
    def __init__(self, text: str, is_user: bool = False):
        super().__init__()
        self.setObjectName("UserBubble" if is_user else "AiBubble")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        if not is_user:
            header_layout = QHBoxLayout()
            header_layout.setContentsMargins(0, 0, 0, 2)
            nixi_tag = QLabel("✦ Nixi")
            nixi_tag.setStyleSheet("color: #818CF8; font-size: 11px; font-weight: 700; background: transparent;")
            header_layout.addWidget(nixi_tag)
            header_layout.addStretch()
            layout.addLayout(header_layout)

        label = QLabel(text)
        label.setObjectName("UserBubbleText" if is_user else "AiBubbleText")
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(label)


class ChatDrawer(QWidget):
    send_message_signal = pyqtSignal(str)
    quick_action_signal = pyqtSignal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet(DRAWER_STYLE)
        
        self.drawer_width = 460
        self.drawer_height = 540
        self.setFixedSize(self.drawer_width, self.drawer_height)

        self._build_ui()

    def showEvent(self, event):
        super().showEvent(event)
        # Apply native Windows Acrylic blur
        apply_glassmorphism(int(self.winId()))

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        self.container = QWidget()
        self.container.setObjectName("DrawerContainer")

        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(18, 16, 18, 18)
        container_layout.setSpacing(12)

        # Header
        header = QHBoxLayout()
        header.setSpacing(8)

        title = QLabel("✦ Nixi Intelligence")
        title.setObjectName("DrawerTitle")
        header.addWidget(title)

        model_name = os.getenv("FREELLMAPI_MODEL", "kilo-auto/free")
        badge = QLabel(model_name)
        badge.setObjectName("ModelBadge")
        header.addWidget(badge)

        header.addStretch()

        clear_btn = QPushButton("Clear")
        clear_btn.setObjectName("HeaderBtn")
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.clicked.connect(self.clear_chat)
        header.addWidget(clear_btn)

        close_btn = QPushButton("✕")
        close_btn.setObjectName("HeaderBtn")
        close_btn.setFixedSize(26, 26)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.hide)
        header.addWidget(close_btn)

        container_layout.addLayout(header)

        # Scroll area for messages — strictly transparent!
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.scroll.viewport().setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.scroll.viewport().setAutoFillBackground(False)
        self.scroll.setStyleSheet("background: transparent !important; border: none;")

        self.messages_widget = QWidget()
        self.messages_widget.setObjectName("MessagesWidget")
        self.messages_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.messages_widget.setStyleSheet("background: transparent !important;")

        self.messages_layout = QVBoxLayout(self.messages_widget)
        self.messages_layout.setContentsMargins(4, 4, 4, 4)
        self.messages_layout.setSpacing(12)
        self.messages_layout.addStretch()

        self.scroll.setWidget(self.messages_widget)
        container_layout.addWidget(self.scroll)

        # Quick action chips
        chips_layout = QHBoxLayout()
        chips_layout.setSpacing(8)
        quick_actions = [
            ("👁️ Screen", "read screen"),
            ("✍️ Dictate", "toggle dictation"),
            ("⏱️ 5m Timer", "set timer for 5 minutes"),
            ("🚀 Chrome", "open chrome"),
        ]
        for label_text, cmd_text in quick_actions:
            chip = QPushButton(label_text)
            chip.setObjectName("QuickChip")
            chip.setCursor(Qt.CursorShape.PointingHandCursor)
            chip.clicked.connect(lambda checked, c=cmd_text: self.quick_action_signal.emit(c))
            chips_layout.addWidget(chip)
        container_layout.addLayout(chips_layout)

        # Input row
        input_layout = QHBoxLayout()
        input_layout.setSpacing(10)

        self.input_field = QLineEdit()
        self.input_field.setObjectName("ChatInput")
        self.input_field.setPlaceholderText("Ask Nixi anything or speak...")
        self.input_field.returnPressed.connect(self._on_send)
        input_layout.addWidget(self.input_field)

        send_btn = QPushButton("Send")
        send_btn.setObjectName("SendButton")
        send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        send_btn.clicked.connect(self._on_send)
        input_layout.addWidget(send_btn)

        container_layout.addLayout(input_layout)
        root.addWidget(self.container)

        # Welcome message
        self.add_message("Hello! I'm Nixi. I live in your top bar and can dictate into any app, read your screen, open apps, and answer any questions.", is_user=False)

    def _on_send(self):
        text = self.input_field.text().strip()
        if not text:
            return
        self.input_field.clear()
        self.add_message(text, is_user=True)
        self.send_message_signal.emit(text)

    def add_message(self, text: str, is_user: bool = False) -> ChatBubble:
        bubble = ChatBubble(text, is_user=is_user)
        count = self.messages_layout.count()
        self.messages_layout.insertWidget(count - 1, bubble)
        self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum())
        return bubble

    def clear_chat(self):
        while self.messages_layout.count() > 1:
            item = self.messages_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def position_below_pill(self, pill_geometry):
        """Align drawer directly below the floating pill."""
        x = pill_geometry.center().x() - (self.width() // 2)
        y = pill_geometry.bottom() + 8
        self.move(x, y)
