"""
Orquestrador da fase offline (pre-processamento).

Executa, por esta ordem, toda a preparacao de dados que antecede o arranque do
dashboard, em conformidade com a arquitetura em camadas (seccao 2.2):
  1. ETL  - Etapas 1-4 (extracao, limpeza, integracao espacial, var. derivadas)
  2. KPIs - Grupo 1 (disponibilidade) e Grupo 2 + IIC (cobertura)
  3. ETL  - Etapa 5 (carregamento do modelo integrado em SQLite)

Uso:
    python construir_modelo.py
"""

import warnings

from etl import load, pipeline
from kpis import grupo1, grupo2


def construir():
    # 1-4. ETL
    artefactos = pipeline.correr_etl()

    # KPIs - Grupo 1
    indicadores_g1 = grupo1.calcular_grupo1(
        artefactos["agg_estacao"], artefactos["agg_estacao_hora"])

    # KPIs - Grupo 2 + IIC
    indicadores_g2 = grupo2.calcular_grupo2(
        artefactos["cobertura"], artefactos["pertenca"], indicadores_g1)

    # 5. Carregamento
    caminho = load.carregar(artefactos, indicadores_g1, indicadores_g2)

    print(f"Modelo integrado persistido em: {caminho}")
    print(f"  EstacaoGIRA: {len(artefactos['estacoes_gira'])}")
    print(f"  DisponibilidadeGIRA: {len(artefactos['historico_limpo'])}")
    print(f"  EstacaoMetro: {len(artefactos['metro_limpo'])}")
    print(f"  RedeCiclavel: {len(artefactos['ciclavel_limpo'])}")
    print(f"  IndicadorDisponibilidadeGIRA: {len(indicadores_g1)}")
    print(f"  IndicadorCoberturaMetro: {len(indicadores_g2)}")


if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    construir()
