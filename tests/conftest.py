"""
Fixtures partilhadas pelos testes.

A construcao do modelo integrado (ETL + KPIs + carregamento) e executada uma
unica vez por sessao, numa base de dados temporaria, e reutilizada por todos os
testes que dela dependem, evitando repetir o processamento pesado.
"""

import sqlite3

import pytest

import config
from etl import clean, derive, extract, spatial


# --------------------------------------------------------------------------- #
# Artefactos do ETL (em memoria) - sessao
# --------------------------------------------------------------------------- #
def _dados_disponiveis():
    """Verifica se os CSV do historico GIRA ja foram extraidos para data/raw."""
    return all(caminho.exists() for caminho in config.FICHEIROS_GIRA)


@pytest.fixture(scope="session")
def artefactos_etl():
    """Corre as Etapas 1-4 do ETL uma vez e devolve os artefactos em memoria."""
    if not _dados_disponiveis():
        pytest.skip(
            "Dados de origem ausentes. Execute primeiro:\n"
            "  python scripts/preparar_dados.py\n"
            "  python construir_modelo.py")
    historico = extract.extrair_historico_gira()
    metro = extract.extrair_metro()
    ciclavel = extract.extrair_ciclavel()

    historico_limpo, q_gira = clean.limpar_historico_gira(historico)
    metro_limpo, _ = clean.limpar_metro(metro)
    ciclavel_limpo, _ = clean.limpar_ciclavel(ciclavel)

    estacoes_gira = spatial.construir_estacoes_gira(historico_limpo)
    cobertura, pertenca = spatial.integracao_espacial(
        estacoes_gira, metro_limpo, ciclavel_limpo)
    agg_estacao, agg_estacao_hora, q_derive = \
        derive.calcular_variaveis_derivadas(historico_limpo, estacoes_gira)

    return {
        "historico_limpo": historico_limpo,
        "estacoes_gira": estacoes_gira,
        "metro_limpo": metro_limpo,
        "ciclavel_limpo": ciclavel_limpo,
        "cobertura": cobertura,
        "pertenca": pertenca,
        "agg_estacao": agg_estacao,
        "agg_estacao_hora": agg_estacao_hora,
        "qualidade_gira": q_gira,
        "qualidade_derive": q_derive,
    }


@pytest.fixture(scope="session")
def indicadores_g1(artefactos_etl):
    from kpis import grupo1
    return grupo1.calcular_grupo1(
        artefactos_etl["agg_estacao"], artefactos_etl["agg_estacao_hora"])


@pytest.fixture(scope="session")
def indicadores_g2(artefactos_etl, indicadores_g1):
    from kpis import grupo2
    return grupo2.calcular_grupo2(
        artefactos_etl["cobertura"], artefactos_etl["pertenca"], indicadores_g1)


# --------------------------------------------------------------------------- #
# Base de dados construida (ficheiro temporario) - sessao
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="session")
def base_dados(tmp_path_factory, artefactos_etl, indicadores_g1, indicadores_g2):
    """Persiste o modelo numa base de dados temporaria e devolve o caminho."""
    from etl import load
    caminho = tmp_path_factory.mktemp("bd") / "mobilidade_teste.db"
    load.carregar(artefactos_etl, indicadores_g1, indicadores_g2,
                  caminho_db=caminho)
    return caminho


@pytest.fixture(scope="session")
def repo(base_dados):
    """Repositorio de dados do dashboard, ligado a base de dados de teste."""
    from app.data import RepositorioDados
    return RepositorioDados(caminho_db=base_dados)


@pytest.fixture
def ligacao_bd(base_dados):
    """Ligacao SQLite (so-leitura) a base de dados de teste."""
    conn = sqlite3.connect(f"file:{base_dados}?mode=ro", uri=True)
    yield conn
    conn.close()
