# iLogger/services/report_service.py

import pandas as pd
import traceback
import tempfile
import os
from PyQt6.QtWidgets import QMessageBox
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak, PageTemplate, Frame, KeepInFrame
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.units import cm
from reportlab.lib import colors
from datetime import datetime

# --- Classe auxiliar para gerar o Sumário ---
class TocEntry:
    def __init__(self, text, level, bookmark_key):
        self.text = text
        self.level = level
        self.bookmark_key = bookmark_key

# --- Funções de Template para Cabeçalho e Rodapé ---
def _header(canvas, doc, content):
    canvas.saveState()
    canvas.setFont('Helvetica', 9)
    canvas.drawString(2 * cm, 28 * cm, content)
    canvas.line(2 * cm, 27.8 * cm, 19 * cm, 27.8 * cm)
    canvas.restoreState()

def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont('Helvetica', 9)
    canvas.drawCentredString(10.5 * cm, 1.5 * cm, f"Página {doc.page}")
    canvas.restoreState()

# --- Função Principal de Geração do PDF ---
def generate_pdf_report(save_path: str, setup_info: dict, observations: str, filter_settings: dict, metrics_df: pd.DataFrame, variations_df: pd.DataFrame, figures: dict):
    try:
        doc = SimpleDocTemplate(save_path,
                                rightMargin=2*cm, leftMargin=2*cm,
                                topMargin=3*cm, bottomMargin=3*cm)

        # Container para todos os elementos do PDF
        story = []
        toc_entries = []

        # Estilos de Texto
        styles = getSampleStyleSheet()
        style_title = ParagraphStyle(name='TitleStyle', fontSize=24, alignment=TA_CENTER, spaceAfter=1*cm, fontName='Helvetica-Bold')
        style_subtitle = ParagraphStyle(name='SubtitleStyle', fontSize=16, alignment=TA_CENTER, spaceAfter=0.5*cm, textColor=colors.darkgrey)
        style_h1 = ParagraphStyle(name='H1', fontSize=16, leading=20, spaceBefore=12, spaceAfter=12, fontName='Helvetica-Bold')
        style_h2 = ParagraphStyle(name='H2', fontSize=12, leading=16, spaceBefore=10, spaceAfter=6, textColor=colors.darkblue, fontName='Helvetica-Bold')
        style_body = ParagraphStyle(name='Body', fontSize=10, leading=14, alignment=TA_LEFT, spaceAfter=6)
        style_info = ParagraphStyle(name='Info', fontSize=10, leading=14, leftIndent=1*cm, spaceBefore=5)

        # --- 1. Capa ---
        story.append(Spacer(1, 5*cm))
        story.append(Paragraph("Relatório de Análise de Desempenho", style_title))
        story.append(Spacer(1, 1*cm))
        
        story.append(Paragraph(f"Data do Relatório: {datetime.now().strftime('%d/%m/%Y')}", style_subtitle))
        story.append(Spacer(1, 2*cm))

        setup_data = [[Paragraph(f"<b>{key}</b>", style_body), Paragraph(value, style_body)] for key, value in setup_info.items()]
        setup_table = Table(setup_data, colWidths=[4*cm, 10*cm])
        setup_table.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'LEFT'), ('VALIGN', (0,0), (-1,-1), 'TOP')]))
        story.append(setup_table)
        story.append(PageBreak())

        # --- 2. Sumário ---
        story.append(Paragraph("Sumário", style_h1))
        
        toc_placeholder = KeepInFrame(0, 0, [])
        story.append(toc_placeholder)
        story.append(PageBreak())

        # Adiciona o template com cabeçalho e rodapé para as páginas de conteúdo
        frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id='normal')
        template = PageTemplate(id='content', frames=[frame], onPage=lambda canvas, doc: _header(canvas, doc, "Relatório de Análise de Desempenho"), onPageEnd=_footer)
        doc.addPageTemplates([template])
        
        # --- 3. Introdução e Configurações ---
        key = "introducao"
        story.append(Paragraph(f'<a name="{key}"/>1. Introdução e Configurações', style_h1))
        toc_entries.append(TocEntry("1. Introdução e Configurações", 0, key))

        story.append(Paragraph("Configurações do Filtro de Análise", style_h2))
        filter_type = filter_settings.get('type', 'N/A').replace('_', ' ').title()
        story.append(Paragraph(f"<b>Tipo:</b> {filter_type}", style_info))
        for key, value in filter_settings.items():
            if key != 'type':
                story.append(Paragraph(f"<b>{key.replace('_', ' ').capitalize()}:</b> {value}", style_info))
        
        if observations and observations.strip():
            story.append(Paragraph("Observações Gerais", style_h2))
            story.append(Paragraph(observations.replace('\n', '<br/>'), style_body))
        story.append(PageBreak())

        # --- 4. Análise Estatística ---
        key = "estatisticas"
        story.append(Paragraph(f'<a name="{key}"/>2. Análise Estatística', style_h1))
        toc_entries.append(TocEntry("2. Análise Estatística", 0, key))

        story.append(Paragraph("Tabela de Métricas Principais", style_h2))
        metrics_header = [Paragraph(f'<b>{col}</b>', style_body) for col in metrics_df.columns]
        metrics_data = [metrics_header] + metrics_df.round(2).values.tolist()
        metrics_table = Table(metrics_data, hAlign='LEFT', repeatRows=1)
        metrics_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.lightblue), ('TEXTCOLOR', (0,0), (-1,0), colors.darkblue),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('GRID', (0,0), (-1,-1), 1, colors.grey), ('FONTNAME', (0,0), (-1,-1), 'Helvetica')
        ]))
        story.append(metrics_table)
        story.append(Spacer(1, 1*cm))

        story.append(Paragraph("Variações Percentuais (%)", style_h2))
        variations_header = [Paragraph(f'<b>{col}</b>', style_body) for col in variations_df.columns]
        variations_data = [variations_header] + variations_df.round(2).values.tolist()
        variations_table = Table(variations_data, hAlign='LEFT', repeatRows=1)
        variations_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.lightgreen), ('TEXTCOLOR', (0,0), (-1,0), colors.darkgreen),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('GRID', (0,0), (-1,-1), 1, colors.grey),
        ]))
        story.append(variations_table)
        story.append(PageBreak())

        # --- 5. Análise Gráfica ---
        key = "graficos"
        story.append(Paragraph(f'<a name="{key}"/>3. Análise Gráfica', style_h1))
        toc_entries.append(TocEntry("3. Análise Gráfica", 0, key))
        
        with tempfile.TemporaryDirectory() as temp_dir:
            plot_order = ['comparativo', 'rotacao', 'velocidade', 'aceleracao', 'distancia', 'relacao']
            for i, p_key in enumerate(plot_order):
                if p_key in figures and figures[p_key] is not None:
                    # figures[p_key] agora são bytes
                    image_bytes = figures[p_key]
                    temp_image_path = os.path.join(temp_dir, f"{p_key}.png")
                    with open(temp_image_path, 'wb') as f_img:
                        f_img.write(image_bytes)
                    
                    chart_title = p_key.replace('_', ' ').capitalize()
                    story.append(Paragraph(chart_title, style_h2))
                    
                    img = Image(temp_image_path, width=16*cm, height=10*cm, kind='proportional')
                    story.append(img)
                    story.append(Spacer(1, 1*cm))

        # --- Construção do Sumário ---
        toc_content = []
        for entry in toc_entries:
            style = ParagraphStyle(name=f'TOC{entry.level}', leftIndent=entry.level*cm, fontSize=11, spaceAfter=4)
            link = f'<a href="#{entry.bookmark_key}">{entry.text}</a>'
            toc_content.append(Paragraph(link, style))
        toc_placeholder.contents = toc_content
        
        # Constrói o PDF
        doc.build(story)
        QMessageBox.information(None, "Sucesso", f"Relatório PDF salvo com sucesso em:\n{save_path}")

    except Exception as e:
        error_details = traceback.format_exc()
        QMessageBox.critical(None, "Erro ao Gerar PDF", f"Ocorreu um erro inesperado: {e}\n\nDetalhes:\n{error_details}")