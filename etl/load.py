"""Persiste o modelo integrado em SQLite, com as geometrias em WKT (WGS84).

Recebe os indicadores ja calculados (kpis/) e apenas os persiste. Entidades:
  EstacaoGIRA, DisponibilidadeGIRA (~1.99 M registos), EstacaoMetro,
  RedeCiclavel e as duas tabelas de indicadores (GIRA e cobertura de metro).
"""

import sqlite3

import geopandas as gpd
import pandas as pd

import config

_CHUNK = 100_000


def _tabela_estacao_gira(estacoes_gira):
    return pd.DataFrame({
        "id_estacao": estacoes_gira["id_estacao"],
        "nome_estacao": estacoes_gira["nome_estacao"],
        "total_docas": estacoes_gira["total_docas"],
        "longitude": estacoes_gira["longitude"],
        "latitude": estacoes_gira["latitude"],
        "geometria_wkt": estacoes_gira.geometry.to_wkt(),
    })


def _tabela_disponibilidade(historico_limpo):
    df = historico_limpo[[
        "id_estacao", "timestamp", "data", "hora", "dia_semana",
        "numbicicletas", "numdocas", "estado"]].copy()
    # timestamp tz-aware -> texto ISO 8601 (SQLite nao tem tipo datetime nativo).
    df["timestamp"] = df["timestamp"].astype(str)
    df["data"] = df["data"].astype(str)
    return df


def _tabela_metro(metro_limpo):
    return pd.DataFrame({
        "id_metro": metro_limpo["OBJECTID"],
        "nome": metro_limpo["NOME"],
        "linha": metro_limpo["LINHA"],
        "situacao": metro_limpo["SITUACAO"],
        "geometria_wkt": metro_limpo.geometry.to_wkt(),
    })


def _tabela_ciclavel(ciclavel_limpo):
    df = pd.DataFrame({
        "id_segmento": ciclavel_limpo["OBJECTID"],
        "designacao": ciclavel_limpo["DESIGNACAO"],
        "tipologia": ciclavel_limpo["TIPOLOGIA"],
        "nivel_segregacao": ciclavel_limpo["NIVEL_SEGREGACAO"],
        "situacao": ciclavel_limpo["SITUACAO"],
        "hierarquia": ciclavel_limpo["HIERARQUIA"],
        "freguesia": ciclavel_limpo["FREGUESIA"],
        "comprimento_m": ciclavel_limpo["COMPRIMENTO"],
        "comp_km": ciclavel_limpo["COMP_KM"],
        "geometria_wkt": ciclavel_limpo.geometry.to_wkt(),
    })
    return df


def _tabela_indicador_cobertura(indicadores_g2):
    df = indicadores_g2.reset_index().copy()
    df["geometria_wkt"] = gpd.GeoSeries(df["geometry"]).to_wkt()
    df["buffer_wkt"] = gpd.GeoSeries(df["buffer"]).to_wkt()
    return df.drop(columns=["geometry", "buffer"])


def carregar(artefactos, indicadores_g1, indicadores_g2, caminho_db=None):
    """Persiste todas as entidades em SQLite. Recria as tabelas a cada execucao."""
    caminho_db = caminho_db or config.BASE_DADOS
    config.DIR_PROCESSED.mkdir(parents=True, exist_ok=True)

    tabelas = {
        "EstacaoGIRA": _tabela_estacao_gira(artefactos["estacoes_gira"]),
        "EstacaoMetro": _tabela_metro(artefactos["metro_limpo"]),
        "RedeCiclavel": _tabela_ciclavel(artefactos["ciclavel_limpo"]),
        "IndicadorDisponibilidadeGIRA": indicadores_g1.reset_index(),
        "IndicadorCoberturaMetro": _tabela_indicador_cobertura(indicadores_g2),
    }
    disponibilidade = _tabela_disponibilidade(artefactos["historico_limpo"])

    with sqlite3.connect(caminho_db) as conn:
        for nome, df in tabelas.items():
            df.to_sql(nome, conn, if_exists="replace", index=False)

        # Entidade temporal grande: escrita em blocos.
        disponibilidade.to_sql("DisponibilidadeGIRA", conn,
                               if_exists="replace", index=False,
                               chunksize=_CHUNK)

        # Indices para consultas eficientes no dashboard.
        cur = conn.cursor()
        cur.execute("CREATE INDEX IF NOT EXISTS idx_disp_estacao_ts "
                    "ON DisponibilidadeGIRA (id_estacao, timestamp)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_disp_estacao_hora "
                    "ON DisponibilidadeGIRA (id_estacao, hora)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_ind_gira "
                    "ON IndicadorDisponibilidadeGIRA (id_estacao)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_ind_metro "
                    "ON IndicadorCoberturaMetro (id_metro)")
        conn.commit()

    return caminho_db
