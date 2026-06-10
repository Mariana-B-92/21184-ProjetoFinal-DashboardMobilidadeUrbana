"""
Testes de sistema / integracao (Capitulo 4 - Testes).

Verificam o funcionamento do sistema como um todo: a integridade do modelo
persistido em SQLite e a coerencia entre os indicadores calculados em tempo real
pela camada de dados do dashboard e os valores persistidos pelo pipeline.
"""

import sqlite3

import pytest


TABELAS_ESPERADAS = {
    "EstacaoGIRA", "DisponibilidadeGIRA", "EstacaoMetro", "RedeCiclavel",
    "IndicadorDisponibilidadeGIRA", "IndicadorCoberturaMetro",
}


# --------------------------------------------------------------------------- #
# Integridade do modelo persistido
# --------------------------------------------------------------------------- #
def test_base_dados_tem_todas_as_entidades(ligacao_bd):
    """As seis entidades do modelo estao presentes na base de dados."""
    cur = ligacao_bd.cursor()
    tabelas = {r[0] for r in cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert TABELAS_ESPERADAS.issubset(tabelas)


def test_entidades_nao_vazias(ligacao_bd):
    """Nenhuma entidade do modelo esta vazia."""
    cur = ligacao_bd.cursor()
    for tabela in TABELAS_ESPERADAS:
        n = cur.execute(f'SELECT COUNT(*) FROM "{tabela}"').fetchone()[0]
        assert n > 0, f"{tabela} esta vazia"


def test_indices_criados(ligacao_bd):
    """Os indices de consulta eficiente foram criados."""
    cur = ligacao_bd.cursor()
    indices = {r[0] for r in cur.execute(
        "SELECT name FROM sqlite_master WHERE type='index'")}
    assert "idx_disp_estacao_ts" in indices


def test_geometrias_em_wkt_validas(ligacao_bd):
    """As geometrias persistidas em WKT sao reconstrutiveis."""
    from shapely import wkt
    cur = ligacao_bd.cursor()
    amostra = cur.execute(
        "SELECT geometria_wkt FROM EstacaoMetro LIMIT 5").fetchall()
    for (g,) in amostra:
        assert wkt.loads(g).geom_type == "Point"


# --------------------------------------------------------------------------- #
# Coerencia app (tempo real) <-> base de dados (persistido)
# --------------------------------------------------------------------------- #
def test_cobertura_app_coerente_com_bd(repo):
    """A cobertura recalculada na app coincide com os indicadores persistidos.

    Para cada estacao de metro, o numero de GIRA na area e o comprimento ciclavel
    calculados em tempo real pela camada de dados devem igualar os valores do
    Grupo 2 guardados na base de dados.
    """
    import geopandas as gpd
    import config

    metro = repo.estacoes_metro
    # Amostra de 8 estacoes para manter o teste rapido mas representativo.
    for _, linha in metro.head(8).iterrows():
        id_metro = linha["id_metro"]
        cob = repo.cobertura_metro(id_metro)

        # N.o de GIRA na area.
        assert len(cob["gira"]) == int(linha["n_gira_influencia"])

        # Comprimento ciclavel (recalculado em CRS metrico).
        comp = cob["ciclavel"].to_crs(config.CRS_METRICO).length.sum()
        assert comp == pytest.approx(linha["comp_ciclavel_m"], abs=1.0)


def test_serie_temporal_consistente(repo):
    """A serie temporal de uma estacao devolve dados dentro do periodo."""
    id_estacao = int(repo.estacoes_gira["id_estacao"].iloc[0])
    serie = repo.serie_temporal(id_estacao, frequencia="D")
    assert not serie.empty
    assert (serie["numbicicletas"] >= 0).all()


def test_heatmap_dimensoes(repo):
    """O heatmap tem, no maximo, a forma 7 dias x 24 horas."""
    id_estacao = int(repo.estacoes_gira["id_estacao"].iloc[0])
    matriz = repo.heatmap_disponibilidade(id_estacao)
    assert matriz.shape[0] <= 7
    assert matriz.shape[1] <= 24


def test_estacoes_gira_tem_indicadores(repo):
    """As estacoes GIRA trazem os indicadores do Grupo 1 (join correto)."""
    assert "disponibilidade_media" in repo.estacoes_gira.columns
    assert "hora_pico" in repo.estacoes_gira.columns
    assert repo.estacoes_gira["disponibilidade_media"].notna().any()


# --------------------------------------------------------------------------- #
# Consultas do repositorio: casos-limite (selecao invalida e listas vazias)
# --------------------------------------------------------------------------- #
def test_props_gira_id_inexistente(repo):
    """Um id de GIRA inexistente devolve None (e nao uma excecao)."""
    assert repo.props_gira(999_999_999) is None


def test_props_gira_id_valido(repo):
    """Um id de GIRA valido devolve um dicionario com a propria estacao."""
    id_estacao = int(repo.estacoes_gira["id_estacao"].iloc[0])
    props = repo.props_gira(id_estacao)
    assert props["id_estacao"] == id_estacao
    assert "geometry" not in props  # JSON-seguro, sem geometria


def test_props_metro_id_inexistente(repo):
    """Um id de metro inexistente devolve None."""
    assert repo.props_metro(999_999_999) is None


def test_centro_metro_id_inexistente(repo):
    """Sem estacao correspondente, o centro do mapa e None."""
    assert repo.centro_metro(999_999_999) is None


def test_centro_metro_id_valido(repo):
    """Para uma estacao valida devolve um par [latitude, longitude]."""
    id_metro = int(repo.estacoes_metro["id_metro"].iloc[0])
    centro = repo.centro_metro(id_metro)
    assert len(centro) == 2
    assert 38 < centro[0] < 39 and -10 < centro[1] < -9  # area de Lisboa


def test_cobertura_metro_id_inexistente(repo):
    """A cobertura de uma estacao inexistente devolve None."""
    assert repo.cobertura_metro(999_999_999) is None


def test_indicadores_metro_id_inexistente(repo):
    """Os indicadores de uma estacao inexistente sao None."""
    assert repo.indicadores_metro(999_999_999) is None


def test_serie_conjunto_lista_vazia(repo):
    """Sem estacoes no conjunto, a serie e um DataFrame vazio."""
    assert repo.serie_conjunto([]).empty


def test_serie_conjunto_lista_valida(repo):
    """Com estacoes validas, a serie do conjunto traz data e media."""
    ids = repo.estacoes_gira["id_estacao"].head(3).tolist()
    serie = repo.serie_conjunto(ids)
    assert not serie.empty
    assert {"data", "media"}.issubset(serie.columns)


def test_serie_temporal_respeita_filtro_de_datas(repo):
    """Com inicio/fim, todas as observacoes caem dentro do periodo pedido."""
    id_estacao = int(repo.estacoes_gira["id_estacao"].iloc[0])
    inicio, fim = repo.intervalo_datas()
    serie = repo.serie_temporal(id_estacao, inicio=inicio, fim=fim)
    assert not serie.empty
    # Os timestamps sao convertidos para hora local (tz-aware).
    assert serie["timestamp"].dt.tz is not None
    datas = serie["timestamp"].dt.strftime("%Y-%m-%d")
    assert (datas >= inicio).all() and (datas <= fim).all()


def test_intervalo_datas_par_ordenado(repo):
    """O intervalo coberto e um par de datas (inicio <= fim)."""
    inicio, fim = repo.intervalo_datas()
    assert inicio <= fim


def test_serie_global_traz_data_e_media(repo):
    """A serie global (vista inicial) devolve a media diaria por data."""
    serie = repo.serie_global()
    assert not serie.empty
    assert {"data", "media"}.issubset(serie.columns)


# --------------------------------------------------------------------------- #
# Camada de apresentacao sobre dados reais (paineis contextuais)
# --------------------------------------------------------------------------- #
def test_painel_global_constroi(repo):
    """O painel de KPIs globais (sem selecao) constroi-se sem erro."""
    from app import callbacks
    painel = callbacks.painel_global(repo)
    assert painel is not None


def test_painel_metro_devolve_painel_e_camadas(repo):
    """O painel de uma estacao de metro produz o painel e as camadas do mapa."""
    from app import callbacks
    import config

    id_metro = int(repo.estacoes_metro["id_metro"].iloc[0])
    props = repo.props_metro(id_metro)
    painel, camadas = callbacks.painel_metro(
        repo, props, raio=config.RAIO_INFLUENCIA_M)
    assert painel is not None
    # Inclui, no minimo, o buffer e o marcador da estacao de metro.
    assert len(camadas) >= 2
