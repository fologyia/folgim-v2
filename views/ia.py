import hashlib
import json
import os
import re
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import streamlit as st
from groq import Groq

from data.analysis import gerar_diagnostico

_IA_CACHE_DIR = ".ia_cache"
_IA_CACHE_TTL_DAYS = 5   # análise expira automaticamente após N dias


def _turma_slug(turma: str) -> str:
    """Transforma o nome da turma em um slug seguro para nome de arquivo."""
    slug = turma.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "_", slug, flags=re.UNICODE)
    return slug.strip("_")[:60]


def _cache_path(turma: str, tipo: str) -> str:
    """Caminho do arquivo de cache para uma turma e tipo ('analise' ou 'plano')."""
    os.makedirs(_IA_CACHE_DIR, exist_ok=True)
    return os.path.join(_IA_CACHE_DIR, f"{_turma_slug(turma)}_{tipo}.json")


def _cache_load_turma(turma: str, tipo: str) -> tuple[dict | None, str | None, bool]:
    """Carrega cache de uma turma.

    Retorna (dados, timestamp_str, expirado).
    - dados=None se o arquivo não existe.
    - expirado=True se passou do TTL (3 dias) — o chamador deve regenerar.
    """
    path = _cache_path(turma, tipo)
    if not os.path.exists(path):
        return None, None, False
    with open(path, encoding="utf-8") as f:
        wrapper = json.load(f)
    generated_at_str = wrapper.get("generated_at", "")
    try:
        generated_at = datetime.fromisoformat(generated_at_str)
    except (ValueError, TypeError):
        return None, None, False
    expirado = datetime.now() - generated_at > timedelta(days=_IA_CACHE_TTL_DAYS)
    ts_fmt = generated_at.strftime("%d/%m/%Y %H:%M")
    return wrapper.get("data"), ts_fmt, expirado


def _cache_save_turma(turma: str, tipo: str, data: dict) -> None:
    """Salva cache com timestamp de geração."""
    path = _cache_path(turma, tipo)
    wrapper = {
        "generated_at": datetime.now().isoformat(),
        "turma": turma,
        "tipo": tipo,
        "data": data,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(wrapper, f, ensure_ascii=False, indent=2)


def _cache_delete_turma(turma: str, tipo: str) -> None:
    path = _cache_path(turma, tipo)
    if os.path.exists(path):
        os.remove(path)


from config import CORES, NOTA_MINIMA, SEQUENCIA_CRITICA_MIN
from data.analysis import calcular_perfil_turma, enriquecer_perfil_ia
from pdf.generator import gerar_relatorio_ia_pdf
from ui.components import divider, section_title

MODELO_GROQ = "llama-3.3-70b-versatile"

_RISCO_COR   = {"critico": "#FF3B30", "atencao": "#F59E0B", "adequado": "#34C759", "excelente": "#007AFF"}
_RISCO_LABEL = {"critico": "🔴 Crítico", "atencao": "🟡 Atenção", "adequado": "🟢 Adequado", "excelente": "🔵 Excelente"}


def _render_fallback_diagnostico(df_turma: pd.DataFrame, turma_sel: str) -> None:
    """Exibe diagnóstico automático (sem IA) como fallback quando a API Groq está indisponível."""
    from data.analysis import calcular_perfil_turma

    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#1E3A5F 0%,#374151 100%);
                border-radius:16px;padding:24px 28px;margin-bottom:24px;color:white">
        <div style="font-size:1.4rem;font-weight:800;font-family:Montserrat,sans-serif;margin-bottom:4px">
            🧠 Diagnóstico Automático — {turma_sel}
        </div>
        <div style="opacity:0.75;font-size:0.85rem">
            Análise gerada por lógica interna · sem IA · disponível mesmo offline
        </div>
    </div>""", unsafe_allow_html=True)

    _hash = str(df_turma["Nota"].sum()) + str(len(df_turma))
    _cols = (
        ["Aluno", "Nota", "Data"]
        + (["Vetor (Peso)"] if "Vetor (Peso)" in df_turma.columns else [])
    )
    perfil = calcular_perfil_turma(_hash, df_turma[_cols].to_json(date_format="iso"))
    if perfil.empty:
        st.info("Sem dados suficientes para gerar diagnóstico.")
        return

    # KPIs resumidos
    n_crit = (perfil["Risco"] == "critico").sum()
    n_at   = (perfil["Risco"] == "atencao").sum()
    n_adeq = (perfil["Risco"] == "adequado").sum()
    n_exc  = (perfil["Risco"] == "excelente").sum()
    media_g = df_turma["Nota"].mean()

    k1, k2, k3, k4, k5 = st.columns(5)
    for col_k, val_k, lbl_k, cor_k in [
        (k1, f"{media_g:.1f}", "Média Geral",    "#007AFF"),
        (k2, str(n_crit),      "Crítico",          "#FF3B30"),
        (k3, str(n_at),        "Atenção",          "#F59E0B"),
        (k4, str(n_adeq),      "Adequado",         "#34C759"),
        (k5, str(n_exc),       "Excelente",        "#007AFF"),
    ]:
        with col_k:
            st.markdown(
                f'<div style="background:white;border-radius:12px;padding:16px;text-align:center;'
                f'box-shadow:0 1px 6px rgba(0,0,0,0.06);border-top:3px solid {cor_k}">'
                f'<div style="font-size:26px;font-weight:800;color:{cor_k}">{val_k}</div>'
                f'<div style="font-size:10px;font-weight:700;text-transform:uppercase;'
                f'color:#8E8E93;margin-top:4px;letter-spacing:0.06em">{lbl_k}</div></div>',
                unsafe_allow_html=True,
            )

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
    section_title("📋 Diagnóstico por Aluno")

    # Ordenar: críticos primeiro
    _ordem = {"critico": 0, "atencao": 1, "adequado": 2, "excelente": 3}
    perfil_ord = perfil.sort_values("Risco", key=lambda s: s.map(_ordem)).reset_index(drop=True)

    col_a, col_b = st.columns(2)
    for i, row in perfil_ord.iterrows():
        try:
            _df_al = df_turma[df_turma["Aluno"] == row["Aluno"]]
            diag = gerar_diagnostico(
                aluno=row["Aluno"],
                media=float(row["Média"]) if "Média" in row.index and pd.notna(row.get("Média")) else 0.0,
                media_pond=float(row["Média"]) if "Média" in row.index and pd.notna(row.get("Média")) else 0.0,
                tendencia=row["Tendencia"] if "Tendencia" in row.index and pd.notna(row.get("Tendencia")) else "indefinida",
                notas_baixas=int(row["Notas_Baixas"]) if "Notas_Baixas" in row.index and pd.notna(row.get("Notas_Baixas")) else 0,
                total_avals=int(row["Total"]) if "Total" in row.index and pd.notna(row.get("Total")) else 1,
                seq_critica=int(row["Seq_Critica"]) if "Seq_Critica" in row.index and pd.notna(row.get("Seq_Critica")) else 0,
                delta_turma=float(row["Média"]) - df_turma["Nota"].mean() if "Média" in row.index else 0.0,
                posicao=i + 1,
                total_alunos=len(perfil_ord),
                bimestres=pd.DataFrame(),
                df_al=_df_al,
            )
        except TypeError as e:
            st.error(f"Erro em gerar_diagnostico para {row['Aluno']}: {e}")
            continue
        cor = _RISCO_COR.get(row["Risco"], "#8E8E93")
        lbl = _RISCO_LABEL.get(row["Risco"], row["Risco"])
        html = (
            f'<div style="background:white;border-radius:14px;padding:18px 20px;'
            f'box-shadow:0 1px 4px rgba(0,0,0,0.06);border-left:4px solid {cor};margin-bottom:12px">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">'
            f'<div style="font-weight:700;font-size:14px;color:#1D1D1F">{row["Aluno"]}</div>'
            f'<div style="font-size:11px;font-weight:700;color:{cor};background:{cor}15;'
            f'padding:3px 10px;border-radius:50px">{lbl}</div></div>'
            f'<div style="font-size:12px;color:#374151;line-height:1.65">{diag["texto_resumido"]}</div>'
        )
        if diag.get("tags"):
            html += '<div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:10px">'
            for tag in diag["tags"]:
                t_cor = "#065F46" if tag.get("tipo") == "positivo" else ("#991B1B" if tag.get("tipo") == "negativo" else "#3730A3")
                t_bg  = "#D1FAE5" if tag.get("tipo") == "positivo" else ("#FEE2E2" if tag.get("tipo") == "negativo" else "#E0E7FF")
                html += f'<span style="background:{t_bg};color:{t_cor};font-size:10px;font-weight:600;padding:3px 9px;border-radius:50px">{tag["texto"]}</span>'
            html += '</div>'
        html += '</div>'

        target_col = col_a if i % 2 == 0 else col_b
        with target_col:
            st.markdown(html, unsafe_allow_html=True)


def render_ia_view(
    df_turma_filter: pd.DataFrame,
    df_freq: pd.DataFrame,
    turma_sel: str,
    perfil_ia: pd.DataFrame | None = None,
    df_turmas: pd.DataFrame = None,
    df_feriados: list = None,
) -> None:
    st.markdown(f"""
    <div class="ia-header">
        <div style="font-size:3.2rem;margin-bottom:12px">🤖</div>
        <div style="font-family:Montserrat;font-size:1.9rem;font-weight:800">Inteligência Pedagógica</div>
        <div style="opacity:0.8;font-size:0.92rem;margin-top:6px">
            Análise de <b>{turma_sel}</b> via <b>Groq · {MODELO_GROQ}</b>
        </div>
    </div>""", unsafe_allow_html=True)

    try:
        _groq_key = st.secrets.get("GROQ_API_KEY", "") or os.environ.get("GROQ_API_KEY", "")
    except Exception:
        _groq_key = os.environ.get("GROQ_API_KEY", "")
    if not _groq_key:
        _render_fallback_diagnostico(df_turma_filter, turma_sel)
        return
    client = Groq(api_key=_groq_key)

    _hash_t = str(df_turma_filter["Nota"].sum()) + str(len(df_turma_filter))

    if perfil_ia is None:
        _cols_ia = (
            ["Aluno", "Nota", "Data"]
            + (["Vetor (Peso)"] if "Vetor (Peso)" in df_turma_filter.columns else [])
            + (["Instrumento / Atividade"] if "Instrumento / Atividade" in df_turma_filter.columns else [])
        )
        perfil_ia = calcular_perfil_turma(_hash_t, df_turma_filter[_cols_ia].to_json(date_format="iso"))

    if perfil_ia.empty:
        st.warning("Sem dados suficientes para análise nesta turma.")
        st.stop()

    perfis_detalhados = enriquecer_perfil_ia(perfil_ia, df_turma_filter, df_freq, turma_sel, df_turmas, df_feriados)

    n_crit_ia = int((perfil_ia["Risco"] == "critico").sum())
    n_at_ia   = int((perfil_ia["Risco"] == "atencao").sum())
    n_adeq_ia = int((perfil_ia["Risco"] == "adequado").sum())
    n_exc_ia  = int((perfil_ia["Risco"] == "excelente").sum())
    pct_aprov = round((n_adeq_ia + n_exc_ia) / len(perfil_ia) * 100) if len(perfil_ia) > 0 else 0
    media_geral_ia = df_turma_filter["Nota"].mean()

    class _SafeEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, (np.bool_,)):    return bool(obj)
            if isinstance(obj, (np.integer,)):  return int(obj)
            if isinstance(obj, (np.floating,)): return float(obj)
            return super().default(obj)

    contexto_alunos = json.dumps(perfis_detalhados, ensure_ascii=False, separators=(",", ":"), cls=_SafeEncoder)

    # ── Diagnóstico: o que está sendo enviado para a IA ──────────────────────
    _col_obs_check = "Observação" in df_turma_filter.columns
    _total_obs = sum(
        len(p.get("todas_observacoes", [])) for p in perfis_detalhados
    )
    _alunos_com_obs = sum(
        1 for p in perfis_detalhados if p.get("todas_observacoes")
    )
    # Quais observações foram filtradas como genéricas de turma?
    _obs_genericas_view: set[str] = set()
    if _col_obs_check:
        _n_alunos = df_turma_filter["Aluno"].nunique()
        _df_obs_tmp = df_turma_filter[["Observação", "Aluno"]].copy()
        _df_obs_tmp["_txt"] = _df_obs_tmp["Observação"].fillna("").astype(str).str.strip()
        _df_obs_tmp = _df_obs_tmp[_df_obs_tmp["_txt"].str.len() > 3]
        _limiar_v = max(2, int(_n_alunos * 0.30))
        _obs_por_aluno_v = _df_obs_tmp.groupby("_txt")["Aluno"].nunique()
        _obs_genericas_view = set(_obs_por_aluno_v[_obs_por_aluno_v >= _limiar_v].index)

    if _col_obs_check and _total_obs > 0:
        st.success(
            f"✅ **{_total_obs} observação(ões) individuais** do docente detectadas em "
            f"**{_alunos_com_obs}** aluno(s) — observações genéricas de turma foram filtradas."
        )
    elif _col_obs_check:
        st.info(
            "ℹ️ Coluna **Observação** encontrada, mas todas as anotações são genéricas de turma "
            "(aparecem para vários alunos ao mesmo tempo). Nenhuma observação individual será "
            "enviada para a IA — a análise usará apenas dados numéricos."
        )
    else:
        st.warning(
            "⚠️ Coluna **Observação** não encontrada na planilha. "
            "Verifique se a coluna existe e está nomeada (ex: *Observação Técnica*)."
        )

    with st.expander("🔍 Ver dados enviados para a IA (por aluno)", expanded=False):
        if _obs_genericas_view:
            st.markdown(
                f"**Filtradas como genéricas de turma** ({len(_obs_genericas_view)} tipo(s)) — "
                f"*aparecem para múltiplos alunos, não são comentários individuais:*"
            )
            for _g in sorted(_obs_genericas_view):
                st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;🚫 ~~`{_g}`~~")
            st.markdown("---")
        st.markdown("**Observações individuais enviadas para cada aluno:**")
        for _p in perfis_detalhados:
            _obs_count = len(_p.get("todas_observacoes", []))
            _cor_exp   = "🟢" if _obs_count > 0 else "⚪"
            st.markdown(
                f"**{_cor_exp} {_p['nome']}** — média {_p['media']} · risco {_p['risco']} · "
                f"{_obs_count} observação(ões) individual(is)"
            )
            if _obs_count > 0:
                for _obs in _p["todas_observacoes"]:
                    st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;📝 `{_obs}`")

    tab_analise, tab_plano = st.tabs(["🤖 Análise Pedagógica", "📚 Plano de Recuperação"])

    # ── Tab 1: Análise Pedagógica ─────────────────────────────────────────────
    with tab_analise:
        prompt = f"""Você é um assistente pedagógico do SENAI. Seu trabalho é interpretar dados de avaliação E as anotações reais do docente para gerar diagnósticos CONCRETOS e ACIONÁVEIS.

    ══ TURMA: {turma_sel} ══
    Total: {len(perfil_ia)} alunos | Média geral: {media_geral_ia:.1f} | Taxa aprovação: {pct_aprov}% | Em risco: {n_crit_ia} crítico, {n_at_ia} atenção

    ══ DADOS POR ALUNO ══
    {contexto_alunos}

    ══ REGRAS OBRIGATÓRIAS ══

    SOBRE AS OBSERVAÇÕES DO DOCENTE (campos todas_observacoes, obs_notas_criticas):
    - As observações são ANOTAÇÕES REAIS escritas pelo próprio docente sobre o aluno
    - Se existirem: USE-AS como base principal do diagnóstico — elas revelam o que realmente acontece
    - CITE textualmente o conteúdo da observação no diagnóstico (ex: "O docente anotou: 'não entregou o projeto'")
    - Se houver padrão nas observações (ex: sempre não entrega, sempre chega tarde, sempre dificuldade em X): NOMEIE o padrão
    - Se todas_observacoes estiver vazio: baseie-se apenas nos dados numéricos

    SOBRE OS DADOS NUMÉRICOS:
    - Cite a nota, o critério com dificuldade e o vetor fraco pelo nome
    - seq_critica > 0 = urgência explícita no texto
    - frequencia_pct < 75 = mencionar risco de reprovação por falta
    - tendencia = "queda" = alertar que está piorando, não apenas "monitorar"

    PROIBIDO:
    - Frases genéricas: "continue se esforçando", "está no caminho certo", "precisa melhorar", "mostrar mais empenho"
    - Repetir diagnósticos entre alunos
    - Acao_docente vaga: "acompanhar", "conversar", "monitorar" sem dizer O QUÊ especificamente

    ══ FORMATO DE SAÍDA (JSON puro, sem markdown) ══
    {{
      "resumo_turma": "3-4 frases sobre o estado real da turma com números",
      "alertas_turma": ["alerta concreto baseado nos dados 1", "alerta concreto 2"],
      "analise_alunos": [
        {{
          "aluno": "Nome exato",
          "diagnostico": "Diagnóstico baseado nas observações do docente E nos dados numéricos (cite a obs se existir)",
          "ponto_forte": "Habilidade ou critério específico com nota boa",
          "ponto_fraco": "Critério ou vetor específico com nota baixa, ou padrão de comportamento das observações",
          "acao_docente": "O QUE fazer nos próximos dias — específico, concreto, realizável dentro da escola"
        }}
      ]
    }}"""

        response_text = ""
        try:
            _cached_data, _cache_ts, _expirado = _cache_load_turma(turma_sel, "analise")

            if _cached_data is not None and not _expirado:
                response_json = _cached_data
                _gerado_em = datetime.strptime(_cache_ts, "%d/%m/%Y %H:%M")
                _dias_restantes = _IA_CACHE_TTL_DAYS - (datetime.now() - _gerado_em).days
                st.caption(
                    f"💾 Análise gerada em **{_cache_ts}** — válida por mais "
                    f"**{max(0, _dias_restantes)} dia(s)**. "
                    f"Clique em **Reanalisar** para gerar uma nova análise agora."
                )
                if st.button("🔄 Reanalisar com IA", key="ia_reanalisar"):
                    _cache_delete_turma(turma_sel, "analise")
                    st.rerun()
            else:
                if _expirado:
                    st.info(f"🕐 A análise anterior (gerada em {_cache_ts}) expirou após {_IA_CACHE_TTL_DAYS} dias — gerando nova análise...")
                with st.spinner("🤖 Analisando turma com IA avançada... isso pode levar alguns segundos"):
                    chat_completion = client.chat.completions.create(
                        messages=[
                            {
                                "role": "system",
                                "content": (
                                    "Você é um especialista em pedagogia do SENAI. "
                                    "Responda APENAS com JSON válido, sem qualquer texto antes ou depois. "
                                    "Nunca use frases genéricas — cada análise deve ser única e baseada nos dados fornecidos."
                                ),
                            },
                            {"role": "user", "content": prompt},
                        ],
                        model=MODELO_GROQ,
                        temperature=0.5,
                        max_tokens=4096,
                    )
                    response_text = chat_completion.choices[0].message.content
                    json_start    = response_text.find('{')
                    json_end      = response_text.rfind('}') + 1
                    response_json = json.loads(response_text[json_start:json_end])
                    _cache_save_turma(turma_sel, "analise", response_json)

            # Resumo geral
            alertas_html = "".join(
                f'<div style="display:flex;align-items:flex-start;gap:10px;margin-bottom:8px">'
                f'<span style="color:{CORES["vermelho"]};font-size:1rem;margin-top:1px">⚠️</span>'
                f'<span style="font-size:0.88rem;color:#374151">{a}</span></div>'
                for a in response_json.get("alertas_turma", [])
            )
            st.markdown(f"""
            <div class="ia-chat-bubble">
                <div style="font-weight:700;color:{CORES['roxo']};margin-bottom:12px;
                            font-size:0.88rem;text-transform:uppercase;letter-spacing:0.06em">
                    🧠 Análise Geral da Turma
                </div>
                <div style="line-height:1.75;color:#1F2937;font-size:0.93rem">
                    {response_json.get('resumo_turma', 'N/A')}
                </div>
                {f'<div style="margin-top:16px;padding-top:14px;border-top:1px solid #E5E7EB">{alertas_html}</div>' if alertas_html else ''}
            </div>""", unsafe_allow_html=True)

            # Botão de exportação PDF
            _col_pdf, _ = st.columns([1, 3])
            with _col_pdf:
                if st.button("📄 Exportar relatório IA em PDF", width="stretch"):
                    with st.spinner("Gerando PDF..."):
                        _pdf = gerar_relatorio_ia_pdf(
                            turma=turma_sel,
                            resumo_turma=response_json.get("resumo_turma", ""),
                            alertas_turma=response_json.get("alertas_turma", []),
                            analise_alunos=response_json.get("analise_alunos", []),
                            n_critico=n_crit_ia, n_atencao=n_at_ia,
                            n_adequado=n_adeq_ia, n_excelente=n_exc_ia,
                            media_geral=media_geral_ia,
                        )
                    _nome = f"relatorio_ia_{turma_sel.replace(' ','_')}_{datetime.now().strftime('%d%m%Y')}.pdf"
                    st.download_button("⬇️ Baixar PDF", data=_pdf, file_name=_nome,
                                       mime="application/pdf", width="stretch")

            divider()

            m1, m2, m3, m4 = st.columns(4)
            for col, val, lbl, cor in [
                (m1, n_crit_ia, "Em Risco Crítico", CORES["vermelho"]),
                (m2, n_at_ia,   "Em Atenção",        CORES["amarelo"]),
                (m3, n_adeq_ia, "Adequados",          CORES["verde"]),
                (m4, n_exc_ia,  "Excelentes",         CORES["roxo"]),
            ]:
                with col:
                    st.markdown(f"""
                    <div style="background:white;border-radius:14px;padding:18px 20px;
                                box-shadow:0 2px 12px rgba(0,0,0,0.06);border-top:4px solid {cor};text-align:center">
                        <div style="font-family:Montserrat;font-size:2rem;font-weight:800;color:{cor}">{val}</div>
                        <div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;
                                    letter-spacing:0.08em;color:#6B7280;margin-top:4px">{lbl}</div>
                    </div>""", unsafe_allow_html=True)

            divider()
            section_title("💬 Insights Pedagógicos Individuais")

            analises_map  = {item["aluno"]: item for item in response_json.get("analise_alunos", [])}
            _icone_risco  = {"critico":"🔴","atencao":"🟡","adequado":"🟢","excelente":"🟣"}
            _label_risco  = {"critico":"Crítico","atencao":"Atenção","adequado":"Adequado","excelente":"Excelente"}
            _label_tend   = {"melhora":"▲ Melhora","queda":"▼ Queda","estável":"● Estável","indefinida":"— Indefinido"}
            _cor_tend     = {"melhora":CORES["verde"],"queda":CORES["vermelho"],"estável":CORES["amarelo"],"indefinida":"#9CA3AF"}
            _cor_borda_r  = {"critico":CORES["vermelho"],"atencao":CORES["amarelo"],"adequado":CORES["verde"],"excelente":CORES["roxo"]}

            cols = st.columns(2)
            for idx, row in perfil_ia.iterrows():
                nome    = row["Aluno"]
                risco   = row["Risco"]
                analise = analises_map.get(nome, {})
                cor_b   = _cor_borda_r[risco]
                tend_c  = _cor_tend[row["Tendencia"]]

                seq_badge = (
                    f'<span style="background:#FEE2E2;color:#991B1B;border-radius:50px;'
                    f'padding:2px 8px;font-size:0.65rem;font-weight:700;margin-left:6px">'
                    f'🚨 {row["Seq_Critica"]} seq. crítica</span>'
                    if row["Seq_Critica"] >= SEQUENCIA_CRITICA_MIN else ""
                )

                parts = [
                    f'<div class="ia-student-card" style="border-left:5px solid {cor_b};padding:18px 20px;margin-bottom:14px">',
                    f'<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:12px">',
                    f'<div><div style="font-weight:700;font-size:1rem;color:#111827">{nome}</div>',
                    f'<div style="font-size:0.72rem;margin-top:3px;display:flex;align-items:center;gap:6px">',
                    f'<span style="background:{cor_b}18;color:{cor_b};padding:2px 9px;border-radius:50px;font-weight:700">{_icone_risco[risco]} {_label_risco[risco]}</span>',
                    f'<span style="color:{tend_c};font-weight:600">{_label_tend[row["Tendencia"]]}</span>',
                    seq_badge, '</div></div>',
                    f'<div style="text-align:right">',
                    f'<div style="font-family:Montserrat;font-weight:800;font-size:1.6rem;color:{cor_b};line-height:1">{row["Média"]:.1f}</div>',
                    f'<div style="font-size:0.68rem;color:#9CA3AF">{row["Notas_Baixas"]} crítica(s) / {row["Total"]} avals</div>',
                    '</div></div>',
                    f'<div style="background:#F8FAFC;border-radius:8px;padding:10px 12px;margin-bottom:10px;border-left:3px solid {cor_b}">',
                    '<div style="font-size:0.7rem;font-weight:700;text-transform:uppercase;letter-spacing:0.06em;color:#6B7280;margin-bottom:4px">📋 Diagnóstico</div>',
                    f'<div style="font-size:0.85rem;color:#1F2937;line-height:1.55">{analise.get("diagnostico","—")}</div></div>',
                    '<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:10px">',
                    '<div style="background:#F0FDF4;border-radius:8px;padding:9px 11px">',
                    '<div style="font-size:0.68rem;font-weight:700;color:#059669;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:3px">✅ Ponto Forte</div>',
                    f'<div style="font-size:0.82rem;color:#065F46;line-height:1.45">{analise.get("ponto_forte","—")}</div></div>',
                    '<div style="background:#FFF5F5;border-radius:8px;padding:9px 11px">',
                    '<div style="font-size:0.68rem;font-weight:700;color:#DC2626;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:3px">⚠️ Ponto Fraco</div>',
                    f'<div style="font-size:0.82rem;color:#991B1B;line-height:1.45">{analise.get("ponto_fraco","—")}</div></div></div>',
                    '<div style="background:#FFFBEB;border:1px solid #FDE68A;border-radius:8px;padding:10px 12px">',
                    '<div style="font-size:0.68rem;font-weight:700;color:#B45309;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:4px">🎯 Ação Recomendada ao Docente</div>',
                    f'<div style="font-size:0.85rem;color:#78350F;line-height:1.55;font-weight:500">{analise.get("acao_docente","—")}</div></div></div>',
                ]
                with cols[idx % 2]:
                    st.markdown("".join(parts), unsafe_allow_html=True)

        except json.JSONDecodeError:
            st.markdown(
                '<div style="background:#FFF7ED;border:1px solid #FED7AA;border-left:5px solid #F97316;'
                'border-radius:12px;padding:16px 20px;margin-bottom:16px">'
                '<b style="color:#C2410C">⚠️ Resposta da IA em formato inesperado</b>'
                '<p style="color:#78350F;font-size:13px;margin:6px 0 0">A IA retornou algo fora do padrão. '
                'Exibindo diagnóstico automático como alternativa.</p></div>',
                unsafe_allow_html=True,
            )
            if response_text:
                with st.expander("Ver resposta bruta da IA"):
                    st.code(response_text)
            _render_fallback_diagnostico(df_turma_filter, turma_sel)
        except Exception as e:
            err_msg = str(e)
            if "auth" in err_msg.lower() or "401" in err_msg or "403" in err_msg:
                _motivo = "Chave da API inválida ou sem permissão (`GROQ_API_KEY` deve começar com `gsk_`)."
            elif "connection" in err_msg.lower() or "network" in err_msg.lower():
                _motivo = "Sem conexão com a API Groq. Verifique internet ou firewall bloqueando `api.groq.com`."
            elif "rate" in err_msg.lower() or "429" in err_msg:
                _motivo = "Limite de requisições da API atingido. Aguarde alguns minutos e tente novamente."
            else:
                _motivo = f"Erro técnico: {err_msg}"
            st.markdown(
                f'<div style="background:#FFF7ED;border:1px solid #FED7AA;border-left:5px solid #F97316;'
                f'border-radius:12px;padding:16px 20px;margin-bottom:16px">'
                f'<b style="color:#C2410C">⚠️ IA temporariamente indisponível</b>'
                f'<p style="color:#78350F;font-size:13px;margin:6px 0 0">{_motivo}</p>'
                f'<p style="color:#92400E;font-size:12px;margin:4px 0 0">'
                f'Exibindo análise automática como alternativa.</p></div>',
                unsafe_allow_html=True,
            )
            _render_fallback_diagnostico(df_turma_filter, turma_sel)

    # ── Tab 2: Plano de Recuperação ───────────────────────────────────────────
    with tab_plano:
        _alunos_risco = perfil_ia[perfil_ia["Risco"].isin(["critico", "atencao"])].copy()

        if _alunos_risco.empty:
            st.markdown(
                '<div style="background:#F0FDF4;border:1px solid #BBF7D0;border-radius:14px;'
                'padding:28px;text-align:center;margin-top:20px">'
                '<div style="font-size:2.5rem;margin-bottom:10px">🎉</div>'
                '<div style="font-weight:700;font-size:1.1rem;color:#15803D">Nenhum aluno em risco ou atenção!</div>'
                '<div style="color:#166534;font-size:0.9rem;margin-top:6px">Toda a turma está com desempenho adequado ou excelente.</div>'
                '</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<div style="background:#FFF7ED;border:1px solid #FED7AA;border-radius:12px;'
                f'padding:14px 20px;margin-bottom:20px">'
                f'<b style="color:#C2410C">📚 Planos de recuperação para {len(_alunos_risco)} aluno(s)</b>'
                f'<span style="color:#92400E;font-size:0.88rem;display:block;margin-top:3px">'
                f'A IA gera um plano de ação personalizado com atividades, cronograma e metas para cada aluno em risco ou atenção.</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

            _perfis_risco = [p for p in perfis_detalhados if p["risco"] in ("critico", "atencao")]
            _ctx_risco    = json.dumps(_perfis_risco, ensure_ascii=False, separators=(",", ":"), cls=_SafeEncoder)

            _plano_prompt = f"""Você é um especialista em pedagogia do SENAI. Crie PLANOS DE RECUPERAÇÃO DETALHADOS E PERSONALIZADOS para cada aluno listado.

    ══ DADOS DOS ALUNOS EM RISCO ══
    {_ctx_risco}

    ══ INSTRUÇÕES ══
    Para cada aluno:
    - Use os dados reais (vetor fraco, critérios com dificuldade, tendência, observações do docente)
    - Sugira atividades CONCRETAS e REALIZÁVEIS dentro da escola/curso técnico
    - Defina metas numéricas (ex: "atingir 6.5 no vetor Saber até o final do mês")
    - Baseie as atividades no contexto SENAI (educação profissional, laboratório, projetos práticos)

    ══ FORMATO DE SAÍDA (JSON puro, sem markdown) ══
    {{
      "planos_recuperacao": [
        {{
          "aluno": "Nome exato",
          "risco": "critico ou atencao",
          "media_atual": 0.0,
          "diagnostico_resumido": "1-2 frases sobre o problema central deste aluno",
          "foco_principal": "Qual área/vetor/critério precisa de mais atenção",
          "acoes_semana_1": ["Ação imediata 1", "Ação imediata 2"],
          "atividades_sugeridas": ["Atividade concreta 1", "Atividade concreta 2", "Atividade concreta 3"],
          "plano_30_dias": "Descrição do que o docente deve implementar nas próximas 4 semanas",
          "meta": "Meta específica e mensurável de resultado"
        }}
      ]
    }}"""

            _plano_response = ""
            try:
                _plano_data, _plano_ts, _plano_expirado = _cache_load_turma(turma_sel, "plano")

                if _plano_data is not None and not _plano_expirado:
                    _plano_json = _plano_data
                    _plano_gerado_em = datetime.strptime(_plano_ts, "%d/%m/%Y %H:%M")
                    _plano_dias_rest = _IA_CACHE_TTL_DAYS - (datetime.now() - _plano_gerado_em).days
                    st.caption(
                        f"💾 Planos gerados em **{_plano_ts}** — válidos por mais "
                        f"**{max(0, _plano_dias_rest)} dia(s)**. "
                        f"Clique em **Reanalisar Planos** para gerar novos agora."
                    )
                    if st.button("🔄 Reanalisar Planos", key="plano_reanalisar"):
                        _cache_delete_turma(turma_sel, "plano")
                        st.rerun()
                else:
                    if _plano_expirado:
                        st.info(f"🕐 Os planos anteriores (gerados em {_plano_ts}) expiraram — gerando novos planos...")
                    with st.spinner("🤖 Gerando planos de recuperação personalizados..."):
                        _plano_chat = client.chat.completions.create(
                            messages=[
                                {
                                    "role": "system",
                                    "content": (
                                        "Você é um especialista em pedagogia do SENAI. "
                                        "Responda APENAS com JSON válido. "
                                        "Cada plano deve ser único e baseado nos dados reais do aluno."
                                    ),
                                },
                                {"role": "user", "content": _plano_prompt},
                            ],
                            model=MODELO_GROQ,
                            temperature=0.4,
                            max_tokens=4096,
                        )
                        _plano_response = _plano_chat.choices[0].message.content
                        _js = _plano_response.find('{')
                        _je = _plano_response.rfind('}') + 1
                        _plano_json = json.loads(_plano_response[_js:_je])
                        _cache_save_turma(turma_sel, "plano", _plano_json)

                divider()
                _icone_r2 = {"critico": "🔴", "atencao": "🟡"}
                _cor_r2   = {"critico": CORES["vermelho"], "atencao": CORES["amarelo"]}
                _cor_bg2  = {"critico": "#FFF1F1", "atencao": "#FFFBEB"}

                for plano in _plano_json.get("planos_recuperacao", []):
                    _rk  = plano.get("risco", "atencao")
                    _cr  = _cor_r2.get(_rk, "#F59E0B")
                    _bg  = _cor_bg2.get(_rk, "#FFFBEB")
                    _ic  = _icone_r2.get(_rk, "🟡")
                    _med = plano.get("media_atual", "—")
                    _acoes = "".join(
                        f'<li style="margin-bottom:4px">{a}</li>'
                        for a in plano.get("acoes_semana_1", [])
                    )
                    _ativs = "".join(
                        f'<div style="background:white;border:1px solid #E5E7EB;border-radius:8px;'
                        f'padding:8px 12px;margin-bottom:6px;font-size:0.84rem;color:#374151">'
                        f'📌 {at}</div>'
                        for at in plano.get("atividades_sugeridas", [])
                    )
                    st.markdown(f"""
                    <div style="background:{_bg};border:1px solid {_cr}40;border-left:5px solid {_cr};
                                border-radius:12px;padding:20px 22px;margin-bottom:18px">
                        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
                            <div>
                                <div style="font-weight:700;font-size:1rem;color:#111827">{_ic} {plano.get('aluno','—')}</div>
                                <div style="font-size:0.78rem;color:{_cr};font-weight:600;margin-top:2px">
                                    Foco: {plano.get('foco_principal','—')}
                                </div>
                            </div>
                            <div style="background:{_cr};color:white;border-radius:50%;width:44px;height:44px;
                                        display:flex;align-items:center;justify-content:center;
                                        font-family:Montserrat;font-weight:800;font-size:1rem">{_med}</div>
                        </div>
                        <div style="background:white;border-radius:8px;padding:10px 14px;margin-bottom:12px;
                                    border-left:3px solid {_cr}">
                            <div style="font-size:0.68rem;font-weight:700;color:#6B7280;text-transform:uppercase;
                                        letter-spacing:0.06em;margin-bottom:4px">📋 Diagnóstico</div>
                            <div style="font-size:0.85rem;color:#1F2937">{plano.get('diagnostico_resumido','—')}</div>
                        </div>
                        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px">
                            <div>
                                <div style="font-size:0.68rem;font-weight:700;color:#DC2626;text-transform:uppercase;
                                            letter-spacing:0.06em;margin-bottom:6px">⚡ Ações Imediatas (Semana 1)</div>
                                <ul style="margin:0;padding-left:16px;color:#374151;font-size:0.84rem;line-height:1.6">
                                    {_acoes}
                                </ul>
                            </div>
                            <div>
                                <div style="font-size:0.68rem;font-weight:700;color:#059669;text-transform:uppercase;
                                            letter-spacing:0.06em;margin-bottom:6px">🎯 Meta</div>
                                <div style="background:#F0FDF4;border-radius:8px;padding:10px 12px;
                                            font-size:0.84rem;color:#065F46">{plano.get('meta','—')}</div>
                            </div>
                        </div>
                        <div style="margin-bottom:10px">
                            <div style="font-size:0.68rem;font-weight:700;color:#1D4ED8;text-transform:uppercase;
                                        letter-spacing:0.06em;margin-bottom:6px">📅 Plano 30 Dias</div>
                            <div style="background:#EFF6FF;border-radius:8px;padding:10px 14px;
                                        font-size:0.84rem;color:#1E40AF;line-height:1.6">{plano.get('plano_30_dias','—')}</div>
                        </div>
                        <div>
                            <div style="font-size:0.68rem;font-weight:700;color:#7C3AED;text-transform:uppercase;
                                        letter-spacing:0.06em;margin-bottom:6px">🛠️ Atividades Sugeridas</div>
                            {_ativs}
                        </div>
                    </div>""", unsafe_allow_html=True)

            except json.JSONDecodeError:
                st.error("A IA retornou um formato inválido. Tente novamente.")
                if _plano_response:
                    with st.expander("Ver resposta bruta"):
                        st.code(_plano_response)
            except Exception as e:
                st.error(f"Erro ao gerar planos de recuperação: {e}")
