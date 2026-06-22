import io
from datetime import datetime
from typing import List, Dict, Any, Optional
import pandas as pd
import streamlit as st

from config import (
    FREQ_MINIMA_PCT, NOTA_MINIMA, NOTA_MINIMA_VETOR,
    PESOS_INSTRUMENTOS, PESOS_VETORES, SEQUENCIA_CRITICA_MIN,
)
from utils import coluna_criterio


def obter_datas_validas(
    turma_nome: str,
    df_turmas: pd.DataFrame,
    df_base: pd.DataFrame,
    df_freq: pd.DataFrame,
    df_feriados: list
) -> list:
    datas_globais = []
    if df_turmas is not None and not df_turmas.empty and "Turma" in df_turmas.columns:
        _turmas_limpas = df_turmas.copy()
        _turmas_limpas["_Turma_lower"] = _turmas_limpas["Turma"].astype(str).str.strip().str.lower()
        _t_lower = str(turma_nome).strip().lower()
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
                datas_globais = [d for d in pd.date_range(d_ini, limite_fim).normalize() if d.dayofweek in dias_validos]
                
    if not datas_globais:
        todas_dr = []
        if df_base is not None and not df_base.empty and "Data" in df_base.columns:
            todas_dr.extend(pd.to_datetime(df_base["Data"], errors="coerce", dayfirst=True).dropna().dt.normalize().tolist())
        if df_freq is not None and not df_freq.empty and "Data" in df_freq.columns:
            todas_dr.extend(pd.to_datetime(df_freq["Data"], errors="coerce", dayfirst=True).dropna().dt.normalize().tolist())
        if todas_dr:
            d_i = min(todas_dr)
            d_f = pd.Timestamp.today().normalize()
            datas_globais = [d for d in pd.date_range(d_i, d_f).normalize() if d.dayofweek in [0, 1, 2, 3, 4]]
            
    if df_feriados:
        _feriados_ts = {pd.to_datetime(f, errors="coerce", dayfirst=True).normalize() for f in df_feriados if pd.notna(f)}
        _feriados_ts = {f for f in _feriados_ts if pd.notna(f)}
        datas_globais = [d for d in datas_globais if d.normalize() not in _feriados_ts]
        
    return sorted(datas_globais)


#------------------------------------Novo-----------------------------
def _montar_calendario_aluno(
    df_freq: pd.DataFrame,
    aluno_sel: str,
    datas_globais: list,
    df_feriados: list = None,
) -> pd.DataFrame:
    """
    Monta o calendário completo de presença/falta/feriado do aluno para um
    conjunto de datas letivas. Centraliza a lógica que antes vivia só dentro
    de _tab_frequencia(), para que outras abas (ex: geração de PDF) também
    possam usá-la sem duplicar código.

    Retorna um DataFrame com colunas: Data, Status, Presente, Aluno.
    Vazio se não houver datas válidas.
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

    feriados_validos  = {d for d in feriados_set if min_d <= d <= max_d}
    datas_calendario  = sorted(list(todas_datas_ts | feriados_validos))

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
 #------------------------------------Novo-----------------------------
print("=" * 80)
def calcular_frequencia_aluno(df_freq: pd.DataFrame, aluno: str, datas_globais: list = None) -> dict:
    vazio = {
        "tem_dados": False,
        "pct_presenca": None, "total_dias": 0, "faltas": 0,
        "faltas_justificadas": 0, "faltas_injustificadas": 0,
        "faltas_restantes": None, "status": "sem_dados",
        "cor": "#9CA3AF", "emoji": "⬜",
        "padrao_seg_sex": False, "pct_seg_sex": 0,
        "faltas_seq_atual": 0, "faltas_seq_datas": [], "faltas_seq_max": 0,
    }

    if datas_globais is not None and len(datas_globais) > 0:
        datas_aulas = sorted(datas_globais)
    else:
        if df_freq is None or df_freq.empty or "Data" not in df_freq.columns:
            return vazio
        datas_aulas = sorted(pd.to_datetime(df_freq["Data"], errors="coerce", dayfirst=True).dropna().dt.normalize().unique())

    total_dias = len(datas_aulas)
    if total_dias == 0:
        return vazio

    df_al = df_freq[df_freq["Aluno"].astype(str).str.strip().str.lower() == str(aluno).strip().lower()].copy() if (df_freq is not None and not df_freq.empty and "Aluno" in df_freq.columns) else pd.DataFrame()

    if not df_al.empty and "Presente" in df_al.columns:
        pres_bool = df_al["Presente"].apply(
            lambda x: True if str(x).strip().lower() in ['v', 'verdadeiro', 'true', 'presente', 'p', '1', 'sim', 's']
            else (True if isinstance(x, bool) and x else False)
        )
        df_faltas = df_al[~pres_bool].copy()
    else:
        df_faltas = df_al.copy()

    if not df_faltas.empty and "Data" in df_faltas.columns:
        df_faltas["Data"] = pd.to_datetime(df_faltas["Data"], errors="coerce", dayfirst=True).dt.normalize()
        df_faltas = df_faltas[df_faltas["Data"].isin(datas_aulas)]

    faltas = len(df_faltas)
    presencas = total_dias - faltas
    if presencas < 0:
        presencas = 0
        faltas = total_dias

    pct = (presencas / total_dias * 100) if total_dias > 0 else 100.0

    faltas_just = 0
    if not df_faltas.empty and "Tipo" in df_faltas.columns:
        faltas_just = int((df_faltas["Tipo"].str.lower().str.strip().isin(["justificada", "j", "just", "atestado"])).sum())
    faltas_injust = faltas - faltas_just

    max_faltas = int(total_dias * (1 - FREQ_MINIMA_PCT / 100))
    restantes  = max(0, max_faltas - faltas)

    if pct >= 90:
        status, cor, emoji = "excelente", "#10B981", "🟢"
    elif pct >= FREQ_MINIMA_PCT + 10:
        status, cor, emoji = "adequado",  "#F59E0B", "🟡"
    elif pct >= FREQ_MINIMA_PCT:
        status, cor, emoji = "atencao",   "#F97316", "🟠"
    else:
        status, cor, emoji = "critico",   "#E30613", "🔴"

    if not df_faltas.empty and "Data" in df_faltas.columns:
        dias_falta  = pd.to_datetime(df_faltas["Data"], errors="coerce", dayfirst=True).dt.dayofweek
        pct_seg_sex = ((dias_falta == 0) | (dias_falta == 4)).sum() / len(df_faltas) * 100
    else:
        pct_seg_sex = 0.0
    padrao_seg_sex = pct_seg_sex >= 50 and faltas >= 3

    # ── Faltas consecutivas ────────────────────────────────────────────────────
    seq_atual = 0
    seq_atual_datas: list = []
    datas_falta_set = set(pd.to_datetime(df_faltas["Data"], errors="coerce", dayfirst=True).dt.normalize().dropna().tolist()) if not df_faltas.empty and "Data" in df_faltas.columns else set()

    for d in reversed(datas_aulas):
        if d in datas_falta_set:
            seq_atual += 1
            seq_atual_datas.insert(0, d)
        else:
            break

    seq_max = 0
    seq_c = 0
    for d in datas_aulas:
        if d in datas_falta_set:
            seq_c += 1
            if seq_c > seq_max:
                seq_max = seq_c
        else:
            seq_c = 0

    return {
        "tem_dados":             True,
        "pct_presenca":          round(pct, 1),
        "total_dias":            total_dias,
        "presencas":             presencas,
        "faltas":                faltas,
        "faltas_justificadas":   faltas_just,
        "faltas_injustificadas": faltas_injust,
        "faltas_restantes":      restantes,
        "status":                status,
        "cor":                   cor,
        "emoji":                 emoji,
        "padrao_seg_sex":        padrao_seg_sex,
        "pct_seg_sex":           round(pct_seg_sex, 1),
        "faltas_seq_atual":      seq_atual,        
        "faltas_seq_datas":      seq_atual_datas,  
        "faltas_seq_max":        seq_max,           
    }


def analisar_freq_notas(df_aluno: pd.DataFrame, df_freq_aluno: pd.DataFrame) -> Optional[dict]:
    """Cruza frequência com notas para identificar correlação e impacto."""
    if df_freq_aluno.empty or df_aluno.empty:
        return None
    if "Data" not in df_aluno.columns or "Nota" not in df_aluno.columns:
        return None

    df_n = df_aluno[["Data", "Nota"]].copy()
    df_n["Data"]   = pd.to_datetime(df_n["Data"], errors="coerce", dayfirst=True)
    df_n = df_n.dropna(subset=["Data"])
    df_n["semana"] = df_n["Data"].dt.to_period("W")

    df_f = df_freq_aluno[["Data", "Presente"]].copy()
    df_f["Data"]   = pd.to_datetime(df_f["Data"], errors="coerce", dayfirst=True)
    df_f = df_f.dropna(subset=["Data"])
    df_f["semana"] = df_f["Data"].dt.to_period("W")

    semanas_com_falta         = set(df_f[~df_f["Presente"]]["semana"])
    df_n["teve_falta_semana"] = df_n["semana"].isin(semanas_com_falta)

    media_com_falta = df_n[df_n["teve_falta_semana"]]["Nota"].mean()
    media_sem_falta = df_n[~df_n["teve_falta_semana"]]["Nota"].mean()
    impacto = (
        round(media_com_falta - media_sem_falta, 2)
        if pd.notna(media_com_falta) and pd.notna(media_sem_falta)
        else None
    )

    notas_serie  = df_n.sort_values("Data")[["Data", "Nota"]].copy()
    faltas_datas = df_f[~df_f["Presente"]]["Data"].tolist()

    sem_presenca          = df_f.groupby("semana")["Presente"].mean().reset_index()
    sem_presenca.columns  = ["semana", "pct_presenca"]
    sem_notas             = df_n.groupby("semana")["Nota"].mean().reset_index()
    merged                = sem_presenca.merge(sem_notas, on="semana")

    if len(merged) >= 3:
        corr = merged["pct_presenca"].corr(merged["Nota"])
        if pd.isna(corr):
            corr_label, corr_cor = "indefinida", "#9CA3AF"
        elif corr >= 0.6:
            corr_label, corr_cor = f"Forte positiva ({corr:.2f})", "#10B981"
        elif corr >= 0.3:
            corr_label, corr_cor = f"Moderada ({corr:.2f})", "#F59E0B"
        elif corr >= 0:
            corr_label, corr_cor = f"Fraca ({corr:.2f})", "#9CA3AF"
        else:
            corr_label, corr_cor = f"Negativa ({corr:.2f})", "#6366F1"
    else:
        corr_label, corr_cor = "Poucos dados", "#9CA3AF"

    return {
        "media_com_falta": round(media_com_falta, 2) if pd.notna(media_com_falta) else None,
        "media_sem_falta": round(media_sem_falta, 2) if pd.notna(media_sem_falta) else None,
        "impacto":         impacto,
        "notas_serie":     notas_serie,
        "faltas_datas":    faltas_datas,
        "corr_label":      corr_label,
        "corr_cor":        corr_cor,
    }


@st.cache_data(ttl=120)
def calcular_ranking(df_hash: str, df_json: str) -> pd.DataFrame:
    df_base = pd.read_json(io.StringIO(df_json))
    return (
        df_base.groupby("Aluno")["Nota"]
        .mean().reset_index().rename(columns={"Nota": "Média"})
        .sort_values("Média", ascending=False).reset_index(drop=True)
    )


_COL_INSTR = "Instrumento / Atividade"


def _nota_vetor(df_vetor: pd.DataFrame, vetor_nome: str) -> float:
    pesos_instr = PESOS_INSTRUMENTOS.get(vetor_nome, {})
    if not pesos_instr or _COL_INSTR not in df_vetor.columns:
        return df_vetor["Nota"].mean()

    medias = df_vetor.groupby(_COL_INSTR)["Nota"].mean()

    presentes = {i: p for i, p in pesos_instr.items() if i in medias.index}
    if not presentes:
        return df_vetor["Nota"].mean()  

    total_peso = sum(presentes.values())
    return sum(medias[i] * (p / total_peso) for i, p in presentes.items())


def _pesos_vetores_efetivos() -> dict:
    """Retorna pesos customizados do session_state (se válidos) ou os padrões do config."""
    try:
        custom = st.session_state.get("pesos_vetores_custom")
        if custom and isinstance(custom, dict) and abs(sum(custom.values()) - 1.0) < 0.01:
            return custom
    except Exception:
        pass
    return PESOS_VETORES


def calcular_notas_por_vetor(df_aluno: pd.DataFrame) -> Dict[str, float]:
    if "Vetor (Peso)" not in df_aluno.columns:
        return {}
    _pv = _pesos_vetores_efetivos()
    return {
        vetor: round(_nota_vetor(df_aluno[df_aluno["Vetor (Peso)"] == vetor].dropna(subset=["Nota"]), vetor), 2)
        for vetor in _pv
        if not df_aluno[df_aluno["Vetor (Peso)"] == vetor].empty
    }


def calcular_media_ponderada(df_aluno: pd.DataFrame) -> float:
    if "Vetor (Peso)" not in df_aluno.columns:
        return df_aluno["Nota"].mean()
    _pv = _pesos_vetores_efetivos()
    total_peso = soma_pond = 0.0
    for vetor, peso in _pv.items():
        sub = df_aluno[df_aluno["Vetor (Peso)"] == vetor].dropna(subset=["Nota"])
        if not sub.empty:
            soma_pond  += _nota_vetor(sub, vetor) * peso
            total_peso += peso
    return soma_pond / total_peso if total_peso > 0 else df_aluno["Nota"].mean()


def detectar_tendencia(df_aluno: pd.DataFrame, janela: int = 5) -> str:
    df_sorted = df_aluno.copy()
    df_sorted["Data_dt"] = pd.to_datetime(df_sorted["Data"], errors="coerce", dayfirst=True)
    serie = df_sorted.dropna(subset=["Data_dt"]).sort_values("Data_dt")["Nota"].tail(janela * 2)
    
    if len(serie) < 4:
        return "indefinida"
    metade = len(serie) // 2
    diff   = serie.iloc[metade:].mean() - serie.iloc[:metade].mean()
    if diff > 0.5:  return "melhora"
    if diff < -0.5: return "queda"
    return "estável"


def detectar_sequencia_critica(df_aluno: pd.DataFrame, minimo: int = SEQUENCIA_CRITICA_MIN) -> int:
    df_sorted = df_aluno.copy()
    df_sorted["Data_dt"] = pd.to_datetime(df_sorted["Data"], errors="coerce", dayfirst=True)
    notas = df_sorted.dropna(subset=["Data_dt"]).sort_values("Data_dt")["Nota"].tolist()
    
    seq = 0
    for n in reversed(notas):
        if n < NOTA_MINIMA:
            seq += 1
        else:
            break
    return seq if seq >= minimo else 0


def classificar_risco(
    media: float, notas_baixas: int, total: int, seq: int,
    notas_por_vetor: Optional[dict] = None,
) -> str:
    if notas_por_vetor and any(n < NOTA_MINIMA_VETOR for n in notas_por_vetor.values()):
        return "critico"
    pct_baixas = notas_baixas / total if total > 0 else 0
    if media < NOTA_MINIMA or seq >= SEQUENCIA_CRITICA_MIN or pct_baixas > 0.40:
        return "critico"
    if media < 7.0 or pct_baixas > 0.20:
        return "atencao"
    if media >= 8.5 and notas_baixas == 0:
        return "excelente"
    return "adequado"


@st.cache_data(ttl=120)
def calcular_perfil_turma(df_hash: str, df_json: str) -> pd.DataFrame:
    df_t = pd.read_json(io.StringIO(df_json))
    df_t["Data"] = pd.to_datetime(df_t["Data"], errors="coerce")
    df_t["Nota"] = pd.to_numeric(df_t["Nota"], errors="coerce")

    rows = []
    for aluno, grp in df_t.groupby("Aluno"):
        media_pond   = calcular_media_ponderada(grp)
        media_simples = grp["Nota"].mean()
        notas_baixas = int((grp["Nota"] < NOTA_MINIMA).sum())
        total        = len(grp)
        notas_ord    = grp.sort_values("Data")["Nota"].tolist()
        seq = 0
        for n in reversed(notas_ord):
            if n < NOTA_MINIMA:
                seq += 1
            else:
                break
        seq   = seq if seq >= SEQUENCIA_CRITICA_MIN else 0
        serie = grp.sort_values("Data")["Nota"].tail(10)
        tend  = "indefinida"
        if len(serie) >= 4:
            metade = len(serie) // 2
            diff   = serie.iloc[metade:].mean() - serie.iloc[:metade].mean()
            tend   = "melhora" if diff > 0.5 else ("queda" if diff < -0.5 else "estável")
        notas_vetor = calcular_notas_por_vetor(grp)
        risco = classificar_risco(media_pond, notas_baixas, total, seq, notas_vetor)
        rows.append({
            "Aluno": aluno, "Média": round(media_pond, 2),
            "Média_Simples": round(media_simples, 2),
            "Notas_Baixas": notas_baixas, "Total": total,
            "Seq_Critica": seq, "Tendencia": tend, "Risco": risco,
        })

    ordem = {"critico": 0, "atencao": 1, "adequado": 2, "excelente": 3}
    return (
        pd.DataFrame(rows)
        .assign(_ordem=lambda d: d["Risco"].map(ordem))
        .sort_values(["_ordem", "Média"])
        .drop(columns="_ordem")
        .reset_index(drop=True)
    )


def gerar_diagnostico(
    aluno: str, media: float, media_pond: float, tendencia: str,
    notas_baixas: int, total_avals: int, seq_critica: int, delta_turma: float,
    posicao: Optional[int], total_alunos: int, bimestres: pd.DataFrame, df_al: pd.DataFrame,
) -> dict:
    partes = []
    resumo = []   
    tags = []
    nome = aluno.split()[0]

    df_sorted_diag = df_al.copy()
    df_sorted_diag["Data_dt"] = pd.to_datetime(df_sorted_diag["Data"], errors="coerce", dayfirst=True)
    df_sorted_diag = df_sorted_diag.dropna(subset=["Data_dt"]).sort_values("Data_dt")
    notas_lista = df_sorted_diag["Nota"].tolist()

    vetores_info = calcular_notas_por_vetor(df_al)
    risco = classificar_risco(media, notas_baixas, total_avals, seq_critica, vetores_info)

    sit_map = {
        "critico":   "está em situação crítica",
        "atencao":   "requer atenção pedagógica",
        "adequado":  "apresenta desempenho adequado",
        "excelente": "tem desempenho excelente",
    }
    frase_abertura = f"{nome} {sit_map[risco]}, com média simples {media:.1f} e média ponderada {media_pond:.1f}."
    partes.append(frase_abertura)
    resumo.append(frase_abertura)   

    gap = round(media_pond - media, 2)
    if abs(gap) >= 0.4:
        if gap > 0:
            partes.append(f"A ponderação favorece o aluno (+{gap:.1f} pt acima da média simples), indicando melhor aproveitamento nos instrumentos de maior peso.")
            tags.append(("Ponderada favorável", "positivo"))
        else:
            partes.append(f"A ponderação penaliza o desempenho ({gap:.1f} pt abaixo da média simples), sinalizando dificuldade justamente nos instrumentos mais importantes.")
            tags.append(("Ponderada desfavorável", "negativo"))

    if posicao and total_alunos >= 3:
        pct_pos = posicao / total_alunos
        if pct_pos <= 0.10:
            tier, tier_tag, tier_icon = "Top 10%", "positivo", "🏆"
        elif pct_pos <= 0.25:
            tier, tier_tag, tier_icon = "Top 25%", "positivo", "🏆"
        elif pct_pos <= 0.50:
            tier, tier_tag, tier_icon = "Metade superior", "positivo", "↑"
        elif pct_pos <= 0.75:
            tier, tier_tag, tier_icon = "Faixa intermediária", "neutro", "—"
        elif pct_pos <= 0.90:
            tier, tier_tag, tier_icon = "Bottom 25%", "negativo", "⚠️"
        else:
            tier, tier_tag, tier_icon = "Bottom 10%", "negativo", "⚠️"
        frase_pos = f"Ocupa a {posicao}ª posição entre {total_alunos} alunos ({tier.lower()} da turma)."
        partes.append(frase_pos)
        resumo.append(frase_pos)
        tags.append((f"{tier_icon} {tier} da turma", tier_tag))

    if abs(delta_turma) >= 0.3:
        sinal = "acima" if delta_turma > 0 else "abaixo"
        pts = f"{abs(delta_turma):.1f} ponto{'s' if abs(delta_turma) >= 2 else ''}"
        partes.append(f"Está {pts} {sinal} da média da turma.")
        tags.append((f"{'▲' if delta_turma > 0 else '▼'} {abs(delta_turma):.1f} vs turma", "positivo" if delta_turma > 0 else "negativo"))

    if total_avals >= 4:
        std = pd.Series(notas_lista).std()
        if std < 1.0:
            partes.append(f"O desempenho é muito consistente (σ={std:.1f}) — pouca variação entre avaliações, comportamento previsível.")
            tags.append(("Consistente", "positivo"))
        elif std > 2.5:
            partes.append(f"O desempenho é bastante irregular (σ={std:.1f}): as notas oscilam muito, o que pode indicar instabilidade, faltas em datas de avaliação ou dificuldades pontuais.")
            tags.append(("Irregular", "negativo"))

    tend_map = {
        "melhora":    "mostra tendência clara de melhora nas últimas avaliações",
        "queda":      "apresenta tendência de queda recente que merece atenção",
        "estável":    "mantém desempenho estável ao longo do tempo",
        "indefinida": "tem avaliações insuficientes para análise de tendência confiável",
    }
    frase_tend = f"{nome} {tend_map[tendencia]}."
    partes.append(frase_tend)
    resumo.append(frase_tend)       
    tags.append({"melhora": ("↑ Tendência positiva", "positivo"), "queda": ("↓ Tendência negativa", "negativo"), "estável": ("→ Estável", "neutro"), "indefinida": ("Dados insuficientes", "neutro")}[tendencia])

    aceleracao = None
    if len(notas_lista) >= 3:
        _alpha = 2.0 / (3 + 1)
        _ema = [notas_lista[0]]
        for _v in notas_lista[1:]:
            _ema.append(_alpha * _v + (1 - _alpha) * _ema[-1])
        _diff_now  = notas_lista[-1] - _ema[-1]
        _diff_prev = notas_lista[-2] - _ema[-2]
        if _diff_now >= 0.5 and _diff_now > _diff_prev:
            aceleracao = "aceleração"
            tags.append(("⚡ Aceleração", "positivo"))
        elif _diff_now <= -0.5 and _diff_now < _diff_prev:
            aceleracao = "desaceleração"
            tags.append(("📉 Desaceleração", "negativo"))
            partes.append(f"Atenção: a última avaliação ({notas_lista[-1]:.1f}) está {abs(_diff_now):.1f} pt abaixo do ritmo médio esperado — possível desaceleração.")

    if total_avals >= 6:
        meio = len(notas_lista) // 2
        media_antiga  = sum(notas_lista[:meio]) / meio
        media_recente = sum(notas_lista[meio:]) / (len(notas_lista) - meio)
        delta_hist = round(media_recente - media_antiga, 1)
        if delta_hist >= 1.0 and tendencia != "queda":
            partes.append(f"No comparativo histórico, {nome} evoluiu {delta_hist:.1f} pt da primeira ({media_antiga:.1f}) para a segunda metade do período ({media_recente:.1f}).")
            tags.append(("Evolução histórica", "positivo"))
        elif delta_hist <= -1.0 and tendencia != "melhora":
            partes.append(f"No comparativo histórico, a média recuou {abs(delta_hist):.1f} pt em relação ao início do período ({media_antiga:.1f} → {media_recente:.1f}).")
            tags.append(("Recuo histórico", "negativo"))

    if seq_critica >= SEQUENCIA_CRITICA_MIN:
        nivel = "ALERTA GRAVE" if seq_critica >= 5 else "ALERTA"
        acao  = "Risco elevado de reprovação — intervenção imediata necessária." if seq_critica >= 5 else "Intervenção pedagógica recomendada."
        frase_seq = f"{nivel}: {seq_critica} avaliações consecutivas abaixo de {NOTA_MINIMA:.0f}. {acao}"
        partes.append(frase_seq)
        resumo.append(frase_seq)    
        tags.append((f"⚠ {seq_critica}× seguidas críticas", "negativo"))
    elif notas_baixas == 0:
        frase_ok = "Nenhuma nota crítica no período — mantém aproveitamento consistentemente acima do mínimo."
        partes.append(frase_ok)
        resumo.append(frase_ok)     
        tags.append(("Sem notas críticas", "positivo"))
    else:
        pct_baixas = notas_baixas / total_avals * 100
        tag_adicionada = False
        if total_avals >= 4:
            criticas_recentes = sum(1 for n in notas_lista[-3:] if n < NOTA_MINIMA)
            criticas_antigas  = sum(1 for n in notas_lista[:-3]  if n < NOTA_MINIMA)
            if criticas_recentes >= 2:
                frase_nc = f"Possui {notas_baixas} nota(s) crítica(s) ({pct_baixas:.0f}% do total), com concentração recente: {criticas_recentes} das últimas 3 avaliações abaixo do mínimo."
                partes.append(frase_nc)
                resumo.append(frase_nc)  
            elif criticas_antigas > 0 and criticas_recentes == 0:
                frase_rec = f"Teve {notas_baixas} nota(s) crítica(s) no histórico, mas as 3 avaliações mais recentes estão todas acima do mínimo — sinal positivo de recuperação."
                partes.append(frase_rec)
                resumo.append(frase_rec)  
                tags.append(("Recuperando-se", "positivo"))
                tag_adicionada = True
            else:
                partes.append(f"Possui {notas_baixas} nota(s) crítica(s), representando {pct_baixas:.0f}% das avaliações.")
        else:
            partes.append(f"Possui {notas_baixas} nota(s) crítica(s) ({pct_baixas:.0f}% das avaliações).")
        if not tag_adicionada:
            tags.append((f"{notas_baixas} nota(s) crítica(s)", "negativo" if pct_baixas > 30 else "neutro"))

    col_crit_d = coluna_criterio(df_al)
    if col_crit_d in df_al.columns and df_al[col_crit_d].nunique() >= 2:
        med_crit      = df_al.groupby(col_crit_d)["Nota"].mean()
        melhor        = med_crit.idxmax()
        pior          = med_crit.idxmin()
        gap_crit      = round(med_crit[melhor] - med_crit[pior], 1)
        n_crit_abaixo = int((med_crit < NOTA_MINIMA).sum())

        if melhor != pior:
            if gap_crit >= 3.0:
                partes.append(f"Há disparidade expressiva entre critérios: de {med_crit[pior]:.1f} em '{pior[:28]}' até {med_crit[melhor]:.1f} em '{melhor[:28]}' (gap de {gap_crit:.1f} pt) — ponto de atenção específico.")
            else:
                partes.append(f"Melhor desempenho em '{melhor[:28]}' ({med_crit[melhor]:.1f}) e maior dificuldade em '{pior[:28]}' ({med_crit[pior]:.1f}).")
            tags.append((f"✓ {melhor[:20]}", "positivo"))
            tags.append((f"✗ {pior[:20]}", "negativo"))

        if n_crit_abaixo >= 2:
            partes.append(f"{n_crit_abaixo} critério(s) com média abaixo do mínimo — indica dificuldades amplas, não isoladas.")
            tags.append((f"{n_crit_abaixo} critérios abaixo", "negativo"))

        df_al_sc = df_al.copy()
        df_al_sc["Data_dt"] = pd.to_datetime(df_al_sc["Data"], errors="coerce", dayfirst=True)
        df_al_sc = df_al_sc.dropna(subset=["Data_dt"]).sort_values("Data_dt")
        quedas_crit: dict = {}
        for _c, _grp in df_al_sc.groupby(col_crit_d):
            _nl = list(_grp["Nota"])
            if len(_nl) >= 4:
                _med_rec  = sum(_nl[-3:]) / 3
                _med_hist = sum(_nl[:-3]) / (len(_nl) - 3)
                quedas_crit[_c] = round(_med_hist - _med_rec, 1)
        if quedas_crit:
            _crit_queda = max(quedas_crit, key=quedas_crit.get)
            _delta_q    = quedas_crit[_crit_queda]
            if _delta_q >= 1.0:
                _med_h = med_crit.get(_crit_queda, 0) if hasattr(med_crit, "get") else med_crit[_crit_queda]
                partes.append(f"Queda recente notável no critério '{_crit_queda[:30]}': média histórica {_med_h:.1f} pt vs últimas 3 avaliações {_med_h - _delta_q:.1f} pt ({_delta_q:+.1f} pt).")
                tags.append((f"↘ {_crit_queda[:18]}", "negativo"))

    if len(vetores_info) >= 2:
        vet_abaixo = {v: n for v, n in vetores_info.items() if n < NOTA_MINIMA_VETOR}
        melhor_vet = max(vetores_info, key=vetores_info.get)
        pior_vet   = min(vetores_info, key=vetores_info.get)
        gap_vet    = round(vetores_info[melhor_vet] - vetores_info[pior_vet], 1)

        _vt = lambda v: v.split(" (")[0]
        if vet_abaixo:
            lista = ", ".join(f"'{v}' ({n:.1f})" for v, n in vet_abaixo.items())
            partes.append(f"Vetor(es) abaixo do mínimo individual: {lista}. Isso pode gerar reprovação independentemente da média geral.")
            for v, n in vet_abaixo.items():
                tags.append((f"🔻 {_vt(v)}: {n:.1f}", "negativo"))
        elif gap_vet >= 1.5:
            partes.append(f"Dentre os vetores, destaca-se em '{melhor_vet}' ({vetores_info[melhor_vet]:.1f}) mas precisa desenvolver '{pior_vet}' ({vetores_info[pior_vet]:.1f}).")
            tags.append((f"✅ {_vt(melhor_vet)}: {vetores_info[melhor_vet]:.1f}", "positivo"))
            tags.append((f"🔻 {_vt(pior_vet)}: {vetores_info[pior_vet]:.1f}", "negativo" if vetores_info[pior_vet] < NOTA_MINIMA_VETOR + 1 else "neutro"))

    col_periodo = "Semana" if "Semana" in bimestres.columns else ("Bimestre" if "Bimestre" in bimestres.columns else None)
    if col_periodo and len(bimestres) >= 3:
        delta_ev   = round(bimestres["Média"].iloc[-1] - bimestres["Média"].iloc[0], 1)
        idx_melhor = bimestres["Média"].idxmax()
        idx_pior   = bimestres["Média"].idxmin()
        label_m    = bimestres.loc[idx_melhor, col_periodo]
        label_p    = bimestres.loc[idx_pior,   col_periodo]
        if abs(delta_ev) >= 0.8:
            direcao = "cresceu" if delta_ev > 0 else "caiu"
            partes.append(f"Ao longo do período, a média {direcao} {abs(delta_ev):.1f} pt ({bimestres['Média'].iloc[0]:.1f} → {bimestres['Média'].iloc[-1]:.1f}). Pico em {label_m} ({bimestres.loc[idx_melhor, 'Média']:.1f}) e pior semana em {label_p} ({bimestres.loc[idx_pior, 'Média']:.1f}).")

    projecao = None
    if total_avals >= 5:
        if media_pond >= 8.5:
            projecao = "aprovado_folga"
        elif media_pond >= 7.0:
            projecao = "aprovado_margem"
        elif media_pond >= NOTA_MINIMA:
            projecao = "aprovado_risco"
        else:
            projecao = "reprovado"

    return {
        "texto":          " ".join(partes),
        "texto_resumido": " ".join(resumo),
        "tags":           tags,
        "risco":          risco,
        "projecao":       projecao,
        "aceleracao":     aceleracao,
    }


def calcular_saude_turma(df_turma: pd.DataFrame, perfil: pd.DataFrame) -> dict:
    """Calcula indicadores de saúde coletiva da turma para o painel diagnóstico."""
    if df_turma.empty or perfil.empty:
        return {}

    n_total     = len(perfil)
    n_aprovados = int(perfil["Risco"].isin(["adequado", "excelente"]).sum())
    n_em_risco  = int(perfil["Risco"].isin(["critico", "atencao"]).sum())
    pct_aprovados = round(n_aprovados / n_total * 100, 1) if n_total > 0 else 0.0

    col_crit = coluna_criterio(df_turma)
    criterios_sistemicos: list = []
    criterio_mais_problematico = None
    pct_abaixo_criterio = 0.0

    if col_crit in df_turma.columns:
        _todos_crits = df_turma[col_crit].dropna().unique()
        # Conta um aluno como "em dificuldade" no critério apenas se a MÉDIA dele
        # nesse critério ficar abaixo do mínimo — assim uma única nota baixa entre
        # várias avaliações não classifica o aluno (nem o critério) como problemático.
        _med_aluno_crit = (
            df_turma.dropna(subset=[col_crit])
            .groupby([col_crit, "Aluno"])["Nota"].mean()
            .reset_index()
        )
        _total_por_crit  = _med_aluno_crit.groupby(col_crit)["Aluno"].nunique()
        _abaixo_por_crit = (
            _med_aluno_crit[_med_aluno_crit["Nota"] < NOTA_MINIMA]
            .groupby(col_crit)["Aluno"].nunique()
        )
        _rows = []
        for _ct in _todos_crits:
            _tot = int(_total_por_crit.get(_ct, 0))
            _n   = int(_abaixo_por_crit.get(_ct, 0))
            _pct = round(_n / _tot * 100, 1) if _tot > 0 else 0.0
            _rows.append({col_crit: _ct, "pct_abaixo": _pct})
        if _rows:
            crit_df = pd.DataFrame(_rows).sort_values("pct_abaixo", ascending=False)
            criterios_sistemicos = crit_df[[col_crit, "pct_abaixo"]].to_dict("records")
            criterio_mais_problematico = crit_df.iloc[0][col_crit]
            pct_abaixo_criterio = float(crit_df.iloc[0]["pct_abaixo"])

    vetor_mais_fraco     = None
    media_vetor_mais_fraco = None
    if "Vetor (Peso)" in df_turma.columns:
        mv = df_turma.groupby("Vetor (Peso)")["Nota"].mean()
        if not mv.empty:
            vetor_mais_fraco       = mv.idxmin()
            media_vetor_mais_fraco = round(float(mv.min()), 2)

    tendencia_coletiva = "indefinida"
    df_s = df_turma.copy()
    df_s["Data_dt"] = pd.to_datetime(df_s["Data"], errors="coerce", dayfirst=True)
    df_s = df_s.dropna(subset=["Data_dt"]).sort_values("Data_dt")
    if not df_s.empty:
        serie_diaria = df_s.groupby("Data_dt")["Nota"].mean()
        if len(serie_diaria) >= 4:
            metade = len(serie_diaria) // 2
            diff   = serie_diaria.iloc[metade:].mean() - serie_diaria.iloc[:metade].mean()
            tendencia_coletiva = "melhora" if diff > 0.3 else ("queda" if diff < -0.3 else "estável")

    return {
        "n_total":                    n_total,
        "n_aprovados":                n_aprovados,
        "n_em_risco":                 n_em_risco,
        "pct_aprovados":              pct_aprovados,
        "criterio_mais_problematico": criterio_mais_problematico,
        "pct_abaixo_criterio":        pct_abaixo_criterio,
        "vetor_mais_fraco":           vetor_mais_fraco,
        "media_vetor_mais_fraco":     media_vetor_mais_fraco,
        "tendencia_coletiva":         tendencia_coletiva,
        "criterios_sistemicos":       criterios_sistemicos,
        "col_crit":                   col_crit,
    }


def agrupar_por_semana(df_aluno: pd.DataFrame) -> pd.DataFrame:
    df = df_aluno.copy()
    df["Data_dt"] = pd.to_datetime(df["Data"], errors="coerce", dayfirst=True)
    df = df.dropna(subset=["Data_dt"])
    df["Semana"] = df["Data_dt"].apply(lambda d: f"{d.isocalendar().year}-S{d.isocalendar().week:02d}")
    return (
        df.groupby("Semana")["Nota"]
        .agg(Média="mean", Total="count", Abaixo_Min=lambda x: (x < NOTA_MINIMA).sum())
        .reset_index().sort_values("Semana")
    )


def enriquecer_perfil_ia(
    perfil: pd.DataFrame,
    df_turma: pd.DataFrame,
    df_freq: pd.DataFrame,
    turma_sel: str = None,
    df_turmas: pd.DataFrame = None,
    df_feriados: list = None,
) -> List[Dict[str, Any]]:
    """Enriquece o perfil da turma com detalhes por aluno para uso na análise IA."""
    col_crit    = coluna_criterio(df_turma)
    media_geral = df_turma["Nota"].mean()
    total_alunos_turma = df_turma["Aluno"].nunique()
    perfis      = []

    _obs_genericas = set()
    _col_obs_turma = "Observação" if "Observação" in df_turma.columns else None
    if _col_obs_turma and total_alunos_turma > 0:
        _df_obs_geral = df_turma[[_col_obs_turma, "Aluno"]].copy()
        _df_obs_geral["_txt"] = _df_obs_geral[_col_obs_turma].fillna("").astype(str).str.strip()
        _df_obs_geral = _df_obs_geral[_df_obs_geral["_txt"].str.len() > 3]
        _obs_por_aluno = _df_obs_geral.groupby("_txt")["Aluno"].nunique()
        _limiar = max(2, int(total_alunos_turma * 0.30))  
        _obs_genericas = set(_obs_por_aluno[_obs_por_aluno >= _limiar].index)

    _dg_cache = {}
    aluno_turma_map = df_turma.set_index("Aluno")["Turma"].to_dict() if "Turma" in df_turma.columns else {}
    
    def _get_dg(t_nome):
        if t_nome not in _dg_cache:
            _dg_cache[t_nome] = obter_datas_validas(t_nome, df_turmas, df_turma, df_freq, df_feriados)
        return _dg_cache[t_nome]

    for _, row in perfil.iterrows():
        nome     = row["Aluno"]
        df_al    = df_turma[df_turma["Aluno"] == nome]

        melhor_crit = pior_crit = melhor_media = pior_media = None
        if col_crit in df_al.columns and df_al[col_crit].nunique() >= 2:
            med_c        = df_al.groupby(col_crit)["Nota"].mean()
            melhor_crit  = med_c.idxmax()
            pior_crit    = med_c.idxmin()
            melhor_media = round(med_c.max(), 1)
            pior_media   = round(med_c.min(), 1)

        vetores_info = {}
        if "Vetor (Peso)" in df_al.columns:
            for v in ["Fazer (40%)", "Saber (30%)", "Comport. (30%)"]:
                sub = df_al[df_al["Vetor (Peso)"] == v]["Nota"]
                if not sub.empty:
                    vetores_info[v] = round(sub.mean(), 1)

        df_al_sorted = df_al.copy()
        df_al_sorted["Data_dt"] = pd.to_datetime(df_al_sorted["Data"], errors="coerce", dayfirst=True)
        df_al_sorted = df_al_sorted.dropna(subset=["Data_dt"]).sort_values("Data_dt")

        ultima      = df_al_sorted.iloc[-1] if not df_al_sorted.empty else None
        ultima_nota = round(float(ultima["Nota"]), 1) if ultima is not None else None
        ultima_data = ultima["Data_dt"].strftime("%d/%m/%Y") if ultima is not None else None

        col_obs = "Observação" if "Observação" in df_al.columns else None
        obs_criticas = []
        todas_obs    = []   

        if col_obs:
            df_obs_all = df_al_sorted.copy()
            df_obs_all["_obs_txt"] = df_obs_all[col_obs].fillna("").astype(str).str.strip()
            df_obs_all = df_obs_all[df_obs_all["_obs_txt"].str.len() > 0].copy()
            df_obs_all = df_obs_all[~df_obs_all["_obs_txt"].str.lower().isin(["nan", "none", "-", "—"])]
            df_obs_all = df_obs_all[~df_obs_all["_obs_txt"].isin(_obs_genericas)]

            for _, r in df_obs_all[df_obs_all["Nota"] < NOTA_MINIMA].sort_values("Data_dt", ascending=False).head(3).iterrows():
                obs_criticas.append({
                    "nota":       round(float(r["Nota"]), 1),
                    "criterio":   str(r.get(col_crit, ""))[:40] if col_crit and col_crit in r.index else "",
                    "observacao": r["_obs_txt"][:100],
                })

            for _, r in df_obs_all.sort_values("Data_dt", ascending=False).head(4).iterrows():
                todas_obs.append(f"[{r['Nota']:.1f}] {r['_obs_txt'][:100]}")

        t_aluno = aluno_turma_map.get(nome, turma_sel)
        _freq = calcular_frequencia_aluno(df_freq, nome, _get_dg(t_aluno))

        perfis.append({
            "nome":                 nome,
            "media":                 round(row["Média"], 1),
            "risco":                 row["Risco"],
            "tendencia":             row["Tendencia"],
            "notas_baixas":          int(row["Notas_Baixas"]),
            "total_avals":           int(row["Total"]),
            "seq_critica":           int(row["Seq_Critica"]),
            "delta_turma":           round(row["Média"] - media_geral, 2),
            "melhor_crit":           melhor_crit,
            "melhor_media":          melhor_media,
            "pior_crit":             pior_crit,
            "pior_media":            pior_media,
            "vetores":               vetores_info,
            "ultima_nota":           ultima_nota,
            "ultima_data":           ultima_data,
            "obs_notas_criticas":    obs_criticas,
            "todas_observacoes":     todas_obs,
            "frequencia_pct":        _freq.get("pct_presenca"),
            "faltas_injustificadas": int(_freq.get("faltas_injustificadas", 0)),
            "freq_status":           _freq.get("status", "sem_dados"),
            "padrao_seg_sex":        bool(_freq.get("padrao_seg_sex", False)),
        })

    return perfis
