SHEET_ID = "10XkC99eFabuLNH_bmpoKwBW7q5pP6g2Xf8fk3TxD-iE"  # sobrescrito em runtime pelo loader.py via st.secrets

CORES = {
    "azul":     "#00539F",
    "vermelho": "#E30613",
    "cinza":    "#F4F6F9",
    "texto":    "#1A1A2E",
    "amarelo":  "#F59E0B",
    "verde":    "#10B981",
    "roxo":     "#8B5CF6",
}

PESOS_VETORES = {
    "Fazer (40%)":    0.45,
    "Saber (30%)":    0.35,
    "Comport. (30%)": 0.20,
}

# Nível 2: pesos dos instrumentos dentro de cada vetor.
# Regra 4: se um instrumento não foi aplicado, seu peso é redistribuído
# proporcionalmente entre os demais do mesmo vetor (feito em runtime).
PESOS_INSTRUMENTOS: dict[str, dict[str, float]] = {
    "Fazer (40%)": {
        "Projeto Prático":    0.50,
        "Observação Oficina": 0.35,
        "Atividade":          0.15,
    },
    "Saber (30%)": {
        "Prova":              0.60,
        "Apresentação":       0.25,
        "Atividade / Quiz":   0.15,
    },
    "Comport. (30%)": {
        "Observação Oficina": 0.70,
        "Apresentação":       0.30,
    },
}

NOTA_MINIMA           = 6.0
NOTA_MINIMA_VETOR     = 6.0   # cada vetor tem mínimo independente (Regra 1)
SEQUENCIA_CRITICA_MIN = 3

FREQ_MINIMA_PCT     = 75.0
DIAS_SEMANA_LETIVOS = 5
