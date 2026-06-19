"""
Indicadores do Grupo 1 - Disponibilidade GIRA, por estacao GIRA.

Notacao: b_i disponibilidade media da estacao i; b_ih media a hora h.

- Indice variabilidade:    IVD_i = sqrt( (1/24) Σ_h (b_ih - b_i)^2 )
- Hora de pico:            h*_i = argmin_h b_ih  (hora de MENOR disponibilidade)

Para estacoes sem cobertura das 24 horas, o somatorio do IVD e dividido pelo
numero de horas efetivamente presentes (coincide com 1/24 na cobertura completa).
b_{i,h*} (disponibilidade na hora de pico) e exposta para o disp_pico do Grupo 2.
"""

import numpy as np
import pandas as pd


def calcular_grupo1(agg_estacao, agg_estacao_hora):
    """Calcula os indicadores do Grupo 1. Retorna DataFrame indexado por id_estacao."""
    # Matriz estacao x hora (b_ih).
    pivot = agg_estacao_hora.pivot(
        index="id_estacao", columns="hora", values="media_bicicletas")

    b_i = agg_estacao["media_bicicletas"].reindex(pivot.index)

    # IVD: divisor = horas presentes (=24 na cobertura total) para nao penalizar
    # estacoes com cobertura horaria parcial.
    desvios2 = pivot.sub(b_i, axis=0) ** 2
    n_horas = pivot.notna().sum(axis=1)
    ivd = np.sqrt(desvios2.sum(axis=1) / n_horas)

    # Hora de pico = hora de MENOR disponibilidade.
    hora_pico = pivot.idxmin(axis=1)

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
