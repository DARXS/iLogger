# =============================================================================
#  analysis_view.py — Mangue Logger v6
#  Contém TODOS os widgets de análise em um único módulo:
#    FilterPanel · ChannelBrowser · ThemeCustomizer · VirtualChannelEditor
#    PlotPanel · MultiAxisOverlay · StatsPanel · IntelligencePanel
#    ComparePanel · PanelCanvas · AnalysisWidget (entry point)
# =============================================================================

import numpy as np
import pyqtgraph as pg
from functools import partial

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel, QPushButton,
    QSplitter, QComboBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QColorDialog, QAbstractItemView, QButtonGroup, QRadioButton,
    QSlider, QCheckBox, QSizePolicy, QStackedWidget, QMenu, QToolButton,
    QSizeGrip, QScrollArea, QLineEdit, QInputDialog, QMessageBox,
    QTreeWidget, QTreeWidgetItem, QTextEdit, QSpinBox, QDialog,
    QListWidget, QListWidgetItem, QGridLayout, QApplication,
)
from PyQt6.QtCore import Qt, pyqtSignal, QBuffer, QIODevice, QPoint, QTimer, QSettings
from PyQt6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat

from ..constants import CHANNELS, CHANNEL_UNITS, CHANNEL_GROUPS, SCATTER_PAIRS
from ..theme import Theme
from ...application.analysis import compute_correlation_matrix
from ...application.analysis import full_analysis as _full_analysis
from ...application.virtual_channels import VirtualChannel
from ...domain.errors import ExpressionError
from ...infrastructure.storage.workspace import WorkspaceManager

import logging
from ...application.session import DEFAULT_FILTER
_log = logging.getLogger(__name__)
WS = WorkspaceManager()   # sem efeitos colaterais no import; diretórios só nascem na primeira escrita


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _bg():      return Theme.BG_BASE
def _fg():      return Theme.TEXT_SEC
def _surface(): return Theme.BG_SURFACE
def _border():  return Theme.BORDER
def _toolbar(): return Theme.BG_RAISED
def _text():    return Theme.TEXT_PRI
def _subtle():  return Theme.TEXT_DIM
def _accent():  return Theme.ACCENT

_SLA = "#FFD54F"   # sync line A colour
_SLB = "#FF6E40"   # sync line B colour
_RGN = (0, 229, 255, 18)

LEVEL_COLOR = {'info': Theme.ACCENT, 'warning': Theme.WARNING,
               'critical': Theme.DANGER, 'good': Theme.SUCCESS}
LEVEL_ICON  = {'info': 'ℹ', 'warning': '⚠', 'critical': '🔴', 'good': '✅'}

_SHORT = {"Tempo (s)":"t","RPM (Filtrado)":"RPM","RPM (Bruto)":"RPM₀",
          "Velocidade (Km/h - Filtrado)":"Vel","Velocidade (Km/h - Bruto)":"Vel₀",
          "Aceleração (m/s² - Filtrado)":"Acel","Distância (m)":"Dist"}


def _pen(color: str, w: int = 2):
    return pg.mkPen(pg.mkColor(color), width=w)


def _style_pi(pi, gx, gy, ga, show_x=True, x_lbl='', y_lbl=''):
    vb = pi.getViewBox()
    if vb: vb.setBackgroundColor(_bg())
    for ax in ('bottom','left','top','right'):
        a = pi.getAxis(ax); a.setPen(_fg()); a.setTextPen(_fg())
    pi.showGrid(x=gx, y=gy, alpha=ga)
    pi.setDownsampling(mode='peak'); pi.setClipToView(True)
    pi.getAxis('bottom').setStyle(showValues=show_x)
    if y_lbl: pi.setLabel('left',   y_lbl, **{'font-size':'8pt','color':_fg()})
    if show_x and x_lbl: pi.setLabel('bottom', x_lbl, **{'font-size':'8pt','color':_fg()})


def _mkbtn(txt, h=30, css=''):
    b = QPushButton(txt); b.setFixedHeight(h)
    base = (f"QPushButton{{background:{Theme.BG_RAISED};"
            f"border:1px solid {Theme.BORDER_LT};border-radius:6px;"
            f"color:{Theme.TEXT_PRI};padding:0 12px;font-size:11px;}}"
            f"QPushButton:hover{{background:{Theme.HOVER};"
            f"color:{Theme.ACCENT};border-color:{Theme.ACCENT_DIM};}}")
    b.setStyleSheet(base + css); return b


def _mkcta(txt, h=32):
    b = QPushButton(txt); b.setFixedHeight(h)
    b.setStyleSheet(
        f"QPushButton{{background:{Theme.ACCENT_BG};"
        f"border:1px solid {Theme.ACCENT_DIM};border-radius:6px;"
        f"color:{Theme.ACCENT};font-weight:bold;font-size:11px;padding:0 16px;}}"
        f"QPushButton:hover{{background:{Theme.HOVER};border-color:{Theme.ACCENT};}}")
    return b


# ─── ViewSettings ─────────────────────────────────────────────────────────────

class ViewSettings:
    line_width = 2; grid_x = True; grid_y = True; grid_alpha = 0.10
    antialias  = True; sync_windows = True


# ═════════════════════════════════════════════════════════════════════════════
#  FILTER PANEL
# ═════════════════════════════════════════════════════════════════════════════

class FilterPanel(QWidget):
    filter_changed = pyqtSignal(dict)
    _DEBOUNCE = 150

    def __init__(self, parent=None):
        super().__init__(parent)
        vl = QVBoxLayout(self); vl.setContentsMargins(5,5,5,5); vl.setSpacing(8)
        self._timer = QTimer(self); self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._emit)

        # Tipo
        self._combo = QComboBox()
        self._combo.addItems(['butterworth','savitzky_golay','chebyshev_type_i',
                              'bessel','median','moving_average'])
        vl.addWidget(QLabel("Tipo de Filtro:")); vl.addWidget(self._combo)

        # Grid de controles
        self._grid = QGridLayout(); self._grid.setColumnStretch(1,1)
        vl.addLayout(self._grid)
        self._widgets: dict[str, list] = {}
        self._sliders: dict[str, QSlider] = {}
        self._vlabels: dict[str, QLabel]  = {}

        defs = {
            'butterworth': [
                ('butter_order',  'Ordem',   1,10, 4,  False,False),
                ('butter_cutoff', 'Cutoff',  1,99, 10, True, False),
            ],
            'savitzky_golay': [
                ('savgol_window',    'Janela',   5,99, 11, False, True),
                ('savgol_polyorder', 'Pol. Ord.',1,10, 2,  False, False),
            ],
            'chebyshev_type_i': [
                ('cheby1_order',  'Ordem',   1,10, 4,  False, False),
                ('cheby1_rp',     'Ripple',  1,10, 1,  False, False),
                ('cheby1_cutoff', 'Cutoff',  1,99, 10, True,  False),
            ],
            'bessel': [
                ('bessel_order',  'Ordem',  1,10, 4,  False, False),
                ('bessel_cutoff', 'Cutoff', 1,99, 10, True,  False),
            ],
            'median': [
                ('median_kernel', 'Kernel', 3,99, 5, False, True),
            ],
            'moving_average': [
                ('ma_window', 'Janela', 3,99, 5, False, False),
            ],
        }
        row = 0
        for ft, controls in defs.items():
            self._widgets[ft] = []
            for name, lbl, mn, mx, iv, is_f, is_odd in controls:
                l = QLabel(lbl)
                s = QSlider(Qt.Orientation.Horizontal)
                s.setRange(mn, mx); s.setValue(iv)
                vl_txt = QLabel(f"{iv/100:.2f}" if is_f else str(iv))
                vl_txt.setFixedWidth(32)
                self._grid.addWidget(l, row, 0)
                self._grid.addWidget(s, row, 1)
                self._grid.addWidget(vl_txt, row, 2)
                upd = partial(self._upd_label, lbl=vl_txt, is_f=is_f, is_odd=is_odd)
                s.valueChanged.connect(upd)
                s.valueChanged.connect(lambda _: self._timer.start(self._DEBOUNCE))
                setattr(self, name + '_slider', s)
                self._widgets[ft].extend([l, s, vl_txt])
                self._sliders[name] = s
                self._vlabels[name] = vl_txt
                row += 1

        # Presets
        pr_row = QHBoxLayout()
        self._preset_cb = QComboBox(); self._preset_cb.setFixedHeight(26)
        self._refresh_presets()
        b_load = _mkbtn("Carregar", 26)
        b_save = _mkbtn("Salvar…", 26)
        b_load.clicked.connect(self._load_preset)
        b_save.clicked.connect(self._save_preset)
        pr_row.addWidget(self._preset_cb, 1)
        pr_row.addWidget(b_load); pr_row.addWidget(b_save)
        vl.addLayout(pr_row)
        vl.addStretch()

        self._combo.currentTextChanged.connect(self._on_type_change)
        self._update_visibility()
        QTimer.singleShot(0, self._emit)

    def _upd_label(self, val, lbl, is_f, is_odd):
        if is_odd and val % 2 == 0: val += 1
        lbl.setText(f"{val/100:.2f}" if is_f else str(val))

    def _on_type_change(self):
        self._update_visibility()
        self._timer.start(0)

    def _update_visibility(self):
        sel = self._combo.currentText()
        for ft, ws in self._widgets.items():
            for w in ws: w.setVisible(ft == sel)

    def _emit(self):
        self.filter_changed.emit(self.settings())

    def settings(self) -> dict:
        ft = self._combo.currentText()
        s  = {'type': ft}
        if ft == 'butterworth':
            s['butter_order']  = self._sliders['butter_order'].value()
            s['butter_cutoff'] = self._sliders['butter_cutoff'].value() / 100.0
        elif ft == 'savitzky_golay':
            w = self._sliders['savgol_window'].value()
            w = w if w % 2 else w + 1
            p = min(self._sliders['savgol_polyorder'].value(), w - 1)
            s['savgol_window'] = w; s['savgol_polyorder'] = p
        elif ft == 'chebyshev_type_i':
            s['cheby1_order']  = self._sliders['cheby1_order'].value()
            s['cheby1_rp']     = self._sliders['cheby1_rp'].value()
            s['cheby1_cutoff'] = self._sliders['cheby1_cutoff'].value() / 100.0
        elif ft == 'bessel':
            s['bessel_order']  = self._sliders['bessel_order'].value()
            s['bessel_cutoff'] = self._sliders['bessel_cutoff'].value() / 100.0
        elif ft == 'median':
            k = self._sliders['median_kernel'].value()
            s['median_kernel'] = k if k % 2 else k + 1
        elif ft == 'moving_average':
            s['moving_avg_window'] = self._sliders['ma_window'].value()
        return s

    def _refresh_presets(self):
        self._preset_cb.clear()
        self._preset_cb.addItem("— preset —")
        for n in WS.list_presets(): self._preset_cb.addItem(n)

    def _load_preset(self):
        n = self._preset_cb.currentText()
        if n == "— preset —": return
        cfg = WS.get_preset(n)
        if cfg: self.filter_changed.emit(cfg)

    def _save_preset(self):
        n, ok = QInputDialog.getText(self, "Salvar Preset", "Nome:")
        if ok and n.strip():
            WS.save_preset(n.strip(), self.settings())
            self._refresh_presets()


# ═════════════════════════════════════════════════════════════════════════════
#  CHANNEL BROWSER
# ═════════════════════════════════════════════════════════════════════════════

class ChannelBrowser(QWidget):
    sig_add    = pyqtSignal(str, object)   # (signal_key, run)
    sigs_add   = pyqtSignal(list)          # [(sk, run), …]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._runs = []; self._vcs = []; self._fs = {}
        self._favs: set = self._load_favs()
        self._filter = "all"
        vl = QVBoxLayout(self); vl.setContentsMargins(6,8,6,6); vl.setSpacing(5)

        hdr = QLabel("CANAIS")
        hdr.setStyleSheet(f"color:{Theme.ACCENT_DIM};font-size:9px;font-weight:bold;"
                          f"letter-spacing:2.5px;background:transparent;")
        vl.addWidget(hdr)

        self._search = QLineEdit(); self._search.setPlaceholderText("🔍 Buscar…")
        self._search.setClearButtonEnabled(True)
        self._search.setStyleSheet(
            f"background:{Theme.BG_INPUT};border:1px solid {Theme.BORDER_LT};"
            f"border-radius:6px;padding:4px 8px;color:{Theme.TEXT_PRI};font-size:10px;")
        self._stimer = QTimer(self); self._stimer.setSingleShot(True)
        self._stimer.timeout.connect(self._apply_filter)
        self._search.textChanged.connect(lambda: self._stimer.start(200))
        vl.addWidget(self._search)

        # Pills
        pill_css = (f"QPushButton{{border:1px solid {Theme.BORDER};border-radius:4px;"
                    f"background:transparent;color:{Theme.TEXT_DIM};font-size:8px;"
                    f"font-weight:bold;padding:2px 6px;letter-spacing:1px;}}"
                    f"QPushButton:checked{{background:{Theme.ACCENT_BG};"
                    f"color:{Theme.ACCENT};border-color:{Theme.ACCENT_DIM};}}"
                    f"QPushButton:hover{{color:{Theme.TEXT_PRI};}}")
        pr = QHBoxLayout(); pr.setSpacing(3)
        self._pall  = QPushButton("TODOS"); self._pfav = QPushButton("★ FAV")
        self._pvirt = QPushButton("⚙ VIRT")
        for b in (self._pall, self._pfav, self._pvirt):
            b.setFixedHeight(22); b.setCheckable(True); b.setStyleSheet(pill_css)
            pr.addWidget(b)
        pr.addStretch()
        self._pall.setChecked(True)
        self._pall.clicked.connect(lambda: self._set_filter("all"))
        self._pfav.clicked.connect(lambda: self._set_filter("fav"))
        self._pvirt.clicked.connect(lambda: self._set_filter("virtual"))
        vl.addLayout(pr)

        self._tree = QTreeWidget(); self._tree.setHeaderHidden(True)
        self._tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._tree.setStyleSheet(
            f"QTreeWidget{{background:{Theme.BG_INPUT};border:1px solid {Theme.BORDER};"
            f"border-radius:6px;outline:none;font-size:10px;color:{Theme.TEXT_SEC};}}"
            f"QTreeWidget::item{{padding:3px 4px;border-radius:4px;}}"
            f"QTreeWidget::item:hover{{background:{Theme.HOVER};color:{Theme.TEXT_PRI};}}"
            f"QTreeWidget::item:selected{{background:{Theme.ACCENT_BG};color:{Theme.ACCENT};}}")
        self._tree.itemDoubleClicked.connect(self._on_dbl)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._ctx)
        self._tree.itemSelectionChanged.connect(self._update_stat)
        vl.addWidget(self._tree, 1)

        b_add = _mkcta("＋  Adicionar ao Canvas")
        b_add.clicked.connect(self._add_selected)
        vl.addWidget(b_add)

        self._stat = QLabel("—")
        self._stat.setWordWrap(True)
        self._stat.setStyleSheet(
            f"color:{Theme.TEXT_DIM};font-size:8px;font-family:{Theme.FONT_MONO};"
            f"background:transparent;padding:3px;")
        vl.addWidget(self._stat)

    def set_data(self, runs, fs, vcs=None):
        self._runs = runs; self._fs = fs; self._vcs = vcs or []
        self._rebuild()

    def _rebuild(self):
        self._tree.clear()
        for ri, run in enumerate(self._runs):
            color = Theme.SERIES[ri % len(Theme.SERIES)]
            ri_item = QTreeWidgetItem(self._tree, [f"  📁  {run.file_name}"])
            ri_item.setExpanded(True)
            ri_item.setFlags(ri_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            ri_item.setForeground(0, QColor(color))
            for grp, keys in CHANNEL_GROUPS.items():
                gi = QTreeWidgetItem(ri_item, [f"  {grp}"])
                gi.setExpanded(True)
                gi.setFlags(gi.flags() & ~Qt.ItemFlag.ItemIsSelectable)
                gi.setForeground(0, QColor(Theme.TEXT_DIM))
                for sk in keys:
                    unit = CHANNEL_UNITS.get(sk,'')
                    ci   = QTreeWidgetItem(gi, [f"  {sk}{'  ['+unit+']' if unit else ''}"])
                    ci.setForeground(0, QColor(color))
                    ci.setData(0, Qt.ItemDataRole.UserRole, (sk, run))
                    fav_key = f"{run.file_name}::{sk}"
                    if fav_key in self._favs:
                        ci.setText(0, "★" + ci.text(0))
        if self._vcs:
            vr = QTreeWidgetItem(self._tree, ["  ⚙  Canais Virtuais"])
            vr.setExpanded(True)
            vr.setFlags(vr.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            vr.setForeground(0, QColor(Theme.ACCENT2))
            for vc in self._vcs:
                if not vc.enabled: continue
                for run in self._runs:
                    ci = QTreeWidgetItem(vr, [f"  [V] {vc.name}"])
                    ci.setForeground(0, QColor(vc.color))
                    ci.setData(0, Qt.ItemDataRole.UserRole, (f"[V]{vc.name}", run))
                    ci.setData(0, Qt.ItemDataRole.UserRole+1, vc)
        self._apply_filter()

    def _apply_filter(self):
        q = self._search.text().strip().lower()
        def visit(item):
            d = item.data(0, Qt.ItemDataRole.UserRole)
            if d:
                txt = item.text(0).lower()
                fk  = ""
                if isinstance(d, tuple) and len(d) == 2:
                    sk, run = d
                    fk = f"{run.file_name}::{sk}"
                vis = True
                if q and q not in txt: vis = False
                if self._filter == "fav"     and fk not in self._favs:       vis = False
                if self._filter == "virtual" and not item.text(0).startswith("  [V]"): vis = False
                item.setHidden(not vis); return vis
            any_v = False
            for i in range(item.childCount()):
                if visit(item.child(i)): any_v = True
            item.setHidden(not any_v); return any_v
        for i in range(self._tree.topLevelItemCount()):
            visit(self._tree.topLevelItem(i))

    def _set_filter(self, f):
        self._filter = f
        for b, m in [(self._pall,"all"),(self._pfav,"fav"),(self._pvirt,"virtual")]:
            b.setChecked(m == f)
        self._apply_filter()

    def _on_dbl(self, item, _):
        d = item.data(0, Qt.ItemDataRole.UserRole)
        if d: self.sig_add.emit(*d)

    def _add_selected(self):
        sel = [(i.data(0, Qt.ItemDataRole.UserRole)) for i in self._tree.selectedItems()
               if i.data(0, Qt.ItemDataRole.UserRole)]
        if sel: self.sigs_add.emit(sel)

    def _ctx(self, pos):
        item = self._tree.itemAt(pos)
        if not item: return
        d = item.data(0, Qt.ItemDataRole.UserRole)
        if not d: return
        sk, run = d
        fk = f"{run.file_name}::{sk}"
        m  = QMenu(self._tree)
        m.setStyleSheet(
            f"QMenu{{background:{Theme.BG_RAISED};border:1px solid {Theme.BORDER_LT};"
            f"border-radius:8px;padding:5px;}}"
            f"QMenu::item{{padding:6px 24px 6px 12px;border-radius:5px;}}"
            f"QMenu::item:selected{{background:{Theme.HOVER};color:{Theme.ACCENT};}}")
        m.addAction("📈  Adicionar ao canvas").triggered.connect(lambda: self.sig_add.emit(sk, run))
        m.addSeparator()
        if fk in self._favs:
            m.addAction("☆  Remover favorito").triggered.connect(lambda: self._toggle_fav(item, fk, False))
        else:
            m.addAction("★  Adicionar favorito").triggered.connect(lambda: self._toggle_fav(item, fk, True))
        m.addSeparator()
        m.addAction("📊  Estatísticas completas").triggered.connect(lambda: self._full_stats(sk, run))
        m.exec(self._tree.viewport().mapToGlobal(pos))

    def _toggle_fav(self, item, fk, add):
        if add: self._favs.add(fk)
        else:   self._favs.discard(fk)
        t = item.text(0)
        if add and not t.startswith("★"): item.setText(0, "★" + t)
        if not add and t.startswith("★"):  item.setText(0, t[1:])
        QSettings("MangueBaja","iLogger").setValue("favs", "|".join(self._favs))
        if self._filter == "fav": self._apply_filter()

    def _load_favs(self):
        raw = QSettings("MangueBaja","iLogger").value("favs","")
        return set(raw.split("|")) if raw else set()

    def _update_stat(self):
        items = self._tree.selectedItems()
        if not items: self._stat.setText("—"); return
        d = items[0].data(0, Qt.ItemDataRole.UserRole)
        if not d: return
        sk, run = d
        yd = run.get_channel(sk) if hasattr(run,'get_channel') else np.array([])
        if yd.size == 0: self._stat.setText("Sem dados"); return
        unit = CHANNEL_UNITS.get(sk,'')
        self._stat.setText(f"n={yd.size}  min={yd.min():.4g}  max={yd.max():.4g}\n"
                           f"mean={yd.mean():.4g}  σ={yd.std():.4g}  [{unit}]")
        self._stat.setStyleSheet(
            f"color:{Theme.ACCENT};font-size:8px;font-family:{Theme.FONT_MONO};"
            f"background:transparent;padding:3px;")

    def _full_stats(self, sk, run):
        yd = run.get_channel(sk) if hasattr(run,'get_channel') else np.array([])
        if yd.size == 0: QMessageBox.information(self,"Stats","Sem dados."); return
        p25,p50,p75 = np.percentile(yd,[25,50,75])
        QMessageBox.information(self, f"Estatísticas — {sk}",
            f"Canal: {sk}\nRun: {run.file_name}\nUnidade: {CHANNEL_UNITS.get(sk,'N/A')}\n"
            f"{'─'*36}\nn={yd.size}\nMin={yd.min():.6g}  Max={yd.max():.6g}\n"
            f"Média={yd.mean():.6g}  σ={yd.std():.6g}\n"
            f"P25={p25:.6g}  P50={p50:.6g}  P75={p75:.6g}  IQR={p75-p25:.6g}")


# ═════════════════════════════════════════════════════════════════════════════
#  THEME CUSTOMIZER  (dialog)
# ═════════════════════════════════════════════════════════════════════════════

class ThemeCustomizer(QDialog):
    applied = pyqtSignal()

    _FIELDS = [
        ("BG_BASE","Fundo principal","Fundos"),("BG_SURFACE","Cards","Fundos"),
        ("BG_RAISED","Toolbar/Header","Fundos"),("BG_INPUT","Inputs","Fundos"),
        ("BORDER","Borda","Bordas"),("BORDER_LT","Borda clara","Bordas"),
        ("TEXT_PRI","Texto principal","Texto"),("TEXT_SEC","Texto sec.","Texto"),
        ("TEXT_DIM","Texto dim","Texto"),
        ("ACCENT","Acento","Acentos"),("ACCENT_DIM","Acento escuro","Acentos"),
        ("ACCENT2","Acento 2","Acentos"),("ACCENT3","Acento 3","Acentos"),
        ("DANGER","Perigo","Estados"),("SUCCESS","Sucesso","Estados"),("WARNING","Alerta","Estados"),
    ]
    _PRESETS = {
        "Motorsport Dark": dict(BG_BASE="#070a0d",BG_SURFACE="#0d1117",BG_RAISED="#131920",BG_INPUT="#0a0f14",BORDER="#1a2332",BORDER_LT="#243347",TEXT_PRI="#e8f1fc",TEXT_SEC="#6d8aaa",TEXT_DIM="#344d66",ACCENT="#00e5ff",ACCENT_DIM="#007799",ACCENT2="#ff6b2b",ACCENT3="#00ff94",DANGER="#ff3355",SUCCESS="#00ff94",WARNING="#ffcc00"),
        "Carbon Black":    dict(BG_BASE="#030507",BG_SURFACE="#080b0e",BG_RAISED="#0e1216",BG_INPUT="#060810",BORDER="#111820",BORDER_LT="#1a2530",TEXT_PRI="#d0dce8",TEXT_SEC="#5a7090",TEXT_DIM="#2a3d50",ACCENT="#e8ff00",ACCENT_DIM="#888800",ACCENT2="#ff4422",ACCENT3="#44ffaa",DANGER="#ff2244",SUCCESS="#44ff88",WARNING="#ffaa00"),
        "Night Blue":      dict(BG_BASE="#050812",BG_SURFACE="#0a0f1e",BG_RAISED="#10162a",BG_INPUT="#070c18",BORDER="#141e36",BORDER_LT="#1e2d4d",TEXT_PRI="#dce8ff",TEXT_SEC="#6080bb",TEXT_DIM="#2d4070",ACCENT="#4dd9ff",ACCENT_DIM="#1a6688",ACCENT2="#ff8844",ACCENT3="#44ddaa",DANGER="#ff4466",SUCCESS="#44ffcc",WARNING="#ffdd44"),
        "Branco Clínico":  dict(BG_BASE="#f4f6fa",BG_SURFACE="#ffffff",BG_RAISED="#eef0f5",BG_INPUT="#f8fafc",BORDER="#d0d8e4",BORDER_LT="#b8c4d4",TEXT_PRI="#1a2a3a",TEXT_SEC="#4a6080",TEXT_DIM="#8a9ab0",ACCENT="#005faa",ACCENT_DIM="#003d77",ACCENT2="#cc4400",ACCENT3="#006633",DANGER="#cc0022",SUCCESS="#006633",WARNING="#996600"),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Personalizar Tema")
        self.resize(700, 560)
        self.setModal(False)
        self._swatches: dict[str, QPushButton] = {}
        self._series_sw: list[QPushButton] = []
        self._build()
        self._load_saved()

    def _build(self):
        root = QVBoxLayout(self); root.setContentsMargins(16,16,16,16); root.setSpacing(10)
        self.setStyleSheet(f"QDialog{{background:{Theme.BG_BASE};}} QLabel{{color:{Theme.TEXT_SEC};background:transparent;}}")

        title = QLabel("🎨  Personalização do Tema")
        title.setStyleSheet(f"color:{Theme.TEXT_PRI};font-size:14px;font-weight:bold;background:transparent;")
        root.addWidget(title)

        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border:none;background:transparent;")
        inner = QWidget(); inner.setStyleSheet("background:transparent;")
        iv = QVBoxLayout(inner); iv.setSpacing(10)

        # Presets
        pr_grp = QFrame(); pr_grp.setStyleSheet(f"background:{Theme.BG_SURFACE};border:1px solid {Theme.BORDER};border-radius:8px;")
        pr_l   = QHBoxLayout(pr_grp); pr_l.setContentsMargins(10,8,10,8)
        pr_l.addWidget(QLabel("Presets:"))
        for name, colors in self._PRESETS.items():
            b = _mkbtn(name, 28)
            b.clicked.connect(lambda _, c=colors: self._apply_preset(c))
            pr_l.addWidget(b)
        pr_l.addStretch()
        iv.addWidget(pr_grp)

        # Cores por grupo
        groups: dict[str,list] = {}
        for attr, lbl, grp in self._FIELDS:
            groups.setdefault(grp, []).append((attr, lbl))

        for grp_name, fields in groups.items():
            grp_f = QFrame()
            grp_f.setStyleSheet(f"background:{Theme.BG_SURFACE};border:1px solid {Theme.BORDER};border-radius:8px;")
            gl = QGridLayout(grp_f); gl.setContentsMargins(10,8,10,10); gl.setSpacing(8)
            gl.addWidget(QLabel(f"<b>{grp_name}</b>"), 0, 0, 1, 8)
            for i,(attr,lbl) in enumerate(fields):
                col = (i % 4) * 2
                row = 1 + (i // 4) * 2
                sw  = QPushButton(); sw.setFixedSize(36,36)
                sw.setStyleSheet(f"background:{getattr(Theme,attr)};border:2px solid rgba(255,255,255,.15);border-radius:6px;")
                sw.setCursor(Qt.CursorShape.PointingHandCursor)
                sw.clicked.connect(partial(self._pick, attr))
                self._swatches[attr] = sw
                l = QLabel(lbl); l.setAlignment(Qt.AlignmentFlag.AlignCenter)
                l.setStyleSheet("font-size:8px;background:transparent;")
                gl.addWidget(sw, row,   col, Qt.AlignmentFlag.AlignCenter)
                gl.addWidget(l,  row+1, col, Qt.AlignmentFlag.AlignCenter)
            iv.addWidget(grp_f)

        # Séries
        ser_f = QFrame()
        ser_f.setStyleSheet(f"background:{Theme.BG_SURFACE};border:1px solid {Theme.BORDER};border-radius:8px;")
        sl = QHBoxLayout(ser_f); sl.setContentsMargins(10,8,10,8)
        sl.addWidget(QLabel("<b>Séries de Gráficos:</b>"))
        for i, color in enumerate(Theme.SERIES):
            sw = QPushButton(); sw.setFixedSize(30,30)
            sw.setStyleSheet(f"background:{color};border:1px solid rgba(255,255,255,.15);border-radius:5px;")
            sw.setCursor(Qt.CursorShape.PointingHandCursor)
            sw.clicked.connect(partial(self._pick_series, i))
            self._series_sw.append(sw); sl.addWidget(sw)
        sl.addStretch()
        iv.addWidget(ser_f)
        iv.addStretch()
        scroll.setWidget(inner); root.addWidget(scroll, 1)

        btn_row = QHBoxLayout()
        b_reset = _mkbtn("↺ Padrão"); b_reset.clicked.connect(self._reset)
        b_save  = _mkbtn("💾 Salvar"); b_save.clicked.connect(self._save)
        b_apply = _mkcta("✓ Aplicar"); b_apply.clicked.connect(self._apply)
        btn_row.addWidget(b_reset); btn_row.addStretch()
        btn_row.addWidget(b_save); btn_row.addWidget(b_apply)
        root.addLayout(btn_row)

    def _pick(self, attr):
        c = QColorDialog.getColor(QColor(getattr(Theme, attr)), self)
        if c.isValid():
            setattr(Theme, attr, c.name())
            self._swatches[attr].setStyleSheet(
                f"background:{c.name()};border:2px solid rgba(255,255,255,.15);border-radius:6px;")

    def _pick_series(self, idx):
        c = QColorDialog.getColor(QColor(Theme.SERIES[idx]), self)
        if c.isValid():
            Theme.SERIES[idx] = c.name()
            self._series_sw[idx].setStyleSheet(
                f"background:{c.name()};border:1px solid rgba(255,255,255,.15);border-radius:5px;")

    def _apply_preset(self, colors: dict):
        for attr, color in colors.items():
            setattr(Theme, attr, color)
            if attr in self._swatches:
                self._swatches[attr].setStyleSheet(
                    f"background:{color};border:2px solid rgba(255,255,255,.15);border-radius:6px;")

    def _apply(self):
        Theme.ACCENT_BG = Theme.ACCENT + "14"; Theme.ACCENT2_BG = Theme.ACCENT2 + "14"
        self.applied.emit()

    def _save(self):
        WS.save_theme({'colors': {a: getattr(Theme,a) for a,*_ in self._FIELDS},
                       'series': list(Theme.SERIES)})
        self._apply()

    def _reset(self):
        self._apply_preset(self._PRESETS["Motorsport Dark"])

    def _load_saved(self):
        d = WS.load_theme()
        if not d: return
        self._apply_preset(d.get('colors', {}))
        for i, c in enumerate(d.get('series', [])):
            if i < len(Theme.SERIES):
                Theme.SERIES[i] = c
                if i < len(self._series_sw):
                    self._series_sw[i].setStyleSheet(
                        f"background:{c};border:1px solid rgba(255,255,255,.15);border-radius:5px;")


# ═════════════════════════════════════════════════════════════════════════════
#  VIRTUAL CHANNEL EDITOR  (dialog)
# ═════════════════════════════════════════════════════════════════════════════

class _ExprHL(QSyntaxHighlighter):
    _KW = {"tempo","vel","rpm","acel","dist","rpm_raw","vel_raw","np","abs",
           "sqrt","log","exp","mean","max","min","clip","grad","cumsum","pi"}
    def highlightBlock(self, text):
        import re
        kf = QTextCharFormat(); kf.setForeground(QColor(Theme.ACCENT)); kf.setFontWeight(700)
        nf = QTextCharFormat(); nf.setForeground(QColor(Theme.ACCENT3))
        of = QTextCharFormat(); of.setForeground(QColor(Theme.WARNING))
        for m in re.finditer(r'\b(' + '|'.join(self._KW) + r')\b', text):
            self.setFormat(m.start(), m.end()-m.start(), kf)
        for m in re.finditer(r'\b\d+\.?\d*\b', text):
            self.setFormat(m.start(), m.end()-m.start(), nf)
        for m in re.finditer(r'[+\-*/^%()<>!=]', text):
            self.setFormat(m.start(), 1, of)


class VirtualChannelEditor(QDialog):
    changed = pyqtSignal()

    def __init__(self, runs=None, fs=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Editor de Canais Virtuais")
        self.resize(860, 520); self.setModal(False)
        self._runs = runs or []; self._fs = fs or {}
        self._ptimer = QTimer(self); self._ptimer.setSingleShot(True)
        self._ptimer.timeout.connect(self._preview)
        self.setStyleSheet(f"QDialog{{background:{Theme.BG_BASE};}} QLabel{{color:{Theme.TEXT_SEC};background:transparent;}}")
        self._build()
        self._refresh_list()

    def _build(self):
        root = QVBoxLayout(self); root.setContentsMargins(14,14,14,14); root.setSpacing(10)
        root.addWidget(QLabel("<b>⚙  Canais Virtuais — expressões NumPy</b>"))
        root.addWidget(QLabel("Variáveis: tempo · vel · rpm · acel · dist · rpm_raw · vel_raw · pi"))

        sp = QSplitter(Qt.Orientation.Horizontal)
        sp.setHandleWidth(5)
        sp.setStyleSheet(f"QSplitter::handle{{background:{Theme.BORDER};}} QSplitter::handle:hover{{background:{Theme.ACCENT_DIM};}}")

        # Lista
        left = QWidget(); ll = QVBoxLayout(left); ll.setContentsMargins(0,0,0,0); ll.setSpacing(6)
        self._list = QListWidget()
        self._list.setStyleSheet(f"QListWidget{{background:{Theme.BG_INPUT};border:1px solid {Theme.BORDER};border-radius:6px;}}"
                                  f"QListWidget::item{{padding:5px 8px;border-radius:4px;}}"
                                  f"QListWidget::item:hover{{background:{Theme.HOVER};color:{Theme.TEXT_PRI};}}"
                                  f"QListWidget::item:selected{{background:{Theme.ACCENT_BG};color:{Theme.ACCENT};}}")
        self._list.currentItemChanged.connect(self._on_select)
        ll.addWidget(self._list)
        br = QHBoxLayout()
        bn = _mkcta("＋ Novo"); bd = _mkbtn("✕ Excluir")
        bn.clicked.connect(self._new); bd.clicked.connect(self._delete)
        br.addWidget(bn); br.addWidget(bd); ll.addLayout(br)
        sp.addWidget(left)

        # Editor
        right = QWidget(); rl = QVBoxLayout(right); rl.setContentsMargins(0,0,0,0); rl.setSpacing(8)
        inp_css = (f"background:{Theme.BG_INPUT};border:1px solid {Theme.BORDER_LT};"
                   f"border-radius:6px;padding:5px 8px;color:{Theme.TEXT_PRI};font-size:11px;")

        self._name = QLineEdit(); self._name.setPlaceholderText("Nome do canal"); self._name.setStyleSheet(inp_css)
        self._unit = QLineEdit(); self._unit.setPlaceholderText("Unidade (ex: kW)"); self._unit.setFixedWidth(100); self._unit.setStyleSheet(inp_css)
        self._color_btn = QPushButton(); self._color_btn.setFixedSize(28,28); self._clr = Theme.ACCENT
        self._style_clr(); self._color_btn.clicked.connect(self._pick_clr)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Nome:"), 0); row1.addWidget(self._name, 1)
        row1.addWidget(QLabel("Unidade:")); row1.addWidget(self._unit)
        row1.addWidget(QLabel("Cor:")); row1.addWidget(self._color_btn)
        rl.addLayout(row1)

        rl.addWidget(QLabel("Expressão NumPy:"))
        self._expr = QTextEdit(); self._expr.setFixedHeight(80)
        self._expr.setFont(QFont("JetBrains Mono, Consolas", 11))
        self._expr.setStyleSheet(f"background:{Theme.BG_INPUT};border:1px solid {Theme.BORDER_LT};border-radius:6px;color:{Theme.TEXT_PRI};padding:6px;")
        self._expr.setPlaceholderText("ex: rpm * vel / 1000\nex: np.gradient(vel, tempo)\nex: np.clip(acel, 0, None)")
        _ExprHL(self._expr.document())
        self._expr.textChanged.connect(lambda: self._ptimer.start(600))
        rl.addWidget(self._expr)

        # Exemplos rápidos
        ex_row = QHBoxLayout(); ex_row.setSpacing(4)
        for lbl, expr in [("RPM×Vel","rpm*vel/1000"),("Acel+","np.clip(acel,0,None)"),
                          ("dVel/dt","np.gradient(vel,tempo)"),("Dist km","dist/1000"),
                          ("Slip","rpm/(vel+.01)/100")]:
            b = _mkbtn(lbl, 24)
            b.clicked.connect(lambda _, e=expr: self._expr.setPlainText(e))
            ex_row.addWidget(b)
        ex_row.addStretch()
        rl.addLayout(ex_row)

        self._prev = QLabel("—  preview —")
        self._prev.setStyleSheet(f"color:{Theme.TEXT_DIM};font-size:9px;font-family:{Theme.FONT_MONO};background:transparent;padding:3px;")
        rl.addWidget(self._prev)

        save_row = QHBoxLayout(); save_row.addStretch()
        bs = _mkcta("💾  Salvar Canal"); bs.clicked.connect(self._save_vc)
        save_row.addWidget(bs); rl.addLayout(save_row)
        rl.addStretch()
        sp.addWidget(right)
        sp.setSizes([230, 600]); root.addWidget(sp, 1)

        # Footer
        fr = QHBoxLayout(); fr.addStretch()
        bex = _mkbtn("📤 Exportar"); bim = _mkbtn("📥 Importar"); bcl = _mkbtn("Fechar")
        bex.clicked.connect(self._export); bim.clicked.connect(self._import_ws)
        bcl.clicked.connect(self.close)
        for b in (bim, bex, bcl): fr.addWidget(b)
        root.addLayout(fr)

    def _style_clr(self):
        self._color_btn.setStyleSheet(f"background:{self._clr};border:2px solid rgba(255,255,255,.2);border-radius:5px;")

    def _pick_clr(self):
        c = QColorDialog.getColor(QColor(self._clr), self)
        if c.isValid(): self._clr = c.name(); self._style_clr()

    def _refresh_list(self):
        self._list.clear()
        for vc in WS.list_virtuals():
            it = QListWidgetItem(f"  {vc.name}  [{vc.unit}]")
            it.setForeground(QColor(vc.color)); it.setData(Qt.ItemDataRole.UserRole, vc.name)
            self._list.addItem(it)

    def _on_select(self, item, _=None):
        if not item: return
        vc = next((v for v in WS.list_virtuals() if v.name == item.data(Qt.ItemDataRole.UserRole)), None)
        if not vc: return
        self._name.setText(vc.name); self._unit.setText(vc.unit)
        self._clr = vc.color; self._style_clr()
        self._expr.setPlainText(vc.expression); self._preview()

    def _new(self):
        self._name.clear(); self._unit.clear()
        self._clr = Theme.ACCENT; self._style_clr()
        self._expr.clear(); self._prev.setText("—  defina a expressão  —")

    def _save_vc(self):
        n = self._name.text().strip(); e = self._expr.toPlainText().strip()
        if not n: QMessageBox.warning(self,"Aviso","Informe um nome."); return
        if not e: QMessageBox.warning(self,"Aviso","Informe a expressão."); return
        try:
            WS.save_virtual(VirtualChannel(n, e, self._unit.text().strip(), self._clr))
        except ExpressionError as ex:
            QMessageBox.warning(self,"Expressão inválida",str(ex)); return
        self._refresh_list(); self.changed.emit()

    def _delete(self):
        it = self._list.currentItem()
        if not it: return
        n = it.data(Qt.ItemDataRole.UserRole)
        if QMessageBox.question(self,"Confirmar",f"Excluir '{n}'?",
           QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            WS.delete_virtual(n); self._refresh_list(); self.changed.emit()

    def _preview(self):
        e = self._expr.toPlainText().strip()
        if not e or not self._runs: self._prev.setText("—"); return
        vc = VirtualChannel("_p_", e)
        try: vc.validate()
        except ExpressionError as ex:
            self._prev.setText(f"✗  {ex}")
            self._prev.setStyleSheet(f"color:{Theme.DANGER};font-size:9px;font-family:{Theme.FONT_MONO};background:transparent;padding:3px;")
            return
        r = vc.evaluate(self._runs[0], self._fs)
        if r is not None and r.size > 0:
            self._prev.setText(f"✓  n={r.size}  min={r.min():.4g}  max={r.max():.4g}  mean={r.mean():.4g}")
            self._prev.setStyleSheet(f"color:{Theme.SUCCESS};font-size:9px;font-family:{Theme.FONT_MONO};background:transparent;padding:3px;")
        else:
            self._prev.setText("✗  Erro — verifique a expressão.")
            self._prev.setStyleSheet(f"color:{Theme.DANGER};font-size:9px;font-family:{Theme.FONT_MONO};background:transparent;padding:3px;")

    def _export(self):
        from PyQt6.QtWidgets import QFileDialog
        path,_ = QFileDialog.getSaveFileName(self,"Exportar","","JSON (*.json)")
        if path: WS.export_all(path); QMessageBox.information(self,"OK",f"Exportado:\n{path}")

    def _import_ws(self):
        from PyQt6.QtWidgets import QFileDialog
        path,_ = QFileDialog.getOpenFileName(self,"Importar","","JSON (*.json)")
        if path:
            try:
                nl,np_,nv = WS.import_all(path)
                self._refresh_list(); self.changed.emit()
                QMessageBox.information(self,"OK",f"{nl} layouts, {np_} presets, {nv} canais importados.")
            except Exception as ex:
                QMessageBox.critical(self,"Erro",str(ex))


# ═════════════════════════════════════════════════════════════════════════════
#  PLOT PANELS + OVERLAY
# ═════════════════════════════════════════════════════════════════════════════

class PanelHeader(QFrame):
    close_requested = pyqtSignal()
    def __init__(self, icon, title, accent="", parent=None):
        super().__init__(parent)
        self.setFixedHeight(32)
        self._drag = False; self._dp = QPoint()
        accent = accent or Theme.ACCENT_DIM
        self.setStyleSheet(f"QFrame{{background:{Theme.BG_RAISED};border-bottom:1px solid {Theme.BORDER};}}")
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        hl = QHBoxLayout(self); hl.setContentsMargins(10,0,6,0); hl.setSpacing(6)
        bar = QFrame(); bar.setFixedSize(3,18); bar.setStyleSheet(f"background:{accent};border-radius:2px;")
        hl.addWidget(bar)
        li = QLabel(icon); li.setStyleSheet("background:transparent;font-size:13px;")
        hl.addWidget(li)
        self._t = QLabel(title)
        self._t.setStyleSheet(f"background:transparent;color:{Theme.TEXT_PRI};font-size:9px;font-weight:bold;")
        hl.addWidget(self._t); hl.addStretch()
        bc = QPushButton("✕"); bc.setFixedSize(22,22)
        bc.setStyleSheet(f"QPushButton{{border:none;color:{Theme.TEXT_DIM};background:transparent;font-size:11px;border-radius:5px;}}QPushButton:hover{{color:{Theme.DANGER};background:rgba(255,51,85,.15);}}")
        bc.clicked.connect(self.close_requested); hl.addWidget(bc)
    def apply_theme(self):
        self.setStyleSheet(f"QFrame{{background:{Theme.BG_RAISED};border-bottom:1px solid {Theme.BORDER};}}")
        self._t.setStyleSheet(f"background:transparent;color:{Theme.TEXT_PRI};")
    def mousePressEvent(self,ev):
        if ev.button()==Qt.MouseButton.LeftButton: self._drag=True; self._dp=ev.globalPosition().toPoint()
    def mouseReleaseEvent(self,_): self._drag=False
    def mouseMoveEvent(self,ev):
        if self._drag:
            p=self.parent(); c=p.parent() if p else None
            if c and hasattr(c,'_reorder'): c._reorder(p,ev.globalPosition().toPoint())


class BasePanel(QWidget):
    close_requested = pyqtSignal(object)
    ICON="●"; TITLE="Painel"; ACCENT=""
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(80)
        root=QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)
        self.header=PanelHeader(self.ICON,self.TITLE,self.ACCENT)
        self.header.close_requested.connect(lambda: self.close_requested.emit(self))
        root.addWidget(self.header)
        self._content=QWidget(); self._content.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Expanding)
        root.addWidget(self._content,1)
        gr=QWidget(); gr.setFixedHeight(14); gl=QHBoxLayout(gr); gl.setContentsMargins(0,0,0,0)
        gl.addStretch(); sg=QSizeGrip(self); sg.setFixedSize(14,14); gl.addWidget(sg)
        root.addWidget(gr)
        self.setStyleSheet(f"QWidget{{background:{_surface()};}}BasePanel{{border:1px solid {_border()};border-radius:8px;}}")
    def content_layout(self):
        l=QVBoxLayout(self._content); l.setContentsMargins(4,4,4,2); return l
    def apply_theme(self):
        self.setStyleSheet(f"QWidget{{background:{_surface()};}}BasePanel{{border:1px solid {_border()};border-radius:8px;}}")
        self.header.apply_theme()


class SyncManager:
    def __init__(self): self.mode='off'; self._panels=[]; self.pos_a=0.; self.pos_b=1.
    def set_panels(self,p): self._panels=p
    def set_mode(self,m): self.mode=m; [p.apply_sync_mode(m,self.pos_a,self.pos_b) for p in self._panels]
    def move_a(self,x,src=None): self.pos_a=x; [p.set_sync_a(x) for p in self._panels if p is not src]; self._bc()
    def move_b(self,x,src=None): self.pos_b=x; [p.set_sync_b(x) for p in self._panels if p is not src]; self._bc()
    def _bc(self):
        if self.mode=='interval':
            d=abs(self.pos_b-self.pos_a)
            for p in self._panels: p.set_interval_label(self.pos_a,self.pos_b,d)
    def interval_stats(self,run,sk,xd,yd):
        if self.mode!='interval' or xd is None or yd is None: return {}
        lo,hi=min(self.pos_a,self.pos_b),max(self.pos_a,self.pos_b)
        ys=yd[(xd>=lo)&(xd<=hi)]
        return {'min':float(ys.min()),'max':float(ys.max()),'mean':float(ys.mean()),'delta':abs(hi-lo)} if ys.size else {}


class PlotPanel(BasePanel):
    cursor_moved=pyqtSignal(float); cursor_b_moved=pyqtSignal(float); ICON='📈'
    def __init__(self,sk,run,xk,color,fs,vs,sync,parent=None):
        self.TITLE=f"{sk}  ·  {run.file_name}"; self.ACCENT=color
        super().__init__(parent)
        self.signal_key=sk; self.run=run; self.x_key=xk; self.color=color
        self.filter_settings=fs; self.vs=vs; self.sync_mgr=sync
        self._ba=self._bb=False; self.xd=self.yd=np.array([])
        # swatch
        sw=QPushButton(); sw.setFixedSize(13,13); sw.setCursor(Qt.CursorShape.PointingHandCursor)
        sw.setStyleSheet(f"background:{color};border:1px solid rgba(255,255,255,.25);border-radius:3px;")
        sw.clicked.connect(lambda: self._pick_clr())
        self._sw=sw; self.header.layout().insertWidget(1,sw)
        # mini stats
        def ml(t,cs=""): l=QLabel(t); l.setStyleSheet(f"font-size:9px;font-family:{Theme.FONT_MONO};background:transparent;color:{Theme.TEXT_DIM};{cs}"); return l
        def vd(): l=QLabel("│"); l.setStyleSheet(f"color:{Theme.BORDER_LT};background:transparent;font-size:11px;"); return l
        self.lc=ml("--",f"color:{_SLA};min-width:56px;"); self.lc2=ml("--",f"color:{_SLB};min-width:56px;")
        self.ld=ml("Δ--",f"color:{Theme.TEXT_SEC};min-width:50px;"); self.lmn=ml("--"); self.lmx=ml("--"); self.lav=ml("--")
        self._irow=QWidget(); self._irow.setVisible(False)
        ir=QHBoxLayout(self._irow); ir.setContentsMargins(8,0,8,0); ir.setSpacing(4)
        for w in [ml("A:"),self.lc,ml("B:"),self.lc2,vd(),ml("Δ:"),self.ld]: ir.addWidget(w)
        ir.addStretch()
        hl=self.header.layout()
        for i in range(hl.count()-1,-1,-1):
            if hl.itemAt(i) and hl.itemAt(i).spacerItem(): hl.removeItem(hl.itemAt(i)); break
        for w in [vd(),ml("min"),self.lmn,ml("max"),self.lmx,ml("~"),self.lav]: hl.addWidget(w)
        hl.addStretch(); ci=hl.takeAt(hl.count()-1); hl.addItem(ci)
        # plot
        cl=self.content_layout(); cl.setContentsMargins(0,0,0,0); cl.setSpacing(0)
        self.pw=pg.PlotWidget(); self.pw.setBackground(_bg())
        self.pi=self.pw.getPlotItem(); _style_pi(self.pi,vs.grid_x,vs.grid_y,vs.grid_alpha,x_lbl=xk,y_lbl=sk)
        mkl=lambda c,s=Qt.PenStyle.DashLine: pg.InfiniteLine(angle=90,movable=True,
            pen=pg.mkPen(pg.mkColor(c),width=1,style=s),hoverPen=pg.mkPen(pg.mkColor(c),width=2))
        self._la=mkl(_SLA); self._lb=mkl(_SLB)
        self._la.setVisible(False); self._lb.setVisible(False)
        self._rg=pg.LinearRegionItem(values=(0,1),brush=pg.mkBrush(*_RGN),movable=False)
        self._rg.setVisible(False); self._rg.setZValue(-10)
        for item in (self._la,self._lb,self._rg): self.pi.addItem(item)
        self._la.sigPositionChanged.connect(self._on_la)
        self._lb.sigPositionChanged.connect(self._on_lb)
        cl.addWidget(self._irow); cl.addWidget(self.pw,1)
        self.refresh()

    def refresh(self):
        self.pi.clear()
        for item in (self._la,self._lb,self._rg): self.pi.addItem(item)
        self.run.apply_filters_and_recalculate(self.filter_settings)
        xd=self.run.get_channel(self.x_key); yd=self.run.get_channel(self.signal_key)
        if xd.size and yd.size:
            n=min(len(xd),len(yd)); self.xd,self.yd=xd[:n],yd[:n]
            self.pi.plot(self.xd,self.yd,pen=_pen(self.color,self.vs.line_width))
            self.lmn.setText(f"{self.yd.min():.4g}"); self.lmx.setText(f"{self.yd.max():.4g}"); self.lav.setText(f"{self.yd.mean():.4g}")
        else:
            self.xd=self.yd=np.array([])
            for l in (self.lmn,self.lmx,self.lav): l.setText("--")

    def update_filter(self,fs): self.filter_settings=fs; self.refresh()
    def update_x(self,xk): self.x_key=xk; self.refresh()
    def link_x(self,pi): self.pi.setXLink(pi)
    def unlink_x(self): self.pi.setXLink(None)
    def apply_vs(self): _style_pi(self.pi,self.vs.grid_x,self.vs.grid_y,self.vs.grid_alpha,x_lbl=self.x_key,y_lbl=self.signal_key); self.refresh() if self.xd.size else None

    def apply_sync_mode(self,m,pa,pb):
        if m=='off': self._la.setVisible(False); self._lb.setVisible(False); self._rg.setVisible(False); self._irow.setVisible(False)
        elif m=='single': self._la.setValue(pa); self._la.setVisible(True); self._lb.setVisible(False); self._rg.setVisible(False); self._irow.setVisible(False); self._sa(pa)
        elif m=='interval':
            self._la.setValue(pa); self._lb.setValue(pb)
            self._la.setVisible(True); self._lb.setVisible(True)
            lo,hi=min(pa,pb),max(pa,pb); self._rg.setRegion((lo,hi)); self._rg.setVisible(True); self._irow.setVisible(True)
            self._sa(pa); self._sb(pb)

    def set_sync_a(self,x): self._ba=True; self._la.setValue(x); self._sa(x); self._upd_rg() if self.sync_mgr.mode=='interval' else None; self._ba=False
    def set_sync_b(self,x): self._bb=True; self._lb.setValue(x); self._sb(x); self._upd_rg(); self._bb=False
    def _upd_rg(self): self._rg.setRegion((min(self._la.value(),self._lb.value()),max(self._la.value(),self._lb.value())))
    def set_interval_label(self,a,b,d): self.ld.setText(f"Δ{d:.4g}")
    def _on_la(self):
        if self._ba: return
        x=self._la.value(); self._sa(x)
        if self.sync_mgr.mode=='interval': self._upd_rg()
        self.cursor_moved.emit(x)
    def _on_lb(self):
        if self._bb: return
        x=self._lb.value(); self._sb(x); self._upd_rg(); self.cursor_b_moved.emit(x)
    def _sa(self,x):
        if self.xd.size and self.yd.size: i=int(np.clip(np.searchsorted(self.xd,x),0,len(self.yd)-1)); self.lc.setText(f"{self.yd[i]:.5g}")
        else: self.lc.setText("--")
    def _sb(self,x):
        if self.xd.size and self.yd.size: i=int(np.clip(np.searchsorted(self.xd,x),0,len(self.yd)-1)); self.lc2.setText(f"{self.yd[i]:.5g}")
        else: self.lc2.setText("--")
    def _pick_clr(self):
        c=QColorDialog.getColor(QColor(self.color),self)
        if c.isValid():
            self.color=c.name(); self._sw.setStyleSheet(f"background:{self.color};border:1px solid rgba(255,255,255,.25);border-radius:3px;"); self.refresh()


class MultiAxisOverlay(QWidget):
    cursor_moved=pyqtSignal(float)
    def __init__(self,vs,parent=None):
        super().__init__(parent); self.vs=vs; self._sigs=[]; self._block=False
        vl=QVBoxLayout(self); vl.setContentsMargins(0,0,0,0); vl.setSpacing(0)
        self._cbar=QFrame(); self._cbar.setFixedHeight(28)
        self._cbar.setStyleSheet(f"background:{Theme.BG_RAISED};border-bottom:1px solid {Theme.BORDER};")
        self._cbl=QHBoxLayout(self._cbar); self._cbl.setContentsMargins(10,0,10,0); self._cbl.setSpacing(14)
        self._clbls: dict={}; self._cbl.addStretch()
        vl.addWidget(self._cbar)
        self.pw=pg.PlotWidget(); self.pw.setBackground(_bg())
        self.pi=self.pw.getPlotItem(); self.pi.hideAxis('left')
        self.pi.getAxis('bottom').setPen(_fg()); self.pi.getAxis('bottom').setTextPen(_fg())
        self.pi.showGrid(x=vs.grid_x,y=False,alpha=vs.grid_alpha)
        self.pi.setDownsampling(mode='peak'); self.pi.setClipToView(True)
        self.cl=pg.InfiniteLine(angle=90,movable=True,
            pen=pg.mkPen(pg.mkColor(_SLA),width=1,style=Qt.PenStyle.DashLine),
            hoverPen=pg.mkPen(pg.mkColor(_SLA),width=2))
        self.pi.addItem(self.cl); self.cl.sigPositionChanged.connect(self._on_cur)
        vl.addWidget(self.pw,1)

    def add_signal(self,sk,run,x,y,color):
        key=(sk,id(run))
        if any(s['kt']==key for s in self._sigs): return
        n=len(self._sigs); vb=pg.ViewBox()
        self.pi.scene().addItem(vb); vb.setXLink(self.pi); vb.setBackgroundColor(pg.mkColor(0,0,0,0))
        side='left' if n%2==0 else 'right'
        ax=pg.AxisItem(orientation=side)
        ax.setPen(pg.mkPen(color,width=1)); ax.setTextPen(pg.mkPen(color))
        unit=CHANNEL_UNITS.get(sk,'')
        ax.setLabel(f"{_SHORT.get(sk,sk[:6])} [{unit}]" if unit else _SHORT.get(sk,sk[:6]),**{'font-size':'8pt','color':color})
        self.pi.layout.addItem(ax,2,0 if side=='left' else 4); ax.linkToView(vb)
        curve=pg.PlotDataItem(x,y,pen=_pen(color,self.vs.line_width),name=f"{sk}·{run.file_name}")
        vb.addItem(curve); self.pi.vb.sigResized.connect(self._sync_geom); self._sync_geom()
        cl=QLabel(f"{_SHORT.get(sk,sk[:5])}: --")
        cl.setStyleSheet(f"color:{color};font-size:9px;font-family:{Theme.FONT_MONO};background:transparent;padding:0 4px;border-left:2px solid {color};")
        self._cbl.insertWidget(self._cbl.count()-1,cl); self._clbls[key]=cl
        self._sigs.append({'kt':key,'key':sk,'run':run,'color':color,'vb':vb,'ax':ax,'curve':curve,'x':x,'y':y,'side':side})

    def remove_signal(self,sk,run):
        key=(sk,id(run)); sig=next((s for s in self._sigs if s['kt']==key),None)
        if not sig: return
        sig['vb'].removeItem(sig['curve']); self.pi.scene().removeItem(sig['vb'])
        self.pi.layout.removeItem(sig['ax']); sig['ax'].deleteLater()
        if key in self._clbls: self._clbls[key].deleteLater(); del self._clbls[key]
        self._sigs=[s for s in self._sigs if s['kt']!=key]; self._sync_geom()

    def clear(self):
        for s in list(self._sigs): self.remove_signal(s['key'],s['run'])

    def set_x_label(self,lbl): self.pi.setLabel('bottom',lbl,**{'font-size':'8pt','color':_fg()})
    def fit(self): self.pi.autoRange(); [s['vb'].autoRange() for s in self._sigs]
    def apply_vs(self): self.pi.showGrid(x=self.vs.grid_x,y=False,alpha=self.vs.grid_alpha); [s['curve'].setPen(_pen(s['color'],self.vs.line_width)) for s in self._sigs]
    def apply_theme(self): self.pw.setBackground(_bg()); self.pi.getAxis('bottom').setPen(_fg()); self.pi.getAxis('bottom').setTextPen(_fg())
    def _sync_geom(self): g=self.pi.vb.sceneBoundingRect(); [s['vb'].setGeometry(g) for s in self._sigs]
    def _on_cur(self):
        if self._block: return
        x=self.cl.value()
        for s in self._sigs:
            xd,yd,key=s['x'],s['y'],s['kt']
            if xd.size and yd.size and key in self._clbls:
                i=int(np.clip(np.searchsorted(xd,x),0,len(yd)-1))
                self._clbls[key].setText(f"{_SHORT.get(s['key'],s['key'][:5])}: {yd[i]:.4g}")
        self.cursor_moved.emit(x)


class StatsPanel(BasePanel):
    ICON='📊'; TITLE='Estatísticas'; ACCENT='#7b2ff7'
    def __init__(self,parent=None):
        super().__init__(parent); cl=self.content_layout()
        # Toggle botão modo estendido
        self._extended = False
        tbar = QHBoxLayout(); tbar.setContentsMargins(0,0,0,3)
        self._btn_ext = _mkbtn("📐 Estendido", 24)
        self._btn_ext.setCheckable(True)
        self._btn_ext.toggled.connect(self._on_ext_toggle)
        tbar.addWidget(self._btn_ext); tbar.addStretch()
        cl.addLayout(tbar)
        self._build_table()
        cl.addWidget(self.tbl)

    def _build_table(self):
        if self._extended:
            cols = ["Sinal","Run","Min","Max","Média","σ","P25","P50","P75","RMS","Skew","Cur A","Cur B","Δ",""]
        else:
            cols = ["Sinal","Run","Min","Max","Média","σ","Cur A","Cur B","Δ",""]
        self.tbl = QTableWidget(); self.tbl.setColumnCount(len(cols))
        self.tbl.setHorizontalHeaderLabels(cols)
        hh = self.tbl.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(len(cols)-1, QHeaderView.ResizeMode.Fixed)
        self.tbl.setColumnWidth(len(cols)-1, 26)
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tbl.setAlternatingRowColors(True)
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

    def _on_ext_toggle(self, checked):
        self._extended = checked
        parent_layout = self.tbl.parent().layout() if self.tbl.parent() else None
        self.tbl.deleteLater(); self._build_table()
        if parent_layout: parent_layout.addWidget(self.tbl)
        self._last_refresh_args and self.refresh(*self._last_refresh_args)
    _last_refresh_args = None

    def refresh(self,panels,fs,sync):
        self._last_refresh_args = (panels, fs, sync)
        self.tbl.setRowCount(len(panels))
        from scipy.stats import skew as _skew
        for i,p in enumerate(panels):
            sk,run,color=p.signal_key,p.run,p.color
            run.apply_filters_and_recalculate(fs); yd=run.get_channel(sk)
            mn=mx=av=sd=p25=p50=p75=rms=skw="--"
            if yd.size:
                mn=f"{yd.min():.4g}"; mx=f"{yd.max():.4g}"
                av=f"{yd.mean():.4g}"; sd=f"{yd.std():.4g}"
                if self._extended:
                    pcts = [float(v) for v in [25,50,75]]
                    p25,p50,p75 = [f"{v:.4g}" for v in [float(import_np_percentile(yd, pct)) for pct in [25,50,75]]]
                    rms = f"{float(np.sqrt(np.mean(yd**2))):.4g}"
                    try:  skw = f"{float(_skew(yd)):.3f}"
                    except Exception: skw="--"
            ca=p.lc.text(); cb=p.lc2.text() if sync.mode=='interval' else "--"
            ds="--"
            if sync.mode=='interval' and p.xd.size and yd.size:
                st=sync.interval_stats(run,sk,p.xd,yd); ds=f"Δx={st['delta']:.4g}" if st else "--"
            if self._extended:
                vals = [sk,run.file_name,mn,mx,av,sd,p25,p50,p75,rms,skw,ca,cb,ds]
            else:
                vals = [sk,run.file_name,mn,mx,av,sd,ca,cb,ds]
            for j,v in enumerate(vals):
                it=QTableWidgetItem(str(v))
                if j==0: it.setForeground(QColor(color))
                self.tbl.setItem(i,j,it)
            b=QPushButton("✕"); b.setFixedSize(18,18)
            b.setStyleSheet(f"QPushButton{{border:none;font-size:9px;color:{Theme.TEXT_DIM};background:transparent;}}QPushButton:hover{{color:{Theme.DANGER};}}")
            b.clicked.connect(lambda _,panel=p: panel.close_requested.emit(panel))
            self.tbl.setCellWidget(i, len(vals), b)

    def update_cursors(self,panels,sync):
        col_a = 11 if self._extended else 6
        col_b = 12 if self._extended else 7
        for i,p in enumerate(panels):
            if i>=self.tbl.rowCount(): break
            if it:=self.tbl.item(i,col_a): it.setText(p.lc.text())
            if sync.mode=='interval':
                if it:=self.tbl.item(i,col_b): it.setText(p.lc2.text())

def import_np_percentile(arr, q): return np.percentile(arr, q)


class ComparePanel(BasePanel):
    ICON='⚖'; TITLE='Comparação'; ACCENT='#c2185b'
    def __init__(self,parent=None):
        super().__init__(parent); cl=self.content_layout()
        self.gl=pg.GraphicsLayoutWidget(); self.gl.setBackground(_bg()); cl.addWidget(self.gl)
    def refresh(self,runs,fs):
        self.gl.clear()
        if not runs: return
        for r in runs: r.apply_filters_and_recalculate(fs)
        keys=[('Vel. Máx (Km/h)','Vel Max'),('RPM Máx','RPM Max'),
              ('Acel. Máx (m/s²)','Acel Max'),('Distância Total (m)','Dist Total')]
        names=[r.file_name for r in runs]; n=len(names)
        for i,(mk,lbl) in enumerate(keys):
            p=self.gl.addPlot(row=i//2,col=i%2); p.setTitle(lbl,size='9pt',color=Theme.TEXT_SEC); p.getViewBox().setBackgroundColor(_bg())
            for ax in ('bottom','left'): p.getAxis(ax).setPen(_fg()); p.getAxis(ax).setTextPen(_fg())
            p.getAxis('bottom').setTicks([list(enumerate(names))])
            vals=[r.stats.get(mk,0) for r in runs]
            p.addItem(pg.BarGraphItem(x=range(n),height=vals,width=.6,brushes=[pg.mkBrush(c) for c in Theme.SERIES[:n]]))
            if vals: p.setYRange(0,max(vals)*1.18 or 1)
    def apply_theme(self): super().apply_theme(); self.gl.setBackground(_bg())


class IntelligencePanel(BasePanel):
    ICON='🧠'; TITLE='Inteligência de Telemetria'; ACCENT='#ff6b2b'
    def __init__(self,parent=None):
        super().__init__(parent); cl=self.content_layout()
        sc=QScrollArea(); sc.setWidgetResizable(True); sc.setStyleSheet("border:none;background:transparent;")
        self._inner=QWidget(); self._inner.setStyleSheet("background:transparent;")
        self._il=QVBoxLayout(self._inner); self._il.setContentsMargins(6,6,6,6); self._il.setSpacing(4); self._il.addStretch()
        sc.setWidget(self._inner); cl.addWidget(sc)
        self._ft=QLabel("—"); self._ft.setStyleSheet(f"color:{Theme.TEXT_DIM};font-size:9px;padding:4px 8px;background:transparent;"); cl.addWidget(self._ft)

    def refresh(self,result):
        while self._il.count()>1:
            it=self._il.takeAt(0)
            if it.widget(): it.widget().deleteLater()
        ins=result.get('insights',[]); corrs=result.get('correlations',{})
        lo={'critical':0,'warning':1,'good':2,'info':3}
        for ins_ in sorted(ins,key=lambda i: lo.get(i.level,9)):
            c=LEVEL_COLOR.get(ins_.level,Theme.ACCENT); ico=LEVEL_ICON.get(ins_.level,'ℹ')
            card=QFrame()
            card.setStyleSheet(f"QFrame{{background:{Theme.BG_SURFACE};border-left:3px solid {c};border-radius:5px;margin:2px 0;}}")
            vl=QVBoxLayout(card); vl.setContentsMargins(10,6,10,6); vl.setSpacing(3)
            hr=QHBoxLayout(); hr.addWidget(QLabel(ico))
            t=QLabel(ins_.title); t.setStyleSheet(f"color:{c};font-weight:bold;font-size:10px;background:transparent;"); hr.addWidget(t); hr.addStretch()
            if ins_.value is not None:
                u=CHANNEL_UNITS.get(ins_.metric,'')
                vl2=QLabel(f"{ins_.value:.2g} {u}"); vl2.setStyleSheet(f"color:{c};font-size:9px;font-family:{Theme.FONT_MONO};background:transparent;"); hr.addWidget(vl2)
            vl.addLayout(hr)
            b=QLabel(ins_.body); b.setWordWrap(True); b.setStyleSheet(f"color:{Theme.TEXT_SEC};font-size:9px;background:transparent;"); vl.addWidget(b)
            self._il.insertWidget(self._il.count()-1,card)
        if corrs:
            sep=QLabel("── CORRELAÇÕES ──"); sep.setStyleSheet(f"color:{Theme.ACCENT_DIM};font-size:8px;font-weight:bold;letter-spacing:2px;padding:6px 0 2px 4px;background:transparent;"); self._il.insertWidget(self._il.count()-1,sep)
            for rn,cs in corrs.items():
                for c in cs:
                    color=Theme.SUCCESS if abs(c.r)>.65 else Theme.TEXT_SEC
                    l=QLabel(f"  {c.label} — r={c.r:.3f} ({c.strength})" + (" *" if c.p<.05 else " (n.s.)"))
                    l.setStyleSheet(f"color:{color};font-size:9px;font-family:{Theme.FONT_MONO};background:transparent;"); self._il.insertWidget(self._il.count()-1,l)
        nw=sum(1 for i in ins if i.level in('warning','critical')); ng=sum(1 for i in ins if i.level=='good')
        self._ft.setText(f"{len(ins)} insights  ·  {nw} alertas  ·  {ng} positivos")


# ═════════════════════════════════════════════════════════════════════════════
#  HISTOGRAM PANEL
# ═════════════════════════════════════════════════════════════════════════════

class HistogramPanel(BasePanel):
    ICON='📶'; TITLE='Histograma'; ACCENT='#aa44ff'
    def __init__(self, runs, fs, parent=None):
        super().__init__(parent)
        self._runs = runs; self._fs = fs
        cl = self.content_layout(); cl.setSpacing(4)

        ctrl = QHBoxLayout()
        self._chan_cb = QComboBox(); self._chan_cb.setFixedHeight(26)
        from ...domain.channels import KEY_VEL_KMH_FILT, KEY_RPM_FILT, KEY_ACEL_MS2_FILT, KEY_DIST_M
        for k in [KEY_VEL_KMH_FILT, KEY_RPM_FILT, KEY_ACEL_MS2_FILT, KEY_DIST_M]:
            self._chan_cb.addItem(k)
        self._bins_sb = QSpinBox(); self._bins_sb.setRange(10, 200); self._bins_sb.setValue(50)
        self._bins_sb.setFixedHeight(26); self._bins_sb.setFixedWidth(70)
        self._norm_cb = QCheckBox("Normalizar")
        self._norm_cb.setStyleSheet(f"color:{Theme.TEXT_SEC};font-size:10px;")
        ctrl.addWidget(QLabel("Canal:")); ctrl.addWidget(self._chan_cb, 1)
        ctrl.addWidget(QLabel("Bins:")); ctrl.addWidget(self._bins_sb)
        ctrl.addWidget(self._norm_cb); ctrl.addStretch()
        cl.addLayout(ctrl)

        self.pw = pg.PlotWidget(); self.pw.setBackground(_bg())
        self.pi = self.pw.getPlotItem()
        _style_pi(self.pi, False, True, 0.10, x_lbl='Valor', y_lbl='Frequência')
        cl.addWidget(self.pw, 1)

        self._chan_cb.currentIndexChanged.connect(self.refresh)
        self._bins_sb.valueChanged.connect(self.refresh)
        self._norm_cb.toggled.connect(self.refresh)
        self.refresh()

    def refresh(self):
        self.pi.clear()
        key  = self._chan_cb.currentText()
        bins = self._bins_sb.value()
        norm = self._norm_cb.isChecked()
        legend = self.pi.addLegend(offset=(10, 10))
        legend.setBrush(pg.mkBrush(Theme.BG_RAISED + 'cc'))
        legend.setPen(pg.mkPen(Theme.BORDER_LT))
        for i, r in enumerate(self._runs):
            r.apply_filters_and_recalculate(self._fs)
            ctrs, cnts = r.compute_histogram_data(key, bins)
            if ctrs.size == 0: continue
            color = Theme.SERIES[i % len(Theme.SERIES)]
            if norm and cnts.sum() > 0:
                cnts = cnts / cnts.sum()
            bw = float(ctrs[1] - ctrs[0]) if len(ctrs) > 1 else 1.0
            item = pg.BarGraphItem(x=ctrs, height=cnts, width=bw * 0.8,
                                   brush=pg.mkBrush(pg.mkColor(color + '88')),
                                   pen=pg.mkPen(color, width=1))
            self.pi.addItem(item)
            legend.addItem(pg.PlotDataItem(pen=_pen(color)), r.file_name[:20])
        unit = CHANNEL_UNITS.get(key, '')
        self.pi.setLabel('bottom', f'{key} [{unit}]' if unit else key,
                         **{'font-size': '8pt', 'color': _fg()})
        self.pi.setLabel('left', 'Frequência relativa' if norm else 'Contagem',
                         **{'font-size': '8pt', 'color': _fg()})

    def update_filter(self, fs): self._fs = fs; self.refresh()
    def apply_theme(self): super().apply_theme(); self.pw.setBackground(_bg())


# ═════════════════════════════════════════════════════════════════════════════
#  FREQUENCY (FFT) PANEL
# ═════════════════════════════════════════════════════════════════════════════

class FrequencyPanel(BasePanel):
    ICON='〰'; TITLE='Espectro de Frequência (FFT)'; ACCENT='#00e5ff'
    def __init__(self, runs, fs, parent=None):
        super().__init__(parent)
        self._runs = runs; self._fs = fs
        cl = self.content_layout(); cl.setSpacing(4)

        ctrl = QHBoxLayout()
        self._chan_cb = QComboBox(); self._chan_cb.setFixedHeight(26)
        from ...domain.channels import KEY_VEL_KMH_FILT, KEY_RPM_FILT, KEY_ACEL_MS2_FILT
        for k in [KEY_VEL_KMH_FILT, KEY_RPM_FILT, KEY_ACEL_MS2_FILT]:
            self._chan_cb.addItem(k)
        self._log_cb = QCheckBox("Log Y")
        self._log_cb.setStyleSheet(f"color:{Theme.TEXT_SEC};font-size:10px;")
        ctrl.addWidget(QLabel("Canal:")); ctrl.addWidget(self._chan_cb, 1)
        ctrl.addWidget(self._log_cb); ctrl.addStretch()
        cl.addLayout(ctrl)

        self.pw = pg.PlotWidget(); self.pw.setBackground(_bg())
        self.pi = self.pw.getPlotItem()
        _style_pi(self.pi, True, True, 0.10, x_lbl='Frequência (Hz)', y_lbl='Magnitude')
        cl.addWidget(self.pw, 1)

        self._dominant_lbl = QLabel("—")
        self._dominant_lbl.setStyleSheet(
            f"color:{Theme.ACCENT};font-size:9px;font-family:{Theme.FONT_MONO};"
            f"background:transparent;padding:3px;")
        cl.addWidget(self._dominant_lbl)

        self._chan_cb.currentIndexChanged.connect(self.refresh)
        self._log_cb.toggled.connect(self.refresh)
        self.refresh()

    def refresh(self):
        self.pi.clear()
        key = self._chan_cb.currentText()
        dom_info = []
        for i, r in enumerate(self._runs):
            r.apply_filters_and_recalculate(self._fs)
            freqs, mag = r.compute_fft(key)
            if freqs.size == 0: continue
            color = Theme.SERIES[i % len(Theme.SERIES)]
            y = np.log10(mag + 1e-12) if self._log_cb.isChecked() else mag
            # Only show up to 20 Hz (relevant range for vehicle dynamics)
            mask = freqs <= 20.0
            self.pi.plot(freqs[mask], y[mask], pen=_pen(color, 2),
                         name=r.file_name[:20])
            if mag.size and freqs.size:
                dom_idx = int(np.argmax(mag[freqs > 0.05]))
                dom_f   = freqs[freqs > 0.05][dom_idx]
                dom_info.append(f"{r.file_name[:14]}: {dom_f:.2f} Hz")
        self.pi.setLabel('bottom', 'Frequência (Hz)', **{'font-size':'8pt','color':_fg()})
        self.pi.setLabel('left', 'Magnitude (log)' if self._log_cb.isChecked() else 'Magnitude',
                         **{'font-size':'8pt','color':_fg()})
        self._dominant_lbl.setText("Freq. dominante — " + "  |  ".join(dom_info) if dom_info else "—")

    def update_filter(self, fs): self._fs = fs; self.refresh()
    def apply_theme(self): super().apply_theme(); self.pw.setBackground(_bg())


# ═════════════════════════════════════════════════════════════════════════════
#  SCATTER PANEL
# ═════════════════════════════════════════════════════════════════════════════

class ScatterPanel(BasePanel):
    ICON='✦'; TITLE='Dispersão (X × Y)'; ACCENT='#ff6b2b'
    def __init__(self, runs, fs, parent=None):
        super().__init__(parent)
        self._runs = runs; self._fs = fs
        cl = self.content_layout(); cl.setSpacing(4)

        ctrl = QHBoxLayout()
        self._x_cb = QComboBox(); self._x_cb.setFixedHeight(26)
        self._y_cb = QComboBox(); self._y_cb.setFixedHeight(26)
        from ...domain.channels import KEY_VEL_KMH_FILT, KEY_RPM_FILT, KEY_ACEL_MS2_FILT, KEY_DIST_M, KEY_TEMPO_S
        all_keys = [KEY_VEL_KMH_FILT, KEY_RPM_FILT, KEY_ACEL_MS2_FILT, KEY_DIST_M, KEY_TEMPO_S]
        for k in all_keys:
            self._x_cb.addItem(k); self._y_cb.addItem(k)
        self._x_cb.setCurrentText(KEY_VEL_KMH_FILT)
        self._y_cb.setCurrentText(KEY_RPM_FILT)
        self._size_sl = QSlider(Qt.Orientation.Horizontal)
        self._size_sl.setRange(1, 8); self._size_sl.setValue(3); self._size_sl.setFixedWidth(70)
        ctrl.addWidget(QLabel("X:")); ctrl.addWidget(self._x_cb, 1)
        ctrl.addWidget(QLabel("Y:")); ctrl.addWidget(self._y_cb, 1)
        ctrl.addWidget(QLabel("Pt:")); ctrl.addWidget(self._size_sl)
        cl.addLayout(ctrl)

        self.pw = pg.PlotWidget(); self.pw.setBackground(_bg())
        self.pi = self.pw.getPlotItem()
        _style_pi(self.pi, True, True, 0.10)
        cl.addWidget(self.pw, 1)

        self._corr_lbl = QLabel("—")
        self._corr_lbl.setStyleSheet(
            f"color:{Theme.ACCENT};font-size:9px;font-family:{Theme.FONT_MONO};"
            f"background:transparent;padding:3px;")
        cl.addWidget(self._corr_lbl)

        self._x_cb.currentIndexChanged.connect(self.refresh)
        self._y_cb.currentIndexChanged.connect(self.refresh)
        self._size_sl.valueChanged.connect(self.refresh)
        self.refresh()

    def refresh(self):
        self.pi.clear()
        kx = self._x_cb.currentText(); ky = self._y_cb.currentText()
        sz = self._size_sl.value()
        corr_info = []
        from scipy.stats import pearsonr
        for i, r in enumerate(self._runs):
            r.apply_filters_and_recalculate(self._fs)
            xd = r.get_channel(kx); yd = r.get_channel(ky)
            if xd.size == 0 or yd.size == 0: continue
            n = min(len(xd), len(yd))
            color = Theme.SERIES[i % len(Theme.SERIES)]
            scatter = pg.ScatterPlotItem(x=xd[:n], y=yd[:n],
                                          size=sz, pen=None,
                                          brush=pg.mkBrush(pg.mkColor(color + '77')))
            self.pi.addItem(scatter)
            # Regression line
            if n > 10:
                z = np.polyfit(xd[:n], yd[:n], 1)
                xl = np.linspace(xd[:n].min(), xd[:n].max(), 100)
                self.pi.plot(xl, np.polyval(z, xl),
                             pen=pg.mkPen(color, width=1,
                                          style=Qt.PenStyle.DashLine))
            try:
                rval, pval = pearsonr(xd[:n], yd[:n])
                sig = '*' if pval < 0.05 else '(n.s.)'
                corr_info.append(f"{r.file_name[:12]}: r={rval:.3f} {sig}")
            except Exception: pass
        ux = CHANNEL_UNITS.get(kx,''); uy = CHANNEL_UNITS.get(ky,'')
        self.pi.setLabel('bottom', f'{kx} [{ux}]' if ux else kx, **{'font-size':'8pt','color':_fg()})
        self.pi.setLabel('left',   f'{ky} [{uy}]' if uy else ky, **{'font-size':'8pt','color':_fg()})
        self._corr_lbl.setText("Correlação Pearson — " + "  |  ".join(corr_info) if corr_info else "—")

    def update_filter(self, fs): self._fs = fs; self.refresh()
    def apply_theme(self): super().apply_theme(); self.pw.setBackground(_bg())


# ═════════════════════════════════════════════════════════════════════════════
#  PHASE PANEL  — visualização de fases de condução
# ═════════════════════════════════════════════════════════════════════════════

class PhasePanel(BasePanel):
    ICON='🎯'; TITLE='Fases de Condução'; ACCENT='#00ff94'
    def __init__(self, runs, fs, parent=None):
        super().__init__(parent)
        self._runs = runs; self._fs = fs
        cl = self.content_layout(); cl.setSpacing(4)

        ctrl = QHBoxLayout()
        self._run_cb = QComboBox(); self._run_cb.setFixedHeight(26)
        for r in runs: self._run_cb.addItem(r.file_name)
        ctrl.addWidget(QLabel("Run:")); ctrl.addWidget(self._run_cb, 1)
        bshow = _mkbtn("📋 Detalhes", 26)
        bshow.clicked.connect(self._show_details)
        ctrl.addWidget(bshow); ctrl.addStretch()
        cl.addLayout(ctrl)

        self.gl = pg.GraphicsLayoutWidget(); self.gl.setBackground(_bg())
        cl.addWidget(self.gl, 1)

        self._sum_lbl = QLabel("—")
        self._sum_lbl.setWordWrap(True)
        self._sum_lbl.setStyleSheet(
            f"color:{Theme.TEXT_SEC};font-size:9px;font-family:{Theme.FONT_MONO};"
            f"background:transparent;padding:4px;")
        cl.addWidget(self._sum_lbl)

        self._run_cb.currentIndexChanged.connect(self.refresh)
        self.refresh()

    def refresh(self):
        self.gl.clear()
        idx = self._run_cb.currentIndex()
        if idx < 0 or idx >= len(self._runs): return
        r = self._runs[idx]
        r.apply_filters_and_recalculate(self._fs)

        from ..theme import Theme as T
        PCOL = T.PHASE_COLORS

        t = r.time_s; vel = r.velocity_filtered_kmh; acel = r.acceleration_filtered_ms2
        if t.size == 0: return

        # Plot velocity + colored phase regions
        p1 = self.gl.addPlot(row=0, col=0)
        p1.setTitle('Velocidade com Fases', size='9pt', color=Theme.TEXT_SEC)
        p1.getViewBox().setBackgroundColor(_bg())
        for ax in ('bottom','left'): p1.getAxis(ax).setPen(_fg()); p1.getAxis(ax).setTextPen(_fg())
        p1.setLabel('left', 'Vel (km/h)', **{'font-size':'8pt','color':_fg()})
        p1.setLabel('bottom', 'Tempo (s)', **{'font-size':'8pt','color':_fg()})
        p1.plot(t, vel, pen=_pen(Theme.ACCENT, 2))

        # Overlay phase regions
        df_ph = r.detect_phases()
        if not df_ph.empty:
            for _, row in df_ph.iterrows():
                c = PCOL.get(row['Fase'], '#888888')
                rgb = QColor(c)
                region = pg.LinearRegionItem(
                    values=(row['Início (s)'], row['Fim (s)']),
                    brush=pg.mkBrush(rgb.red(), rgb.green(), rgb.blue(), 25),
                    movable=False)
                region.setZValue(-10); p1.addItem(region)

        # Plot acceleration
        p2 = self.gl.addPlot(row=1, col=0)
        p2.setTitle('Aceleração', size='9pt', color=Theme.TEXT_SEC)
        p2.getViewBox().setBackgroundColor(_bg())
        for ax in ('bottom','left'): p2.getAxis(ax).setPen(_fg()); p2.getAxis(ax).setTextPen(_fg())
        p2.setLabel('left', 'Acel (m/s²)', **{'font-size':'8pt','color':_fg()})
        p2.plot(t, acel, pen=_pen(Theme.ACCENT2, 2))
        p2.addItem(pg.InfiniteLine(angle=0, pos=0, pen=pg.mkPen(_fg(), width=1,
                                    style=Qt.PenStyle.DashLine)))
        p2.setXLink(p1)

        # Phase summary bar chart
        summary = r.phase_summary()
        if summary:
            p3 = self.gl.addPlot(row=0, col=1, rowspan=2)
            p3.setTitle('Distribuição (%)', size='9pt', color=Theme.TEXT_SEC)
            p3.getViewBox().setBackgroundColor(_bg())
            for ax in ('bottom','left'): p3.getAxis(ax).setPen(_fg()); p3.getAxis(ax).setTextPen(_fg())
            phases = list(summary.keys()); pcts = [summary[p]['percent_%'] for p in phases]
            colors = [PCOL.get(p, '#888888') for p in phases]
            p3.addItem(pg.BarGraphItem(
                x=range(len(phases)), height=pcts, width=0.6,
                brushes=[pg.mkBrush(c) for c in colors]))
            p3.getAxis('bottom').setTicks([list(enumerate([p[:5] for p in phases]))])
            p3.setYRange(0, 105)
            lines = []
            for ph, summ in summary.items():
                c = PCOL.get(ph, '#888888')
                lines.append(f"<font color='{c}'>{ph[:4]}: {summ['percent_%']:.0f}% "
                             f"({summ['duración_s'] if 'duración_s' in summ else summ.get('duração_s',0):.0f}s, "
                             f"{summ['n_eventos']} ev.)</font>")
            self._sum_lbl.setText("  |  ".join(lines))

        self.gl.ci.layout.setColumnStretchFactor(0, 3)
        self.gl.ci.layout.setColumnStretchFactor(1, 1)

    def _show_details(self):
        idx = self._run_cb.currentIndex()
        if idx < 0 or idx >= len(self._runs): return
        r = self._runs[idx]; r.apply_filters_and_recalculate(self._fs)
        df = r.detect_phases()
        if df.empty:
            QMessageBox.information(self, "Fases", "Nenhuma fase detectada."); return
        dlg = QDialog(self); dlg.setWindowTitle(f"Fases — {r.file_name}")
        dlg.resize(900, 500)
        dlg.setStyleSheet(f"QDialog{{background:{Theme.BG_BASE};}}")
        vl = QVBoxLayout(dlg)
        tbl = QTableWidget(); tbl.setColumnCount(len(df.columns))
        tbl.setHorizontalHeaderLabels(list(df.columns))
        tbl.setRowCount(len(df))
        tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        from ..theme import Theme as T
        for i, (_, row) in enumerate(df.iterrows()):
            c = T.PHASE_COLORS.get(str(row.iloc[0]), '#888888')
            for j, v in enumerate(row.values):
                it = QTableWidgetItem(str(round(v, 3) if isinstance(v, float) else v))
                if j == 0: it.setForeground(QColor(c))
                tbl.setItem(i, j, it)
        vl.addWidget(tbl)
        dlg.exec()

    def update_filter(self, fs): self._fs = fs; self.refresh()
    def apply_theme(self): super().apply_theme(); self.gl.setBackground(_bg())


# ═════════════════════════════════════════════════════════════════════════════
#  GEAR ANALYSIS PANEL
# ═════════════════════════════════════════════════════════════════════════════

class GearPanel(BasePanel):
    ICON='⚙'; TITLE='Análise de Marchas (RPM × Vel)'; ACCENT='#ffcc00'
    def __init__(self, runs, fs, parent=None):
        super().__init__(parent)
        self._runs = runs; self._fs = fs
        cl = self.content_layout(); cl.setSpacing(4)

        ctrl = QHBoxLayout()
        self._run_cb = QComboBox(); self._run_cb.setFixedHeight(26)
        for r in runs: self._run_cb.addItem(r.file_name)
        self._n_gears = QSpinBox(); self._n_gears.setRange(1, 8)
        self._n_gears.setValue(5); self._n_gears.setFixedWidth(55); self._n_gears.setFixedHeight(26)
        ctrl.addWidget(QLabel("Run:")); ctrl.addWidget(self._run_cb, 1)
        ctrl.addWidget(QLabel("Marchas:")); ctrl.addWidget(self._n_gears)
        cl.addLayout(ctrl)

        self.pw = pg.PlotWidget(); self.pw.setBackground(_bg())
        self.pi = self.pw.getPlotItem()
        _style_pi(self.pi, True, True, 0.10, x_lbl='Velocidade (km/h)', y_lbl='RPM')
        cl.addWidget(self.pw, 1)

        self._gear_lbl = QLabel("—")
        self._gear_lbl.setWordWrap(True)
        self._gear_lbl.setStyleSheet(
            f"color:{Theme.TEXT_SEC};font-size:9px;font-family:{Theme.FONT_MONO};"
            f"background:transparent;padding:3px;")
        cl.addWidget(self._gear_lbl)

        self._run_cb.currentIndexChanged.connect(self.refresh)
        self._n_gears.valueChanged.connect(self.refresh)
        self.refresh()

    def refresh(self):
        self.pi.clear()
        idx = self._run_cb.currentIndex()
        if idx < 0 or idx >= len(self._runs): return
        r = self._runs[idx]; r.apply_filters_and_recalculate(self._fs)

        vel = r.velocity_filtered_kmh; rpm = r.rpm_filtered
        if vel.size == 0: return
        n = min(len(vel), len(rpm))

        # Background scatter (all points)
        scatter = pg.ScatterPlotItem(x=vel[:n], y=rpm[:n], size=2, pen=None,
                                      brush=pg.mkBrush(Theme.ACCENT + '33'))
        self.pi.addItem(scatter)

        # Overlay gear ratio lines
        gears = r.estimate_gear_ratios(self._n_gears.value())
        gear_texts = []
        vel_range = np.linspace(float(vel[vel > 5].min()) if (vel > 5).any() else 5,
                                float(vel.max()), 100)
        for i, (gname, gdata) in enumerate(gears.items()):
            color = Theme.SERIES[(i + 2) % len(Theme.SERIES)]
            ratio = gdata['ratio_rpm_kmh']
            rpm_line = ratio * vel_range
            self.pi.plot(vel_range, rpm_line, pen=_pen(color, 2),
                         name=f"{gname} ({ratio:.0f} rpm/km/h)")
            gear_texts.append(
                f"<font color='{color}'>{gname}: {ratio:.1f} rpm/kmh · "
                f"vel@1000rpm={gdata['vel_por_1000rpm']:.1f} km/h · "
                f"{gdata['freq_%']:.0f}%</font>")
        self._gear_lbl.setText("<br>".join(gear_texts) if gear_texts else "Marchas não detectadas")
        self.pi.setLabel('bottom', 'Velocidade (km/h)', **{'font-size':'8pt','color':_fg()})
        self.pi.setLabel('left',   'RPM', **{'font-size':'8pt','color':_fg()})

    def update_filter(self, fs): self._fs = fs; self.refresh()
    def apply_theme(self): super().apply_theme(); self.pw.setBackground(_bg())



class CvtPanel(BasePanel):
    ICON='🌀'; TITLE='CVT — RPM × Velocidade'; ACCENT='#00ff94'
    def __init__(self, runs, fs, parent=None):
        super().__init__(parent)
        self._runs = runs; self._fs = fs
        cl = self.content_layout(); cl.setSpacing(4)
        ctrl = QHBoxLayout()
        self._run_cb = QComboBox(); self._run_cb.setFixedHeight(26)
        for r in runs: self._run_cb.addItem(r.file_name)
        ctrl.addWidget(QLabel("Run:")); ctrl.addWidget(self._run_cb, 1); ctrl.addStretch()
        cl.addLayout(ctrl)
        self.pw = pg.PlotWidget(); self.pw.setBackground(_bg())
        self.pi = self.pw.getPlotItem()
        _style_pi(self.pi, True, True, 0.10, x_lbl='Velocidade (km/h)', y_lbl='RPM')
        cl.addWidget(self.pw, 1)
        self._lbl = QLabel("—"); self._lbl.setWordWrap(True)
        self._lbl.setStyleSheet(f"color:{Theme.TEXT_SEC};font-size:9px;font-family:{Theme.FONT_MONO};background:transparent;padding:3px;")
        cl.addWidget(self._lbl)
        self._run_cb.currentIndexChanged.connect(self.refresh)
        self.refresh()

    def refresh(self):
        self.pi.clear()
        idx = self._run_cb.currentIndex()
        if idx < 0 or idx >= len(self._runs): return
        r = self._runs[idx]; r.apply_filters_and_recalculate(self._fs)
        vel = r.velocity_filtered_kmh; rpm = r.rpm_filtered
        if vel.size == 0: return
        n = min(len(vel), len(rpm))
        self.pi.addItem(pg.ScatterPlotItem(x=vel[:n], y=rpm[:n], size=2, pen=None, brush=pg.mkBrush(Theme.ACCENT + '33')))
        cvt = r.analyze_cvt()
        if cvt is None:
            self._lbl.setText("Dados insuficientes para analisar o CVT (poucas amostras em movimento)."); return
        ok = np.isfinite(cvt.rpm_median)
        x = cvt.speed_centers_kmh[ok]
        lo = pg.PlotCurveItem(x, cvt.rpm_p10[ok], pen=_pen(Theme.ACCENT3, 1))
        hi = pg.PlotCurveItem(x, cvt.rpm_p90[ok], pen=_pen(Theme.ACCENT3, 1))
        self.pi.addItem(lo); self.pi.addItem(hi)
        self.pi.addItem(pg.FillBetweenItem(lo, hi, brush=pg.mkBrush(Theme.ACCENT3 + '22')))
        self.pi.plot(x, cvt.rpm_median[ok], pen=_pen(Theme.ACCENT2, 3), name='RPM mediano')
        parts = []
        if cvt.launch_rpm is not None: parts.append(f"RPM de saída ≈ {cvt.launch_rpm:.0f}")
        if cvt.hold_rpm is not None: parts.append(f"RPM sustentado ≈ {cvt.hold_rpm:.0f} (CV {cvt.hold_cv_pct:.1f}%)")
        self._lbl.setText("  ·  ".join(parts) if parts else "Sem trechos de aceleração plena para estimar RPM sustentado.")

    def update_filter(self, fs): self._fs = fs; self.refresh()
    def apply_theme(self): super().apply_theme(); self.pw.setBackground(_bg())


# ═════════════════════════════════════════════════════════════════════════════
#  CORRELATION MATRIX PANEL
# ═════════════════════════════════════════════════════════════════════════════

class CorrelationPanel(BasePanel):
    ICON='🔗'; TITLE='Matriz de Correlação'; ACCENT='#ff2d7a'
    def __init__(self, runs, fs, parent=None):
        super().__init__(parent)
        self._runs = runs; self._fs = fs
        cl = self.content_layout(); cl.setSpacing(4)

        ctrl = QHBoxLayout()
        self._run_cb = QComboBox(); self._run_cb.setFixedHeight(26)
        for r in runs: self._run_cb.addItem(r.file_name)
        ctrl.addWidget(QLabel("Run:")); ctrl.addWidget(self._run_cb, 1); ctrl.addStretch()
        cl.addLayout(ctrl)

        self.tbl = QTableWidget()
        self.tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tbl.setAlternatingRowColors(True)
        self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tbl.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        cl.addWidget(self.tbl, 1)

        self._run_cb.currentIndexChanged.connect(self.refresh)
        self.refresh()

    def refresh(self):
        idx = self._run_cb.currentIndex()
        if idx < 0 or idx >= len(self._runs): return
        matrices = compute_correlation_matrix([self._runs[idx]], self._fs)
        rn = self._runs[idx].file_name
        cmat = matrices.get(rn)
        if cmat is None: return
        keys = list(cmat.columns)
        short = [CHANNEL_UNITS.get(k, '') and f"{k[:12]}\n[{CHANNEL_UNITS.get(k,'')}]" or k[:14]
                 for k in keys]
        self.tbl.setColumnCount(len(keys)); self.tbl.setRowCount(len(keys))
        self.tbl.setHorizontalHeaderLabels(short); self.tbl.setVerticalHeaderLabels(short)
        for i, ki in enumerate(keys):
            for j, kj in enumerate(keys):
                val = float(cmat.loc[ki, kj])
                it  = QTableWidgetItem(f"{val:.3f}")
                it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                # Color: red=negative, white=zero, green=positive
                r_c  = int(max(0, min(255, 255 * (1 - val) / 2)))
                g_c  = int(max(0, min(255, 255 * (1 + val) / 2)))
                b_c  = 40
                alpha = int(abs(val) * 180 + 30)
                it.setBackground(QColor(r_c, g_c, b_c, alpha))
                if i == j:
                    it.setForeground(QColor(Theme.ACCENT))
                self.tbl.setItem(i, j, it)

    def update_filter(self, fs): self._fs = fs; self.refresh()


class PanelCanvas(QSplitter):
    panel_removed=pyqtSignal(object)
    def __init__(self,parent=None):
        super().__init__(Qt.Orientation.Vertical,parent); self.setHandleWidth(5); self.setChildrenCollapsible(False)
        self.setStyleSheet(f"QSplitter::handle{{background:{_border()};}}QSplitter::handle:hover{{background:{Theme.ACCENT_DIM};}}")
    def add_panel(self,p): p.close_requested.connect(self._close); self.addWidget(p); self._eq()
    def remove_panel(self,p): p.setParent(None); p.deleteLater(); self._eq()
    def panels(self): return [self.widget(i) for i in range(self.count()) if isinstance(self.widget(i),BasePanel)]
    def _eq(self):
        n=self.count()
        if n: self.setSizes([max(self.height(),n*120)//n]*n)
    def _close(self,p): self.panel_removed.emit(p); self.remove_panel(p)
    def _reorder(self,panel,gp):
        ly=self.mapFromGlobal(gp).y(); ps=self.panels()
        if len(ps)<2: return
        ti=min(range(len(ps)),key=lambda i: abs(ps[i].geometry().center().y()-ly))
        si=ps.index(panel) if panel in ps else -1
        if si<0 or ti==si: return
        sz=self.sizes(); panel.setParent(None); ps.pop(si); ps.insert(ti,panel)
        for p in ps: p.setParent(None)
        for p in ps: self.addWidget(p); p.show()
        if len(sz)==len(ps): self.setSizes(sz)
    def apply_theme(self): self.setStyleSheet(f"QSplitter::handle{{background:{_border()};}}QSplitter::handle:hover{{background:{Theme.ACCENT_DIM};}}")


# ═════════════════════════════════════════════════════════════════════════════
#  ANALYSIS WIDGET  — entry point
# ═════════════════════════════════════════════════════════════════════════════

class AnalysisWidget(QWidget):
    filter_changed=pyqtSignal(dict)

    def __init__(self,parent=None):
        super().__init__()
        self.app_state=None; self.vs=ViewSettings(); self.sync=SyncManager()
        self._sigs=[]; self._cidx=0; self._mode='separate'
        self._fp=self._sp=self._cp=self._ip=None
        self._hist_p=self._fft_p=self._scatter_p=self._phase_p=self._gear_p=self._corr_p=self._cvt_p=None
        self._vc_dlg=self._theme_dlg=None
        self._build()

    @property
    def filter_settings(self):
        if self._fp and self._fp.parent(): return self._fp.fp_ctrl.settings()
        if self.app_state: return dict(self.app_state.session.filter_settings)
        return dict(DEFAULT_FILTER)

    def _build(self):
        root=QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)
        self._tbar=self._make_toolbar(); root.addWidget(self._tbar)
        self._hsplit=QSplitter(Qt.Orientation.Horizontal)
        self._hsplit.setHandleWidth(4); self._hsplit.setChildrenCollapsible(True)
        self._hsplit.setStyleSheet(f"QSplitter::handle{{background:{_border()};}}QSplitter::handle:hover{{background:{Theme.ACCENT_DIM};}}")
        self._browser=ChannelBrowser()
        self._browser.setFixedWidth(248)
        self._browser.sig_add.connect(self._add_signal)
        self._browser.sigs_add.connect(lambda lst: [self._add_signal(sk,r) for sk,r in lst])
        self._hsplit.addWidget(self._browser)
        self._hsplit.addWidget(self._make_canvas())
        self._hsplit.setSizes([248,9999]); self._hsplit.setStretchFactor(1,1)
        root.addWidget(self._hsplit,1)

    # ── toolbar ───────────────────────────────────────────────────────────────

    def _make_toolbar(self):
        bar=QFrame(); bar.setFixedHeight(50)
        bar.setStyleSheet(f"QFrame{{background:{_toolbar()};border-bottom:2px solid {Theme.BORDER};}}")
        hl=QHBoxLayout(bar); hl.setContentsMargins(14,6,14,6); hl.setSpacing(6)
        def lbl(t): l=QLabel(t); l.setStyleSheet(f"font-size:8px;color:{_subtle()};font-weight:bold;background:transparent;letter-spacing:2px;"); return l
        def sep(): s=QFrame(); s.setFrameShape(QFrame.Shape.VLine); s.setFixedSize(1,24); s.setStyleSheet(f"background:{Theme.BORDER_LT};"); return s
        def tb(t,tip="",chk=False): return _mkbtn(t,32)

        hl.addWidget(lbl("EIXO X"))
        self._cx=QComboBox(); self._cx.addItems(CHANNELS); self._cx.setFixedSize(188,32)
        self._cx.currentTextChanged.connect(self._on_x); hl.addWidget(self._cx); hl.addWidget(sep())

        hl.addWidget(lbl("MODO"))
        self._grp=QButtonGroup(self); self._rs=QRadioButton("Separado"); self._rs.setChecked(True); self._ro=QRadioButton("Sobreposto")
        for rb in(self._rs,self._ro): rb.setStyleSheet(f"color:{_text()};font-size:11px;"); hl.addWidget(rb)
        self._grp.addButton(self._rs,0); self._grp.addButton(self._ro,1); self._grp.buttonToggled.connect(self._on_mode); hl.addWidget(sep())

        hl.addWidget(lbl("SYNC"))
        sf=QFrame(); sf.setFixedHeight(34)
        sf.setStyleSheet(f"QFrame{{background:{_surface()};border:1px solid {_border()};border-radius:7px;}}")
        shl=QHBoxLayout(sf); shl.setContentsMargins(3,3,3,3); shl.setSpacing(2)
        sc=(f"QPushButton{{border:none;border-radius:5px;background:transparent;color:{_subtle()};padding:0 10px;font-size:10px;font-weight:bold;}}"
            f"QPushButton:hover{{background:{Theme.HOVER};color:{_text()};}}"
            f"QPushButton:checked{{background:{Theme.ACCENT_BG};color:{Theme.ACCENT};}}")
        self._bs0=QPushButton("Off"); self._bs0.setCheckable(True); self._bs0.setChecked(True)
        self._bs1=QPushButton("| Cursor"); self._bs1.setCheckable(True)
        self._bs2=QPushButton("|·| Intervalo"); self._bs2.setCheckable(True)
        for b in(self._bs0,self._bs1,self._bs2): b.setFixedHeight(28); b.setStyleSheet(sc); shl.addWidget(b)
        self._sg=QButtonGroup(self); self._sg.setExclusive(True)
        self._sg.addButton(self._bs0,0); self._sg.addButton(self._bs1,1); self._sg.addButton(self._bs2,2)
        self._sg.idClicked.connect(self._on_sync); hl.addWidget(sf); hl.addWidget(sep())

        ba=QToolButton(); ba.setText("＋  Adicionar"); ba.setFixedHeight(32)
        ba.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        ba.setStyleSheet(f"QToolButton{{padding:0 14px;border-radius:6px;border:1px solid {Theme.ACCENT_DIM};background:{Theme.ACCENT_BG};color:{Theme.ACCENT};font-size:11px;font-weight:bold;}}QToolButton::menu-indicator{{image:none;}}QToolButton:hover{{background:{Theme.HOVER};border-color:{Theme.ACCENT};}}")
        ma=QMenu(ba)
        ma.addAction("⚗  Filtro",            self._add_fp)
        ma.addAction("📊  Estatísticas",     self._add_sp)
        ma.addAction("⚖  Comparação",       self._add_cp)
        ma.addAction("🧠  Inteligência",     self._add_ip)
        ma.addSeparator()
        ma.addAction("📶  Histograma",       self._add_hist)
        ma.addAction("〰  FFT / Espectro",  self._add_fft)
        ma.addAction("✦  Dispersão X×Y",   self._add_scatter)
        ma.addAction("🎯  Fases",            self._add_phase)
        ma.addAction("⚙  Marchas",          self._add_gear)
        ma.addAction("🌀  CVT",              self._add_cvt)
        ma.addAction("🔗  Correlações",      self._add_corr)
        ma.addSeparator()
        ma.addAction("⚙  Canais Virtuais",  self._open_vc)
        ba.setMenu(ma); hl.addWidget(ba); hl.addWidget(sep())

        bf=tb("⊞ Fit"); bf.clicked.connect(self._fit); hl.addWidget(bf)
        bc=tb("✕ Limpar"); bc.clicked.connect(self._clear); hl.addWidget(bc); hl.addWidget(sep())

        bw=QToolButton(); bw.setText("💾  Workspace"); bw.setFixedHeight(32)
        bw.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        bw.setStyleSheet(f"QToolButton{{padding:0 12px;border-radius:6px;border:1px solid {Theme.BORDER_LT};background:{_surface()};color:{_text()};font-size:11px;}}QToolButton::menu-indicator{{image:none;}}QToolButton:hover{{background:{Theme.HOVER};color:{Theme.ACCENT};}}")
        mw=QMenu(bw)
        mw.addAction("💾  Salvar Layout…",  self._save_layout)
        mw.addAction("📂  Carregar Layout…", self._load_layout)
        mw.addSeparator()
        mw.addAction("📤  Exportar", self._export_ws)
        mw.addAction("📥  Importar", self._import_ws)
        bw.setMenu(mw); hl.addWidget(bw)

        bt=tb("🎨 Tema"); bt.clicked.connect(self._open_theme); hl.addWidget(bt)
        self._nl=QLabel("—"); self._nl.setStyleSheet(f"font-size:10px;color:{_subtle()};margin-left:8px;background:transparent;font-family:{Theme.FONT_MONO};"); hl.addWidget(self._nl)
        hl.addStretch()
        bside=QPushButton("◀ Canais"); bside.setFixedHeight(32); bside.setCheckable(True)
        bside.setStyleSheet(f"QPushButton{{border:1px solid {_border()};border-radius:6px;background:{_surface()};color:{_text()};padding:0 10px;font-size:11px;}}QPushButton:checked{{background:{Theme.ACCENT_BG};color:{Theme.ACCENT};border-color:{Theme.ACCENT};}}")
        bside.toggled.connect(lambda c: self._browser.setVisible(not c)); hl.addWidget(bside)
        return bar

    # ── canvas ────────────────────────────────────────────────────────────────

    def _make_canvas(self):
        ct=QWidget(); ct.setStyleSheet(f"background:{_bg()};")
        vl=QVBoxLayout(ct); vl.setContentsMargins(0,0,0,0); vl.setSpacing(0)
        self._canvas=PanelCanvas(); self._canvas.panel_removed.connect(self._on_removed)
        ph=QWidget(); ph.setStyleSheet(f"background:{_bg()};")
        phl=QVBoxLayout(ph); phl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        phl.addWidget((lambda l: (l.setAlignment(Qt.AlignmentFlag.AlignCenter),l.setStyleSheet("font-size:52px;background:transparent;"),l)[2])(QLabel("📈")))
        phl.addWidget((lambda l: (l.setAlignment(Qt.AlignmentFlag.AlignCenter),l.setWordWrap(True),l.setStyleSheet(f"font-size:13px;color:{_subtle()};background:transparent;line-height:1.7;"),l)[3])(QLabel("Canvas vazio\n\nClique duplo num canal no browser à esquerda\nou use ＋ Adicionar para incluir painéis.\n\nModo Sobreposto: múltiplos sinais com eixos Y independentes.")))
        self._stk=QStackedWidget(); self._stk.addWidget(ph); self._stk.addWidget(self._canvas)
        self._ovl=MultiAxisOverlay(self.vs); self._ovl.cursor_moved.connect(self._on_ovl_cur)
        self._mstk=QStackedWidget(); self._mstk.addWidget(self._stk); self._mstk.addWidget(self._ovl)
        vl.addWidget(self._mstk,1); return ct

    # ── state ─────────────────────────────────────────────────────────────────

    def link_state(self,app_state):
        self.app_state=app_state; app_state.data_loaded.connect(self._on_loaded); self._on_loaded()

    def _on_loaded(self):
        if not self.app_state or not self.app_state.runs: return
        fs=self.filter_settings
        for r in self.app_state.runs: r.apply_filters_and_recalculate(fs)
        self._browser.set_data(self.app_state.runs,fs,WS.list_virtuals())
        WS.push_recent([r.file_path for r in self.app_state.runs])
        if self._cp and self._cp.parent(): self._cp.refresh(self.app_state.runs,fs)
        if self._sp and self._sp.parent(): self._ref_sp()
        if self._ip and self._ip.parent(): self._ref_ip()

    # ── signals ───────────────────────────────────────────────────────────────

    def _next_color(self): c=Theme.SERIES[self._cidx%len(Theme.SERIES)]; self._cidx+=1; return c

    def _add_signal(self,sk,run):
        if any(s['key']==sk and s['run'] is run for s in self._sigs): return
        color=self._next_color(); self._sigs.append({'key':sk,'run':run,'color':color})
        if self._mode=='separate':
            p=PlotPanel(sk,run,self._cx.currentText(),color,self.filter_settings,self.vs,self.sync)
            p.cursor_moved.connect(lambda x,src=p: self.sync.move_a(x,src))
            p.cursor_b_moved.connect(lambda x,src=p: self.sync.move_b(x,src))
            p.close_requested.connect(self._on_removed)
            self._canvas.add_panel(p); self._stk.setCurrentIndex(1)
            p.apply_sync_mode(self.sync.mode,self.sync.pos_a,self.sync.pos_b); self._sync_x()
        else:
            run.apply_filters_and_recalculate(self.filter_settings)
            xd=run.get_channel(self._cx.currentText()); yd=run.get_channel(sk)
            if xd.size and yd.size: n=min(len(xd),len(yd)); self._ovl.add_signal(sk,run,xd[:n],yd[:n],color)
            self._ovl.set_x_label(self._cx.currentText())
        self.sync.set_panels(self._pps()); self._ref_sp(); self._upd_n()

    def _pps(self): return [p for p in self._canvas.panels() if isinstance(p,PlotPanel)]

    # ── panels ────────────────────────────────────────────────────────────────

    def _add_fp(self):
        if self._fp and self._fp.parent(): return
        class _FP(BasePanel):
            ICON='⚗'; TITLE='Filtro'; ACCENT='#00a870'
            def __init__(s,parent=None):
                super().__init__(parent); cl=s.content_layout(); s.fp_ctrl=FilterPanel(); s.fp_ctrl.filter_changed.connect(s.filter_changed); cl.addWidget(s.fp_ctrl)
            filter_changed=pyqtSignal(dict)
        self._fp=_FP(); self._fp.filter_changed.connect(self._on_filter); self._fp.close_requested.connect(self._on_removed)
        self._canvas.add_panel(self._fp); self._stk.setCurrentIndex(1)

    def _add_sp(self):
        if self._sp and self._sp.parent(): return
        self._sp=StatsPanel(); self._sp.close_requested.connect(self._on_removed)
        self._canvas.add_panel(self._sp); self._stk.setCurrentIndex(1); self._ref_sp()

    def _add_cp(self):
        if self._cp and self._cp.parent(): return
        self._cp=ComparePanel(); self._cp.close_requested.connect(self._on_removed)
        self._canvas.add_panel(self._cp); self._stk.setCurrentIndex(1)
        if self.app_state and self.app_state.runs: self._cp.refresh(self.app_state.runs,self.filter_settings)

    def _add_ip(self):
        if self._ip and self._ip.parent(): return
        self._ip=IntelligencePanel(); self._ip.close_requested.connect(self._on_removed)
        self._canvas.add_panel(self._ip); self._stk.setCurrentIndex(1); self._ref_ip()

    def _add_hist(self):
        if self._hist_p and self._hist_p.parent(): return
        runs = self.app_state.runs if self.app_state else []
        if not runs: QMessageBox.information(self,"Histograma","Carregue dados primeiro."); return
        self._hist_p = HistogramPanel(runs, self.filter_settings)
        self._hist_p.close_requested.connect(self._on_removed)
        self._canvas.add_panel(self._hist_p); self._stk.setCurrentIndex(1)

    def _add_fft(self):
        if self._fft_p and self._fft_p.parent(): return
        runs = self.app_state.runs if self.app_state else []
        if not runs: QMessageBox.information(self,"FFT","Carregue dados primeiro."); return
        self._fft_p = FrequencyPanel(runs, self.filter_settings)
        self._fft_p.close_requested.connect(self._on_removed)
        self._canvas.add_panel(self._fft_p); self._stk.setCurrentIndex(1)

    def _add_scatter(self):
        if self._scatter_p and self._scatter_p.parent(): return
        runs = self.app_state.runs if self.app_state else []
        if not runs: QMessageBox.information(self,"Scatter","Carregue dados primeiro."); return
        self._scatter_p = ScatterPanel(runs, self.filter_settings)
        self._scatter_p.close_requested.connect(self._on_removed)
        self._canvas.add_panel(self._scatter_p); self._stk.setCurrentIndex(1)

    def _add_phase(self):
        if self._phase_p and self._phase_p.parent(): return
        runs = self.app_state.runs if self.app_state else []
        if not runs: QMessageBox.information(self,"Fases","Carregue dados primeiro."); return
        self._phase_p = PhasePanel(runs, self.filter_settings)
        self._phase_p.close_requested.connect(self._on_removed)
        self._canvas.add_panel(self._phase_p); self._stk.setCurrentIndex(1)

    def _add_gear(self):
        if self._gear_p and self._gear_p.parent(): return
        runs = self.app_state.runs if self.app_state else []
        if not runs: QMessageBox.information(self,"Marchas","Carregue dados primeiro."); return
        self._gear_p = GearPanel(runs, self.filter_settings)
        self._gear_p.close_requested.connect(self._on_removed)
        self._canvas.add_panel(self._gear_p); self._stk.setCurrentIndex(1)

    def _add_cvt(self):
        if self._cvt_p and self._cvt_p.parent(): return
        runs = self.app_state.runs if self.app_state else []
        if not runs: QMessageBox.information(self,"CVT","Carregue dados primeiro."); return
        self._cvt_p = CvtPanel(runs, self.filter_settings)
        self._cvt_p.close_requested.connect(self._on_removed)
        self._canvas.add_panel(self._cvt_p); self._stk.setCurrentIndex(1)

    def _add_corr(self):
        if self._corr_p and self._corr_p.parent(): return
        runs = self.app_state.runs if self.app_state else []
        if not runs: QMessageBox.information(self,"Correlação","Carregue dados primeiro."); return
        self._corr_p = CorrelationPanel(runs, self.filter_settings)
        self._corr_p.close_requested.connect(self._on_removed)
        self._canvas.add_panel(self._corr_p); self._stk.setCurrentIndex(1)

    def _on_removed(self,panel):
        if isinstance(panel,PlotPanel):
            self._sigs=[s for s in self._sigs if not(s['key']==panel.signal_key and s['run'] is panel.run)]
            self._ovl.remove_signal(panel.signal_key,panel.run)
        elif panel is self._fp: self._fp=None
        elif panel is self._sp: self._sp=None
        elif panel is self._cp: self._cp=None
        elif panel is self._ip: self._ip=None
        elif panel is self._hist_p:    self._hist_p=None
        elif panel is self._fft_p:     self._fft_p=None
        elif panel is self._scatter_p: self._scatter_p=None
        elif panel is self._phase_p:   self._phase_p=None
        elif panel is self._gear_p:    self._gear_p=None
        elif panel is self._cvt_p:     self._cvt_p=None
        elif panel is self._corr_p:    self._corr_p=None
        self.sync.set_panels(self._pps()); self._ref_sp(); self._upd_n()
        if self._canvas.count()==0: self._stk.setCurrentIndex(0)

    def _open_vc(self):
        runs=self.app_state.runs if self.app_state else []
        if self._vc_dlg is None or not self._vc_dlg.isVisible():
            self._vc_dlg=VirtualChannelEditor(runs,self.filter_settings,self)
            self._vc_dlg.changed.connect(lambda: self._browser.set_data(self.app_state.runs if self.app_state else [],self.filter_settings,WS.list_virtuals()))
        self._vc_dlg.show(); self._vc_dlg.raise_()

    def _open_theme(self):
        if self._theme_dlg is None or not self._theme_dlg.isVisible():
            self._theme_dlg=ThemeCustomizer(self)
            self._theme_dlg.applied.connect(self.apply_theme)
        self._theme_dlg.show(); self._theme_dlg.raise_()

    # ── filter ────────────────────────────────────────────────────────────────

    def _on_filter(self,fs):
        if self.app_state: self.app_state.session.set_filter(fs)
        for p in self._pps(): p.update_filter(fs)
        if self._mode=='overlay': self._rebuild_ovl()
        self._ref_sp(); self._ref_cp(); self._ref_ip()
        # Propaga para novos painéis
        for p in [self._hist_p, self._fft_p, self._scatter_p,
                  self._phase_p, self._gear_p, self._corr_p, self._cvt_p]:
            if p and p.parent(): p.update_filter(fs)
        self.filter_changed.emit(fs)
        if self.app_state and self.app_state.runs:
            self._browser.set_data(self.app_state.runs,fs,WS.list_virtuals())

    # ── mode ─────────────────────────────────────────────────────────────────

    def _on_mode(self,_,checked):
        if not checked: return
        new='separate' if self._grp.checkedId()==0 else 'overlay'
        if new==self._mode: return
        self._mode=new
        self._mstk.setCurrentIndex(1 if new=='overlay' else 0)
        if new=='overlay': self._rebuild_ovl()

    def _rebuild_ovl(self):
        self._ovl.clear(); fs=self.filter_settings; xk=self._cx.currentText()
        for e in self._sigs:
            e['run'].apply_filters_and_recalculate(fs)
            xd=e['run'].get_channel(xk); yd=e['run'].get_channel(e['key'])
            if xd.size and yd.size: n=min(len(xd),len(yd)); self._ovl.add_signal(e['key'],e['run'],xd[:n],yd[:n],e['color'])
        self._ovl.set_x_label(xk)

    # ── sync / x ──────────────────────────────────────────────────────────────

    def _on_sync(self,idx): m={0:'off',1:'single',2:'interval'}[idx]; self.sync.set_mode(m); self.vs.sync_windows=(idx>0); self._sync_x()
    def _on_x(self,xk): [p.update_x(xk) for p in self._pps()]; self._rebuild_ovl() if self._mode=='overlay' else None
    def _on_ovl_cur(self,_): self._ref_sp()
    def _sync_x(self):
        ps=self._pps()
        if not ps: return
        if self.vs.sync_windows: [p.link_x(ps[0].pi) for p in ps[1:]]
        else: [p.unlink_x() for p in ps]

    # ── refresh helpers ───────────────────────────────────────────────────────

    def _ref_sp(self):
        if self._sp and self._sp.parent(): self._sp.refresh(self._pps(),self.filter_settings,self.sync)
    def _ref_cp(self):
        if self._cp and self._cp.parent() and self.app_state and self.app_state.runs: self._cp.refresh(self.app_state.runs,self.filter_settings)
    def _ref_ip(self):
        if self._ip and self._ip.parent() and self.app_state and self.app_state.runs:
            try: self._ip.refresh(_full_analysis(self.app_state.runs,self.filter_settings,self.app_state.session.profile))
            except Exception as e: _log.warning("[Intel] %s", e)

    # ── workspace ─────────────────────────────────────────────────────────────

    def _save_layout(self):
        n,ok=QInputDialog.getText(self,"Salvar Layout","Nome:")
        if not ok or not n.strip(): return
        WS.save_layout(n.strip(),{'filter':self.filter_settings,'x_key':self._cx.currentText(),'mode':self._mode,
            'panels':[{'sk':p.signal_key,'run':p.run.file_name,'color':p.color} for p in self._pps()]})
        QMessageBox.information(self,"OK",f"Layout '{n}' salvo.")

    def _load_layout(self):
        ns=WS.list_layouts()
        if not ns: QMessageBox.information(self,"Layouts","Nenhum layout salvo."); return
        n,ok=QInputDialog.getItem(self,"Carregar Layout","Selecione:",ns,0,False)
        if not ok: return
        d=WS.load_layout(n)
        if not d: return
        self._clear()
        if d.get('x_key') in CHANNELS: self._cx.setCurrentText(d['x_key'])
        if self.app_state and self.app_state.runs:
            rm={r.file_name:r for r in self.app_state.runs}
            for pd in d.get('panels',[]):
                r=rm.get(pd.get('run')); sk=pd.get('sk','')
                if r and sk: self._add_signal(sk,r)

    def _export_ws(self):
        from PyQt6.QtWidgets import QFileDialog
        p,_=QFileDialog.getSaveFileName(self,"Exportar Workspace","","JSON (*.json)")
        if p: WS.export_all(p); QMessageBox.information(self,"OK",f"Exportado:\n{p}")

    def _import_ws(self):
        from PyQt6.QtWidgets import QFileDialog
        p,_=QFileDialog.getOpenFileName(self,"Importar Workspace","","JSON (*.json)")
        if p:
            try: nl,np_,nv=WS.import_all(p); QMessageBox.information(self,"OK",f"{nl} layouts, {np_} presets, {nv} canais.")
            except Exception as e: QMessageBox.critical(self,"Erro",str(e))

    # ── misc ──────────────────────────────────────────────────────────────────

    def _fit(self):
        if self._mode=='separate': [p.pi.autoRange() for p in self._pps()]
        else: self._ovl.fit()

    def _clear(self):
        for p in list(self._canvas.panels()): self._canvas.remove_panel(p)
        self._ovl.clear(); self._sigs.clear(); self._cidx=0
        self._fp=self._sp=self._cp=self._ip=None
        self.sync.set_panels([]); self._stk.setCurrentIndex(0); self._upd_n()

    def _upd_n(self):
        n=len(self._sigs); self._nl.setText("—" if not n else "1 sinal" if n==1 else f"{n} sinais")

    def apply_theme(self):
        pg.setConfigOption('background',Theme.BG_BASE); pg.setConfigOption('foreground',Theme.TEXT_SEC)
        self._tbar.setStyleSheet(f"QFrame{{background:{_toolbar()};border-bottom:2px solid {Theme.BORDER};}}")
        self._canvas.apply_theme()
        for p in self._canvas.panels(): p.apply_theme()
        for p in self._pps(): p.pw.setBackground(_bg()); _style_pi(p.pi,self.vs.grid_x,self.vs.grid_y,self.vs.grid_alpha,x_lbl=p.x_key,y_lbl=p.signal_key)
        self._ovl.apply_theme()
        for p in [self._hist_p, self._fft_p, self._scatter_p, self._gear_p]:
            if p and p.parent(): p.apply_theme()

    def get_figure_for_report(self):
        try:
            t=self._canvas if self._mode=='separate' else self._ovl
            px=t.grab(); buf=QBuffer(); buf.open(QIODevice.OpenModeFlag.WriteOnly)
            px.save(buf,"PNG"); return bytes(buf.data())
        except Exception: return None


# Alias
CustomPlotWidget = AnalysisWidget
