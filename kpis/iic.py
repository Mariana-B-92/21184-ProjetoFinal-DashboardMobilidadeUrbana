"""
Indice de Intermodalidade Composto (IIC), por estacao de metro.

Combina proximidade, densidade e conectividade ciclavel num valor em [0, 1].

1. d_min(j) e truncada a d_max ANTES da normalizacao (limita o efeito de
   estacoes muito distantes na escala min-max).
2. Normalizacao min-max sobre o conjunto de estacoes de metro; proximidade e o
   complementar (1 - dist normalizada). Se max(x) == min(x), valor neutro 0,5
   para essa variavel (evita divisao por zero).
3. IIC(j) = w1*prox + w2*N + w3*L, com w1+w2+w3 = 1.

A normalizacao e recalculada a cada execucao sobre a distribuicao observada.
"""

import pandas as pd

import config


def normalizar_minmax(serie):
    """Normalizacao min-max em [0, 1].

    Se max == min (todos os valores iguais), devolve o valor neutro 0,5 para
    evitar divisao por zero.
    """
    minimo = serie.min()
    maximo = serie.max()
    if maximo == minimo:
        return pd.Series(config.VALOR_NEUTRO_NORMALIZACAO, index=serie.index)
    return (serie - minimo) / (maximo - minimo)


def calcular_iic(dist_gira_min, n_gira, comp_ciclavel, pesos=None):
    """Calcula o IIC e as suas componentes normalizadas por estacao de metro.

    Recebe tres Series alinhadas (indexadas por estacao de metro).
    """
    pesos = pesos or config.PESOS_IIC

    dist_truncada = dist_gira_min.clip(upper=config.DISTANCIA_MAX_TRUNCATURA_M)

    # Proximidade = complementar da distancia normalizada (menor distancia melhor).
    prox = 1 - normalizar_minmax(dist_truncada)
    n_norm = normalizar_minmax(n_gira)
    l_norm = normalizar_minmax(comp_ciclavel)

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
