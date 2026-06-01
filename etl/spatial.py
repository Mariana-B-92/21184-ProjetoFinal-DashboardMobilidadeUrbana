"""
ETL - Etapa 3: Integracao espacial.

Com vista ao calculo dos indicadores de cobertura (Grupo 2), esta etapa:
- materializa a entidade base EstacaoGIRA (pontos unicos a partir do historico);
- reprojeta os dados geograficos para um CRS metrico (EPSG:3763), permitindo
  operacoes de distancia em metros;
- cria a area de influencia (buffer de raio R) em torno de cada estacao de metro;
- calcula, por estacao de metro, as distancias e contagens necessarias aos
  indicadores de cobertura.

Implementacao fiel ao documento das metricas:
- d_min(j): distancia minima a qualquer estacao GIRA (sobre todo o conjunto G);
- N_GIRA(j): numero de estacoes GIRA com dist(j,i) <= R;
- L_ciclavel(j): SOMA dos comprimentos das PORCOES de segmento contidas no buffer
  (intersecao geometrica segmento ∩ A_j(R)), evitando a sobrestimacao que
  resultaria de somar comprimentos totais de segmentos que apenas intersetam
  parcialmente a area de influencia.

A disponibilidade media nas horas de pico (disp_pico) NAO e calculada aqui:
depende da hora de pico individual (Grupo 1). Esta etapa devolve, para esse
efeito, a pertenca de cada estacao GIRA ao buffer de cada estacao de metro.
"""

import geopandas as gpd
import pandas as pd

import config


def construir_estacoes_gira(historico_limpo):
    """Materializa a entidade base EstacaoGIRA a partir do historico limpo.

    Coordenada representativa = mediana por estacao (robusta a ruido de GPS).
    Capacidade (total de docas) = maximo de docas observado por estacao.
    Retorna um GeoDataFrame de pontos em EPSG:4326.
    """
    agreg = historico_limpo.groupby("id_estacao").agg(
        nome_estacao=("nome_estacao", "first"),
        longitude=("longitude", "median"),
        latitude=("latitude", "median"),
        total_docas=("numdocas", "max"),
    ).reset_index()

    return gpd.GeoDataFrame(
        agreg,
        geometry=gpd.points_from_xy(agreg["longitude"], agreg["latitude"]),
        crs=config.CRS_GEOGRAFICO,
    )


def integracao_espacial(estacoes_gira, metro_limpo, ciclavel_limpo,
                        raio=None):
    """Calcula as medidas espaciais por estacao de metro.

    Retorna (gdf_cobertura, pertenca):
    - gdf_cobertura: GeoDataFrame (uma linha por estacao de metro) com
      dist_gira_min_m, n_gira_influencia e comp_ciclavel_m, mais a geometria
      do ponto e do buffer (ambas em EPSG:4326, para o mapa e persistencia WKT);
    - pertenca: dict {id_metro: [id_estacao GIRA dentro do buffer]}, necessario
      ao calculo posterior da disponibilidade nas horas de pico.
    """
    raio = raio if raio is not None else config.RAIO_INFLUENCIA_M

    # Reprojecao para CRS metrico (distancias/buffers em metros).
    gira_m = estacoes_gira.to_crs(config.CRS_METRICO)
    metro_m = metro_limpo.to_crs(config.CRS_METRICO)
    ciclavel_m = ciclavel_limpo.to_crs(config.CRS_METRICO)

    gira_ids = gira_m["id_estacao"].to_numpy()
    geom_ciclavel = ciclavel_m.geometry

    linhas = []
    pertenca = {}

    for _, metro in metro_m.iterrows():
        id_metro = int(metro["OBJECTID"])
        ponto = metro.geometry
        buffer_geom = ponto.buffer(raio)

        # Distancias do ponto de metro a todas as estacoes GIRA (conjunto G).
        distancias = gira_m.geometry.distance(ponto)

        dist_min = float(distancias.min())
        dentro = distancias <= raio
        n_gira = int(dentro.sum())
        ids_dentro = [int(x) for x in gira_ids[dentro.to_numpy()]]

        # Comprimento ciclavel = soma das PORCOES contidas no buffer (intersecao).
        intersecao = geom_ciclavel.intersection(buffer_geom)
        comp_ciclavel = float(intersecao.length.sum())

        pertenca[id_metro] = ids_dentro
        linhas.append({
            "id_metro": id_metro,
            "nome_metro": metro["NOME"],
            "linha": metro["LINHA"],
            "dist_gira_min_m": round(dist_min, 2),
            "n_gira_influencia": n_gira,
            "comp_ciclavel_m": round(comp_ciclavel, 2),
            "geometry": ponto,       # ponto em CRS metrico (reprojeta-se a seguir)
            "buffer": buffer_geom,   # buffer em CRS metrico
        })

    cobertura_m = gpd.GeoDataFrame(linhas, geometry="geometry",
                                   crs=config.CRS_METRICO)

    # Reprojecao de volta para WGS84 (mapa Leaflet e persistencia em WKT).
    cobertura = cobertura_m.to_crs(config.CRS_GEOGRAFICO)
    buffers_wgs = gpd.GeoSeries(cobertura_m["buffer"],
                                crs=config.CRS_METRICO).to_crs(
        config.CRS_GEOGRAFICO)
    cobertura["buffer"] = buffers_wgs.values

    return cobertura, pertenca
