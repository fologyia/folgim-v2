import io
from datetime import datetime

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable, KeepTogether, PageBreak, Paragraph,
    SimpleDocTemplate, Spacer, Table, TableStyle,
)
from reportlab.graphics import renderPDF

from config import NOTA_MINIMA, SEQUENCIA_CRITICA_MIN
from data.analysis import (
    agrupar_por_semana, classificar_risco, detectar_tendencia, gerar_diagnostico,
)
from utils import coluna_criterio, coluna_uc, nota_formatada
from pdf.styles import (
    _C, _MARGEM, _LARGURA,
    _S_SEC, _S_BODY, _S_BODY_C, _S_BOLD_C, _S_OBS,
    _S_DIAG, _S_DIAG_TIT, _S_LEG3,
    _S_CAPA_NOME, _S_CAPA_DT, _S_ALERTA_IN,
    _S_REC_OBS, _S_RECOM_TIT, _ps,
)
from pdf.helpers import (
    _draw_page_frame, _secao_titulo,
    _cor_nota, _cor_nota_bg, _kpi_card,
    _barra_progresso, _pdf_radar_chart, _pdf_bar_bimestre,
    _pdf_line_chart_evolucao, _pdf_freq_calendar,
    _pdf_line_turma, _pdf_barra_risco,
    _gerar_recomendacoes, _tabela_recomendacoes,
)


def gerar_relatorio_ia_pdf(
    turma: str,
    resumo_turma: str,
    alertas_turma: list[str],
    analise_alunos: list[dict],
    n_critico: int, n_atencao: int, n_adequado: int, n_excelente: int,
    media_geral: float,
) -> bytes:
    """Gera PDF com o relatório completo da análise pedagógica da IA."""
    emitido = datetime.now().strftime("%d/%m/%Y às %H:%M")
    buffer  = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=_MARGEM, rightMargin=_MARGEM,
        topMargin=1.6 * cm, bottomMargin=1.4 * cm,
    )

    def _cb(canv, d):
        _draw_page_frame(canv, d, f"Análise IA — {turma}", turma, emitido)

    story = []

    # ── CABEÇALHO ──────────────────────────────────────────────────────────────
    capa_data = [[
        Paragraph(
            f"<b><font size='16' color='#00539F'>Relatório de Inteligência Pedagógica</font></b><br/>"
            f"<font size='9' color='#475569'>Turma: {turma}</font>",
            _S_CAPA_NOME,
        ),
        Paragraph(
            f"<font size='8' color='#475569'>Gerado em {emitido}<br/>Modelo: IA Pedagógica SENAI</font>",
            _S_CAPA_DT,
        ),
    ]]
    capa_tbl = Table(capa_data, colWidths=[_LARGURA * 0.62, _LARGURA * 0.38])
    capa_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _C["azul_claro"]),
        ("ROWPADDING", (0, 0), (-1, -1), 14),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW",  (0, 0), (-1, -1), 2.5, _C["azul"]),
        ("LINEBEFORE", (0, 0), (0, -1),  3,   _C["roxo"]),
    ]))
    story += [Spacer(1, 0.3 * cm), capa_tbl, Spacer(1, 0.5 * cm)]

    # ── KPIs DA TURMA ──────────────────────────────────────────────────────────
    story.append(_secao_titulo("Panorama da Turma"))
    story.append(Spacer(1, 0.3 * cm))
    total = n_critico + n_atencao + n_adequado + n_excelente
    pct_aprov = round((n_adequado + n_excelente) / total * 100) if total > 0 else 0
    kpi_row = [[
        _kpi_card(str(total),         "Total Alunos",      _C["azul"]),
        _kpi_card(f"{media_geral:.1f}","Média Geral",       _C["azul"]),
        _kpi_card(str(n_critico),      "Risco Crítico",     _C["verm"]),
        _kpi_card(str(n_atencao),      "Em Atenção",        _C["amarelo"]),
        _kpi_card(str(n_adequado),     "Adequados",         _C["verde"]),
        _kpi_card(f"{pct_aprov}%",     "Taxa Aprovação",    _C["verde"] if pct_aprov >= 70 else _C["verm"]),
    ]]
    kpi_tbl = Table(kpi_row, colWidths=[3.1 * cm] * 6, hAlign="CENTER")
    kpi_tbl.setStyle(TableStyle([
        ("ALIGN",  (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
    ]))
    story += [kpi_tbl, Spacer(1, 0.5 * cm)]

    # ── RESUMO GERAL ───────────────────────────────────────────────────────────
    story.append(_secao_titulo("Análise Geral da Turma"))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(resumo_turma, _S_DIAG))
    story.append(Spacer(1, 0.4 * cm))

    # ── ALERTAS ────────────────────────────────────────────────────────────────
    if alertas_turma:
        alerta_rows = [[
            Paragraph("<b>Alertas Identificados</b>", _S_RECOM_TIT), ""
        ]]
        for i, alerta in enumerate(alertas_turma, 1):
            alerta_rows.append([
                Paragraph(f"⚠️", _S_BODY_C),
                Paragraph(alerta, _S_DIAG),
            ])
        a_tbl = Table(alerta_rows, colWidths=[0.8 * cm, _LARGURA - 0.8 * cm])
        a_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0), _C["amarelo"]),
            ("SPAN",          (0, 0), (-1, 0)),
            ("TOPPADDING",    (0, 0), (-1, 0), 7),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 7),
            ("LEFTPADDING",   (0, 0), (-1, 0), 10),
            ("FONTSIZE",      (0, 1), (-1, -1), 8),
            ("GRID",          (0, 1), (-1, -1), 0.25, _C["cinza2"]),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING",    (0, 1), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
            ("LEFTPADDING",   (0, 1), (-1, -1), 8),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), [_C["branco"], _C["amar_claro"]]),
        ]))
        story += [a_tbl, Spacer(1, 0.5 * cm)]

    # ── ANÁLISE INDIVIDUAL POR ALUNO ───────────────────────────────────────────
    story.append(KeepTogether([
        _secao_titulo("Insights Pedagógicos Individuais"),
        Spacer(1, 0.4 * cm),
    ]))

    _cor_risco = {
        "critico": _C["verm"], "atencao": _C["amarelo"],
        "adequado": _C["verde"], "excelente": _C["roxo"],
    }

    for item in analise_alunos:
        nome       = item.get("aluno", "—")
        diagn      = item.get("diagnostico", "—")
        forte      = item.get("ponto_forte", "—")
        fraco      = item.get("ponto_fraco", "—")
        acao       = item.get("acao_docente", "—")

        # Cabeçalho do aluno
        header_data = [[Paragraph(
            f"<b><font color='white'>{nome}</font></b>",
            _ps(f"aluno_h_{nome[:10]}", fontName="Helvetica-Bold", fontSize=10, textColor=_C["branco"], leading=14),
        )]]
        header_tbl = Table(header_data, colWidths=[_LARGURA])
        header_tbl.setStyle(TableStyle([
            ("BACKGROUND",  (0, 0), (-1, -1), _C["azul"]),
            ("ROWPADDING",  (0, 0), (-1, -1), 8),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ]))

        # Corpo: diagnóstico + ponto forte / fraco + ação
        corpo_rows = [
            [Paragraph("<b>Diagnóstico</b>", _S_DIAG_TIT),
             Paragraph(diagn, _S_DIAG)],
            [Paragraph("<b>Ponto Forte</b>", _ps("pf_tit", fontName="Helvetica-Bold", fontSize=8,
                        textColor=_C["verde"], leading=11)),
             Paragraph(forte, _S_DIAG)],
            [Paragraph("<b>Ponto Fraco</b>", _ps("pfr_tit", fontName="Helvetica-Bold", fontSize=8,
                        textColor=_C["verm"], leading=11)),
             Paragraph(fraco, _S_DIAG)],
            [Paragraph("<b>Ação Docente</b>", _ps("ac_tit", fontName="Helvetica-Bold", fontSize=8,
                        textColor=colors.HexColor("#B45309"), leading=11)),
             Paragraph(acao, _ps("acao_body", fontName="Helvetica-Bold", fontSize=8,
                                  textColor=_C["texto"], leading=12))],
        ]
        corpo_tbl = Table(corpo_rows, colWidths=[2.6 * cm, _LARGURA - 2.6 * cm])
        corpo_tbl.setStyle(TableStyle([
            ("FONTSIZE",      (0, 0), (-1, -1), 8),
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ("GRID",          (0, 0), (-1, -1), 0.25, _C["cinza2"]),
            ("TOPPADDING",    (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING",   (0, 0), (-1, -1), 8),
            ("BACKGROUND",    (0, 0), (0, -1), _C["cinza"]),
            ("BACKGROUND",    (0, 3), (-1, 3), _C["amar_claro"]),
        ]))

        story.append(KeepTogether([header_tbl, corpo_tbl, Spacer(1, 0.35 * cm)]))

    doc.build(story, onFirstPage=_cb, onLaterPages=_cb)
    buffer.seek(0)
    return buffer.read()


def gerar_relatorio_turma_pdf(
    turma: str,
    perfil: pd.DataFrame,
    df_turma: pd.DataFrame,
    saude: dict | None = None,
    df_freq: pd.DataFrame | None = None,
) -> bytes:
    """Relatório completo de desempenho da turma (panorama, saúde, critérios,
    vetores, UCs, evolução temporal, ranking e alunos em risco)."""
    emitido = datetime.now().strftime("%d/%m/%Y às %H:%M")
    buffer  = io.BytesIO()
    saude   = saude or {}

    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=_MARGEM, rightMargin=_MARGEM,
        topMargin=1.6 * cm, bottomMargin=1.4 * cm,
    )

    def _cb(canv, d):
        _draw_page_frame(canv, d, f"Relatório da Turma — {turma}", turma, emitido)

    # ── Métricas base ──────────────────────────────────────────────────────────
    n_critico   = int((perfil["Risco"] == "critico").sum())
    n_atencao   = int((perfil["Risco"] == "atencao").sum())
    n_adequado  = int((perfil["Risco"] == "adequado").sum())
    n_excelente = int((perfil["Risco"] == "excelente").sum())
    total       = len(perfil)
    media_geral = float(df_turma["Nota"].mean()) if not df_turma.empty else 0.0
    pct_aprov   = round((n_adequado + n_excelente) / total * 100) if total > 0 else 0

    col_crit = coluna_criterio(df_turma)
    col_uc   = coluna_uc(df_turma)

    story = []

    # ── CAPA ───────────────────────────────────────────────────────────────────
    capa_data = [[
        Paragraph(
            f"<b><font size='16' color='#00539F'>Relatório de Desempenho da Turma</font></b><br/>"
            f"<font size='9' color='#475569'>Turma: {turma}</font>",
            _S_CAPA_NOME,
        ),
        Paragraph(
            f"<font size='8' color='#475569'>Gerado em {emitido}<br/>SENAI · Painel Docente</font>",
            _S_CAPA_DT,
        ),
    ]]
    capa_tbl = Table(capa_data, colWidths=[_LARGURA * 0.62, _LARGURA * 0.38])
    capa_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _C["azul_claro"]),
        ("ROWPADDING", (0, 0), (-1, -1), 14),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW",  (0, 0), (-1, -1), 2.5, _C["azul"]),
        ("LINEBEFORE", (0, 0), (0, -1),  3,   _C["azul"]),
    ]))
    story += [Spacer(1, 0.3 * cm), capa_tbl, Spacer(1, 0.5 * cm)]

    # ── PANORAMA (KPIs) ────────────────────────────────────────────────────────
    story.append(_secao_titulo("Panorama Geral"))
    story.append(Spacer(1, 0.3 * cm))
    kpi_row = [[
        _kpi_card(str(total),          "Total Alunos",    _C["azul"]),
        _kpi_card(f"{media_geral:.1f}", "Média Geral",     _cor_nota(media_geral)),
        _kpi_card(f"{pct_aprov}%",      "Taxa Aprovação",  _C["verde"] if pct_aprov >= 70 else _C["verm"]),
        _kpi_card(str(n_critico),       "Risco Crítico",   _C["verm"]),
        _kpi_card(str(n_atencao),       "Em Atenção",      _C["amarelo"]),
        _kpi_card(str(n_adequado + n_excelente), "Aprovados", _C["verde"]),
    ]]
    kpi_tbl = Table(kpi_row, colWidths=[_LARGURA / 6] * 6, hAlign="CENTER")
    kpi_tbl.setStyle(TableStyle([
        ("ALIGN",  (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story += [kpi_tbl, Spacer(1, 0.45 * cm)]

    # ── SAÚDE DA TURMA ─────────────────────────────────────────────────────────
    if saude:
        crit_prob = str(saude.get("criterio_mais_problematico") or "—")[:22]
        pct_crit  = saude.get("pct_abaixo_criterio", 0)
        vet_fraco = str(saude.get("vetor_mais_fraco") or "—").split(" (")[0]
        med_vet   = saude.get("media_vetor_mais_fraco")
        tend      = saude.get("tendencia_coletiva", "indefinida")
        tend_txt  = {"melhora": "▲ Melhora", "queda": "▼ Queda",
                     "estável": "● Estável", "indefinida": "— Indefinida"}.get(tend, "—")
        cor_tend  = (_C["verde"] if tend == "melhora"
                     else _C["verm"] if tend == "queda" else _C["amarelo"])

        s_row = [[
            _kpi_card(f"{saude.get('pct_aprovados', 0):.0f}%", "% Aprovados",
                      _C["verde"] if saude.get("pct_aprovados", 0) >= 70 else _C["verm"], largura=_LARGURA / 4),
            _kpi_card(f"{pct_crit:.0f}%", f"+ Crítico: {crit_prob}",
                      _C["verm"] if pct_crit >= 50 else _C["amarelo"], largura=_LARGURA / 4),
            _kpi_card(f"{vet_fraco} {med_vet:.1f}" if med_vet is not None else vet_fraco,
                      "Vetor + Fraco", _C["amarelo"], largura=_LARGURA / 4),
            _kpi_card(tend_txt, "Tendência Coletiva", cor_tend, largura=_LARGURA / 4),
        ]]
        s_tbl = Table(s_row, colWidths=[_LARGURA / 4] * 4, hAlign="CENTER")
        s_tbl.setStyle(TableStyle([
            ("ALIGN",  (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING",  (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(KeepTogether([
            _secao_titulo("Saúde da Turma"),
            Spacer(1, 0.3 * cm),
            s_tbl,
            Spacer(1, 0.3 * cm),
        ]))

        # Alerta pedagógico: critério com >=50% dos alunos abaixo do mínimo
        criticos_sis = [c for c in saude.get("criterios_sistemicos", [])
                        if c.get("pct_abaixo", 0) >= 50]
        if criticos_sis:
            nomes = ", ".join(str(c.get(saude.get("col_crit", col_crit), ""))[:30]
                              for c in criticos_sis[:3])
            alerta_data = [[Paragraph(
                f"<b><font color='white' size='9'>ALERTA PEDAGÓGICO — dificuldade coletiva</font></b><br/>"
                f"<font color='white' size='7.5'>{len(criticos_sis)} critério(s) com 50%+ dos alunos com média abaixo de "
                f"{NOTA_MINIMA:.0f},0: {nomes}. Sugere revisão de metodologia/conteúdo, não apenas reforço individual.</font>",
                _S_ALERTA_IN)]]
            alerta_tbl = Table(alerta_data, colWidths=[_LARGURA])
            alerta_tbl.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), _C["verm"]),
                ("ROWPADDING", (0, 0), (-1, -1), 9),
                ("LEFTPADDING",(0, 0), (-1, -1), 14),
                ("LINEBEFORE", (0, 0), (0, -1),  5, colors.HexColor("#7F1D1D")),
            ]))
            story += [alerta_tbl, Spacer(1, 0.4 * cm)]
        else:
            story.append(Spacer(1, 0.15 * cm))

    # ── DISTRIBUIÇÃO DE RISCO ──────────────────────────────────────────────────
    story.append(KeepTogether([
        _secao_titulo("Distribuição de Risco"),
        Spacer(1, 0.3 * cm),
        _pdf_barra_risco(n_critico, n_atencao, n_adequado, n_excelente,
                         largura=_LARGURA, altura=58),
        Spacer(1, 0.4 * cm),
    ]))

    # ── EVOLUÇÃO TEMPORAL DA TURMA ─────────────────────────────────────────────
    sem_df = (
        agrupar_por_semana(df_turma)
        if (not df_turma.empty and "Data" in df_turma.columns and "Nota" in df_turma.columns)
        else pd.DataFrame()
    )
    if not sem_df.empty and len(sem_df) >= 2:
        story.append(KeepTogether([
            _secao_titulo("Evolução Temporal da Turma"),
            Spacer(1, 0.3 * cm),
            _pdf_line_turma(sem_df, largura=_LARGURA, altura=180),
            Spacer(1, 0.4 * cm),
        ]))

    # ── CRITÉRIOS SISTÊMICOS ───────────────────────────────────────────────────
    crit_sis = saude.get("criterios_sistemicos", []) if saude else []
    if crit_sis:
        col_key = saude.get("col_crit", col_crit)
        header = [Paragraph("<b>Critério</b>", _S_BOLD_C),
                  Paragraph("<b>% Abaixo do Mínimo</b>", _S_BOLD_C),
                  Paragraph("<b>Distribuição</b>", _S_BOLD_C)]
        rows  = [header]
        style = [
            ("BACKGROUND", (0, 0), (-1, 0), _C["azul"]),
            ("TEXTCOLOR",  (0, 0), (-1, 0), _C["branco"]),
            ("FONTSIZE",   (0, 0), (-1, -1), 8),
            ("ROWPADDING", (0, 0), (-1, -1), 5),
            ("GRID",       (0, 0), (-1, -1), 0.25, _C["cinza2"]),
            ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN",      (1, 0), (2, -1), "CENTER"),
        ]
        for i, c in enumerate(crit_sis, start=1):
            pct = float(c.get("pct_abaixo", 0))
            cor = _C["verm"] if pct >= 50 else (_C["amarelo"] if pct >= 25 else _C["verde"])
            rows.append([
                Paragraph(str(c.get(col_key, "")).replace("Leórica", "Teórica"), _S_BODY),
                Paragraph(f"<b><font color='#{cor.hexval()}'>{pct:.0f}%</font></b>", _S_BOLD_C),
                _barra_progresso(min(pct / 10.0, 10.0)),
            ])
            if i % 2 == 0:
                style.append(("BACKGROUND", (0, i), (-1, i), _C["cinza"]))
        sis_tbl = Table(rows, colWidths=[8.0 * cm, 3.0 * cm, _LARGURA - 11.0 * cm])
        sis_tbl.setStyle(TableStyle(style))
        story.append(KeepTogether([
            _secao_titulo("Critérios Sistêmicos — Dificuldade Coletiva"),
            Spacer(1, 0.2 * cm),
            Paragraph("Percentual de alunos cuja média no critério ficou abaixo do mínimo (não uma nota isolada) — distingue dificuldade coletiva de tropeços individuais.", _S_OBS),
            Spacer(1, 0.2 * cm),
            sis_tbl,
            Spacer(1, 0.4 * cm),
        ]))

    # ── DESEMPENHO POR CRITÉRIO (média da turma) ───────────────────────────────
    if col_crit in df_turma.columns and df_turma[col_crit].nunique() >= 2:
        med_crit = df_turma.groupby(col_crit)["Nota"].mean().sort_values(ascending=False)
        header = [Paragraph("<b>Critério</b>", _S_BOLD_C),
                  Paragraph("<b>Média</b>", _S_BOLD_C),
                  Paragraph("<b>Desempenho</b>", _S_BOLD_C),
                  Paragraph("<b>Situação</b>", _S_BOLD_C)]
        rows  = [header]
        style = [
            ("BACKGROUND", (0, 0), (-1, 0), _C["azul"]),
            ("TEXTCOLOR",  (0, 0), (-1, 0), _C["branco"]),
            ("FONTSIZE",   (0, 0), (-1, -1), 8),
            ("ROWPADDING", (0, 0), (-1, -1), 5),
            ("GRID",       (0, 0), (-1, -1), 0.25, _C["cinza2"]),
            ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN",      (1, 0), (3, -1), "CENTER"),
        ]
        for i, (crit, m) in enumerate(med_crit.items(), start=1):
            sit = "Adequado" if m >= NOTA_MINIMA else "Crítico"
            cor_sit = _C["verde"] if m >= NOTA_MINIMA else _C["verm"]
            rows.append([
                Paragraph(str(crit).replace("Leórica", "Teórica"), _S_BODY),
                Paragraph(f"<b><font color='#{_cor_nota(m).hexval()}'>{m:.1f}</font></b>", _S_BOLD_C),
                _barra_progresso(m),
                Paragraph(f"<font color='#{cor_sit.hexval()}'><b>{sit}</b></font>", _S_BOLD_C),
            ])
            if i % 2 == 0:
                style.append(("BACKGROUND", (0, i), (0, i), _C["cinza"]))
                style.append(("BACKGROUND", (3, i), (3, i), _C["cinza"]))
        crit_tbl = Table(rows, colWidths=[7.5 * cm, 1.5 * cm, 6.0 * cm, 2.4 * cm])
        crit_tbl.setStyle(TableStyle(style))
        story.append(KeepTogether([
            _secao_titulo("Desempenho por Critério"),
            Spacer(1, 0.2 * cm),
            crit_tbl,
            Spacer(1, 0.4 * cm),
        ]))

    # ── DESEMPENHO POR VETOR ───────────────────────────────────────────────────
    if "Vetor (Peso)" in df_turma.columns and df_turma["Vetor (Peso)"].nunique() >= 1:
        med_vet = df_turma.groupby("Vetor (Peso)")["Nota"].mean().sort_values(ascending=False)
        cards = []
        for v, m in med_vet.items():
            cards.append(_kpi_card(f"{m:.1f}", str(v)[:18], _cor_nota(m), largura=_LARGURA / max(len(med_vet), 1)))
        v_tbl = Table([cards], colWidths=[_LARGURA / max(len(med_vet), 1)] * len(med_vet), hAlign="CENTER")
        v_tbl.setStyle(TableStyle([
            ("ALIGN",  (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING",  (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(KeepTogether([
            _secao_titulo("Desempenho por Vetor"),
            Spacer(1, 0.3 * cm),
            v_tbl,
            Spacer(1, 0.4 * cm),
        ]))

    # ── DESEMPENHO POR UNIDADE CURRICULAR ──────────────────────────────────────
    if col_uc in df_turma.columns and df_turma[col_uc].nunique() >= 2:
        med_uc = df_turma.groupby(col_uc)["Nota"].mean().sort_values(ascending=False)
        header = [Paragraph("<b>Unidade Curricular</b>", _S_BOLD_C),
                  Paragraph("<b>Média</b>", _S_BOLD_C),
                  Paragraph("<b>Desempenho</b>", _S_BOLD_C)]
        rows  = [header]
        style = [
            ("BACKGROUND", (0, 0), (-1, 0), _C["azul"]),
            ("TEXTCOLOR",  (0, 0), (-1, 0), _C["branco"]),
            ("FONTSIZE",   (0, 0), (-1, -1), 8),
            ("ROWPADDING", (0, 0), (-1, -1), 5),
            ("GRID",       (0, 0), (-1, -1), 0.25, _C["cinza2"]),
            ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN",      (1, 0), (2, -1), "CENTER"),
        ]
        for i, (uc, m) in enumerate(med_uc.items(), start=1):
            rows.append([
                Paragraph(str(uc), _S_BODY),
                Paragraph(f"<b><font color='#{_cor_nota(m).hexval()}'>{m:.1f}</font></b>", _S_BOLD_C),
                _barra_progresso(m),
            ])
            if i % 2 == 0:
                style.append(("BACKGROUND", (0, i), (-1, i), _C["cinza"]))
        uc_tbl = Table(rows, colWidths=[9.0 * cm, 1.5 * cm, _LARGURA - 10.5 * cm])
        uc_tbl.setStyle(TableStyle(style))
        story.append(KeepTogether([
            _secao_titulo("Desempenho por Unidade Curricular"),
            Spacer(1, 0.2 * cm),
            uc_tbl,
            Spacer(1, 0.4 * cm),
        ]))

    # ── RANKING COMPLETO DE ALUNOS ─────────────────────────────────────────────
    _risco_lbl = {"critico": "Crítico", "atencao": "Atenção",
                  "adequado": "Adequado", "excelente": "Excelente"}
    _risco_cor = {"critico": _C["verm"], "atencao": _C["amarelo"],
                  "adequado": _C["verde"], "excelente": _C["roxo"]}
    _tend_lbl  = {"melhora": "▲ Melhora", "queda": "▼ Queda",
                  "estável": "● Estável", "indefinida": "—"}

    rank = perfil.sort_values("Média", ascending=False).reset_index(drop=True)
    header = [Paragraph("<b>#</b>", _S_BOLD_C),
              Paragraph("<b>Aluno</b>", _S_BOLD_C),
              Paragraph("<b>Média</b>", _S_BOLD_C),
              Paragraph("<b>Críticas</b>", _S_BOLD_C),
              Paragraph("<b>Aval.</b>", _S_BOLD_C),
              Paragraph("<b>Tendência</b>", _S_BOLD_C),
              Paragraph("<b>Situação</b>", _S_BOLD_C)]
    rows  = [header]
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), _C["azul"]),
        ("TEXTCOLOR",  (0, 0), (-1, 0), _C["branco"]),
        ("FONTSIZE",   (0, 0), (-1, -1), 7.5),
        ("ROWPADDING", (0, 0), (-1, -1), 4),
        ("GRID",       (0, 0), (-1, -1), 0.25, _C["cinza2"]),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN",      (0, 0), (0, -1), "CENTER"),
        ("ALIGN",      (2, 0), (-1, -1), "CENTER"),
        ("ALIGN",      (1, 0), (1, -1), "LEFT"),
    ]
    for i, row in rank.iterrows():
        pos    = i + 1
        risco  = row["Risco"]
        cor_r  = _risco_cor.get(risco, _C["cinza4"])
        m      = float(row["Média"])
        tend_r = row.get("Tendencia", "indefinida")
        rows.append([
            Paragraph(str(pos), _S_BODY_C),
            Paragraph(str(row["Aluno"]), _S_BODY),
            Paragraph(f"<b><font color='#{_cor_nota(m).hexval()}'>{m:.1f}</font></b>", _S_BOLD_C),
            Paragraph(str(int(row["Notas_Baixas"])), _S_BODY_C),
            Paragraph(str(int(row["Total"])), _S_BODY_C),
            Paragraph(_tend_lbl.get(tend_r, "—"), _S_BODY_C),
            Paragraph(f"<font color='#{cor_r.hexval()}'><b>{_risco_lbl.get(risco, '—')}</b></font>", _S_BOLD_C),
        ])
        if pos % 2 == 0:
            style.append(("BACKGROUND", (0, pos), (-1, pos), _C["cinza"]))
    rank_tbl = Table(
        rows,
        colWidths=[0.9 * cm, _LARGURA - 9.9 * cm, 1.6 * cm, 1.6 * cm, 1.4 * cm, 2.0 * cm, 2.4 * cm],
        repeatRows=1,
    )
    rank_tbl.setStyle(TableStyle(style))
    story.append(_secao_titulo("Ranking Completo de Alunos"))
    story.append(Spacer(1, 0.2 * cm))
    story.append(rank_tbl)
    story.append(Spacer(1, 0.4 * cm))

    # ── ALUNOS QUE REQUEREM ATENÇÃO ────────────────────────────────────────────
    em_risco = rank[rank["Risco"].isin(["critico", "atencao"])]
    if not em_risco.empty:
        header = [Paragraph("<b>Aluno</b>", _S_BOLD_C),
                  Paragraph("<b>Média</b>", _S_BOLD_C),
                  Paragraph("<b>Notas Críticas</b>", _S_BOLD_C),
                  Paragraph("<b>Seq. Crítica</b>", _S_BOLD_C),
                  Paragraph("<b>Situação</b>", _S_BOLD_C)]
        rows  = [header]
        style = [
            ("BACKGROUND", (0, 0), (-1, 0), _C["verm"]),
            ("TEXTCOLOR",  (0, 0), (-1, 0), _C["branco"]),
            ("FONTSIZE",   (0, 0), (-1, -1), 8),
            ("ROWPADDING", (0, 0), (-1, -1), 5),
            ("GRID",       (0, 0), (-1, -1), 0.25, _C["cinza2"]),
            ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN",      (1, 0), (-1, -1), "CENTER"),
            ("ALIGN",      (0, 0), (0, -1), "LEFT"),
        ]
        for i, (_, row) in enumerate(em_risco.iterrows(), start=1):
            risco = row["Risco"]
            cor_r = _risco_cor.get(risco, _C["cinza4"])
            m     = float(row["Média"])
            seq_c = int(row["Seq_Critica"])
            rows.append([
                Paragraph(str(row["Aluno"]), _S_BODY),
                Paragraph(f"<b><font color='#{_cor_nota(m).hexval()}'>{m:.1f}</font></b>", _S_BOLD_C),
                Paragraph(str(int(row["Notas_Baixas"])), _S_BODY_C),
                Paragraph(f"<b><font color='#{(_C['verm'] if seq_c >= SEQUENCIA_CRITICA_MIN else _C['texto']).hexval()}'>{seq_c}</font></b>", _S_BOLD_C),
                Paragraph(f"<font color='#{cor_r.hexval()}'><b>{_risco_lbl.get(risco, '—')}</b></font>", _S_BOLD_C),
            ])
            if i % 2 == 0:
                style.append(("BACKGROUND", (0, i), (-1, i), _C["cinza"]))
        risco_tbl = Table(rows, colWidths=[_LARGURA - 11.0 * cm, 1.8 * cm, 3.2 * cm, 3.0 * cm, 3.0 * cm])
        risco_tbl.setStyle(TableStyle(style))
        story.append(KeepTogether([
            _secao_titulo("Alunos que Requerem Atenção"),
            Spacer(1, 0.2 * cm),
            Paragraph("Alunos classificados como Crítico ou Em Atenção — priorizar acompanhamento individualizado.", _S_OBS),
            Spacer(1, 0.2 * cm),
        ]))
        story.append(risco_tbl)
        story.append(Spacer(1, 0.3 * cm))

    doc.build(story, onFirstPage=_cb, onLaterPages=_cb)
    buffer.seek(0)
    return buffer.read()


def gerar_boletim_pdf(
    aluno: str, turma: str, df_al: pd.DataFrame,
    media_al: float, media_pond: float, media_turma: float,
    notas_baixas: int, total_avals: int, delta: float,
    bimestres: pd.DataFrame, seq_critica: int, comparar_turma: bool,
    df_turma: pd.DataFrame, df_rec_aluno: pd.DataFrame | None = None,
    obs_geral: str = "", posicao: int | None = None, total_alunos: int = 0,
    freq_aluno: dict | None = None,
    analise_fn_aluno: dict | None = None,
    df_cal_aluno: pd.DataFrame | None = None,
) -> bytes:
    emitido = datetime.now().strftime("%d/%m/%Y às %H:%M")
    buffer  = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=_MARGEM, rightMargin=_MARGEM,
        topMargin=1.6 * cm, bottomMargin=1.4 * cm,
    )

    def _cb(canv, d):
        _draw_page_frame(canv, d, aluno, turma, emitido)

    risco_aluno = classificar_risco(media_al, notas_baixas, total_avals, seq_critica)
    tendencia   = detectar_tendencia(df_al)
    story       = []

    # ── CAPA ─────────────────────────────────────────────────────────────────
    _risco_cores_pdf = {"critico": _C["verm"], "atencao": _C["amarelo"], "adequado": _C["verde"], "excelente": _C["roxo"]}
    _risco_labels_pdf = {"critico": "SITUAÇÃO CRÍTICA", "atencao": "REQUER ATENÇÃO", "adequado": "SITUAÇÃO ADEQUADA", "excelente": "DESEMPENHO EXCELENTE"}
    cor_risco   = _risco_cores_pdf[risco_aluno]
    label_risco = _risco_labels_pdf[risco_aluno]

    capa_data = [[
        Paragraph(f"<b><font size='18' color='#00539F'>{aluno}</font></b><br/><font size='10' color='#475569'>{turma}</font>", _S_CAPA_NOME),
        Paragraph(f"<font size='8' color='#475569'>Boletim Individual de Desempenho<br/>Emitido em {emitido}</font>", _S_CAPA_DT),
    ]]
    capa_tbl = Table(capa_data, colWidths=[_LARGURA * 0.62, _LARGURA * 0.38])
    capa_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _C["azul_claro"]),
        ("ROWPADDING", (0, 0), (-1, -1), 14),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW",  (0, 0), (-1, -1), 2.5, _C["azul"]),
        ("LINEBEFORE", (0, 0), (0, -1),  3,   _C["azul"]),
    ]))

    risco_data = [[
        Paragraph(f"<font color='white'><b>{label_risco}</b></font>  <font color='white' size='7.5'>·  Posição: {'%dº de %d' % (posicao, total_alunos) if posicao else 'N/A'}  ·  Avaliações: {total_avals}</font>",
                  _ps(f"risco_badge_{risco_aluno}", fontName="Helvetica-Bold", fontSize=8, textColor=_C["branco"], leading=12))
    ]]
    risco_tbl = Table(risco_data, colWidths=[_LARGURA])
    risco_tbl.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, -1), cor_risco),
        ("ROWPADDING",  (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
    ]))

    story += [Spacer(1, 0.2 * cm), capa_tbl, Spacer(1, 0.15 * cm), risco_tbl, Spacer(1, 0.3 * cm)]

    # ── ALERTA SEQUÊNCIA CRÍTICA ──────────────────────────────────────────────
    if seq_critica >= SEQUENCIA_CRITICA_MIN:
        alerta_data = [[Paragraph(f"<b><font color='white' size='9'>ATENÇÃO: {seq_critica} avaliações consecutivas abaixo de {NOTA_MINIMA:.0f},0</font></b><br/><font color='white' size='7.5'>Intervenção pedagógica urgente recomendada.</font>", _S_ALERTA_IN)]]
        alerta_tbl = Table(alerta_data, colWidths=[_LARGURA])
        alerta_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), _C["verm"]),
            ("ROWPADDING", (0, 0), (-1, -1), 10),
            ("LEFTPADDING",(0, 0), (-1, -1), 14),
            ("LINEBEFORE", (0, 0), (0, -1),  5, colors.HexColor("#7F1D1D")),
        ]))
        story += [alerta_tbl, Spacer(1, 0.3 * cm)]

    # ── OBSERVAÇÃO GERAL ─────────────────────────────────────────────────────
    if obs_geral:
        obs_data = [[Paragraph("📌 Observação do Docente", _S_DIAG_TIT), Paragraph(obs_geral, _S_DIAG)]]
        obs_tbl = Table(obs_data, colWidths=[3.5 * cm, _LARGURA - 3.5 * cm])
        obs_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), _C["azul_med"]),
            ("ROWPADDING", (0, 0), (-1, -1), 8),
            ("VALIGN",     (0, 0), (-1, -1), "TOP"),
            ("GRID",       (0, 0), (-1, -1), 0.25, _C["cinza2"]),
        ]))
        story += [obs_tbl, Spacer(1, 0.3 * cm)]

    # ── KPI CARDS ─────────────────────────────────────────────────────────────
    story.append(_secao_titulo("ResSummary de Desempenho"))
    story.append(Spacer(1, 0.2 * cm))

    sinal    = "+" if delta >= 0 else ""
    tend_txt = {"melhora":"▲ Melhora","queda":"▼ Queda","estável":"● Estável","indefinida":"— Indefinido"}[tendencia]
    cor_tend = _C["verde"] if tendencia == "melhora" else (_C["verm"] if tendencia == "queda" else _C["amarelo"])

    largura_card = _LARGURA / 6
    kpi_row = [[
        _kpi_card(f"{media_al:.1f}",    "Média Simples",   _cor_nota(media_al), largura=largura_card),
        _kpi_card(f"{media_pond:.1f}",  "Média Ponderada", _cor_nota(media_pond), largura=largura_card),
        _kpi_card(f"{media_turma:.1f}", "Média da Turma",  _C["azul"], largura=largura_card),
        _kpi_card(f"{sinal}{delta:.1f}","Dif. vs Turma",   (_C["verde"] if delta >= 0 else _C["verm"]), largura=largura_card),
        _kpi_card(str(notas_baixas),    "Notas Críticas",  (_C["verm"] if notas_baixas > 0 else _C["verde"]), largura=largura_card),
        _kpi_card(tend_txt,             "Tendência",       cor_tend, largura=largura_card),
    ]]
    kpi_tbl = Table(kpi_row, colWidths=[largura_card] * 6, hAlign="CENTER")
    kpi_tbl.setStyle(TableStyle([
        ("ALIGN",        (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING",   (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 0),
    ]))
    story += [kpi_tbl, Spacer(1, 0.4 * cm)]

    # ── DIAGNÓSTICO AUTOMÁTICO ────────────────────────────────────────────────
    diag = gerar_diagnostico(aluno, media_al, media_pond, tendencia, notas_baixas, total_avals, seq_critica, delta, posicao, total_alunos, bimestres, df_al)
    story.append(KeepTogether([
        _secao_titulo("Diagnóstico Automático"),
        Spacer(1, 0.2 * cm),
        Paragraph(diag["texto"], _S_DIAG),
        Spacer(1, 0.4 * cm),
    ]))

    # ── FREQUÊNCIA ────────────────────────────────────────────────────────────
    if freq_aluno and freq_aluno.get("tem_dados"):
        pct    = freq_aluno.get("pct_presenca", 0)
        faltas = freq_aluno.get("total_faltas", 0)
        aulas  = freq_aluno.get("total_aulas", 0)
        cor_freq = _C["verde"] if pct >= 90 else (_C["amarelo"] if pct >= 75 else _C["verm"])

        iif_val  = "—"
        iif_cor  = _C["verde"]
        msf_val  = "—"
        mcf_val  = "—"
        if analise_fn_aluno:
            msf = analise_fn_aluno.get("media_sem_falta")
            mcf = analise_fn_aluno.get("media_com_falta")
            imp = analise_fn_aluno.get("impacto")
            msf_val = f"{msf:.1f}" if msf is not None else "—"
            mcf_val = f"{mcf:.1f}" if mcf is not None else "—"
            if imp is not None and pct < 100:
                pct_falta  = 1 - (pct / 100)
                iif_num    = round(min(10, pct_falta * abs(imp) * 10), 1)
                iif_val    = f"{iif_num:.1f}"
                iif_cor    = (_C["verde"] if iif_num <= 2 else (_C["amarelo"] if iif_num <= 4 else (colors.HexColor("#F97316") if iif_num <= 6 else _C["verm"])))
            elif pct == 100:
                iif_val = "0.0"

        lc = _LARGURA / 4
        freq_row = [[
            _kpi_card(f"{pct:.1f}%",     "Frequência",        cor_freq,    largura=lc),
            _kpi_card(str(faltas),        "Faltas",            _C["verm"] if faltas > 0 else _C["verde"], largura=lc),
            _kpi_card(msf_val,            "Média s/ Falta",    _C["verde"], largura=lc),
            _kpi_card(iif_val,            "Índice Imp. Falta", iif_cor,     largura=lc),
        ]]
        freq_tbl = Table(freq_row, colWidths=[lc] * 4, hAlign="CENTER")
        freq_tbl.setStyle(TableStyle([
            ("ALIGN",        (0, 0), (-1, -1), "CENTER"),
            ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING",  (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING",   (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 0),
        ]))
        story += [
            _secao_titulo("Frequência"),
            Spacer(1, 0.2 * cm),
            freq_tbl,
            Spacer(1, 0.3 * cm),
        ]

        story.append(Spacer(1, 0.1 * cm))

    # ── GRÁFICOS: RADAR + EVOLUÇÃO TEMPORAL ────────────────────────────────────
    col_crit_pdf = coluna_criterio(df_al)
    col_uc_pdf   = coluna_uc(df_al)
    col_obs_pdf  = "Observação" if "Observação" in df_al.columns else None

    criterios = sorted(df_al[col_crit_pdf].dropna().unique().tolist()) if col_crit_pdf in df_al.columns else []
    if criterios:
        vals_aluno = [df_al[df_al[col_crit_pdf] == c]["Nota"].mean() or 0 for c in criterios]
        vals_turma_r = ([df_turma[df_turma[col_crit_pdf] == c]["Nota"].mean() or 0 for c in criterios] if comparar_turma and col_crit_pdf in df_turma.columns else None)
        
        # Instanciação dos três gráficos
        radar = _pdf_radar_chart(criterios, vals_aluno, vals_turma_r, largura=220, altura=190)
        bar_bim = _pdf_bar_bimestre(bimestres, largura=220, altura=165) if not bimestres.empty else None
        line_ev = _pdf_line_chart_evolucao(df_al, largura=220, altura=165)

        # Títulos internos para os gráficos (Definição dos estilos e objetos Paragraph)
        style_title = _ps("graph_title", fontName="Helvetica-Bold", fontSize=8, 
                          alignment=1, textColor=_C["azul"], spaceAfter=5)
        
        titulo_radar = Paragraph("DISTRIBUIÇÃO DE COMPETÊNCIAS", style_title)
        titulo_linha = Paragraph("EVOLUÇÃO TEMPORAL (ÚLTIMAS NOTAS)", style_title)

        # Montagem estruturada do grid em 2 colunas dependendo do bar_bim
        if bar_bim:
            titulo_bimestre = Paragraph("EVOLUÇÃO BIMESTRAL", style_title)
            graficos_data = [
                [titulo_radar, titulo_linha],
                [radar, line_ev],
                [titulo_bimestre, ""],
                [bar_bim, ""]
            ]
            t_style = [
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 2),
                ("TOPPADDING", (0, 1), (-1, 1), 5),
                ("BOTTOMPADDING", (0, 2), (-1, 2), 2),
                ("TOPPADDING", (0, 3), (-1, 3), 5),
            ]
        else:
            graficos_data = [
                [titulo_radar, titulo_linha],
                [radar, line_ev]
            ]
            t_style = [
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 2),
                ("TOPPADDING", (0, 1), (-1, 1), 5),
            ]
        
        g_tbl = Table(graficos_data, colWidths=[_LARGURA / 2, _LARGURA / 2])
        g_tbl.setStyle(TableStyle(t_style))

        story += [
            _secao_titulo("Perfil de Habilidades e Evolução Temporal"),
            Spacer(1, 0.2 * cm),
            g_tbl,
            Spacer(1, 0.4 * cm),
        ]

    # ── DESEMPENHO POR CRITÉRIO ───────────────────────────────────────────────
    if col_crit_pdf in df_al.columns and df_al[col_crit_pdf].nunique() >= 2:
        med_crit = df_al.groupby(col_crit_pdf)["Nota"].mean().sort_values(ascending=False)
        crit_header = [Paragraph("<b>Critério</b>", _S_BOLD_C), Paragraph("<b>Média</b>", _S_BOLD_C), Paragraph("<b>Desempenho</b>", _S_BOLD_C), Paragraph("<b>Situação</b>", _S_BOLD_C)]
        crit_rows  = [crit_header]
        crit_style = [
            ("BACKGROUND",    (0, 0), (-1, 0), _C["azul"]),
            ("TEXTCOLOR",     (0, 0), (-1, 0), _C["branco"]),
            ("FONTSIZE",      (0, 0), (-1, -1), 8),
            ("ROWPADDING",    (0, 0), (-1, -1), 5),
            ("GRID",          (0, 0), (-1, -1), 0.25, _C["cinza2"]),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN",         (1, 0), (3, -1), "CENTER"),
        ]
        for i, (crit, media_c) in enumerate(med_crit.items(), start=1):
            sit = "Aprovado" if media_c >= NOTA_MINIMA else "Crítico"
            cor_sit = _C["verde"] if media_c >= NOTA_MINIMA else _C["verm"]
            crit_rows.append([
                Paragraph(str(crit).replace("Leórica", "Teórica"), _S_BODY),
                Paragraph(f"<b><font color='#{_cor_nota(media_c).hexval()}'>{media_c:.1f}</font></b>", _S_BOLD_C),
                _barra_progresso(media_c),
                Paragraph(f"<font color='#{cor_sit.hexval()}'><b>{sit}</b></font>", _S_BOLD_C),
            ])
            if i % 2 == 0:
                crit_style.append(("BACKGROUND", (0, i), (0, i), _C["cinza"]))
                crit_style.append(("BACKGROUND", (3, i), (3, i), _C["cinza"]))

        crit_tbl = Table(crit_rows, colWidths=[7.5 * cm, 1.5 * cm, 6.0 * cm, 2.4 * cm])
        crit_tbl.setStyle(TableStyle(crit_style))
        story.append(KeepTogether([
            _secao_titulo("Desempenho por Critério"),
            Spacer(1, 0.2 * cm),
            crit_tbl,
            Spacer(1, 0.4 * cm),
        ]))

    # ── ALERTAS (Notas abaixo de 6,0) ─────────────────────────────────────────
    df_crit_pdf = (df_al[df_al["Nota"] < NOTA_MINIMA].sort_values("Data", ascending=False) if "Nota" in df_al.columns else pd.DataFrame())
    if not df_crit_pdf.empty:
        story.append(KeepTogether([_secao_titulo("Alertas — Notas Abaixo de 6,0"), Spacer(1, 0.2 * cm)]))
        
        a_header = [
            Paragraph("<b>Data</b>", _S_BOLD_C), 
            Paragraph("<b>Critério</b>", _S_BOLD_C), 
            Paragraph("<b>UC</b>", _S_BOLD_C), 
            Paragraph("<b>Vetor</b>", _S_BOLD_C), 
            Paragraph("<b>Nota</b>", _S_BOLD_C), 
            Paragraph("<b>Observação</b>", _S_BOLD_C)
        ]
        alerta_rows = [a_header]  # DECLARAÇÃO EXPLÍCITA QUE ESTAVA FALTANDO
        
        for _, row in df_crit_pdf.head(15).iterrows():
            dt    = row["Data"].strftime("%d/%m/%Y") if pd.notna(row["Data"]) else "—"
            obs   = str(row.get(col_obs_pdf, "") or "")
            nota_v = row["Nota"]
            alerta_rows.append([
                Paragraph(dt, _S_BODY_C), 
                Paragraph(str(row.get(col_crit_pdf, "—")).replace("Leórica", "Teórica"), _S_BODY),
                Paragraph(str(row.get(col_uc_pdf, "—")), _S_BODY), 
                Paragraph(str(row.get("Vetor (Peso)", "—")), _S_BODY_C),
                Paragraph(f"<b><font color='#E30613'>{nota_v:.1f}</font></b>", _S_BOLD_C), 
                Paragraph(obs, _S_OBS),
            ])
        a_tbl = Table(alerta_rows, colWidths=[1.9 * cm, 4.4 * cm, 3.5 * cm, 2.8 * cm, 1.1 * cm, 3.7 * cm], repeatRows=1)
        a_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0), _C["verm"]), ("TEXTCOLOR",     (0, 0), (-1, 0), _C["branco"]),
            ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE",      (0, 0), (-1, -1), 8),
            ("ROWPADDING",    (0, 0), (-1, -1), 5), ("GRID",          (0, 0), (-1, -1), 0.25, _C["cinza2"]),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), [_C["branco"], _C["verm_claro"]]), ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story += [a_tbl, Spacer(1, 0.4 * cm)]

    # ── RECUPERAÇÕES ──────────────────────────────────────────────────────────
    if df_rec_aluno is not None and not df_rec_aluno.empty and "Nota_Rec" in df_rec_aluno.columns and df_rec_aluno["Nota_Rec"].notna().any():
        story.append(KeepTogether([_secao_titulo("Histórico de Recuperações"), Spacer(1, 0.2 * cm)]))
        r_header = [Paragraph("<b>Data Rec.</b>", _S_BOLD_C), Paragraph("<b>Critério</b>", _S_BOLD_C), Paragraph("<b>UC</b>", _S_BOLD_C), Paragraph("<b>Nota Orig.</b>", _S_BOLD_C), Paragraph("<b>Nota Rec.</b>", _S_BOLD_C), Paragraph("<b>Delta</b>", _S_BOLD_C), Paragraph("<b>Resultado</b>", _S_BOLD_C), Paragraph("<b>Observação</b>", _S_BOLD_C)]
        rec_rows = [r_header]
        for _, row in df_rec_aluno.iterrows():
            nota_orig = row.get("Nota_Orig")
            nota_rec  = row.get("Nota_Rec")
            delta_r   = (nota_rec - nota_orig) if pd.notna(nota_rec) and pd.notna(nota_orig) else None
            data_r    = row.get("Data_Rec", "")
            data_fmt  = data_r.strftime("%d/%m/%Y") if pd.notna(data_r) and hasattr(data_r, "strftime") else str(data_r)
            aprovado  = "Aprovado" if pd.notna(nota_rec) and nota_rec >= NOTA_MINIMA else "Não aprovado"
            cor_ap    = "#059669" if aprovado == "Aprovado" else "#E30613"
            delta_str = (f"{'▲' if delta_r >= 0 else '▼'}{abs(delta_r):.1f}") if delta_r is not None else "—"
            cor_d     = "#059669" if delta_r and delta_r >= 0 else "#E30613"
            obs_r     = str(row.get("Observação", "") or "")
            rec_rows.append([
                Paragraph(data_fmt, _S_BODY_C), Paragraph(str(row.get("Critério", "—")).replace("Leórica", "Teórica"), _S_BODY), Paragraph(str(row.get("UC", "—")), _S_BODY),
                Paragraph(nota_formatada(nota_orig), _S_BODY_C), Paragraph(f"<b><font color='{cor_ap}'>{nota_formatada(nota_rec)}</font></b>", _S_BOLD_C),
                Paragraph(f"<font color='{cor_d}'><b>{delta_str}</b></font>", _S_BOLD_C), Paragraph(f"<font color='{cor_ap}'><b>{aprovado}</b></font>", _S_BODY_C), Paragraph(obs_r, _S_OBS),
            ])
        r_tbl = Table(rec_rows, colWidths=[1.8 * cm, 3.2 * cm, 2.4 * cm, 1.5 * cm, 1.5 * cm, 1.3 * cm, 2.1 * cm, 3.6 * cm], repeatRows=1)
        r_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0), _C["amarelo"]), ("TEXTCOLOR",     (0, 0), (-1, 0), _C["texto"]),
            ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE",      (0, 0), (-1, -1), 7.5),
            ("ROWPADDING",    (0, 0), (-1, -1), 5), ("GRID",          (0, 0), (-1, -1), 0.25, _C["cinza2"]),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), [_C["branco"], _C["amar_claro"]]), ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story += [r_tbl, Spacer(1, 0.4 * cm)]

    # ── HISTÓRICO COMPLETO ────────────────────────────────────────────────────
    story.append(_secao_titulo("Histórico de Avaliações (últimas 30)"))
    story.append(Spacer(1, 0.2 * cm))

    h_header = [Paragraph("<b>Data</b>", _S_BOLD_C), Paragraph("<b>UC</b>", _S_BOLD_C), Paragraph("<b>Critério</b>", _S_BOLD_C), Paragraph("<b>Vetor</b>", _S_BOLD_C), Paragraph("<b>Nota</b>", _S_BOLD_C), Paragraph("<b>Obs</b>", _S_BOLD_C)]
    hist_rows   = [h_header]
    hist_style = [
        ("BACKGROUND", (0, 0), (-1, 0), _C["azul"]), ("TEXTCOLOR",  (0, 0), (-1, 0), _C["branco"]),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE",   (0, 0), (-1, -1), 8),
        ("ROWPADDING", (0, 0), (-1, -1), 5), ("GRID",       (0, 0), (-1, -1), 0.25, _C["cinza2"]),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"), ("ALIGN",      (0, 1), (0, -1), "CENTER"), ("ALIGN",      (3, 1), (4, -1), "CENTER"),
    ]

    for i, (_, row) in enumerate(df_al.sort_values("Data", ascending=False).head(30).iterrows(), start=1):
        dt     = row["Data"].strftime("%d/%m/%Y") if pd.notna(row["Data"]) else "—"
        nota_v = float(row.get("Nota", 0))
        hex_n  = "#059669" if nota_v >= 8 else ("#B45309" if nota_v >= NOTA_MINIMA else "#DC2626")
        bg     = _cor_nota_bg(nota_v)
        obs_h  = str(row.get(col_obs_pdf, "") or "")
        
        hist_style.append(("BACKGROUND", (4, i), (4, i), bg))
        hist_rows.append([
            Paragraph(dt, _S_BODY_C), Paragraph(str(row.get(col_uc_pdf, "—")), _S_BODY),
            Paragraph(str(row.get(col_crit_pdf, "—")).replace("Leórica", "Teórica"), _S_BODY), Paragraph(str(row.get("Vetor (Peso)", "—")), _S_BODY_C),
            Paragraph(f"<b><font color='{hex_n}'>{nota_v:.1f}</font></b>", _S_BOLD_C), Paragraph(obs_h, _S_OBS),
        ])
        if i % 2 == 0:
            for ci in range(5):
                hist_style.append(("BACKGROUND", (ci, i), (ci, i), _C["cinza"]))

    h_tbl = Table(hist_rows, colWidths=[1.9 * cm, 4.0 * cm, 4.8 * cm, 2.8 * cm, 1.3 * cm, 2.6 * cm], repeatRows=1)
    h_tbl.setStyle(TableStyle(hist_style))
    story += [h_tbl, Spacer(1, 0.3 * cm)]

    # ── LEGENDA ───────────────────────────────────────────────────────────────
    legenda_data = [[Paragraph("<b><font color='#059669'>■</font></b> Nota ≥ 8,0 (Excelente) &nbsp;&nbsp;<b><font color='#F59E0B'>■</font></b> Nota ≥ 6,0 (Adequado) &nbsp;&nbsp;<b><font color='#E30613'>■</font></b> Nota &lt; 6,0 (Crítico)", _S_LEG3)]]
    leg_tbl = Table(legenda_data, colWidths=[_LARGURA])
    leg_tbl.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), _C["cinza"]), ("ROWPADDING", (0, 0), (-1, -1), 6), ("BOX",        (0, 0), (-1, -1), 0.5, _C["cinza2"])]))
    story.append(leg_tbl)

    doc.build(story, onFirstPage=_cb, onLaterPages=_cb)
    buffer.seek(0)
    return buffer.read()


def gerar_relatorio_individual_ia_pdf(
    aluno: str,
    turma: str,
    media_pond: float,
    risco: str,
    tendencia: str,
    notas_baixas: int,
    total_avals: int,
    freq_pct: float | None,
    diagnostico: str,
    ponto_forte: str,
    ponto_fraco: str,
    acao_docente: str,
    obs_geral: str = "",
) -> bytes:
    """Gera PDF individual do aluno com análise pedagógica da IA."""
    emitido = datetime.now().strftime("%d/%m/%Y às %H:%M")
    buffer  = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=_MARGEM, rightMargin=_MARGEM,
        topMargin=1.6 * cm, bottomMargin=1.4 * cm,
    )

    def _cb(canv, d):
        _draw_page_frame(canv, d, f"Relatório Individual — {aluno}", turma, emitido)

    _cor_risco = {
        "critico": _C["verm"], "atencao": _C["amarelo"],
        "adequado": _C["verde"], "excelente": _C["roxo"],
    }
    _label_risco = {
        "critico": "Situação Crítica", "atencao": "Requer Atenção",
        "adequado": "Situação Adequada", "excelente": "Desempenho Excelente",
    }
    _cor_r = _cor_risco.get(risco, _C["azul"])
    _lbl_r = _label_risco.get(risco, risco.capitalize())

    story = []

    # ── CABEÇALHO ─────────────────────────────────────────────────────────────
    capa_data = [[
        Paragraph(
            f"<b><font size='16' color='#00539F'>{aluno}</font></b><br/>"
            f"<font size='9' color='#475569'>Turma: {turma}</font>",
            _S_CAPA_NOME,
        ),
        Paragraph(
            f"<font size='8' color='#475569'>Gerado em {emitido}<br/>"
            f"Análise via IA Pedagógica SENAI</font>",
            _S_CAPA_DT,
        ),
    ]]
    capa_tbl = Table(capa_data, colWidths=[_LARGURA * 0.62, _LARGURA * 0.38])
    capa_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _C["azul_claro"]),
        ("ROWPADDING", (0, 0), (-1, -1), 14),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW",  (0, 0), (-1, -1), 2.5, _C["azul"]),
        ("LINEBEFORE", (0, 0), (0, -1),  3,   _cor_r),
    ]))
    story += [Spacer(1, 0.3 * cm), capa_tbl, Spacer(1, 0.5 * cm)]

    # ── KPIs ──────────────────────────────────────────────────────────────────
    story.append(_secao_titulo("Indicadores de Desempenho"))
    story.append(Spacer(1, 0.3 * cm))

    freq_str = f"{freq_pct:.1f}%" if freq_pct is not None else "—"
    kpi_row = [[
        _kpi_card(f"{media_pond:.1f}", "Média Ponderada", _cor_nota(media_pond)),
        _kpi_card(_lbl_r,              "Situação",         _cor_r),
        _kpi_card(tendencia.capitalize(), "Tendência",     _C["azul"]),
        _kpi_card(str(notas_baixas),    "Notas Críticas",  _C["verm"] if notas_baixas > 0 else _C["verde"]),
        _kpi_card(str(total_avals),     "Avaliações",      _C["cinza2"]),
        _kpi_card(freq_str,             "Frequência",      _C["verde"] if freq_pct and freq_pct >= 75 else _C["verm"]),
    ]]
    kpi_tbl = Table(kpi_row, colWidths=[3.1 * cm] * 6, hAlign="CENTER")
    kpi_tbl.setStyle(TableStyle([
        ("ALIGN",  (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
    ]))
    story += [kpi_tbl, Spacer(1, 0.5 * cm)]

    # ── OBSERVAÇÃO GERAL ──────────────────────────────────────────────────────
    if obs_geral:
        obs_data = [[Paragraph(f"<b>Observação Geral:</b> {obs_geral}", _S_OBS)]]
        obs_tbl = Table(obs_data, colWidths=[_LARGURA])
        obs_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), _C["azul_claro"]),
            ("ROWPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING",(0, 0), (-1, -1), 10),
            ("BOX",        (0, 0), (-1, -1), 0.5, _C["azul"]),
        ]))
        story += [obs_tbl, Spacer(1, 0.4 * cm)]

    # ── ANÁLISE IA ────────────────────────────────────────────────────────────
    story.append(_secao_titulo("Análise Pedagógica — Inteligência Artificial"))
    story.append(Spacer(1, 0.3 * cm))

    secoes_ia = [
        ("📋 Diagnóstico",     diagnostico,  _C["azul"],                  _C["azul_claro"]),
        ("✅ Ponto Forte",     ponto_forte,  _C["verde"],                 colors.HexColor("#F0FDF4")),
        ("⚠️ Ponto Fraco",    ponto_fraco,  _C["verm"],                  colors.HexColor("#FFF1F1")),
        ("🎯 Ação Recomendada", acao_docente, colors.HexColor("#B45309"), _C["amar_claro"]),
    ]

    for titulo_s, texto_s, cor_titulo, cor_fundo in secoes_ia:
        _key = titulo_s[:8].replace(" ", "").replace("📋", "d").replace("✅", "f").replace("⚠️", "w").replace("🎯", "a")
        s_data = [[
            Paragraph(f"<b>{titulo_s}</b>",
                      _ps(f"ia_tit_{_key}", fontName="Helvetica-Bold", fontSize=9,
                          textColor=_C["branco"], leading=13)),
            Paragraph(texto_s,
                      _ps(f"ia_body_{_key}", fontName="Helvetica", fontSize=9,
                          textColor=_C["texto"], leading=14)),
        ]]
        s_tbl = Table(s_data, colWidths=[3.0 * cm, _LARGURA - 3.0 * cm])
        s_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), cor_fundo),
            ("BACKGROUND",    (0, 0), (0, -1),  cor_titulo),
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING",    (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING",   (0, 0), (-1, -1), 10),
            ("LINEBELOW",     (0, 0), (-1, -1), 0.5, _C["cinza2"]),
        ]))
        story += [s_tbl, Spacer(1, 0.15 * cm)]

    doc.build(story, onFirstPage=_cb, onLaterPages=_cb)
    buffer.seek(0)
    return buffer.read()


def gerar_relatorio_basico_turma_pdf(
    turma: str,
    perfil_df: pd.DataFrame,
    df_turma: pd.DataFrame,
    df_freq: pd.DataFrame,
) -> bytes:
    """Gera PDF com o relatório básico da turma: KPIs, tabela completa de alunos
    (ordenada por risco) e seção destacada de alunos em situação crítica/atenção.
    Usado como anexo no relatório semanal por e-mail.
    """
    from data.analysis import calcular_frequencia_aluno

    emitido = datetime.now().strftime("%d/%m/%Y às %H:%M")
    buffer  = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=_MARGEM, rightMargin=_MARGEM,
        topMargin=1.6 * cm, bottomMargin=1.4 * cm,
    )

    def _cb(canv, d):
        _draw_page_frame(canv, d, f"Relatório da Turma — {turma}", turma, emitido)

    story = []

    # ── CABEÇALHO ──────────────────────────────────────────────────────────────
    capa_data = [[
        Paragraph(
            f"<b><font size='15' color='#00539F'>Relatório Semanal da Turma</font></b><br/>"
            f"<font size='9' color='#475569'>{turma} · Emitido em {emitido}</font>",
            _S_CAPA_NOME,
        ),
        Paragraph(
            "<font size='8' color='#475569'>SENAI · Painel Docente<br/>"
            "Documento confidencial — uso exclusivo do docente</font>",
            _S_CAPA_DT,
        ),
    ]]
    capa_tbl = Table(capa_data, colWidths=[_LARGURA * 0.65, _LARGURA * 0.35])
    capa_tbl.setStyle(TableStyle([
        ("VALIGN",         (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",    (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",   (0, 0), (-1, -1), 0),
        ("LINEBELOW",      (0, 0), (-1, -1), 1.5, _C["azul"]),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 8),
    ]))
    story += [capa_tbl, Spacer(1, 0.5 * cm)]

    # ── KPIs GERAIS ────────────────────────────────────────────────────────────
    n_total   = len(perfil_df)
    n_crit    = int((perfil_df["Risco"] == "critico").sum())
    n_at      = int((perfil_df["Risco"] == "atencao").sum())
    n_adeq    = int((perfil_df["Risco"] == "adequado").sum())
    n_exc     = int((perfil_df["Risco"] == "excelente").sum())
    media_g   = round(df_turma["Nota"].mean(), 1) if not df_turma.empty else 0.0
    pct_aprov = round((n_adeq + n_exc) / n_total * 100) if n_total else 0

    kpi_cards = [
        _kpi_card(str(n_total),     "Alunos",          _C["azul"]),
        _kpi_card(f"{media_g:.1f}", "Média Geral",     _C["azul"]),
        _kpi_card(str(n_crit),      "Críticos",        _C["verm"]),
        _kpi_card(str(n_at),        "Atenção",         _C["amarelo"]),
        _kpi_card(f"{pct_aprov}%",  "Taxa Aprovação", _C["verde"]),
    ]
    kpi_row = Table([kpi_cards], colWidths=[_LARGURA / 5] * 5)
    kpi_row.setStyle(TableStyle([
        ("LEFTPADDING",  (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
    ]))
    story += [kpi_row, Spacer(1, 0.5 * cm)]

    # ── TABELA COMPLETA DE ALUNOS ──────────────────────────────────────────────
    story.append(_secao_titulo("Desempenho Completo da Turma"))
    story.append(Spacer(1, 0.25 * cm))

    _risco_label = {
        "critico": "Crítico", "atencao": "Atenção",
        "adequado": "Adequado", "excelente": "Excelente",
    }
    _risco_cor_cell = {
        "critico":   (_C["verm"],    _C["verm_claro"]),
        "atencao":   (_C["amarelo"], _C["amar_claro"]),
        "adequado":  (_C["verde"],   _C["verde_claro"]),
        "excelente": (_C["roxo"],    _C["roxo_claro"]),
    }

    header_row = [
        Paragraph("<b>Aluno</b>",         _S_BOLD_C),
        Paragraph("<b>Média</b>",          _S_BOLD_C),
        Paragraph("<b>Situação</b>",       _S_BOLD_C),
        Paragraph("<b>Tendência</b>",      _S_BOLD_C),
        Paragraph("<b>Notas &lt;6</b>",    _S_BOLD_C),
        Paragraph("<b>Frequência</b>",     _S_BOLD_C),
        Paragraph("<b>Seq. Crítica</b>",   _S_BOLD_C),
        Paragraph("<b>Faltas Consec.</b>", _S_BOLD_C),
    ]
    col_w = [4.2*cm, 1.5*cm, 2.2*cm, 2.0*cm, 1.6*cm, 2.0*cm, 1.8*cm, 1.8*cm]

    _tend_symbol = {"melhora": "▲ Melhora", "queda": "▼ Queda",
                    "estável": "● Estável", "indefinida": "— Indefinido"}
    _tend_cor    = {"melhora": _C["verde"], "queda": _C["verm"],
                    "estável": _C["amarelo"], "indefinida": _C["cinza3"]}

    table_data   = [header_row]
    row_styles   = []

    for i, (_, row) in enumerate(perfil_df.iterrows(), start=1):
        risco  = row["Risco"]
        freq   = calcular_frequencia_aluno(df_freq, row["Aluno"])
        freq_s = f"{freq['pct_presenca']:.1f}%" if freq["tem_dados"] else "—"
        seq_f  = freq.get("faltas_seq_atual", 0)
        seq_f_s = f"{seq_f}×" if seq_f >= 2 else "—"
        seq_c  = int(row.get("Seq_Critica", 0))
        tend   = row.get("Tendencia", "indefinida")

        cor_txt, cor_bg = _risco_cor_cell.get(risco, (_C["azul"], _C["cinza"]))
        cor_nota_hex = _cor_nota(row["Média"]).hexval()
        cor_tend_hex = _tend_cor.get(tend, _C["cinza3"]).hexval()
        cor_seq_hex  = _C["verm"].hexval() if seq_c else _C["cinza3"].hexval()
        cor_faltas_hex = (_C["roxo"] if seq_f >= 3 else (_C["verm"] if seq_f >= 2 else _C["cinza3"])).hexval()

        table_data.append([
            Paragraph(str(row["Aluno"]), _S_BODY),
            Paragraph(f"<b><font color='#{cor_nota_hex}'>{row['Média']:.1f}</font></b>", _S_BODY_C),
            Paragraph(f"<b><font color='#{cor_txt.hexval()}'>{_risco_label.get(risco, risco)}</font></b>", _S_BODY_C),
            Paragraph(f"<font color='#{cor_tend_hex}'>{_tend_symbol.get(tend, '—')}</font>", _S_BODY_C),
            Paragraph(str(int(row["Notas_Baixas"])), _S_BODY_C),
            Paragraph(freq_s, _S_BODY_C),
            Paragraph(f"<b><font color='#{cor_seq_hex}'>{str(seq_c) if seq_c else '—'}</font></b>", _S_BODY_C),
            Paragraph(f"<b><font color='#{cor_faltas_hex}'>{seq_f_s}</font></b>", _S_BODY_C),
        ])
        row_styles.append(("BACKGROUND", (0, i), (-1, i), cor_bg if risco in ("critico", "atencao") else colors.white))

    t_alunos = Table(table_data, colWidths=col_w, repeatRows=1)
    base_style = [
        ("BACKGROUND",    (0, 0), (-1, 0), _C["azul"]),
        ("TEXTCOLOR",     (0, 0), (-1, 0), _C["branco"]),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, 0), 8),
        ("ROWBACKGROUND", (0, 1), (-1, -1), [colors.white, _C["cinza"]]),
        ("ROWPADDING",    (0, 0), (-1, -1), 6),
        ("GRID",          (0, 0), (-1, -1), 0.3, _C["cinza2"]),
        ("LINEBELOW",     (0, 0), (-1, 0), 1.0, _C["azul"]),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]
    t_alunos.setStyle(TableStyle(base_style + row_styles))
    story += [t_alunos, Spacer(1, 0.6 * cm)]

    # ── SEÇÃO DE ALUNOS EM RISCO (detalhes extras) ────────────────────────────
    df_risco = perfil_df[perfil_df["Risco"].isin(["critico", "atencao"])]
    if not df_risco.empty:
        story.append(_secao_titulo("Alunos que Requerem Atenção Imediata"))
        story.append(Spacer(1, 0.25 * cm))

        for _, row in df_risco.iterrows():
            risco   = row["Risco"]
            cor_txt, cor_bg = _risco_cor_cell[risco]
            freq    = calcular_frequencia_aluno(df_freq, row["Aluno"])
            seq_f   = freq.get("faltas_seq_atual", 0)

            alertas = []
            if int(row.get("Seq_Critica", 0)) > 0:
                alertas.append(f"🚨 {int(row['Seq_Critica'])} avaliações consecutivas abaixo de {NOTA_MINIMA:.0f}")
            if freq["tem_dados"] and freq["pct_presenca"] < 75:
                alertas.append(f"📉 Frequência crítica: {freq['pct_presenca']:.1f}% (mín. 75%)")
            if seq_f >= 3:
                datas = [d.strftime("%d/%m") for d in freq.get("faltas_seq_datas", []) if hasattr(d, "strftime")]
                alertas.append(f"⛔ {seq_f} faltas consecutivas — risco de desistência" + (f" ({', '.join(datas)})" if datas else ""))
            elif seq_f == 2:
                alertas.append(f"⚠️ 2 faltas consecutivas — verificar com aluno")
            if row["Tendencia"] == "queda":
                alertas.append("📉 Tendência de queda nas últimas avaliações")

            # Card do aluno
            alerta_txt = "<br/>".join(alertas) if alertas else "Nenhum alerta adicional."
            card_data = [[
                Paragraph(
                    f"<b><font size='11' color='#FFFFFF'>{row['Aluno']}</font></b><br/>"
                    f"<font size='8' color='#FFFFFF'>{_risco_label.get(risco, risco)} · Média: {row['Média']:.1f}</font>",
                    _ps(f"card_h_{row['Aluno'][:6]}", fontName="Helvetica-Bold", fontSize=11,
                        textColor=_C["branco"], leading=14),
                ),
                Paragraph(
                    alerta_txt,
                    _ps(f"card_b_{row['Aluno'][:6]}", fontName="Helvetica", fontSize=8,
                        textColor=_C["texto"], leading=12),
                ),
            ]]
            card_tbl = Table(card_data, colWidths=[4.5 * cm, _LARGURA - 4.5 * cm])
            card_tbl.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (0, -1),  cor_txt),
                ("BACKGROUND",    (1, 0), (1, -1),  cor_bg),
                ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING",    (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("LEFTPADDING",   (0, 0), (-1, -1), 12),
                ("BOX",           (0, 0), (-1, -1), 0.5, _C["cinza2"]),
            ]))
            story += [KeepTogether([card_tbl]), Spacer(1, 0.2 * cm)]

    # ── LEGENDA ────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 0.3 * cm))
    leg_items = [
        ("🔴 Crítico",   "Média < 6,0 ou vetor abaixo do mínimo"),
        ("🟡 Atenção",   "Média entre 6,0 e 7,0 ou >20% de notas baixas"),
        ("🟢 Adequado",  "Média ≥ 7,0, sem sequência crítica"),
        ("🟣 Excelente", "Média ≥ 8,5, sem nenhuma nota crítica"),
    ]
    leg_data = [[
        Paragraph(f"<b>{s}</b>", _ps(f"leg_s_{s[:4]}", fontName="Helvetica-Bold", fontSize=7, textColor=_C["texto"])),
        Paragraph(d, _ps(f"leg_d_{s[:4]}", fontName="Helvetica", fontSize=7, textColor=_C["texto2"])),
    ] for s, d in leg_items]
    leg_tbl = Table(leg_data, colWidths=[3.0 * cm, _LARGURA - 3.0 * cm])
    leg_tbl.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, -1), _C["cinza"]),
        ("ROWPADDING",  (0, 0), (-1, -1), 5),
        ("BOX",         (0, 0), (-1, -1), 0.5, _C["cinza2"]),
        ("LINEBELOW",   (0, 0), (-1, -2), 0.3, _C["cinza2"]),
    ]))
    story.append(
        Paragraph("Legenda de Situação", _ps("leg_titulo", fontName="Helvetica-Bold",
                                              fontSize=8, textColor=_C["cinza4"], spaceAfter=4))
    )
    story.append(leg_tbl)

    doc.build(story, onFirstPage=_cb, onLaterPages=_cb)
    buffer.seek(0)
    return buffer.read()
