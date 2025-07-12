# iLogger/ui/widgets/filter_control_panel.py

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QComboBox, QLabel, QSlider, QGridLayout, QGroupBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from functools import partial
from config import *

class FilterControlPanel(QWidget):
    """
    Painel de controle de filtros.
    Versão 3: Adiciona mostradores de valor para cada slider e aumenta o range.
    """
    filter_changed = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(5, 5, 5, 5)
        self.main_layout.setSpacing(10)

        filter_group = QGroupBox("Configuração de Filtro")
        # Layout de 3 colunas: Label, Slider, Valor
        self.grid_layout = QGridLayout(filter_group)
        self.grid_layout.setColumnStretch(1, 1) # Faz o slider ocupar o espaço extra

        self.grid_layout.addWidget(QLabel("Tipo de Filtro:"), 0, 0, 1, 3)
        self.filter_type_combo = QComboBox()
        self.filter_type_combo.addItems(['butterworth', 'savitzky_golay', 'chebyshev_type_i', 'bessel', 'median', 'moving_average'])
        self.grid_layout.addWidget(self.filter_type_combo, 1, 0, 1, 3)
        
        self.filter_widgets = {}
        self.value_labels = {}

        self._create_butterworth_controls()
        self._create_savgol_controls()
        self._create_cheby1_controls()
        self._create_bessel_controls()
        self._create_median_controls()
        self._create_ma_controls()
        
        self.main_layout.addWidget(filter_group)
        self.main_layout.addStretch()

        self.filter_type_combo.currentTextChanged.connect(self._on_filter_type_change)
        self._update_controls_visibility()
        self.emit_filter_change() # Emite o estado inicial

    def _create_slider(self, min_val, max_val, initial_val, tick_interval=1):
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(min_val, max_val)
        slider.setValue(initial_val)
        slider.setTickInterval(tick_interval)
        slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        return slider
    
    def _add_slider_control(self, layout_row, name, min_val, max_val, initial_val, label_text, is_float=False, is_odd=False):
        """Cria um conjunto completo de Label-Slider-Valor."""
        label = QLabel(label_text)
        slider = self._create_slider(min_val, max_val, initial_val)
        value_label = QLabel(str(initial_val))
        value_label.setFixedWidth(30) # Largura fixa para o valor

        self.grid_layout.addWidget(label, layout_row, 0)
        self.grid_layout.addWidget(slider, layout_row, 1)
        self.grid_layout.addWidget(value_label, layout_row, 2)
        
        # Conecta o slider para atualizar o label e emitir a mudança
        update_func = partial(self._update_value_label, label=value_label, is_float=is_float, is_odd=is_odd)
        slider.valueChanged.connect(update_func)
        slider.valueChanged.connect(self.emit_filter_change)

        # Atualiza o label com o valor inicial formatado
        self._update_value_label(initial_val, value_label, is_float, is_odd)

        return label, slider, value_label

    def _update_value_label(self, value, label, is_float, is_odd):
        """Atualiza o texto do label de valor do slider."""
        display_value = value
        if is_odd and value % 2 == 0:
            display_value = value + 1 # Mostra o valor ímpar que será usado
        if is_float:
            label.setText(f"{display_value / 100.0:.2f}")
        else:
            label.setText(str(display_value))

    def _add_filter_controls(self, filter_name, controls_to_add, start_row):
        """Adiciona um grupo de widgets de filtro ao layout e ao dicionário."""
        self.filter_widgets[filter_name] = []
        row = start_row
        for (name, params) in controls_to_add.items():
            label, slider, value_label = self._add_slider_control(row, name, **params)
            self.filter_widgets[filter_name].extend([label, slider, value_label])
            setattr(self, name, slider) # Armazena o slider como atributo da classe
            row += 1

    def _create_butterworth_controls(self):
        controls = {
            'butter_order_slider': {'min_val': 1, 'max_val': 10, 'initial_val': BUTTERWORTH_ORDER, 'label_text': "Ordem:"},
            'butter_cutoff_slider': {'min_val': 1, 'max_val': 99, 'initial_val': int(BUTTERWORTH_CUTOFF * 100), 'label_text': "Cutoff:", 'is_float': True}
        }
        self._add_filter_controls('butterworth', controls, 2)

    def _create_savgol_controls(self):
        controls = {
            'savgol_window_slider': {'min_val': 5, 'max_val': 99, 'initial_val': SAVGOL_WINDOW, 'label_text': "Janela:", 'is_odd': True},
            'savgol_poly_slider': {'min_val': 1, 'max_val': 10, 'initial_val': SAVGOL_POLYORDER, 'label_text': "Ordem Polinomial:"}
        }
        self._add_filter_controls('savitzky_golay', controls, 2)

    def _create_cheby1_controls(self):
        controls = {
            'cheby1_order_slider': {'min_val': 1, 'max_val': 10, 'initial_val': CHEBY1_ORDER, 'label_text': "Ordem:"},
            'cheby1_rp_slider': {'min_val': 1, 'max_val': 10, 'initial_val': CHEBY1_RP, 'label_text': "Ripple (rp):"},
            'cheby1_cutoff_slider': {'min_val': 1, 'max_val': 99, 'initial_val': int(CHEBY1_CUTOFF * 100), 'label_text': "Cutoff:", 'is_float': True}
        }
        self._add_filter_controls('chebyshev_type_i', controls, 2)

    def _create_bessel_controls(self):
        controls = {
            'bessel_order_slider': {'min_val': 1, 'max_val': 10, 'initial_val': BESSEL_ORDER, 'label_text': "Ordem:"},
            'bessel_cutoff_slider': {'min_val': 1, 'max_val': 99, 'initial_val': int(BESSEL_CUTOFF * 100), 'label_text': "Cutoff:", 'is_float': True}
        }
        self._add_filter_controls('bessel', controls, 2)
    
    def _create_median_controls(self):
        controls = {
            'median_kernel_slider': {'min_val': 3, 'max_val': 99, 'initial_val': MEDIAN_KERNEL_SIZE, 'label_text': "Tamanho Kernel:", 'is_odd': True}
        }
        self._add_filter_controls('median', controls, 2)

    def _create_ma_controls(self):
        controls = {
            'ma_window_slider': {'min_val': 3, 'max_val': 99, 'initial_val': MOVING_AVG_WINDOW, 'label_text': "Janela Média Móvel:"}
        }
        self._add_filter_controls('moving_average', controls, 2)

    def _on_filter_type_change(self):
        self._update_controls_visibility()
        self.emit_filter_change()

    def _update_controls_visibility(self):
        selected_filter = self.filter_type_combo.currentText()
        for filter_name, widgets in self.filter_widgets.items():
            is_visible = (filter_name == selected_filter)
            for widget in widgets:
                widget.setVisible(is_visible)

    def get_settings(self) -> dict:
        filter_type = self.filter_type_combo.currentText()
        settings = {'type': filter_type}

        if filter_type == 'butterworth':
            settings['butter_order'] = self.butter_order_slider.value()
            settings['butter_cutoff'] = self.butter_cutoff_slider.value() / 100.0
        elif filter_type == 'savitzky_gola_y':
            win = self.savgol_window_slider.value()
            settings['savgol_window'] = win + 1 if win % 2 == 0 else win
            poly = self.savgol_poly_slider.value()
            settings['savgol_polyorder'] = min(poly, settings['savgol_window'] - 2)
        elif filter_type == 'chebyshev_type_i':
            settings['cheby1_order'] = self.cheby1_order_slider.value()
            settings['cheby1_rp'] = self.cheby1_rp_slider.value()
            settings['cheby1_cutoff'] = self.cheby1_cutoff_slider.value() / 100.0
        elif filter_type == 'bessel':
            settings['bessel_order'] = self.bessel_order_slider.value()
            settings['bessel_cutoff'] = self.bessel_cutoff_slider.value() / 100.0
        elif filter_type == 'median':
            k = self.median_kernel_slider.value()
            settings['median_kernel'] = k + 1 if k % 2 == 0 else k
        elif filter_type == 'moving_average':
            settings['moving_avg_window'] = self.ma_window_slider.value()

        return settings

    def emit_filter_change(self):
        self.filter_changed.emit(self.get_settings())