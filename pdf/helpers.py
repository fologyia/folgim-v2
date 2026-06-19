import math
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.graphics.shapes import (
    Drawing, Rect, Line, String, Circle, PolyLine, Polygon,
)

from config import NOTA_MINIMA
from pdf.styles import (
    _C, _MARGEM, _LARGURA,
    _S_SEC, _S_KPI_VAL, _S_KPI_LBL, _S_BODY, _S_BODY_C, _S_BOLD_C,
    _S_RECOM, _S_RECOM_TIT, _ps,
)


def _draw_page_frame(canv, doc, aluno: str, turma: str, emitido: str):
    """Cabeçalho e rodapé em todas as páginas via canvas direto."""
    w, h = A4
    canv.saveState()

    canv.setFillColor(_C["azul"])
    canv.rect(0, h - 1.15 * cm, w, 1.15 * cm, fill=1, stroke=0)
    canv.setFillColor(_C["verm"])
    canv.rect(0, h - 1.15 * cm - 0.2 * cm, w, 0.2 * cm, fill=1, stroke=0)

    canv.setFont("Helvetica-Bold", 11)
    canv.setFillColor(colors.white)
    canv.drawString(_MARGEM, h - 0.80 * cm, "SENAI")
    canv.setFont("Helvetica", 8)
    canv.drawString(_MARGEM + 1.45 * cm, h - 0.80 * cm, "| Painel Docente")
    canv.setFont("Helvetica-Bold", 8)
    canv.drawRightString(w - _MARGEM, h - 0.80 * cm, aluno[:55])

    canv.setFillColor(_C["cinza2"])
    canv.rect(0, 0, w, 0.90 * cm, fill=1, stroke=0)
    canv.setFont("Helvetica", 6.5)
    canv.setFillColor(_C["texto2"])
    canv.drawString(
        _MARGEM, 0.32 * cm,
        f"Turma: {turma}  ·  Gerado em: {emitido}  ·  Documento confidencial — uso exclusivo do docente",
    )
    canv.setFont("Helvetica-Bold", 7)
    canv.drawRightString(w - _MARGEM, 0.32 * cm, f"Pág. {canv.getPageNumber()}")

    canv.saveState()
    canv.translate(w / 2, h / 2)
    canv.rotate(45)
    canv.setFont("Helvetica-Bold", 52)
    canv.setFillColor(colors.HexColor("#00539F"))
    canv.setFillAlpha(0.035)
    canv.drawCentredString(0, 0, "CONFIDENCIAL")
    canv.restoreState()

    canv.restoreState()


def _secao_titulo(texto: str, icone: str = "") -> Table:
    label = f"{icone}  {texto}" if icone else texto
    t = Table([[Paragraph(label, _S_SEC), ""]], colWidths=[_LARGURA * 0.60, _LARGURA * 0.40])
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (0, 0), _C["azul"]),
        ("BACKGROUND",    (1, 0), (1, 0), _C["azul_esc"]),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("ROWPADDING",    (0, 0), (-1, -1), 8),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t


def _cor_nota(nota: float) -> colors.Color:
    if nota >= 8: return _C["verde"]
    if nota >= 6: return _C["amarelo"]
    return _C["verm"]


def _cor_nota_bg(nota: float) -> colors.Color:
    if nota >= 8: return _C["verde_claro"]
    if nota >= 6: return _C["amar_claro"]
    return _C["verm_claro"]


def _kpi_card(valor: str, label: str, cor_borda: colors.Color, largura: float = None) -> Table:
    if largura is None:
        largura = _LARGURA / 6
        
    hex_cor = cor_borda.hexval()
    # Reduz fonte dinamicamente para valores longos
    n = len(str(valor))
    fs = 19 if n <= 4 else (15 if n <= 7 else (11 if n <= 10 else 9))
    
    # RESOLUÇÃO DO CACHE E ALINHAMENTO: Forçamos nomes únicos para evitar poluição do cache
    # Usamos alignment=1 (TA_CENTER) e fixamos leading=22 para que o bloco de texto ocupe o mesmo espaço
    _s_val = _ps(f"kpi_val_strict_{fs}", fontName="Helvetica-Bold", fontSize=fs,
                 leading=22, alignment=1)  # 1 = TA_CENTER correto
    _s_lbl = _ps("kpi_lbl_strict_center", fontName="Helvetica", fontSize=7, 
                 textColor=_C["texto2"], leading=10, alignment=1) # 1 = TA_CENTER correto
                 
    p_val = Paragraph(f"<font color='#{hex_cor}'>{valor}</font>", _s_val)
    p_lbl = Paragraph(label, _s_lbl)
    
    # RESOLUÇÃO DA ASSIMETRIA: Fixamos rigidamente a altura das duas linhas (26pt para o valor, 14pt para o label)
    # Isso garante que todos os 6 retângulos tenham exatamente 40pt de altura útil, independente da fonte interna.
    t = Table([[p_val], [p_lbl]], colWidths=[largura], rowHeights=[26, 14])
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), _C["cinza"]),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),  # Centraliza os elementos na coluna da tabela
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),  # Centraliza verticalmente o texto no retângulo
        ("LINEAFTER",     (0, 0), (0, -1),  2.5, cor_borda),
        # Zera os paddings agressivos para o rowHeights assumir o controle simétrico
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING",   (0, 0), (-1, -1), 2),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 2),
    ]))
    return t


def _barra_progresso(
    valor: float, maximo: float = 10.0,
    largura: float = 5.2 * cm, altura: float = 0.38 * cm,
) -> Drawing:
    d   = Drawing(largura, altura)
    pct = min(valor / maximo, 1.0)
    cor = _cor_nota(valor)
    d.add(Rect(0, 0, largura, altura, fillColor=_C["cinza2"], strokeColor=None, strokeWidth=0))
    if pct > 0:
        d.add(Rect(0, 0, largura * pct, altura, fillColor=cor, strokeColor=None, strokeWidth=0))
    return d


def _cor_nota_local(nota: float) -> colors.Color:
    if nota >= 8:            return _C["verde"]
    if nota >= NOTA_MINIMA:  return _C["amarelo"]
    return _C["verm"]


def _pdf_radar_chart(
    criterios: list,
    vals_aluno: list,
    vals_turma: list | None,
    largura: float = 240,
    altura: float = 210,
) -> Drawing:
    d = Drawing(largura, altura)
    n = len(criterios)
    if n < 3:
        return d

    cx   = largura / 2
    cy   = altura / 2 - 4
    raio = min(cx, cy) - 40

    for nv in [2, 4, 6, 8, 10]:
        r = raio * (nv / 10.0)
        pts = []
        for i in range(n):
            ang = math.pi / 2 - 2 * math.pi * i / n
            pts += [cx + r * math.cos(ang), cy + r * math.sin(ang)]
        pts += [pts[0], pts[1]]
        d.add(PolyLine(pts, strokeColor=_C["cinza2"], strokeWidth=0.5))
        ang0 = math.pi / 2
        lx = cx + r * math.cos(ang0) + 2
        ly = cy + r * math.sin(ang0) - 4
        d.add(String(lx, ly, str(nv),
                     fontSize=5.5, fillColor=_C["cinza4"], fontName="Helvetica"))

    for i in range(n):
        ang = math.pi / 2 - 2 * math.pi * i / n
        d.add(Line(cx, cy,
                   cx + raio * math.cos(ang), cy + raio * math.sin(ang),
                   strokeColor=_C["cinza2"], strokeWidth=0.5))

    r_min = raio * (NOTA_MINIMA / 10.0)
    pts_min = []
    for i in range(n):
        ang = math.pi / 2 - 2 * math.pi * i / n
        pts_min += [cx + r_min * math.cos(ang), cy + r_min * math.sin(ang)]
    pts_min += [pts_min[0], pts_min[1]]
    d.add(PolyLine(pts_min, strokeColor=_C["verm"], strokeWidth=1.0,
                   strokeDashArray=[3, 2]))

    if vals_turma:
        pts_t = []
        for i, v in enumerate(vals_turma):
            ang = math.pi / 2 - 2 * math.pi * i / n
            r   = raio * (min(float(v or 0), 10.0) / 10.0)
            pts_t += [cx + r * math.cos(ang), cy + r * math.sin(ang)]
        d.add(Polygon(pts_t,
                      fillColor=colors.HexColor("#94A3B820", hasAlpha=True),
                      strokeColor=_C["cinza3"], strokeWidth=1.0))

    pts_a = []
    for i, v in enumerate(vals_aluno):
        ang = math.pi / 2 - 2 * math.pi * i / n
        r   = raio * (min(float(v or 0), 10.0) / 10.0)
        pts_a += [cx + r * math.cos(ang), cy + r * math.sin(ang)]
    d.add(Polygon(pts_a,
                  fillColor=colors.HexColor("#00539F25", hasAlpha=True),
                  strokeColor=_C["azul"], strokeWidth=1.8))

    for i, v in enumerate(vals_aluno):
        ang = math.pi / 2 - 2 * math.pi * i / n
        r   = raio * (min(float(v or 0), 10.0) / 10.0)
        px  = cx + r * math.cos(ang)
        py  = cy + r * math.sin(ang)
        cor = _cor_nota_local(v)
        d.add(Circle(px, py, 3.5,
                     fillColor=cor, strokeColor=colors.white, strokeWidth=0.8))
        dx = 7 * math.cos(ang)
        dy = 7 * math.sin(ang)
        d.add(String(px + dx, py + dy - 2.5, f"{v:.1f}",
                     fontSize=6.5, fillColor=cor,
                     fontName="Helvetica-Bold", textAnchor="middle"))

    for i, crit in enumerate(criterios):
        ang   = math.pi / 2 - 2 * math.pi * i / n
        dist  = raio + 16
        lx    = cx + dist * math.cos(ang)
        ly    = cy + dist * math.sin(ang)
        label = str(crit).replace("Leórica", "Teórica")
        palavras = label.split()
        if len(palavras) > 2:
            meio  = (len(palavras) + 1) // 2
            linhas = [" ".join(palavras[:meio]), " ".join(palavras[meio:])]
        else:
            linhas = [label]
        for k, linha in enumerate(linhas):
            offset = (len(linhas) - 1) * 3.5 - k * 7
            d.add(String(lx, ly + offset, linha,
                         fontSize=6.5, fillColor=_C["texto"],
                         fontName="Helvetica-Bold", textAnchor="middle"))

    leg_y = 8
    d.add(Rect(4, leg_y, 10, 5,
               fillColor=colors.HexColor("#00539F25", hasAlpha=True),
               strokeColor=_C["azul"], strokeWidth=1.2))
    d.add(String(17, leg_y, "Aluno",
                 fontSize=6, fillColor=_C["texto2"], fontName="Helvetica"))
    if vals_turma:
        d.add(Rect(50, leg_y, 10, 5,
                   fillColor=colors.HexColor("#94A3B820", hasAlpha=True),
                   strokeColor=_C["cinza3"], strokeWidth=1.0))
        d.add(String(63, leg_y, "Turma",
                     fontSize=6, fillColor=_C["texto2"], fontName="Helvetica"))
    d.add(Line(largura - 66, leg_y + 2.5, largura - 54, leg_y + 2.5,
               strokeColor=_C["verm"], strokeWidth=1.0, strokeDashArray=[3, 2]))
    d.add(String(largura - 51, leg_y, f"Mínimo ({NOTA_MINIMA:.0f})",
                 fontSize=6, fillColor=_C["verm"], fontName="Helvetica"))

    return d


def _pdf_bar_bimestre(
    bim_df: pd.DataFrame,
    largura: float = 220,
    altura: float = 165,
) -> Drawing:
    if bim_df.empty:
        return Drawing(largura, altura)

    d      = Drawing(largura, altura)
    medias = [float(v) for v in bim_df["Média"].tolist()]
    labels = bim_df["Semana"].tolist()
    n      = len(medias)

    pad_l, pad_r, pad_b, pad_t = 30, 10, 34, 14
    w = largura - pad_l - pad_r
    h = altura  - pad_b - pad_t

    gap   = w / n
    bar_w = min(gap * 0.65, 22.0)

    for nv in [2, 4, 6, 8, 10]:
        yg = pad_b + (nv / 10.0) * h
        d.add(Line(pad_l, yg, pad_l + w, yg,
                   strokeColor=_C["cinza2"], strokeWidth=0.4))
        d.add(String(pad_l - 3, yg - 3, str(nv),
                     fontSize=6, fillColor=_C["cinza4"],
                     fontName="Helvetica", textAnchor="end"))

    y6 = pad_b + (NOTA_MINIMA / 10.0) * h
    d.add(Line(pad_l, y6, pad_l + w, y6,
               strokeColor=_C["verm"], strokeWidth=1.0,
               strokeDashArray=[4, 3]))

    d.add(Line(pad_l, pad_b, pad_l + w, pad_b,
               strokeColor=_C["cinza3"], strokeWidth=0.6))

    def _cx(i): return pad_l + gap * i + gap / 2

    for i in range(n - 1):
        y1 = pad_b + (medias[i]     / 10.0) * h
        y2 = pad_b + (medias[i + 1] / 10.0) * h
        d.add(Line(_cx(i), y1, _cx(i + 1), y2,
                   strokeColor=_C["azul"], strokeWidth=1.2,
                   strokeDashArray=[3, 2]))

    tem_total = "Total" in bim_df.columns
    for i, m in enumerate(medias):
        cor = _cor_nota_local(m)
        cx  = _cx(i)
        bx  = cx - bar_w / 2
        bh  = (m / 10.0) * h
        d.add(Rect(bx, pad_b, bar_w, bh,
                   fillColor=colors.HexColor(cor.hexval()[:7] + "BB"),
                   strokeColor=cor, strokeWidth=0.8))
        if bh >= 14:
            d.add(String(cx, pad_b + bh - 10, f"{m:.1f}",
                         fontSize=7, fillColor=colors.white,
                         fontName="Helvetica-Bold", textAnchor="middle"))
        else:
            d.add(String(cx, pad_b + bh + 3, f"{m:.1f}",
                         fontSize=7, fillColor=cor,
                         fontName="Helvetica-Bold", textAnchor="middle"))
        d.add(Circle(cx, pad_b + bh, 3,
                     fillColor=cor, strokeColor=colors.white, strokeWidth=0.8))
        lbl_curto = (labels[i]
                     .replace("2026-", "").replace("2025-", "").replace("2024-", ""))
        d.add(String(cx, pad_b - 11, lbl_curto,
                     fontSize=6, fillColor=_C["texto2"],
                     fontName="Helvetica", textAnchor="middle"))
        if tem_total:
            total = int(bim_df.iloc[i].get("Total", 0))
            d.add(String(cx, pad_b - 20, f"({total} av.)",
                         fontSize=5.5, fillColor=_C["cinza4"],
                         fontName="Helvetica", textAnchor="middle"))


def _gerar_recomendacoes(
    risco: str, tendencia: str, seq_critica: int,
    notas_baixas: int, total_avals: int, media: float, media_pond: float,
) -> list[tuple[str, str]]:
    """Retorna lista de (emoji, texto) com recomendações pedagógicas personalizadas."""
    recs = []
    pct_baixas = notas_baixas / total_avals if total_avals > 0 else 0

    if seq_critica >= 3:
        recs.append(("🚨", f"Convocar o aluno para reunião de intervenção pedagógica urgente — "
                           f"{seq_critica} avaliações seguidas abaixo da média mínima."))
    if risco == "critico":
        recs.append(("📋", "Elaborar Plano de Desenvolvimento Individual (PDI) com metas claras e prazos definidos."))
        recs.append(("👥", "Articular com equipe pedagógica e família para suporte externo ao processo de aprendizagem."))
    if tendencia == "queda":
        recs.append(("📉", "Investigar possíveis fatores externos (saúde, trabalho, vida pessoal) que possam estar afetando o desempenho."))
        recs.append(("🔄", "Revisar metodologia de ensino para os conteúdos com maior índice de notas baixas."))
    if pct_baixas > 0.30:
        recs.append(("📚", f"{pct_baixas*100:.0f}% das avaliações estão abaixo de {NOTA_MINIMA:.0f},0 — "
                           f"programar atividades de reforço focadas nos critérios deficientes."))
    if risco == "atencao":
        recs.append(("⚠️", "Monitorar o aluno nas próximas avaliações com feedback individualizado após cada atividade."))
        recs.append(("💬", "Realizar conversa motivacional e identificar eventuais dificuldades específicas por critério."))
    if tendencia == "melhora":
        recs.append(("✅", "Manter o aluno motivado reconhecendo sua evolução positiva — reforço positivo é fundamental."))
    if risco in ("adequado", "excelente"):
        recs.append(("🌟", "Aluno em situação positiva — considerar desafios adicionais ou atividades de extensão para potencializar o desenvolvimento."))
    if abs(media - media_pond) > 0.5:
        melhor = "Fazer" if media_pond > media else "teórico"
        recs.append(("⚖️", f"Diferença significativa entre média simples e ponderada — atentar ao equilíbrio entre vetores; o aluno se sai melhor em atividades de {melhor}."))

    if not recs:
        recs.append(("📌", "Continuar acompanhamento regular do aluno, mantendo feedback constante e qualificado."))

    return recs[:6]


def _tabela_recomendacoes(recs: list[tuple[str, str]]) -> Table:
    """Tabela de recomendações com fundo alternado."""
    rows = [[Paragraph("<b>Recomendações Pedagógicas</b>", _S_RECOM_TIT), ""]]
    header_style = [
        ("BACKGROUND",    (0, 0), (-1, 0), _C["amarelo"]),
        ("SPAN",          (0, 0), (-1, 0)),
        ("TOPPADDING",    (0, 0), (-1, 0), 7),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 7),
        ("LEFTPADDING",   (0, 0), (-1, 0), 10),
    ]
    data_style = [
        ("FONTSIZE",      (0, 1), (-1, -1), 8),
        ("GRID",          (0, 1), (-1, -1), 0.25, _C["cinza2"]),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",   (0, 1), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 1), (-1, -1), 8),
        ("TOPPADDING",    (0, 1), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
    ]
    for i, (emoji, texto) in enumerate(recs, start=1):
        rows.append([Paragraph(emoji, _S_BODY_C), Paragraph(texto, _S_RECOM)])
        if i % 2 == 0:
            data_style.append(("BACKGROUND", (0, i), (-1, i), _C["cinza"]))

    t = Table(rows, colWidths=[0.8 * cm, _LARGURA - 0.8 * cm])
    t.setStyle(TableStyle(header_style + data_style))
    return t

def _pdf_freq_calendar(df_cal: pd.DataFrame, largura: float = 400, altura: float = None) -> Drawing:
    """Grid semanas × dias com cores: verde=Presente, vermelho=Falta, cinza=Feriado."""
    from reportlab.graphics.shapes import String as RLString
    if df_cal is None or df_cal.empty:
        return Drawing(largura, 20)

    df = df_cal.dropna(subset=["Data", "Status"]).copy()
    if df.empty:
        return Drawing(largura, 20)

    df["_data"] = pd.to_datetime(df["Data"])
    df["_dow"]  = df["_data"].dt.dayofweek
    df["_week"] = df["_data"].apply(
        lambda d: f"{d.isocalendar().year}-S{d.isocalendar().week:02d}"
    )

    semanas   = sorted(df["_week"].unique())
    dias_map  = {0: "Seg", 1: "Ter", 2: "Qua", 3: "Qui", 4: "Sex", 5: "Sáb"}
    cols_used = sorted([c for c in df["_dow"].unique() if c in dias_map])
    pivot     = df.pivot_table(index="_week", columns="_dow", values="Status", aggfunc="first")

    n_sem   = len(semanas)
    n_col   = len(cols_used)
    cell_w  = max(14, min(20, int((largura - 62) / max(n_col, 1))))
    cell_h  = 11
    label_w = 56
    header_h = 16
    legend_h = 14

    total_h = altura or (header_h + n_sem * cell_h + legend_h + 4)
    d       = Drawing(largura, total_h)

    cor_pres  = colors.HexColor("#059669")
    cor_falta = colors.HexColor("#E30613")
    cor_fer   = colors.HexColor("#D1D5DB")
    cor_vazio = colors.HexColor("#F3F4F6")
    cor_txt   = colors.HexColor("#6B7280")

    base_y = legend_h + 4

    for j, dow in enumerate(cols_used):
        x = label_w + j * cell_w
        d.add(RLString(x + cell_w / 2, base_y + n_sem * cell_h + 4,
                       dias_map[dow], fontSize=6, fillColor=colors.HexColor("#374151"),
                       textAnchor="middle"))

    for i, sem in enumerate(semanas):
        y      = base_y + (n_sem - 1 - i) * cell_h
        label  = sem[-5:] if len(sem) > 5 else sem
        d.add(RLString(label_w - 3, y + 3, label,
                       fontSize=5, fillColor=cor_txt, textAnchor="end"))
        for j, dow in enumerate(cols_used):
            x   = label_w + j * cell_w
            val = None
            if dow in pivot.columns and sem in pivot.index:
                v = pivot.loc[sem, dow]
                if not pd.isna(v):
                    val = v
            cor = cor_pres if val == "Presente" else (
                  cor_falta if val == "Falta" else (
                  cor_fer   if val == "Feriado" else cor_vazio))
            d.add(Rect(x + 1, y + 1, cell_w - 2, cell_h - 2,
                       fillColor=cor, strokeColor=colors.white, strokeWidth=0.5))

    lx = label_w
    for txt, cor in [("Presente", cor_pres), ("Falta", cor_falta), ("Feriado", cor_fer)]:
        d.add(Rect(lx, 3, 8, 8, fillColor=cor, strokeColor=None, strokeWidth=0))
        d.add(RLString(lx + 11, 4, txt, fontSize=5.5, fillColor=cor_txt))
        lx += 52

    return d


def _pdf_line_turma(
    sem_df: pd.DataFrame,
    largura: float = 480,
    altura: float = 175,
) -> Drawing:
    """Linha da média semanal da turma + barra do nº de avaliações abaixo do mínimo."""
    d = Drawing(largura, altura)
    if sem_df is None or sem_df.empty:
        return d

    df_plot = sem_df.tail(14).copy()
    medias  = [float(v) for v in df_plot["Média"].tolist()]
    labels  = df_plot["Semana"].tolist()
    totais  = ([int(v) for v in df_plot["Total"].tolist()]
               if "Total" in df_plot.columns else [0] * len(medias))
    n = len(medias)
    if n < 1:
        return d

    pad_l, pad_r, pad_b, pad_t = 32, 14, 34, 16
    w = largura - pad_l - pad_r
    h = altura  - pad_b - pad_t

    def _x(i): return pad_l + (i * w / max(n - 1, 1))
    def _y(v): return pad_b + (v / 10.0) * h

    y6 = _y(NOTA_MINIMA)
    d.add(Rect(pad_l, pad_b, w, y6 - pad_b,
               fillColor=colors.HexColor("#FEE2E2"), strokeColor=None, strokeWidth=0))

    for nv in [0, 2, 4, 6, 8, 10]:
        yg = _y(nv)
        d.add(Line(pad_l, yg, pad_l + w, yg,
                   strokeColor=_C["cinza2"] if nv != 0 else _C["cinza3"],
                   strokeWidth=0.4 if nv != 0 else 0.6))
        d.add(String(pad_l - 3, yg - 3, str(nv),
                     fontSize=6, fillColor=_C["cinza4"],
                     fontName="Helvetica", textAnchor="end"))

    d.add(Line(pad_l, y6, pad_l + w, y6,
               strokeColor=_C["verm"], strokeWidth=1.0, strokeDashArray=[4, 3]))

    if n > 1:
        for i in range(n - 1):
            d.add(Line(_x(i), _y(medias[i]), _x(i + 1), _y(medias[i + 1]),
                       strokeColor=_C["azul"], strokeWidth=1.8))

    for i, v in enumerate(medias):
        cor    = _cor_nota_local(v)
        px, py = _x(i), _y(v)
        d.add(Circle(px, py, 3.6,
                     fillColor=cor, strokeColor=colors.white, strokeWidth=1.0))
        acima = py < _y(9.0)
        oy    = 7 if acima else -9
        d.add(String(px, py + oy, f"{v:.1f}",
                     fontSize=6.5, fillColor=cor,
                     fontName="Helvetica-Bold", textAnchor="middle"))

    for i, sem in enumerate(labels):
        lbl = sem[-3:] if len(sem) > 3 else sem
        px  = _x(i)
        d.add(Line(px, pad_b, px, pad_b - 3, strokeColor=_C["cinza3"], strokeWidth=0.5))
        d.add(String(px, pad_b - 12, lbl,
                     fontSize=6, fillColor=_C["texto2"],
                     fontName="Helvetica", textAnchor="middle"))
        if totais[i]:
            d.add(String(px, pad_b - 21, f"{totais[i]}av",
                         fontSize=5, fillColor=_C["cinza4"],
                         fontName="Helvetica", textAnchor="middle"))

    d.add(Line(pad_l, pad_b, pad_l + w, pad_b, strokeColor=_C["cinza3"], strokeWidth=0.6))

    leg_y = altura - 9
    d.add(Line(pad_l, leg_y, pad_l + 14, leg_y, strokeColor=_C["azul"], strokeWidth=1.8))
    d.add(String(pad_l + 17, leg_y - 3, "Média semanal da turma",
                 fontSize=6.5, fillColor=_C["texto2"], fontName="Helvetica"))
    d.add(Line(pad_l + 140, leg_y, pad_l + 154, leg_y,
               strokeColor=_C["verm"], strokeWidth=1.0, strokeDashArray=[4, 3]))
    d.add(String(pad_l + 157, leg_y - 3, f"Mínimo ({NOTA_MINIMA:.0f})",
                 fontSize=6.5, fillColor=_C["verm"], fontName="Helvetica"))
    return d


def _pdf_barra_risco(
    n_crit: int, n_at: int, n_adeq: int, n_exc: int,
    largura: float = 480, altura: float = 58,
) -> Drawing:
    """Barra horizontal empilhada da distribuição de risco da turma."""
    d = Drawing(largura, altura)
    total = n_crit + n_at + n_adeq + n_exc
    if total <= 0:
        return d

    segs = [
        (n_crit, _C["verm"],    "Crítico"),
        (n_at,   _C["amarelo"], "Atenção"),
        (n_adeq, _C["verde"],   "Adequado"),
        (n_exc,  _C["roxo"],    "Excelente"),
    ]

    bar_h = 22
    bar_y = altura - bar_h - 4
    x     = 0
    for val, cor, _lbl in segs:
        if val <= 0:
            continue
        seg_w = largura * (val / total)
        d.add(Rect(x, bar_y, seg_w, bar_h, fillColor=cor, strokeColor=colors.white, strokeWidth=1.0))
        if seg_w >= 22:
            d.add(String(x + seg_w / 2, bar_y + bar_h / 2 - 3.5,
                         f"{val}", fontSize=9, fillColor=colors.white,
                         fontName="Helvetica-Bold", textAnchor="middle"))
            d.add(String(x + seg_w / 2, bar_y + bar_h / 2 + 6,
                         f"{val/total*100:.0f}%", fontSize=5.5, fillColor=colors.white,
                         fontName="Helvetica", textAnchor="middle"))
        x += seg_w

    lx = 0
    for val, cor, lbl in segs:
        d.add(Rect(lx, 2, 9, 9, fillColor=cor, strokeColor=None, strokeWidth=0))
        d.add(String(lx + 13, 3, f"{lbl} ({val})",
                     fontSize=6.5, fillColor=_C["texto2"], fontName="Helvetica"))
        lx += largura / 4
    return d


def _pdf_line_chart_evolucao(
    df_al: pd.DataFrame,
    largura: float = 220,
    altura: float = 165,
) -> Drawing:
    if df_al.empty:
        return Drawing(largura, altura)

    d = Drawing(largura, altura)

    pad_l, pad_r, pad_b, pad_t = 30, 14, 30, 14
    w = largura - pad_l - pad_r
    h = altura  - pad_b - pad_t

    df_plot = df_al.sort_values("Data").tail(12).copy()
    notas   = [float(v) for v in df_plot["Nota"].tolist()]
    n       = len(notas)
    if n < 1:
        return d

    def _x(i): return pad_l + (i * w / max(n - 1, 1))
    def _y(v): return pad_b + (v / 10.0) * h

    y6 = _y(NOTA_MINIMA)
    d.add(Rect(pad_l, pad_b, w, y6 - pad_b,
               fillColor=colors.HexColor("#FEE2E2"),
               strokeColor=None, strokeWidth=0))

    for nv in [0, 2, 4, 6, 8, 10]:
        yg = _y(nv)
        d.add(Line(pad_l, yg, pad_l + w, yg,
                   strokeColor=_C["cinza2"] if nv != 0 else _C["cinza3"],
                   strokeWidth=0.4 if nv != 0 else 0.6))
        d.add(String(pad_l - 3, yg - 3, str(nv),
                     fontSize=6, fillColor=_C["cinza4"],
                     fontName="Helvetica", textAnchor="end"))

    d.add(Line(pad_l, y6, pad_l + w, y6,
               strokeColor=_C["verm"], strokeWidth=1.0,
               strokeDashArray=[4, 3]))
    d.add(String(pad_l + w + 2, y6 - 3, "6",
                 fontSize=5.5, fillColor=_C["verm"], fontName="Helvetica-Bold"))

    alpha = 2.0 / (4 + 1)
    ema   = [notas[0]]
    for v in notas[1:]:
        ema.append(alpha * v + (1 - alpha) * ema[-1])
    if n > 1:
        for i in range(n - 1):
            d.add(Line(_x(i), _y(ema[i]), _x(i + 1), _y(ema[i + 1]),
                       strokeColor=_C["amarelo"], strokeWidth=1.3,
                       strokeDashArray=[3, 2]))

    if n > 1:
        for i in range(n - 1):
            d.add(Line(_x(i), _y(notas[i]), _x(i + 1), _y(notas[i + 1]),
                       strokeColor=_C["azul"], strokeWidth=1.8))

    for i, v in enumerate(notas):
        cor    = _cor_nota_local(v)
        px, py = _x(i), _y(v)
        d.add(Circle(px, py, 3.8,
                     fillColor=cor, strokeColor=colors.white, strokeWidth=1.0))
        acima = py < _y(9.0)
        oy    = 7 if acima else -9
        d.add(String(px, py + oy, f"{v:.1f}",
                     fontSize=6.5, fillColor=cor,
                     fontName="Helvetica-Bold", textAnchor="middle"))

    datas    = df_plot["Data"].dt.strftime("%d/%m").tolist()
    contagem: dict = {}
    for i, dt in enumerate(datas):
        contagem[dt] = contagem.get(dt, 0) + 1
        label = dt if contagem[dt] == 1 else f"{dt}·{contagem[dt]}"
        px    = _x(i)
        d.add(Line(px, pad_b, px, pad_b - 3,
                   strokeColor=_C["cinza3"], strokeWidth=0.5))
        d.add(String(px, pad_b - 12, label,
                     fontSize=5.5, fillColor=_C["texto2"],
                     fontName="Helvetica", textAnchor="middle"))

    d.add(Line(pad_l, pad_b, pad_l + w, pad_b,
               strokeColor=_C["cinza3"], strokeWidth=0.6))

    leg_y = altura - 8
    d.add(Line(pad_l, leg_y, pad_l + 14, leg_y,
               strokeColor=_C["azul"], strokeWidth=1.8))
    d.add(String(pad_l + 17, leg_y - 3, "Notas",
                 fontSize=6, fillColor=_C["texto2"], fontName="Helvetica"))
    d.add(Line(pad_l + 50, leg_y, pad_l + 64, leg_y,
               strokeColor=_C["amarelo"], strokeWidth=1.3,
               strokeDashArray=[3, 2]))
    d.add(String(pad_l + 67, leg_y - 3, "Tendência (EMA)",
                 fontSize=6, fillColor=_C["texto2"], fontName="Helvetica"))

    return d
