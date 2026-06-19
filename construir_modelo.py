"""
Orquestrador da fase offline: corre o ETL, calcula os KPIs e persiste o modelo
integrado em SQLite.

Uso:
    python construir_modelo.py
"""

import sqlite3
import warnings

from etl import load, pipeline
from kpis import grupo1, grupo2


def _pre_agregar_serie_global(caminho):
    """Pre-calcula a serie diaria da disponibilidade media global numa tabela
    auxiliar (DisponibilidadeGlobalDiaria).

    Feito offline para o runtime nao ter de agregar ~1.99 M registos a pedido
    na vista inicial do dashboard.
    """
    with sqlite3.connect(caminho) as conn:
        conn.execute("DROP TABLE IF EXISTS DisponibilidadeGlobalDiaria")
        conn.execute(
            "CREATE TABLE DisponibilidadeGlobalDiaria AS "
            "SELECT data, AVG(numbicicletas) AS media "
            "FROM DisponibilidadeGIRA GROUP BY data ORDER BY data")
        conn.commit()


def construir():
    artefactos = pipeline.correr_etl()

    indicadores_g1 = grupo1.calcular_grupo1(
        artefactos["agg_estacao"], artefactos["agg_estacao_hora"])

    indicadores_g2 = grupo2.calcular_grupo2(
        artefactos["cobertura"], artefactos["pertenca"], indicadores_g1)

    caminho = load.carregar(artefactos, indicadores_g1, indicadores_g2)

    _pre_agregar_serie_global(caminho)

    print(f"Modelo integrado persistido em: {caminho}")
    print(f"  EstacaoGIRA: {len(artefactos['estacoes_gira'])}")
    print(f"  DisponibilidadeGIRA: {len(artefactos['historico_limpo'])}")
    print(f"  EstacaoMetro: {len(artefactos['metro_limpo'])}")
    print(f"  RedeCiclavel: {len(artefactos['ciclavel_limpo'])}")
    print(f"  IndicadorDisponibilidadeGIRA: {len(indicadores_g1)}")
    print(f"  IndicadorCoberturaMetro: {len(indicadores_g2)}")


if __name__ == "__main__":
    # Silencia avisos cosmeticos (pandas/geopandas); local ao script.
    warnings.filterwarnings("ignore")
    construir()