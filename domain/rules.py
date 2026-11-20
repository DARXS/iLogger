"""Motor de regras: transforma sinais processados em `Finding`s (insights).

Limiares vêm do `VehicleProfile.rules` — nada de números mágicos no código.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats as sp_stats

from . import channels as ch
from .analyzers.cvt import analyze_cvt, power_band_usage, robust_zscore_anomalies
from .analyzers.phases import detect_phases, phase_summary
from .models import Run, VehicleProfile
from .pipeline import ProcessedRun
from .stats import DISPLAY_LABELS, RunStats

INFO, WARN, CRIT, GOOD = "info", "warning", "critical", "good"


@dataclass(frozen=True)
class Finding:
    title: str
    body: str
    level: str = INFO
    metric: str = ""            # id ou rótulo de canal (usado só para achar a unidade na UI)
    value: float | None = None

    def __repr__(self) -> str:
        return f"[{self.level.upper()}] {self.title}: {self.body}"


def evaluate_run(run: Run, p: ProcessedRun, profile: VehicleProfile) -> list[Finding]:
    rules, nm, t = profile.rules, run.name, p.time_s
    vel, rpm, acel, dist = p.vel_kmh, p.rpm, p.acel, p.dist
    out: list[Finding] = []

    # Qualidade dos dados vem primeiro: tudo abaixo depende dela.
    for w in run.quality.warnings:
        out.append(Finding(f"Qualidade de dados — {nm}", w, WARN))
    if vel.size < 20:
        return out

    i = int(vel.argmax())
    out.append(Finding(f"Vel. máx — {nm}", f"Pico de {vel[i]:.1f} km/h em t={t[i]:.1f} s.", INFO, ch.VEL, float(vel[i])))

    if rpm.size and rpm.max() > 0:
        util = float(rpm.mean() / rpm.max())
        good = util > rules.rpm_util_good
        out.append(Finding(
            f"RPM — {nm}",
            f"Máx {rpm.max():.0f}, média {rpm.mean():.0f} ({util * 100:.0f}% do pico). "
            + ("Utilização adequada." if good else "RPM médio baixo — verifique a relação de transmissão/CVT."),
            GOOD if good else WARN, ch.RPM, float(rpm.max())))

    brake = acel < rules.hard_brake_ms2
    if brake.any():
        out.append(Finding(
            f"Frenagem brusca — {nm}",
            f"Desaceleração < {rules.hard_brake_ms2:g} m/s² em t≈{t[brake][0]:.1f} s "
            f"({int(brake.sum())} amostras). Verificar desgaste de pastilhas.", WARN, ch.ACEL))
    hard = acel > rules.hard_accel_ms2
    if hard.any():
        out.append(Finding(
            f"Aceleração violenta — {nm}",
            f"Aceleração > +{rules.hard_accel_ms2:g} m/s² em t≈{t[hard][0]:.1f} s "
            f"({int(hard.sum())} amostras). Risco de perda de tração.", WARN, ch.ACEL))

    anoms = robust_zscore_anomalies(vel, rules.anomaly_z)
    if anoms.size:
        pts = ", ".join(f"t={t[k]:.1f} s" for k in anoms[:3])
        out.append(Finding(f"Anomalias de velocidade — {nm}",
                           f"{anoms.size} ponto(s) anômalo(s) (MAD Z-score > {rules.anomaly_z:g}): "
                           f"{pts}{'…' if anoms.size > 3 else ''}.", WARN, ch.VEL))

    if rpm.size > 20:
        spikes = int((np.abs(np.diff(rpm)) > rules.rpm_spike).sum())
        if spikes > rules.rpm_spike_count:
            out.append(Finding(f"Instabilidade RPM — {nm}",
                               f"{spikes} variações abruptas (> {rules.rpm_spike:g} RPM/amostra). "
                               "Verificar CVT ou ignição.", CRIT, ch.RPM))

    if dist.size and t.size and t[-1] > 0:
        out.append(Finding(f"Distância — {nm}",
                           f"{dist[-1]:.1f} m em {t[-1]:.1f} s (vel. efetiva média: {dist[-1] / t[-1] * 3.6:.1f} km/h).",
                           INFO, ch.DIST, float(dist[-1])))

    if vel.size > 30:
        skw = float(sp_stats.skew(vel))
        if abs(skw) > 1.0:
            where = "concentrada em baixas velocidades" if skw > 0 else "concentrada em altas velocidades"
            hint = ("muito tempo em baixa velocidade (arrancadas/obstáculos)." if skw > 0
                    else "perfil de velocidade sustentada alta.")
            out.append(Finding(f"Distribuição de vel. — {nm}", f"Assimetria = {skw:+.2f}: {where}; {hint}",
                               WARN if abs(skw) > 2.0 else INFO))

    ph = phase_summary(detect_phases(acel, t, vel, dist, rules.phase_accel_thr, rules.phase_brake_thr), run.duration_s)
    if ph:
        a, b, s = ph["aceleração"], ph["frenagem"], ph["estabilização"]
        out.append(Finding(
            f"Fases de condução — {nm}",
            f"Aceleração {a['percent_%']:.0f}% ({a['n_eventos']} eventos) · "
            f"Frenagem {b['percent_%']:.0f}% ({b['n_eventos']} eventos) · Estabilização {s['percent_%']:.0f}%.",
            INFO if a["percent_%"] > 30 else WARN))

    cvt = analyze_cvt(vel, rpm, acel, rules.cvt_min_speed_kmh)
    if cvt and cvt.hold_cv_pct is not None and cvt.hold_rpm is not None:
        bad = cvt.hold_cv_pct > rules.cvt_hold_cv_warn_pct
        out.append(Finding(
            f"CVT — {nm}",
            f"Em aceleração a alta velocidade o RPM mediano é {cvt.hold_rpm:.0f} (CV {cvt.hold_cv_pct:.1f}%). "
            + ("RPM oscila bastante: o CVT não está segurando a rotação — revisar peso/mola/rampa."
               if bad else "RPM estável: o CVT mantém o motor numa rotação consistente.")
            + (f" RPM de saída ≈ {cvt.launch_rpm:.0f}." if cvt.launch_rpm else ""),
            WARN if bad else GOOD, ch.RPM, cvt.hold_rpm))

    if profile.power_band_rpm:
        pb = power_band_usage(rpm, acel, profile.power_band_rpm)
        if pb:
            lo, hi = pb.band
            extra = f" Em aceleração: {pb.pct_time_accelerating:.0f}%." if pb.pct_time_accelerating is not None else ""
            out.append(Finding(f"Faixa de potência — {nm}",
                               f"{pb.pct_time_total:.0f}% do tempo entre {lo:.0f} e {hi:.0f} RPM.{extra}",
                               GOOD if (pb.pct_time_accelerating or pb.pct_time_total) >= 50 else WARN,
                               ch.RPM, pb.pct_time_total))
    return out


_COMPARED = [("vel_max", "Vel. máx", "km/h", ch.VEL), ("rpm_max", "RPM máx", "RPM", ch.RPM),
             ("dist_total", "Distância", "m", ch.DIST), ("vel_mean", "Vel. média", "km/h", ch.VEL),
             ("acel_max", "Acel. máx", "m/s²", ch.ACEL)]


def compare_stats(base: RunStats, other: RunStats) -> list[Finding]:
    """Variação percentual entre duas runs, por id de métrica (não por texto de UI)."""
    out = []
    for mid, label, unit, channel in _COMPARED:
        assert mid in DISPLAY_LABELS
        bv, ov = base.metric(mid), other.metric(mid)
        denom = abs(bv) if bv else 1e-9
        dv = ov - bv
        pv = 100.0 * dv / denom
        if abs(pv) > 1.0:
            out.append(Finding(f"{label}: {base.name} × {other.name}",
                               f"{other.name}: {ov:.1f} {unit} vs {bv:.1f} {unit} ({dv:+.1f}, {pv:+.1f}%).",
                               GOOD if dv > 0 else WARN, channel, float(dv)))
    return out
