import io
import zipfile
from datetime import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config import CORES, NOTA_MINIMA, SEQUENCIA_CRITICA_MIN
from data.analysis import (
    agrupar_por_semana,
    calcular_frequencia_aluno,
    calcular_perfil_turma,
    calcular_saude_turma,
)
from data.export import gerar_excel_turma
from pdf.generator import gerar_boletim_pdf, gerar_relatorio_turma_pdf
from ui.components import divider, section_title
from utils import coluna_uc


def render_turma_view(
    df_turma_filter: pd.DataFrame,
    df_freq: pd.DataFrame,
    risco_filtro: list,
    uc_sel_turma: str,
    turma_sel: str,
    df_turmas: pd.DataFrame = None,
    df_feriados: list = None, # Datas de feriados e recessos
) -> None:
    df_t_view = df_turma_filter.copy()
    if uc_sel_turma != "Todas as Unidades":
        df_t_view = df_t_view[df_t_view[coluna_uc(df_t_view)] == uc_sel_turma]

    _hash_t = str(df_t_view["Nota"].sum()) + str(len(df_t_view))
    _cols_t = (
        ["Aluno", "Nota", "Data"]
        + (["Vetor (Peso)"] if "Vetor (Peso)" in df_t_view.columns else [])
        + (["Instrumento / Atividade"] if "Instrumento / Atividade" in df_t_view.columns else [])
    )
    perfil  = calcular_perfil_turma(_hash_t, df_t_view[_cols_t].to_json(date_format="iso"))
    saude   = calcular_saude_turma(df_t_view, perfil)

    n_critico   = (perfil["Risco"] == "critico").sum()
    n_atencao   = (perfil["Risco"] == "atencao").sum()
    n_adequado  = (perfil["Risco"] == "adequado").sum()
    n_excelente = (perfil["Risco"] == "excelente").sum()
    media_geral = df_t_view["Nota"].mean()

    label_turma_view = turma_sel if turma_sel != "Todas as Turmas" else "Todas as Turmas"
    st.markdown(f"""
    <div class="turma-header">
        <div style="margin-bottom:22px">
            <div style="font-family:Montserrat,sans-serif;font-size:1.6rem;font-weight:800;
                        color:white;letter-spacing:-0.02em">🏫 {label_turma_view}</div>
            <div style="font-size:0.85rem;color:rgba(255,255,255,0.65);margin-top:5px">
                Visão Geral · {datetime.now().strftime('%d/%m/%Y')}
            </div>
        </div>
        <div class="resp-grid" style="display:grid;grid-template-columns:repeat(5,1fr);gap:14px">
            <div class="turma-stat">
                <div class="turma-stat-val">{len(perfil)}</div>
                <div class="turma-stat-lbl">Alunos</div>
            </div>
            <div class="turma-stat">
                <div class="turma-stat-val">{media_geral:.1f}</div>
                <div class="turma-stat-lbl">Média Geral</div>
            </div>
            <div class="turma-stat" style="background:rgba(227,6,19,0.28);border-color:rgba(227,6,19,0.45)">
                <div class="turma-stat-val">{n_critico}</div>
                <div class="turma-stat-lbl">Em Risco</div>
            </div>
            <div class="turma-stat" style="background:rgba(245,158,11,0.28);border-color:rgba(245,158,11,0.45)">
                <div class="turma-stat-val">{n_atencao}</div>
                <div class="turma-stat-lbl">Em Atenção</div>
            </div>
            <div class="turma-stat" style="background:rgba(16,185,129,0.28);border-color:rgba(16,185,129,0.45)">
                <div class="turma-stat-val">{n_adequado + n_excelente}</div>
                <div class="turma-stat-lbl">Aprovados</div>
            </div>
        </div>
    </div>""", unsafe_allow_html=True)

    if saude:
        _tend_col_s = {"queda": "#DC2626", "melhora": "#16A34A", "estável": "#6B7280", "indefinida": "#9CA3AF"}.get(saude.get("tendencia_coletiva", "indefinida"), "#9CA3AF")
        _tend_ic_s  = {"queda": "📉 Queda", "melhora": "📈 Melhora", "estável": "→ Estável", "indefinida": "—"}.get(saude.get("tendencia_coletiva", "indefinida"), "—")
        _vetor_str  = f"{saude['vetor_mais_fraco'].split(' (')[0]}: {saude['media_vetor_mais_fraco']:.1f}" if saude.get("vetor_mais_fraco") else "—"
        _crit_str   = f"{str(saude.get('criterio_mais_problematico',''))[:22]} ({saude.get('pct_abaixo_criterio',0):.0f}%)" if saude.get("criterio_mais_problematico") else "—"
        _vetor_cor  = "#DC2626" if (saude.get("media_vetor_mais_fraco") or 10) < NOTA_MINIMA else "#F59E0B"
        _crit_cor   = "#DC2626" if saude.get("pct_abaixo_criterio", 0) >= 50 else "#F59E0B"

        _periodo_txt = ""
        if "Data" in df_t_view.columns:
            _dts_s = pd.to_datetime(df_t_view["Data"], errors="coerce", dayfirst=True).dropna()
            if not _dts_s.empty:
                _d_ini_s, _d_fim_s = _dts_s.min(), _dts_s.max()
                _periodo_txt = (
                    _d_ini_s.strftime("%d/%m/%Y")
                    if _d_ini_s.date() == _d_fim_s.date()
                    else f"{_d_ini_s.strftime('%d/%m/%Y')} a {_d_fim_s.strftime('%d/%m/%Y')}"
                )
        _uc_txt = uc_sel_turma if uc_sel_turma != "Todas as Unidades" else "todas as unidades"

        section_title("🩺 Saúde da Turma · Diagnóstico Coletivo")
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:8px;background:#F8FAFC;border:1px solid #E5E7EB;'
            f'border-left:3px solid #1E3A8A;border-radius:8px;padding:8px 14px;margin:-4px 0 2px;'
            f'font-size:12px;color:#475569;line-height:1.4">'
            f'<span style="font-size:14px">ℹ️</span><span>Indicadores calculados sobre <b>todo o período avaliado</b>'
            f'{(" · " + _periodo_txt) if _periodo_txt else ""} · <b>{len(df_t_view)}</b> avaliações · {_uc_txt}. '
            f'Refletem o acúmulo do período, não apenas a aula mais recente '
            f'(exceto a <i>Tendência Coletiva</i>, que compara as avaliações mais recentes).</span></div>',
            unsafe_allow_html=True,
        )
        st.markdown(f"""
        <div class="resp-grid" style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:14px 0 4px">
            <div style="background:white;border-radius:12px;padding:14px 16px;border:1px solid #E5E7EB;box-shadow:0 1px 3px rgba(0,0,0,0.06)">
                <div style="font-size:10px;color:#6B7280;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:6px">Taxa de Aprovação</div>
                <div style="font-size:26px;font-weight:800;color:#16A34A">{saude['pct_aprovados']:.0f}%</div>
                <div style="font-size:11px;color:#6B7280;margin-top:2px">{saude['n_aprovados']} aprovados de {saude['n_total']}</div>
            </div>
            <div style="background:white;border-radius:12px;padding:14px 16px;border:1px solid #E5E7EB;box-shadow:0 1px 3px rgba(0,0,0,0.06)">
                <div style="font-size:10px;color:#6B7280;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:6px">Critério + Problemático</div>
                <div style="font-size:14px;font-weight:700;color:{_crit_cor};line-height:1.3">{_crit_str}</div>
                <div style="font-size:11px;color:#6B7280;margin-top:2px">alunos com média abaixo de {NOTA_MINIMA:.0f}</div>
            </div>
            <div style="background:white;border-radius:12px;padding:14px 16px;border:1px solid #E5E7EB;box-shadow:0 1px 3px rgba(0,0,0,0.06)">
                <div style="font-size:10px;color:#6B7280;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:6px">Vetor Coletivo Fraco</div>
                <div style="font-size:14px;font-weight:700;color:{_vetor_cor};line-height:1.3">{_vetor_str}</div>
                <div style="font-size:11px;color:#6B7280;margin-top:2px">média do vetor mais fraco</div>
            </div>
            <div style="background:white;border-radius:12px;padding:14px 16px;border:1px solid #E5E7EB;box-shadow:0 1px 3px rgba(0,0,0,0.06)">
                <div style="font-size:10px;color:#6B7280;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:6px">Tendência Coletiva</div>
                <div style="font-size:20px;font-weight:800;color:{_tend_col_s}">{_tend_ic_s}</div>
                <div style="font-size:11px;color:#6B7280;margin-top:2px">últimas avaliações da turma</div>
            </div>
        </div>""", unsafe_allow_html=True)

        if saude.get("pct_abaixo_criterio", 0) >= 50:
            st.markdown(
                f'<div style="background:#FEF2F2;border:1px solid #FECACA;border-radius:10px;'
                f'padding:10px 16px;margin:6px 0 14px;color:#991B1B;font-size:13px;font-weight:600">'
                f'🚨 Alerta Pedagógico: <b>{saude.get("criterio_mais_problematico","")}</b> — '
                f'{saude.get("pct_abaixo_criterio",0):.0f}% da turma com média abaixo do mínimo no período avaliado'
                f'{(" (" + _periodo_txt + ")") if _periodo_txt else ""}. '
                f'Revisão de conteúdo e metodologia recomendada.</div>',
                unsafe_allow_html=True,
            )

    c1, c2, c3 = st.columns(3)

    with c1:
        section_title("🚦 Distribuição de Risco")
        fig_risco = go.Figure(data=[go.Pie(
            labels=["Crítico", "Atenção", "Adequado", "Excelente"],
            values=[n_critico, n_atencao, n_adequado, n_excelente],
            hole=0.58,
            marker=dict(
                colors=[CORES["vermelho"], CORES["amarelo"], CORES["verde"], CORES["roxo"]],
                line=dict(color="white", width=2.5),
            ),
            textinfo="label+value", textfont=dict(size=11),
        )])
        fig_risco.add_annotation(
            text=f"<b>{len(perfil)}</b><br>alunos",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16, color=CORES["texto"]),
        )
        fig_risco.update_layout(
            showlegend=False, margin=dict(t=10, b=10, l=10, r=10),
            paper_bgcolor="white", height=270,
        )
        st.plotly_chart(fig_risco, width="stretch")

    with c2:
        section_title("📊 Distribuição de Médias")
        fig_dist = px.histogram(perfil, x="Média", nbins=10, color_discrete_sequence=[CORES["azul"]])
        fig_dist.add_vline(x=NOTA_MINIMA, line_dash="dash", line_color=CORES["vermelho"],
                           annotation_text="Mínimo", annotation_position="top right", annotation_font_size=10)
        fig_dist.add_vline(x=media_geral, line_dash="dot", line_color=CORES["amarelo"],
                           annotation_text=f"Média: {media_geral:.1f}", annotation_position="top left",
                           annotation_font_size=10)
        fig_dist.update_layout(
            plot_bgcolor="white", paper_bgcolor="white",
            xaxis=dict(range=[0, 10.5], gridcolor="#F3F4F6"),
            yaxis=dict(gridcolor="#F3F4F6", title="Qtd alunos", dtick=1),
            margin=dict(t=35, b=10, l=10, r=10),
            height=270, bargap=0.1,
        )
        st.plotly_chart(fig_dist, width="stretch")

    with c3:
        section_title("📚 Média por UC")
        col_uc_t = coluna_uc(df_t_view)
        if col_uc_t in df_t_view.columns:
            uc_t = (
                df_t_view.groupby(col_uc_t)["Nota"].mean().reset_index()
                .rename(columns={"Nota": "Média"}).sort_values("Média", ascending=True)
            )
            fig_uc_t = px.bar(
                uc_t, x="Média", y=col_uc_t, orientation="h", color="Média",
                color_continuous_scale=[[0, CORES["vermelho"]], [0.6, CORES["amarelo"]], [1, CORES["verde"]]],
                text="Média",
            )
            fig_uc_t.update_traces(texttemplate="%{text:.1f}", textposition="outside")
            fig_uc_t.update_layout(
                plot_bgcolor="white", paper_bgcolor="white",
                xaxis=dict(range=[0, 11], gridcolor="#F3F4F6"), yaxis_title="",
                coloraxis_showscale=False, margin=dict(t=10, b=10, l=10, r=10), height=270,
            )
            fig_uc_t.add_vline(x=NOTA_MINIMA, line_dash="dash", line_color="#9CA3AF", line_width=1.5)
            st.plotly_chart(fig_uc_t, width="stretch")
        else:
            st.info("Sem dados de UC.")

    # =========================================================================
    # SECÇÃO: EVOLUÇÃO TEMPORAL DAS NOTAS (COM FILTRO DE TENDÊNCIA ESTILO TRADING)
    # =========================================================================
    divider()
    section_title("📈 Evolução Temporal das Notas")
    
    df_tempo = df_t_view.copy()
    if "Data" in df_tempo.columns and not df_tempo.empty:
        df_tempo["Data_dt"] = pd.to_datetime(df_tempo["Data"], errors="coerce", dayfirst=True)
        df_tempo = df_tempo.dropna(subset=["Data_dt"]).sort_values("Data_dt")
        
        if not df_tempo.empty:
            # 1. Vetor de Média Diária Real (Alta variação/Volatilidade)
            df_media_tempo = df_tempo.groupby("Data_dt")["Nota"].mean().reset_index()
            
            # 2. ALGORITMO DE SUAVIZAÇÃO: Média Móvel Exponencial (Low Variance Trend Indicator)
            df_media_tempo["Nota_suave"] = df_media_tempo["Nota"].ewm(span=3, min_periods=1).mean()
            
            # 3. Vetor de Trajetórias Individuais dos Alunos
            df_alunos_tempo = df_tempo.groupby(["Data_dt", "Aluno"])["Nota"].mean().reset_index()
            
            fig_tempo = px.line(
                df_alunos_tempo,
                x="Data_dt",
                y="Nota",
                color="Aluno",
                markers=True,
            )
            
            # Alunos em segundo plano com opacidade reduzida
            fig_tempo.update_traces(
                line=dict(width=1.5), 
                marker=dict(size=5),
                opacity=0.30
            )
            
            # Injeção da Média Diária Real (Linha com variação/volatilidade micro)
            fig_tempo.add_trace(go.Scatter(
                x=df_media_tempo["Data_dt"],
                y=df_media_tempo["Nota"],
                mode="lines+markers",
                name="Média Diária (Micro Volatilidade)",
                line=dict(color="#2563EB", width=2.5),
                marker=dict(size=6, color="#2563EB"),
                opacity=0.65
            ))
            
            # INJEÇÃO DA LINHA MESTRE DE TENDÊNCIA: Indicador de Direção Macro (Baixíssima variação)
            fig_tempo.add_trace(go.Scatter(
                x=df_media_tempo["Data_dt"],
                y=df_media_tempo["Nota_suave"],
                mode="lines",
                name="<b>Direção Macro (EMA Suavizada)</b>",
                line=dict(color="#F97316", width=4.5, dash="dash"), # Tracejado laranja estilo indicador técnico
                opacity=1.0
            ))
            
            fig_tempo.update_layout(
                plot_bgcolor="white",
                paper_bgcolor="white",
                xaxis=dict(
                    title="",
                    gridcolor="#F3F4F6",
                    tickformat="%d/%m/%Y",
                    tickangle=-30
                ),
                yaxis=dict(
                    title="Nota",
                    range=[0, 10.5],
                    gridcolor="#F3F4F6",
                    dtick=2
                ),
                margin=dict(t=15, b=15, l=10, r=10),
                height=350,
                hovermode="x unified",
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                )
            )
            st.plotly_chart(fig_tempo, width="stretch")
        else:
            st.info("Formato de data inválido para gerar a análise de tendência.")
    else:
        st.info("Dados temporais indisponíveis nesta Unidade Curricular.")
    # =========================================================================

    divider()
    section_title("🚦 Painel de Risco Individual")

    _busca = st.text_input(
        "🔍 Buscar aluno", placeholder="Digite parte do nome...",
        label_visibility="collapsed", key="turma_busca_aluno",
    )
    perfil_filtrado = perfil[perfil["Risco"].isin(risco_filtro)]
    if _busca.strip():
        perfil_filtrado = perfil_filtrado[
            perfil_filtrado["Aluno"].str.contains(_busca.strip(), case=False, na=False)
        ]
    _icones  = {"critico":"🔴","atencao":"🟡","adequado":"🟢","excelente":"🟣"}
    _rotulos = {"critico":"Crítico","atencao":"Atenção","adequado":"Adequado","excelente":"Excelente"}
    _tend_ic = {"melhora":"▲","queda":"▼","estável":"●","indefinida":"—"}

    aluno_turma_dict = {}
    if "Turma" in df_turma_filter.columns:
        aluno_turma_dict = df_turma_filter.set_index("Aluno")["Turma"].to_dict()

    _cache_datas_globais = {}
    def _get_datas_globais(t_nome):
        if not t_nome or t_nome == "Todas as Turmas":
            return []
        if t_nome in _cache_datas_globais:
            return _cache_datas_globais[t_nome]
        
        dg = []
        if df_turmas is not None and not df_turmas.empty and "Turma" in df_turmas.columns:
            _turmas_limpas = df_turmas.copy()
            _turmas_limpas["_Turma_lower"] = _turmas_limpas["Turma"].astype(str).str.strip().str.lower()
            _t_lower = str(t_nome).strip().lower()
            turma_row = _turmas_limpas[_turmas_limpas["_Turma_lower"] == _t_lower]
            if not turma_row.empty:
                r = turma_row.iloc[0]
                d_ini = pd.to_datetime(r.get("Data Início", r.get("Data Início ", r.get("Data Inicio"))), errors="coerce", dayfirst=True)
                d_fim = pd.to_datetime(r.get("Data fim", r.get("Data Fim", r.get("Data Fim "))), errors="coerce", dayfirst=True)
                aulas_sem = str(r.get("Aulas Semana", "")).lower()
                
                dias_validos = []
                for k, v in {"seg": 0, "ter": 1, "qua": 2, "qui": 3, "sex": 4, "sab": 5, "sáb": 5, "dom": 6}.items():
                    if k in aulas_sem: dias_validos.append(v)
                if not dias_validos: dias_validos = [0, 1, 2, 3, 4]
                
                if pd.notna(d_ini):
                    _lim_fim = d_fim if pd.notna(d_fim) else pd.Timestamp.today().normalize()
                    limite_fim = min(_lim_fim, pd.Timestamp.today().normalize())
                    dg = [d for d in pd.date_range(d_ini, limite_fim).normalize() if d.dayofweek in dias_validos]
        
        if not dg:
            todas_dr = []
            if not df_t_view.empty and "Data" in df_t_view.columns:
                todas_dr.extend(pd.to_datetime(df_t_view["Data"], errors="coerce", dayfirst=True).dropna().dt.normalize().tolist())
            if not df_freq.empty and "Data" in df_freq.columns:
                todas_dr.extend(pd.to_datetime(df_freq["Data"], errors="coerce", dayfirst=True).dropna().dt.normalize().tolist())
            if todas_dr:
                d_i = min(todas_dr)
                d_f = pd.Timestamp.today().normalize()
                dg = [d for d in pd.date_range(d_i, d_f).normalize() if d.dayofweek in [0, 1, 2, 3, 4]]
                
        if df_feriados:
            _feriados_ts = {pd.to_datetime(f, errors="coerce", dayfirst=True).normalize() for f in df_feriados if pd.notna(f)}
            _feriados_ts = {f for f in _feriados_ts if pd.notna(f)}
            dg = [d for d in dg if d.normalize() not in _feriados_ts]
        _cache_datas_globais[t_nome] = dg
        return dg

    _freq_map = {
        nome: calcular_frequencia_aluno(df_freq, nome, _get_datas_globais(aluno_turma_dict.get(nome, turma_sel)))
        for nome in perfil_filtrado["Aluno"].unique()
    }

    for risco_nivel in ["critico", "atencao", "adequado", "excelente"]:
        grupo = perfil_filtrado[perfil_filtrado["Risco"] == risco_nivel]
        if grupo.empty:
            continue
        _cor_sec = {
            "critico": CORES["vermelho"], "atencao": "#B45309",
            "adequado": CORES["verde"], "excelente": "#6366F1",
        }[risco_nivel]
        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:10px;margin:22px 0 14px">
            <div style="font-family:Montserrat;font-weight:700;font-size:0.82rem;
                        color:{_cor_sec};text-transform:uppercase;letter-spacing:0.1em">
                {_icones[risco_nivel]} {_rotulos[risco_nivel]} — {len(grupo)} aluno(s)
            </div>
            <div style="flex:1;height:2px;background:linear-gradient(90deg,{_cor_sec}40,transparent)"></div>
        </div>""", unsafe_allow_html=True)

        alunos_grupo = grupo.to_dict("records")
        for i in range(0, len(alunos_grupo), 3):
            cols_r = st.columns(3)
            for j, row in enumerate(alunos_grupo[i:i+3]):
                with cols_r[j]:
                    risco_r   = row["Risco"]
                    tend_ic   = _tend_ic.get(row["Tendencia"], "—")
                    seq_badge = (
                        f'<span style="background:#FEE2E2;color:#991B1B;border-radius:50px;'
                        f'padding:2px 9px;font-size:0.65rem;font-weight:700">🚨 {row["Seq_Critica"]} seq</span>'
                        if row["Seq_Critica"] >= SEQUENCIA_CRITICA_MIN else ""
                    )
                    _freq_t     = _freq_map.get(row["Aluno"], {"tem_dados": False})
                    _freq_badge = ""
                    if _freq_t["tem_dados"]:
                        _freq_badge = (
                            f'<span style="background:{_freq_t["cor"]}18;color:{_freq_t["cor"]};'
                            f'border-radius:50px;padding:1px 8px;font-size:0.65rem;font-weight:700;margin-left:4px">'
                            f'📅 {_freq_t["pct_presenca"]}%</span>'
                        )
                    st.markdown(f"""
<div class="risco-card {risco_r}">
<div class="semaforo {risco_r}">{_icones[risco_r]}</div>
<div style="flex:1;min-width:0">
<div class="risco-nome">{row['Aluno']}</div>
<div class="risco-meta">
{tend_ic} {row['Tendencia'].capitalize()} · {row['Notas_Baixas']} crítica(s) de {row['Total']} {seq_badge}{_freq_badge}
</div>
</div>
<div class="risco-nota {risco_r}">{row['Média']:.1f}</div>
</div>""", unsafe_allow_html=True)

    divider()
    section_title("🏆 Ranking Completo")
    fig_rank_t = px.bar(
        perfil.sort_values("Média", ascending=True),
        x="Média", y="Aluno", orientation="h", color="Média",
        color_continuous_scale=[[0, CORES["vermelho"]], [0.6, CORES["amarelo"]], [1, CORES["verde"]]],
        text="Média",
        hover_data={"Notas_Baixas": True, "Total": True, "Tendencia": True},
    )
    fig_rank_t.update_traces(texttemplate="%{text:.1f}", textposition="outside")
    fig_rank_t.update_layout(
        plot_bgcolor="white", paper_bgcolor="white",
        xaxis=dict(range=[0, 11], gridcolor="#F3F4F6"),
        yaxis=dict(tickfont=dict(size=9.5)),
        coloraxis_showscale=False,
        margin=dict(t=10, b=10, l=10, r=10),
        height=max(300, len(perfil) * 30 + 60),
    )
    fig_rank_t.add_vline(x=NOTA_MINIMA, line_dash="dash", line_color="#9CA3AF", line_width=1.5)
    st.plotly_chart(fig_rank_t, width="stretch")

    divider()
    section_title("🌡️ Mapa de Calor Interativo")

    _col_crit_t  = "Critério Avaliado"   if "Critério Avaliado"   in df_t_view.columns else None
    _col_inst_t  = "Instrumento / Atividade" if "Instrumento / Atividade" in df_t_view.columns else None
    _col_vetor_t = "Vetor (Peso)"          if "Vetor (Peso)"          in df_t_view.columns else None

    _modos_disp = {}
    if _col_crit_t:  _modos_disp["Por Critério"]    = _col_crit_t
    if _col_inst_t:  _modos_disp["Por Atividade"]   = _col_inst_t
    if _col_vetor_t: _modos_disp["Por Vetor"]        = _col_vetor_t

    if not _modos_disp:
        st.info("Nenhuma coluna de critério, atividade ou vetor encontrada.")
    else:
        _hc1, _hc2, _hc3 = st.columns([2, 2, 3])
        with _hc1:
            _modo_heat = st.radio(
                "Agrupar por", list(_modos_disp.keys()),
                horizontal=False, key="heat_modo",
                label_visibility="collapsed",
            )
        with _hc2:
            _filtro_risco_heat = st.multiselect(
                "Destacar risco",
                ["🔴 Crítico", "🟡 Atenção", "🟢 Adequado", "🟣 Excelente"],
                default=["🔴 Crítico", "🟡 Atenção"],
                key="heat_risco",
            )
        with _hc3:
            _ordenar_heat = st.radio(
                "Ordenar alunos por",
                ["Pior média (topo)", "Melhor média (topo)", "Nome"],
                horizontal=True, key="heat_ordem",
                label_visibility="visible",
            )

        _col_grupo = _modos_disp[_modo_heat]
        heat_df = (
            df_t_view.groupby(["Aluno", _col_grupo])["Nota"].mean().reset_index()
            .pivot(index="Aluno", columns=_col_grupo, values="Nota")
        )

        _map_risco = {"🔴 Crítico": "critico", "🟡 Atenção": "atencao", "🟢 Adequado": "adequado", "🟣 Excelente": "excelente"}
        if _filtro_risco_heat and not perfil.empty:
            _riscos_sel = [_map_risco[r] for r in _filtro_risco_heat if r in _map_risco]
            _alunos_filtro = perfil[perfil["Risco"].isin(_riscos_sel)]["Aluno"].tolist()
            heat_df = heat_df[heat_df.index.isin(_alunos_filtro)]

        heat_df["_m"] = heat_df.mean(axis=1)
        if _ordenar_heat == "Pior média (topo)":
            heat_df = heat_df.sort_values("_m", ascending=True)
        elif _ordenar_heat == "Melhor média (topo)":
            heat_df = heat_df.sort_values("_m", ascending=False)
        else:
            heat_df = heat_df.sort_index()
        heat_df = heat_df.drop(columns="_m")

        if heat_df.empty:
            st.info("Nenhum aluno para o filtro de risco selecionado.")
        else:
            def _txt_cell(v):
                if pd.isna(v): return "—"
                return f"{v:.1f}"

            def _txt_color(v):
                if pd.isna(v): return "#C7C7CC"
                return "white" if (v < 5 or v > 8.5) else "#1D1D1F"

            _text_annot  = [[_txt_cell(v) for v in row] for row in heat_df.values]
            _font_colors = [[_txt_color(v) for v in row] for row in heat_df.values]

            fig_heat_t = go.Figure(data=go.Heatmap(
                z=heat_df.values,
                x=heat_df.columns.tolist(),
                y=heat_df.index.tolist(),
                colorscale=[
                    [0.0,  "#B91C1C"],
                    [0.45, "#F97316"],
                    [0.60, "#FDE68A"],
                    [0.70, "#86EFAC"],
                    [1.0,  "#059669"],
                ],
                zmin=0, zmax=10,
                text=_text_annot,
                texttemplate="%{text}",
                textfont=dict(size=9),
                hoverongaps=False,
                colorbar=dict(
                    title=dict(text="Nota", font=dict(size=11)),
                    tickvals=[0, 3, 6, 7, 8.5, 10],
                    ticktext=["0 — Crítico", "3", "6 — Mínimo", "7", "8,5", "10 — Excelente"],
                    tickfont=dict(size=9),
                    len=0.85,
                ),
                hoverlabel=dict(bgcolor="white", font_size=12),
                hovertemplate=(
                    "<b>%{y}</b><br>"
                    + _col_grupo + ": <b>%{x}</b><br>"
                    "Média: <b>%{z:.1f}</b><extra></extra>"
                ),
            ))

            fig_heat_t.update_layout(
                plot_bgcolor="white", paper_bgcolor="white",
                xaxis=dict(
                    tickangle=-35, tickfont=dict(size=9),
                    showgrid=False, side="bottom",
                ),
                yaxis=dict(tickfont=dict(size=9.5), showgrid=False, autorange="reversed"),
                margin=dict(t=10, b=10, l=10, r=10),
                height=max(320, len(heat_df) * 34 + 100),
            )
            st.plotly_chart(fig_heat_t, width="stretch")

            st.markdown(
                '<div style="display:flex;gap:20px;flex-wrap:wrap;font-size:11px;'
                'font-weight:600;color:#6B7280;margin-top:-8px;margin-bottom:4px;padding:0 4px">'
                '<span>🔴 &lt; 6,0 — Crítico</span>'
                '<span>🟠 6,0 – 6,9 — Atenção</span>'
                '<span>🟡 7,0 – 7,9 — Adequado</span>'
                '<span>🟢 8,0 – 8,4 — Bom</span>'
                '<span>🔵 ≥ 8,5 — Excelente</span>'
                '</div>',
                unsafe_allow_html=True,
            )

    if saude and saude.get("criterios_sistemicos"):
        divider()
        section_title("🔍 Critérios Sistêmicos")
        st.markdown(
            '<p style="font-size:13px;color:#6B7280;margin:-8px 0 12px">Percentual de alunos cuja '
            f'<b>média</b> no critério ficou abaixo de {NOTA_MINIMA:.0f}, considerando <b>todo o período avaliado</b>'
            f'{(" (" + _periodo_txt + ")") if _periodo_txt else ""}. Usa a média do aluno no critério (não uma nota '
            f'isolada) para distinguir dificuldades coletivas (pedagógicas) de tropeços individuais.</p>',
            unsafe_allow_html=True,
        )
        _col_crit_key = saude.get("col_crit", "Critério Avaliado")
        for row_s in saude["criterios_sistemicos"]:
            pct   = row_s.get("pct_abaixo", 0)
            cor   = "#DC2626" if pct >= 50 else ("#F59E0B" if pct >= 25 else "#16A34A")
            bbg   = "#FEF2F2" if pct >= 50 else ("#FEF3C7" if pct >= 25 else "#F0FDF4")
            label = str(row_s.get(_col_crit_key, ""))[:42]
            bar_w = min(100, int(pct))
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:7px">'
                f'<div style="min-width:210px;max-width:210px;font-size:12px;color:#374151;font-weight:500;'
                f'overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="{label}">{label}</div>'
                f'<div style="flex:1;background:#F3F4F6;border-radius:4px;height:10px;overflow:hidden">'
                f'<div style="width:{bar_w}%;background:{cor};height:10px;border-radius:4px"></div></div>'
                f'<div style="min-width:52px;text-align:right">'
                f'<span style="background:{bbg};color:{cor};border-radius:50px;padding:2px 9px;'
                f'font-size:11px;font-weight:700">{pct:.0f}%</span></div></div>',
                unsafe_allow_html=True,
            )

    divider()
    _col_pdf, _col_xlsx = st.columns(2)
    with _col_pdf:
        if st.button("📄 Gerar relatório da turma em PDF", width="stretch"):
            with st.spinner("Gerando PDF..."):
                pdf_bytes = gerar_relatorio_turma_pdf(
                    label_turma_view, perfil, df_t_view, saude, df_freq
                )
            nome_pdf = f"relatorio_turma_{label_turma_view.replace(' ', '_')}_{datetime.now().strftime('%d%m%Y')}.pdf"
            st.download_button(
                "⬇️ Baixar PDF", data=pdf_bytes, file_name=nome_pdf,
                mime="application/pdf", width="stretch",
            )
    with _col_xlsx:
        if st.button("📊 Exportar relatório da turma em Excel", width="stretch"):
            with st.spinner("Gerando Excel..."):
                xlsx_bytes = gerar_excel_turma(perfil, df_t_view, df_freq, label_turma_view)
            nome_xlsx = f"turma_{label_turma_view.replace(' ', '_')}_{datetime.now().strftime('%d%m%Y')}.xlsx"
            st.download_button(
                "⬇️ Baixar Excel", data=xlsx_bytes, file_name=nome_xlsx,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width="stretch",
            )

    # ── Exportar todos os boletins em ZIP ────────────────────────────────────
    _zip_key  = f"zip_boletins_{label_turma_view}"
    _n_alunos = len(perfil)
    with st.expander(f"📦 Exportar boletins individuais em ZIP  ({_n_alunos} alunos)", expanded=False):
        st.markdown(
            '<div style="font-size:12px;color:#6B7280;line-height:1.6;margin-bottom:12px">'
            'Gera um PDF de boletim individual para <b>cada aluno</b> da turma e empacota '
            'tudo em um único arquivo <b>.zip</b> — ideal para o encerramento de módulo ou '
            'entrega de resultados aos coordenadores.'
            '</div>',
            unsafe_allow_html=True,
        )
        if st.button(
            f"📥 Gerar ZIP com {_n_alunos} boletins",
            width="stretch",
            key="btn_zip_boletins",
        ):
            _media_geral_zip = df_t_view["Nota"].mean()
            _zip_buf = io.BytesIO()
            _erros   = []
            with zipfile.ZipFile(_zip_buf, "w", zipfile.ZIP_DEFLATED) as _zf:
                _prog = st.progress(0, text="Iniciando geração dos boletins…")
                for _idx, _row in enumerate(perfil.itertuples(index=False), start=1):
                    _al    = _row.Aluno
                    _df_al = df_t_view[df_t_view["Aluno"] == _al].copy()
                    if _df_al.empty:
                        continue
                    _prog.progress(
                        _idx / _n_alunos,
                        text=f"Gerando boletim de {_al}… ({_idx}/{_n_alunos})",
                    )
                    try:
                        _bim = agrupar_por_semana(_df_al)
                        _pdf = gerar_boletim_pdf(
                            aluno=_al,
                            turma=label_turma_view,
                            df_al=_df_al,
                            media_al=float(getattr(_row, "Média_Simples", _df_al["Nota"].mean())),
                            media_pond=float(_row.Média),
                            media_turma=_media_geral_zip,
                            notas_baixas=int(_row.Notas_Baixas),
                            total_avals=int(_row.Total),
                            delta=float(_row.Média) - _media_geral_zip,
                            bimestres=_bim,
                            seq_critica=int(_row.Seq_Critica),
                            comparar_turma=False,
                            df_turma=df_t_view,
                            posicao=_idx,
                            total_alunos=_n_alunos,
                        )
                        _nome_arq = f"boletim_{_al.replace(' ', '_')}.pdf"
                        _zf.writestr(_nome_arq, _pdf)
                    except Exception as _e:
                        _erros.append(_al)
                _prog.empty()

            _zip_buf.seek(0)
            st.session_state[_zip_key] = _zip_buf.read()

            if _erros:
                st.warning(f"⚠️ {len(_erros)} boletim(s) não puderam ser gerados: {', '.join(_erros)}")

        if st.session_state.get(_zip_key):
            _zip_nome = (
                f"boletins_{label_turma_view.replace(' ', '_')}_"
                f"{datetime.now().strftime('%d%m%Y')}.zip"
            )
            st.download_button(
                "⬇️ Baixar ZIP",
                data=st.session_state[_zip_key],
                file_name=_zip_nome,
                mime="application/zip",
                width="stretch",
                key="dl_zip_boletins",
            )
            _ok = _n_alunos - len(st.session_state.get(f"_erros_{_zip_key}", []))
            st.success(f"✅ ZIP pronto com {_ok} boletins.")

    divider()
    with st.expander("📋 Tabela detalhada de todos os alunos"):
        df_tabela = perfil.copy()
        df_tabela["Risco"]     = df_tabela["Risco"].map(_rotulos)
        df_tabela["Tendência"] = df_tabela["Tendencia"].str.capitalize()
        df_tabela = df_tabela[["Aluno","Média","Notas_Baixas","Total","Seq_Critica","Tendência","Risco"]]
        df_tabela.columns = ["Aluno","Média","Notas Críticas","Avaliações","Seq. Crítica","Tendência","Risco"]
        st.dataframe(df_tabela, hide_index=True, width="stretch")
