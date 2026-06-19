"""Integracao espacial: materializa a entidade EstacaoGIRA, reprojeta para CRS
metrico e calcula, por estacao de metro, distancia minima a GIRA, contagem de
estacoes GIRA no buffer de raio R e comprimento ciclavel contido nesse buffer."""

import geopandas as gpd

import config


def construir_estacoes_gira(historico_limpo):
    """Materializa a entidade EstacaoGIRA (pontos unicos) a partir do historico.

    Coordenada representativa = mediana por estacao (robusta a ruido de GPS).
    Capacidade (total de docas) = maximo de docas observado por estacao.
    Retorna um GeoDataFrame de pontos em CRS geografico.
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
      do ponto e do buffer (ambas em CRS geografico, para mapa e persistencia WKT);
    - pertenca: dict {id_metro: [id_estacao GIRA dentro do buffer]}.
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

        distancias = gira_m.geometry.distance(ponto)

        dist_min = float(distancias.min())
        dentro = distancias <= raio
        n_gira = int(dentro.sum())
        ids_dentro = [int(x) for x in gira_ids[dentro.to_numpy()]]

        # Soma so as porcoes contidas no buffer (intersecao), evitando
        # sobrestimar com segmentos que apenas o intersetam parcialmente.
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
