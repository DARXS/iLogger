"""CLI headless: ``mangue-logger analyze runs/*.csv --excel out.xlsx`` (sem Qt)."""

from __future__ import annotations

import argparse
import json
import sys
from importlib import resources
from pathlib import Path

from . import __version__
from .application.analysis import compare_setups, full_analysis, generate_stats
from .application.loading import load_runs
from .application.ports import ReportContext
from .application.session import Session
from .domain.errors import MangueLoggerError
from .domain.models import VehicleProfile
from .infrastructure.exporters import get_exporter
from .infrastructure.readers.csv_reader import CsvRunReader


def _load_profile(path: str | None) -> VehicleProfile:
    if path:
        return VehicleProfile.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
    default = resources.files("mangue_logger").joinpath("profiles/baja_default.json")
    return VehicleProfile.from_dict(json.loads(default.read_text(encoding="utf-8")))


def _filter_dict(args: argparse.Namespace, fs_hz: float) -> dict:
    nyq = fs_hz / 2.0
    return {"type": args.filter, "butter_order": args.order, "butter_cutoff": args.cutoff_hz / nyq,
            "bessel_order": args.order, "bessel_cutoff": args.cutoff_hz / nyq,
            "cheby1_order": args.order, "cheby1_cutoff": args.cutoff_hz / nyq}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="mangue-logger", description=__doc__)
    p.add_argument("--version", action="version", version=f"mangue-logger {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("analyze", help="analisa runs e imprime resumo/insights; exporta relatórios")
    a.add_argument("files", nargs="+", help="CSVs (a 1ª run é a base de comparação)")
    a.add_argument("--profile", help="perfil do veículo (JSON)")
    a.add_argument("--filter", default="butterworth",
                   choices=["butterworth", "bessel", "chebyshev_type_i", "savitzky_golay", "median", "moving_average"])
    a.add_argument("--order", type=int, default=4)
    a.add_argument("--cutoff-hz", type=float, default=1.0)
    for flag in ("--excel", "--pdf", "--json", "--csv"):
        a.add_argument(flag)
    a.add_argument("--group-by", metavar="SETUP_KEY", help="compara grupos de runs por meta.setup[SETUP_KEY] (Welch)")
    a.add_argument("--metric", default="vel_max", help="métrica da comparação de grupos (ex.: vel_max, rpm_mean)")

    q = sub.add_parser("quality", help="só relatório de qualidade dos dados")
    q.add_argument("files", nargs="+")
    q.add_argument("--profile")
    sub.add_parser("gui", help="abre a interface gráfica")
    return p


def _cmd_quality(args: argparse.Namespace) -> int:
    profile = _load_profile(args.profile)
    reader, bad = CsvRunReader(profile.sensor), 0
    for f in args.files:
        try:
            run = reader.read(f)
        except MangueLoggerError as exc:
            print(f"✗ {f}: {exc}")
            bad += 1
            continue
        mark = "✓" if run.quality.ok else "⚠"
        print(f"{mark} {run.name}: {run.quality.n_samples} amostras, {run.duration_s:.1f} s")
        for w in run.quality.warnings:
            print(f"    - {w}")
        bad += 0 if run.quality.ok else 1
    return 1 if bad else 0


def _cmd_analyze(args: argparse.Namespace) -> int:
    profile = _load_profile(args.profile)
    sess = Session(profile)
    res = load_runs(args.files, CsvRunReader(profile.sensor), sess.processing, profile)
    for e in res.errors:
        print(f"✗ {e}", file=sys.stderr)
    if not res.runs:
        return 2
    sess.set_runs(res.runs)
    sess.set_filter(_filter_dict(args, profile.sensor.sample_rate_hz))
    fs = sess.filter_settings

    metrics, variations = generate_stats(res.runs, fs)
    print(metrics.T.to_string())
    print()
    if not variations.empty:
        print("Variação vs. base (%):")
        print(variations.T.to_string())
        print()
    out = full_analysis(res.runs, fs, profile)
    order = {"critical": 0, "warning": 1, "good": 2, "info": 3}
    for f in sorted(out["insights"], key=lambda i: order.get(i.level, 9)):
        print(f"[{f.level:<8}] {f.title}: {f.body}")

    if args.group_by:
        cmp = compare_setups(res.runs, fs, args.group_by, args.metric)
        print(f"\nComparação por {args.group_by!r} ({args.metric}):")
        for g, (m, s, n) in cmp["summary"].items():
            print(f"  {g}: {m:.2f} ± {s:.2f} (n={n})")
        for g, t in cmp["tests"].items():
            if t is None:
                print(f"  {cmp['baseline']} × {g}: repetições insuficientes (precisa de n≥2 por grupo)")
            else:
                print(f"  {cmp['baseline']} × {g}: Δ={t.diff:+.2f} IC95%[{t.ci95[0]:+.2f}, {t.ci95[1]:+.2f}] "
                      f"p={t.p:.4f} d={t.cohens_d:+.2f} {'(significativo)' if t.significant else '(n.s.)'}")

    ctx = ReportContext(runs=res.runs, filter_settings=fs)
    for ext, path in ((".xlsx", args.excel), (".pdf", args.pdf), (".json", args.json), (".csv", args.csv)):
        if path:
            get_exporter(ext).export(ctx, path)
            print(f"✓ {path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.cmd == "quality":
            return _cmd_quality(args)
        if args.cmd == "gui":
            from .presentation.app import main as gui_main
            return gui_main()
        return _cmd_analyze(args)
    except MangueLoggerError as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
