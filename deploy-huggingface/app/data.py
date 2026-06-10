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

import json
import sqlite3
from pathlib import Path

import geopandas as gpd
import pandas as pd

import config

# Nomes legiveis dos dias da semana (0 = segunda-feira).
DIAS_SEMANA = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]


class RepositorioDados:
    """Ponto unico de acesso ao modelo integrado em SQLite."""

    def __init__(self, caminho_db=None):
        self.caminho_db = str(caminho_db or config.BASE_DADOS)
        # Pre-condicao: o modelo integrado tem de existir. Se ainda nao foi
        # construido, o erro nativo do SQLite ("unable to open database file")
        # e criptico; aqui devolve-se uma instrucao acionavel.
        if not Path(self.caminho_db).exists():
            raise FileNotFoundError(
                f"Base de dados nao encontrada em '{self.caminho_db}'.\n"
                "Corra primeiro a fase offline para a gerar:\n"
                "    python construir_modelo.py")
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
        # Cache dos agregados globais (heatmap/serie de TODAS as GIRA), que sao
        # consultas pesadas; evita repeti-las ao alternar a selecao com o mesmo
        # periodo. Chave: (tipo, inicio, fim).
        self._cache_global = {}
        # Cache da cobertura espacial por (id_metro, raio): a mesma selecao de
        # metro alimenta dois callbacks (indicadores e analise), que de outro
        # modo repetiriam o buffer e as intersecoes. Chave: (id_metro, raio).
        self._cache_cobertura = {}

    # ------------------------------------------------------------------ #
    # Ligacao
    # ------------------------------------------------------------------ #
    def _ligar(self):
        # Modo so-leitura: o dashboard nunca escreve na base de dados.
        return sqlite3.connect(f"file:{self.caminho_db}?mode=ro", uri=True)

    def _ler(self, sql, params=None):
        with self._ligar() as conn:
            return pd.read_sql_query(sql, conn, params=params)

    def _tem_tabela(self, nome):
        """Indica se uma tabela existe na base de dados."""
        df = self._ler(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            [nome])
        return not df.empty

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
        # Buffer (area de influencia) como coluna geometrica. A coluna de texto
        # buffer_wkt e descartada apos a reconstrucao, para nao viajar (WKT do
        # poligono) ate ao mapa e ao dcc.Store em cada selecao.
        gdf["buffer"] = gpd.GeoSeries.from_wkt(
            df["buffer_wkt"], crs=config.CRS_GEOGRAFICO).values
        return gdf.drop(columns=["buffer_wkt"])

    def _carregar_rede_ciclavel(self):
        """Segmentos ciclaveis executados (linhas)."""
        df = self._ler("""
            SELECT id_segmento, designacao, tipologia, nivel_segregacao,
                   freguesia, comprimento_m, comp_km, geometria_wkt
            FROM RedeCiclavel
        """)
        return self._para_geodataframe(df)

    # ------------------------------------------------------------------ #
    # Consultas a pedido (entidade temporal grande)
    # ------------------------------------------------------------------ #
    def intervalo_datas(self):
        """Intervalo de datas (min, max) coberto pelo historico GIRA.

        Devolve um par de strings 'YYYY-MM-DD'. A coluna 'data' e texto ISO,
        pelo que MIN/MAX lexicografico coincide com o cronologico. Usado para
        limitar o seletor de datas ao periodo realmente disponivel.
        """
        df = self._ler("SELECT MIN(data) AS inicio, MAX(data) AS fim "
                       "FROM DisponibilidadeGIRA")
        return df["inicio"].iloc[0], df["fim"].iloc[0]

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
        # Reconverte para hora local: a reamostragem diaria/horaria deve usar o
        # mesmo calendario local que o heatmap (que assenta em 'hora'/'dia_semana'
        # gravados em Europe/Lisbon). Sem isto, a serie seria agregada em UTC e
        # poderia divergir do heatmap junto a meia-noite.
        df["timestamp"] = (pd.to_datetime(df["timestamp"], utc=True, format="mixed")
                           .dt.tz_convert(config.FUSO_HORARIO))
        df = df.sort_values("timestamp")

        if frequencia:
            df = (df.set_index("timestamp")
                    .resample(frequencia)["numbicicletas"].mean()
                    .reset_index())
        return df

    def heatmap_disponibilidade(self, id_estacao, inicio=None, fim=None):
        """Disponibilidade media por dia da semana x hora do dia (matriz 7x24).

        Restringe-se ao periodo (inicio/fim) para acompanhar o filtro de datas,
        a par das series temporais.
        """
        sql = ("SELECT dia_semana, hora, AVG(numbicicletas) AS media "
               "FROM DisponibilidadeGIRA WHERE id_estacao = ?")
        params = [int(id_estacao)]
        if inicio:
            sql += " AND data >= ?"
            params.append(str(inicio))
        if fim:
            sql += " AND data <= ?"
            params.append(str(fim))
        sql += " GROUP BY dia_semana, hora"
        df = self._ler(sql, params)
        if df.empty:
            return df
        matriz = (df.pivot(index="dia_semana", columns="hora", values="media")
                    .reindex(index=range(7), columns=range(24)))
        matriz.index = [DIAS_SEMANA[i] for i in matriz.index]
        return matriz

    def serie_global(self, inicio=None, fim=None):
        """Serie diaria da disponibilidade media de bicicletas em TODAS as GIRA.

        Media sobre o conjunto de estacoes, por dia, restrita ao periodo. Usada
        na vista inicial (sem selecao). Resultado em cache por (inicio, fim).

        Le a tabela pre-agregada DisponibilidadeGlobalDiaria (gerada no ETL),
        instantanea. Se essa tabela nao existir, recorre ao agregado a pedido
        sobre o historico completo.
        """
        chave = ("serie", inicio, fim)
        if chave in self._cache_global:
            return self._cache_global[chave]
        pre = self._tem_tabela("DisponibilidadeGlobalDiaria")
        if pre:
            sql = "SELECT data, media FROM DisponibilidadeGlobalDiaria WHERE 1=1"
        else:
            sql = ("SELECT data, AVG(numbicicletas) AS media "
                   "FROM DisponibilidadeGIRA WHERE 1=1")
        params = []
        if inicio:
            sql += " AND data >= ?"
            params.append(str(inicio))
        if fim:
            sql += " AND data <= ?"
            params.append(str(fim))
        sql += " ORDER BY data" if pre else " GROUP BY data ORDER BY data"
        df = self._ler(sql, params)
        if not df.empty:
            df["data"] = pd.to_datetime(df["data"])
        self._cache_global[chave] = df
        return df

    def serie_conjunto(self, ids, inicio=None, fim=None):
        """Serie diaria da disponibilidade media de um CONJUNTO de estacoes GIRA
        (ex.: as contidas na area de influencia de um metro).

        Consulta filtrada por id_estacao IN (...), bem mais leve do que o
        agregado global; por isso nao usa cache.
        """
        ids = [int(i) for i in (ids or [])]
        if not ids:
            return pd.DataFrame()
        marcadores = ",".join("?" * len(ids))
        sql = ("SELECT data, AVG(numbicicletas) AS media "
               "FROM DisponibilidadeGIRA "
               f"WHERE id_estacao IN ({marcadores})")
        params = list(ids)
        if inicio:
            sql += " AND data >= ?"
            params.append(str(inicio))
        if fim:
            sql += " AND data <= ?"
            params.append(str(fim))
        sql += " GROUP BY data ORDER BY data"
        df = self._ler(sql, params)
        if not df.empty:
            df["data"] = pd.to_datetime(df["data"])
        return df

    def cobertura_metro(self, id_metro, raio=None):
        """Area de influencia de uma estacao de metro e elementos contidos.

        Calculado em CRS metrico (consistente com o ETL) e devolvido em WGS84.
        As medidas (n_gira, comp_ciclavel_m, disp_pico, dist_gira_min_m) sao
        calculadas para o raio indicado, permitindo a exploracao interativa do
        raio de influencia. Para raios diferentes do oficial (config), estas
        medidas sao exploratorias e nao substituem os indicadores persistidos.

        Devolve um dicionario com: buffer, gira, ciclavel (geometrias) e as
        medidas n_gira, comp_ciclavel_m, disp_pico, dist_gira_min_m.
        """
        raio = raio if raio is not None else config.RAIO_INFLUENCIA_M
        chave = (int(id_metro), raio)
        if chave in self._cache_cobertura:
            return self._cache_cobertura[chave]
        metro = self._metro_m[self._metro_m["id_metro"] == id_metro]
        if metro.empty:
            return None
        ponto = metro.geometry.iloc[0]
        buffer_m = ponto.buffer(raio)

        # Estacoes GIRA na area de influencia (e distancia minima, que nao
        # depende do raio, mas e devolvida por conveniencia).
        distancias = self._gira_m.geometry.distance(ponto)
        idx_dentro = distancias.index[distancias <= raio]
        gira_dentro = self.estacoes_gira.loc[idx_dentro]
        dist_min = float(distancias.min())

        # Porcoes de rede ciclavel contidas no buffer (intersecao).
        intersecao = self._ciclavel_m.geometry.intersection(buffer_m)
        intersecao = intersecao[~intersecao.is_empty]
        comp_ciclavel_m = float(intersecao.length.sum())

        # Disponibilidade media nas horas de pico das GIRA contidas (Grupo 2).
        if len(gira_dentro) > 0 and "disponibilidade_hora_pico" in gira_dentro:
            disp_pico = float(gira_dentro["disponibilidade_hora_pico"].mean())
        else:
            disp_pico = 0.0

        buffer_wgs = gpd.GeoSeries([buffer_m], crs=config.CRS_METRICO).to_crs(
            config.CRS_GEOGRAFICO).iloc[0]
        ciclavel_wgs = gpd.GeoSeries(intersecao.values,
                                     crs=config.CRS_METRICO).to_crs(
            config.CRS_GEOGRAFICO)

        resultado = {"buffer": buffer_wgs, "gira": gira_dentro,
                     "ciclavel": ciclavel_wgs,
                     "n_gira": len(gira_dentro),
                     "comp_ciclavel_m": comp_ciclavel_m,
                     "disp_pico": disp_pico,
                     "dist_gira_min_m": dist_min,
                     "raio": raio}
        self._cache_cobertura[chave] = resultado
        return resultado

    def indicadores_metro(self, id_metro):
        """Linha de indicadores do Grupo 2 de uma estacao de metro."""
        sel = self.estacoes_metro[self.estacoes_metro["id_metro"] == id_metro]
        return None if sel.empty else sel.iloc[0]

    # ------------------------------------------------------------------ #
    # Selecao por nome (mesma forma que o clique no mapa devolve)
    # ------------------------------------------------------------------ #
    def props_gira(self, id_estacao):
        """Propriedades de uma estacao GIRA no mesmo formato que o clickData do
        mapa (dicionario JSON-seguro, sem geometria)."""
        sel = self.estacoes_gira[self.estacoes_gira["id_estacao"]
                                 == int(id_estacao)]
        if sel.empty:
            return None
        return json.loads(sel.drop(columns="geometry").iloc[0].to_json())

    def props_metro(self, id_metro):
        """Propriedades de uma estacao de metro, como o clickData do mapa."""
        sel = self.estacoes_metro[self.estacoes_metro["id_metro"]
                                  == int(id_metro)]
        if sel.empty:
            return None
        linha = sel.drop(columns=["geometry", "buffer"]).iloc[0]
        return json.loads(linha.to_json())

    def centro_metro(self, id_metro):
        """Coordenadas [lat, lng] de uma estacao de metro (para centrar o mapa)."""
        sel = self.estacoes_metro[self.estacoes_metro["id_metro"]
                                  == int(id_metro)]
        if sel.empty:
            return None
        ponto = sel.geometry.iloc[0]
        return [ponto.y, ponto.x]