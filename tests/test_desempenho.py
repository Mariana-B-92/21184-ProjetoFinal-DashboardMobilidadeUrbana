"""
Testes de desempenho (Capitulo 4 - Testes).

Medem os tempos de execucao das operacoes-chave do sistema e verificam que se
mantem dentro de limiares razoaveis para uma utilizacao interativa fluida. Os
tempos medidos sao impressos (visiveis com `pytest -s`) para inclusao no
relatorio.

Os limiares sao deliberadamente folgados para nao gerar falsos negativos em
maquinas mais lentas; o objetivo e detetar regressoes graves de desempenho, nao
fixar uma marca exata.
"""

import time

import pytest


def _cronometrar(funcao, repeticoes=3):
    """Devolve o tempo MEDIO (s) de varias execucoes de uma funcao."""
    tempos = []
    for _ in range(repeticoes):
        inicio = time.perf_counter()
        funcao()
        tempos.append(time.perf_counter() - inicio)
    return sum(tempos) / len(tempos)


def test_desempenho_arranque_repositorio(base_dados):
    """O arranque do repositorio (carregamento dos estaticos) e rapido."""
    from app.data import RepositorioDados

    tempo = _cronometrar(lambda: RepositorioDados(caminho_db=base_dados),
                         repeticoes=2)
    print(f"\n[desempenho] arranque do repositorio: {tempo*1000:.0f} ms")
    assert tempo < 5.0


def test_desempenho_serie_temporal(repo):
    """A consulta de uma serie temporal (com indice) e rapida."""
    id_estacao = int(repo.estacoes_gira["id_estacao"].iloc[0])
    tempo = _cronometrar(
        lambda: repo.serie_temporal(id_estacao, frequencia="D"))
    print(f"\n[desempenho] serie temporal (1 estacao): {tempo*1000:.0f} ms")
    assert tempo < 2.0


def test_desempenho_heatmap(repo):
    """O calculo do heatmap (agregacao server-side) e rapido."""
    id_estacao = int(repo.estacoes_gira["id_estacao"].iloc[0])
    tempo = _cronometrar(
        lambda: repo.heatmap_disponibilidade(id_estacao))
    print(f"\n[desempenho] heatmap (1 estacao): {tempo*1000:.0f} ms")
    assert tempo < 2.0


def test_desempenho_cobertura_metro(repo):
    """A analise de cobertura (buffer + intersecoes) responde ao clique."""
    id_metro = int(repo.estacoes_metro["id_metro"].iloc[0])
    tempo = _cronometrar(lambda: repo.cobertura_metro(id_metro))
    print(f"\n[desempenho] cobertura de uma estacao de metro: {tempo*1000:.0f} ms")
    assert tempo < 2.0


def test_desempenho_consulta_indexada_vs_volume(ligacao_bd):
    """A consulta por id_estacao usa o indice (tempo baixo apesar do volume)."""
    cur = ligacao_bd.cursor()
    total = cur.execute("SELECT COUNT(*) FROM DisponibilidadeGIRA").fetchone()[0]
    id_estacao = cur.execute(
        "SELECT id_estacao FROM EstacaoGIRA LIMIT 1").fetchone()[0]

    def consulta():
        cur.execute("SELECT COUNT(*) FROM DisponibilidadeGIRA "
                    "WHERE id_estacao = ?", [id_estacao]).fetchone()

    tempo = _cronometrar(consulta, repeticoes=5)
    print(f"\n[desempenho] consulta indexada sobre {total:,} registos: "
          f"{tempo*1000:.1f} ms")
    assert tempo < 1.0
