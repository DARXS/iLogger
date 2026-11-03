"""Exportações JSON e CSV tidy. Sem Qt."""

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


def export_json(runs, save_path: str, filter_settings: dict,
                setup_info: dict, observations: str):
    """Exporta todos os dados, estatísticas, fases e correlações em JSON."""
    try:
        from ...application.analysis import compute_correlation_matrix, compute_phase_summary_all

        data = {
            'version':          '6.0',
            'exported_at':      datetime.now().isoformat(),
            'filter_settings':  filter_settings,
            'setup_info':       setup_info or {},
            'observations':     observations or '',
            'runs':             [],
        }

        corr_matrices  = compute_correlation_matrix(runs, filter_settings)
        phase_summaries = compute_phase_summary_all(runs, filter_settings)

        for r in runs:
            r.apply_filters_and_recalculate(filter_settings)
            run_dict = {
                'file_name':   r.file_name,
                'file_path':   r.file_path,
                'n_samples':   int(r.time_s.size),
                'duration_s':  float(r.time_s[-1]) if r.time_s.size else 0,
                'stats':       {k: float(v) if isinstance(v, (int, float, np.floating))
                                else v for k, v in r.stats.items()},
                'extended_stats': {},
                'gear_ratios':   r.estimate_gear_ratios(),
                'phase_summary': phase_summaries.get(r.file_name, {}),
                'correlation_matrix': (
                    corr_matrices.get(r.file_name, pd.DataFrame())
                    .to_dict() if r.file_name in corr_matrices else {}
                ),
            }
            from ...domain.channels import KEY_VEL_KMH_FILT, KEY_RPM_FILT, KEY_ACEL_MS2_FILT, KEY_DIST_M
            for key in [KEY_VEL_KMH_FILT, KEY_RPM_FILT, KEY_ACEL_MS2_FILT, KEY_DIST_M]:
                run_dict['extended_stats'][key] = r.compute_extended_stats(key)
            data['runs'].append(run_dict)

        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)

    except Exception:
        log.exception("falha na exportação")
        raise


# ═════════════════════════════════════════════════════════════════════════════
#  CSV Tidy Export  (todos os canais, todas as runs, formato "long")
# ═════════════════════════════════════════════════════════════════════════════

def export_csv_tidy(runs, save_path: str, filter_settings: dict):
    """Exporta CSV organizado: uma coluna 'run' + todos os canais para cada run."""
    try:
        dfs = []
        for r in runs:
            r.apply_filters_and_recalculate(filter_settings)
            df = r.as_dataframe().copy()
            df.insert(0, 'Run', r.file_name)
            dfs.append(df)
        pd.concat(dfs, ignore_index=True).to_csv(save_path, index=False, float_format='%.6f')
    except Exception:
        log.exception("falha na exportação")
        raise
