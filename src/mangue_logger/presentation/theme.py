"""Design tokens + QSS (apenas apresentação)."""

from __future__ import annotations


# ── Design System ─────────────────────────────────────────────────────────────
class Theme:
    BG_BASE    = "#070a0d";  BG_SURFACE = "#0d1117"
    BG_RAISED  = "#131920";  BG_INPUT   = "#0a0f14"
    BORDER     = "#1a2332";  BORDER_LT  = "#243347"
    TEXT_PRI   = "#e8f1fc";  TEXT_SEC   = "#6d8aaa";  TEXT_DIM = "#344d66"
    ACCENT     = "#00e5ff";  ACCENT_DIM = "#007799";  ACCENT_BG = "#00e5ff14"
    ACCENT2    = "#ff6b2b";  ACCENT2_BG = "#ff6b2b14"
    ACCENT3    = "#00ff94"
    HOVER      = "#162030";  ACTIVE  = "#0a1520"
    DANGER     = "#ff3355";  SUCCESS = "#00ff94";  WARNING = "#ffcc00"
    SERIES = ["#00e5ff","#ff6b2b","#00ff94","#ff2d7a","#aa44ff",
              "#ffcc00","#26d9ff","#ff5533","#44ffbb","#ff99cc","#88aaff","#ccff44"]
    FONT_MONO = "JetBrains Mono, Consolas, monospace"
    FONT_UI   = "Segoe UI, SF Pro Display, system-ui, sans-serif"

    PHASE_COLORS = {
        'aceleração':    '#00ff94',
        'frenagem':      '#ff3355',
        'estabilização': '#ffcc00',
    }

    @staticmethod
    def qss() -> str:
        T = Theme
        return f"""
QWidget {{ background:{T.BG_BASE}; color:{T.TEXT_PRI};
           font-family:{T.FONT_UI}; font-size:11px;
           selection-background-color:{T.ACCENT_DIM}; selection-color:{T.TEXT_PRI}; }}
QMainWindow, QDialog {{ background:{T.BG_BASE}; border:none; }}
QGroupBox {{ background:{T.BG_SURFACE}; border:1px solid {T.BORDER}; border-radius:8px;
             margin-top:20px; padding:10px 8px 8px 8px;
             font-size:9px; font-weight:bold; letter-spacing:2px; color:{T.ACCENT_DIM}; }}
QGroupBox::title {{ subcontrol-origin:margin; subcontrol-position:top left;
                    left:12px; top:3px; background:{T.BG_SURFACE}; padding:0 6px; }}
QLabel {{ background:transparent; color:{T.TEXT_SEC}; }}
QPushButton {{ background:{T.BG_RAISED}; color:{T.TEXT_PRI}; border:1px solid {T.BORDER_LT};
               border-radius:6px; padding:5px 14px; font-size:11px; }}
QPushButton:hover   {{ background:{T.HOVER}; border-color:{T.ACCENT_DIM}; color:{T.ACCENT}; }}
QPushButton:pressed {{ background:{T.ACTIVE}; }}
QPushButton:checked {{ background:{T.ACCENT_BG}; border-color:{T.ACCENT}; color:{T.ACCENT}; }}
QPushButton:disabled {{ background:{T.BG_SURFACE}; color:{T.TEXT_DIM}; border-color:{T.BORDER}; }}
QPushButton#CTA {{ background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
    stop:0 {T.ACCENT_DIM},stop:1 #0044bb); color:#fff; border:none;
    border-radius:6px; font-weight:bold; padding:7px 20px; }}
QPushButton#CTA:hover {{ background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
    stop:0 {T.ACCENT},stop:1 #0066ff); }}
QComboBox {{ background:{T.BG_INPUT}; border:1px solid {T.BORDER_LT}; border-radius:6px;
             padding:4px 8px; color:{T.TEXT_PRI}; font-size:11px; min-height:28px; }}
QComboBox:hover {{ border-color:{T.ACCENT_DIM}; }}
QComboBox:focus {{ border-color:{T.ACCENT}; }}
QComboBox::drop-down {{ border:none; width:22px; }}
QComboBox::down-arrow {{ image:none; border-left:4px solid transparent;
    border-right:4px solid transparent; border-top:5px solid {T.TEXT_SEC}; margin-right:7px; }}
QComboBox QAbstractItemView {{ background:{T.BG_RAISED}; border:1px solid {T.BORDER_LT};
    border-radius:6px; selection-background-color:{T.HOVER}; color:{T.TEXT_PRI}; padding:4px; }}
QLineEdit {{ background:{T.BG_INPUT}; border:1px solid {T.BORDER_LT}; border-radius:6px;
             padding:5px 10px; color:{T.TEXT_PRI}; font-size:11px; }}
QLineEdit:hover {{ border-color:{T.ACCENT_DIM}; }}
QLineEdit:focus {{ border-color:{T.ACCENT}; }}
QTextEdit {{ background:{T.BG_INPUT}; border:1px solid {T.BORDER_LT};
             border-radius:6px; padding:6px; color:{T.TEXT_PRI}; }}
QTextEdit:focus {{ border-color:{T.ACCENT}; }}
QListWidget {{ background:{T.BG_INPUT}; border:1px solid {T.BORDER}; border-radius:6px;
               padding:3px; outline:none; font-size:10px; color:{T.TEXT_SEC}; }}
QListWidget::item {{ padding:4px 8px; border-radius:4px; }}
QListWidget::item:hover    {{ background:{T.HOVER}; color:{T.TEXT_PRI}; }}
QListWidget::item:selected {{ background:{T.ACCENT_BG}; color:{T.ACCENT}; }}
QTreeWidget {{ background:{T.BG_INPUT}; border:1px solid {T.BORDER}; border-radius:6px;
               outline:none; font-size:10px; color:{T.TEXT_SEC}; }}
QTreeWidget::item {{ padding:3px 6px; border-radius:4px; }}
QTreeWidget::item:hover    {{ background:{T.HOVER}; color:{T.TEXT_PRI}; }}
QTreeWidget::item:selected {{ background:{T.ACCENT_BG}; color:{T.ACCENT}; }}
QTableWidget {{ background:{T.BG_INPUT}; border:1px solid {T.BORDER}; border-radius:6px;
                gridline-color:{T.BORDER}; outline:none; font-size:10px; }}
QHeaderView::section {{ background:{T.BG_RAISED}; color:{T.ACCENT_DIM}; border:none;
    border-bottom:1px solid {T.BORDER_LT}; padding:5px 8px;
    font-size:9px; font-weight:bold; letter-spacing:1px; }}
QTableWidget::item               {{ color:{T.TEXT_PRI}; padding:3px 6px; }}
QTableWidget::item:selected      {{ background:{T.ACCENT_BG}; color:{T.ACCENT}; }}
QTableWidget::item:alternate     {{ background:{T.BG_SURFACE}; }}
QSlider::groove:horizontal {{ height:3px; background:{T.BORDER_LT}; border-radius:2px; }}
QSlider::handle:horizontal {{ background:{T.ACCENT}; border:2px solid {T.BG_BASE};
    width:13px; height:13px; margin:-5px 0; border-radius:7px; }}
QSlider::handle:horizontal:hover {{ background:#fff; width:15px; height:15px; margin:-6px 0; }}
QSlider::sub-page:horizontal {{ background:{T.ACCENT_DIM}; border-radius:2px; }}
QScrollBar:vertical {{ background:{T.BG_SURFACE}; width:5px; border-radius:3px; }}
QScrollBar::handle:vertical {{ background:{T.BORDER_LT}; border-radius:3px; min-height:30px; }}
QScrollBar::handle:vertical:hover {{ background:{T.ACCENT_DIM}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
QScrollBar:horizontal {{ background:{T.BG_SURFACE}; height:5px; border-radius:3px; }}
QScrollBar::handle:horizontal {{ background:{T.BORDER_LT}; border-radius:3px; min-width:30px; }}
QScrollBar::handle:horizontal:hover {{ background:{T.ACCENT_DIM}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width:0; }}
QSplitter::handle {{ background:{T.BORDER}; }}
QSplitter::handle:hover {{ background:{T.ACCENT_DIM}; }}
QSplitter::handle:vertical {{ height:4px; }} QSplitter::handle:horizontal {{ width:4px; }}
QScrollArea {{ border:none; background:transparent; }}
QScrollArea > QWidget > QWidget {{ background:transparent; }}
QCheckBox {{ color:{T.TEXT_SEC}; spacing:6px; }}
QCheckBox::indicator {{ width:14px; height:14px; border:1px solid {T.BORDER_LT};
    border-radius:3px; background:{T.BG_INPUT}; }}
QCheckBox::indicator:hover   {{ border-color:{T.ACCENT_DIM}; }}
QCheckBox::indicator:checked {{ background:{T.ACCENT_DIM}; border-color:{T.ACCENT}; }}
QRadioButton {{ color:{T.TEXT_SEC}; spacing:6px; }}
QRadioButton::indicator {{ width:13px; height:13px; border:1px solid {T.BORDER_LT};
    border-radius:7px; background:{T.BG_INPUT}; }}
QRadioButton::indicator:checked {{ background:{T.ACCENT}; border-color:{T.ACCENT}; }}
QMenu {{ background:{T.BG_RAISED}; border:1px solid {T.BORDER_LT}; border-radius:8px;
         padding:5px; color:{T.TEXT_PRI}; }}
QMenu::item {{ padding:6px 28px 6px 14px; border-radius:5px; }}
QMenu::item:selected {{ background:{T.HOVER}; color:{T.ACCENT}; }}
QMenu::separator {{ height:1px; background:{T.BORDER}; margin:5px 10px; }}
QStatusBar {{ background:{T.BG_RAISED}; border-top:1px solid {T.BORDER};
              color:{T.TEXT_SEC}; font-size:10px; padding:0 10px; }}
QToolButton {{ background:transparent; border:1px solid transparent; border-radius:6px;
               padding:4px 10px; color:{T.TEXT_SEC}; font-size:11px; }}
QToolButton:hover {{ background:{T.HOVER}; color:{T.TEXT_PRI}; border-color:{T.BORDER_LT}; }}
QToolButton:pressed {{ background:{T.ACTIVE}; }}
QToolButton::menu-indicator {{ image:none; }}
QFrame#BrandBar {{ background:{T.BG_RAISED}; border-bottom:2px solid {T.ACCENT_DIM}; }}
QFrame#TabBar   {{ background:{T.BG_RAISED}; border-top:1px solid {T.BORDER}; }}
QPushButton#Tab {{ background:transparent; border:none; border-top:2px solid transparent;
    border-radius:0; color:{T.TEXT_DIM}; padding:0 28px; font-size:10px;
    font-weight:bold; letter-spacing:1.5px; }}
QPushButton#Tab:hover   {{ background:{T.HOVER}; color:{T.TEXT_PRI}; }}
QPushButton#Tab:checked {{ color:{T.ACCENT}; background:{T.ACCENT_BG}; border-top:2px solid {T.ACCENT}; }}
"""
