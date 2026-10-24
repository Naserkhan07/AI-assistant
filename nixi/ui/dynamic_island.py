"""
Nixi Dynamic Island — Hover-Expandable Top Widget
Inspired by Apple Dynamic Island & HeyNixi.
Collapsed: Ultra-compact black capsule (140x40) with cute glowing animated eyes.
Expanded on hover: Smoothly animates into a full glassmorphic assistant (490x280)
with text input, mic button, screen seeing button, action chips, and live responses.
"""
from __future__ import annotations

import math
import os
import re
from typing import Optional
from PyQt6.QtCore import (
    Qt, QRect, QTimer, pyqtSignal, QPropertyAnimation, QEasingCurve, QPoint
)
from PyQt6.QtGui import (
    QPainter, QColor, QRadialGradient, QLinearGradient, QPen, QBrush, QFont, QCursor, QPainterPath
)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QToolButton, QScrollArea, QFrame, QApplication
)

from .blur_effect import apply_glassmorphism


class CuteEyesWidget(QWidget):
    """Two cute glowing animated eyes that blink periodically like HeyNixi."""
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedSize(56, 26)
        self.is_blinking = False
        self.eye_state = "happy"  # "happy", "listening", "thinking"
        self.phase = 0.0

        # Animation timer (30 FPS)
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._animate)
        self.anim_timer.start(33)

        # Periodic blink timer (every 3.5 seconds)
        self.blink_timer = QTimer(self)
        self.blink_timer.timeout.connect(self._trigger_blink)
        self.blink_timer.start(3500)

    def _animate(self):
        self.phase = (self.phase + 0.1) % (2 * math.pi)
        self.update()

    def _trigger_blink(self):
        self.is_blinking = True
        self.update()
        QTimer.singleShot(160, self._end_blink)

    def _end_blink(self):
        self.is_blinking = False
        self.update()

    def set_eye_state(self, state: str):
        self.eye_state = state
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setClipRect(self.rect())

        w, h = self.width(), self.height()
        cy = h / 2

        # Eye color: warm amber/orange glow like the screenshot
        if self.eye_state == "listening":
            base_col = QColor(168, 85, 247)  # Purple
        elif self.eye_state == "thinking":
            base_col = QColor(236, 72, 153)  # Magenta
        else:
            base_col = QColor(245, 158, 11)   # Warm amber/orange

        left_cx = 17.0
        right_cx = w - 17.0

        pulse = (math.sin(self.phase) + 1.0) * 0.5
        eye_w = 11.0 + (pulse * 1.5)
        eye_h = 7.0 if not self.is_blinking else 1.5

        for cx in (left_cx, right_cx):
            # Outer glow
            glow = QRadialGradient(cx, cy, 14.0)
            c_g = QColor(base_col)
            c_g.setAlpha(120)
            glow.setColorAt(0.0, c_g)
            c_fade = QColor(base_col)
            c_fade.setAlpha(0)
            glow.setColorAt(1.0, c_fade)
            painter.setBrush(QBrush(glow))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QRect(int(cx - 13), int(cy - 11), 26, 22))

            # Cute Eye Shape: Happy arc ^
            path = QPainterPath()
            if self.is_blinking:
                path.moveTo(cx - 6, cy)
                path.lineTo(cx + 6, cy)
                pen = QPen(base_col, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPath(path)
            else:
                # Triangular / curved happy eye ^
                path.moveTo(cx - 6, cy + 2)
                path.quadTo(cx, cy - eye_h, cx + 6, cy + 2)
                path.quadTo(cx, cy - (eye_h * 0.4), cx - 6, cy + 2)
                path.closeSubpath()

                grad = QLinearGradient(cx, cy - eye_h, cx, cy + 2)
                grad.setColorAt(0.0, QColor(255, 255, 255, 240))
                grad.setColorAt(0.5, base_col)
                grad.setColorAt(1.0, base_col.darker(140))
                painter.setBrush(QBrush(grad))
                painter.setPen(QPen(QColor(255, 255, 255, 140), 0.8))
                painter.drawPath(path)


DYNAMIC_STYLE = """
QWidget#IslandContainer {
    background-color: rgba(10, 10, 14, 0.96);
    border: 1px solid rgba(255, 255, 255, 0.16);
    border-top: 1px solid rgba(255, 255, 255, 0.32);
    border-radius: 20px;
}

QLabel#HeaderTitle {
    color: #FFFFFF;
    font-family: 'Segoe UI Variable Display', 'Segoe UI', system-ui, sans-serif;
    font-size: 13px;
    font-weight: 700;
}

QLabel#StatusBadge {
    color: #F59E0B;
    font-family: 'Segoe UI', sans-serif;
    font-size: 11px;
    font-weight: 600;
}

QScrollArea {
    background: transparent !important;
    border: none;
}

QScrollArea #qt_scrollarea_viewport {
    background: transparent !important;
    border: none;
}

QLabel#ResponseText {
    color: #F3F4F6;
    font-family: 'Segoe UI', system-ui, sans-serif;
    font-size: 12.5px;
    line-height: 1.4;
}

/* Quick Action Chips */
QPushButton#ActionChip {
    background-color: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 11px;
    color: #E5E7EB;
    font-family: 'Segoe UI', sans-serif;
    font-size: 11px;
    font-weight: 500;
    padding: 5px 10px;
}

QPushButton#ActionChip:hover {
    background-color: rgba(245, 158, 11, 0.22);
    border: 1px solid rgba(245, 158, 11, 0.5);
    color: #FEF3C7;
}

/* Input Row */
QLineEdit#InputBar {
    background-color: rgba(255, 255, 255, 0.07);
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 13px;
    color: #FFFFFF;
    font-family: 'Segoe UI', system-ui, sans-serif;
    font-size: 12.5px;
    padding: 8px 14px;
}

QLineEdit#InputBar:focus {
    border: 1px solid #F59E0B;
    background-color: rgba(255, 255, 255, 0.10);
}

QToolButton#ToolBtn {
    background-color: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 13px;
    color: #D1D5DB;
    font-size: 13px;
    padding: 6px;
}

QToolButton#ToolBtn:hover {
    background-color: rgba(255, 255, 255, 0.18);
    color: #FFFFFF;
    border: 1px solid rgba(255, 255, 255, 0.28);
}

QToolButton#ToolBtn:checked {
    background-color: rgba(245, 158, 11, 0.3);
    color: #FDE68A;
    border: 1px solid #F59E0B;
}

QPushButton#SendBtn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #F59E0B, stop:1 #D97706);
    border: none;
    border-radius: 13px;
    color: #000000;
    font-family: 'Segoe UI', system-ui, sans-serif;
    font-size: 12px;
    font-weight: 700;
    padding: 8px 16px;
}

QPushButton#SendBtn:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #FBBF24, stop:1 #B45309);
}

QToolButton#HeaderIconBtn {
    background: transparent;
    border: none;
    color: #9CA3AF;
    font-size: 12px;
    padding: 2px 4px;
}

QToolButton#HeaderIconBtn:hover {
    color: #FFFFFF;
}
"""


class NixiDynamicIsland(QWidget):
    send_query_signal = pyqtSignal(str)
    dictate_toggled_signal = pyqtSignal(bool)
    screen_vision_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet(DYNAMIC_STYLE)

        # Sizes
        self.collapsed_w = 144
        self.collapsed_h = 40
        self.expanded_w = 490
        self.expanded_h = 280

        self.is_expanded = False
        self.is_pinned = False
        self.is_executing = False
        self._drag_pos = None

        # Debounce timer for collapsing on mouse leave
        self.collapse_timer = QTimer(self)
        self.collapse_timer.setSingleShot(True)
        self.collapse_timer.timeout.connect(self._try_collapse)

        self._build_ui()
        self._position_collapsed()

    def showEvent(self, event):
        super().showEvent(event)
        apply_glassmorphism(int(self.winId()))

    def _position_collapsed(self):
        screen = QApplication.primaryScreen()
        if screen:
            geom = screen.geometry()
            x = (geom.width() - self.collapsed_w) // 2
            y = 10
            self.setGeometry(x, y, self.collapsed_w, self.collapsed_h)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        self.container = QWidget()
        self.container.setObjectName("IslandContainer")
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(10, 6, 10, 8)
        self.container_layout.setSpacing(6)

        # ── 1. Collapsed View (Cute Eyes) ────────────────────────────────────
        self.eyes_box = QHBoxLayout()
        self.eyes_box.setContentsMargins(0, 0, 0, 0)
        self.eyes_box.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.eyes = CuteEyesWidget()
        self.eyes_box.addWidget(self.eyes)
        self.container_layout.addLayout(self.eyes_box)

        # ── 2. Expanded View Elements (Initially Hidden) ─────────────────────
        self.expanded_widget = QWidget()
        exp_layout = QVBoxLayout(self.expanded_widget)
        exp_layout.setContentsMargins(4, 2, 4, 4)
        exp_layout.setSpacing(8)

        # Header Row
        header = QHBoxLayout()
        header.setSpacing(8)

        self.header_title = QLabel("✦ Nixi")
        self.header_title.setObjectName("HeaderTitle")
        header.addWidget(self.header_title)

        self.status_badge = QLabel("Idle")
        self.status_badge.setObjectName("StatusBadge")
        header.addWidget(self.status_badge)

        header.addStretch()

        # Pin toggle button (keep open)
        self.pin_btn = QToolButton()
        self.pin_btn.setObjectName("HeaderIconBtn")
        self.pin_btn.setText("📌")
        self.pin_btn.setToolTip("Pin Open (don't collapse)")
        self.pin_btn.setCheckable(True)
        self.pin_btn.toggled.connect(self._on_pin_toggled)
        header.addWidget(self.pin_btn)

        # Close / collapse button
        collapse_btn = QToolButton()
        collapse_btn.setObjectName("HeaderIconBtn")
        collapse_btn.setText("▲")
        collapse_btn.setToolTip("Collapse Island")
        collapse_btn.clicked.connect(self.collapse)
        header.addWidget(collapse_btn)

        exp_layout.addLayout(header)

        # Response Scroll Box
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFixedHeight(110)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(2, 2, 2, 2)

        self.response_label = QLabel("I'm ready. Ask me to fill boxes, read your screen, open apps, or dictate.")
        self.response_label.setObjectName("ResponseText")
        self.response_label.setWordWrap(True)
        self.response_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        scroll_layout.addWidget(self.response_label)
        scroll_layout.addStretch()

        self.scroll.setWidget(scroll_content)
        exp_layout.addWidget(self.scroll)

        # Action Chips Row
        chips_layout = QHBoxLayout()
        chips_layout.setSpacing(6)
        chips = [
            ("👁️ See Screen", "read screen"),
            ("⚡ Fill Form", "fill these boxes"),
            ("✍️ Dictate", "toggle dictation"),
            ("🚀 Chrome", "open chrome"),
        ]
        for label_text, cmd_text in chips:
            chip = QPushButton(label_text)
            chip.setObjectName("ActionChip")
            chip.setCursor(Qt.CursorShape.PointingHandCursor)
            chip.clicked.connect(lambda ch, c=cmd_text: self._on_chip_clicked(c))
            chips_layout.addWidget(chip)
        exp_layout.addLayout(chips_layout)

        # Bottom Input Bar Row (Text Input + Screen Eye + Mic + Send)
        input_row = QHBoxLayout()
        input_row.setSpacing(6)

        self.input_field = QLineEdit()
        self.input_field.setObjectName("InputBar")
        self.input_field.setPlaceholderText("Ask Nixi, e.g. 'fill these boxes'...")
        self.input_field.returnPressed.connect(self._on_send)
        input_row.addWidget(self.input_field)

        # Screen Seeing Button
        self.screen_btn = QToolButton()
        self.screen_btn.setObjectName("ToolBtn")
        self.screen_btn.setText("👁️")
        self.screen_btn.setToolTip("See Screen & Execute")
        self.screen_btn.clicked.connect(lambda: self.screen_vision_signal.emit())
        input_row.addWidget(self.screen_btn)

        # Mic / Dictate Button
        self.mic_btn = QToolButton()
        self.mic_btn.setObjectName("ToolBtn")
        self.mic_btn.setText("🎙️")
        self.mic_btn.setToolTip("Dictate into focused app (F8)")
        self.mic_btn.setCheckable(True)
        self.mic_btn.toggled.connect(lambda ch: self.dictate_toggled_signal.emit(ch))
        input_row.addWidget(self.mic_btn)

        # Send Button
        send_btn = QPushButton("Send")
        send_btn.setObjectName("SendBtn")
        send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        send_btn.clicked.connect(self._on_send)
        input_row.addWidget(send_btn)

        exp_layout.addLayout(input_row)

        self.container_layout.addWidget(self.expanded_widget)
        self.expanded_widget.hide()

        root.addWidget(self.container)

    # ── Hover Events for Dynamic Expansion & Collapse ────────────────────────
    def enterEvent(self, event):
        self.collapse_timer.stop()
        if not self.is_expanded:
            self.expand()
        super().enterEvent(event)

    def leaveEvent(self, event):
        # Debounce collapse check
        if self.is_expanded and not self.is_pinned and not self.is_executing:
            self.collapse_timer.start(450)
        super().leaveEvent(event)

    def _try_collapse(self):
        # Only collapse if mouse is genuinely outside and input doesn't have focus
        if not self.rect().contains(self.mapFromGlobal(QCursor.pos())) and not self.input_field.hasFocus():
            self.collapse()

    def expand(self):
        if self.is_expanded:
            return
        self.is_expanded = True
        self.eyes_box.parentWidget()  # ensure parent
        self.eyes.hide()
        self.expanded_widget.show()

        # Animate geometry downwards & outwards smoothly
        cur_geom = self.geometry()
        center_x = cur_geom.center().x()
        target_x = max(10, center_x - (self.expanded_w // 2))
        target_y = cur_geom.y()

        self.anim = QPropertyAnimation(self, b"geometry")
        self.anim.setDuration(240)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.anim.setStartValue(cur_geom)
        self.anim.setEndValue(QRect(target_x, target_y, self.expanded_w, self.expanded_h))
        self.anim.start()

        QTimer.singleShot(150, self.input_field.setFocus)

    def collapse(self):
        if not self.is_expanded:
            return
        self.is_expanded = False
        self.expanded_widget.hide()
        self.eyes.show()

        cur_geom = self.geometry()
        center_x = cur_geom.center().x()
        target_x = max(10, center_x - (self.collapsed_w // 2))
        target_y = cur_geom.y()

        self.anim = QPropertyAnimation(self, b"geometry")
        self.anim.setDuration(220)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.anim.setStartValue(cur_geom)
        self.anim.setEndValue(QRect(target_x, target_y, self.collapsed_w, self.collapsed_h))
        self.anim.start()

    def _on_pin_toggled(self, pinned: bool):
        self.is_pinned = pinned
        self.pin_btn.setText("📌" if not pinned else "📍")

    def _on_chip_clicked(self, cmd: str):
        self.send_query_signal.emit(cmd)

    def _on_send(self):
        text = self.input_field.text().strip()
        if not text:
            return
        self.input_field.clear()
        self.set_response(f"You: {text}\n\nThinking...")
        self.send_query_signal.emit(text)

    def set_response(self, text: str):
        self.response_label.setText(text)
        self.scroll.verticalScrollBar().setValue(0)

    def set_status(self, text: str, state: str = "idle"):
        self.status_badge.setText(text)
        self.eyes.set_eye_state(state)

    def set_audio_level(self, level: float):
        pass  # eyes pulse automatically

    # Window Dragging support
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self._drag_pos:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
