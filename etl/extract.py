"""Extracao dos ficheiros de origem (CSV do historico GIRA, GeoJSON de metro e
rede ciclavel), com validacao de colunas essenciais antes de prosseguir."""

import geopandas as gpd
import pandas as pd

import config

COLUNAS_GIRA = ["desigcomercial", "numbicicletas", "numdocas",
                "position", "entity_ts", "estado"]
COLUNAS_METRO = ["OBJECTID", "NOME", "LINHA", "SITUACAO", "geometry"]
# Inclui HIERARQUIA e COMP_KM porque sao consumidas no carregamento (load.py);
# validar aqui evita falha tardia na persistencia.
COLUNAS_CICLAVEL = ["OBJECTID", "DESIGNACAO", "TIPOLOGIA", "NIVEL_SEGREGACAO",
                    "SITUACAO", "HIERARQUIA", "COMPRIMENTO", "COMP_KM",
                    "FREGUESIA", "geometry"]


def _validar_colunas(df, esperadas, nome):
    """Garante que o dataset contem todas as colunas essenciais."""
    em_falta = [c for c in esperadas if c not in df.columns]
    if em_falta:
        raise ValueError(
            f"Dataset '{nome}': colunas essenciais em falta: {em_falta}"
        )


def extrair_historico_gira(ficheiros=None):
    """Le e concatena os ficheiros CSV do historico GIRA num unico DataFrame."""
    ficheiros = ficheiros or config.FICHEIROS_GIRA
    partes = []
    for caminho in ficheiros:
        df = pd.read_csv(caminho, dtype={"numbicicletas": "Int32",
                                         "numdocas": "Int32"})
        _validar_colunas(df, COLUNAS_GIRA, caminho.name)
        df["ficheiro_origem"] = caminho.name
        partes.append(df)
    historico = pd.concat(partes, ignore_index=True)
    return historico


def extrair_metro(caminho=None):
    """Le o GeoJSON das estacoes de metro."""
    caminho = caminho or config.FICHEIRO_METRO
    gdf = gpd.read_file(caminho)
    _validar_colunas(gdf, COLUNAS_METRO, "estacoes_metro")
    return gdf


def extrair_ciclavel(caminho=None):
    """Le o GeoJSON da rede ciclavel."""
    caminho = caminho or config.FICHEIRO_CICLAVEL
    gdf = gpd.read_file(caminho)
    _validar_colunas(gdf, COLUNAS_CICLAVEL, "rede_ciclavel")
    return gdf