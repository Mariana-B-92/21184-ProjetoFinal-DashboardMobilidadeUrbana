"""
Camada de acesso a dados do dashboard.

Le o modelo integrado persistido em SQLite (gerado por construir_modelo.py) e
expoe-o as vistas da aplicacao Dash. Segue a arquitetura da seccao 2.2:
- as tabelas pequenas e as geometrias sao carregadas em memoria no arranque
  (reconstruidas a partir do WKT);
- a entidade temporal DisponibilidadeGIRA (~1.99 M registos) permanece em SQLite
  e e consultada a pedido, recorrendo aos indices, para nao sobrecarregar a
  memoria (restricao tecnologica do Capitulo 1).
"""

import sqlite3

import geopandas as gpd
import pandas as pd

import config

# Nomes legiveis dos dias da semana (0 = segunda-feira).
DIAS_SEMANA = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]


class RepositorioDados:
    """Ponto unico de acesso ao modelo integrado em SQLite."""

    def __init__(self, caminho_db=None):
        self.caminho_db = str(caminho_db or config.BASE_DADOS)
        # Estaticos carregados em memoria no arranque.
        self.estacoes_gira = self._carregar_estacoes_gira()
        self.estacoes_metro = self._carregar_estacoes_metro()
        self.rede_ciclavel = self._carregar_rede_ciclavel()
        # Versoes em CRS metrico, reutilizadas nas operacoes espaciais
        # (consistentes com a logica do ETL).
        self._gira_m = self.estacoes_gira.to_crs(config.CRS_METRICO)
        self._metro_m = (self.estacoes_metro.drop(columns=["buffer"])
                         .to_crs(config.CRS_METRICO))
        self._ciclavel_m = self.rede_ciclavel.to_crs(config.CRS_METRICO)

    # ------------------------------------------------------------------ #
    # Ligacao
    # ------------------------------------------------------------------ #
    def _ligar(self):
        # Modo so-leitura: o dashboard nunca escreve na base de dados.
        return sqlite3.connect(f"file:{self.caminho_db}?mode=ro", uri=True)

    def _ler(self, sql, params=None):
        with self._ligar() as conn:
            return pd.read_sql_query(sql, conn, params=params)

    @staticmethod
    def _para_geodataframe(df, coluna_wkt="geometria_wkt"):
        geom = gpd.GeoSeries.from_wkt(df[coluna_wkt], crs=config.CRS_GEOGRAFICO)
        return gpd.GeoDataFrame(df.drop(columns=[coluna_wkt]),
                                geometry=geom, crs=config.CRS_GEOGRAFICO)

    # ------------------------------------------------------------------ #
    # Estaticos (carregados no arranque)
    # ------------------------------------------------------------------ #
    def _carregar_estacoes_gira(self):
        """Estacoes GIRA (pontos) com os indicadores do Grupo 1."""
        df = self._ler("""
            SELECT g.id_estacao, g.nome_estacao, g.total_docas,
                   g.longitude, g.latitude, g.geometria_wkt,
                   i.disponibilidade_media, i.taxa_media_disponibilidade,
                   i.indice_variabilidade_diaria, i.hora_pico,
                   i.disponibilidade_hora_pico, i.n_horas_presentes
            FROM EstacaoGIRA g
            LEFT JOIN IndicadorDisponibilidadeGIRA i
                   ON g.id_estacao = i.id_estacao
        """)
        return self._para_geodataframe(df)

    def _carregar_estacoes_metro(self):
        """Estacoes de metro (pontos) com indicadores do Grupo 2 e buffer."""
        df = self._ler("""
            SELECT id_metro, nome_metro, linha,
                   dist_gira_min_m, n_gira_influencia, comp_ciclavel_m,
                   disp_pico, dist_truncada_m, prox_norm, n_gira_norm,
                   comp_ciclavel_norm, iic, geometria_wkt, buffer_wkt
            FROM IndicadorCoberturaMetro
        """)
        gdf = self._para_geodataframe(df)
        # Buffer (area de influencia) como coluna geometrica auxiliar.
        gdf["buffer"] = gpd.GeoSeries.from_wkt(
            df["buffer_wkt"], crs=config.CRS_GEOGRAFICO).values
        return gdf

    def _carregar_rede_ciclavel(self):
        """Segmentos cicláveis executados (linhas)."""
        df = self._ler("""
            SELECT id_segmento, designacao, tipologia, nivel_segregacao,
                   freguesia, comprimento_m, comp_km, geometria_wkt
            FROM RedeCiclavel
        """)
        return self._para_geodataframe(df)

    # ------------------------------------------------------------------ #
    # Consultas a pedido (entidade temporal grande)
    # ------------------------------------------------------------------ #
    def serie_temporal(self, id_estacao, inicio=None, fim=None, frequencia=None):
        """Serie temporal de disponibilidade de uma estacao GIRA.

        inicio/fim: datas (YYYY-MM-DD) que restringem o periodo (filtro sobre a
            coluna 'data', lexicograficamente segura).
        frequencia: se indicada (ex.: 'D', 'h'), reamostra a media server-side
            para reduzir o volume enviado as vistas.
        """
        sql = ("SELECT timestamp, numbicicletas, numdocas "
               "FROM DisponibilidadeGIRA WHERE id_estacao = ?")
        params = [int(id_estacao)]
        if inicio:
            sql += " AND data >= ?"
            params.append(str(inicio))
        if fim:
            sql += " AND data <= ?"
            params.append(str(fim))

        df = self._ler(sql, params)
        if df.empty:
            return df
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, format="mixed")
        df = df.sort_values("timestamp")

        if frequencia:
            df = (df.set_index("timestamp")
                    .resample(frequencia)["numbicicletas"].mean()
                    .reset_index())
        return df

    def heatmap_disponibilidade(self, id_estacao):
        """Disponibilidade media por dia da semana x hora do dia (matriz 7x24)."""
        df = self._ler("""
            SELECT dia_semana, hora, AVG(numbicicletas) AS media
            FROM DisponibilidadeGIRA
            WHERE id_estacao = ?
            GROUP BY dia_semana, hora
        """, [int(id_estacao)])
        if df.empty:
            return df
        matriz = (df.pivot(index="dia_semana", columns="hora", values="media")
                    .reindex(index=range(7), columns=range(24)))
        matriz.index = [DIAS_SEMANA[i] for i in matriz.index]
        return matriz

    # ------------------------------------------------------------------ #
    # Cobertura espacial de uma estacao de metro (analise de cobertura)
    # ------------------------------------------------------------------ #
    def cobertura_metro(self, id_metro, raio=None):
        """Area de influencia de uma estacao de metro e elementos contidos.

        Calculado em CRS metrico (consistente com o ETL) e devolvido em WGS84:
          - buffer: poligono da area de influencia (raio R);
          - gira: estacoes GIRA dentro da area;
          - ciclavel: porcoes de segmentos cicláveis contidas no buffer.
        """
        raio = raio if raio is not None else config.RAIO_INFLUENCIA_M
        metro = self._metro_m[self._metro_m["id_metro"] == id_metro]
        if metro.empty:
            return None
        ponto = metro.geometry.iloc[0]
        buffer_m = ponto.buffer(raio)

        # Estacoes GIRA na area de influencia.
        distancias = self._gira_m.geometry.distance(ponto)
        idx_dentro = distancias.index[distancias <= raio]
        gira_dentro = self.estacoes_gira.loc[idx_dentro]

        # Porcoes de rede ciclavel contidas no buffer (intersecao).
        intersecao = self._ciclavel_m.geometry.intersection(buffer_m)
        intersecao = intersecao[~intersecao.is_empty]

        buffer_wgs = gpd.GeoSeries([buffer_m], crs=config.CRS_METRICO).to_crs(
            config.CRS_GEOGRAFICO).iloc[0]
        ciclavel_wgs = gpd.GeoSeries(intersecao.values,
                                     crs=config.CRS_METRICO).to_crs(
            config.CRS_GEOGRAFICO)

        return {"buffer": buffer_wgs, "gira": gira_dentro,
                "ciclavel": ciclavel_wgs}

    def indicadores_metro(self, id_metro):
        """Linha de indicadores do Grupo 2 de uma estacao de metro."""
        sel = self.estacoes_metro[self.estacoes_metro["id_metro"] == id_metro]
        return None if sel.empty else sel.iloc[0]
