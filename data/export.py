import io
from datetime import datetime

import pandas as pd


def gerar_excel_turma(
    perfil: pd.DataFrame,
    df_turma: pd.DataFrame,
    df_freq: pd.DataFrame,
    turma_sel: str,
) -> bytes:
    """Gera Excel com ranking, perfil de risco e frequência da turma."""
    from data.analysis import calcular_frequencia_aluno

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:

        # ── Aba 1: Ranking ───────────────────────────────────────────────────
        ranking = perfil[["Aluno", "Média", "Notas_Baixas", "Total", "Seq_Critica", "Tendencia", "Risco"]].copy()
        ranking.columns = ["Aluno", "Média", "Notas Críticas", "Avaliações", "Seq. Crítica", "Tendência", "Risco"]
        ranking = ranking.sort_values("Média", ascending=False).reset_index(drop=True)
        ranking.index += 1
        ranking.index.name = "Posição"
        ranking.to_excel(writer, sheet_name="Ranking")

        # ── Aba 2: Perfil de Risco ────────────────────────────────────────────
        risco_map   = {"critico": "Crítico", "atencao": "Atenção", "adequado": "Adequado", "excelente": "Excelente"}
        tend_map    = {"melhora": "Melhora", "queda": "Queda", "estável": "Estável", "indefinida": "Indefinido"}
        perfil_exp  = perfil.copy()
        perfil_exp["Risco"]     = perfil_exp["Risco"].map(risco_map)
        perfil_exp["Tendencia"] = perfil_exp["Tendencia"].map(tend_map)
        perfil_exp.to_excel(writer, sheet_name="Perfil de Risco", index=False)

        # ── Aba 3: Frequência ────────────────────────────────────────────────
        if not df_freq.empty:
            freq_rows = []
            for nome in perfil["Aluno"]:
                f = calcular_frequencia_aluno(df_freq, nome)
                freq_rows.append({
                    "Aluno":             nome,
                    "Presença %":        f.get("pct_presenca"),
                    "Total Dias":        f.get("total_dias", 0),
                    "Faltas":            f.get("faltas", 0),
                    "F. Justificadas":   f.get("faltas_justificadas", 0),
                    "F. Injustificadas": f.get("faltas_injustificadas", 0),
                    "Faltas Restantes":  f.get("faltas_restantes"),
                    "Status":            f.get("status", "sem_dados"),
                })
            df_freq_exp = pd.DataFrame(freq_rows)
            df_freq_exp.to_excel(writer, sheet_name="Frequência", index=False)

        # ── Aba 4: Histórico completo ────────────────────────────────────────
        hist = df_turma.copy()
        if "Data" in hist.columns:
            hist["Data"] = hist["Data"].dt.strftime("%d/%m/%Y")
        hist.to_excel(writer, sheet_name="Histórico", index=False)

        # ── Aba 5: Resumo ────────────────────────────────────────────────────
        n_crit = (perfil["Risco"] == "critico").sum()
        n_at   = (perfil["Risco"] == "atencao").sum()
        n_adeq = (perfil["Risco"] == "adequado").sum()
        n_exc  = (perfil["Risco"] == "excelente").sum()
        resumo = pd.DataFrame([
            {"Indicador": "Turma",               "Valor": turma_sel},
            {"Indicador": "Gerado em",            "Valor": datetime.now().strftime("%d/%m/%Y %H:%M")},
            {"Indicador": "Total de alunos",      "Valor": len(perfil)},
            {"Indicador": "Média geral",          "Valor": round(df_turma["Nota"].mean(), 2)},
            {"Indicador": "Em risco crítico",     "Valor": int(n_crit)},
            {"Indicador": "Em atenção",           "Valor": int(n_at)},
            {"Indicador": "Adequados",            "Valor": int(n_adeq)},
            {"Indicador": "Excelentes",           "Valor": int(n_exc)},
            {"Indicador": "Taxa de aprovação %",  "Valor": round((n_adeq + n_exc) / len(perfil) * 100, 1) if len(perfil) > 0 else 0},
        ])
        resumo.to_excel(writer, sheet_name="Resumo", index=False)

    buf.seek(0)
    return buf.read()


def gerar_excel(
    aluno: str,
    df_aluno: pd.DataFrame,
    df_turma: pd.DataFrame,
    bimestres: pd.DataFrame,
    df_rec_aluno: pd.DataFrame,
) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df_exp = df_aluno.copy()
        df_exp["Data"] = df_exp["Data"].dt.strftime("%d/%m/%Y")
        df_exp.to_excel(writer, sheet_name="Histórico", index=False)

        bimestres.to_excel(writer, sheet_name="Por Semana", index=False)

        rank = (
            df_turma.groupby("Aluno")["Nota"]
            .mean().reset_index().rename(columns={"Nota": "Média"})
            .sort_values("Média", ascending=False).reset_index(drop=True)
        )
        rank.index += 1
        rank.index.name = "Posição"
        rank.to_excel(writer, sheet_name="Ranking Turma")

        if not df_rec_aluno.empty:
            df_rec_exp = df_rec_aluno.copy()
            for col in ["Data_Orig", "Data_Rec"]:
                if col in df_rec_exp.columns:
                    df_rec_exp[col] = df_rec_exp[col].apply(
                        lambda d: d.strftime("%d/%m/%Y")
                        if pd.notna(d) and hasattr(d, "strftime") else str(d)
                    )
            df_rec_exp.to_excel(writer, sheet_name="Recuperações", index=False)

    buf.seek(0)
    return buf.read()
