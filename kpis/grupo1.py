"""
Indicadores do Grupo 1 - Disponibilidade GIRA.

Materializa a entidade IndicadorDisponibilidadeGIRA, calculada por estacao GIRA
a partir das agregacoes temporais produzidas na Etapa 4 do ETL.

Formulas (documento das metricas), com b_i a disponibilidade media de bicicletas
da estacao i e b_ih a media a hora h:

- Disponibilidade media:   b_i = (1/n) Σ_t b_i(t)
- Taxa media disponib.:    TMD_i = (1/n) Σ_t b_i(t)/D_i        (em [0,1])
- Indice variabilidade:    IVD_i = sqrt( (1/24) Σ_h (b_ih - b_i)^2 )
- Hora de pico:            h*_i = argmin_h b_ih  (hora de MENOR disponibilidade)

Adaptacao documentada: para estacoes sem cobertura das 24 horas, o somatorio do
IVD e dividido pelo numero de horas efetivamente presentes (coincide com 1/24 na
cobertura completa). O numero de horas presentes e guardado para interpretacao.

Calcula-se ainda b_{i,h*} (disponibilidade media na hora de pico), variavel
intermedia necessaria ao indicador disp_pico do Grupo 2.
"""

import numpy as np
import pandas as pd


def calcular_grupo1(agg_estacao, agg_estacao_hora):
    """Calcula os indicadores do Grupo 1 por estacao GIRA.

    Retorna um DataFrame indexado por id_estacao.
    """
    # Matriz estacao x hora com a media de bicicletas (b_ih).
    pivot = agg_estacao_hora.pivot(
        index="id_estacao", columns="hora", values="media_bicicletas")

    # Disponibilidade media global por estacao (b_i), alinhada ao pivot.
    b_i = agg_estacao["media_bicicletas"].reindex(pivot.index)

    # Indice de variabilidade diaria: RMS dos desvios das medias horarias
    # face a b_i, dividido pelo n.o de horas presentes (=24 na cobertura total).
    desvios2 = pivot.sub(b_i, axis=0) ** 2
    n_horas = pivot.notna().sum(axis=1)
    ivd = np.sqrt(desvios2.sum(axis=1) / n_horas)

    # Hora de pico: hora de menor disponibilidade media.
    hora_pico = pivot.idxmin(axis=1)

    # Disponibilidade media na hora de pico (b_{i,h*}).
    disp_hora_pico = pd.Series(
        pivot.to_numpy()[np.arange(len(pivot)),
                         pivot.columns.get_indexer(hora_pico)],
        index=pivot.index,
    )

    resultado = pd.DataFrame({
        "disponibilidade_media": b_i,
        "taxa_media_disponibilidade": agg_estacao["media_taxa_ocupacao"]
            .reindex(pivot.index),
        "indice_variabilidade_diaria": ivd,
        "hora_pico": hora_pico.astype("int32"),
        "disponibilidade_hora_pico": disp_hora_pico,
        "n_horas_presentes": n_horas.astype("int32"),
    })
    resultado.index.name = "id_estacao"
    return resultado
