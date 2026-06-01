"""
Testes unitarios do ETL (Capitulo 4 - Testes).

Cobrem o parsing e a limpeza dos dados e a integracao espacial, incluindo a
questao metodologica do orientador sobre o comprimento ciclavel: deve ser
calculado pela intersecao segmento ∩ buffer, e nao pela soma dos comprimentos
totais dos segmentos que intersetam a area (que sobrestimaria o valor).
"""

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import LineString, Point

import config
from etl import clean, spatial


# --------------------------------------------------------------------------- #
# Parsing e limpeza
# --------------------------------------------------------------------------- #
def test_parsing_id_estacao_e_coordenadas():
    """Extrai o id (prefixo numerico) e as coordenadas do campo 'position'."""
    bruto = pd.DataFrame({
        "desigcomercial": ["417 - Av. Duque de Ávila"],
        "numbicicletas": [5], "numdocas": [20],
        "position": ["[-9.145, 38.736]"],
        "entity_ts": ["2022-01-01T10:00:00Z"],
        "estado": ["active"],
    })
    limpo, _ = clean.limpar_historico_gira(bruto)
    assert limpo["id_estacao"].iloc[0] == 417
    assert limpo["longitude"].iloc[0] == pytest.approx(-9.145)
    assert limpo["latitude"].iloc[0] == pytest.approx(38.736)
    assert "417" not in limpo["nome_estacao"].iloc[0]


def test_remocao_duplicados():
    """Registos identicos (mesma estacao e timestamp) sao deduplicados."""
    bruto = pd.DataFrame({
        "desigcomercial": ["100 - X"] * 3,
        "numbicicletas": [5, 5, 6], "numdocas": [20, 20, 20],
        "position": ["[-9.1, 38.7]"] * 3,
        "entity_ts": ["2022-01-01T10:00:00Z"] * 3,
        "estado": ["active"] * 3,
    })
    limpo, q = clean.limpar_historico_gira(bruto)
    assert len(limpo) == 1
    assert q["duplicados_removidos"] == 2


def test_filtro_repair_configuravel(monkeypatch):
    """Quando ativado, os registos 'repair' sao removidos."""
    monkeypatch.setattr(config, "EXCLUIR_ESTADO_REPAIR", True)
    bruto = pd.DataFrame({
        "desigcomercial": ["100 - X", "100 - X"],
        "numbicicletas": [5, 6], "numdocas": [20, 20],
        "position": ["[-9.1, 38.7]", "[-9.1, 38.7]"],
        "entity_ts": ["2022-01-01T10:00:00Z", "2022-01-01T11:00:00Z"],
        "estado": ["active", "repair"],
    })
    limpo, q = clean.limpar_historico_gira(bruto)
    assert (limpo["estado"] == "active").all()
    assert q["registos_repair_removidos"] == 1


def test_filtro_ciclavel_executado():
    """Apenas segmentos 'Executado' permanecem; geometrias nulas sao removidas."""
    gdf = gpd.GeoDataFrame({
        "DESIGNACAO": ["A", "B", "C"],
        "TIPOLOGIA": ["x", "x", "x"], "NIVEL_SEGREGACAO": ["x", "x", "x"],
        "SITUACAO": ["Executado", "Projeto", "Executado"],
        "COMPRIMENTO": [1, 2, 3], "FREGUESIA": ["f", "f", "f"],
        "HIERARQUIA": ["h", "h", "h"], "COMP_KM": [0.001, 0.002, 0.003],
        "geometry": [LineString([(0, 0), (1, 1)]), LineString([(0, 0), (1, 0)]),
                     None],
    }, crs=config.CRS_GEOGRAFICO)
    limpo, q = clean.limpar_ciclavel(gdf)
    assert (limpo["SITUACAO"] == "Executado").all()
    assert len(limpo) == 1  # B excluido (Projeto), C excluido (geometria nula)
    assert q["geometrias_nulas_removidas"] == 1


# --------------------------------------------------------------------------- #
# Integracao espacial: intersecao vs soma total (questao do orientador)
# --------------------------------------------------------------------------- #
def test_comprimento_ciclavel_usa_intersecao():
    """O comprimento ciclavel conta apenas a porcao contida no buffer.

    Cenario controlado: uma estacao de metro na origem (buffer de 500 m) e um
    segmento que entra e sai do buffer. Espera-se que o comprimento contabilizado
    seja MENOR do que o comprimento total do segmento (intersecao, nao soma total).
    """
    # Estacao GIRA (longe, irrelevante para o comprimento) e metro na origem.
    gira = gpd.GeoDataFrame(
        {"id_estacao": [1], "nome_estacao": ["g"], "total_docas": [20],
         "longitude": [0.0], "latitude": [0.0]},
        geometry=[Point(0, 0)], crs=config.CRS_METRICO).to_crs(
        config.CRS_GEOGRAFICO)

    metro = gpd.GeoDataFrame(
        {"OBJECTID": [1], "NOME": ["M"], "LINHA": ["Azul"],
         "SITUACAO": ["Linha existente"]},
        geometry=[Point(0, 0)], crs=config.CRS_METRICO).to_crs(
        config.CRS_GEOGRAFICO)

    # Segmento de 2000 m em CRS metrico: de x=0 ate x=2000 (so 500 m no buffer).
    seg = gpd.GeoDataFrame(
        {"DESIGNACAO": ["s"], "TIPOLOGIA": ["x"], "NIVEL_SEGREGACAO": ["x"],
         "SITUACAO": ["Executado"], "COMPRIMENTO": [2000.0],
         "FREGUESIA": ["f"], "HIERARQUIA": ["h"], "COMP_KM": [2.0]},
        geometry=[LineString([(0, 0), (2000, 0)])],
        crs=config.CRS_METRICO).to_crs(config.CRS_GEOGRAFICO)

    cobertura, _ = spatial.integracao_espacial(gira, metro, seg, raio=500)
    comp = cobertura["comp_ciclavel_m"].iloc[0]

    # Apenas ~500 m (porcao no buffer), nao os 2000 m totais.
    assert comp == pytest.approx(500, abs=5)
    assert comp < 2000


def test_n_gira_e_distancia_minima():
    """Contagem de GIRA no buffer e distancia minima corretas."""
    gira = gpd.GeoDataFrame(
        {"id_estacao": [1, 2, 3], "nome_estacao": ["a", "b", "c"],
         "total_docas": [20, 20, 20],
         "longitude": [0, 0, 0], "latitude": [0, 0, 0]},
        geometry=[Point(100, 0), Point(400, 0), Point(900, 0)],
        crs=config.CRS_METRICO).to_crs(config.CRS_GEOGRAFICO)
    metro = gpd.GeoDataFrame(
        {"OBJECTID": [1], "NOME": ["M"], "LINHA": ["Azul"],
         "SITUACAO": ["Linha existente"]},
        geometry=[Point(0, 0)], crs=config.CRS_METRICO).to_crs(
        config.CRS_GEOGRAFICO)
    ciclavel = gpd.GeoDataFrame(
        {"DESIGNACAO": [], "TIPOLOGIA": [], "NIVEL_SEGREGACAO": [],
         "SITUACAO": [], "COMPRIMENTO": [], "FREGUESIA": [], "HIERARQUIA": [],
         "COMP_KM": []},
        geometry=[], crs=config.CRS_METRICO).to_crs(config.CRS_GEOGRAFICO)

    cobertura, pertenca = spatial.integracao_espacial(
        gira, metro, ciclavel, raio=500)
    # GIRA a 100 e 400 m estao dentro de 500 m; a 900 m esta fora.
    assert cobertura["n_gira_influencia"].iloc[0] == 2
    assert cobertura["dist_gira_min_m"].iloc[0] == pytest.approx(100, abs=2)
