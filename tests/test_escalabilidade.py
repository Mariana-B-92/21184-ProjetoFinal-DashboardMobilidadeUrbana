"""
Testes de escalabilidade (Capitulo 4 - Testes).

Avaliam como o desempenho do sistema evolui quando o volume de dados cresce.
Em vez de medir um unico ponto, medem o tempo em funcao do tamanho do problema e
verificam que o crescimento e sub-linear ou linear (e nao explosivo), gracas aos
indices da base de dados e a agregacao server-side.

Os tempos sao impressos (visiveis com `pytest -s`) para construir as tabelas e
graficos de escalabilidade do relatorio.
"""

import time

import pandas as pd
import pytest


def _cronometrar(funcao, repeticoes=3):
    tempos = []
    for _ in range(repeticoes):
        inicio = time.perf_counter()
        funcao()
        tempos.append(time.perf_counter() - inicio)
    return sum(tempos) / len(tempos)


def test_escalabilidade_consulta_por_volume(ligacao_bd):
    """Tempo de consulta agregada para volumes crescentes de registos.

    Consulta a disponibilidade media limitando a um numero crescente de linhas.
    Espera-se crescimento controlado (aproximadamente linear) com o volume.
    """
    cur = ligacao_bd.cursor()
    total = cur.execute("SELECT COUNT(*) FROM DisponibilidadeGIRA").fetchone()[0]

    limites = [10_000, 50_000, 100_000, 500_000]
    limites = [n for n in limites if n <= total]

    print(f"\n[escalabilidade] consulta agregada (total disponivel: {total:,})")
    tempos = []
    for n in limites:
        def consulta():
            cur.execute(
                "SELECT AVG(numbicicletas) FROM "
                "(SELECT numbicicletas FROM DisponibilidadeGIRA LIMIT ?)",
                [n]).fetchone()
        t = _cronometrar(consulta, repeticoes=3)
        tempos.append(t)
        print(f"  {n:>8,} registos -> {t*1000:6.1f} ms")

    # O tempo nao deve explodir: 50x mais dados nao deve custar >100x o tempo.
    if len(tempos) >= 2:
        fator_dados = limites[-1] / limites[0]
        fator_tempo = tempos[-1] / max(tempos[0], 1e-6)
        print(f"  fator dados x{fator_dados:.0f} -> fator tempo x{fator_tempo:.1f}")
        assert fator_tempo < fator_dados * 2


def test_escalabilidade_series_multiplas_estacoes(repo):
    """Tempo de obtencao de series para um numero crescente de estacoes.

    Simula a carga de varias consultas (ex.: comparar multiplas estacoes). O
    tempo deve crescer aproximadamente de forma linear com o numero de estacoes.
    """
    ids = repo.estacoes_gira["id_estacao"].head(20).tolist()
    contagens = [1, 5, 10, 20]
    contagens = [c for c in contagens if c <= len(ids)]

    print("\n[escalabilidade] series temporais para N estacoes")
    tempos = []
    for n in contagens:
        def consulta():
            for id_e in ids[:n]:
                repo.serie_temporal(int(id_e), frequencia="D")
        t = _cronometrar(consulta, repeticoes=2)
        tempos.append(t)
        print(f"  {n:>2} estacoes -> {t*1000:7.1f} ms "
              f"({t/n*1000:.1f} ms/estacao)")

    # Custo por estacao aproximadamente estavel (crescimento linear).
    if len(tempos) >= 2:
        custo_inicial = tempos[0] / contagens[0]
        custo_final = tempos[-1] / contagens[-1]
        print(f"  custo/estacao: {custo_inicial*1000:.1f} -> "
              f"{custo_final*1000:.1f} ms")
        assert custo_final < custo_inicial * 3


def test_escalabilidade_cobertura_por_raio(repo):
    """Tempo da analise de cobertura para raios crescentes.

    Raios maiores intersetam mais geometria ciclavel; o tempo deve manter-se
    praticavel mesmo para o raio maximo (exploracao interativa fluida).
    """
    id_metro = int(repo.estacoes_metro["id_metro"].iloc[0])
    raios = [250, 500, 750, 1000]

    print("\n[escalabilidade] cobertura por raio de influencia")
    for raio in raios:
        t = _cronometrar(lambda: repo.cobertura_metro(id_metro, raio=raio),
                         repeticoes=3)
        print(f"  raio {raio:>4} m -> {t*1000:6.1f} ms")
        assert t < 3.0
