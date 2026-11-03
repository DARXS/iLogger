"""Exporters: cada formato implementa o Protocol `Exporter` e se registra aqui. Sem Qt."""

from __future__ import annotations

from ...application.analysis import generate_stats
from ...application.ports import Exporter, ReportContext
from .excel import export_excel
from .pdf import generate_pdf
from .tabular import export_csv_tidy, export_json


class ExcelExporter:
    name, extension = "Excel", ".xlsx"

    def export(self, ctx: ReportContext, path: str) -> None:
        metrics, variations = generate_stats(ctx.runs, ctx.filter_settings)
        export_excel(ctx.runs, path, metrics, variations, ctx.filter_settings, ctx.setup_info, ctx.observations)


class PdfExporter:
    name, extension = "PDF", ".pdf"

    def export(self, ctx: ReportContext, path: str) -> None:
        metrics, variations = generate_stats(ctx.runs, ctx.filter_settings)
        generate_pdf(path, ctx.setup_info, ctx.observations, ctx.filter_settings, metrics, variations,
                     ctx.figures, runs=ctx.runs)


class JsonExporter:
    name, extension = "JSON", ".json"

    def export(self, ctx: ReportContext, path: str) -> None:
        export_json(ctx.runs, path, ctx.filter_settings, ctx.setup_info, ctx.observations)


class CsvExporter:
    name, extension = "CSV", ".csv"

    def export(self, ctx: ReportContext, path: str) -> None:
        export_csv_tidy(ctx.runs, path, ctx.filter_settings)


_REGISTRY: dict[str, Exporter] = {e.extension: e for e in (ExcelExporter(), PdfExporter(), JsonExporter(), CsvExporter())}


def get_exporter(extension: str) -> Exporter:
    try:
        return _REGISTRY[extension.lower()]
    except KeyError:
        raise KeyError(f"nenhum exporter para {extension!r}; disponíveis: {sorted(_REGISTRY)}") from None


def available_exporters() -> list[Exporter]:
    return list(_REGISTRY.values())
