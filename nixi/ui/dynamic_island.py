"""
Nixi Dynamic Island — Hover-Expandable Top Widget
Inspired by Apple Dynamic Island & HeyNixi.
Collapsed: Ultra-compact black capsule with cute glowing animated eyes & audio visualizer wave.
Expanded on hover: Smoothly animates into a full glassmorphic assistant (510x290)
with text input, mic button, screen seeing button, system god-mode action chips, and live responses.
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


class AudioWaveWidget(QWidget):
    """5-bar reactive audio waveform visualizer that pulses with microphone/TTS level."""
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedSize(36, 20)
        self.level = 0.0
        self.phase = 0.0
        self.is_active = False

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(33)

    def set_level(self, lvl: float):
        self.level = max(0.0, min(1.0, lvl))
        self.is_active = self.level > 0.04
        self.update()

    def _tick(self):
        if self.is_active:
            self.phase = (self.phase + 0.25) % (2 * math.pi)
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setClipRect(self.rect())

        w, h = self.width(), self.height()
        bars = 5
        bar_w = 3.0
        spacing = (w - (bars * bar_w)) / (bars + 1)
        cy = h / 2.0

        for i in range(bars):
            x = spacing + i * (bar_w + spacing)
            # Modulate height by level and sine wave
            if self.is_active:
                wave = math.sin(self.phase + i * 0.9)
                bar_h = max(3.0, (self.level * 14.0) + (wave * 3.0))
            else:
                bar_h = 3.0

            y = cy - (bar_h / 2.0)
            rect = QRect(int(x), int(y), int(bar_w), int(bar_h))

            # Amber to cyan glowing gradient
            grad = QLinearGradient(x, y, x, y + bar_h)
            grad.setColorAt(0.0, QColor(245, 158, 11, 230))
            grad.setColorAt(1.0, QColor(217, 119, 6, 180))

            painter.setBrush(QBrush(grad))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(rect, 1.5, 1.5)


class CuteEyesWidget(QWidget):
    """Two cute glowing animated eyes with rich multi-emotion expressions."""
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedSize(56, 26)
        self.is_blinking = False
        self.eye_state = "happy"  # "happy", "listening", "thinking", "speaking", "surprised", "winking"
        self.phase = 0.0
        self.audio_pulse = 0.0

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
        if self.eye_state not in ("thinking", "speaking"):
            self.is_blinking = True
            self.update()
            QTimer.singleShot(160, self._end_blink)

    def _end_blink(self):
        self.is_blinking = False
        self.update()

    def set_eye_state(self, state: str):
        self.eye_state = state
        self.update()

    def set_audio_pulse(self, lvl: float):
        self.audio_pulse = lvl
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setClipRect(self.rect())

        w, h = self.width(), self.height()
        cy = h / 2.0

        # Eye color palette based on state
        if self.eye_state == "listening":
            base_col = QColor(168, 85, 247)  # Electric Purple
        elif self.eye_state == "thinking":
            base_col = QColor(236, 72, 153)  # Hot Pink / Magenta
        elif self.eye_state == "speaking":
            base_col = QColor(56, 189, 248)  # Cyan
        elif self.eye_state == "surprised":
            base_col = QColor(239, 68, 68)   # Coral Red
        else:
            base_col = QColor(245, 158, 11)   # Warm Amber / Gold

        left_cx = 17.0
        right_cx = w - 17.0

        pulse = (math.sin(self.phase) + 1.0) * 0.5
        eye_w = 11.0 + (pulse * 1.5) + (self.audio_pulse * 4.0)
        eye_h = 7.0 if not self.is_blinking else 1.5

        for i, cx in enumerate((left_cx, right_cx)):
            # Outer Radial Glow
            glow = QRadialGradient(cx, cy, 14.0)
            c_g = QColor(base_col)
            c_g.setAlpha(130)
            glow.setColorAt(0.0, c_g)
            c_fade = QColor(base_col)
            c_fade.setAlpha(0)
            glow.setColorAt(1.0, c_fade)
            painter.setBrush(QBrush(glow))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QRect(int(cx - 13), int(cy - 11), 26, 22))

            # Check wink state: if winking, right eye is closed
            is_eye_winked = (self.eye_state == "winking" and i == 1)

            path = QPainterPath()
            if self.is_blinking or is_eye_winked:
                # Closed blinking eye line
                path.moveTo(cx - 6, cy)
                path.lineTo(cx + 6, cy)
                pen = QPen(base_col, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPath(path)

            elif self.eye_state == "speaking":
                # Undulating playful wave eye ~
                wave_off = math.sin(self.phase * 2.0 + i) * 2.0
                path.moveTo(cx - 6, cy + wave_off)
                path.cubicTo(cx - 2, cy - 4 + wave_off, cx + 2, cy + 4 + wave_off, cx + 6, cy + wave_off)
                pen = QPen(base_col, 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPath(path)

            elif self.eye_state == "thinking":
                # Focused scanning eye > <
                dx = math.sin(self.phase * 3.0) * 2.0
                if i == 0:
                    path.moveTo(cx - 5 + dx, cy - 4)
                    path.lineTo(cx + 4 + dx, cy)
                    path.lineTo(cx - 5 + dx, cy + 4)
                else:
                    path.moveTo(cx + 5 + dx, cy - 4)
                    path.lineTo(cx - 4 + dx, cy)
                    path.lineTo(cx + 5 + dx, cy + 4)
                pen = QPen(base_col, 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPath(path)

            elif self.eye_state == "surprised":
                # Wide open circular eye O
                painter.setPen(QPen(QColor(255, 255, 255, 220), 1.0))
                painter.setBrush(QBrush(base_col))
                painter.drawEllipse(QRect(int(cx - 6), int(cy - 6), 12, 12))

            elif self.eye_state == "listening":
                # Glowing alert circle •
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(base_col))
                r_size = 5.0 + (pulse * 2.0)
                painter.drawEllipse(QRect(int(cx - r_size), int(cy - r_size), int(r_size * 2), int(r_size * 2)))

            else:
                # Default Happy curved arc ^
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
    background-color: rgba(245, 158, 11, 0.14);
    border: 1px solid rgba(245, 158, 11, 0.28);
    border-radius: 9px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 600;
}

QLabel#ResponseText {
    color: #F3F4F6;
    font-family: 'Segoe UI Variable Text', 'Segoe UI', system-ui, sans-serif;
    font-size: 13px;
    line-height: 1.45;
}

QPushButton#ActionChip {
    background-color: rgba(255, 255, 255, 0.07);
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 12px;
    color: #E5E7EB;
    font-size: 11px;
    font-weight: 600;
    padding: 4px 10px;
}

QPushButton#ActionChip:hover {
    background-color: rgba(245, 158, 11, 0.22);
    border: 1px solid #F59E0B;
    color: #FFFFFF;
}

QLineEdit#InputBar {
    background-color: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 14px;
    color: #FFFFFF;
    font-family: 'Segoe UI Variable Text', 'Segoe UI', system-ui, sans-serif;
    font-size: 13px;
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
        self.collapsed_w = 156
        self.collapsed_h = 42
        self.expanded_w = 510
        self.expanded_h = 295

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
        self.container_layout.setContentsMargins(8, 6, 8, 6)

        # ── Collapsed Widget: Cute Animated Eyes + Waveform ──────────────────
        self.collapsed_widget = QWidget()
        collapsed_layout = QHBoxLayout(self.collapsed_widget)
        collapsed_layout.setContentsMargins(4, 0, 4, 0)
        collapsed_layout.setSpacing(6)

        self.eyes = CuteEyesWidget(self)
        collapsed_layout.addWidget(self.eyes, alignment=Qt.AlignmentFlag.AlignCenter)

        self.audio_wave = AudioWaveWidget(self)
        collapsed_layout.addWidget(self.audio_wave, alignment=Qt.AlignmentFlag.AlignCenter)

        self.container_layout.addWidget(self.collapsed_widget)

        # ── Expanded Widget: Header + Response Box + God Chips + Input Bar ──
        self.expanded_widget = QWidget()
        exp_layout = QVBoxLayout(self.expanded_widget)
        exp_layout.setContentsMargins(4, 4, 4, 4)
        exp_layout.setSpacing(8)

        # Header (Nixi Title + Cute Eyes + Status Badge + Pin + Collapse)
        header = QHBoxLayout()
        header.setSpacing(8)

        title_lbl = QLabel("Nixi ✦")
        title_lbl.setObjectName("HeaderTitle")
        header.addWidget(title_lbl)

        self.header_eyes = CuteEyesWidget(self)
        self.header_eyes.setFixedSize(48, 22)
        header.addWidget(self.header_eyes)

        self.status_badge = QLabel("Ready")
        self.status_badge.setObjectName("StatusBadge")
        header.addWidget(self.status_badge)

        header.addStretch()

        # Pin button
        self.pin_btn = QToolButton()
        self.pin_btn.setObjectName("HeaderIconBtn")
        self.pin_btn.setText("📌")
        self.pin_btn.setToolTip("Keep Open / Unpin")
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
        self.scroll.setFixedHeight(115)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.viewport().setAutoFillBackground(False)

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(2, 2, 2, 2)

        self.response_label = QLabel("I'm ready. Ask me anything, control system volume, search the web, fill forms, or dictate.")
        self.response_label.setObjectName("ResponseText")
        self.response_label.setWordWrap(True)
        self.response_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        scroll_layout.addWidget(self.response_label)
        scroll_layout.addStretch()

        self.scroll.setWidget(scroll_content)
        exp_layout.addWidget(self.scroll)

        # God-Mode Quick Action Chips Row
        chips_layout = QHBoxLayout()
        chips_layout.setSpacing(6)
        chips = [
            ("⚡ Fill Form", "fill these boxes"),
            ("🌐 Search Web", "search the web for "),
            ("💻 PowerShell", "run powershell dir"),
            ("👁️ See Screen", "read screen"),
            ("🔇 Mute", "mute"),
            ("🖥️ Desktop", "show desktop"),
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
        self.input_field.setPlaceholderText("Do anything, e.g. 'search web for...', 'volume 70', 'fill form'...")
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
        if self.is_expanded and not self.is_pinned and not self.is_executing:
            # 700ms debounce so user can easily mouse in and out
            self.collapse_timer.start(700)
        super().leaveEvent(event)

    def _try_collapse(self):
        # Don't collapse if cursor is still inside or if pinned/executing
        if self.underMouse() or self.is_pinned or self.is_executing:
            return
        if not self.input_field.hasFocus():
            self.collapse()

    def expand(self):
        """Smoothly expand Dynamic Island downwards."""
        if self.is_expanded:
            return
        self.is_expanded = True

        screen = QApplication.primaryScreen()
        if not screen:
            return
        geom = screen.geometry()
        target_x = (geom.width() - self.expanded_w) // 2
        target_y = 10

        self.collapsed_widget.hide()
        self.expanded_widget.show()

        self.anim = QPropertyAnimation(self, b"geometry")
        self.anim.setDuration(220)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.anim.setStartValue(self.geometry())
        self.anim.setEndValue(QRect(target_x, target_y, self.expanded_w, self.expanded_h))
        self.anim.start()

        QTimer.singleShot(240, lambda: self.input_field.setFocus())

    def collapse(self):
        """Smoothly collapse Dynamic Island back into minimal pill."""
        if not self.is_expanded or self.is_pinned or self.is_executing:
            return
        self.is_expanded = False

        screen = QApplication.primaryScreen()
        if not screen:
            return
        geom = screen.geometry()
        target_x = (geom.width() - self.collapsed_w) // 2
        target_y = 10

        self.expanded_widget.hide()
        self.collapsed_widget.show()

        self.anim = QPropertyAnimation(self, b"geometry")
        self.anim.setDuration(200)
        self.anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.anim.setStartValue(self.geometry())
        self.anim.setEndValue(QRect(target_x, target_y, self.collapsed_w, self.collapsed_h))
        self.anim.start()

    def _on_pin_toggled(self, checked: bool):
        self.is_pinned = checked
        self.pin_btn.setText("📌" if checked else "📍")

    def _on_chip_clicked(self, cmd: str):
        if cmd.endswith(" "):
            self.input_field.setText(cmd)
            self.input_field.setFocus()
            self.input_field.setCursorPosition(len(cmd))
        else:
            self.send_query_signal.emit(cmd)

    def _on_send(self):
        text = self.input_field.text().strip()
        if not text:
            return
        self.input_field.clear()
        self.send_query_signal.emit(text)

    # ── Draggable Window via Header Mouse Press ──────────────────────────────
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    # ── External Bridge Slots ────────────────────────────────────────────────
    def set_status(self, text: str, eye_state: str = "happy"):
        self.status_badge.setText(text)
        self.eyes.set_eye_state(eye_state)
        self.header_eyes.set_eye_state(eye_state)

    def set_audio_level(self, level: float):
        self.audio_wave.set_level(level)
        self.eyes.set_audio_pulse(level)

    def set_response(self, text: str):
        self.response_label.setText(text)
