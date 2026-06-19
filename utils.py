import pandas as pd


def coluna_criterio(df: pd.DataFrame) -> str:
    return "Critério Avaliado" if "Critério Avaliado" in df.columns else df.columns[-2]


def coluna_uc(df: pd.DataFrame) -> str:
    return "UC" if "UC" in df.columns else "Unidade Curricular (UC)"


def nota_formatada(valor, fallback: str = "—") -> str:
    return f"{valor:.1f}" if isinstance(valor, (int, float)) and pd.notna(valor) else fallback
