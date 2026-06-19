"""
Camada de acesso a dados do dashboard (SQLite gerado por construir_modelo.py).

Tabelas pequenas e geometrias sao carregadas em memoria no arranque
(reconstruidas a partir do WKT). A entidade temporal DisponibilidadeGIRA
(~1.99 M registos) permanece em SQLite e e consultada a pedido, recorrendo aos
indices, para nao sobrecarregar a memoria.
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
        # Erro acionavel: o nativo do SQLite ("unable to open database file") e
        # criptico quando o modelo ainda nao foi construido.
        if not Path(self.caminho_db).exists():
            raise FileNotFoundError(
                f"Base de dados nao encontrada em '{self.caminho_db}'.\n"
                "Corra primeiro a fase offline para a gerar:\n"
                "    python construir_modelo.py")
        self.estacoes_gira = self._carregar_estacoes_gira()
        self.estacoes_metro = self._carregar_estacoes_metro()
        self.rede_ciclavel = self._carregar_rede_ciclavel()
        # Versoes em CRS metrico, reutilizadas nas operacoes espaciais (mesmo
        # CRS do ETL).
        self._gira_m = self.estacoes_gira.to_crs(config.CRS_METRICO)
        self._metro_m = (self.estacoes_metro.drop(columns=["buffer"])
                         .to_crs(config.CRS_METRICO))
        self._ciclavel_m = self.rede_ciclavel.to_crs(config.CRS_METRICO)
        # Cache dos agregados globais (consultas pesadas) para nao repetir ao
        # alternar a selecao com o mesmo periodo. Chave: (tipo, inicio, fim).
        self._cache_global = {}
        # Cache da cobertura espacial: a mesma selecao de metro alimenta dois
        # callbacks, que de outro modo repetiriam o buffer e as intersecoes.
        # Chave: (id_metro, raio).
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

    @staticmethod
    def _filtrar_datas(sql, params, inicio, fim):
        """Acrescenta o filtro de periodo ao SQL, mutando 'params' no local.

        A coluna 'data' e texto ISO, pelo que a comparacao lexicografica
        coincide com a cronologica.
        """
        if inicio:
            sql += " AND data >= ?"
            params.append(str(inicio))
        if fim:
            sql += " AND data <= ?"
            params.append(str(fim))
        return sql

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
        # Buffer como coluna geometrica; buffer_wkt e descartado para o WKT do
        # poligono nao viajar ate ao mapa e ao dcc.Store em cada selecao.
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
        pelo que MIN/MAX lexicografico coincide com o cronologico.
        """
        df = self._ler("SELECT MIN(data) AS inicio, MAX(data) AS fim "
                       "FROM DisponibilidadeGIRA")
        return df["inicio"].iloc[0], df["fim"].iloc[0]

    def serie_temporal(self, id_estacao, inicio=None, fim=None, frequencia=None):
        """Serie temporal de disponibilidade de uma estacao GIRA.

        inicio/fim: datas (YYYY-MM-DD) que restringem o periodo.
        frequencia: se indicada (ex.: 'D', 'h'), reamostra a media server-side
            para reduzir o volume devolvido.
        """
        sql = ("SELECT timestamp, numbicicletas, numdocas "
               "FROM DisponibilidadeGIRA WHERE id_estacao = ?")
        params = [int(id_estacao)]
        sql = self._filtrar_datas(sql, params, inicio, fim)

        df = self._ler(sql, params)
        if df.empty:
            return df
        # Hora local: a reamostragem diaria/horaria tem de usar o mesmo
        # calendario que o heatmap (assente em 'hora'/'dia_semana' em
        # Europe/Lisbon). Em UTC, a serie divergiria do heatmap junto a
        # meia-noite.
        df["timestamp"] = (pd.to_datetime(df["timestamp"], utc=True, format="mixed")
                           .dt.tz_convert(config.FUSO_HORARIO))
        df = df.sort_values("timestamp")

        if frequencia:
            df = (df.set_index("timestamp")
                    .resample(frequencia)["numbicicletas"].mean()
                    .reset_index())
        return df

    def heatmap_disponibilidade(self, id_estacao, inicio=None, fim=None):
        """Disponibilidade media por dia da semana x hora do dia (matriz 7x24)."""
        sql = ("SELECT dia_semana, hora, AVG(numbicicletas) AS media "
               "FROM DisponibilidadeGIRA WHERE id_estacao = ?")
        params = [int(id_estacao)]
        sql = self._filtrar_datas(sql, params, inicio, fim)
        sql += " GROUP BY dia_semana, hora"
        df = self._ler(sql, params)
        if df.empty:
            return df
        matriz = (df.pivot(index="dia_semana", columns="hora", values="media")
                    .reindex(index=range(7), columns=range(24)))
        matriz.index = [DIAS_SEMANA[i] for i in matriz.index]
        return matriz

    def perfil_horario(self, id_estacao, inicio=None, fim=None):
        """Disponibilidade media por hora do dia (0-23), agregando os dias.

        E o perfil b̄_i(h) — a media de bicicletas a cada hora — cuja dispersao
        em torno da media define o IVD.
        """
        sql = ("SELECT hora, AVG(numbicicletas) AS media "
               "FROM DisponibilidadeGIRA WHERE id_estacao = ?")
        params = [int(id_estacao)]
        sql = self._filtrar_datas(sql, params, inicio, fim)
        sql += " GROUP BY hora ORDER BY hora"
        return self._ler(sql, params)

    def serie_global(self, inicio=None, fim=None):
        """Serie diaria da disponibilidade media de bicicletas em TODAS as GIRA.

        Resultado em cache por (inicio, fim). Le a tabela pre-agregada
        DisponibilidadeGlobalDiaria (instantanea); se nao existir, recorre ao
        agregado a pedido sobre o historico completo.
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
        sql = self._filtrar_datas(sql, params, inicio, fim)
        sql += " ORDER BY data" if pre else " GROUP BY data ORDER BY data"
        df = self._ler(sql, params)
        if not df.empty:
            df["data"] = pd.to_datetime(df["data"])
        self._cache_global[chave] = df
        return df

    def serie_conjunto(self, ids, inicio=None, fim=None):
        """Serie diaria da disponibilidade media de um CONJUNTO de estacoes GIRA.

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
        sql = self._filtrar_datas(sql, params, inicio, fim)
        sql += " GROUP BY data ORDER BY data"
        df = self._ler(sql, params)
        if not df.empty:
            df["data"] = pd.to_datetime(df["data"])
        return df

    def cobertura_metro(self, id_metro, raio=None):
        """Area de influencia de uma estacao de metro e elementos contidos.

        Calculado em CRS metrico (como o ETL) e devolvido em WGS84. As medidas
        sao recalculadas para o 'raio' indicado; para raios diferentes do oficial
        (config) sao exploratorias e nao substituem os indicadores persistidos.

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

        # Estacoes GIRA na area de influencia. dist_min nao depende do raio, mas
        # e devolvido por conveniencia.
        distancias = self._gira_m.geometry.distance(ponto)
        idx_dentro = distancias.index[distancias <= raio]
        gira_dentro = self.estacoes_gira.loc[idx_dentro].copy()
        # Anexa a distancia de cada GIRA ao metro (ja calculada acima).
        gira_dentro["dist_m"] = distancias.loc[idx_dentro].values
        dist_min = float(distancias.min())

        # Porcoes de rede ciclavel contidas no buffer (intersecao).
        intersecao = self._ciclavel_m.geometry.intersection(buffer_m)
        intersecao = intersecao[~intersecao.is_empty]
        comp_ciclavel_m = float(intersecao.length.sum())
        # Decomposicao por nivel de segregacao: quanto da rede na area e separada
        # fisicamente / visualmente / partilhada.
        if len(intersecao) > 0:
            niveis = self._ciclavel_m.loc[intersecao.index, "nivel_segregacao"]
            ciclavel_por_seg = {str(k): float(v) for k, v in
                                intersecao.length.groupby(niveis).sum().items()}
        else:
            ciclavel_por_seg = {}

        # Disponibilidade media nas horas de pico das GIRA contidas.
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
                     "ciclavel_por_seg": ciclavel_por_seg,
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