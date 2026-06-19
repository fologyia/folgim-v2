import os
from collections import defaultdict
from datetime import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import time
import numpy as np

from config import CORES, FREQ_MINIMA_PCT, NOTA_MINIMA, SEQUENCIA_CRITICA_MIN
from data.analysis import (
    analisar_freq_notas,
    agrupar_por_semana,
    calcular_frequencia_aluno,
    calcular_media_ponderada,
    calcular_notas_por_vetor,
    calcular_ranking,
    classificar_risco,
    detectar_sequencia_critica,
    detectar_tendencia,
    gerar_diagnostico,
)
import hashlib
import json

from groq import Groq

from data.export import gerar_excel
from pdf.generator import gerar_boletim_pdf, gerar_relatorio_individual_ia_pdf
from ui.components import divider, render_freq_card, section_title
from utils import coluna_criterio, coluna_uc, nota_formatada


# ══════════════════════════════════════════════════════════════════════════════
# ABA 1 — VISÃO GERAL
# ══════════════════════════════════════════════════════════════════════════════
def _tab_geral(
    df_aluno: pd.DataFrame, df_turma: pd.DataFrame,
    col_crit: str, col_uc: str, aluno_sel: str, comparar_turma: bool,
    freq_aluno: dict, media_aluno: float, media_pond: float,
    notas_baixas: int, total_avals: int, tend_label: str, tend_cor: str,
    seq_critica: int, bimestres: pd.DataFrame,
    posicao: int | None, total_alunos: int,
    tendencia: str, delta_turma: float, media_turma: float,
) -> None:
    c1, c2, c3 = st.columns(3)

    mp_cor = "#FF3B30" if media_pond < NOTA_MINIMA else ("#F59E0B" if media_pond < 7 else "#34C759")
    with c1:
        st.markdown(
            f'<div class="apple-kpi" style="border-left:3px solid {mp_cor}">'
            f'<div class="apple-label">Média Ponderada</div>'
            f'<div style="display:flex;align-items:baseline;gap:5px;margin-top:6px">'
            f'<span class="apple-value" style="color:{mp_cor}">{media_pond:.1f}</span>'
            f'<span style="font-size:14px;color:#8E8E93">/10</span>'
            f'<span style="margin-left:auto;font-size:12px;color:{tend_cor};font-weight:500">{tend_label}</span>'
            f'</div>'
            f'<div style="margin-top:10px;height:4px;background:#F2F2F7;border-radius:2px">'
            f'<div style="width:{min(100,media_pond*10):.0f}%;height:4px;background:{mp_cor};border-radius:2px"></div>'
            f'</div>'
            f'<div style="display:flex;justify-content:space-between;margin-top:3px">'
            f'<span style="font-size:10px;color:#C7C7CC">0</span>'
            f'<span style="font-size:10px;color:#C7C7CC">mín. 6.0</span>'
            f'<span style="font-size:10px;color:#C7C7CC">10</span>'
            f'</div></div>',
            unsafe_allow_html=True,
        )

    freq_cor          = freq_aluno["cor"] if freq_aluno["tem_dados"] else "#8E8E93"
    freq_pct          = f'{freq_aluno["pct_presenca"]:.1f}%' if freq_aluno["tem_dados"] else "—"
    freq_status_label = {
        "excelente":"regular","adequado":"regular","atencao":"atenção",
        "critico":"crítico","sem_dados":"sem dados",
    }.get(freq_aluno["status"], "—")
    with c2:
        st.markdown(
            f'<div class="apple-kpi" style="border-left:3px solid {freq_cor}">'
            f'<div class="apple-label">Frequência</div>'
            f'<div style="display:flex;align-items:baseline;gap:5px;margin-top:6px">'
            f'<span class="apple-value" style="color:{freq_cor}">{freq_pct}</span>'
            f'<span style="margin-left:auto;font-size:12px;color:{freq_cor};font-weight:500">{freq_status_label}</span>'
            f'</div>'
            f'<div style="margin-top:10px;height:4px;background:#F2F2F7;border-radius:2px">'
            f'<div style="width:{min(100, freq_aluno["pct_presenca"] if freq_aluno["tem_dados"] else 0):.0f}%;height:4px;background:{freq_cor};border-radius:2px"></div>'
            f'</div>'
            f'<div style="display:flex;justify-content:space-between;margin-top:3px">'
            f'<span style="font-size:10px;color:#C7C7CC">0%</span>'
            f'<span style="font-size:10px;color:#C7C7CC">mín. 75%</span>'
            f'<span style="font-size:10px;color:#C7C7CC">100%</span>'
            f'</div></div>',
            unsafe_allow_html=True,
        )

    with c3:
        st.markdown(
            f'<div class="apple-kpi" style="border-left:3px solid {"#FF3B30" if notas_baixas > 0 else "#34C759"}">'
            f'<div class="apple-label">Alertas</div>'
            f'<div style="display:flex;align-items:baseline;gap:8px;margin-top:6px">'
            f'<span class="apple-value" style="color:{"#FF3B30" if notas_baixas > 0 else "#34C759"}">{notas_baixas}</span>'
            f'<span style="font-size:14px;color:#8E8E93">notas abaixo de {NOTA_MINIMA:.0f}</span>'
            f'</div>'
            f'<div style="margin-top:10px;height:4px;background:#F2F2F7;border-radius:2px">'
            f'<div style="margin-top:10px;font-size:12px;color:{"#FF3B30" if notas_baixas > 0 else "#34C759"};'
            f'background:{"#FFF5F5" if notas_baixas > 0 else "#F0FDF4"};border-radius:6px;padding:4px 10px;display:inline-block;font-weight:500">'
            f'{"%.0f%% das avaliações" % (notas_baixas/total_avals*100) if total_avals > 0 else "sem alertas"}'
            f'</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    diag = gerar_diagnostico(
        aluno_sel, media_aluno, media_pond, tendencia, notas_baixas,
        total_avals, seq_critica, delta_turma, posicao, total_alunos,
        bimestres, df_aluno,
    )

    col_diag, col_radar = st.columns(2)

    with col_diag:
        _risco_bg2 = {"critico":"#FFF5F5","atencao":"#FFFBEB","adequado":"#F0FDF4","excelente":"#F0F9FF"}
        _risco_bd2 = {"critico":"#FF3B30","atencao":"#F59E0B","adequado":"#34C759","excelente":"#007AFF"}

        _key_expandido = f"diag_expandido_{aluno_sel}"
        if _key_expandido not in st.session_state:
            st.session_state[_key_expandido] = False

        _expandido   = st.session_state[_key_expandido]
        _texto_exib  = diag["texto"] if _expandido else diag["texto_resumido"]
        _btn_label   = "▲ Resumir" if _expandido else "▼ Ver diagnóstico completo"

        tags_html2 = "".join(
            f'<span style="font-size:11px;font-weight:600;padding:3px 10px;border-radius:50px;'
            f'margin-right:5px;margin-bottom:5px;display:inline-block;'
            f'background:{"#F0FDF4" if t=="positivo" else ("#FFF5F5" if t=="negativo" else "#F2F2F7")};'
            f'color:{"#15803D" if t=="positivo" else ("#DC2626" if t=="negativo" else "#48484A")}">{label}</span>'
            for label, t in diag["tags"]
        )
        _proj_html = ""
        if diag.get("projecao"):
            _proj_map = {
                "aprovado_folga":  ("✅ No ritmo atual: Aprovado com folga", "#15803D", "#F0FDF4"),
                "aprovado_margem": ("✅ No ritmo atual: Aprovado (margem curta)", "#92400E", "#FEF3C7"),
                "aprovado_risco":  ("⚠️ No ritmo atual: Em risco de não aprovação", "#C2410C", "#FFF7ED"),
                "reprovado":       ("❌ No ritmo atual: Risco elevado de reprovação", "#991B1B", "#FEF2F2"),
            }
            _plabel, _pcor, _pbg = _proj_map.get(diag["projecao"], ("", "", ""))
            if _plabel:
                _proj_html = (
                    f'<div style="margin-top:10px;padding:7px 12px;border-radius:8px;'
                    f'background:{_pbg};color:{_pcor};font-size:12px;font-weight:700;'
                    f'border:1px solid {_pcor}30">{_plabel}</div>'
                )
        st.markdown("".join([
            f'<div class="apple-card" style="border-left:4px solid {_risco_bd2[diag["risco"]]};'
            f'background:{_risco_bg2[diag["risco"]]};height:100%">'
            f'<div class="apple-label">Diagnóstico Automático</div>'
            f'<p style="font-size:14px;line-height:1.75;color:#1D1D1F;margin:0 0 12px">{_texto_exib}</p>'
            f'<div style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:4px">{tags_html2}</div>'
            f'{_proj_html}'
            '</div>',
        ]), unsafe_allow_html=True)

        if st.button(
            _btn_label,
            key=f"btn_diag_{aluno_sel}",
            width="stretch",
        ):
            st.session_state[_key_expandido] = not _expandido
            st.rerun()

    with col_radar:
        criterios = sorted(df_aluno[col_crit].dropna().unique().tolist()) if col_crit in df_aluno.columns else []
        if criterios:
            vals_aluno_r = [df_aluno[df_aluno[col_crit] == c]["Nota"].mean() or 0 for c in criterios]
            vals_turma_r = [df_turma[df_turma[col_crit] == c]["Nota"].mean() or 0 for c in criterios]
            c_fechado    = criterios + [criterios[0]]
            va           = vals_aluno_r + [vals_aluno_r[0]]
            vt           = vals_turma_r + [vals_turma_r[0]]
            fig_radar_g  = go.Figure()
            
            # [MODIFICAÇÃO] Adicionada a linha de mínimo tracejada para consistência visual com a Aba 2
            _min_vals_g = [NOTA_MINIMA] * len(criterios) + [NOTA_MINIMA]
            fig_radar_g.add_trace(go.Scatterpolar(
                r=_min_vals_g, theta=c_fechado, fill="toself", name=f"Mínimo ({NOTA_MINIMA:.0f})",
                line=dict(color="#FF3B30", width=1.5, dash="dot"), fillcolor="rgba(255,59,48,0.02)",
            ))
            
            if comparar_turma:
                fig_radar_g.add_trace(go.Scatterpolar(
                    r=vt, theta=c_fechado, fill="toself", name="Média Turma",
                    line=dict(color="#C7C7CC", width=1.5), fillcolor="rgba(199,199,204,0.12)",
                ))
            fig_radar_g.add_trace(go.Scatterpolar(
                r=va, theta=c_fechado, fill="toself", name=aluno_sel,
                line=dict(color="#007AFF", width=2.5), fillcolor="rgba(0,122,255,0.12)",
                marker=dict(color="#007AFF", size=5),
            ))
            fig_radar_g.update_layout(
                polar=dict(
                    radialaxis=dict(visible=True, range=[0, 10], tickfont=dict(size=8),
                                    gridcolor="#F2F2F7", linecolor="#E5E5EA"),
                    angularaxis=dict(tickfont=dict(size=9, color="#48484A")),
                    bgcolor="white",
                ),
                showlegend=comparar_turma,
                legend=dict(orientation="h", y=-0.08, font=dict(size=10)),
                margin=dict(t=60, b=40, l=80, r=80),
                paper_bgcolor="white", height=340,
            )
            st.markdown('<div class="apple-card" style="padding:18px 20px"><div class="apple-label">Perfil de Habilidades</div>', unsafe_allow_html=True)
            st.plotly_chart(fig_radar_g, width="stretch")
            st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    col_evo, col_alert_g = st.columns([1.3, 1])

    with col_evo:
        # [MODIFICAÇÃO] Tratamento rigoroso de datas e substituição do rolling pela EMA sequencial por avaliação
        df_tempo_g = df_aluno.copy()
        df_tempo_g["Data_dt"] = pd.to_datetime(df_tempo_g["Data"], errors="coerce", dayfirst=True)
        df_tempo_g = df_tempo_g.dropna(subset=["Data_dt"]).sort_values("Data_dt")
        df_tempo_g["Tendência"] = df_tempo_g["Nota"].ewm(span=4, min_periods=1).mean()

        # Monta custom_data para tooltip rico
        _col_obs_ev = "Observação" if "Observação" in df_tempo_g.columns else None
        _col_uc_ev  = col_uc if col_uc in df_tempo_g.columns else None
        _cd_cols    = [c for c in [col_crit, _col_uc_ev, "Vetor (Peso)", _col_obs_ev] if c]
        _cd_data    = df_tempo_g[_cd_cols].fillna("—").values if _cd_cols else None

        cores_vet_g = {"Fazer (40%)":"#007AFF","Saber (30%)":"#FF3B30","Comport. (30%)":"#8E8E93"}
        fig_ev_g = px.scatter(
            df_tempo_g, x="Data_dt", y="Nota",
            color="Vetor (Peso)" if "Vetor (Peso)" in df_tempo_g.columns else None,
            color_discrete_map=cores_vet_g,
            custom_data=_cd_cols if _cd_cols else None,
        )
        # Monta hovertemplate dinâmico com todos os campos disponíveis
        _tmpl_lines = ["<b>%{y:.1f}</b> em %{x|%d/%m/%Y}"]
        for i, c in enumerate(_cd_cols):
            _tmpl_lines.append(f"<span style='color:#8E8E93'>{c}:</span> %{{customdata[{i}]}}")
        fig_ev_g.update_traces(
            marker=dict(size=9, line=dict(width=1.5, color="white")),
            hovertemplate="<br>".join(_tmpl_lines) + "<extra></extra>",
        )
        fig_ev_g.add_trace(go.Scatter(
            x=df_tempo_g["Data_dt"], y=df_tempo_g["Tendência"],
            mode="lines", name="Tendência",
            line=dict(color="#F59E0B", width=2.5, dash="dot"),
            hovertemplate="Tendência: <b>%{y:.1f}</b><extra></extra>",
        ))
        fig_ev_g.add_hline(y=NOTA_MINIMA, line_dash="dash", line_color="#FF3B30", line_width=1,
                           annotation_text="Mín.", annotation_position="bottom right",
                           annotation_font_size=9)
        fig_ev_g.update_layout(
            xaxis=dict(tickformat="%b/%Y", gridcolor="#F9F9F9", showgrid=True, linecolor="rgba(0,0,0,0)"),
            yaxis=dict(range=[0, 10.5], gridcolor="#F9F9F9", showgrid=True),
            legend=dict(orientation="h", y=-0.2, font=dict(size=9)),
            plot_bgcolor="white", paper_bgcolor="white",
            margin=dict(t=8, b=8, l=8, r=8), height=280,
            hoverlabel=dict(bgcolor="white", bordercolor="#E5E5EA", font_size=12),
        )
        st.markdown('<div class="apple-card"><div class="apple-label">Evolução das Notas</div>', unsafe_allow_html=True)
        st.plotly_chart(fig_ev_g, width="stretch")
        st.markdown('</div>', unsafe_allow_html=True)

    with col_alert_g:
        col_obs_alert_g = "Observação" if "Observação" in df_aluno.columns else "Observação Técnica (Log)"
        df_alertas_g    = df_aluno[df_aluno["Nota"] < NOTA_MINIMA].sort_values("Data", ascending=False)
        alert_parts = ['<div class="apple-card"><div class="apple-label">Intervenção Pedagógica</div>']
        if not df_alertas_g.empty:
            grupos = defaultdict(list)
            for _, row_a in df_alertas_g.iterrows():
                key_a = (
                    str(row_a.get(col_crit, "—")),
                    str(row_a.get("Vetor (Peso)", "—")),
                    str(row_a.get(col_obs_alert_g, "") or ""),
                )
                grupos[key_a].append(row_a["Nota"])
            for (crit_a, vet_a, obs_a), notas_a in list(grupos.items())[:5]:
                cnt   = len(notas_a)
                badge = f'<span class="apple-badge">{cnt}×</span> ' if cnt > 1 else ""
                alert_parts.append(
                    f'<div class="apple-alert-item">'
                    f'<span style="font-size:18px;line-height:1;margin-top:1px">⚠️</span>'
                    f'<div style="flex:1">'
                    f'<div style="font-size:13px;font-weight:600;color:#1D1D1F;margin-bottom:2px">{badge}{crit_a}</div>'
                    f'<div style="font-size:11px;color:#8E8E93">{vet_a}'
                    f'{" · " + obs_a[:40] if obs_a and obs_a != "nan" else ""}</div>'
                    f'</div></div>'
                )
        else:
            alert_parts.append(
                '<div style="background:#F0FDF4;border-radius:10px;padding:14px;font-size:13px;color:#15803D;text-align:center">'
                '✅ Nenhuma nota crítica</div>'
            )
        alert_parts.append('</div>')
        st.markdown("".join(alert_parts), unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# ABA 2 — DESEMPENHO
# ══════════════════════════════════════════════════════════════════════════════
def _tab_desempenho(
    df_aluno: pd.DataFrame, df_turma: pd.DataFrame,
    col_crit: str, col_uc: str, aluno_sel: str, turma_label: str,
    bimestres: pd.DataFrame, ranking: pd.DataFrame, posicao: int | None,
    media_aluno: float, media_pond: float, media_turma: float,
    notas_baixas: int, total_avals: int, delta_turma: float, seq_critica: int,
    mostrar_ranking: bool, mostrar_turma: bool,
    df_rec_aluno: pd.DataFrame, obs_geral: str,
    freq_aluno: dict | None = None,
    df_cal_aluno: pd.DataFrame | None = None,
) -> None:
    # ── SEÇÃO 1: VETORES DE COMPETÊNCIA ─────────────────────────────────────
    if "Vetor (Peso)" in df_aluno.columns:
        vetor_counts = df_aluno.groupby("Vetor (Peso)").agg(
            Contagem=("Nota", "count"), Média=("Nota", "mean"),
        ).reset_index()

        section_title("🎯 Vetores de Competência")
        vet_cols = st.columns(len(vetor_counts))
        for i, (_, vrow) in enumerate(vetor_counts.iterrows()):
            vc = "#34C759" if vrow["Média"] >= 7 else ("#F59E0B" if vrow["Média"] >= NOTA_MINIMA else "#FF3B30")
            with vet_cols[i]:
                st.markdown(
                    f'<div class="apple-vetor-card">'
                    f'<div style="font-size:12px;font-weight:600;color:#8E8E93;margin-bottom:8px">{vrow["Vetor (Peso)"]}</div>'
                    f'<div style="font-size:28px;font-weight:700;color:{vc}">{vrow["Média"]:.1f}</div>'
                    f'<div style="font-size:11px;color:#C7C7CC;margin-top:4px">{int(vrow["Contagem"])} avaliações</div>'
                    f'<div style="margin-top:10px;height:4px;background:#E5E5EA;border-radius:2px">'
                    f'<div style="width:{vrow["Média"]*10:.0f}%;height:4px;background:{vc};border-radius:2px"></div>'
                    f'</div></div>',
                    unsafe_allow_html=True,
                )
    else:
        vetor_counts = pd.DataFrame()

    # Radar de vetores
    if "Vetor (Peso)" in df_aluno.columns and not vetor_counts.empty and len(vetor_counts) >= 2:
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        _vetores_radar = vetor_counts["Vetor (Peso)"].tolist()
        _medias_radar  = vetor_counts["Média"].tolist()
        _vets_fechado  = _vetores_radar + [_vetores_radar[0]]
        _vals_fechado  = _medias_radar  + [_medias_radar[0]]
        _fig_radar_v   = go.Figure()
        _min_vals = [NOTA_MINIMA] * len(_vetores_radar) + [NOTA_MINIMA]
        _fig_radar_v.add_trace(go.Scatterpolar(
            r=_min_vals, theta=_vets_fechado, fill="toself", name=f"Mínimo ({NOTA_MINIMA:.0f})",
            line=dict(color="#FF3B30", width=1.5, dash="dot"), fillcolor="rgba(255,59,48,0.05)",
        ))
        if not df_turma.empty and "Vetor (Peso)" in df_turma.columns:
            _turma_med_v  = df_turma.groupby("Vetor (Peso)")["Nota"].mean()
            _vals_turma_v = [_turma_med_v.get(v, 0) for v in _vetores_radar] + [_turma_med_v.get(_vetores_radar[0], 0)]
            _fig_radar_v.add_trace(go.Scatterpolar(
                r=_vals_turma_v, theta=_vets_fechado, fill="toself", name="Média Turma",
                line=dict(color="#C7C7CC", width=1.5), fillcolor="rgba(199,199,204,0.12)",
            ))
        _fig_radar_v.add_trace(go.Scatterpolar(
            r=_vals_fechado, theta=_vets_fechado, fill="toself", name=aluno_sel,
            line=dict(color="#007AFF", width=2.5), fillcolor="rgba(0,122,255,0.14)",
            marker=dict(color="#007AFF", size=7),
        ))
        _fig_radar_v.update_layout(
            polar=dict(
                radialaxis=dict(visible=True, range=[0, 10], tickvals=[0,2,4,6,8,10],
                                tickfont=dict(size=8), gridcolor="#F2F2F7"),
                angularaxis=dict(tickfont=dict(size=11, color="#1D1D1F")),
                bgcolor="white",
            ),
            showlegend=True,
            legend=dict(orientation="h", y=-0.08, font=dict(size=10)),
            margin=dict(t=50, b=40, l=60, r=60),
            paper_bgcolor="white", height=320,
        )
        st.markdown(
            '<div class="apple-card" style="padding:18px 20px">'
            '<div class="apple-label">Radar Fazer · Saber · Comportamento</div>',
            unsafe_allow_html=True,
        )
        st.plotly_chart(_fig_radar_v, width="stretch")
        st.markdown('</div>', unsafe_allow_html=True)

    # ── SEÇÃO 2: ANÁLISE ESTATÍSTICA ─────────────────────────────────────────
    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    section_title("📊 Análise Estatística")
    col_box_d, col_hist_d, col_uc_d = st.columns(3)

    with col_box_d:
        st.markdown('<div class="apple-card"><div class="apple-label">Distribuição por Vetor</div>', unsafe_allow_html=True)
        if "Vetor (Peso)" in df_aluno.columns:
            fig_box_d = px.box(
                df_aluno, x="Vetor (Peso)", y="Nota", color="Vetor (Peso)",
                color_discrete_map={"Fazer (40%)":"#007AFF","Saber (30%)":"#FF3B30","Comport. (30%)":"#8E8E93"},
                points="all",
            )
            fig_box_d.update_layout(
                showlegend=False, plot_bgcolor="white", paper_bgcolor="white",
                yaxis=dict(range=[0, 10.5], gridcolor="#F9F9F9"), xaxis_title="",
                margin=dict(t=10, b=8, l=8, r=8), height=260,
            )
            fig_box_d.add_hline(y=NOTA_MINIMA, line_dash="dash", line_color="#FF3B30", line_width=1)
            st.plotly_chart(fig_box_d, width="stretch")
        else:
            st.markdown('<p style="color:#8E8E93;font-size:13px">Sem dados de vetor.</p>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col_hist_d:
        st.markdown('<div class="apple-card"><div class="apple-label">Distribuição de Notas</div>', unsafe_allow_html=True)
        fig_hist_d = px.histogram(df_aluno, x="Nota", nbins=10, color_discrete_sequence=["#007AFF"])
        fig_hist_d.update_layout(
            plot_bgcolor="white", paper_bgcolor="white",
            xaxis=dict(range=[0, 10.5], gridcolor="#F9F9F9"),
            yaxis=dict(gridcolor="#F9F9F9", dtick=1), # [MODIFICAÇÃO] dtick=1 impede frações de avaliações no eixo Y
            margin=dict(t=10, b=8, l=8, r=8), height=260, bargap=0.15,
        )
        fig_hist_d.add_vline(x=media_aluno, line_dash="dash", line_color="#F59E0B", line_width=1.5,
                             annotation_text=f"Média: {media_aluno:.1f}", annotation_position="top right",
                             annotation_font_size=9)
        st.plotly_chart(fig_hist_d, width="stretch")
        st.markdown('</div>', unsafe_allow_html=True)

    with col_uc_d:
        st.markdown('<div class="apple-card"><div class="apple-label">Média por Unidade Curricular</div>', unsafe_allow_html=True)
        if col_uc in df_aluno.columns:
            uc_media_d = (
                df_aluno.groupby(col_uc)["Nota"].mean().reset_index()
                .rename(columns={"Nota": "Média"}).sort_values("Média", ascending=True)
            )
            fig_uc_d = px.bar(
                uc_media_d, x="Média", y=col_uc, orientation="h", color="Média",
                color_continuous_scale=[[0,"#FF3B30"],[0.6,"#F59E0B"],[1,"#34C759"]], text="Média",
            )
            fig_uc_d.update_traces(texttemplate="%{text:.1f}", textposition="outside")
            fig_uc_d.update_layout(
                plot_bgcolor="white", paper_bgcolor="white",
                xaxis=dict(range=[0, 11], gridcolor="#F9F9F9"),
                yaxis_title="", coloraxis_showscale=False,
                margin=dict(t=10, b=8, l=8, r=8), height=260,
            )
            fig_uc_d.add_vline(x=NOTA_MINIMA, line_dash="dash", line_color="#C7C7CC", line_width=1)
            st.plotly_chart(fig_uc_d, width="stretch")
        else:
            st.markdown('<p style="color:#8E8E93;font-size:13px">Sem dados de UC.</p>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # ── SEÇÃO 3: EVOLUÇÃO POR SEMANA ─────────────────────────────────────────
    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    section_title("📈 Evolução por Semana")
    col_donut_d, col_bim_d = st.columns([1, 1.6])

    with col_donut_d:
        st.markdown('<div class="apple-card"><div class="apple-label">Composição por Vetor</div>', unsafe_allow_html=True)
        if "Vetor (Peso)" in df_aluno.columns and not vetor_counts.empty:
            fig_donut_d = go.Figure(data=[go.Pie(
                labels=vetor_counts["Vetor (Peso)"], values=vetor_counts["Contagem"],
                hole=0.62,
                marker=dict(colors=["#007AFF","#FF3B30","#8E8E93"], line=dict(color="white", width=2.5)),
                textinfo="label+percent", textfont=dict(size=10),
            )])
            fig_donut_d.add_annotation(
                text=f"<b>{media_aluno:.1f}</b><br><span style='font-size:10px'>Média</span>",
                x=0.5, y=0.5, showarrow=False, font=dict(size=18, color="#1D1D1F"),
            )
            fig_donut_d.update_layout(
                showlegend=False,
                margin=dict(t=10, b=8, l=8, r=8), paper_bgcolor="white", height=240,
            )
            st.plotly_chart(fig_donut_d, width="stretch")
            st.dataframe(
                vetor_counts.rename(columns={"Vetor (Peso)": "Vetor"})
                .assign(Média=vetor_counts["Média"].round(1))[["Vetor","Contagem","Média"]],
                hide_index=True, width="stretch",
            )
        else:
            st.markdown('<p style="color:#8E8E93;font-size:13px">Sem dados de vetor.</p>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col_bim_d:
        st.markdown('<div class="apple-card"><div class="apple-label">Evolução por Semana</div>', unsafe_allow_html=True)
        if not bimestres.empty:
            cor_barras_d = [
                "#34C759" if m >= 7 else ("#F59E0B" if m >= NOTA_MINIMA else "#FF3B30")
                for m in bimestres["Média"]
            ]
            fig_bim_d = go.Figure()
            fig_bim_d.add_trace(go.Bar(
                x=bimestres["Semana"], y=bimestres["Média"],
                marker_color=cor_barras_d, marker_line=dict(color="white", width=1.5),
                text=bimestres["Média"].round(1), textposition="outside", name="Média",
                hovertemplate="<b>%{x}</b><br>Média: %{y:.1f}<br>Avaliações: %{customdata[0]}<br>Abaixo do Mínimo: %{customdata[1]}<extra></extra>",
                customdata=bimestres[["Total","Abaixo_Min"]].values,
            ))
            if len(bimestres) >= 2:
                fig_bim_d.add_trace(go.Scatter(
                    x=bimestres["Semana"], y=bimestres["Média"],
                    mode="lines+markers", name="Tendência",
                    line=dict(color="#007AFF", width=2, dash="dot"),
                    marker=dict(size=7, color="#007AFF"),
                ))
            fig_bim_d.add_hline(y=NOTA_MINIMA, line_dash="dash", line_color="#C7C7CC", line_width=1,
                                annotation_text="Mínimo", annotation_position="bottom right",
                                annotation_font_size=9)
            fig_bim_d.update_layout(
                plot_bgcolor="white", paper_bgcolor="white",
                yaxis=dict(range=[0, 11], gridcolor="#F9F9F9"),
                xaxis=dict(gridcolor="#F9F9F9"),
                legend=dict(orientation="h", y=-0.18, font=dict(size=9)),
                margin=dict(t=10, b=8, l=8, r=8), height=240, hovermode="x unified",
            )
            st.plotly_chart(fig_bim_d, width="stretch")
            st.dataframe(
                bimestres.rename(columns={"Abaixo_Min": "Abaixo de 6"})
                .assign(Média=bimestres["Média"].round(1)),
                hide_index=True, width="stretch",
            )
        else:
            st.markdown('<p style="color:#8E8E93;font-size:13px">Sem avaliações suficientes.</p>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # ── SEÇÃO 4: CRITÉRIOS COM DIFICULDADE ───────────────────────────────────
    if col_crit in df_aluno.columns and df_aluno[col_crit].nunique() >= 2:
        med_crit_d = df_aluno.groupby(col_crit)["Nota"].mean().sort_values()
        dificeis   = med_crit_d[med_crit_d < NOTA_MINIMA]
        if not dificeis.empty:
            st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
            section_title("⚠️ Critérios com Dificuldade")
            crit_parts = ['<div class="apple-card">']
            for crit_nome, crit_media in dificeis.items():
                vc2   = "#FF3B30" if crit_media < 4 else "#F59E0B"
                pct_w = f"{crit_media * 10:.0f}%"
                crit_parts.append(
                    f'<div class="apple-stat-row">'
                    f'<div style="font-size:13px;font-weight:500;color:#1D1D1F;flex:1">{crit_nome}</div>'
                    f'<div style="display:flex;align-items:center;gap:10px">'
                    f'<div style="width:80px;height:6px;background:#F2F2F7;border-radius:3px">'
                    f'<div style="width:{pct_w};height:6px;background:{vc2};border-radius:3px"></div></div>'
                    f'<span style="font-size:16px;font-weight:700;color:{vc2};min-width:32px;text-align:right">{crit_media:.1f}</span>'
                    f'</div></div>'
                )
            crit_parts.append('</div>')
            st.markdown("".join(crit_parts), unsafe_allow_html=True)

    # ── SEÇÃO 5: RAIO-X DE ATIVIDADES ────────────────────────────────────────
    _COL_INST = "Instrumento / Atividade"
    if _COL_INST in df_aluno.columns and df_aluno[_COL_INST].notna().any():
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        section_title("🔬 Raio-X das Atividades")

        inst_stats = (
            df_aluno.groupby(_COL_INST)["Nota"]
            .agg(Média="mean", Total="count", Mínima="min", Máxima="max",
                 Abaixo=lambda x: (x < NOTA_MINIMA).sum())
            .reset_index()
            .sort_values("Média")
        )

        fig_inst = go.Figure()

        cores_inst = [
            "#FF3B30" if m < NOTA_MINIMA else ("#F59E0B" if m < 7 else "#34C759")
            for m in inst_stats["Média"]
        ]
        def _hex_to_rgba(h: str, alpha: float = 0.3) -> str:
            h = h.lstrip("#")
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            return f"rgba({r},{g},{b},{alpha})"

        fig_inst.add_trace(go.Bar(
            x=inst_stats["Média"],
            y=inst_stats[_COL_INST],
            orientation="h",
            marker_color=[_hex_to_rgba(c) for c in cores_inst],
            marker_line=dict(color=cores_inst, width=2),
            text=inst_stats["Média"].round(1),
            textposition="outside",
            name="Média",
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Média: <b>%{x:.1f}</b><br>"
                "Avaliações: %{customdata[0]}<br>"
                "Mín: %{customdata[1]:.1f}  ·  Máx: %{customdata[2]:.1f}<br>"
                "Abaixo de 6: %{customdata[3]}<extra></extra>"
            ),
            customdata=inst_stats[["Total", "Mínima", "Máxima", "Abaixo"]].values,
        ))

        for ativ in inst_stats[_COL_INST]:
            notas_ativ = df_aluno[df_aluno[_COL_INST] == ativ]["Nota"].tolist()
            datas_ativ = df_aluno[df_aluno[_COL_INST] == ativ]["Data"].tolist()
            cores_pt   = ["#FF3B30" if n < NOTA_MINIMA else ("#F59E0B" if n < 7 else "#34C759") for n in notas_ativ]
            fig_inst.add_trace(go.Scatter(
                x=notas_ativ,
                y=[ativ] * len(notas_ativ),
                mode="markers",
                marker=dict(size=9, color=cores_pt, line=dict(color="white", width=1.5), opacity=0.85),
                name=ativ,
                showlegend=False,
                hovertemplate=[
                    f"<b>{ativ}</b><br>Nota: <b>{n:.1f}</b><br>"
                    f"Data: {d.strftime('%d/%m/%Y') if pd.notna(d) and hasattr(d,'strftime') else '—'}<extra></extra>"
                    for n, d in zip(notas_ativ, datas_ativ)
                ],
            ))

        fig_inst.add_vline(x=NOTA_MINIMA, line_dash="dot", line_color="#FF3B30",
                           line_width=1.2, annotation_text="Mínimo",
                           annotation_font_size=9, annotation_font_color="#FF3B30")

        _h_inst = max(260, len(inst_stats) * 44 + 60)
        fig_inst.update_layout(
            plot_bgcolor="white", paper_bgcolor="white",
            xaxis=dict(range=[0, 11], gridcolor="#F9F9F9", title="Nota"),
            yaxis=dict(tickfont=dict(size=10), autorange="reversed"),
            showlegend=False,
            margin=dict(t=10, b=30, l=10, r=50),
            height=_h_inst,
            hovermode="closest",
            bargap=0.35,
        )
        st.markdown('<div class="apple-card"><div class="apple-label">Média por atividade · Pontos = avaliações individuais · Pior desempenho no topo</div>', unsafe_allow_html=True)
        st.plotly_chart(fig_inst, width="stretch")

        tbl_inst = inst_stats.copy()
        tbl_inst["Média"]  = tbl_inst["Média"].round(1)
        tbl_inst["Mínima"] = tbl_inst["Mínima"].round(1)
        tbl_inst["Máxima"] = tbl_inst["Máxima"].round(1)
        tbl_inst["Taxa OK"] = ((tbl_inst["Total"] - tbl_inst["Abaixo"]) / tbl_inst["Total"] * 100).round(0).astype(int).astype(str) + "%"
        tbl_inst = tbl_inst.rename(columns={_COL_INST: "Atividade", "Total": "Qtd", "Abaixo": "Abaixo de 6"})
        st.dataframe(
            tbl_inst[["Atividade","Qtd","Média","Mínima","Máxima","Abaixo de 6","Taxa OK"]],
            hide_index=True, width="stretch",
        )
        st.markdown('</div>', unsafe_allow_html=True)

    # ── SEÇÃO 6: RANKING DA TURMA ─────────────────────────────────────────────
    if mostrar_ranking:
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        section_title("🏆 Ranking da Turma")
        st.markdown('<div class="apple-card">', unsafe_allow_html=True)
        if posicao:
            st.markdown(
                f'<div style="background:#F0F9FF;border:1px solid #BAE6FD;border-radius:10px;'
                f'padding:12px 18px;margin-bottom:14px;font-size:13px;font-weight:600;color:#007AFF">'
                f'{aluno_sel} está em <b>{posicao}º lugar</b> de {len(ranking)} alunos</div>',
                unsafe_allow_html=True,
            )
        fig_rank_d = px.bar(
            ranking.head(20), x="Aluno", y="Média", color="Média", text="Média",
            color_continuous_scale=[[0,"#FF3B30"],[0.6,"#F59E0B"],[1,"#34C759"]],
        )
        fig_rank_d.update_traces(texttemplate="%{text:.1f}", textposition="outside")
        fig_rank_d.update_layout(
            plot_bgcolor="white", paper_bgcolor="white",
            yaxis=dict(range=[0, 11], gridcolor="#F9F9F9"),
            xaxis_title="", coloraxis_showscale=False,
            margin=dict(t=10, b=8, l=8, r=8), height=320,
        )
        fig_rank_d.add_hline(y=NOTA_MINIMA, line_dash="dash", line_color="#C7C7CC", line_width=1)
        st.plotly_chart(fig_rank_d, width="stretch")
        st.markdown('</div>', unsafe_allow_html=True)

    # ── SEÇÃO 7: RECUPERAÇÕES ────────────────────────────────────────────────
    if (
    df_rec_aluno is not None
    and not df_rec_aluno.empty
    and "Nota_Rec" in df_rec_aluno.columns
    and df_rec_aluno["Nota_Rec"].notna().any()
    ):
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        section_title("🔁 Histórico de Recuperações")
        st.markdown('<div class="apple-card">', unsafe_allow_html=True)
        for _, row in df_rec_aluno.iterrows():
            nota_orig = row.get("Nota_Orig")
            nota_rec  = row.get("Nota_Rec")
            delta_rec = (nota_rec - nota_orig) if pd.notna(nota_rec) and pd.notna(nota_orig) else None
            data_r    = row.get("Data_Rec", "")
            data_fmt  = data_r.strftime("%d/%m/%Y") if pd.notna(data_r) and hasattr(data_r, "strftime") else str(data_r)
            aprovado  = "✅ Aprovado" if pd.notna(nota_rec) and nota_rec >= NOTA_MINIMA else "❌ Não aprovado"
            obs_r     = str(row.get("Observação", "") or "")
            antes     = nota_formatada(nota_orig)
            depois    = nota_formatada(nota_rec)
            delta_str = (f"{'▲' if delta_rec >= 0 else '▼'}{abs(delta_rec):.1f}") if delta_rec is not None else "—"
            cor_dr    = "#34C759" if delta_rec and delta_rec >= 0 else "#FF3B30"
            st.markdown(
                f'<div class="rec-item">'
                f'<div style="text-align:center;min-width:60px">'
                f'<div style="font-size:10px;color:#92400E;font-weight:600">ANTES</div>'
                f'<div style="font-family:Montserrat;font-size:1.3rem;font-weight:800;color:#B45309">{antes}</div>'
                f'</div>'
                f'<div style="font-size:1.3rem;color:#D97706">→</div>'
                f'<div style="text-align:center;min-width:60px">'
                f'<div style="font-size:10px;color:#065F46;font-weight:600">DEPOIS</div>'
                f'<div style="font-family:Montserrat;font-size:1.3rem;font-weight:800;'
                f'color:{"#34C759" if pd.notna(nota_rec) and nota_rec >= NOTA_MINIMA else "#FF3B30"}">{depois}</div>'
                f'</div>'
                f'<div style="flex:1">'
                f'<strong style="font-size:0.88rem">{row.get("Critério","—")} · {aprovado}</strong>'
                f'<span style="display:block;font-size:0.75rem;color:#8E8E93">{data_fmt} · {row.get("UC","—")}</span>'
                f'{"<span style=font-size:0.75rem;color:#92400E;font-style:italic>" + obs_r + "</span>" if obs_r else ""}'
                f'</div>'
                f'<div style="font-family:Montserrat;font-weight:800;font-size:1rem;color:{cor_dr}">{delta_str}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        st.markdown('</div>', unsafe_allow_html=True)

    # ── SEÇÃO 8: MAPA DE CALOR DA TURMA ──────────────────────────────────────
    if mostrar_turma:
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        section_title("🌡️ Mapa de Calor da Turma")
        col_crit_heat = "Critério Avaliado" if "Critério Avaliado" in df_turma.columns else None
        if col_crit_heat:
            st.markdown('<div class="apple-card">', unsafe_allow_html=True)
            heat_df = (
                df_turma.groupby(["Aluno", col_crit_heat])["Nota"]
                .mean().reset_index()
                .pivot(index="Aluno", columns=col_crit_heat, values="Nota")
            )
            heat_df["_media"] = heat_df.mean(axis=1)
            heat_df = heat_df.sort_values("_media", ascending=False).drop(columns="_media")
            fig_heat_d = go.Figure(data=go.Heatmap(
                z=heat_df.values,
                x=heat_df.columns.tolist(), y=heat_df.index.tolist(),
                colorscale=[[0,"#FF3B30"],[0.5,"#F59E0B"],[0.6,"#FDE68A"],[0.75,"#86EFAC"],[1,"#34C759"]],
                zmin=0, zmax=10,
                text=[[f"{v:.1f}" if pd.notna(v) else "—" for v in row] for row in heat_df.values],
                texttemplate="%{text}", textfont=dict(size=9),
                hoverongaps=False,
                colorbar=dict(title="Nota", tickvals=[0,2,4,6,8,10]),
            ))
            if aluno_sel in heat_df.index:
                idx_h = heat_df.index.tolist().index(aluno_sel)
                fig_heat_d.add_shape(
                    type="rect",
                    x0=-0.5, x1=len(heat_df.columns)-0.5,
                    y0=idx_h-0.5, y1=idx_h+0.5,
                    line=dict(color="#007AFF", width=3),
                )
            fig_heat_d.update_layout(
                plot_bgcolor="white", paper_bgcolor="white",
                xaxis=dict(tickangle=-35, tickfont=dict(size=9)),
                yaxis=dict(tickfont=dict(size=9)),
                margin=dict(t=10, b=10, l=10, r=10),
                height=max(300, len(heat_df)*38+60),
            )
            st.plotly_chart(fig_heat_d, width="stretch")
            st.caption("🔵 Borda azul = aluno selecionado")
            st.markdown('</div>', unsafe_allow_html=True)

    # ── SEÇÃO 9: REGISTROS E EXPORTAÇÃO ──────────────────────────────────────
    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    section_title("📁 Registros e Exportação")
    st.markdown('<div class="apple-card">', unsafe_allow_html=True)
    with st.expander("🗂️ Ver todos os registros do aluno"):
        df_disp_d         = df_aluno.copy()
        df_disp_d["Data"] = df_disp_d["Data"].dt.strftime("%d/%m/%Y")
        st.dataframe(df_disp_d.sort_values("Data", ascending=False),
                     width="stretch", hide_index=True)
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    
    if f"pdf_bytes_{aluno_sel}" not in st.session_state:
        st.session_state[f"pdf_bytes_{aluno_sel}"] = None
    if f"xlsx_bytes_{aluno_sel}" not in st.session_state:
        st.session_state[f"xlsx_bytes_{aluno_sel}"] = None

    col_pdf_d, col_xlsx_d = st.columns(2)
    
    with col_pdf_d:
        if st.button("📄 Gerar Boletim em PDF", width="stretch", type="primary", key="pdf_btn"):
            with st.spinner("Gerando boletim PDF..."):
                analise_fn_pdf = None
                if (
                    freq_aluno and freq_aluno.get("tem_dados")
                    and df_cal_aluno is not None and not df_cal_aluno.empty
                ):
                    df_cal_sem_feriado = df_cal_aluno[df_cal_aluno["Status"] != "Feriado"]
                    analise_fn_pdf = analisar_freq_notas(df_aluno, df_cal_sem_feriado)

                st.session_state[f"pdf_bytes_{aluno_sel}"] = gerar_boletim_pdf(
                    aluno=aluno_sel, turma=turma_label, df_al=df_aluno,
                    media_al=media_aluno, media_pond=media_pond, media_turma=media_turma,
                    notas_baixas=notas_baixas, total_avals=total_avals, delta=delta_turma,
                    bimestres=bimestres, seq_critica=seq_critica,
                    comparar_turma=False, df_turma=df_turma,
                    df_rec_aluno=df_rec_aluno if not df_rec_aluno.empty else None,
                    obs_geral=obs_geral, posicao=posicao, total_alunos=len(df_turma["Aluno"].unique()),
                    freq_aluno=freq_aluno,
                    analise_fn_aluno=analise_fn_pdf,
                    df_cal_aluno=df_cal_aluno,
                )
        
        if st.session_state[f"pdf_bytes_{aluno_sel}"] is not None:
            nome_pdf = f"boletim_{aluno_sel.replace(' ','_')}_{datetime.now().strftime('%d%m%Y')}.pdf"
            st.download_button("⬇️ Baixar PDF", data=st.session_state[f"pdf_bytes_{aluno_sel}"], file_name=nome_pdf,
                               mime="application/pdf", width="stretch")

    with col_xlsx_d:
        if st.button("📊 Gerar Arquivo Excel", width="stretch", key="xlsx_btn"):
            with st.spinner("Gerando Excel..."):
                st.session_state[f"xlsx_bytes_{aluno_sel}"] = gerar_excel(aluno_sel, df_aluno, df_turma, bimestres, df_rec_aluno)
        
        if st.session_state[f"xlsx_bytes_{aluno_sel}"] is not None:
            nome_xlsx = f"dados_{aluno_sel.replace(' ','_')}_{datetime.now().strftime('%d%m%Y')}.xlsx"
            st.download_button("⬇️ Baixar Excel", data=st.session_state[f"xlsx_bytes_{aluno_sel}"], file_name=nome_xlsx,
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               width="stretch")
    st.markdown('</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# ABA 3 — FREQUÊNCIA
# ══════════════════════════════════════════════════════════════════════════════
def _calendario_faltas(df_freq_aluno: pd.DataFrame) -> None:
    df = df_freq_aluno.dropna(subset=["Data", "Status"]).copy()
    if df.empty:
        return

    df["_data"]       = pd.to_datetime(df["Data"])
    df["_dow"]        = df["_data"].dt.dayofweek          
    df["_week_label"] = df["_data"].apply(
        lambda d: f"{d.isocalendar().year}-S{d.isocalendar().week:02d}"
    )

    pivot = (
        df.pivot_table(index="_week_label", columns="_dow", values="Status", aggfunc="first")
        .sort_index()
    )

    dias_map   = {0: "Seg", 1: "Ter", 2: "Qua", 3: "Qui", 4: "Sex", 5: "Sáb", 6: "Dom"}
    cols_used  = sorted(list(set(pivot.columns.tolist()) | {0, 1, 2, 3, 4}))
    x_labels   = [dias_map.get(c, str(c)) for c in cols_used]
    semanas    = list(pivot.index)

    z_vals, hover_vals, text_vals = [], [], []
    for week in semanas:
        row_z, row_h, row_t = [], [], []
        for dow in cols_used:
            val = pivot.loc[week, dow] if dow in pivot.columns and not pd.isna(pivot.loc[week, dow]) else None
            if val is None:
                row_z.append(None); row_h.append("—"); row_t.append("")
            elif val == "Presente":
                row_z.append(1);    row_h.append("✅ Presente"); row_t.append("✓")
            elif val == "Falta":
                row_z.append(0);    row_h.append("❌ Falta");    row_t.append("✗")
            elif val == "Feriado":
                row_z.append(0.5);  row_h.append("🏖️ Feriado");  row_t.append("")
        z_vals.append(row_z)
        hover_vals.append(row_h)
        text_vals.append(row_t)

    altura = max(140, min(520, len(semanas) * 32 + 80))

    fig = go.Figure(go.Heatmap(
        z=z_vals,
        x=x_labels,
        y=semanas,
        customdata=hover_vals,
        text=text_vals,
        texttemplate="%{text}",
        textfont=dict(size=11, color="white"),
        hovertemplate="<b>%{y}</b> · %{x}: %{customdata}<extra></extra>",
        colorscale=[
            [0.0, "#FF3B30"], [0.33, "#FF3B30"],
            [0.33, "white"],  [0.66, "white"],
            [0.66, "#34C759"], [1.0, "#34C759"]
        ],
        showscale=False,
        zmin=0, zmax=1,
        xgap=4, ygap=4,
    ))
    fig.update_layout(
        plot_bgcolor="#F5F5F7",
        paper_bgcolor="white",
        margin=dict(t=8, b=8, l=80, r=8),
        height=altura,
        xaxis=dict(
            side="top",
            tickfont=dict(size=12, color="#1D1D1F"),
            fixedrange=True,
        ),
        yaxis=dict(
            autorange="reversed",
            tickfont=dict(size=10, color="#6B7280"),
            fixedrange=True,
        ),
    )

    n_pres  = (df["Status"] == "Presente").sum()
    n_falta = (df["Status"] == "Falta").sum()
    n_feriado = (df["Status"] == "Feriado").sum()
    
    n_sem_aula = sum(
        1 for week in semanas for dow in cols_used 
        if not (dow in pivot.columns and not pd.isna(pivot.loc[week, dow]))
    )

    st.markdown(
        f'<div style="display:flex;gap:20px;margin-bottom:8px;font-size:12px;color:#6B7280">'
        f'<span><span style="display:inline-block;width:12px;height:12px;border-radius:3px;'
        f'background:#34C759;margin-right:5px;vertical-align:middle"></span>Presente ({int(n_pres)})</span>'
        f'<span><span style="display:inline-block;width:12px;height:12px;border-radius:3px;'
        f'background:#FF3B30;margin-right:5px;vertical-align:middle"></span>Falta ({int(n_falta)})</span>'
        f'<span><span style="display:inline-block;width:12px;height:12px;border-radius:3px;'
        f'background:white;border:1px solid #D1D5DB;margin-right:5px;vertical-align:middle"></span>Feriado ({int(n_feriado)})</span>'
        f'<span><span style="display:inline-block;width:12px;height:12px;border-radius:3px;'
        f'background:#E5E7EB;margin-right:5px;vertical-align:middle"></span>Sem aula ({int(n_sem_aula)})</span>'
        f'</div>',
        unsafe_allow_html=True,
    )
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def _montar_calendario_aluno(
    df_freq: pd.DataFrame,
    aluno_sel: str,
    datas_globais: list,
    df_feriados: list = None,
) -> pd.DataFrame:
    """
    Monta o calendário completo de presença/falta/feriado do aluno.
    Centraliza a lógica para que PDF e aba Frequência usem os mesmos dados.
    """
    if not datas_globais or len(datas_globais) == 0:
        return pd.DataFrame()

    todas_datas = sorted(datas_globais)

    df_faltas = (
        df_freq[df_freq["Aluno"].astype(str).str.strip().str.lower() == str(aluno_sel).strip().lower()]
        if not df_freq.empty and "Aluno" in df_freq.columns else pd.DataFrame()
    )

    if "Presente" in df_faltas.columns:
        pres_bool = df_faltas["Presente"].apply(
            lambda x: True if str(x).strip().lower() in ['v', 'verdadeiro', 'true', 'presente', 'p', '1', 'sim', 's']
            else (True if isinstance(x, bool) and x else False)
        )
        datas_falta = set(pd.to_datetime(df_faltas[~pres_bool]["Data"], errors="coerce", dayfirst=True).dt.normalize().dropna())
    elif not df_faltas.empty and "Data" in df_faltas.columns:
        datas_falta = set(pd.to_datetime(df_faltas["Data"], errors="coerce", dayfirst=True).dt.normalize().dropna())
    else:
        datas_falta = set()

    feriados_set = (
        {pd.to_datetime(d, errors="coerce", dayfirst=True).normalize() for d in df_feriados if pd.notna(d)}
        if df_feriados else set()
    )
    feriados_set = {d for d in feriados_set if pd.notna(d)}

    todas_datas_ts = {pd.to_datetime(d).normalize() for d in todas_datas}
    min_d = min(todas_datas_ts) if todas_datas_ts else pd.Timestamp.min
    max_d = max(todas_datas_ts) if todas_datas_ts else pd.Timestamp.max

    feriados_validos = {d for d in feriados_set if min_d <= d <= max_d}
    datas_calendario = sorted(list(todas_datas_ts | feriados_validos))

    dados_aluno = []
    for d in datas_calendario:
        status = "Feriado" if d in feriados_set else ("Falta" if d in datas_falta else "Presente")
        dados_aluno.append({
            "Data": d,
            "Status": status,
            "Presente": status == "Presente",
            "Aluno": aluno_sel,
        })
    return pd.DataFrame(dados_aluno)


def _tab_frequencia(
    df_aluno: pd.DataFrame,
    df_freq: pd.DataFrame,
    aluno_sel: str,
    freq_aluno: dict,
    df_cal_aluno: pd.DataFrame,
) -> None:
    if not freq_aluno["tem_dados"]:
        st.markdown(
            '<div style="background:#F8FAFC;border-radius:14px;padding:24px;border:1px dashed #D1D5DB;'
            'color:#8E8E93;font-size:14px;text-align:center">'
            '⬜ Sem dados de frequência — adicione a aba <b>Frequência</b> na planilha</div>',
            unsafe_allow_html=True,
        )
        return

    render_freq_card(freq_aluno)
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    df_freq_aluno_tab = df_cal_aluno

    if not df_freq_aluno_tab.empty:
        section_title("📅 Calendário de Presenças")
        _calendario_faltas(df_freq_aluno_tab)
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    analise_fn_tab = analisar_freq_notas(df_aluno, df_freq_aluno_tab[df_freq_aluno_tab["Status"] != "Feriado"] if not df_freq_aluno_tab.empty else pd.DataFrame())

    if not analise_fn_tab:
        return

    section_title("📊 Frequência × Notas")
    fi1, fi2, fi3 = st.columns(3)
    _impacto_t = analise_fn_tab["impacto"]
    _imp_cor_t = (
        "#FF3B30" if _impacto_t and _impacto_t < -0.5
        else ("#F59E0B" if _impacto_t and _impacto_t < 0 else "#34C759")
    )
    _imp_val_t = f"{_impacto_t:+.1f}" if _impacto_t is not None else "—"
    _mcf_t     = f"{analise_fn_tab['media_com_falta']:.1f}" if analise_fn_tab["media_com_falta"] else "—"
    _msf_t     = f"{analise_fn_tab['media_sem_falta']:.1f}" if analise_fn_tab["media_sem_falta"] else "—"

    # [MODIFICAÇÃO] Interceptação cosmética amigável para alunos com 100% de frequência estável
    if freq_aluno["pct_presenca"] == 100.0:
        _imp_val_t = "Nenhum"
        _mcf_t = "— (Sem faltas)"

    for col_fi, val_fi, lbl_fi, cor_fi in [
        (fi1, _msf_t,     "Média sem falta",  "#34C759"),
        (fi2, _mcf_t,     "Média com falta",  "#FF3B30" if analise_fn_tab["media_com_falta"] and analise_fn_tab["media_com_falta"] < NOTA_MINIMA else "#F59E0B"),
        (fi3, _imp_val_t, "Impacto da falta", _imp_cor_t),
    ]:
        with col_fi:
            st.markdown(
                f'<div class="apple-kpi" style="text-align:center;border-top:3px solid {cor_fi}">'
                f'<div style="font-size:28px;font-weight:700;color:{cor_fi};margin-top:4px">{val_fi}</div>'
                f'<div class="apple-label" style="margin-top:6px">{lbl_fi}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    if _impacto_t is None or not analise_fn_tab["media_sem_falta"]:
        return

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    pct_falta_t   = 1 - (freq_aluno["pct_presenca"] / 100)
    impacto_abs_t = abs(_impacto_t)
    iif_t         = round(min(10, (pct_falta_t * impacto_abs_t * 10)), 1)

    if iif_t <= 2:   iif_cor_t, iif_nivel_t, iif_emoji_t = "#34C759", "Baixo risco", "🟢"
    elif iif_t <= 4: iif_cor_t, iif_nivel_t, iif_emoji_t = "#F59E0B", "Atenção",     "🟡"
    elif iif_t <= 6: iif_cor_t, iif_nivel_t, iif_emoji_t = "#F97316", "Alto risco",  "🟠"
    else:            iif_cor_t, iif_nivel_t, iif_emoji_t = "#FF3B30", "Crítico",     "🔴"

    nota_proj_t = round(
        analise_fn_tab["media_sem_falta"] + (_impacto_t * (pct_falta_t / max(pct_falta_t, 0.01))), 1
    ) if pct_falta_t > 0 else analise_fn_tab["media_sem_falta"]
    nota_proj_t = max(0, min(10, nota_proj_t))
    np_cor_t    = "#FF3B30" if nota_proj_t < NOTA_MINIMA else "#34C759"

    if iif_t <= 2:   interp_t = "✅ A frequência não está comprometendo o desempenho. Manter o padrão atual."
    elif iif_t <= 4: interp_t = f"📉 As faltas estão gerando queda de <b>{impacto_abs_t:.1f} ponto(s)</b> nas semanas afetadas. Vale uma conversa preventiva."
    elif iif_t <= 6: interp_t = f"⚠️ Impacto considerável — cada semana com falta custa <b>{impacto_abs_t:.1f} pontos</b>. Intervenção recomendada."
    else:            interp_t = f"🚨 A frequência é o principal fator de risco. Queda de <b>{impacto_abs_t:.1f} pontos</b> por semana com falta — ação imediata."

    iif_parts = [
        f'<div style="background:white;border-radius:16px;padding:22px 26px;'
        f'box-shadow:0 1px 3px rgba(0,0,0,0.06),0 4px 16px rgba(0,0,0,0.04);border-top:4px solid {iif_cor_t}">',
        f'<div style="font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.08em;color:#8E8E93;margin-bottom:16px">',
        '🧮 Índice de Impacto da Frequência (IIF)',
        '<span class="iif-tooltip-wrap"><span class="iif-tooltip-icon">ℹ</span>',
        '<div class="iif-tooltip-box">',
        '<b>⚠️ Importante</b><br>O IIF mede correlação, não causa. Falta e nota baixa podem ter a mesma origem (ex: problema familiar). Use como sinal de atenção, não como julgamento.<br><br>',
        '<table style="width:100%;border-collapse:collapse;font-size:0.75rem">',
        '<tr style="border-bottom:1px solid #334155"><td style="padding:5px 6px;color:#94A3B8;font-weight:700">Situação real</td><td style="padding:5px 6px;color:#94A3B8;font-weight:700">O que o IIF shows</td></tr>',
        '<tr style="border-bottom:1px solid #1E293B"><td style="padding:6px">Falta pouco, nota não muda</td><td style="padding:6px;color:#A5B4FC">IIF baixo → frequência não é o problema</td></tr>',
        '<tr style="border-bottom:1px solid #1E293B"><td style="padding:6px">Falta pouco, nota cai muito</td><td style="padding:6px;color:#FDE68A">IIF médio → falta pontual tem grande impacto</td></tr>',
        '<tr style="border-bottom:1px solid #1E293B"><td style="padding:6px">Falta muito, nota não muda</td><td style="padding:6px;color:#FDE68A">IIF médio → provavelmente estuda por conta própria</td></tr>',
        '<tr><td style="padding:6px">Falta muito E nota cai muito</td><td style="padding:6px;color:#FCA5A5">IIF alto → frequência é o principal fator de risco</td></tr>',
        '</table></div></span></div>',
        f'<div style="background:#F5F5F7;border-radius:12px;padding:14px 18px;margin-bottom:18px;font-family:monospace;font-size:14px;color:#1D1D1F;line-height:2.2">',
        f'IIF = ( % faltas × |impacto na nota| × 10 )<br>',
        f'<span style="color:#8E8E93;font-size:13px">&nbsp;&nbsp;&nbsp;= ( {pct_falta_t*100:.1f}% × {impacto_abs_t:.1f} × 10 ) = ',
        f'<b style="color:{iif_cor_t};font-size:15px">{iif_t}</b> / 10</span></div>',
        f'<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:16px">',
        f'<div style="background:{iif_cor_t}10;border:1.5px solid {iif_cor_t}30;border-radius:12px;padding:14px;text-align:center">',
        f'<div style="font-size:28px;font-weight:700;color:{iif_cor_t}">{iif_emoji_t} {iif_t}</div>',
        f'<div style="font-size:10px;font-weight:700;text-transform:uppercase;color:{iif_cor_t};margin-top:4px;letter-spacing:0.06em">{iif_nivel_t}</div></div>',
        f'<div style="background:#F0FDF4;border:1.5px solid #A7F3D0;border-radius:12px;padding:14px;text-align:center">',
        f'<div style="font-size:10px;font-weight:700;color:#8E8E93;text-transform:uppercase;margin-bottom:5px">Sem falta → Com falta</div>',
        f'<div style="font-size:16px;font-weight:700;color:#1D1D1F">{_msf_t} → {_mcf_t}</div>',
        f'<div style="font-size:11px;color:#FF3B30;font-weight:600;margin-top:2px">Δ {_impacto_t:+.1f} pontos</div></div>',
        f'<div style="background:{np_cor_t}10;border:1.5px solid {np_cor_t}30;border-radius:12px;padding:14px;text-align:center">',
        f'<div style="font-size:10px;font-weight:700;color:#8E8E93;text-transform:uppercase;margin-bottom:5px">Nota projetada</div>',
        f'<div style="font-size:24px;font-weight:700;color:{np_cor_t}">{nota_proj_t:.1f}</div>',
        f'<div style="font-size:10px;color:#8E8E93;margin-top:2px">se padrão continuar</div></div></div>',
        f'<div style="background:#F5F5F7;border-radius:8px;padding:9px 13px;display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">',
        f'<span style="font-size:12px;color:#8E8E93;font-weight:600">Correlação presença × nota</span>',
        f'<span style="font-weight:700;font-size:13px;color:{analise_fn_tab["corr_cor"]}">{analise_fn_tab["corr_label"]}</span></div>',
        f'<div style="border-left:4px solid {iif_cor_t};background:{iif_cor_t}08;border-radius:8px;padding:10px 13px;font-size:13px;color:#1D1D1F;line-height:1.6">',
        f'{interp_t}</div></div>',
    ]
    st.markdown("".join(iif_parts), unsafe_allow_html=True)

    notas_s = analise_fn_tab.get("notas_serie")
    faltas_d = analise_fn_tab.get("faltas_datas", [])
    if notas_s is not None and not notas_s.empty:
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        section_title("📉 Linha do Tempo: Notas × Faltas")
        st.markdown('<div class="apple-card"><div class="apple-label">Cada ponto é uma avaliação · Triângulos vermelhos indicam dias com falta naquela semana</div>', unsafe_allow_html=True)

        fig_tl = go.Figure()

        fig_tl.add_hrect(
            y0=0, y1=NOTA_MINIMA,
            fillcolor="rgba(255,59,48,0.04)", line_width=0,
        )

        fig_tl.add_hline(
            y=NOTA_MINIMA, line_dash="dot", line_color="#FF3B30",
            line_width=1.2,
            annotation_text=f"Mínimo {NOTA_MINIMA:.0f}",
            annotation_font_size=9, annotation_font_color="#FF3B30",
            annotation_position="right",
        )

        if faltas_d:
            fig_tl.add_trace(go.Scatter(
                x=faltas_d,
                y=[0.3] * len(faltas_d),
                mode="markers",
                marker=dict(symbol="triangle-up", size=10, color="#FF3B30", opacity=0.7),
                name="Falta",
                hovertemplate="<b>Falta</b>: %{x|%d/%m/%Y}<extra></extra>",
            ))

        cores_pontos = [
            "#34C759" if n >= 7 else ("#F59E0B" if n >= NOTA_MINIMA else "#FF3B30")
            for n in notas_s["Nota"]
        ]
        fig_tl.add_trace(go.Scatter(
            x=notas_s["Data"],
            y=notas_s["Nota"],
            mode="lines+markers",
            name="Nota",
            line=dict(color="#007AFF", width=2),
            marker=dict(size=9, color=cores_pontos, line=dict(color="white", width=1.5)),
            hovertemplate="<b>%{x|%d/%m/%Y}</b><br>Nota: <b>%{y:.1f}</b><extra></extra>",
        ))

        fig_tl.update_layout(
            plot_bgcolor="white", paper_bgcolor="white",
            yaxis=dict(range=[-0.5, 10.5], gridcolor="#F9F9F9", title="Nota"),
            xaxis=dict(gridcolor="#F9F9F9", title=""),
            showlegend=True,
            legend=dict(orientation="h", y=1.08, font=dict(size=10)),
            margin=dict(t=20, b=10, l=40, r=30),
            height=240,
        )
        st.plotly_chart(fig_tl, width="stretch")
        st.markdown('</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# ABA 4 — ANÁLISE IA INDIVIDUAL
# ══════════════════════════════════════════════════════════════════════════════
_MODELO_GROQ_IND = "moonshotai/kimi-k2-instruct"


def _tab_ia_individual(
    df_aluno: pd.DataFrame,
    aluno_sel: str,
    turma_label: str,
    risco_aluno: str,
    tendencia: str,
    media_pond: float,
    notas_baixas: int,
    total_avals: int,
    seq_critica: int,
    freq_aluno: dict,
    obs_geral: str,
    col_crit: str,
) -> None:
    st.markdown(
        '<div style="background:linear-gradient(135deg,#EEF2FF,#F5F3FF);border-radius:14px;'
        'padding:16px 20px;margin-bottom:20px;border:1px solid #C7D2FE">'
        '<div style="font-weight:700;color:#4F46E5;margin-bottom:4px">🤖 Análise Pedagógica Individual com IA</div>'
        '<div style="font-size:0.86rem;color:#6366F1">A IA analisa os dados deste aluno e gera um diagnóstico '
        'contextualizado com pontos fortes, dificuldades e ações concretas para o docente.</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    _nota_str  = ",".join(df_aluno.sort_values("Data")["Nota"].astype(str).tolist())
    _ia_key    = "ia_ind_" + hashlib.md5(f"{aluno_sel}|{_nota_str}".encode()).hexdigest()[:12]
    _cached_ia = st.session_state.get(_ia_key)

    if _cached_ia is None:
        if st.button("🤖 Gerar Análise com IA", type="primary", width="content",
                     key="btn_ia_individual"):
            try:
                _groq_key = st.secrets.get("GROQ_API_KEY", "") or os.environ.get("GROQ_API_KEY", "")
            except Exception:
                _groq_key = os.environ.get("GROQ_API_KEY", "")
            if not _groq_key:
                st.error("Chave `GROQ_API_KEY` não encontrada. Adicione-a nos Secrets do Replit.")
                return
            _client = Groq(api_key=_groq_key)

            _melhor = _pior = _melhor_m = _pior_m = None
            if col_crit in df_aluno.columns and df_aluno[col_crit].nunique() >= 2:
                _mc = df_aluno.groupby(col_crit)["Nota"].mean()
                _melhor, _melhor_m = _mc.idxmax(), round(_mc.max(), 1)
                _pior,   _pior_m   = _mc.idxmin(), round(_mc.min(), 1)

            _vetores = {}
            if "Vetor (Peso)" in df_aluno.columns:
                for _v in ["Fazer (40%)", "Saber (30%)", "Comport. (30%)"]:
                    _sub = df_aluno[df_aluno["Vetor (Peso)"] == _v]["Nota"]
                    if not _sub.empty:
                        _vetores[_v] = round(_sub.mean(), 1)

            _ctx = {
                "nome": aluno_sel,
                "turma": turma_label,
                "media_ponderada": round(media_pond, 1),
                "risco": risco_aluno,
                "tendencia": tendencia,
                "notas_baixas": notas_baixas,
                "total_avals": total_avals,
                "seq_critica": seq_critica,
                "frequencia_pct": freq_aluno.get("pct_presenca"),
                "melhor_criterio": _melhor,
                "melhor_media": _melhor_m,
                "pior_criterio": _pior,
                "pior_media": _pior_m,
                "vetores": _vetores,
                "obs_geral": obs_geral,
            }

            _prompt_ind = f"""Você é um especialista em pedagogia do SENAI. Analise os dados deste aluno e gere um relatório pedagógico individual DETALHADO E PERSONALIZADO.

Dados do aluno:
{json.dumps(_ctx, ensure_ascii=False, indent=2)}

REGRAS:
- Seja ESPECÍFICO: cite números, critérios e vetores concretos
- A ação_docente deve ser CONCRETA (o que fazer nos próximos dias)
- Linguagem profissional mas acessível
- Se frequencia_pct < 75: mencione risco de reprovação por falta
- Se seq_critica > 0: mencione urgência explicitamente

FORMATO (JSON puro, sem markdown):
{{
  "diagnostico": "Diagnóstico completo baseado nos dados (2-3 frases com números)",
  "ponto_forte": "Habilidade específica que se destaca",
  "ponto_fraco": "Dificuldade específica com critério/vetor",
  "acao_docente": "Ação concreta que o docente deve tomar nos próximos dias"
}}"""

            with st.spinner("🤖 Gerando análise personalizada..."):
                try:
                    _chat = _client.chat.completions.create(
                        messages=[
                            {"role": "system", "content": "Você é especialista em pedagogia SENAI. Responda APENAS com JSON válido."},
                            {"role": "user", "content": _prompt_ind},
                        ],
                        model=_MODELO_GROQ_IND,
                        temperature=0.4,
                        max_tokens=1024,
                    )
                    _resp = _chat.choices[0].message.content
                    _js = _resp.find('{'); _je = _resp.rfind('}') + 1
                    _result = json.loads(_resp[_js:_je])
                    st.session_state[_ia_key] = _result
                    st.rerun()
                except json.JSONDecodeError:
                    st.error("A IA retornou um formato inválido. Tente novamente.")
                except Exception as _e:
                    st.error(f"Erro ao comunicar com a IA: {_e}")
        return

    _ic_r = {"critico":"🔴","atencao":"🟡","adequado":"🟢","excelente":"🟣"}.get(risco_aluno,"⚪")
    _cl_r = {"critico":"#EF4444","atencao":"#F59E0B","adequado":"#10B981","excelente":"#6366F1"}.get(risco_aluno,"#6B7280")

    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:16px">
        <span style="font-size:1.4rem">{_ic_r}</span>
        <div>
            <div style="font-weight:700;font-size:1rem;color:#111827">{aluno_sel}</div>
            <div style="font-size:0.78rem;color:{_cl_r};font-weight:600">Média: {media_pond:.1f} · {risco_aluno.capitalize()} · {tendencia.capitalize()}</div>
        </div>
    </div>""", unsafe_allow_html=True)

    _secoes = [
        ("📋 Diagnóstico",       _cached_ia.get("diagnostico","—"),   "#F8FAFC", "#374151", "#3B82F6"),
        ("✅ Ponto Forte",       _cached_ia.get("ponto_forte","—"),   "#F0FDF4", "#065F46", "#10B981"),
        ("⚠️ Ponto Fraco",      _cached_ia.get("ponto_fraco","—"),   "#FFF5F5", "#991B1B", "#EF4444"),
        ("🎯 Ação ao Docente",   _cached_ia.get("acao_docente","—"), "#FFFBEB", "#78350F", "#F59E0B"),
    ]
    for _titulo, _texto, _bg, _cor_txt, _cor_borda in _secoes:
        st.markdown(
            f'<div style="background:{_bg};border-left:4px solid {_cor_borda};border-radius:8px;'
            f'padding:12px 16px;margin-bottom:10px">'
            f'<div style="font-size:0.68rem;font-weight:700;color:{_cor_borda};text-transform:uppercase;'
            f'letter-spacing:0.07em;margin-bottom:5px">{_titulo}</div>'
            f'<div style="font-size:0.9rem;color:{_cor_txt};line-height:1.6">{_texto}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    
    if f"pdf_ia_bytes_{aluno_sel}" not in st.session_state:
        st.session_state[f"pdf_ia_bytes_{aluno_sel}"] = None

    _col_pdf_ia, _col_reset_ia = st.columns([2, 1])

    with _col_pdf_ia:
        if st.button("📄 Gerar Relatório PDF com IA", width="stretch", type="primary", key="pdf_ia_btn"):
            with st.spinner("Gerando PDF..."):
                st.session_state[f"pdf_ia_bytes_{aluno_sel}"] = gerar_relatorio_individual_ia_pdf(
                    aluno=aluno_sel,
                    turma=turma_label,
                    media_pond=media_pond,
                    risco=risco_aluno,
                    tendencia=tendencia,
                    notas_baixas=notas_baixas,
                    total_avals=total_avals,
                    freq_pct=freq_aluno.get("pct_presenca"),
                    diagnostico=_cached_ia.get("diagnostico", ""),
                    ponto_forte=_cached_ia.get("ponto_forte", ""),
                    ponto_fraco=_cached_ia.get("ponto_fraco", ""),
                    acao_docente=_cached_ia.get("acao_docente", ""),
                    obs_geral=obs_geral,
                )
            st.rerun()
        
        if st.session_state[f"pdf_ia_bytes_{aluno_sel}"] is not None:
            _nome_pdf_ia = f"relatorio_ia_{aluno_sel.replace(' ','_')}_{datetime.now().strftime('%d%m%Y')}.pdf"
            st.download_button(
                "⬇️ Baixar PDF da IA", 
                data=st.session_state[f"pdf_ia_bytes_{aluno_sel}"], 
                file_name=_nome_pdf_ia,
                mime="application/pdf", 
                width="stretch",
                key="download_ia_triggered"
            )

    with _col_reset_ia:
        if st.button("🔄 Reanalisar", width="stretch", key="reset_ia_btn"):
            del st.session_state[_ia_key]
            if f"pdf_ia_bytes_{aluno_sel}" in st.session_state:
                st.session_state[f"pdf_ia_bytes_{aluno_sel}"] = None
            st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# ABA 5 — MODELO PROBABILISTICO
# ══════════════════════════════════════════════════════════════════════════════
def _tab_monte_carlo(df_aluno: pd.DataFrame, media_pond: float) -> None:
    st.markdown(
        '<div style="background:linear-gradient(135deg,#FAF5FF,#F3E8FF);border-radius:14px;'
        'padding:16px 20px;margin-bottom:20px;border:1px solid #E9D5FF">'
        '<div style="font-weight:700;color:#6B21A8;margin-bottom:4px">🎲 Centro de Modelagem Estatística Preditiva</div>'
        '<div style="font-size:0.86rem;color:#7E22CE">Motores estocásticos baseados no histórico do aluno. '
        'Simule milhares de cenários futuros para prever com precisão matemática as chances de aprovação.</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    # =========================================================================
    # TEXTO EXPLICATIVO DOS MÉTODOS PROBABILÍSTICOS (GUIA DO DOCENTE)
    # =========================================================================
    with st.expander("ℹ️ Guia Rápido dos Motores: Como funcionam as simulações?", expanded=False):
        st.markdown("""
        ### Por que usar simulações probabilísticas?
        Em vez de apenas calcular uma média aritmética simples do passado, esses modelos geram **5.000 cenários de futuro possíveis** para as avaliações que o aluno ainda não fez. Isso permite calcular a **densidade de probabilidade real** de aprovação, considerando o fator de incerteza (volatilidade) do estudante.
        
        ---
        
        ### 1. Monte Carlo Tradicional (Estático)
        * **Como funciona:** Assume que o futuro do aluno será uma oscilação natural ao redor da sua média ponderada atual ($\mu$). O modelo usa o desvio padrão ($\sigma$) para simular notas mais altas ou mais baixas, mas sempre puxando o aluno de volta para o seu centro de massa histórico.
        * **Analogia Física:** Um sistema em **regime permanente**. Como um pêndulo oscilando sob uma posição fixa.
        * **Quando usar:** Ideal para alunos estáveis, cujas notas não apresentam grandes picos de melhora ou piora nas últimas semanas.
        
        ### 2. Monte Carlo com Drift Dinâmico
        * **Como funciona:** Identifica se o aluno possui um **momento linear** (uma tendência de aceleração ou desaceleração). O modelo calcula a inclinação matemática de todas as notas passadas e projeta essa força de tendência para o futuro.
        * **Analogia Física:** Um sistema em **movimento cinemático** (posição + velocidade). Se o aluno está em ritmo de recuperação, o modelo injeta essa força propulsora para cima a cada nota futura simulada.
        * **Quando usar:** Ideal para alunos que começaram o semestre mal mas estão subindo rapidamente de rendimento (ou vice-versa), pois o modelo premia o esforço recente de recuperação.
        
        ### 3. Modelagem Industrial PERT-Beta
        * **Como funciona:** Os modelos anteriores usam uma curva normal (simétrica), que teoricamente pode projetar notas impossíveis (como menor que 0 ou maior que 10), exigindo cortes artificiais. O PERT-Beta modela o futuro confinado estritamente no ecossistema real de **0.0 a 10.0**, permitindo curvas **assimétricas**.
        * **Analogia Física:** Um sistema com **limitadores mecânicos de fim de curso** (stops mecânicos). 
        * **Quando usar:** Perfeito para avaliar cenários de risco extremo (alunos excelentes ou muito críticos). Ele entende, por exemplo, que um aluno nota 9.5 tem muita chance de continuar alto, mas sua margem de oscilação é restrita para cima (teto 10) e longa para baixo.
        """, unsafe_allow_html=True)

    DURACAO_DESEJADA_SEG = 10.0
    TOTAL_FRAMES = 40
    SIMULACOES_POR_FRAME = 125
    INTERVALO_SLEEP = DURACAO_DESEJADA_SEG / TOTAL_FRAMES
    NOTA_CORTE = 6.0

    # Tratamento e ordenação cronológica rigorosa
    df_cronos = df_aluno.copy()
    if "Data" in df_cronos.columns:
        df_cronos["Data_dt"] = pd.to_datetime(df_cronos["Data"], errors="coerce", dayfirst=True)
        df_cronos = df_cronos.dropna(subset=["Data_dt"]).sort_values("Data_dt")
    
    notas_historicas = df_cronos["Nota"].dropna().values
    qtd_historica = len(notas_historicas)

    mu = media_pond
    
    # Volatilidade Exponencial (EWMSD)
    if qtd_historica > 1:
        vols_exponenciais = df_cronos["Nota"].ewm(span=4, min_periods=1).std().values
        sigma = vols_exponenciais[-1]
    else:
        sigma = 1.2
    if pd.isna(sigma) or sigma < 0.5: sigma = 0.8

    # Cálculo do Drift (Momento Linear)
    if qtd_historica >= 2:
        x_valores = np.arange(qtd_historica)
        inclinacao, _ = np.polyfit(x_valores, notas_historicas, 1)
        drift_por_avaliacao = inclinacao * 0.5
        drift_por_avaliacao = np.clip(drift_por_avaliacao, -0.75, 0.75)
    else:
        drift_por_avaliacao = 0.0

    # Parametrização do Modelo PERT-Beta
    if qtd_historica >= 2:
        a_pert = max(0.0, np.min(notas_historicas) - 0.5)
        b_pert = min(10.0, np.max(notas_historicas) + 0.5)
    else:
        a_pert = max(0.0, mu - 2 * sigma)
        b_pert = min(10.0, mu + 2 * sigma)
        
    m_pert = mu
    if (b_pert - a_pert) < 0.2:
        a_pert = max(0.0, mu - 1.5)
        b_pert = min(10.0, mu + 1.5)

    alpha1 = 1 + 4 * ((m_pert - a_pert) / (b_pert - a_pert))
    alpha2 = 1 + 4 * ((b_pert - m_pert) / (b_pert - a_pert))

    # Interface do Formulário
    with st.form("mc_simulation_form"):
        c_sel1, c_sel2 = st.columns([1, 1])
        with c_sel1:
            tipo_modelo = st.radio(
                "🧠 Selecione o Motor Probabilístico",
                [
                    "Monte Carlo Tradicional (Estático)", 
                    "Monte Carlo com Drift Dinâmico",
                    "Modelagem Industrial PERT-Beta (Assimétrico)"
                ],
                help="Escolha o motor mais adequado ao comportamento do estudante."
            )
        with c_sel2:
            avals_restantes = st.slider("📝 Avaliações restantes no período", min_value=1, max_value=10, value=4, key="mc_restantes")

        st.markdown("<div style='height:5px'></div>", unsafe_allow_html=True)
        
        if tipo_modelo == "Monte Carlo Tradicional (Estático)":
            st.markdown(
                f'<div style="background:#F9FAFB; border-radius:10px; padding:12px; border:1px solid #E5E7EB">'
                f'<div style="font-size:11px; color:#8E8E93; font-weight:600; text-transform:uppercase">Parâmetros: Regime Permanente Simétrico</div>'
                f'<div style="font-size:13px; color:#1D1D1F; margin-top:4px"><b>μ Estático:</b> {mu:.2f} · <b>σ Exponencial:</b> {sigma:.2f}</div>'
                f'</div>', unsafe_allow_html=True
            )
        elif tipo_modelo == "Monte Carlo com Drift Dinâmico":
            cor_drift = "#34C759" if drift_por_avaliacao >= 0 else "#FF3B30"
            sinal_drift = "+" if drift_por_avaliacao >= 0 else ""
            st.markdown(
                f'<div style="background:#F9FAFB; border-radius:10px; padding:12px; border:1px solid #E5E7EB">'
                f'<div style="font-size:11px; color:#8E8E93; font-weight:600; text-transform:uppercase">Parâmetros: Sistema Dinâmico Não-Estacionário</div>'
                f'<div style="font-size:13px; color:#1D1D1F; margin-top:4px"><b>μ Base:</b> {mu:.2f} · <b>Drift (α):</b> <span style="color:{cor_drift}; font-weight:700">{sinal_drift}{drift_por_avaliacao:.2f}</span></div>'
                f'</div>', unsafe_allow_html=True
            )
        else:
            st.markdown(
                f'<div style="background:#F9FAFB; border-radius:10px; padding:12px; border:1px solid #E5E7EB">'
                f'<div style="font-size:11px; color:#8E8E93; font-weight:600; text-transform:uppercase">Parâmetros: Modelagem de Fronteira Constrangida (PERT)</div>'
                f'<div style="font-size:13px; color:#1D1D1F; margin-top:4px"><b>Pessimista (a):</b> {a_pert:.1f} · <b>Provável (m):</b> {m_pert:.2f} · <b>Otimista (b):</b> {b_pert:.1f}</div>'
                f'</div>', unsafe_allow_html=True
            )
            
        st.markdown("<div style='height:5px'></div>", unsafe_allow_html=True)
        executar_simulacao = st.form_submit_button("🚀 Iniciar Simulação Estatística", type="primary", width="stretch")

    progress_container = st.empty()
    chart_container = st.empty()
    metrics_container = st.empty()

    if executar_simulacao:
        pool_resultados = []
        qtd_total_avals = qtd_historica + avals_restantes
        soma_historica = np.sum(notas_historicas) if qtd_historica > 0 else 0.0
        vetor_drift = np.arange(1, avals_restantes + 1) * drift_por_avaliacao

        config_eixos = dict(gridcolor="#F3F4F6")
        layout_base = dict(
            plot_bgcolor="white", paper_bgcolor="white",
            margin=dict(t=15, b=10, l=10, r=10), height=280, bargap=0.08, showlegend=False
        )

        for frame in range(1, TOTAL_FRAMES + 1):
            t_inicio_frame = time.time()

            if tipo_modelo == "Monte Carlo Tradicional (Estático)":
                ruido = np.random.normal(0.0, sigma, (SIMULACOES_POR_FRAME, avals_restantes))
                notas_simuladas = mu + ruido
                notas_simuladas = np.clip(notas_simuladas, 0.0, 10.0)
            elif tipo_modelo == "Monte Carlo com Drift Dinâmico":
                ruido = np.random.normal(0.0, sigma, (SIMULACOES_POR_FRAME, avals_restantes))
                notas_simuladas = mu + vetor_drift + ruido
                notas_simuladas = np.clip(notas_simuladas, 0.0, 10.0)
            else:
                amostras_beta = np.random.beta(alpha1, alpha2, (SIMULACOES_POR_FRAME, avals_restantes))
                notas_simuladas = a_pert + (b_pert - a_pert) * amostras_beta

            somas_simuladas = np.sum(notas_simuladas, axis=1)
            medias_finais_lote = (soma_historica + somas_simuladas) / qtd_total_avals

            pool_resultados.extend(medias_finais_lote.tolist())
            arr_total = np.array(pool_resultados)
            
            media_atual = np.mean(arr_total)
            prob_aprovacao = (np.sum(arr_total >= NOTA_CORTE) / len(arr_total)) * 100

            pct_progresso = frame / TOTAL_FRAMES
            progress_container.progress(pct_progresso, text=f"Iterações: {len(arr_total)} / {TOTAL_FRAMES * SIMULACOES_POR_FRAME}")

            _cor_metric = "#34C759" if prob_aprovacao >= 70 else ("#F59E0B" if prob_aprovacao >= 50 else "#FF3B30")
            metrics_container.markdown(
                f'<div style="display:grid; grid-template-columns:1fr 1fr; gap:14px; margin-bottom:14px">'
                f'<div class="apple-kpi" style="border-left:3px solid {_cor_metric}; text-align:center">'
                f'<div style="font-size:32px; font-weight:800; color:{_cor_metric}">{prob_aprovacao:.1f}%</div>'
                f'<div class="apple-label">Chance Matemática de Aprovação</div>'
                f'</div>'
                f'<div class="apple-kpi" style="border-left:3px solid #6B21A8; text-align:center">'
                f'<div style="font-size:32px; font-weight:800; color:#6B21A8">{media_atual:.2f}</div>'
                f'<div class="apple-label">Média Esperada dos Cenários</div>'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True
            )

            folga = 0.30
            xmin = max(0.0, min(5.5, np.min(arr_total) - folga))
            xmax = min(10.0, max(6.5, np.max(arr_total) + folga))

            fig = px.histogram(
                x=arr_total, nbins=25,
                color_discrete_sequence=["#A855F7"], opacity=0.75
            )
            
            fig.add_vline(
                x=NOTA_CORTE, line_dash="dash", line_color="#FF3B30", line_width=2,
                annotation_text="Linha de Corte (6.0)", annotation_position="top left",
                annotation_font_color="#FF3B30", annotation_font_size=10
            )
            fig.add_vline(
                x=media_atual, line_dash="dash", line_color="#6B21A8", line_width=2,
                annotation_text=f"Média {media_atual:.2f}", annotation_position="top right",
                annotation_font_color="#6B21A8", annotation_font_size=10
            )

            fig.update_layout(
                xaxis=dict(title="Nota Final Projetada", range=[xmin, xmax], **config_eixos),
                yaxis=dict(title="Cenários Encontrados (Frequência)", **config_eixos),
                **layout_base
            )
            chart_container.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

            t_decorrido_frame = time.time() - t_inicio_frame
            tempo_sono_real = max(0.001, INTERVALO_SLEEP - t_decorrido_frame)
            time.sleep(tempo_sono_real)

        progress_container.empty()
# ══════════════════════════════════════════════════════════════════════════════
# ABA 6 — GUIA DE USO
# ══════════════════════════════════════════════════════════════════════════════
def _tab_ajuda() -> None:  
    st.markdown("""
    <div style="background:linear-gradient(135deg,#1E3A5F 0%,#00539F 60%,#0369A1 100%);
                border-radius:20px;padding:32px 40px;margin-bottom:28px;color:white;
                box-shadow:0 10px 40px rgba(0,83,159,0.3)">
      <div style="font-size:1.6rem;font-weight:800;font-family:Montserrat,sans-serif;margin-bottom:6px">
        📘 Guia do Painel Docente
      </div>
      <div style="opacity:0.8;font-size:0.92rem;line-height:1.6">
        Aprenda a ler cada indicador, interpretar os gráficos e conectar os dados
        para entender o desempenho real de cada aluno.
      </div>
    </div>
    """, unsafe_allow_html=True)

    section_title("🚦 Níveis de Risco")
    st.markdown("""
    <div class="apple-card">
      <div class="apple-label">O que cada cor significa</div>
      <p style="font-size:13px;color:#6B7280;margin:0 0 16px">
        Todo aluno recebe um nível de risco calculado automaticamente a partir da
        média ponderada, sequência de notas baixas e desempenho por vetor.
      </p>
      <div class="resp-grid" style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px">
        <div style="background:#FFF5F5;border-left:4px solid #FF3B30;border-radius:10px;padding:14px">
          <div style="font-weight:800;color:#FF3B30;font-size:1rem;margin-bottom:6px">🔴 Crítico</div>
          <div style="font-size:12px;color:#6B7280;line-height:1.6">
            Média <b>&lt; 6,0</b> <b>OU</b> 3+ notas baixas seguidas <b>OU</b> algum vetor abaixo do mínimo independente.
            Requer intervenção imediata.
          </div>
        </div>
        <div style="background:#FFFBEB;border-left:4px solid #F59E0B;border-radius:10px;padding:14px">
          <div style="font-weight:800;color:#B45309;font-size:1rem;margin-bottom:6px">🟡 Atenção</div>
          <div style="font-size:12px;color:#6B7280;line-height:1.6">
            Média entre <b>6,0 e 6,9</b>. Passou do mínimo, mas com margem pequena.
            Acompanhamento preventivo recomendado.
          </div>
        </div>
        <div style="background:#F0FDF4;border-left:4px solid #34C759;border-radius:10px;padding:14px">
          <div style="font-weight:800;color:#15803D;font-size:1rem;margin-bottom:6px">🟢 Adequado</div>
          <div style="font-size:12px;color:#6B7280;line-height:1.6">
            Média entre <b>7,0 e 8,4</b>. Dentro do esperado.
            Sem necessidade de ação imediata.
          </div>
        </div>
        <div style="background:#F0F9FF;border-left:4px solid #007AFF;border-radius:10px;padding:14px">
          <div style="font-weight:800;color:#007AFF;font-size:1rem;margin-bottom:6px">🔵 Excelente</div>
          <div style="font-size:12px;color:#6B7280;line-height:1.6">
            Média <b>≥ 8,5</b>. Desempenho acima do esperado.
            Pode receber desafios adicionais.
          </div>
        </div>
      </div>
      <div style="background:#F8FAFC;border-radius:10px;padding:14px;margin-top:16px;
                  font-size:12px;color:#6B7280;border-left:3px solid #E5E7EB">
        <b>⚠️ Atenção:</b> Um aluno pode ter média 7,0 mas ainda ser <b>Crítico</b> se tiver um vetor
        (Fazer, Saber ou Comportamento) com nota abaixo do mínimo independente — verifique sempre os vetores.
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
    section_title("📋 Aba: Visão Geral")

    with st.expander("📌 KPIs do Topo — Média, Frequência e Alertas", expanded=True):
        st.markdown("""
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px;padding:4px 0">
          <div style="background:#F8FAFC;border-radius:12px;padding:16px;border-top:3px solid #007AFF">
            <div style="font-size:11px;font-weight:700;color:#8E8E93;text-transform:uppercase;margin-bottom:8px">
              📊 Média Ponderada
            </div>
            <div style="font-size:13px;color:#1D1D1F;line-height:1.7">
              Calculada com <b>pesos por instrumento e vetor</b> (Fazer 40%, Saber 30%, Comportamento 30%).
              É a nota oficial para fins de aprovação.<br><br>
              <b>Diferente da média simples</b> — um aluno pode ter média simples 7,0 mas ponderada 5,8
              se suas notas boas forem em instrumentos de menor peso.
            </div>
          </div>
          <div style="background:#F8FAFC;border-radius:12px;padding:16px;border-top:3px solid #34C759">
            <div style="font-size:11px;font-weight:700;color:#8E8E93;text-transform:uppercase;margin-bottom:8px">
              📅 Frequência
            </div>
            <div style="font-size:13px;color:#1D1D1F;line-height:1.7">
              Percentual de dias letivos em que o aluno esteve presente.<br><br>
              <b>Mínimo obrigatório: 75%.</b><br>
              Cor laranja = abaixo de 85% (atenção).<br>
              Cor vermelha = abaixo de 75% (reprovação por falta).
            </div>
          </div>
          <div style="background:#F8FAFC;border-radius:12px;padding:16px;border-top:3px solid #FF3B30">
            <div style="font-size:11px;font-weight:700;color:#8E8E93;text-transform:uppercase;margin-bottom:8px">
              ⚠️ Alertas de Notas
            </div>
            <div style="font-size:13px;color:#1D1D1F;line-height:1.7">
              Contagem de notas abaixo de 6,0 no período.<br><br>
              1-2 notas baixas = atenção pontual.<br>
              3+ notas baixas seguidas = sequência crítica, aluno em risco de reprovação.
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)

    with st.expander("🧠 Diagnóstico Automático — Como interpretar"):
        st.markdown("""
        <div style="font-size:13px;color:#1D1D1F;line-height:1.8;padding:4px 0">
          O diagnóstico é gerado por <b>regras lógicas</b> (não IA) a partir dos dados do aluno.
          Ele analisa <b>8 dimensões</b>:
          <ol style="margin-top:10px;padding-left:20px;line-height:2.2">
            <li><b>Situação geral</b> — risco + gap entre média simples e ponderada</li>
            <li><b>Posição na turma</b> — ranking percentual (top 25%, intermediário, quartil inferior)</li>
            <li><b>Comparação com turma</b> — quanto está acima/abaixo da média geral</li>
            <li><b>Consistência</b> — desvio-padrão: notas estáveis (bom sinal) vs. notas irregulares (atenção)</li>
            <li><b>Tendência recente</b> — as últimas avaliações estão melhorando, caindo ou estáveis?</li>
            <li><b>Sequência crítica</b> — alerta se 3+ notas baixas consecutivas</li>
            <li><b>Critérios</b> — qual critério avaliado é o ponto forte e qual é o fraco</li>
            <li><b>Velocidade e Vetores</b> — Fazer/Saber/Comportamento: qual está puxando a média para baixo?</li>
          </ol>
          <div style="background:#F0F9FF;border-radius:10px;padding:12px 16px;margin-top:12px;
                      border-left:3px solid #007AFF;font-size:12px">
            <b>💡 Dica:</b> O botão <b>"Ver diagnóstico completo"</b> expande todas as 8 dimensões.
            O resumo padrão mostra apenas as informações mais críticas do momento.
          </div>
        </div>
        """, unsafe_allow_html=True)

    with st.expander("🕸️ Radar de Habilidades — Como ler"):
        st.markdown("""
        <div style="font-size:13px;color:#1D1D1F;line-height:1.8;padding:4px 0">
          O radar mostra a <b>média por critério avaliado</b> (ex: Exatidão Dimensional, Planejamento/Lógica…).
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px">
            <div style="background:#F0F9FF;border-radius:10px;padding:12px;font-size:12px">
              <b style="color:#007AFF">🔵 Área azul</b> — notas do aluno.<br>
              Quanto maior a área, melhor o desempenho geral.
            </div>
            <div style="background:#F8FAFC;border-radius:10px;padding:12px;font-size:12px">
              <b style="color:#6B7280">⬜ Área cinza</b> — média da turma (quando ativado).<br>
              Compara onde o aluno está acima ou abaixo da turma.
            </div>
          </div>
          <div style="margin-top:12px;font-size:12px;color:#6B7280">
            <b>Vértices "afundados"</b> (próximos ao centro) = ponto fraco específico — foque ali.<br>
            <b>Radar muito pequeno no geral</b> = dificuldade ampla, não isolada.
          </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
    section_title("📊 Aba: Desempenho")

    with st.expander("🎯 Vetores — Fazer, Saber e Comportamento"):
        st.markdown("""
        <div style="font-size:13px;color:#1D1D1F;line-height:1.8;padding:4px 0">
          O sistema avalia o aluno em <b>3 vetores com pesos diferentes</b>:
          <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin:12px 0">
            <div style="background:#EFF6FF;border-radius:10px;padding:14px;border-top:3px solid #007AFF">
              <div style="font-weight:700;color:#007AFF;margin-bottom:6px">🔨 Fazer (40%)</div>
              <div style="font-size:12px;color:#374151">Habilidades práticas e técnicas.
              Projetos, observações em oficina, atividades hands-on.</div>
            </div>
            <div style="background:#FFF1F2;border-radius:10px;padding:14px;border-top:3px solid #FF3B30">
              <div style="font-weight:700;color:#FF3B30;margin-bottom:6px">📚 Saber (30%)</div>
              <div style="font-size:12px;color:#374151">Conhecimento teórico.
              Provas escritas, apresentações, quizzes.</div>
            </div>
            <div style="background:#F5F5F7;border-radius:10px;padding:14px;border-top:3px solid #8E8E93">
              <div style="font-weight:700;color:#48484A;margin-bottom:6px">🤝 Comportamento (30%)</div>
              <div style="font-size:12px;color:#374151">Atitudes e postura.
              Observações de conduta, colaboração, pontualidade.</div>
            </div>
          </div>
          <div style="background:#FFF5F5;border-radius:10px;padding:12px 16px;border-left:3px solid #FF3B30;font-size:12px">
            <b>⚠️ Regra importante:</b> Cada vetor tem um <b>mínimo independente</b>.
            Se o aluno tiver 9,0 de média mas Comportamento 3,0 — pode reprovar por esse vetor isoladamente.
            Verifique sempre os 3 vetores individualmente.
          </div>
        </div>
        """, unsafe_allow_html=True)

    with st.expander("📈 Evolução por Semana — Como ler"):
        st.markdown("""
        <div style="font-size:13px;color:#1D1D1F;line-height:1.8;padding:4px 0">
          Mostra a <b>média das avaliações agrupadas por semana ISO</b> (ex: 2025-S10 = semana 10 de 2025).
          <div style="margin-top:12px;display:grid;grid-template-columns:1fr 1fr;gap:12px">
            <div style="background:#F8FAFC;border-radius:10px;padding:12px;font-size:12px">
              <b>Barras coloridas:</b><br>
              🟢 Verde = semana com média ≥ 7,0<br>
              🟡 Amarelo = média entre 6,0 e 6,9<br>
              🔴 Vermelho = média abaixo de 6,0
            </div>
            <div style="background:#F8FAFC;border-radius:10px;padding:12px;font-size:12px">
              <b>Linha pontilhada azul:</b><br>
              Tendência de evolução — se está subindo, o aluno está melhorando semana a semana.
              Se caindo, há regressão recente.
            </div>
          </div>
          <div style="margin-top:12px;font-size:12px;color:#6B7280">
            <b>Como usar:</b> Identifique semanas com barras vermelhas e verifique
            o que aconteceu naquele período (ausências? avaliação difícil? problema pessoal?).
          </div>
        </div>
        """, unsafe_allow_html=True)

    with st.expander("📉 Boxplot por Vetor — O que significa"):
        st.markdown("""
        <div style="font-size:13px;color:#1D1D1F;line-height:1.8;padding:4px 0">
          O boxplot mostra a <b>dispersão das notas</b> dentro de cada vetor:
          <div style="margin-top:10px;background:#F8FAFC;border-radius:10px;padding:14px;font-size:12px;line-height:2">
            <b>Caixa estreita e alta</b> → notas consistentes, pouca variação.<br>
            <b>Caixa larga</b> → notas muito irregulares no mesmo vetor (bom em alguns, ruim em outros).<br>
            <b>Pontos abaixo da linha vermelha</b> → avaliações críticas (abaixo de 6,0).<br>
            <b>Ponto isolado ("outlier")</b> → nota muito fora do padrão habitual do aluno — investigar.
          </div>
        </div>
        """, unsafe_allow_html=True)

    with st.expander("🔬 Raio-X das Atividades — Como usar"):
        st.markdown("""
        <div style="font-size:13px;color:#1D1D1F;line-height:1.8;padding:4px 0">
          O <b>Raio-X das Atividades</b> mostra o desempenho do aluno em cada instrumento de avaliação
          (ex: Prova Escrita, Projeto Prático, Observação de Conduta…), ordenado do pior para o melhor.
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:12px 0">
            <div style="background:#F8FAFC;border-radius:10px;padding:14px;font-size:12px">
              <b>🟥 Barra vermelha</b><br>
              Média abaixo de 6,0 — essa atividade está reprovando o aluno.
              Ação imediata de reforço ou recuperação direcionada.
            </div>
            <div style="background:#FFFBEB;border-radius:10px;padding:14px;font-size:12px">
              <b>🟨 Barra amarela</b><br>
              Média entre 6,0 e 6,9 — passou, mas com margem mínima.
              Monitorar nas próximas avaliações do mesmo tipo.
            </div>
            <div style="background:#F0FDF4;border-radius:10px;padding:14px;font-size:12px">
              <b>🟢 Pontos coloridos sobrepostos</b><br>
              Cada ponto = uma avaliação individual. Pontos espalhados = irregularidade.
              Pontos agrupados no alto = consistência positiva.
            </div>
            <div style="background:#F0F9FF;border-radius:10px;padding:14px;font-size:12px">
              <b>📊 Tabela abaixo do gráfico</b><br>
              Mostra mínima, máxima, quantidade de avaliações e a taxa de aprovação
              (% de notas ≥ 6,0) por atividade.
            </div>
          </div>
          <div style="background:#FFF5F5;border-radius:10px;padding:12px;border-left:3px solid #FF3B30;font-size:12px">
            <b>💡 Como usar na prática:</b> Identifique as atividades no topo da lista (piores).
            Se forem do mesmo vetor (ex: todos "Saber"), o problema é teórico.
            Se forem de vetores diferentes, o aluno tem dificuldade generalizada — não apenas em um tipo.
          </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
    section_title("📅 Aba: Frequência")

    with st.expander("🗓️ Calendário de Presenças — Como ler"):
        st.markdown("""
        <div style="font-size:13px;color:#1D1D1F;line-height:1.8;padding:4px 0">
          O calendário mostra <b>cada dia letivo registrado</b>, organizado por semana (linhas) e dia da semana (colunas).
          <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin:12px 0">
            <div style="background:#F0FDF4;border-radius:10px;padding:12px;text-align:center;font-size:12px">
              <div style="font-size:18px">✓</div>
              <b style="color:#34C759">Verde</b><br>Presente
            </div>
            <div style="background:#FFF5F5;border-radius:10px;padding:12px;text-align:center;font-size:12px">
              <div style="font-size:18px">✗</div>
              <b style="color:#FF3B30">Vermelho</b><br>Falta
            </div>
            <div style="background:#F5F5F7;border-radius:10px;padding:12px;text-align:center;font-size:12px">
              <div style="font-size:18px"> </div>
              <b style="color:#8E8E93">Cinza vazio</b><br>Sem aula
            </div>
          </div>
          <div style="font-size:12px;color:#6B7280">
            <b>Padrões a observar:</b><br>
            • Coluna inteira vermelha em "Seg" ou "Sex" → padrão de faltas estratégicas.<br>
            • Bloco de semanas seguidas com vermelho → período de ausência prolongada.<br>
            • Vermelho logo antes de barras baixas no gráfico semanal → falta impactando nota.
          </div>
        </div>
        """, unsafe_allow_html=True)

    with st.expander("📉 Linha do Tempo: Notas × Faltas — Como ler"):
        st.markdown("""
        <div style="font-size:13px;color:#1D1D1F;line-height:1.8;padding:4px 0">
          O gráfico de linha mostra <b>todas as notas do aluno em ordem cronológica</b>,
          com marcadores de falta sobrepostos na mesma linha do tempo.
          <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin:12px 0">
            <div style="background:#F0F9FF;border-radius:10px;padding:12px;font-size:12px;text-align:center">
              <div style="font-size:20px;margin-bottom:6px">🔵</div>
              <b style="color:#007AFF">Linha azul</b><br>
              Trajetória das notas ao longo do tempo. Subindo = melhora. Caindo = regressão.
            </div>
            <div style="background:#FFF5F5;border-radius:10px;padding:12px;font-size:12px;text-align:center">
              <div style="font-size:20px;margin-bottom:6px">▲</div>
              <b style="color:#FF3B30">Triângulos vermelhos</b><br>
              Dias com falta registrada. Se aparecem antes de quedas na linha, a falta impactou a nota.
            </div>
            <div style="background:#FFF5F5;border-radius:10px;padding:12px;font-size:12px;text-align:center">
              <div style="font-size:20px;margin-bottom:6px">- - -</div>
              <b style="color:#FF3B30">Linha pontilhada</b><br>
              Nota mínima (6,0). Pontos abaixo dela são avaliações críticas.
            </div>
          </div>
          <div style="background:#F0FDF4;border-radius:10px;padding:12px;border-left:3px solid #34C759;font-size:12px">
            <b>💡 O que observar:</b><br>
            • Triângulo vermelho <b>logo antes de ponto vermelho na linha</b> → forte evidência de que a falta causou a queda.<br>
            • Triângulo vermelho <b>sem queda na nota seguinte</b> → aluno manteve o ritmo mesmo faltando; possível estudo autônomo.<br>
            • Vários triângulos em sequência + linha descendo → padrão de ausência crônica com impacto cumulativo.
          </div>
        </div>
        """, unsafe_allow_html=True)

    with st.expander("🧮 IIF — Índice de Impacto da Frequência"):
        st.markdown("""
        <div style="font-size:13px;color:#1D1D1F;line-height:1.8;padding:4px 0">
          O IIF mede <b>o quanto as faltas estão prejudicando as notas</b>, numa escala de 0 a 10.
          <div class="resp-grid" style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:12px 0">
            <div style="background:#F0FDF4;border-radius:10px;padding:12px;text-align:center;font-size:12px">
              <b style="color:#34C759">0–2</b><br><br>Baixo risco<br>Frequência não compromete
            </div>
            <div style="background:#FFFBEB;border-radius:10px;padding:12px;text-align:center;font-size:12px">
              <b style="color:#F59E0B">3–4</b><br><br>Atenção<br>Queda leve por falta
            </div>
            <div style="background:#FFF3E0;border-radius:10px;padding:12px;text-align:center;font-size:12px">
              <b style="color:#F97316">5–6</b><br><br>Alto risco<br>Impacto considerável
            </div>
            <div style="background:#FFF5F5;border-radius:10px;padding:12px;text-align:center;font-size:12px">
              <b style="color:#FF3B30">7–10</b><br><br>Crítico<br>Falta é causa principal
            </div>
          </div>
          <div style="background:#F8FAFC;border-radius:10px;padding:12px;font-size:12px;color:#6B7280;border-left:3px solid #E5E7EB">
            <b>⚠️ Importante:</b> O IIF mede correlação, não causa. Falta e nota baixa podem ter
            a mesma origem (ex: problema familiar, desmotivação). Use como sinal de atenção, não como julgamento.
          </div>
          <div style="margin-top:12px;font-size:12px;color:#374151">
            <b>Nota projetada</b> = estimativa da nota final se o padrão de faltas continuar.
            Útil para conversar preventivamente com o aluno antes que ele reprove.
          </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
    section_title("🤖 Aba: Análise IA")

    with st.expander("🧠 Como a IA analisa o aluno"):
        st.markdown("""
        <div style="font-size:13px;color:#1D1D1F;line-height:1.8;padding:4px 0">
          A análise IA envia os dados do aluno para o modelo <b>Kimi K2</b> (Groq) e retorna um diagnóstico
          pedagógico enriquecido, levando em conta principalmente as <b>observações escritas pelo docente</b>.
          <div style="margin-top:12px;display:grid;grid-template-columns:1fr 1fr;gap:12px">
            <div style="background:#F5F3FF;border-radius:10px;padding:14px;font-size:12px">
              <b style="color:#7C3AED">O que a IA recebe:</b><br><br>
              • Média, risco, tendência<br>
              • Notas críticas e critérios fracos<br>
              • Vetor mais fraco<br>
              • <b>Observações individuais do docente</b> (as mais relevantes)
            </div>
            <div style="background:#F0FDF4;border-radius:10px;padding:14px;font-size:12px">
              <b style="color:#15803D">O que a IA gera:</b><br><br>
              • Diagnóstico contextualizado<br>
              • Ponto forte identificado<br>
              • Ponto fraco com sugestão<br>
              • <b>Ação pedagógica concreta</b>
            </div>
          </div>
          <div style="background:#FFFBEB;border-radius:10px;padding:12px;margin-top:12px;
                      font-size:12px;border-left:3px solid #F59E0B">
            <b>💡 Dica:</b> Quanto mais observações individuais o docente escrever na planilha,
            mais rica e personalizada será a análise da IA.
            Observações genéricas de turma são filtradas automaticamente.
          </div>
          <div style="background:#F8FAFC;border-radius:10px;padding:12px;margin-top:10px;font-size:12px;color:#6B7280">
            <b>Cache de 5 dias:</b> A análise é salva por 5 dias para não gastar tokens desnecessariamente.
            Clique em "Reanalisar" para forçar uma nova análise com dados atualizados.
          </div>
        </div>
        """, unsafe_allow_html=True)

    with st.expander("🔌 Quando a IA está indisponível — Diagnóstico Automático"):
        st.markdown("""
        <div style="font-size:13px;color:#1D1D1F;line-height:1.8;padding:4px 0">
          Se a chave da API Groq não estiver configurada ou a conexão com o servidor falhar,
          o sistema exibe automaticamente o <b>Diagnóstico Automático da Turma</b> como alternativa.
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:12px 0">
            <div style="background:#F5F3FF;border-radius:10px;padding:14px;font-size:12px">
              <b style="color:#7C3AED">O que aparece no fallback:</b><br><br>
              • KPIs da turma (média, críticos, atenção, adequados, excelentes)<br>
              • Diagnóstico resumido de cada aluno<br>
              • Tags de situação (positivo / negativo / neutro)<br>
              • Ordenado do mais crítico para o melhor
            </div>
            <div style="background:#FFF7ED;border-radius:10px;padding:14px;font-size:12px">
              <b style="color:#C2410C">Diferença da análise IA completa:</b><br><br>
              • Não usa linguagem natural elaborada<br>
              • Não considera observações escritas do docente<br>
              • Mas é <b>100% offline</b>, instantânea e sempre disponível<br>
              • Usa as mesmas 8 dimensões do diagnóstico automático
            </div>
          </div>
          <div style="background:#F0FDF4;border-radius:10px;padding:12px;border-left:3px solid #34C759;font-size:12px">
            <b>💡 Dica:</b> Para ativar a IA completa, adicione a chave <code>GROQ_API_KEY</code>
            ao arquivo <code>.streamlit/secrets.toml</code>. A chave começa com <code>gsk_</code>
            e pode ser obtida gratuitamente em <b>console.groq.com</b>.
          </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
    section_title("🔗 Conectando os Dados — Leitura Completa do Aluno")

    st.markdown("""
    <div class="apple-card">
      <div class="apple-label">Fluxo de Leitura Recomendado</div>
      <div style="font-size:13px;color:#6B7280;margin:0 0 16px">
        Siga esta sequência para ter uma visão completa e precisa do aluno:
      </div>
      <div style="display:flex;flex-direction:column;gap:0">
    """, unsafe_allow_html=True)

    passos = [
        ("#007AFF", "1", "Comece pelo nível de risco e as KPIs no topo",
         "O badge colorido (🔴🟡🟢🔵) e as três métricas principais dão o diagnóstico rápido. "
         "Se estiver vermelho, o restante da leitura é prioritário."),
        ("#8B5CF6", "2", "Leia o Diagnóstico Automático",
         "Clique em 'Ver diagnóstico completo' para entender <b>por que</b> o aluno está naquele risco. "
         "O diagnóstico identifica se o problema é tendência, consistência, critério específico ou vetor."),
        ("#34C759", "3", "Verifique os 3 vetores individualmente",
         "Na aba Desempenho, veja Fazer, Saber e Comportamento separadamente. "
         "Um vetor abaixo do mínimo pode reprovar o aluno mesmo com boa média geral."),
        ("#F59E0B", "4", "Analise a Evolução e o Raio-X das Atividades",
         "O gráfico semanal mostra <b>quando</b> o aluno começou a piorar ou melhorar. "
         "Depois use o <b>Raio-X das Atividades</b> para identificar <b>qual instrumento específico</b> "
         "(Prova Escrita, Projeto, Observação…) está puxando a nota para baixo. "
         "Barras vermelhas no topo do Raio-X = atividades críticas."),
        ("#FF3B30", "5", "Cruze com a Frequência e a Linha do Tempo",
         "Abra o Calendário de Presenças e o gráfico <b>Linha do Tempo: Notas × Faltas</b>. "
         "Se os triângulos vermelhos (faltas) aparecem logo antes das quedas na linha de notas, "
         "o problema é presença. Se a linha cai sem faltas, é dificuldade de conteúdo. "
         "O IIF quantifica o impacto numa escala de 0 a 10."),
        ("#0369A1", "6", "Use a Análise IA para o diagnóstico final",
         "Após entender os dados quantitativos, a IA complementa com interpretação das "
         "<b>observações que você mesmo escreveu</b>. A ação pedagógica sugerida é o ponto de partida "
         "for a intervenção."),
    ]
    for cor, num, titulo, desc in passos:
        st.markdown(f"""
        <div style="display:flex;gap:16px;align-items:flex-start;padding:14px 0;
                    border-bottom:1px solid #F2F2F7">
          <div style="width:32px;height:32px;border-radius:50%;background:{cor};
                      color:white;display:flex;align-items:center;justify-content:center;
                      font-weight:800;font-size:14px;flex-shrink:0;margin-top:2px">{num}</div>
          <div>
            <div style="font-size:14px;font-weight:700;color:#1D1D1F;margin-bottom:4px">{titulo}</div>
            <div style="font-size:12px;color:#6B7280;line-height:1.7">{desc}</div>
          </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown('</div></div>', unsafe_allow_html=True)

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
    section_title("🔍 Situações Comuns e Como Agir")

    casos = [
        ("🔴 Média baixa + IIF alto + Calendário cheio de vermelho",
         "Problema de frequência.",
         "O aluno falta muito e isso impacta diretamente as notas. Ação: contato com responsável, "
         "investigar o motivo das faltas. Ofereça reposição de conteúdo antes de cobrar desempenho.",
         "#FFF5F5", "#FF3B30"),
        ("🟡 Média razoável + Vetor 'Saber' crítico + Notas irregulares",
         "Dificuldade teórica específica.",
         "O aluno se sai bem na prática mas tem dificuldade nas provas e teoria. Ação: reforço teórico "
         "individualizado, revisão dos conteúdos avaliados nas provas, verificar se há dificuldade de leitura/escrita.",
         "#FFFBEB", "#F59E0B"),
        ("🔴 Sequência crítica de 4+ notas + Frequência OK",
         "Desmotivação ou dificuldade de aprendizado.",
         "O aluno está presente mas não consegue atingir o mínimo. Ação: conversa individual, verificar "
         "se houve mudança na vida pessoal, identificar o critério mais fraco e planejar recuperação direcionada.",
         "#FFF5F5", "#FF3B30"),
        ("🟢 Média boa + Diagnóstico 'ponderada desfavorável'",
         "Bom aluno com ponto fraco nos instrumentos pesados.",
         "O aluno tem boas notas simples mas os instrumentos de maior peso (projetos, provas) estão puxando "
         "a ponderada para baixo. Ação: identificar quais instrumentos pesados estão baixos e direcionar esforço neles.",
         "#F0FDF4", "#34C759"),
        ("🔵 Excelente + Radar muito regular e cheio",
         "Aluno de alto desempenho.",
         "Todas as dimensões são boas. Ação: oferecer desafios adicionais, projetos de extensão ou mentoria "
         "para outros alunos. Não negligencie — alunos excelentes podem regredir sem estímulo.",
         "#F0F9FF", "#007AFF"),
    ]
    for titulo, subtitulo, acao, bg, cor in casos:
        st.markdown(f"""
        <div style="background:{bg};border-left:4px solid {cor};border-radius:0 12px 12px 0;
                    padding:16px 20px;margin-bottom:10px">
          <div style="font-size:13px;font-weight:700;color:#1D1D1F;margin-bottom:2px">{titulo}</div>
          <div style="font-size:11px;font-weight:700;color:{cor};text-transform:uppercase;
                      letter-spacing:0.06em;margin-bottom:8px">{subtitulo}</div>
          <div style="font-size:12px;color:#374151;line-height:1.7">
            <b>Como agir:</b> {acao}
          </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
    section_title("🔀 Cruzando Informações Entre Abas")

    st.markdown("""
    <div class="apple-card">
      <div class="apple-label">Por que cruzar dados?</div>
      <p style="font-size:13px;color:#6B7280;margin:0 0 14px;line-height:1.7">
        Cada aba responde uma pergunta diferente. O diagnóstico real aparece quando você
        <b>combina as respostas</b>. Um dado isolado pode enganar — dois dados juntos revelam a causa.
      </p>
    </div>
    """, unsafe_allow_html=True)

    cruzamentos = [
        (
            "Visão Geral",    "#007AFF",
            "Desempenho",     "#F59E0B",
            "Diagnóstico diz 'vetor fraco'",
            "Confirme qual vetor está baixo",
            "Se o diagnóstico apontou 'Saber fraco', abra Desempenho → Vetores de Competência "
            "e veja a barra do Saber. Depois vá no Raio-X das Atividades e veja quais instrumentos "
            "(Prova Escrita, Quiz…) estão puxando aquele vetor para baixo. "
            "<b>Resultado: você sabe exatamente qual atividade requer recuperação.</b>",
        ),
        (
            "Desempenho",     "#F59E0B",
            "Frequência",     "#FF3B30",
            "Evolução semanal com quedas",
            "Descubra se as quedas têm faltas por trás",
            "Identifique as semanas com barras vermelhas no gráfico semanal (Desempenho). "
            "Anote o número dessas semanas (ex: S08, S09). Abra a aba Frequência → "
            "Linha do Tempo e veja se há triângulos vermelhos nessas mesmas semanas. "
            "Se sim, as faltas causaram as quedas. Se não, é dificuldade de conteúdo. "
            "<b>Resultado: a causa da queda fica clara em menos de 30 segundos.</b>",
        ),
        (
            "Frequência",     "#FF3B30",
            "Visão Geral",    "#007AFF",
            "IIF alto (≥ 5)",
            "Cheque se o risco geral reflete a frequência",
            "Se o IIF for alto, volte à Visão Geral e leia o diagnóstico automático completo. "
            "Se ele citar 'tendência de queda' junto com IIF alto, a frequência é o motor da queda. "
            "Se o diagnóstico citar 'inconsistência' mas sem queda, o aluno até frequenta mas "
            "não está aprendendo — são problemas diferentes que pedem soluções diferentes. "
            "<b>Resultado: você distingue 'falta que causa queda' de 'presença sem aprendizado'.</b>",
        ),
        (
            "Desempenho",     "#F59E0B",
            "Raio-X",          "#8B5CF6",
            "Radar com vértice afundado em um critério",
            "Identifique qual atividade está causando aquele critério fraco",
            "O radar mostra que 'Metrologia' está fraco. Abra o Raio-X das Atividades e filtre "
            "mentalmente as atividades de Metrologia (ex: Prova de Metrologia, Quiz Dimensional). "
            "Se todas as atividades daquele critério estiverem vermelhas, o problema é sistemático. "
            "Se apenas uma estiver vermelha, foi um evento pontual. "
            "<b>Resultado: você decide entre reforço contínuo ou recuperação pontual.</b>",
        ),
        (
            "Análise IA",     "#7C3AED",
            "Frequência",     "#FF3B30",
            "IA sugere 'investigar fatores externos'",
            "Use o calendário como evidência concreta",
            "Quando a IA sugere 'fatores externos', abra o Calendário de Presenças. "
            "Se há um bloco de semanas seguidas com vermelho (ausência prolongada), "
            "isso é evidência concreta de um evento de vida (doença, trabalho, problema familiar). "
            "Anote as semanas antes da conversa com o aluno — datas concretas ajudam a "
            "abrir o diálogo sem parecer acusação. "
            "<b>Resultado: você chega ao aluno com dados, não com suposições.</b>",
        ),
        (
            "Visão Geral",    "#007AFF",
            "Análise IA",     "#7C3AED",
            "Badge mudou de 🟢 para 🔴 após atualização",
            "Use a IA para entender a velocidade da regressão",
            "Se o aluno regrediu de Adequado para Crítico rapidamente, abra a Análise IA "
            "e clique em 'Reanalisar'. A IA terá contexto atualizado e poderá identificar "
            "se a regressão tem padrão (ex: 'queda consistente há 3 semanas') ou foi pontual "
            "(ex: 'uma prova muito abaixo da média'). A ação é completamente diferente em cada caso. "
            "<b>Resultado: você não trata regressão pontual como crise — nem ignora crise como pontual.</b>",
        ),
    ]

    for i, (aba_a, cor_a, aba_b, cor_b, gatilho, objetivo, como) in enumerate(cruzamentos):
        bg = "#F8FAFC" if i % 2 == 0 else "white"
        st.markdown(f"""
        <div style="background:{bg};border-radius:14px;padding:18px 22px;margin-bottom:12px;
                    border:1px solid #F2F2F7">
          <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px;flex-wrap:wrap">
            <span style="background:{cor_a};color:white;font-size:11px;font-weight:700;
                         padding:4px 12px;border-radius:50px">{aba_a}</span>
            <span style="font-size:16px;color:#C7C7CC">→</span>
            <span style="background:{cor_b};color:white;font-size:11px;font-weight:700;
                         padding:4px 12px;border-radius:50px">{aba_b}</span>
            <span style="margin-left:auto;font-size:11px;font-weight:600;color:#8E8E93">
              Quando: <b style="color:#1D1D1F">{gatilho}</b>
            </span>
          </div>
          <div style="font-size:13px;font-weight:700;color:#1D1D1F;margin-bottom:6px">
            🎯 {objetivo}
          </div>
          <div style="font-size:12px;color:#374151;line-height:1.75">{como}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("""
    <div style="background:linear-gradient(135deg,#1E3A5F,#0369A1);border-radius:14px;
                padding:18px 24px;margin-bottom:8px;color:white;font-size:12px;line-height:1.8">
      <b style="font-size:13px">🧠 Regra de ouro do cruzamento</b><br><br>
      Sempre que encontrar um indicador negativo (badge vermelho, IIF alto, barra vermelha no Raio-X,
      vértice afundado no radar), faça a pergunta: <b>"isso aparece em mais de uma aba?"</b><br><br>
      Se o mesmo problema aparece em 2 ou mais abas → é um padrão real, não ruído.
      Se aparece em apenas 1 aba → investigue mais antes de agir.
      <b>Quanto mais indicadores apontam na mesma direção, mais confiante você pode ser na intervenção.</b>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
    section_title("🎓 Exemplo Prático — Analisando João Silva")
    st.markdown("""
    <div style="background:linear-gradient(135deg,#1E3A5F,#0369A1);border-radius:16px;
                padding:20px 28px;margin-bottom:20px;color:white">
      <div style="font-size:0.75rem;font-weight:700;text-transform:uppercase;
                  letter-spacing:0.12em;opacity:0.7;margin-bottom:4px">Caso fictício para fins didáticos</div>
      <div style="font-size:1.2rem;font-weight:800;font-family:Montserrat,sans-serif">
        João Silva · Técnico em Mecatrônica · Turma 2025-A
      </div>
      <div style="opacity:0.75;font-size:0.85rem;margin-top:4px">
        Acompanhe a leitura passo a passo de um aluno real e como chegar à ação correta
      </div>
    </div>
    """, unsafe_allow_html=True)

    with st.expander("📍 Passo 1 — Olhar o badge de risco e os KPIs", expanded=True):
        st.markdown("""
        <div style="font-size:13px;color:#1D1D1F;line-height:1.8;padding:4px 0">
          Ao abrir o perfil de João, você vê:
          <div style="background:#FFF5F5;border-radius:12px;padding:16px 20px;margin:12px 0;
                      border-left:5px solid #FF3B30">
            <div class="resp-grid" style="display:grid;grid-template-columns:repeat(3,1fr);gap:14px">
              <div style="text-align:center">
                <div style="font-size:26px;font-weight:800;color:#FF3B30">5,8</div>
                <div style="font-size:10px;font-weight:700;color:#8E8E93;text-transform:uppercase">Média Ponderada</div>
              </div>
              <div style="text-align:center">
                <div style="font-size:26px;font-weight:800;color:#F59E0B">71%</div>
                <div style="font-size:10px;font-weight:700;color:#8E8E93;text-transform:uppercase">Frequência</div>
              </div>
              <div style="text-align:center">
                <div style="font-size:26px;font-weight:800;color:#FF3B30">4</div>
                <div style="font-size:10px;font-weight:700;color:#8E8E93;text-transform:uppercase">Notas críticas</div>
              </div>
            </div>
          </div>
          <b>O que isso significa imediatamente:</b>
          <ul style="margin-top:8px;padding-left:20px;line-height:2.1;color:#374151;font-size:12px">
            <li>🔴 Badge <b>Crítico</b> — a média ponderada está abaixo de 6,0</li>
            <li>🟡 Frequência <b>71%</b> — abaixo do mínimo de 75%, risco de reprovação por falta</li>
            <li>⚠️ <b>4 notas críticas</b> — mais de ⅓ das avaliações abaixo do mínimo</li>
          </ul>
          <div style="background:#F0F9FF;border-radius:10px;padding:10px 14px;font-size:12px;
                      border-left:3px solid #007AFF;margin-top:8px">
            <b>Conclusão do passo 1:</b> João tem dois problemas simultâneos — nota baixa E frequência baixa.
            Preciso entender qual veio primeiro.
          </div>
        </div>
        """, unsafe_allow_html=True)

    with st.expander("📍 Passo 2 — Ler o Diagnóstico Automático"):
        st.markdown("""
        <div style="font-size:13px;color:#1D1D1F;line-height:1.8;padding:4px 0">
          O diagnóstico resumido diz:
          <div style="background:#EBF4FF;border:1px solid #BAE6FD;border-radius:12px;
                      padding:16px 20px;margin:12px 0;border-left:5px solid #007AFF;
                      font-size:12px;color:#1E3A5F;line-height:1.75;font-style:italic">
            "João está em situação crítica (média ponderada 5,8). Ocupa o 18º lugar entre 20 alunos.
            Apresenta tendência de queda nas últimas 3 semanas. Sequência de 4 notas críticas consecutivas.
            Vetor mais fraco: Saber (4,2). Critério mais fraco: Metrologia."
          </div>
          <b>O que isso revela:</b>
          <ul style="margin-top:8px;padding-left:20px;line-height:2.1;color:#374151;font-size:12px">
            <li>A queda é <b>recente</b> (últimas 3 semanas) — algo aconteceu nesse período</li>
            <li>O problema principal está no <b>vetor Saber</b> (teoria) — 4,2 é muito baixo</li>
            <li>O critério <b>Metrologia</b> é o ponto fraco específico — não é dificuldade geral</li>
            <li>Ele está em posição <b>quase último da turma</b> — situação urgente</li>
          </ul>
          <div style="background:#FFFBEB;border-radius:10px;padding:10px 14px;font-size:12px;
                      border-left:3px solid #F59E0B;margin-top:8px">
            <b>Conclusão do passo 2:</b> O problem é teórico (Saber/Metrologia), não prático.
            Agora preciso saber se as faltas estão causando essa dificuldade teórica.
          </div>
        </div>
        """, unsafe_allow_html=True)

    with st.expander("📍 Passo 3 — Raio-X das Atividades (aba Desempenho)"):
        st.markdown("""
        <div style="font-size:13px;color:#1D1D1F;line-height:1.8;padding:4px 0">
          No Raio-X das Atividades, o gráfico mostra (pior para melhor):
          <div style="background:#F8FAFC;border-radius:12px;padding:16px;margin:12px 0;font-size:12px">
            <div style="display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid #F2F2F7">
              <div style="width:90px;height:8px;background:#FF3B30;border-radius:4px"></div>
              <span><b>Prova Escrita</b> — Média 3,8 · 3 avaliações · 0% de aprovação</span>
            </div>
            <div style="display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid #F2F2F7">
              <div style="width:130px;height:8px;background:#F59E0B;border-radius:4px"></div>
              <span><b>Quiz Online</b> — Média 5,5 · 2 avaliações · 50% de aprovação</span>
            </div>
            <div style="display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid #F2F2F7">
              <div style="width:170px;height:8px;background:#F59E0B;border-radius:4px"></div>
              <span><b>Observação de Conduta</b> — Média 6,3 · 4 avaliações · 75% de aprovação</span>
            </div>
            <div style="display:flex;align-items:center;gap:10px;padding:8px 0">
              <div style="width:200px;height:8px;background:#34C759;border-radius:4px"></div>
              <span><b>Projeto Prático</b> — Média 8,1 · 3 avaliações · 100% de aprovação</span>
            </div>
          </div>
          <b>Interpretação:</b>
          <ul style="margin-top:8px;padding-left:20px;line-height:2.1;color:#374151;font-size:12px">
            <li>João <b>vai muito bem em Projeto Prático</b> (8,1) — habilidade manual excelente</li>
            <li>João <b>reprovaria pela Prova Escrita</b> (3,8) — zero aproveitamento nas provas teóricas</li>
            <li>Isso confirma: o problema é teórico/Metrologia, <b>não falta de esforço prático</b></li>
          </ul>
          <div style="background:#F0FDF4;border-radius:10px;padding:10px 14px;font-size:12px;
                      border-left:3px solid #34C759;margin-top:8px">
            <b>Conclusão do passo 3:</b> João não tem problema de comportamento ou prática —
            tem dificuldade específica em avaliações teóricas escritas. Possível dificuldade de escrita,
            nervosismo em provas ou lacuna em Metrologia.
          </div>
        </div>
        """, unsafe_allow_html=True)

    with st.expander("📍 Passo 4 — Linha do Tempo e Calendário (aba Frequência)"):
        st.markdown("""
        <div style="font-size:13px;color:#1D1D1F;line-height:1.8;padding:4px 0">
          Na aba Frequência, você vê:
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:12px 0">
            <div style="background:#FFF5F5;border-radius:12px;padding:14px;font-size:12px;border-top:3px solid #FF3B30">
              <b>Calendário de Presenças:</b><br><br>
              Semanas 8, 9 e 10 com várias faltas seguidas (bloco vermelho). Padrão de <b>ausência prolongada</b>.
              Coincide exatamente com as semanas em que as 4 provas escritas foram realizadas.
            </div>
            <div style="background:#FFF5F5;border-radius:12px;padding:14px;font-size:12px;border-top:3px solid #FF3B30">
              <b>Linha do Tempo:</b><br><br>
              Triângulos vermelhos (faltas) aparecem <b>imediatamente antes</b> de cada ponto baixo na linha de notas.
              IIF calculado em <b>7,4 — Crítico</b>. Nota projetada: 4,9.
            </div>
          </div>
          <b>O que isso muda na análise:</b>
          <ul style="margin-top:8px;padding-left:20px;line-height:2.1;color:#374151;font-size:12px">
            <li>As <b>faltas estão diretamente causando as notas baixas nas provas</b></li>
            <li>João faltou nas semanas de prova e ficou sem o conteúdo de Metrologia</li>
            <li>O IIF 7,4 indica que a frequência é o <b>principal fator de risco</b></li>
          </ul>
          <div style="background:#FFF5F5;border-radius:10px;padding:10px 14px;font-size:12px;
                      border-left:3px solid #FF3B30;margin-top:8px">
            <b>Conclusão do passo 4:</b> A hipótese muda — o problema não é dificuldade teórica,
            é que João <b>não estava presente quando o conteúdo foi ensinado e as provas foram feitas</b>.
            A causa raiz são as faltas, não a capacidade cognitiva.
          </div>
        </div>
        """, unsafe_allow_html=True)

    with st.expander("📍 Passo 5 — Ação Pedagógica Final"):
        st.markdown("""
        <div style="font-size:13px;color:#1D1D1F;line-height:1.8;padding:4px 0">
          Com todas as evidências conectadas, a ação pedagógica correta é:
          <div style="display:flex;flex-direction:column;gap:10px;margin-top:12px">
            <div style="background:#FFF5F5;border-left:4px solid #FF3B30;border-radius:0 12px 12px 0;
                        padding:14px 18px;font-size:12px">
              <b style="color:#FF3B30">🚨 Urgente — Frequência</b><br><br>
              João está com 71% (abaixo do mínimo de 75%). Contatar responsável imediatamente para
              entender o motivo das faltas. Se for problema externo (saúde, trabalho), registrar e
              buscar solução junto à equipe pedagógica.
            </div>
            <div style="background:#FFFBEB;border-left:4px solid #F59E0B;border-radius:0 12px 12px 0;
                        padding:14px 18px;font-size:12px">
              <b style="color:#B45309">📚 Curto prazo — Reposição de Conteúdo</b><br><br>
              Organizar reposição do conteúdo de Metrologia das semanas 8–10.
              Não cobrar prova nova antes de garantir que João teve acesso ao conteúdo.
              Tutoria individualizada ou material de apoio.
            </div>
            <div style="background:#FFF7ED;border-left:4px solid #F97316;border-radius:0 12px 12px 0;
                        padding:14px 18px;font-size:12px">
              <b style="color:#C2410C">📝 Médio prazo — Recuperação Dirigida</b><br><br>
              Após reposição, aplicar avaliação recuperativa focada em Metrologia (Prova Escrita).
              João tem boa capacidade prática (Projeto 8,1), então o conteúdo teórico pode ser
              ensinado com apoio em exemplos práticos da oficina.
            </div>
            <div style="background:#F0FDF4;border-left:4px solid #34C759;border-radius:0 12px 12px 0;
                        padding:14px 18px;font-size:12px">
              <b style="color:#15803D">✅ Longo prazo — Monitoramento</b><br><br>
              Acompanhar presença semanalmente. Se normalizar, a tendência de melhora deve aparecer
              no gráfico semanal em 2–3 semanas. Se o IIF cair abaixo de 3,0, o risco por frequência
              está controlado — focar só em recuperar as notas teóricas.
            </div>
          </div>
          <div style="background:#1E3A5F;border-radius:12px;padding:16px 20px;margin-top:16px;color:white;font-size:12px">
            <b style="font-size:13px">🎓 Resumo do Caso João Silva</b><br><br>
            Sem conectar os dados, um professor poderia concluir que "João tem dificuldade com Metrologia"
            e aplicar reforço teórico — que seria ineficaz porque João <b>não estava na aula</b>.<br><br>
            Conectando Raio-X → Linha do Tempo → IIF, a conclusão correta é:
            <b>o problema é ausência, não incapacidade</b>. A intervenção muda completamente.
            Esse é o poder de ler os dados de forma integrada.
          </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    st.markdown("""
    <div style="text-align:center;padding:20px;color:#9CA3AF;font-size:12px">
      📘 Guia do Painel Docente · SENAI · Gerado automaticamente pelo sistema
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════
def render_aluno_view(
    df: pd.DataFrame,
    df_turma_filter: pd.DataFrame,
    df_alunos: pd.DataFrame,
    df_rec: pd.DataFrame,
    df_freq: pd.DataFrame,
    aluno_sel: str,
    uc_sel: str,
    vetor_sel: str,
    col_uc_global: str,
    comparar_turma: bool,
    mostrar_ranking: bool,
    mostrar_turma: bool,
    turma_sel: str,
    df_turmas: pd.DataFrame = None, 
    df_feriados: list = None,      
) -> None:
    if not aluno_sel:
        st.warning("Nenhum aluno encontrado para os filtros selecionados.")
        st.stop()

    df_aluno = df[df["Aluno"] == aluno_sel].copy()
    df_turma = df_turma_filter.copy()

    if uc_sel != "Todas as Unidades":
        df_aluno = df_aluno[df_aluno[col_uc_global] == uc_sel]
        df_turma = df_turma[df_turma[col_uc_global] == uc_sel]
    if vetor_sel != "Todos os Vetores" and "Vetor (Peso)" in df_aluno.columns:
        df_aluno = df_aluno[df_aluno["Vetor (Peso)"] == vetor_sel]
        df_turma = df_turma[df_turma["Vetor (Peso)"] == vetor_sel]

    df_rec_aluno = (
        df_rec[df_rec["Aluno"] == aluno_sel].copy()
        if not df_rec.empty and "Aluno" in df_rec.columns else pd.DataFrame()
    )
    obs_geral = ""
    if not df_alunos.empty and "Aluno" in df_alunos.columns:
        row_aluno = df_alunos[df_alunos["Aluno"] == aluno_sel]
        if not row_aluno.empty and "Observações Gerais" in row_aluno.columns:
            _val = row_aluno.iloc[0].get("Observações Gerais", "")
            obs_geral = "" if pd.isna(_val) else str(_val).strip()

    turma_label = turma_sel if turma_sel != "Todas as Turmas" else "Todas as Turmas"
    if not df_alunos.empty and {"Aluno", "Turma"} <= set(df_alunos.columns):
        row = df_alunos[df_alunos["Aluno"] == aluno_sel]
        if not row.empty:
            turma_label = row.iloc[0].get("Turma", turma_label)

    from data.analysis import obter_datas_validas
    datas_globais = obter_datas_validas(turma_label, df_turmas, df, df_freq, df_feriados)

    freq_aluno   = calcular_frequencia_aluno(df_freq, aluno_sel, datas_globais)
    df_cal_aluno = _montar_calendario_aluno(df_freq, aluno_sel, datas_globais, df_feriados)
    col_crit     = coluna_criterio(df_aluno)
    col_uc     = coluna_uc(df_aluno)

    if df_aluno.empty:
        st.warning("⚠️ Sem dados para este aluno com os filtros atuais.")
        st.stop()

    media_aluno  = df_aluno["Nota"].mean()
    media_pond   = calcular_media_ponderada(df_aluno)
    media_turma  = df_turma["Nota"].mean()
    total_avals  = len(df_aluno)
    notas_baixas = int((df_aluno["Nota"] < NOTA_MINIMA).sum())
    delta_turma  = media_aluno - media_turma
    tendencia    = detectar_tendencia(df_aluno)
    seq_critica  = detectar_sequencia_critica(df_aluno)
    bimestres    = agrupar_por_semana(df_aluno)

    _turma_hash  = str(df_turma["Nota"].sum()) + str(len(df_turma))
    ranking      = calcular_ranking(_turma_hash, df_turma[["Aluno", "Nota"]].to_json())
    pos_list     = ranking[ranking["Aluno"] == aluno_sel].index
    posicao      = int(pos_list[0]) + 1 if len(pos_list) > 0 else None
    total_alunos = df["Aluno"].nunique()

    notas_vetor = calcular_notas_por_vetor(df_aluno)
    risco_aluno = classificar_risco(media_aluno, notas_baixas, total_avals, seq_critica, notas_vetor)

    _tend_info = {
        "melhora":    ("▲ Melhorando",   "#34C759"),
        "queda":      ("▼ Em queda",      "#FF3B30"),
        "estável":    ("● Estável",       "#F59E0B"),
        "indefinida": ("— Poucos dados",  "#8E8E93"),
    }
    tend_label, tend_cor = _tend_info[tendencia]

    _risco_cores  = {"critico":"#FF3B30","atencao":"#F59E0B","adequado":"#34C759","excelente":"#007AFF"}
    _risco_labels = {
        "critico":"🔴 Situação Crítica","atencao":"🟡 Requer Atenção",
        "adequado":"🟢 Situação Adequada","excelente":"🔵 Desempenho Excelente",
    }
    _risco_cor = _risco_cores[risco_aluno]

    st.markdown(
        f'<div style="margin-bottom:20px">'
        f'<div style="font-size:11px;font-weight:600;color:#8E8E93;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:4px">SENAI · Painel Docente</div>'
        f'<div style="display:flex;align-items:center;justify-content:space-between">'
        f'<div>'
        f'<div style="font-size:24px;font-weight:700;color:#1D1D1F;letter-spacing:-0.02em">{aluno_sel}</div>'
        f'<div style="font-size:13px;color:#8E8E93;margin-top:2px">{turma_label}</div>'
        f'</div>'
        f'<div style="background:{_risco_cor}18;border:1px solid {_risco_cor}40;border-radius:50px;padding:6px 16px;font-size:12px;font-weight:600;color:{_risco_cor}">'
        f'{_risco_labels[risco_aluno]}</div>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    if seq_critica >= SEQUENCIA_CRITICA_MIN:
        datas_seq = df_aluno.sort_values("Data")["Data"].tail(seq_critica)
        d_inicio  = datas_seq.iloc[0].strftime("%d/%m/%Y") if len(datas_seq) > 0 else "—"
        st.markdown(
            f'<div style="background:linear-gradient(135deg,#7F1D1D,#B91C1C);border-radius:12px;'
            f'padding:14px 20px;margin-bottom:18px;display:flex;align-items:center;gap:14px;'
            f'box-shadow:0 6px 20px rgba(127,29,29,0.35)">'
            f'<span style="font-size:1.8rem">🚨</span>'
            f'<div style="color:white">'
            f'<strong style="font-size:0.9rem;display:block">{seq_critica} avaliações consecutivas abaixo de {NOTA_MINIMA:.0f},0</strong>'
            f'<span style="font-size:0.8rem;opacity:0.85">Desde {d_inicio} · Intervenção pedagógica urgente recomendada.</span>'
            f'</div></div>',
            unsafe_allow_html=True,
        )

    _seq_f      = freq_aluno.get("faltas_seq_atual", 0)
    _seq_f_datas = freq_aluno.get("faltas_seq_datas", [])
    _datas_fmt  = " · ".join(
        d.strftime("%d/%m") for d in _seq_f_datas if hasattr(d, "strftime")
    )

    if _seq_f >= 3:
        st.markdown(
            f'<div style="background:linear-gradient(135deg,#1E1B4B,#3730A3);border-radius:12px;'
            f'padding:14px 20px;margin-bottom:18px;display:flex;align-items:center;gap:14px;'
            f'box-shadow:0 6px 20px rgba(55,48,163,0.35)">'
            f'<span style="font-size:1.8rem">⛔</span>'
            f'<div style="color:white">'
            f'<strong style="font-size:0.9rem;display:block">Possível desistência — {_seq_f} faltas consecutivas</strong>'
            f'<span style="font-size:0.8rem;opacity:0.85">'
            f'{"Datas: " + _datas_fmt + " · " if _datas_fmt else ""}'
            f'3 ou mais faltas seguidas indicam risco real de abandono. Contato imediato recomendado.</span>'
            f'</div></div>',
            unsafe_allow_html=True,
        )
    elif _seq_f == 2:
        st.markdown(
            f'<div style="background:linear-gradient(135deg,#451A03,#C2410C);border-radius:12px;'
            f'padding:14px 20px;margin-bottom:18px;display:flex;align-items:center;gap:14px;'
            f'box-shadow:0 4px 16px rgba(194,65,12,0.30)">'
            f'<span style="font-size:1.8rem">⚠️</span>'
            f'<div style="color:white">'
            f'<strong style="font-size:0.9rem;display:block">2 faltas consecutivas recentes</strong>'
            f'<span style="font-size:0.8rem;opacity:0.85">'
            f'{"Datas: " + _datas_fmt + " · " if _datas_fmt else ""}'
            f'Verificar o motivo antes de uma próxima falta transformar em desistência.</span>'
            f'</div></div>',
            unsafe_allow_html=True,
        )

    if obs_geral:
        st.markdown(
            f'<div style="background:#F0F9FF;border:1px solid #BAE6FD;border-radius:12px;padding:14px 20px;margin-bottom:18px">'
            f'<span style="font-size:11px;font-weight:600;color:#64748B;display:block;margin-bottom:4px">📌 Observação geral</span>'
            f'<p style="font-size:14px;color:#0369A1;margin:0;font-style:italic;line-height:1.6">{obs_geral}</p>'
            f'</div>',
            unsafe_allow_html=True,
        )

    tab_geral, tab_desempenho, tab_freq, tab_monte_carlo, tab_ia, tab_ajuda = st.tabs([
        "📋 Visão Geral", "📊 Desempenho", "📅 Frequência", "🎲 Modelo Prob.", "🤖 Análise IA", "❓",
    ])

    with tab_geral:
        _tab_geral(
            df_aluno, df_turma, col_crit, col_uc, aluno_sel, comparar_turma,
            freq_aluno, media_aluno, media_pond, notas_baixas, total_avals,
            tend_label, tend_cor, seq_critica, bimestres,
            posicao, total_alunos, tendencia, delta_turma, media_turma,
        )

    with tab_desempenho:
        _tab_desempenho(
            df_aluno, df_turma, col_crit, col_uc, aluno_sel, turma_label,
            bimestres, ranking, posicao,
            media_aluno, media_pond, media_turma,
            notas_baixas, total_avals, delta_turma, seq_critica,
            mostrar_ranking, mostrar_turma,
            df_rec_aluno, obs_geral,
            freq_aluno=freq_aluno,
            df_cal_aluno=df_cal_aluno,
        )

    with tab_freq:
        _tab_frequencia(df_aluno, df_freq, aluno_sel, freq_aluno, df_cal_aluno)

    with tab_monte_carlo:
        _tab_monte_carlo(df_aluno=df_aluno, media_pond=media_pond)

    with tab_ajuda:
        _tab_ajuda()

    with tab_ia:
        _tab_ia_individual(
            df_aluno=df_aluno,
            aluno_sel=aluno_sel,
            turma_label=turma_label,
            risco_aluno=risco_aluno,
            tendencia=tendencia,
            media_pond=media_pond,
            notas_baixas=notas_baixas,
            total_avals=total_avals,
            seq_critica=seq_critica,
            freq_aluno=freq_aluno,
            obs_geral=obs_geral,
            col_crit=col_crit,
        )
