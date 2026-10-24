"""
Nixi Floating Pill Window — Ultra-Glassmorphism Edition
Minimal top-of-screen floating bar with native Windows acrylic blur,
deep ambient shadow, animated glowing orb, and audio waveform visualizer.
"""
from __future__ import annotations

import math
from typing import Optional
from PyQt6.QtCore import Qt, QPoint, QRect, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QPainter, QColor, QRadialGradient, QLinearGradient, QPen, QBrush, QFont, QCursor
)
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QToolButton, QApplication, QGraphicsDropShadowEffect
)

from .styles import PILL_STYLE
from .chat_drawer import ChatDrawer
from .blur_effect import apply_glassmorphism

class OrbState:
    IDLE = "idle"
    LISTENING = "listening"
    DICTATING = "dictating"
    THINKING = "thinking"
    SPEAKING = "speaking"


class GlowingOrb(QWidget):
    """An animated, pulsing glowing orb representing Nixi's internal state & mic volume."""
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedSize(32, 32)
        self.state = OrbState.IDLE
        self.level = 0.0
        self.phase = 0.0

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._animate)
        self.timer.start(30)

    def set_state(self, state: str):
        self.state = state
        self.update()

    def set_level(self, level: float):
        self.level = max(0.0, min(1.0, level))
        self.update()

    def _animate(self):
        self.phase = (self.phase + 0.12) % (2 * math.pi)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2

        if self.state == OrbState.LISTENING:
            base_col = QColor(168, 85, 247)   # Purple
            halo_col = QColor(192, 132, 252)
        elif self.state == OrbState.DICTATING:
            base_col = QColor(245, 158, 11)   # Amber
            halo_col = QColor(251, 191, 36)
        elif self.state == OrbState.THINKING:
            base_col = QColor(236, 72, 153)   # Pink/Magenta
            halo_col = QColor(244, 114, 182)
        elif self.state == OrbState.SPEAKING:
            base_col = QColor(16, 185, 129)   # Emerald
            halo_col = QColor(52, 211, 153)
        else:
            base_col = QColor(6, 182, 212)    # Cyan
            halo_col = QColor(103, 232, 249)

        pulse = (math.sin(self.phase) + 1.0) * 0.5
        # Bound radius strictly so it never extends into negative coordinates
        radius = 5.0 + (pulse * 1.2) + (self.level * 2.0)
        glow_r = min(14.0, radius * 1.8)

        # Strictly clip to widget boundary
        painter.setClipRect(self.rect())

        # Outer soft ambient glow
        outer_grad = QRadialGradient(cx, cy, glow_r)
        glow_alpha = int(70 + (pulse * 50) + (self.level * 80))
        glow_alpha = min(200, glow_alpha)
        
        c_glow = QColor(base_col)
        c_glow.setAlpha(glow_alpha)
        outer_grad.setColorAt(0.0, c_glow)
        
        c_fade = QColor(halo_col)
        c_fade.setAlpha(int(glow_alpha * 0.4))
        outer_grad.setColorAt(0.6, c_fade)

        c_trans = QColor(base_col)
        c_trans.setAlpha(0)
        outer_grad.setColorAt(1.0, c_trans)

        painter.setBrush(QBrush(outer_grad))
        painter.setPen(Qt.PenStyle.NoPen)
        gx, gy = int(cx - glow_r), int(cy - glow_r)
        gw, gh = int(glow_r * 2), int(glow_r * 2)
        painter.drawEllipse(QRect(max(0, gx), max(0, gy), min(w, gw), min(h, gh)))

        # Inner solid core with highlight
        inner_r = min(8.0, radius * 0.8)
        inner_grad = QRadialGradient(cx - 1, cy - 1, inner_r)
        inner_grad.setColorAt(0.0, QColor(255, 255, 255, 230))
        inner_grad.setColorAt(0.4, base_col)
        inner_grad.setColorAt(1.0, base_col.darker(130))

        painter.setBrush(QBrush(inner_grad))
        painter.setPen(QPen(QColor(255, 255, 255, 180), 1.0))
        ix, iy = int(cx - inner_r), int(cy - inner_r)
        iw, ih = int(inner_r * 2), int(inner_r * 2)
        painter.drawEllipse(QRect(max(0, ix), max(0, iy), min(w, iw), min(h, ih)))


class AudioWaveBars(QWidget):
    """Subtle mini audio equalizer bars that bounce when mic is receiving audio."""
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedSize(22, 16)
        self.level = 0.0
        self.phase = 0.0

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._animate)
        self.timer.start(40)

    def set_level(self, level: float):
        self.level = level
        self.update()

    def _animate(self):
        self.phase = (self.phase + 0.25) % (2 * math.pi)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        bars = 3
        bar_w = 2.5
        spacing = 4.0
        max_h = 13.0
        min_h = 3.0

        for i in range(bars):
            offset = i * 0.8
            dynamic = (math.sin(self.phase + offset) + 1.0) * 0.5
            h = min_h + (dynamic * 4.0) + (self.level * (max_h - min_h))
            h = min(max_h, max(min_h, h))
            
            x = 2.0 + i * (bar_w + spacing)
            y = (self.height() - h) / 2

            col = QColor(168, 85, 247, int(120 + self.level * 135))
            painter.setBrush(QBrush(col))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(QRect(int(x), int(y), int(bar_w), int(h)), 1.2, 1.2)


class NixiPillWindow(QWidget):
    dictate_toggled = pyqtSignal(bool)
    screen_requested = pyqtSignal()
    mic_clicked = pyqtSignal()
    chat_toggled = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet(PILL_STYLE)

        self.pill_width = 360
        self.pill_height = 48
        self.setFixedSize(self.pill_width, self.pill_height)

        # Chat drawer instance
        self.drawer = ChatDrawer()

        self._drag_pos = None
        self._build_ui()
        self._position_top_center()

    def showEvent(self, event):
        super().showEvent(event)
        # Apply native Windows Acrylic blur
        apply_glassmorphism(int(self.winId()))

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        self.container = QWidget()
        self.container.setObjectName("PillContainer")
        self.container.setFixedHeight(self.pill_height)

        layout = QHBoxLayout(self.container)
        layout.setContentsMargins(12, 4, 12, 4)
        layout.setSpacing(10)

        # Glowing Orb
        self.orb = GlowingOrb()
        self.orb.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.orb.mousePressEvent = lambda e: self.mic_clicked.emit()
        layout.addWidget(self.orb)

        # Status text + Waveform
        status_box = QHBoxLayout()
        status_box.setSpacing(6)
        self.status_label = QLabel("Nixi")
        self.status_label.setObjectName("StatusText")
        status_box.addWidget(self.status_label)

        self.wave_bars = AudioWaveBars()
        status_box.addWidget(self.wave_bars)
        layout.addLayout(status_box)

        layout.addStretch()

        # Dictate Toggle Button (F8)
        self.dictate_btn = QToolButton()
        self.dictate_btn.setText("🎙️")
        self.dictate_btn.setToolTip("Toggle Dictation into active app (F8)")
        self.dictate_btn.setCheckable(True)
        self.dictate_btn.toggled.connect(self._on_dictate_toggled)
        layout.addWidget(self.dictate_btn)

        # Screen Vision Button (F10)
        self.screen_btn = QToolButton()
        self.screen_btn.setText("👁️")
        self.screen_btn.setToolTip("Analyze Screen with Vision (F10)")
        self.screen_btn.clicked.connect(lambda: self.screen_requested.emit())
        layout.addWidget(self.screen_btn)

        # Chat Drawer Button (F9)
        self.chat_btn = QToolButton()
        self.chat_btn.setText("💬")
        self.chat_btn.setToolTip("Open Chat Drawer (F9)")
        self.chat_btn.clicked.connect(self.toggle_drawer)
        layout.addWidget(self.chat_btn)

        # Close / Minimize
        self.close_btn = QToolButton()
        self.close_btn.setObjectName("CloseBtn")
        self.close_btn.setText("✕")
        self.close_btn.setToolTip("Close Nixi")
        self.close_btn.clicked.connect(self.close)
        layout.addWidget(self.close_btn)

        root.addWidget(self.container)

    def _position_top_center(self):
        screen = QApplication.primaryScreen()
        if screen:
            geom = screen.geometry()
            x = (geom.width() - self.width()) // 2
            y = 12
            self.move(x, y)

    def set_status(self, text: str, state: str = OrbState.IDLE):
        if len(text) > 22:
            display_text = text[:20] + "..."
        else:
            display_text = text
        self.status_label.setText(display_text)
        self.orb.set_state(state)

    def set_audio_level(self, level: float):
        self.orb.set_level(level)
        self.wave_bars.set_level(level)

    def _on_dictate_toggled(self, checked: bool):
        if checked:
            self.dictate_btn.setObjectName("DictateActive")
            self.dictate_btn.setText("✍️")
            self.set_status("Dictating...", OrbState.DICTATING)
        else:
            self.dictate_btn.setObjectName("")
            self.dictate_btn.setText("🎙️")
            self.set_status("Nixi", OrbState.IDLE)
        self.dictate_btn.setStyle(self.dictate_btn.style())
        self.dictate_toggled.emit(checked)

    def toggle_drawer(self):
        if self.drawer.isVisible():
            self.drawer.hide()
        else:
            self.drawer.position_below_pill(self.geometry())
            self.drawer.show()
            self.drawer.raise_()
            self.drawer.input_field.setFocus()
            self.chat_toggled.emit()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self._drag_pos:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            if self.drawer.isVisible():
                self.drawer.position_below_pill(self.geometry())
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def closeEvent(self, event):
        self.drawer.close()
        super().closeEvent(event)
