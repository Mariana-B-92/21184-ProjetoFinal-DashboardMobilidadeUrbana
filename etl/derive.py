"""
ETL - Etapa 4: Calculo de variaveis derivadas.

Calcula as variaveis que alimentam diretamente os indicadores do Grupo 1:
- taxa de ocupacao instantanea por observacao: b_i(t) / D_i, onde D_i e a
  capacidade (total de docas) da estacao. Limitada a [0, 1] quando configurado,
  garantindo que a taxa media de disponibilidade fica em [0, 1] "por construcao";
- agregacoes temporais de disponibilidade: media por estacao e media por
  (estacao, hora do dia).

Estas agregacoes sao consumidas pelo modulo kpis/grupo1.py, que materializa os
indicadores. A separacao mantem o ETL responsavel pelas agregacoes e o modulo de
KPIs responsavel pela formula de cada indicador.
"""

import config


def calcular_variaveis_derivadas(historico_limpo, estacoes_gira):
    """Calcula a taxa de ocupacao instantanea e as agregacoes temporais.

    Retorna (agg_estacao, agg_estacao_hora, qualidade):
    - agg_estacao: por id_estacao -> media_bicicletas, media_taxa_ocupacao, n_obs;
    - agg_estacao_hora: por (id_estacao, hora) -> media_bicicletas, n_obs;
    - qualidade: estatisticas para o relatorio (clamps, cobertura horaria).
    """
    q = {}
    df = historico_limpo.copy()

    # Capacidade D_i (total de docas) por estacao, vinda da entidade EstacaoGIRA.
    docas = estacoes_gira.set_index("id_estacao")["total_docas"]
    df["D_i"] = df["id_estacao"].map(docas).astype("int32")

    # Taxa de ocupacao instantanea: b_i(t) / D_i.
    taxa = df["numbicicletas"] / df["D_i"]
    if config.LIMITAR_TAXA_OCUPACAO:
        n_clamp = int((taxa > 1).sum() + (taxa < 0).sum())
        taxa = taxa.clip(lower=0, upper=1)
        q["registos_taxa_limitada"] = n_clamp
    df["taxa_ocupacao"] = taxa

    # Agregacao por estacao.
    agg_estacao = df.groupby("id_estacao").agg(
        media_bicicletas=("numbicicletas", "mean"),
        media_taxa_ocupacao=("taxa_ocupacao", "mean"),
        n_obs=("numbicicletas", "size"),
    )

    # Agregacao por estacao x hora do dia (base do IVD e da hora de pico).
    agg_estacao_hora = df.groupby(["id_estacao", "hora"]).agg(
        media_bicicletas=("numbicicletas", "mean"),
        n_obs=("numbicicletas", "size"),
    ).reset_index()

    # Cobertura horaria: estacoes sem as 24 horas presentes.
    horas_presentes = agg_estacao_hora.groupby("id_estacao")["hora"].nunique()
    incompletas = horas_presentes[horas_presentes < 24]
    q["n_estacoes_sem_24h"] = int(len(incompletas))
    q["estacoes_sem_24h"] = {int(k): int(v) for k, v in incompletas.items()}

    return agg_estacao, agg_estacao_hora, q
