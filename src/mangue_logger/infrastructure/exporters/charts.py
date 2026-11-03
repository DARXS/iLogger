"""Gráficos matplotlib (PNG em bytes) para PDF/Excel. Sem Qt."""

from __future__ import annotations

import json
import logging
from datetime import datetime

import numpy as np
import pandas as pd

from ...domain.channels import (
    KEY_ACEL_MS2_FILT, KEY_DIST_M, KEY_RPM_FILT, KEY_RPM_RAW, KEY_TEMPO_S,
    KEY_VEL_KMH_FILT, KEY_VEL_KMH_RAW,
)
from ...domain.channels import DEFAULT_CHANNELS

CHANNEL_UNITS = {c.label: c.unit for c in DEFAULT_CHANNELS}

log = logging.getLogger(__name__)


def _mpl_available() -> bool:
    try:
        import matplotlib
        return True
    except ImportError:
        return False


def _make_figure(runs, key_x, key_y, title, xlabel, ylabel, colors,
                 figsize=(8, 3.5)) -> bytes | None:
    """Gera figura matplotlib e retorna bytes PNG."""
    if not _mpl_available():
        return None
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=figsize, facecolor='#0d1117')
    ax.set_facecolor('#070a0d')
    for spine in ax.spines.values():
        spine.set_color('#1a2332')
    ax.tick_params(colors='#6d8aaa', labelsize=8)
    ax.xaxis.label.set_color('#6d8aaa')
    ax.yaxis.label.set_color('#6d8aaa')
    ax.set_title(title, color='#e8f1fc', fontsize=10, pad=8)
    ax.set_xlabel(xlabel, fontsize=8)
    ax.set_ylabel(ylabel, fontsize=8)
    ax.grid(True, alpha=0.12, color='#1a2332')
    for r, c in zip(runs, colors):
        xd = r.get_channel(key_x); yd = r.get_channel(key_y)
        if xd.size and yd.size:
            n = min(len(xd), len(yd))
            ax.plot(xd[:n], yd[:n], color=c, linewidth=1.2,
                    label=r.file_name, alpha=0.9)
    ax.legend(fontsize=7, facecolor='#131920', edgecolor='#1a2332',
              labelcolor='#e8f1fc', loc='upper right')
    plt.tight_layout(pad=0.8)
    import io
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=130, bbox_inches='tight',
                facecolor=fig.get_facecolor())
    plt.close(fig)
    return buf.getvalue()


def _make_histogram_figure(runs, key, title, xlabel, colors,
                            bins=50, figsize=(8, 3.5)) -> bytes | None:
    if not _mpl_available():
        return None
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=figsize, facecolor='#0d1117')
    ax.set_facecolor('#070a0d')
    for spine in ax.spines.values(): spine.set_color('#1a2332')
    ax.tick_params(colors='#6d8aaa', labelsize=8)
    ax.set_title(title, color='#e8f1fc', fontsize=10, pad=8)
    ax.set_xlabel(xlabel, fontsize=8); ax.set_ylabel('Frequência', fontsize=8)
    ax.grid(True, alpha=0.12, color='#1a2332', axis='y')
    for r, c in zip(runs, colors):
        data = r.get_channel(key)
        if data.size:
            ax.hist(data, bins=bins, alpha=0.55, color=c,
                    label=r.file_name, edgecolor='none')
    ax.legend(fontsize=7, facecolor='#131920', edgecolor='#1a2332',
              labelcolor='#e8f1fc')
    plt.tight_layout(pad=0.8)
    import io
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=130, bbox_inches='tight',
                facecolor=fig.get_facecolor())
    plt.close(fig)
    return buf.getvalue()


def _make_scatter_figure(runs, key_x, key_y, title, xlabel, ylabel, colors,
                          figsize=(8, 3.5)) -> bytes | None:
    if not _mpl_available():
        return None
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=figsize, facecolor='#0d1117')
    ax.set_facecolor('#070a0d')
    for spine in ax.spines.values(): spine.set_color('#1a2332')
    ax.tick_params(colors='#6d8aaa', labelsize=8)
    ax.set_title(title, color='#e8f1fc', fontsize=10, pad=8)
    ax.set_xlabel(xlabel, fontsize=8); ax.set_ylabel(ylabel, fontsize=8)
    ax.grid(True, alpha=0.10, color='#1a2332')
    for r, c in zip(runs, colors):
        xd = r.get_channel(key_x); yd = r.get_channel(key_y)
        if xd.size and yd.size:
            n = min(len(xd), len(yd))
            ax.scatter(xd[:n], yd[:n], color=c, s=3, alpha=0.5,
                       label=r.file_name, linewidths=0)
    ax.legend(fontsize=7, facecolor='#131920', edgecolor='#1a2332',
              labelcolor='#e8f1fc')
    plt.tight_layout(pad=0.8)
    import io
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=130, bbox_inches='tight',
                facecolor=fig.get_facecolor())
    plt.close(fig)
    return buf.getvalue()


def _make_phase_bar_figure(phase_data: dict, figsize=(8, 4)) -> bytes | None:
    """Gráfico de barras empilhadas com distribuição de fases."""
    if not _mpl_available() or not phase_data:
        return None
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    runs_names = list(phase_data.keys())
    phases = ['aceleração', 'frenagem', 'estabilização']
    colors = ['#00ff94', '#ff3355', '#ffcc00']
    vals = {p: [] for p in phases}
    for rn in runs_names:
        pd_ = phase_data.get(rn, {})
        for p in phases:
            vals[p].append(pd_.get(p, {}).get('percent_%', 0))
    x = np.arange(len(runs_names))
    fig, ax = plt.subplots(figsize=figsize, facecolor='#0d1117')
    ax.set_facecolor('#070a0d')
    for spine in ax.spines.values(): spine.set_color('#1a2332')
    ax.tick_params(colors='#6d8aaa', labelsize=8)
    ax.set_title('Distribuição de Fases por Run (%)', color='#e8f1fc', fontsize=10, pad=8)
    ax.set_ylabel('Tempo (%)', fontsize=8)
    bottom = np.zeros(len(runs_names))
    for p, c in zip(phases, colors):
        heights = np.array(vals[p])
        ax.bar(x, heights, bottom=bottom, color=c, alpha=0.85,
               label=p.capitalize(), edgecolor='none')
        # Label on bar if visible
        for i, (h, b) in enumerate(zip(heights, bottom)):
            if h > 4:
                ax.text(i, b + h/2, f'{h:.0f}%', ha='center', va='center',
                        fontsize=7, color='#0d1117', fontweight='bold')
        bottom += heights
    ax.set_xticks(x)
    ax.set_xticklabels([n[:18] for n in runs_names], rotation=20, ha='right')
    ax.legend(fontsize=7, facecolor='#131920', edgecolor='#1a2332',
              labelcolor='#e8f1fc', loc='lower right')
    ax.set_ylim(0, 105)
    ax.grid(True, alpha=0.10, color='#1a2332', axis='y')
    plt.tight_layout(pad=0.8)
    import io
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=130, bbox_inches='tight',
                facecolor=fig.get_facecolor())
    plt.close(fig)
    return buf.getvalue()


