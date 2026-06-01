"""
Indice de Intermodalidade Composto (IIC).

Indicador-sintese do Grupo 2, combina tres dimensoes (proximidade, densidade e
conectividade ciclavel) num unico valor em [0, 1], por estacao de metro.

Implementacao fiel a subseccao 2.3.2.1 do documento das metricas:

1. Pre-processamento da distancia: d_min(j) e truncada a d_max = 1000 m ANTES
   da normalizacao. A normalizacao min-max e aplicada sobre a distancia truncada.
2. Normalizacao min-max sobre o conjunto M de estacoes de metro:
     N(j) = (N_GIRA(j) - min(N)) / (max(N) - min(N))
     L(j) = (L_ciclavel(j) - min(L)) / (max(L) - min(L))
     prox(j) = 1 - (d_trunc(j) - min(d)) / (max(d) - min(d))     [proximidade]
   Caso-limite: se max(x) == min(x), atribui-se o valor neutro 0,5 a todas as
   estacoes para essa variavel (evita divisao por zero).
3. Agregacao: IIC(j) = w1*prox + w2*N + w3*L, com w1+w2+w3 = 1.

A normalizacao e recalculada a cada execucao, refletindo a distribuicao
observada das variaveis no conjunto analisado.
"""

import pandas as pd

import config


def normalizar_minmax(serie):
    """Normalizacao min-max em [0, 1] com tratamento do caso max == min.

    Quando todos os valores sao iguais, devolve o valor neutro (0,5) para toda
    a serie, evitando divisao por zero (caso-limite documentado).
    """
    minimo = serie.min()
    maximo = serie.max()
    if maximo == minimo:
        return pd.Series(config.VALOR_NEUTRO_NORMALIZACAO, index=serie.index)
    return (serie - minimo) / (maximo - minimo)


def calcular_iic(dist_gira_min, n_gira, comp_ciclavel, pesos=None):
    """Calcula o IIC e as suas componentes normalizadas por estacao de metro.

    Recebe tres Series alinhadas (indexadas por estacao de metro) e devolve um
    DataFrame com a distancia truncada, as tres componentes normalizadas e o IIC.
    """
    pesos = pesos or config.PESOS_IIC

    # 1. Truncatura da distancia antes da normalizacao.
    dist_truncada = dist_gira_min.clip(upper=config.DISTANCIA_MAX_TRUNCATURA_M)

    # 2. Normalizacao min-max.
    # Proximidade = complementar da distancia normalizada (menor distancia melhor).
    prox = 1 - normalizar_minmax(dist_truncada)
    n_norm = normalizar_minmax(n_gira)
    l_norm = normalizar_minmax(comp_ciclavel)

    # 3. Agregacao (media ponderada).
    iic = (pesos["proximidade"] * prox
           + pesos["densidade"] * n_norm
           + pesos["ciclavel"] * l_norm)

    return pd.DataFrame({
        "dist_truncada_m": dist_truncada,
        "prox_norm": prox,
        "n_gira_norm": n_norm,
        "comp_ciclavel_norm": l_norm,
        "iic": iic,
    })
