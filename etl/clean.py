"""
ETL - Etapa 2: Limpeza e normalizacao.

Resolve os problemas de qualidade identificados na seccao 2.3.1 e uniformiza a
estrutura dos dados:
- parsing do identificador de estacao (embebido em 'desigcomercial');
- parsing das coordenadas (embebidas em 'position' como GeoJSON string);
- conversao dos timestamps de UTC para hora local (Europe/Lisbon);
- remocao de duplicados e tratamento de valores em falta;
- filtragem dos registos relevantes (estado, situacao de execucao/funcionamento).

Cada operacao alimenta um dicionario de qualidade, base do relatorio gerado na
Etapa 5. As decisoes de tratamento sao controladas por config.py.

Nota: o calculo da taxa de ocupacao instantanea pertence a Etapa 4 (variaveis
derivadas), pelo que NAO e feito aqui; apenas se contabilizam, para o relatorio,
os registos com numbicicletas > numdocas.
"""

import pandas as pd

import config


def _registar(qualidade, chave, valor):
    qualidade[chave] = valor


def limpar_historico_gira(historico):
    """Limpa e normaliza o historico GIRA concatenado.

    Retorna (DataFrame_limpo, dict_qualidade).
    """
    q = {}
    _registar(q, "registos_iniciais", int(len(historico)))

    df = historico.copy()

    # --- Parsing do identificador de estacao (prefixo numerico) ---
    # ex.: "417 - Av. Duque de Avila / Jardim Arco Do Cego" -> 417
    df["id_estacao"] = (
        df["desigcomercial"].str.extract(r"^\s*(\d+)", expand=False)
    )
    sem_id = int(df["id_estacao"].isna().sum())
    _registar(q, "registos_sem_id_estacao", sem_id)
    df = df.dropna(subset=["id_estacao"])
    df["id_estacao"] = df["id_estacao"].astype("int32")
    # Designacao "limpa" sem o prefixo numerico, para apresentacao.
    df["nome_estacao"] = (
        df["desigcomercial"].str.replace(r"^\s*\d+\s*-\s*", "", regex=True)
        .str.strip()
    )

    # --- Parsing das coordenadas embebidas no campo 'position' ---
    coords = df["position"].str.extract(
        r"\[\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*\]"
    )
    df["longitude"] = pd.to_numeric(coords[0], errors="coerce")
    df["latitude"] = pd.to_numeric(coords[1], errors="coerce")
    sem_coords = int(df[["longitude", "latitude"]].isna().any(axis=1).sum())
    _registar(q, "registos_sem_coordenadas", sem_coords)
    df = df.dropna(subset=["longitude", "latitude"])

    # --- Conversao de timestamps UTC -> hora local ---
    ts = pd.to_datetime(df["entity_ts"], utc=True, errors="coerce")
    sem_ts = int(ts.isna().sum())
    _registar(q, "registos_sem_timestamp", sem_ts)
    df = df.loc[ts.notna()].copy()
    ts = ts.loc[df.index]
    df["timestamp"] = ts.dt.tz_convert(config.FUSO_HORARIO)
    df["data"] = df["timestamp"].dt.date
    df["hora"] = df["timestamp"].dt.hour
    df["dia_semana"] = df["timestamp"].dt.dayofweek  # 0=segunda ... 6=domingo

    # --- Valores em falta nos campos de disponibilidade ---
    nulos_disp = int(df[["numbicicletas", "numdocas"]].isna().any(axis=1).sum())
    _registar(q, "registos_com_disponibilidade_nula", nulos_disp)
    df = df.dropna(subset=["numbicicletas", "numdocas"])
    df["numbicicletas"] = df["numbicicletas"].astype("int32")
    df["numdocas"] = df["numdocas"].astype("int32")

    # --- Remocao de duplicados ---
    antes = len(df)
    df = df.drop_duplicates(subset=["id_estacao", "timestamp"])
    _registar(q, "duplicados_removidos", int(antes - len(df)))

    # --- Anomalia: numbicicletas > numdocas (TMD sairia de [0,1]) ---
    # Apenas contabilizado aqui; o clamp efetivo ocorre na Etapa 4 / KPIs.
    _registar(q, "registos_bicicletas_superior_docas",
              int((df["numbicicletas"] > df["numdocas"]).sum()))

    # --- Distribuicao de estados (antes de filtrar) ---
    _registar(q, "distribuicao_estado",
              {str(k): int(v) for k, v in df["estado"].value_counts().items()})

    # --- Filtro: manter so o estado "active" (configuravel) ---
    # So "active" e oferta efetiva; todos os outros estados (incluindo "repair")
    # sao removidos. O contador agrega esses registos nao-active removidos.
    if config.EXCLUIR_ESTADO_REPAIR:
        antes = len(df)
        df = df[df["estado"] == "active"]
        _registar(q, "registos_repair_removidos", int(antes - len(df)))
    else:
        _registar(q, "registos_repair_removidos", 0)

    # --- Filtro: docas == 0 (configuravel; evita divisao por zero no TMD) ---
    if config.REMOVER_DOCAS_ZERO:
        antes = len(df)
        df = df[df["numdocas"] > 0]
        _registar(q, "registos_docas_zero_removidos", int(antes - len(df)))
    else:
        _registar(q, "registos_docas_zero_removidos", 0)

    # --- Resumo final ---
    _registar(q, "registos_finais", int(len(df)))
    _registar(q, "n_estacoes_distintas", int(df["id_estacao"].nunique()))
    _registar(q, "intervalo_temporal", {
        "inicio": str(df["timestamp"].min()),
        "fim": str(df["timestamp"].max()),
    })

    colunas = ["id_estacao", "nome_estacao", "longitude", "latitude",
               "timestamp", "data", "hora", "dia_semana",
               "numbicicletas", "numdocas", "estado"]
    return df[colunas].reset_index(drop=True), q


def limpar_metro(gdf):
    """Filtra estacoes de metro em funcionamento e valida geometrias."""
    q = {"registos_iniciais": int(len(gdf))}
    g = gdf[gdf["SITUACAO"] == config.SITUACAO_METRO_VALIDA].copy()
    g = g[g.geometry.notna() & g.geometry.is_valid]
    q["registos_finais"] = int(len(g))
    return g.reset_index(drop=True), q


def limpar_ciclavel(gdf):
    """Filtra segmentos ciclaveis executados e remove geometrias nulas."""
    q = {"registos_iniciais": int(len(gdf))}
    g = gdf[gdf["SITUACAO"] == config.SITUACAO_CICLAVEL_VALIDA].copy()
    nulas = int(g.geometry.isna().sum())
    q["geometrias_nulas_removidas"] = nulas
    g = g[g.geometry.notna() & g.geometry.is_valid]
    q["registos_finais"] = int(len(g))
    return g.reset_index(drop=True), q
