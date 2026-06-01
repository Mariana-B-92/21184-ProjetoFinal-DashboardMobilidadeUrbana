"""
Indicadores do Grupo 2 - Cobertura de Infraestrutura.

Materializa a entidade IndicadorCoberturaMetro, por estacao de metro, combinando
as medidas espaciais (Etapa 3 do ETL) com os indicadores de disponibilidade
(Grupo 1) e o Indice de Intermodalidade Composto.

Indicadores (documento das metricas):
- Distancia a estacao GIRA mais proxima: d_min(j)          [Etapa 3]
- N.o de estacoes GIRA na area de influencia: N_GIRA(j)    [Etapa 3]
- Comprimento de rede ciclavel na area de influencia: L(j) [Etapa 3, intersecao]
- Disponibilidade media nas horas de pico individuais: disp_pico(j)
- Indice de Intermodalidade Composto: IIC(j)               [modulo iic]

disp_pico(j) = (1/|Gj(R)|) Σ_{i∈Gj(R)} b_{i,h*_i}
onde Gj(R) e o conjunto de estacoes GIRA na area de influencia de j e b_{i,h*_i}
a disponibilidade media da estacao i na sua hora de pico (Grupo 1).
Quando Gj(R) = ∅, disp_pico(j) = 0.
"""

from kpis import iic


def calcular_disp_pico(pertenca, indicadores_grupo1):
    """Disponibilidade media nas horas de pico individuais, por estacao de metro.

    pertenca: dict {id_metro: [id_estacao GIRA no buffer]}.
    indicadores_grupo1: DataFrame indexado por id_estacao com a coluna
        'disponibilidade_hora_pico' (b_{i,h*_i}).
    """
    disp_hora_pico = indicadores_grupo1["disponibilidade_hora_pico"]
    valores = {}
    for id_metro, ids_gira in pertenca.items():
        if not ids_gira:
            valores[id_metro] = 0.0  # Gj(R) vazio
        else:
            valores[id_metro] = float(
                disp_hora_pico.reindex(ids_gira).mean())
    return valores


def calcular_grupo2(cobertura, pertenca, indicadores_grupo1):
    """Calcula os indicadores do Grupo 2 por estacao de metro.

    cobertura: GeoDataFrame da Etapa 3 (dist_gira_min_m, n_gira_influencia,
        comp_ciclavel_m, geometria do ponto e do buffer).
    Retorna um DataFrame indexado por id_metro.
    """
    df = cobertura.set_index("id_metro").copy()

    # disp_pico(j) a partir da pertenca e do Grupo 1.
    disp_pico = calcular_disp_pico(pertenca, indicadores_grupo1)
    df["disp_pico"] = df.index.map(disp_pico)

    # IIC e componentes normalizadas.
    componentes = iic.calcular_iic(
        df["dist_gira_min_m"], df["n_gira_influencia"], df["comp_ciclavel_m"])
    df = df.join(componentes)

    colunas = ["nome_metro", "linha",
               "dist_gira_min_m", "n_gira_influencia", "comp_ciclavel_m",
               "disp_pico", "dist_truncada_m", "prox_norm", "n_gira_norm",
               "comp_ciclavel_norm", "iic", "geometry", "buffer"]
    return df[colunas]
