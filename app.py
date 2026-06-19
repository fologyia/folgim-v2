import os
import time
from datetime import datetime

import pandas as pd
import streamlit as st

from data.loader import carregar_dados
from data.cleaner import limpar_avaliacoes, limpar_alunos, limpar_recuperacoes, limpar_frequencia
from data.analysis import calcular_perfil_turma
from ui.styles import CSS_GLOBAL
from utils import coluna_uc
from views.aluno import render_aluno_view
from views.turma import render_turma_view
from views.ia import render_ia_view
from email_report import enviar_relatorio, enviar_email_teste, ultimo_envio_fmt, deve_enviar_agora

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURAÇÃO DA PÁGINA
# ══════════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="SENAI | Painel Docente",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(CSS_GLOBAL, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# CARGA E PRÉ-PROCESSAMENTO
# ══════════════════════════════════════════════════════════════════════════════
force_ts = st.session_state.get("force_ts", 0)

with st.spinner("Carregando dados..."):
    raw_aval, raw_alunos, raw_rec, raw_freq, raw_turmas, raw_feriados, fonte_dados = carregar_dados(force_ts)
    df        = limpar_avaliacoes(raw_aval)
    df_alunos = limpar_alunos(raw_alunos)
    df_rec    = limpar_recuperacoes(raw_rec)
    df_freq   = limpar_frequencia(raw_freq)
    df_turmas = raw_turmas.copy() if not raw_turmas.empty else pd.DataFrame()
    _col_feriado = "Data"
    if not raw_feriados.empty:
        for col in raw_feriados.columns:
            col_lower = str(col).strip().lower()
            if col_lower in ["data", "datas", "feriado", "feriados", "dia", "dias", "recesso", "recessos"]:
                _col_feriado = col
                break
        else:
            _col_feriado = raw_feriados.columns[0]
            
    df_feriados = pd.to_datetime(raw_feriados[_col_feriado], errors="coerce", dayfirst=True).dropna().dt.normalize().unique().tolist() if not raw_feriados.empty and _col_feriado in raw_feriados.columns else []

_dup = df.attrs.get("duplicatas_removidas", 0)
if _dup:
    st.html(
        f"""
        <style>
        body {{ margin:0; padding:0; overflow:hidden; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; }}
        #dup-alert {{
            background:#FFF7ED; border:1px solid #FED7AA;
            border-left:5px solid #F97316; border-radius:10px;
            padding:12px 16px; transition:opacity 0.5s ease;
        }}
        </style>
        <div id="dup-alert">
            <b style="color:#C2410C">⚠️ {_dup} avaliação(ões) duplicada(s) removida(s)</b>
            <span style="color:#92400E;font-size:0.88rem;display:block;margin-top:3px">
                Mesmo aluno + data + critério + vetor. Verifique a planilha — apenas o último registro foi mantido.
            </span>
        </div>
        <script>
        setTimeout(function() {{
            var el = document.getElementById('dup-alert');
            if (el) {{
                el.style.opacity = '0';
                setTimeout(function() {{
                    el.style.display = 'none';
                    var frame = window.frameElement;
                    if (frame) frame.style.height = '0px';
                }}, 500);
            }}
        }}, 20000);
        </script>
        """)

# Registrar horário da última carga e detectar regressões após refresh
_foi_refresh = force_ts != 0 and force_ts != st.session_state.get("last_force_ts", -1)

if "ultima_atualizacao" not in st.session_state or _foi_refresh:
    st.session_state["ultima_atualizacao"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    st.session_state["last_force_ts"] = force_ts

# ── Chip de frescor dos dados (canto superior direito do conteúdo) ────────
_ts_chip = st.session_state.get("ultima_atualizacao", "")
if _ts_chip:
    try:
        _dt_chip  = datetime.strptime(_ts_chip, "%d/%m/%Y %H:%M:%S")
        _min_chip = int((datetime.now() - _dt_chip).total_seconds() / 60)
        if _min_chip < 3:
            _chip_cor, _chip_txt, _chip_emoji = "#10B981", "Agora mesmo",         "🟢"
        elif _min_chip < 10:
            _chip_cor, _chip_txt, _chip_emoji = "#10B981", f"há {_min_chip} min", "🟢"
        elif _min_chip < 60:
            _chip_cor, _chip_txt, _chip_emoji = "#F59E0B", f"há {_min_chip} min", "🟡"
        elif _min_chip < 180:
            _chip_cor, _chip_txt, _chip_emoji = "#F97316", f"há {_min_chip//60}h{_min_chip%60:02d}min", "🟠"
        else:
            _chip_cor, _chip_txt, _chip_emoji = "#E30613", f"há {_min_chip//60}h — clique em Atualizar", "🔴"
        st.markdown(
            f'<div style="display:flex;justify-content:flex-end;margin-bottom:4px">'
            f'<span style="font-size:0.72rem;color:{_chip_cor};font-weight:600;'
            f'background:{_chip_cor}12;border:1px solid {_chip_cor}30;border-radius:50px;'
            f'padding:3px 10px">{_chip_emoji} Dados atualizados {_chip_txt}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
    except Exception:
        pass

# Enriquecer df com coluna Turma a partir de df_alunos
if "Turma" not in df.columns:
    df["Turma"] = ""
if not df_alunos.empty and {"Aluno", "Turma"} <= set(df_alunos.columns):
    turma_map = df_alunos.set_index("Aluno")["Turma"].to_dict()
    sem_turma = df["Turma"].isna() | (df["Turma"].astype(str).str.strip() == "")
    df.loc[sem_turma, "Turma"] = df.loc[sem_turma, "Aluno"].map(turma_map)
df["Turma"] = df["Turma"].fillna("Geral").replace("", "Geral")

# ── Snapshot do perfil atual para detecção de regressão no próximo refresh ──
def _snapshot_perfil(df_snap: pd.DataFrame) -> dict:
    """Retorna {aluno: risco} para a turma inteira."""
    if df_snap.empty:
        return {}
    _cols = ["Aluno", "Nota", "Data"] + (["Vetor (Peso)"] if "Vetor (Peso)" in df_snap.columns else [])
    _hash = str(df_snap["Nota"].sum()) + str(len(df_snap))
    perfil = calcular_perfil_turma(_hash, df_snap[_cols].to_json())
    return dict(zip(perfil["Aluno"], perfil["Risco"])) if not perfil.empty else {}

_ORDEM_RISCO = {"excelente": 3, "adequado": 2, "atencao": 1, "critico": 0}

# Gravar snapshot ANTES de mostrar o alerta (para a próxima comparação)
_snap_key = "perfil_snapshot"
_perfil_atual = _snapshot_perfil(df)

if _foi_refresh and _snap_key in st.session_state:
    _prev = st.session_state[_snap_key]
    _regressoes = []
    for aluno, risco_novo in _perfil_atual.items():
        risco_ant = _prev.get(aluno)
        if risco_ant and _ORDEM_RISCO.get(risco_novo, 2) < _ORDEM_RISCO.get(risco_ant, 2):
            _regressoes.append((aluno, risco_ant, risco_novo))

    if _regressoes:
        _icone_r = {"critico": "🔴", "atencao": "🟡", "adequado": "🟢", "excelente": "🟣"}
        _label_r = {"critico": "Crítico", "atencao": "Atenção", "adequado": "Adequado", "excelente": "Excelente"}
        _itens   = "".join(
            f"<li><b>{a}</b>: {_icone_r.get(ant,'?')} {_label_r.get(ant,ant)} "
            f"→ {_icone_r.get(nov,'?')} {_label_r.get(nov,nov)}</li>"
            for a, ant, nov in _regressoes
        )
        st.markdown(
            f'<div style="background:#FFF7ED;border:1px solid #FED7AA;border-left:5px solid #F97316;'
            f'border-radius:10px;padding:14px 18px;margin-bottom:16px">'
            f'<div style="font-weight:700;color:#C2410C;margin-bottom:8px">'
            f'⚠️ {len(_regressoes)} aluno(s) regrediram desde a última atualização</div>'
            f'<ul style="margin:0;padding-left:18px;color:#7C2D12;font-size:0.9rem">{_itens}</ul>'
            f'</div>',
            unsafe_allow_html=True,
        )

st.session_state[_snap_key] = _perfil_atual

# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    if os.path.exists("logo_senai.png"):
        st.image("logo_senai.png", width="stretch")
    else:
        st.markdown("""
        <div style='text-align:center;padding:16px 0 24px'>
            <div style='font-family:Montserrat,sans-serif;font-size:2rem;
                        font-weight:900;color:white;letter-spacing:-0.03em'>SENAI</div>
            <div style='font-size:0.68rem;color:rgba(255,255,255,0.55);
                        letter-spacing:0.18em;margin-top:3px'>PAINEL DOCENTE</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("---")
    modo_view = st.radio(
        "Modo de visualização",
        ["👤 Aluno Individual", "🏫 Visão da Turma", "🤖 Análise IA da Turma"],
        label_visibility="collapsed",
    )

    st.markdown("---")
    lista_turmas    = ["Todas as Turmas"] + sorted(df["Turma"].dropna().unique().tolist())
    turma_sel       = st.selectbox("🏫 Turma / Curso", lista_turmas)
    df_turma_filter = df if turma_sel == "Todas as Turmas" else df[df["Turma"] == turma_sel]

    # Valores padrão para variáveis de filtro
    aluno_sel       = None
    uc_sel          = "Todas as Unidades"
    vetor_sel       = "Todos os Vetores"
    col_uc_global   = coluna_uc(df)
    comparar_turma  = False
    mostrar_ranking = False
    mostrar_turma   = False
    uc_sel_turma    = "Todas as Unidades"
    risco_filtro    = []

    if modo_view == "👤 Aluno Individual":
        lista_alunos = sorted(df_turma_filter["Aluno"].dropna().unique().tolist())
        if lista_alunos:
            aluno_sel = st.selectbox("👤 Aluno", lista_alunos)

        lista_uc = ["Todas as Unidades"] + sorted(df[col_uc_global].dropna().unique().tolist())
        uc_sel   = st.selectbox("📚 Unidade Curricular", lista_uc)

        if "Vetor (Peso)" in df.columns:
            lista_vetores = ["Todos os Vetores"] + sorted(df["Vetor (Peso)"].dropna().unique().tolist())
            vetor_sel     = st.selectbox("🎯 Vetor", lista_vetores)

        st.markdown("---")
        comparar_turma  = st.checkbox("📊 Comparar com a Turma", value=False)
        mostrar_ranking = st.checkbox("🏆 Ranking da Turma", value=False)
        mostrar_turma   = st.checkbox("🌡️ Mapa de Calor da Turma", value=False)

    elif modo_view == "🏫 Visão da Turma":
        lista_uc_t = ["Todas as Unidades"] + sorted(df[col_uc_global].dropna().unique().tolist())
        uc_sel_turma = st.selectbox("📚 Filtrar por UC", lista_uc_t)

        risco_filtro = st.multiselect(
            "🚦 Filtrar por risco",
            ["critico", "atencao", "adequado", "excelente"],
            default=["critico", "atencao", "adequado", "excelente"],
            format_func=lambda x: {
                "critico":  "🔴 Crítico",
                "atencao":  "🟡 Atenção",
                "adequado": "🟢 Adequado",
                "excelente":"🟣 Excelente",
            }[x],
        )

    # ── Rodapé da sidebar: indicador de frescor + e-mail + refresh ──────────
    st.markdown("---")
    icone = "🟢" if fonte_dados == "google_sheets" else "🟡"
    label = "Google Sheets" if fonte_dados == "google_sheets" else "Arquivo local"
    ultima = st.session_state.get("ultima_atualizacao", "—")
    _freq_ok = not df_freq.empty and "Aluno" in df_freq.columns
    _freq_icone = "🟢" if _freq_ok else "🔴"
    _freq_label = f"{len(df_freq)} registros" if _freq_ok else "não carregada"

    # Calcular frescor dos dados
    _ts_ultima = st.session_state.get("ultima_atualizacao")
    _frescor_cor = "rgba(255,255,255,0.5)"
    _frescor_txt = "—"
    if _ts_ultima:
        try:
            _dt_ult = datetime.strptime(_ts_ultima, "%d/%m/%Y %H:%M:%S")
            _mins = int((datetime.now() - _dt_ult).total_seconds() / 60)
            if _mins < 3:
                _frescor_cor, _frescor_txt = "#34C759", f"Agora mesmo"
            elif _mins < 10:
                _frescor_cor, _frescor_txt = "#34C759", f"há {_mins} min"
            elif _mins < 60:
                _frescor_cor, _frescor_txt = "#F59E0B", f"há {_mins} min"
            elif _mins < 180:
                _frescor_cor, _frescor_txt = "#F97316", f"há {_mins//60}h{_mins%60:02d}min"
            else:
                _frescor_cor, _frescor_txt = "#E30613", f"há {_mins//60}h — atualize!"
        except Exception:
            pass

    st.markdown(f"""
    <div style='font-size:0.72rem;color:rgba(255,255,255,0.5);margin-bottom:8px'>
        {icone} Fonte: <b style='color:rgba(255,255,255,0.8)'>{label}</b><br>
        {_freq_icone} Frequência: <b style='color:rgba(255,255,255,0.8)'>{_freq_label}</b><br>
        <span style='font-size:0.68rem;color:{_frescor_cor};font-weight:600'>⏱ Dados: {_frescor_txt}</span>
    </div>""", unsafe_allow_html=True)

    if st.button("🔄 Atualizar dados", width="stretch"):
        st.session_state["force_ts"] = int(time.time())
        st.rerun()

    # ── Relatório Semanal por E-mail ─────────────────────────────────────────
    st.markdown("---")
    try:
        _email_conf = bool(
            st.secrets.get("EMAIL_REMETENTE", "") and
            st.secrets.get("EMAIL_SENHA", "") and
            st.secrets.get("EMAIL_DESTINATARIO", "")
        )
    except Exception:
        _email_conf = False
    _ultimo_envio = ultimo_envio_fmt()
    _envio_lbl    = f"Último: {_ultimo_envio}" if _ultimo_envio else "Nunca enviado"

    st.markdown(
        f'<div style="font-size:0.72rem;color:rgba(255,255,255,0.5);margin-bottom:6px">'
        f'{"✉️" if _email_conf else "⚙️"} <b style="color:rgba(255,255,255,0.8)">Relatório Semanal</b>'
        f'{"" if not _email_conf else " <span style=\"color:#34C759;font-size:0.65rem\">● ativo</span>"}<br>'
        f'<span style="font-size:0.65rem;opacity:0.7">📅 Sextas às 16:30 · {_envio_lbl}</span></div>',
        unsafe_allow_html=True,
    )

    if not _email_conf:
        st.markdown(
            '<div style="font-size:0.68rem;color:#F59E0B;margin-bottom:6px">'
            '⚙️ Configure EMAIL_* em secrets.toml para ativar</div>',
            unsafe_allow_html=True,
        )
    else:
        if st.button("🧪 Testar configuração", width="stretch", key="btn_teste_email"):
            with st.spinner("Enviando e-mail de teste..."):
                _ok_t, _msg_t = enviar_email_teste()
            if _ok_t:
                st.success(_msg_t)
            else:
                st.error(_msg_t)

        if st.button("📧 Enviar relatório agora", width="stretch"):
            with st.spinner("Gerando e enviando relatório..."):
                _cols_email = (
                    ["Aluno", "Nota", "Data"]
                    + (["Vetor (Peso)"] if "Vetor (Peso)" in df_turma_filter.columns else [])
                )
                _hash_email = str(df_turma_filter["Nota"].sum()) + str(len(df_turma_filter))
                _perf_email = calcular_perfil_turma(_hash_email, df_turma_filter[_cols_email].to_json())
                _ok, _msg = enviar_relatorio(
                    turma=turma_sel,
                    perfil_df=_perf_email,
                    df_freq=df_freq,
                    df_turma=df_turma_filter,
                    df_turmas=df_turmas,
                    df_feriados=df_feriados,
                )
            if _ok:
                st.success(_msg)
            else:
                st.error(_msg)

    # Auto-envio semanal (verificar na carga, silencioso)
    if _email_conf and deve_enviar_agora():
        try:
            _cols_ae = (
                ["Aluno", "Nota", "Data"]
                + (["Vetor (Peso)"] if "Vetor (Peso)" in df.columns else [])
            )
            _hash_ae = str(df["Nota"].sum()) + str(len(df))
            _perf_ae = calcular_perfil_turma(_hash_ae, df[_cols_ae].to_json())
            _ok_ae, _ = enviar_relatorio(
                turma="Todas as Turmas",
                perfil_df=_perf_ae,
                df_freq=df_freq,
                df_turma=df,
                    df_turmas=df_turmas,
                    df_feriados=df_feriados,
            )
        except Exception:
            pass  # falha silenciosa no auto-envio

# ══════════════════════════════════════════════════════════════════════════════
# ROTEAMENTO DE VIEWS
# ══════════════════════════════════════════════════════════════════════════════
if modo_view == "🤖 Análise IA da Turma":
    _cols_ia = (
        ["Aluno", "Nota", "Data"]
        + (["Vetor (Peso)"] if "Vetor (Peso)" in df_turma_filter.columns else [])
        + (["Instrumento / Atividade"] if "Instrumento / Atividade" in df_turma_filter.columns else [])
    )
    _hash_ia  = str(df_turma_filter["Nota"].sum()) + str(len(df_turma_filter))
    _perfil_ia = calcular_perfil_turma(_hash_ia, df_turma_filter[_cols_ia].to_json())
    render_ia_view(df_turma_filter, df_freq, turma_sel, perfil_ia=_perfil_ia, df_turmas=df_turmas, df_feriados=df_feriados)

elif modo_view == "🏫 Visão da Turma":
    render_turma_view(df_turma_filter, df_freq, risco_filtro, uc_sel_turma, turma_sel, df_turmas=df_turmas, df_feriados=df_feriados)

else:  # 👤 Aluno Individual
    if aluno_sel:
        render_aluno_view(
            df, df_turma_filter, df_alunos, df_rec, df_freq,
            aluno_sel, uc_sel, vetor_sel, col_uc_global,
            comparar_turma, mostrar_ranking, mostrar_turma, turma_sel, df_turmas=df_turmas, df_feriados=df_feriados,
        )
    else:
        st.info("Nenhum aluno encontrado para a turma selecionada.")
