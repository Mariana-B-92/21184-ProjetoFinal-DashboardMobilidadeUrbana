"""
Orquestrador do pipeline de ETL.

Cobre as Etapas 1-4: 1 (Extracao), 2 (Limpeza), 3 (Integracao espacial) e
4 (Variaveis derivadas). A Etapa 5 (Carregamento) e deliberadamente externa a
este modulo: corre em etl/load.py, orquestrada por construir_modelo.py, DEPOIS
do calculo dos indicadores (kpis/) sobre as agregacoes devolvidas aqui. Esta
separacao mantem o pipeline focado na transformacao e a persistencia isolada.
"""

import json
import warnings

import config
from etl import clean, derive, extract, spatial


def correr_etl():
    """Corre as Etapas 1-4 e devolve os artefactos processados + qualidade.

    Retorna um dicionario com:
      historico_limpo, estacoes_gira, metro_limpo, ciclavel_limpo,
      cobertura, pertenca, agg_estacao, agg_estacao_hora, qualidade
    """
    qualidade = {}

    # Etapa 1 - Extracao
    historico = extract.extrair_historico_gira()
    metro = extract.extrair_metro()
    ciclavel = extract.extrair_ciclavel()

    # Etapa 2 - Limpeza e normalizacao
    historico_limpo, q_gira = clean.limpar_historico_gira(historico)
    metro_limpo, q_metro = clean.limpar_metro(metro)
    ciclavel_limpo, q_ciclavel = clean.limpar_ciclavel(ciclavel)
    qualidade["historico_gira"] = q_gira
    qualidade["estacoes_metro"] = q_metro
    qualidade["rede_ciclavel"] = q_ciclavel

    # Etapa 3 - Integracao espacial
    estacoes_gira = spatial.construir_estacoes_gira(historico_limpo)
    cobertura, pertenca = spatial.integracao_espacial(
        estacoes_gira, metro_limpo, ciclavel_limpo)
    qualidade["integracao_espacial"] = {
        "n_estacoes_gira": int(len(estacoes_gira)),
        "n_estacoes_metro": int(len(cobertura)),
        "raio_influencia_m": config.RAIO_INFLUENCIA_M,
        "n_metro_sem_gira_no_buffer": int(
            (cobertura["n_gira_influencia"] == 0).sum()),
        "comp_ciclavel_total_m": round(
            float(cobertura["comp_ciclavel_m"].sum()), 2),
    }

    # Etapa 4 - Variaveis derivadas
    agg_estacao, agg_estacao_hora, q_derive = derive.calcular_variaveis_derivadas(
        historico_limpo, estacoes_gira)
    qualidade["variaveis_derivadas"] = q_derive

    config.DIR_REPORTS.mkdir(parents=True, exist_ok=True)
    with open(config.RELATORIO_QUALIDADE, "w", encoding="utf-8") as f:
        json.dump(qualidade, f, ensure_ascii=False, indent=2)

    return {
        "historico_limpo": historico_limpo,
        "estacoes_gira": estacoes_gira,
        "metro_limpo": metro_limpo,
        "ciclavel_limpo": ciclavel_limpo,
        "cobertura": cobertura,
        "pertenca": pertenca,
        "agg_estacao": agg_estacao,
        "agg_estacao_hora": agg_estacao_hora,
        "qualidade": qualidade,
    }


if __name__ == "__main__":
    # Silencia o ruido cosmetico de avisos do pandas/geopandas/shapely nesta
    # execucao offline (ver nota igual em construir_modelo.py). Deliberado e
    # limitado a este script: NAO afeta o runtime do dashboard.
    warnings.filterwarnings("ignore")
    resultado = correr_etl()
    print(json.dumps(resultado["qualidade"], ensure_ascii=False, indent=2))
