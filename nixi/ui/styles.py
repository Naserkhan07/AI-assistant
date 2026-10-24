"""
Nixi Ultra-Premium Glassmorphism Style System
Crafted with frosted translucency, ambient refraction borders, and glowing micro-interactions.
"""

PILL_STYLE = """
QWidget#PillContainer {
    background-color: rgba(18, 20, 30, 0.88);
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-top: 1px solid rgba(255, 255, 255, 0.28);
    border-radius: 23px;
}

QLabel#StatusText {
    color: #F9FAFB;
    font-family: 'Segoe UI Variable Display', 'Segoe UI', system-ui, sans-serif;
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 0.3px;
}

QLabel#StatusSub {
    color: #9CA3AF;
    font-family: 'Segoe UI', system-ui, sans-serif;
    font-size: 11px;
}

QToolButton {
    background-color: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 15px;
    color: #D1D5DB;
    font-size: 13px;
    padding: 5px;
}

QToolButton:hover {
    background-color: rgba(255, 255, 255, 0.16);
    border: 1px solid rgba(255, 255, 255, 0.25);
    color: #FFFFFF;
}

QToolButton:pressed {
    background-color: rgba(255, 255, 255, 0.22);
}

QToolButton#DictateActive {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(245, 158, 11, 0.35), stop:1 rgba(217, 119, 6, 0.45));
    color: #FDE68A;
    border: 1px solid rgba(251, 191, 36, 0.7);
}

QToolButton#ScreenActive {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(6, 182, 212, 0.35), stop:1 rgba(14, 165, 233, 0.45));
    color: #A5F3FC;
    border: 1px solid rgba(34, 211, 238, 0.7);
}

QToolButton#CloseBtn {
    background-color: transparent;
    border: none;
    color: #9CA3AF;
    font-size: 12px;
}

QToolButton#CloseBtn:hover {
    background-color: rgba(239, 68, 68, 0.3);
    color: #FCA5A5;
    border-radius: 12px;
}
"""

DRAWER_STYLE = """
QWidget#DrawerContainer {
    background-color: rgba(16, 18, 27, 0.90);
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-top: 1px solid rgba(255, 255, 255, 0.28);
    border-radius: 20px;
}

QLabel#DrawerTitle {
    color: #FFFFFF;
    font-family: 'Segoe UI Variable Display', 'Segoe UI', system-ui, sans-serif;
    font-size: 15px;
    font-weight: 700;
    letter-spacing: 0.2px;
}

QLabel#ModelBadge {
    background-color: rgba(99, 102, 241, 0.2);
    border: 1px solid rgba(129, 140, 248, 0.4);
    border-radius: 8px;
    color: #A5B4FC;
    font-family: 'Segoe UI', sans-serif;
    font-size: 11px;
    font-weight: 600;
    padding: 3px 8px;
}

/* Force complete transparency on the scroll area and viewport */
QScrollArea, QScrollArea > QWidget > QWidget {
    background: transparent !important;
    background-color: transparent !important;
    border: none;
}

QScrollArea #qt_scrollarea_viewport {
    background: transparent !important;
    background-color: transparent !important;
    border: none;
}

QWidget#MessagesWidget {
    background: transparent !important;
    background-color: transparent !important;
}

QScrollBar:vertical {
    border: none;
    background: transparent;
    width: 6px;
    margin: 4px 0px;
}

QScrollBar::handle:vertical {
    background: rgba(255, 255, 255, 0.20);
    min-height: 30px;
    border-radius: 3px;
}

QScrollBar::handle:vertical:hover {
    background: rgba(255, 255, 255, 0.40);
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* Chat Input Bar */
QLineEdit#ChatInput {
    background-color: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-top: 1px solid rgba(255, 255, 255, 0.20);
    border-radius: 14px;
    color: #FFFFFF;
    font-family: 'Segoe UI', system-ui, sans-serif;
    font-size: 13px;
    padding: 10px 16px;
    selection-background-color: #6366F1;
}

QLineEdit#ChatInput:focus {
    border: 1px solid #818CF8;
    background-color: rgba(255, 255, 255, 0.10);
}

QPushButton#SendButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #6366F1, stop:1 #8B5CF6);
    border: 1px solid rgba(255, 255, 255, 0.25);
    border-radius: 14px;
    color: #FFFFFF;
    font-family: 'Segoe UI', system-ui, sans-serif;
    font-size: 13px;
    font-weight: 600;
    padding: 10px 18px;
}

QPushButton#SendButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #4F46E5, stop:1 #7C3AED);
    border: 1px solid rgba(255, 255, 255, 0.4);
}

QPushButton#SendButton:pressed {
    background-color: #4338CA;
}

/* Quick Action Chips */
QPushButton#QuickChip {
    background-color: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 11px;
    color: #E5E7EB;
    font-family: 'Segoe UI', sans-serif;
    font-size: 11px;
    font-weight: 500;
    padding: 6px 12px;
}

QPushButton#QuickChip:hover {
    background-color: rgba(99, 102, 241, 0.25);
    border: 1px solid rgba(129, 140, 248, 0.5);
    color: #EEF2FF;
}

QPushButton#HeaderBtn {
    background-color: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 12px;
    color: #9CA3AF;
    font-size: 11px;
    padding: 4px 10px;
}

QPushButton#HeaderBtn:hover {
    background-color: rgba(255, 255, 255, 0.12);
    color: #FFFFFF;
}

/* Bubbles */
QFrame#UserBubble {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #4F46E5, stop:1 #7C3AED);
    border: 1px solid rgba(255, 255, 255, 0.18);
    border-radius: 16px;
    border-bottom-right-radius: 4px;
}

QFrame#AiBubble {
    background-color: rgba(255, 255, 255, 0.07);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-top: 1px solid rgba(255, 255, 255, 0.22);
    border-radius: 16px;
    border-bottom-left-radius: 4px;
}

QLabel#UserBubbleText {
    color: #FFFFFF;
    font-family: 'Segoe UI', system-ui, sans-serif;
    font-size: 13px;
    line-height: 1.45;
}

QLabel#AiBubbleText {
    color: #F3F4F6;
    font-family: 'Segoe UI', system-ui, sans-serif;
    font-size: 13px;
    line-height: 1.45;
}
"""
