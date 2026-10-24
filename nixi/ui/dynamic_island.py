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
    Qt, QRect, QRectF, QPoint, QPointF, QTimer, pyqtSignal, QPropertyAnimation, QEasingCurve
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


class StylizedCartoonEyes(QWidget):
    """
    Stylized Cartoon Eyes matching the 12-expression reference image:
    Column 1:
        1. 'horned_tall'    (Col 1 Row 1: Peaked tall cat/bat ears with inner pupils)
        2. 'angry_brow'     (Col 1 Row 2: Intense downward anime brow)
        3. 'crescent_down'  (Col 1 Row 3: Sly looking down crescent)
        4. 'kidney_bean'    (Col 1 Row 4: Inquisitive tilted bean eyes)
    Column 2:
        5. 'cat_slit_wide'  (Col 2 Row 1: Classic horizontal feline cat slit)
        6. 'inner_focus'    (Col 2 Row 2: Inward looking / cute derp focus)
        7. 'crescent_arc'   (Col 2 Row 3: Happy smiling crescent arcs)
        8. 'half_moon_glint'(Col 2 Row 4: Flat-top anime eye with catchlight glint dot)
    Column 3:
        9. 'horned_demon'   (Col 3 Row 1: Playful sharp impish horns)
        10. 'cat_slit_oval' (Col 3 Row 2: Rounded oval cat eye with slit pupil)
        11. 'squint_slit'   (Col 3 Row 3: Suspicious squinting slit)
        12. 'sharp_leaf_slit'(Col 3 Row 4: Sharp winged leaf cat eye)

    Animations:
    - Real-time saccades (smooth gaze shifts: center, left, right, up, down)
    - Natural blinks & occasional cute double-blinks
    - Autonomous expression shifting during idle
    - Reactive audio pulsing (pupils dilate with sound/speech)
    - Click to cycle through all 12 styles, double-click to lock/unlock!
    """
    STYLES = [
        "cat_slit_wide",    # 1. Classic Feline Cat Slit (Col 2 Row 1)
        "horned_tall",      # 2. Peaked Alert Horns (Col 1 Row 1)
        "horned_demon",     # 3. Playful Imp Horns (Col 3 Row 1)
        "angry_brow",       # 4. Determined Anime Brow (Col 1 Row 2)
        "half_moon_glint",  # 5. Anime Glint Half-Moon (Col 2 Row 4)
        "inner_focus",      # 6. Inward Focus / Derp (Col 2 Row 2)
        "cat_slit_oval",    # 7. Oval Cat Slit (Col 3 Row 2)
        "crescent_down",    # 8. Sly Looking Down (Col 1 Row 3)
        "crescent_arc",     # 9. Smiling Crescent (Col 2 Row 3)
        "squint_slit",      # 10. Suspicious Squint (Col 3 Row 3)
        "kidney_bean",      # 11. Tilted Bean Eye (Col 1 Row 4)
        "sharp_leaf_slit",  # 12. Sharp Winged Slit (Col 3 Row 4)
    ]

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedSize(58, 26)
        self.is_blinking = False
        self.is_locked = False
        self.eye_state = "idle"
        self.style_idx = 0
        self.phase = 0.0
        self.audio_pulse = 0.0

        # Saccade / gaze offsets (smooth interpolation)
        self.look_x = 0.0
        self.look_y = 0.0
        self.target_look_x = 0.0
        self.target_look_y = 0.0

        # Animation frame timer (30 FPS)
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._animate)
        self.anim_timer.start(33)

        # Periodic blink timer
        self.blink_timer = QTimer(self)
        self.blink_timer.timeout.connect(self._trigger_blink)
        self.blink_timer.start(3600)

        # Periodic saccade / gaze shift timer (every 2.8s)
        self.gaze_timer = QTimer(self)
        self.gaze_timer.timeout.connect(self._shift_gaze)
        self.gaze_timer.start(2800)

        # Idle expression cycle timer (every 11s)
        self.idle_cycle_timer = QTimer(self)
        self.idle_cycle_timer.timeout.connect(self._idle_cycle_expression)
        self.idle_cycle_timer.start(11000)

        self._update_tooltip()

    def _update_tooltip(self):
        style_name = self.STYLES[self.style_idx]
        lock_txt = " (Locked)" if self.is_locked else " (Auto-cycle)"
        self.setToolTip(f"Nixi Eyes: {style_name} [{self.style_idx+1}/12]{lock_txt}\nClick to cycle next • Double-click to lock/unlock")

    def mousePressEvent(self, event):
        """Single click cycles through all 12 styles with a quick wink transition!"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._trigger_quick_transition()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        """Double click toggles lock mode so it stays on your favorite style."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_locked = not self.is_locked
            self._update_tooltip()
            self.update()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def _trigger_quick_transition(self):
        self.is_blinking = True
        self.update()
        def switch():
            self.style_idx = (self.style_idx + 1) % len(self.STYLES)
            self._update_tooltip()
            self.is_blinking = False
            self.update()
        QTimer.singleShot(110, switch)

    def _animate(self):
        self.phase = (self.phase + 0.1) % (2 * math.pi)

        # Smoothly ease gaze towards target
        self.look_x += (self.target_look_x - self.look_x) * 0.22
        self.look_y += (self.target_look_y - self.look_y) * 0.22

        self.update()

    def _trigger_blink(self):
        if self.eye_state not in ("thinking", "speaking"):
            self.is_blinking = True
            self.update()
            # 25% chance of cute natural double-blink
            import random
            if random.random() < 0.25:
                QTimer.singleShot(120, self._open_and_flutter)
            else:
                QTimer.singleShot(140, self._end_blink)

    def _open_and_flutter(self):
        self.is_blinking = False
        self.update()
        QTimer.singleShot(80, lambda: setattr(self, 'is_blinking', True) or self.update())
        QTimer.singleShot(180, self._end_blink)

    def _end_blink(self):
        self.is_blinking = False
        self.update()

    def _shift_gaze(self):
        """Living gaze: glances slightly left, right, up, down, or center."""
        if self.eye_state in ("thinking", "speaking", "listening"):
            return
        import random
        choices = [
            (0.0, 0.0),      # Center
            (0.0, 0.0),      # Center (weighted)
            (-1.4, 0.0),     # Glance Left
            (1.4, 0.0),      # Glance Right
            (0.0, -1.0),     # Look Up
            (0.0, 0.8),      # Look Down
        ]
        self.target_look_x, self.target_look_y = random.choice(choices)

    def _idle_cycle_expression(self):
        """In idle state, naturally shift expressions every few seconds if unlocked."""
        if self.is_locked or self.eye_state not in ("idle", "happy"):
            return
        # Transition to next expression smoothly via a blink
        self.is_blinking = True
        self.update()
        def shift():
            self.style_idx = (self.style_idx + 1) % len(self.STYLES)
            self._update_tooltip()
            self.is_blinking = False
            self.update()
        QTimer.singleShot(130, shift)

    def set_eye_state(self, state: str):
        self.eye_state = state.lower()
        if self.eye_state == "thinking":
            self.target_look_x = 0.0
            self.target_look_y = 0.0
        self.update()

    def set_audio_pulse(self, lvl: float):
        self.audio_pulse = max(0.0, min(1.0, lvl))
        self.update()

    def _get_active_style(self) -> str:
        # Dynamic emotional states override temporarily unless user locked a specific style
        if not self.is_locked:
            if self.eye_state in ("thinking", "scanning"):
                return "half_moon_glint"
            elif self.eye_state in ("listening", "alert"):
                return "horned_tall"
            elif self.eye_state in ("guardian", "angry", "determined"):
                return "angry_brow"
            elif self.eye_state in ("happy", "done", "complete"):
                return "crescent_arc"
            elif self.eye_state == "speaking":
                return "cat_slit_wide"
        return self.STYLES[self.style_idx]

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setClipRect(self.rect())

        w, h = self.width(), self.height()
        cy = h / 2.0
        left_cx = 17.0
        right_cx = w - 17.0

        hw = 9.5
        hh = 7.0

        # Ambient aura glow based on mood
        if self.eye_state == "listening":
            glow_col = QColor(168, 85, 247, 95)   # Electric Purple
        elif self.eye_state in ("thinking", "half_moon_glint"):
            glow_col = QColor(236, 72, 153, 95)   # Neon Magenta
        elif self.eye_state == "speaking":
            glow_col = QColor(56, 189, 248, 115)  # Cyan
        elif self.eye_state in ("guardian", "angry", "determined"):
            glow_col = QColor(239, 68, 68, 95)    # Crimson
        else:
            glow_col = QColor(245, 158, 11, 85)   # Amber Gold

        active_style = self._get_active_style()

        for i, cx in enumerate((left_cx, right_cx)):
            mirror = -1.0 if i == 1 else 1.0

            # Breathing ambient aura
            pulse = (math.sin(self.phase) + 1.0) * 0.5
            glow_r = 13.0 + (pulse * 2.0) + (self.audio_pulse * 4.5)
            glow = QRadialGradient(cx, cy, glow_r)
            glow.setColorAt(0.0, glow_col)
            c_fade = QColor(glow_col)
            c_fade.setAlpha(0)
            glow.setColorAt(1.0, c_fade)
            painter.setBrush(QBrush(glow))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QRectF(cx - glow_r, cy - glow_r, glow_r * 2, glow_r * 2))

            painter.save()
            painter.translate(cx, cy)

            # Eyelid closed in blink
            if self.is_blinking:
                pen = QPen(QColor(255, 255, 255, 240), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
                painter.setPen(pen)
                painter.drawLine(int(-hw * 0.85), 0, int(hw * 0.85), 0)
                painter.restore()
                continue

            path = QPainterPath()

            # -------------------------------------------------------------
            # 1. HORNED TALL (Col 1 Row 1)
            # -------------------------------------------------------------
            if active_style == "horned_tall":
                path.moveTo(-hw * 0.8 * mirror, hh * 0.7)
                path.cubicTo(-hw * 0.7 * mirror, -hh * 0.5, -hw * 0.25 * mirror, -hh * 1.35, -hw * 0.15 * mirror, -hh * 1.35)
                path.cubicTo(hw * 0.3 * mirror, -hh * 0.3, hw * 0.8 * mirror, 0, hw * 0.85 * mirror, hh * 0.7)
                path.cubicTo(hw * 0.3 * mirror, hh * 1.15, -hw * 0.4 * mirror, hh * 1.15, -hw * 0.8 * mirror, hh * 0.7)
                path.closeSubpath()
                self._draw_white(painter, path)
                self._draw_circle_pupil(painter, hw * 0.32 * mirror + self.look_x, hh * 0.35 + self.look_y, 2.7)

            # -------------------------------------------------------------
            # 2. ANGRY / DETERMINED BROW (Col 1 Row 2)
            # -------------------------------------------------------------
            elif active_style == "angry_brow":
                path.moveTo(-hw * mirror, -hh * 0.95)
                path.lineTo(hw * mirror, hh * 0.15)
                path.cubicTo(hw * 0.6 * mirror, hh * 1.25, -hw * 0.5 * mirror, hh * 1.25, -hw * mirror, -hh * 0.95)
                path.closeSubpath()
                self._draw_white(painter, path)
                self._draw_circle_pupil(painter, hw * 0.32 * mirror + self.look_x, hh * 0.22 + self.look_y, 2.8)

            # -------------------------------------------------------------
            # 3. CRESCENT DOWN (Col 1 Row 3)
            # -------------------------------------------------------------
            elif active_style == "crescent_down":
                path.moveTo(-hw * mirror, -hh * 0.1)
                path.cubicTo(-hw * 0.4 * mirror, -hh * 1.0, hw * 0.4 * mirror, -hh * 1.0, hw * mirror, -hh * 0.1)
                path.cubicTo(hw * 0.8 * mirror, hh * 1.0, -hw * 0.8 * mirror, hh * 1.0, -hw * mirror, -hh * 0.1)
                path.closeSubpath()
                self._draw_white(painter, path)
                self._draw_circle_pupil(painter, hw * 0.28 * mirror + self.look_x, hh * 0.35 + self.look_y, 2.5)

            # -------------------------------------------------------------
            # 4. KIDNEY BEAN (Col 1 Row 4)
            # -------------------------------------------------------------
            elif active_style == "kidney_bean":
                path.moveTo(-hw * 0.9 * mirror, -hh * 0.7)
                path.cubicTo(-hw * 0.1 * mirror, -hh * 1.25, hw * 0.9 * mirror, -hh * 0.4, hw * 0.8 * mirror, hh * 0.6)
                path.cubicTo(hw * 0.3 * mirror, hh * 1.2, -hw * 0.6 * mirror, hh * 0.9, -hw * 0.9 * mirror, -hh * 0.7)
                path.closeSubpath()
                self._draw_white(painter, path)
                self._draw_circle_pupil(painter, hw * 0.35 * mirror + self.look_x, hh * 0.38 + self.look_y, 2.5)

            # -------------------------------------------------------------
            # 5. CAT SLIT WIDE (Col 2 Row 1)
            # -------------------------------------------------------------
            elif active_style == "cat_slit_wide":
                path.moveTo(-hw * mirror, 0)
                path.cubicTo(-hw * 0.35 * mirror, -hh * 1.15, hw * 0.35 * mirror, -hh * 1.15, hw * mirror, 0)
                path.cubicTo(hw * 0.35 * mirror, hh * 1.15, -hw * 0.35 * mirror, hh * 1.15, -hw * mirror, 0)
                path.closeSubpath()
                self._draw_white(painter, path)
                slit_w = 2.4 + (self.audio_pulse * 3.0)
                self._draw_slit_pupil(painter, slit_w, hh * 1.65, self.look_x)

            # -------------------------------------------------------------
            # 6. INNER FOCUS / DERP (Col 2 Row 2)
            # -------------------------------------------------------------
            elif active_style == "inner_focus":
                path.moveTo(-hw * 0.95 * mirror, 0)
                path.cubicTo(-hw * 0.35 * mirror, -hh * 1.1, hw * 0.5 * mirror, -hh * 1.1, hw * mirror, 0)
                path.cubicTo(hw * 0.5 * mirror, hh * 1.1, -hw * 0.35 * mirror, hh * 1.1, -hw * 0.95 * mirror, 0)
                path.closeSubpath()
                self._draw_white(painter, path)
                self._draw_circle_pupil(painter, hw * 0.80 * mirror, 0.0, 2.1)

            # -------------------------------------------------------------
            # 7. CRESCENT ARC (Col 2 Row 3)
            # -------------------------------------------------------------
            elif active_style == "crescent_arc":
                path.moveTo(-hw * mirror, hh * 0.25)
                path.cubicTo(-hw * 0.35 * mirror, -hh * 0.85, hw * 0.35 * mirror, -hh * 0.85, hw * mirror, hh * 0.25)
                path.cubicTo(hw * 0.25 * mirror, -hh * 0.15, -hw * 0.25 * mirror, -hh * 0.15, -hw * mirror, hh * 0.25)
                path.closeSubpath()
                self._draw_white(painter, path)

            # -------------------------------------------------------------
            # 8. HALF MOON GLINT (Col 2 Row 4)
            # -------------------------------------------------------------
            elif active_style == "half_moon_glint":
                path.moveTo(-hw * mirror, -hh * 0.35)
                path.lineTo(hw * mirror, -hh * 0.35)
                path.cubicTo(hw * 0.85 * mirror, hh * 1.25, -hw * 0.85 * mirror, hh * 1.25, -hw * mirror, -hh * 0.35)
                path.closeSubpath()
                self._draw_white(painter, path)

                # Scanning pupil when thinking
                scan_offset = math.sin(self.phase * 2.8) * 1.8 if self.eye_state in ("thinking", "scanning") else self.look_x
                px = scan_offset
                py = hh * 0.25 + self.look_y
                self._draw_circle_pupil(painter, px, py, 3.2)
                # Catchlight glint dot
                painter.setBrush(QBrush(QColor(255, 255, 255)))
                painter.drawEllipse(QRectF(px + 1.2 * mirror - 0.8, py - 1.2 - 0.8, 1.6, 1.6))

            # -------------------------------------------------------------
            # 9. HORNED DEMON (Col 3 Row 1)
            # -------------------------------------------------------------
            elif active_style == "horned_demon":
                path.moveTo(-hw * 0.9 * mirror, hh * 0.45)
                path.cubicTo(-hw * 0.8 * mirror, -hh * 0.2, -hw * 0.65 * mirror, -hh * 1.35, -hw * 0.5 * mirror, -hh * 1.35)
                path.cubicTo(hw * 0.1 * mirror, -hh * 0.3, hw * 0.7 * mirror, 0, hw * 0.85 * mirror, hh * 0.5)
                path.cubicTo(0, hh * 1.15, -hw * 0.5 * mirror, hh * 0.9, -hw * 0.9 * mirror, hh * 0.45)
                path.closeSubpath()
                self._draw_white(painter, path)
                self._draw_circle_pupil(painter, hw * 0.25 * mirror + self.look_x, hh * 0.35 + self.look_y, 2.5)

            # -------------------------------------------------------------
            # 10. CAT SLIT OVAL (Col 3 Row 2)
            # -------------------------------------------------------------
            elif active_style == "cat_slit_oval":
                path.moveTo(-hw * 0.9 * mirror, 0)
                path.cubicTo(-hw * 0.3 * mirror, -hh * 1.2, hw * 0.3 * mirror, -hh * 1.2, hw * 0.9 * mirror, 0)
                path.cubicTo(hw * 0.3 * mirror, hh * 1.2, -hw * 0.3 * mirror, hh * 1.2, -hw * 0.9 * mirror, 0)
                path.closeSubpath()
                self._draw_white(painter, path)
                slit_w = 2.4 + (self.audio_pulse * 2.4)
                self._draw_slit_pupil(painter, slit_w, hh * 1.55, self.look_x)

            # -------------------------------------------------------------
            # 11. SQUINT SLIT (Col 3 Row 3)
            # -------------------------------------------------------------
            elif active_style == "squint_slit":
                path.moveTo(-hw * mirror, -hh * 0.1)
                path.cubicTo(-hw * 0.3 * mirror, -hh * 0.7, hw * 0.3 * mirror, -hh * 0.7, hw * mirror, -hh * 0.1)
                path.cubicTo(hw * 0.4 * mirror, hh * 0.65, -hw * 0.4 * mirror, hh * 0.65, -hw * mirror, -hh * 0.1)
                path.closeSubpath()
                self._draw_white(painter, path)
                self._draw_slit_pupil(painter, 2.2, hh * 1.15, self.look_x)

            # -------------------------------------------------------------
            # 12. SHARP LEAF SLIT (Col 3 Row 4)
            # -------------------------------------------------------------
            elif active_style == "sharp_leaf_slit":
                path.moveTo(-hw * 1.05 * mirror, -hh * 0.2)
                path.cubicTo(-hw * 0.3 * mirror, -hh * 1.1, hw * 0.4 * mirror, -hh * 0.8, hw * 0.95 * mirror, hh * 0.2)
                path.cubicTo(hw * 0.3 * mirror, hh * 1.1, -hw * 0.4 * mirror, hh * 0.8, -hw * 1.05 * mirror, -hh * 0.2)
                path.closeSubpath()
                self._draw_white(painter, path)
                slit_w = 2.4 + (self.audio_pulse * 2.5)
                self._draw_slit_pupil(painter, slit_w, hh * 1.5, self.look_x)

            painter.restore()

    def _draw_white(self, painter: QPainter, path: QPainterPath):
        painter.setPen(QPen(QColor(255, 255, 255, 240), 0.8))
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        painter.drawPath(path)

    def _draw_circle_pupil(self, painter: QPainter, cx: float, cy: float, r: float):
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(10, 10, 14)))
        painter.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))

    def _draw_slit_pupil(self, painter: QPainter, w: float, h: float, offset_x: float = 0.0):
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(10, 10, 14)))
        path = QPainterPath()
        path.addRoundedRect(QRectF(-w / 2.0 + offset_x, -h / 2.0, w, h), w / 2.0, w / 2.0)
        painter.drawPath(path)


# Backwards compatibility alias
CuteEyesWidget = StylizedCartoonEyes


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
        self.chips_layout = QHBoxLayout()
        self.chips_layout.setSpacing(6)
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
            self.chips_layout.addWidget(chip)
        exp_layout.addLayout(self.chips_layout)

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

    def show_clipboard_chip(self, chip_info: dict):
        """Displays a reactive glowing chip when clipboard detects a URL, code, or error."""
        try:
            label = chip_info.get("label", "⚡ Action")
            action = chip_info.get("action", "")
            preview = chip_info.get("preview", "")

            if hasattr(self, "_clipboard_chip") and self._clipboard_chip is not None:
                self._clipboard_chip.deleteLater()
                self._clipboard_chip = None

            chip = QPushButton(label)
            chip.setObjectName("ActionChip")
            chip.setStyleSheet("""
                QPushButton#ActionChip {
                    background-color: rgba(245, 158, 11, 0.28);
                    border: 1px solid #F59E0B;
                    color: #FFFFFF;
                    font-weight: 700;
                }
            """)
            chip.setToolTip(f"Copied: {preview}\nClick to execute: {action}")
            chip.setCursor(Qt.CursorShape.PointingHandCursor)
            chip.clicked.connect(lambda: self.send_query_signal.emit(action))
            self._clipboard_chip = chip
            self.chips_layout.insertWidget(0, chip)

            # Update status badge
            self.set_status(f"Clip: {preview[:12]}", "alert")
        except Exception:
            pass
