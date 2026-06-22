import pandas as pd

_RENAME_AVAL = {
    "data": "Data", "DATA": "Data",
    "Nome do Aluno": "Aluno", "nome do aluno": "Aluno", "aluno": "Aluno", "ALUNO": "Aluno",
    "Unidade Curricular (UC)": "UC", "unidade curricular (uc)": "UC", "Unidade Curricular": "UC",
    "vetor (peso)": "Vetor (Peso)", "VETOR (PESO)": "Vetor (Peso)",
    "instrumento / atividade": "Instrumento / Atividade", "Instrumento": "Instrumento / Atividade",
    "critério avaliado": "Critério Avaliado", "criterio avaliado": "Critério Avaliado",
    "Criterio Avaliado": "Critério Avaliado",
    "nota": "Nota", "NOTA": "Nota",
    "Observação Técnica (Log)": "Observação", "Observação Técnica": "Observação",
    "observação": "Observação", "observacao": "Observação",
    "turma": "Turma", "TURMA": "Turma",
}


def _encontrar_coluna(df: pd.DataFrame, *palavras: str) -> str | None:
    for col in df.columns:
        if any(p in col.lower() for p in palavras):
            return col
    return None


def limpar_avaliacoes(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().lstrip("\ufeff") for c in df.columns]
    df.rename(columns={k: v for k, v in _RENAME_AVAL.items() if k in df.columns}, inplace=True)
    for alvo, palavras in [
        ("Data",      ["data", "date"]),
        ("Aluno",     ["aluno", "nome"]),
        ("Nota",      ["nota"]),
        ("Observação",["observ"]),      # captura "Observação Técnica", "Observação", etc.
    ]:
        if alvo not in df.columns:
            col = _encontrar_coluna(df, *palavras)
            if col:
                df.rename(columns={col: alvo}, inplace=True)
    if "Data" in df.columns:
        df = df[~df["Data"].astype(str).str.contains(r"↑|instrução|exemplo", case=False, na=False)]
        df["Data"] = pd.to_datetime(df["Data"], format="mixed", dayfirst=True, errors="coerce")
    if "Nota" in df.columns:
        df["Nota"] = pd.to_numeric(
            df["Nota"].astype(str).str.replace(",", ".", regex=False),
            errors="coerce",
        )
    df = df.dropna(subset=["Data", "Nota"])

    # Detectar duplicatas: mesmo Aluno + Data + Critério + Vetor
    _chave = [c for c in ["Aluno", "Data", "Critério Avaliado", "Vetor (Peso)"] if c in df.columns]
    if len(_chave) >= 2:
        _n_antes = len(df)
        df = df.drop_duplicates(subset=_chave, keep="last")
        _removidas = _n_antes - len(df)
        if _removidas > 0:
            df.attrs["duplicatas_removidas"] = _removidas

    return df


def limpar_alunos(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    df.columns = [str(c).strip().lstrip("\ufeff") for c in df.columns]
    # Renomeação exata primeiro
    df.rename(columns={"Nome Completo": "Aluno", "Turma / Curso": "Turma"}, inplace=True)
    # Fuzzy fallback
    for alvo, palavras in [("Aluno", ["nome completo", "aluno", "nome"]), ("Turma", ["turma", "curso"])]:
        if alvo not in df.columns:
            col = _encontrar_coluna(df, *palavras)
            if col:
                df.rename(columns={col: alvo}, inplace=True)
    return df


def limpar_recuperacoes(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    df.columns = [str(c).strip().lstrip("\ufeff") for c in df.columns]
    # Renomeação exata
    df.rename(columns={
        "Nome do Aluno": "Aluno", "Data Original": "Data_Orig",
        "Data Recuperação": "Data_Rec", "Nota Original": "Nota_Orig",
        "Nota Recuperação": "Nota_Rec",
    }, inplace=True)
    # Fuzzy fallback para colunas com título mesclado
    for alvo, palavras in [
        ("Data_Orig", ["data original", "data orig"]),
        ("Aluno",     ["aluno", "nome do aluno", "nome"]),
        ("Data_Rec",  ["data recupera", "data rec"]),
        ("Nota_Orig", ["nota original", "nota orig"]),
        ("Nota_Rec",  ["nota recupera", "nota rec"]),
    ]:
        if alvo not in df.columns:
            col = _encontrar_coluna(df, *palavras)
            if col:
                df.rename(columns={col: alvo}, inplace=True)
    for col in ["Data_Orig", "Data_Rec"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], dayfirst=True, errors="coerce")
    for col in ["Nota_Orig", "Nota_Rec"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def limpar_frequencia(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza a aba Frequência. Colunas esperadas:
       Aluno | Data | Presente (Sim/Não/1/0/True/False) | Tipo | Observação
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=["Aluno", "Data", "Presente", "Tipo", "Observacao"])
    df = df.copy()
    df.columns = [str(c).strip().lstrip("\ufeff") for c in df.columns]

    mapa_fuzzy = {
        "Aluno":      ["aluno", "nome"],
        "Data":       ["data", "date"],
        "Presente":   ["presente", "presença", "presenca"],
        "Tipo":       ["tipo"],
        "Observacao": ["observa", "obs"],
    }
    rename_final = {}
    for novo_nome, palavras in mapa_fuzzy.items():
        for col in df.columns:
            col_lower = col.lower()
            if novo_nome not in df.columns and any(p in col_lower for p in palavras):
                rename_final[col] = novo_nome
                break
    df.rename(columns=rename_final, inplace=True)

    if "Data" in df.columns:
        df["Data"] = pd.to_datetime(df["Data"], format="mixed", dayfirst=True, errors="coerce")
    if "Presente" in df.columns:
        mapa = {
            "sim": True, "s": True, "yes": True, "1": True, "1.0": True, "true": True,
            "presente": True, "p": True, "x": True,
            "não": False, "nao": False, "n": False, "no": False,
            "0": False, "0.0": False, "false": False,
            "ausente": False, "a": False, "falta": False,
        }
        df["Presente"] = df["Presente"].astype(str).str.strip().str.lower().map(mapa)
    if "Tipo" not in df.columns:
        df["Tipo"] = "Injustificada"

    def _norm_tipo(v):
        v = str(v).strip().lower() if pd.notna(v) and str(v).strip() else "injustificada"
        if any(x in v for x in ["just", "atestado", "médico", "medico", "licença", "licenca"]):
            return "Justificada"
        return "Injustificada"

    df["Tipo"] = df["Tipo"].apply(_norm_tipo)
    if "Observacao" not in df.columns:
        df["Observacao"] = ""

    colunas_existentes = [c for c in ["Data", "Aluno", "Presente"] if c in df.columns]
    if len(colunas_existentes) < 3:
        return pd.DataFrame(columns=["Aluno", "Data", "Presente", "Tipo", "Observacao"])
    return df.dropna(subset=colunas_existentes)
