"""Exporters: cada formato implementa o Protocol `Exporter` (ReportModel → arquivo). Sem Qt."""

from __future__ import annotations

from ...application.ports import Exporter
from ...application.report_model import ReportModel


class ExcelExporter:
    name, extension = "Excel", ".xlsx"

    def export(self, model: ReportModel, path: str) -> None:
        from .excel import render_excel
        render_excel(model, path)


class PdfExporter:
    name, extension = "PDF", ".pdf"

    def export(self, model: ReportModel, path: str) -> None:
        from .pdf import render_pdf
        render_pdf(model, path)


class HtmlExporter:
    name, extension = "HTML", ".html"

    def export(self, model: ReportModel, path: str) -> None:
        from .html import render_html
        with open(path, "w", encoding="utf-8") as f:
            f.write(render_html(model))


class JsonExporter:
    name, extension = "JSON", ".json"

    def export(self, model: ReportModel, path: str) -> None:
        from .tabular import render_json
        render_json(model, path)


class CsvExporter:
    name, extension = "CSV", ".csv"

    def export(self, model: ReportModel, path: str) -> None:
        from .tabular import render_csv
        render_csv(model, path)


_REGISTRY: dict[str, Exporter] = {
    e.extension: e for e in (PdfExporter(), ExcelExporter(), HtmlExporter(), JsonExporter(), CsvExporter())
}


def get_exporter(extension: str) -> Exporter:
    try:
        return _REGISTRY[extension.lower()]
    except KeyError:
        raise KeyError(f"nenhum exporter para {extension!r}; disponíveis: {sorted(_REGISTRY)}") from None


def available_exporters() -> list[Exporter]:
    return list(_REGISTRY.values())
