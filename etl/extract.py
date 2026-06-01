"""
ETL - Etapa 1: Extracao.

Le os ficheiros de origem da plataforma Lisboa Aberta:
- historico GIRA (2 ficheiros CSV, concatenados);
- estacoes de metro e rede ciclavel (GeoJSON).

Valida a presenca dos campos essenciais em cada dataset antes de prosseguir.
"""

import geopandas as gpd
import pandas as pd

import config

# Colunas esperadas em cada fonte (validacao de integridade estrutural).
COLUNAS_GIRA = ["desigcomercial", "numbicicletas", "numdocas",
                "position", "entity_ts", "estado"]
COLUNAS_METRO = ["NOME", "LINHA", "SITUACAO", "geometry"]
COLUNAS_CICLAVEL = ["DESIGNACAO", "TIPOLOGIA", "NIVEL_SEGREGACAO",
                    "SITUACAO", "COMPRIMENTO", "FREGUESIA", "geometry"]


def _validar_colunas(df, esperadas, nome):
    """Garante que o dataset contem todas as colunas essenciais."""
    em_falta = [c for c in esperadas if c not in df.columns]
    if em_falta:
        raise ValueError(
            f"Dataset '{nome}': colunas essenciais em falta: {em_falta}"
        )


def extrair_historico_gira(ficheiros=None):
    """Le e concatena os ficheiros CSV do historico GIRA.

    Retorna um DataFrame unico com os dois semestres de 2022.
    """
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
