"""
Testes das funções puras de data/analysis.py.
Execute com: .venv/Scripts/pytest tests/ -v
"""
import pandas as pd
import pytest

from data.analysis import (
    calcular_media_ponderada,
    calcular_notas_por_vetor,
    classificar_risco,
    detectar_sequencia_critica,
    detectar_tendencia,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _df_notas(notas: list[float], datas: list[str] | None = None) -> pd.DataFrame:
    """Cria um DataFrame mínimo de avaliações para testes."""
    if datas is None:
        datas = [f"2024-01-{i+1:02d}" for i in range(len(notas))]
    return pd.DataFrame({"Nota": notas, "Data": pd.to_datetime(datas)})


def _df_vetores(fazer: list[float], saber: list[float], comp: list[float]) -> pd.DataFrame:
    notas, vetores, datas = [], [], []
    base = pd.Timestamp("2024-01-01")
    for i, n in enumerate(fazer):
        notas.append(n); vetores.append("Fazer (40%)"); datas.append(base + pd.Timedelta(days=i))
    for i, n in enumerate(saber):
        notas.append(n); vetores.append("Saber (30%)"); datas.append(base + pd.Timedelta(days=100 + i))
    for i, n in enumerate(comp):
        notas.append(n); vetores.append("Comport. (30%)"); datas.append(base + pd.Timedelta(days=200 + i))
    return pd.DataFrame({"Nota": notas, "Vetor (Peso)": vetores, "Data": datas})


# ── classificar_risco ─────────────────────────────────────────────────────────

class TestClassificarRisco:
    def test_critico_por_media(self):
        assert classificar_risco(media=5.5, notas_baixas=1, total=5, seq=0) == "critico"

    def test_critico_por_sequencia(self):
        assert classificar_risco(media=7.0, notas_baixas=3, total=10, seq=3) == "critico"

    def test_critico_por_pct_baixas(self):
        # 5 de 10 = 50% > 40%
        assert classificar_risco(media=6.5, notas_baixas=5, total=10, seq=0) == "critico"

    def test_atencao_media_baixa(self):
        assert classificar_risco(media=6.5, notas_baixas=1, total=10, seq=0) == "atencao"

    def test_atencao_pct_baixas(self):
        # 3 de 10 = 30% > 20%
        assert classificar_risco(media=7.5, notas_baixas=3, total=10, seq=0) == "atencao"

    def test_excelente(self):
        assert classificar_risco(media=9.0, notas_baixas=0, total=10, seq=0) == "excelente"

    def test_adequado(self):
        assert classificar_risco(media=7.5, notas_baixas=1, total=10, seq=0) == "adequado"

    def test_media_exatamente_minima(self):
        # média == 6.0 não é crítico pela média (< 6.0 é crítico)
        assert classificar_risco(media=6.0, notas_baixas=0, total=5, seq=0) == "atencao"

    def test_total_zero_nao_quebra(self):
        resultado = classificar_risco(media=5.0, notas_baixas=0, total=0, seq=0)
        assert resultado in {"critico", "atencao", "adequado", "excelente"}


# ── detectar_tendencia ────────────────────────────────────────────────────────

class TestDetectarTendencia:
    def test_melhora_clara(self):
        df = _df_notas([4, 4, 4, 4, 8, 8, 8, 8])
        assert detectar_tendencia(df) == "melhora"

    def test_queda_clara(self):
        df = _df_notas([9, 9, 9, 9, 4, 4, 4, 4])
        assert detectar_tendencia(df) == "queda"

    def test_estavel(self):
        df = _df_notas([7, 7, 7, 7, 7, 7, 7, 7])
        assert detectar_tendencia(df) == "estável"

    def test_poucos_dados_indefinido(self):
        df = _df_notas([5, 8])
        assert detectar_tendencia(df) == "indefinida"

    def test_exatamente_4_dados(self):
        # 4 pontos é o mínimo aceito
        df = _df_notas([5, 5, 9, 9])
        assert detectar_tendencia(df) in {"melhora", "queda", "estável"}


# ── detectar_sequencia_critica ────────────────────────────────────────────────

class TestDetectarSequenciaCritica:
    def test_sequencia_de_3(self):
        df = _df_notas([8, 8, 5, 5, 5])
        assert detectar_sequencia_critica(df) == 3

    def test_sequencia_de_5(self):
        df = _df_notas([9, 4, 4, 4, 4, 4])
        assert detectar_sequencia_critica(df) == 5

    def test_sem_sequencia_critica(self):
        df = _df_notas([5, 5, 8])  # termina com 8 → sequência = 0
        assert detectar_sequencia_critica(df) == 0

    def test_sequencia_abaixo_minimo_retorna_zero(self):
        # 2 consecutivas < mínimo de 3
        df = _df_notas([8, 5, 5])
        assert detectar_sequencia_critica(df) == 0

    def test_todas_criticas(self):
        # 4, 3, 2 são críticos; 7, 7, 7 aprovam → sequência final = 0
        # Para testar todas críticas: [4, 3, 2, 4, 4, 4] → 6 críticas consecutivas no final
        df = _df_notas([4, 3, 2, 4, 4, 4])
        assert detectar_sequencia_critica(df) == 6

    def test_ultima_nota_aprovado_zera(self):
        df = _df_notas([4, 4, 4, 8])
        assert detectar_sequencia_critica(df) == 0


# ── classificar_risco com notas_por_vetor ─────────────────────────────────────

class TestClassificarRiscoComVetores:
    def test_vetor_abaixo_minimo_forca_critico(self):
        # Média geral boa mas Comportamento abaixo de 6 → crítico (Regra 1)
        assert classificar_risco(
            media=8.0, notas_baixas=0, total=10, seq=0,
            notas_por_vetor={"Fazer (40%)": 9.0, "Saber (30%)": 8.0, "Comport. (30%)": 5.5},
        ) == "critico"

    def test_todos_vetores_aprovados_nao_forca_critico(self):
        assert classificar_risco(
            media=7.5, notas_baixas=0, total=10, seq=0,
            notas_por_vetor={"Fazer (40%)": 8.0, "Saber (30%)": 7.0, "Comport. (30%)": 7.0},
        ) != "critico"

    def test_sem_notas_por_vetor_comportamento_normal(self):
        # Sem o parâmetro, funciona como antes
        assert classificar_risco(media=9.0, notas_baixas=0, total=10, seq=0) == "excelente"

    def test_exatamente_no_minimo_nao_critico(self):
        assert classificar_risco(
            media=7.0, notas_baixas=0, total=5, seq=0,
            notas_por_vetor={"Fazer (40%)": 6.0, "Saber (30%)": 6.0},
        ) != "critico"


# ── calcular_notas_por_vetor ──────────────────────────────────────────────────

def _df_com_instrumentos(dados: list[tuple]) -> pd.DataFrame:
    """dados = [(vetor, instrumento, nota), ...]"""
    rows = []
    base = pd.Timestamp("2024-01-01")
    for i, (v, instr, n) in enumerate(dados):
        rows.append({
            "Vetor (Peso)": v,
            "Instrumento / Atividade": instr,
            "Nota": n,
            "Data": base + pd.Timedelta(days=i),
        })
    return pd.DataFrame(rows)


class TestCalcularNotasPorVetor:
    def test_retorna_vazio_sem_coluna_vetor(self):
        df = _df_notas([7, 8, 9])
        assert calcular_notas_por_vetor(df) == {}

    def test_instrumento_unico_usa_nota_direta(self):
        df = _df_com_instrumentos([
            ("Fazer (40%)", "Projeto Prático", 8.0),
        ])
        notas = calcular_notas_por_vetor(df)
        # Só Projeto Prático (50%) presente → peso redistribuído para 100% → nota = 8.0
        assert notas["Fazer (40%)"] == pytest.approx(8.0)

    def test_multiplas_avaliacoes_mesmo_instrumento_faz_media(self):
        # Regra 3: duas provas → média antes do peso
        df = _df_com_instrumentos([
            ("Saber (30%)", "Prova", 8.0),
            ("Saber (30%)", "Prova", 6.0),  # média = 7.0
        ])
        notas = calcular_notas_por_vetor(df)
        # Só Prova presente → 100% do peso → nota = 7.0
        assert notas["Saber (30%)"] == pytest.approx(7.0)

    def test_redistribuicao_instrumento_ausente(self):
        # Regra 4: Fazer sem Atividade (15%) → Projeto e Observação redistribuem
        # Pesos originais: Projeto 50%, Observação 35%  → total 85%
        # Redistribuídos: Projeto 50/85 ≈ 58.82%, Observação 35/85 ≈ 41.18%
        df = _df_com_instrumentos([
            ("Fazer (40%)", "Projeto Prático",    9.0),
            ("Fazer (40%)", "Observação Oficina", 7.0),
        ])
        esperado = (9.0 * 50 + 7.0 * 35) / (50 + 35)
        notas = calcular_notas_por_vetor(df)
        assert notas["Fazer (40%)"] == pytest.approx(esperado, rel=1e-3)

    def test_instrumento_nao_reconhecido_usa_media_simples(self):
        df = _df_com_instrumentos([
            ("Saber (30%)", "Instrumento Desconhecido", 7.0),
            ("Saber (30%)", "Instrumento Desconhecido", 9.0),
        ])
        notas = calcular_notas_por_vetor(df)
        assert notas["Saber (30%)"] == pytest.approx(8.0)


# ── calcular_media_ponderada ──────────────────────────────────────────────────

class TestCalcularMediaPonderada:
    def test_sem_vetores_retorna_media_simples(self):
        df = _df_notas([6, 8, 10])
        assert calcular_media_ponderada(df) == pytest.approx(8.0)

    def test_pesos_corretos(self):
        # Fazer=10 (40%), Saber=0 (30%), Comp=0 (30%) → 10*0.4 = 4.0
        df = _df_vetores(fazer=[10], saber=[0], comp=[0])
        assert calcular_media_ponderada(df) == pytest.approx(4.0)

    def test_todos_iguais_igual_media_simples(self):
        df = _df_vetores(fazer=[8, 8], saber=[8, 8], comp=[8, 8])
        assert calcular_media_ponderada(df) == pytest.approx(8.0)

    def test_vetor_ausente_ignora_peso(self):
        # Só tem Fazer e Saber (sem Comportamento)
        notas   = [10, 10, 6, 6]
        vetores = ["Fazer (40%)", "Fazer (40%)", "Saber (30%)", "Saber (30%)"]
        datas   = pd.date_range("2024-01-01", periods=4)
        df = pd.DataFrame({"Nota": notas, "Vetor (Peso)": vetores, "Data": datas})
        resultado = calcular_media_ponderada(df)
        # Fazer=10 (peso 0.4), Saber=6 (peso 0.3) → (10*0.4 + 6*0.3) / 0.7 ≈ 8.286
        assert resultado == pytest.approx((10 * 0.4 + 6 * 0.3) / 0.7, rel=1e-3)
