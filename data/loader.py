import os
import time
import urllib.parse

import pandas as pd
import streamlit as st


def _sheet_id() -> str:
    try:
        val = st.secrets.get("SHEET_ID", "")
        if val and val != "SEU_ID_AQUI":
            return val
    except Exception:
        pass
    env_val = os.environ.get("SHEET_ID", "SEU_ID_AQUI")
    return env_val


def _drop_unnamed(df: pd.DataFrame) -> pd.DataFrame:
    """Remove colunas cujo nome começa com 'Unnamed'."""
    return df.loc[:, ~df.columns.astype(str).str.startswith("Unnamed")]


def url_aba(sheet_id: str, nome_aba: str, bust_cache: bool = False) -> str:
    ts = f"&_t={int(time.time())}" if bust_cache else ""
    return (
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq"
        f"?tqx=out:csv&sheet={urllib.parse.quote(nome_aba)}{ts}"
    )


@st.cache_data(ttl=120)
def carregar_dados(force_ts: int = 0):  # force_ts quebra o cache do Streamlit E do Google
    bust      = force_ts != 0
    SHEET_ID  = _sheet_id()
    if SHEET_ID != "SEU_ID_AQUI":
        try:
            df_freq_gs = pd.DataFrame()
            _freq_names = ["Frequência", "Frequencia", "Freq", "frequência", "FREQUENCIA", "FREQUÊNCIA"]
            for _fname in _freq_names:
                try:
                    _raw = pd.read_csv(url_aba(SHEET_ID, _fname, bust))
                    _cols_lower = [str(c).lower() for c in _raw.columns]
                    if not any("aluno" in c or "nome" in c for c in _cols_lower):
                        # Tentar com skiprows=1 (cabeçalho na segunda linha)
                        _raw2 = pd.read_csv(url_aba(SHEET_ID, _fname, bust), skiprows=1)
                        _cols2 = [str(c).lower() for c in _raw2.columns]
                        if any("aluno" in c or "nome" in c for c in _cols2):
                            _raw = _raw2
                    df_freq_gs = _raw
                    break
                except Exception:
                    continue
            # Tenta variações de nome para cada aba principal
            def _ler_aba(nomes: list, **kwargs) -> pd.DataFrame:
                for nome in nomes:
                    try:
                        df_r = pd.read_csv(url_aba(SHEET_ID, nome, bust), **kwargs)
                        if not df_r.empty:
                            return df_r
                    except Exception:
                        continue
                return pd.DataFrame()

            df_aval = _ler_aba(["Avaliações", "Avaliacoes", "Avaliacao", "Avaliações ", "avaliações", "AVALIAÇÕES", "Notas", "notas"])
            df_alun = _ler_aba(["Alunos", "alunos", "ALUNOS", "Aluno"], skiprows=1)
            df_recu = _ler_aba(["Recuperações", "Recuperacoes", "Recuperação", "recuperações", "RECUPERAÇÕES", "Rec"])
            df_turm = _ler_aba(["Turmas", "turmas", "TURMAS"], skiprows=1)
            df_feri = _ler_aba(["Feriados", "feriados", "FERIADOS", "Recessos", "recessos"], skiprows=1)

            if df_aval.empty:
                raise ValueError("Aba de Avaliações não encontrada no Google Sheets.")

            return (
                _drop_unnamed(df_aval.dropna(how="all")),
                _drop_unnamed(df_alun.dropna(how="all")),
                _drop_unnamed(df_recu.dropna(how="all")),
                _drop_unnamed(df_freq_gs),
                _drop_unnamed(df_turm.dropna(how="all")).rename(columns=lambda x: x.strip()),
                _drop_unnamed(df_feri.dropna(how="all")).rename(columns=lambda x: x.strip()),
                "google_sheets",
            )
        except Exception as e:
            st.sidebar.warning(f"⚠️ Sheets indisponível: {e} — usando arquivo local")

    try:
        xls  = pd.ExcelFile("planilha_notas.xlsx", engine="openpyxl")
        abas = xls.sheet_names
        df_aval  = pd.read_excel(xls, sheet_name="Avaliações" if "Avaliações" in abas else 0)
        df_aluno = pd.read_excel(xls, sheet_name="Alunos") if "Alunos" in abas else pd.DataFrame()
        df_rec   = pd.read_excel(xls, sheet_name="Recuperações") if "Recuperações" in abas else pd.DataFrame()
        _freq_aba = next(
            (a for a in abas
             if a.strip().lower().replace("ê", "e").replace("é", "e") in ("frequencia", "freq")),
            None,
        )
        if _freq_aba:
            _df_freq_raw = pd.read_excel(xls, sheet_name=_freq_aba, header=0)
            _cols_lower = [str(c).lower() for c in _df_freq_raw.columns]
            if not any("aluno" in c or "nome" in c for c in _cols_lower):
                # Tentar cabeçalho na linha 2
                _df_freq_raw2 = pd.read_excel(xls, sheet_name=_freq_aba, header=1)
                _cols2 = [str(c).lower() for c in _df_freq_raw2.columns]
                if any("aluno" in c or "nome" in c for c in _cols2):
                    _df_freq_raw = _df_freq_raw2
            df_freq = _df_freq_raw
        else:
            df_freq = pd.DataFrame()
        df_turm = pd.read_excel(xls, sheet_name="Turmas", skiprows=1) if "Turmas" in abas else pd.DataFrame()
        df_feri = pd.read_excel(xls, sheet_name="Feriados", skiprows=1) if "Feriados" in abas else pd.DataFrame()
        return df_aval, df_aluno, df_rec, df_freq, df_turm, df_feri, "local"
    except FileNotFoundError:
        st.error("⚠️ Planilha não encontrada. Configure o SHEET_ID ou coloque 'planilha_notas.xlsx' na pasta.")
        st.stop()
