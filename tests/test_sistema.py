"""
Testes de sistema / integracao (Capitulo 4 - Testes).

Verificam o funcionamento do sistema como um todo: a integridade do modelo
persistido em SQLite e a coerencia entre os indicadores calculados em tempo real
pela camada de dados do dashboard e os valores persistidos pelo pipeline.
"""

import sqlite3

import pytest


TABELAS_ESPERADAS = {
    "EstacaoGIRA", "DisponibilidadeGIRA", "EstacaoMetro", "RedeCiclavel",
    "IndicadorDisponibilidadeGIRA", "IndicadorCoberturaMetro",
}


# --------------------------------------------------------------------------- #
# Integridade do modelo persistido
# --------------------------------------------------------------------------- #
def test_base_dados_tem_todas_as_entidades(ligacao_bd):
    """As seis entidades do modelo estao presentes na base de dados."""
    cur = ligacao_bd.cursor()
    tabelas = {r[0] for r in cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert TABELAS_ESPERADAS.issubset(tabelas)


def test_entidades_nao_vazias(ligacao_bd):
    """Nenhuma entidade do modelo esta vazia."""
    cur = ligacao_bd.cursor()
    for tabela in TABELAS_ESPERADAS:
        n = cur.execute(f'SELECT COUNT(*) FROM "{tabela}"').fetchone()[0]
        assert n > 0, f"{tabela} esta vazia"


def test_indices_criados(ligacao_bd):
    """Os indices de consulta eficiente foram criados."""
    cur = ligacao_bd.cursor()
    indices = {r[0] for r in cur.execute(
        "SELECT name FROM sqlite_master WHERE type='index'")}
    assert "idx_disp_estacao_ts" in indices


def test_geometrias_em_wkt_validas(ligacao_bd):
    """As geometrias persistidas em WKT sao reconstrutiveis."""
    from shapely import wkt
    cur = ligacao_bd.cursor()
    amostra = cur.execute(
        "SELECT geometria_wkt FROM EstacaoMetro LIMIT 5").fetchall()
    for (g,) in amostra:
        assert wkt.loads(g).geom_type == "Point"


# --------------------------------------------------------------------------- #
# Coerencia app (tempo real) <-> base de dados (persistido)
# --------------------------------------------------------------------------- #
def test_cobertura_app_coerente_com_bd(repo):
    """A cobertura recalculada na app coincide com os indicadores persistidos.

    Para cada estacao de metro, o numero de GIRA na area e o comprimento ciclavel
    calculados em tempo real pela camada de dados devem igualar os valores do
    Grupo 2 guardados na base de dados.
    """
    import geopandas as gpd
    import config

    metro = repo.estacoes_metro
    # Amostra de 8 estacoes para manter o teste rapido mas representativo.
    for _, linha in metro.head(8).iterrows():
        id_metro = linha["id_metro"]
        cob = repo.cobertura_metro(id_metro)

        # N.o de GIRA na area.
        assert len(cob["gira"]) == int(linha["n_gira_influencia"])

        # Comprimento ciclavel (recalculado em CRS metrico).
        comp = cob["ciclavel"].to_crs(config.CRS_METRICO).length.sum()
        assert comp == pytest.approx(linha["comp_ciclavel_m"], abs=1.0)


def test_serie_temporal_consistente(repo):
    """A serie temporal de uma estacao devolve dados dentro do periodo."""
    id_estacao = int(repo.estacoes_gira["id_estacao"].iloc[0])
    serie = repo.serie_temporal(id_estacao, frequencia="D")
    assert not serie.empty
    assert (serie["numbicicletas"] >= 0).all()


def test_heatmap_dimensoes(repo):
    """O heatmap tem, no maximo, a forma 7 dias x 24 horas."""
    id_estacao = int(repo.estacoes_gira["id_estacao"].iloc[0])
    matriz = repo.heatmap_disponibilidade(id_estacao)
    assert matriz.shape[0] <= 7
    assert matriz.shape[1] <= 24


def test_estacoes_gira_tem_indicadores(repo):
    """As estacoes GIRA trazem os indicadores do Grupo 1 (join correto)."""
    assert "disponibilidade_media" in repo.estacoes_gira.columns
    assert "hora_pico" in repo.estacoes_gira.columns
    assert repo.estacoes_gira["disponibilidade_media"].notna().any()
