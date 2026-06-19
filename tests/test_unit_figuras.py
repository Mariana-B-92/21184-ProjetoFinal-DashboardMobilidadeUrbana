"""
Testes unitarios dos geradores de figuras (Capitulo 4 - Testes).

Verificam que cada funcao figura_* devolve uma figura Plotly valida, com dados
quando ha dados e um estado vazio (sem tracos, com mensagem) nos casos-limite.
Cobrem a camada de visualizacao, que de outro modo so e exercitada no navegador.
"""

import plotly.graph_objects as go

import config
from app import figures


def _metro_com_gira(repo):
    """Id de uma estacao de metro com GIRA na area (figuras com dados)."""
    for m in repo.estacoes_metro["id_metro"]:
        cob = repo.cobertura_metro(int(m))
        if cob is not None and len(cob["gira"]) > 0:
            return int(m)
    return int(repo.estacoes_metro["id_metro"].iloc[0])


def _gira_com_indicadores(repo):
    """Id de uma GIRA com indicadores (historico nao vazio)."""
    g = repo.estacoes_gira.dropna(subset=["hora_pico"])
    return int((g if not g.empty else repo.estacoes_gira)["id_estacao"].iloc[0])


# --------------------------------------------------------------------------- #
# Estado vazio e helper de abreviacao
# --------------------------------------------------------------------------- #
def test_figura_vazia_e_figura_sem_tracos_com_mensagem():
    """figura_vazia devolve uma figura sem dados, mas com a mensagem (anotacao)."""
    fig = figures.figura_vazia("xpto")
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 0
    assert any("xpto" in (a.text or "") for a in fig.layout.annotations)


def test_abreviar_trunca_nomes_longos():
    """_abreviar mantem nomes curtos e trunca os longos com reticencias."""
    assert figures._abreviar("Saldanha", 26) == "Saldanha"
    curto = figures._abreviar("A" * 30, 26)
    assert len(curto) == 26 and curto.endswith("…")


# --------------------------------------------------------------------------- #
# Figuras de uma estacao GIRA
# --------------------------------------------------------------------------- #
def test_serie_temporal_tem_dados(repo):
    fig = figures.figura_serie_temporal(repo, _gira_com_indicadores(repo))
    assert isinstance(fig, go.Figure)
    assert len(fig.data) >= 1


def test_serie_temporal_sem_id_e_estado_vazio(repo):
    """Sem estacao selecionada (id None), devolve o estado vazio."""
    fig = figures.figura_serie_temporal(repo, None)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 0


def test_heatmap_tem_traco(repo):
    fig = figures.figura_heatmap(repo, _gira_com_indicadores(repo))
    assert isinstance(fig, go.Figure)
    assert len(fig.data) >= 1


def test_perfil_horario_tem_dados(repo):
    fig = figures.figura_perfil_horario(repo, _gira_com_indicadores(repo))
    assert isinstance(fig, go.Figure)
    assert len(fig.data) >= 1


# --------------------------------------------------------------------------- #
# Series global e de conjunto (req. 2.5.2)
# --------------------------------------------------------------------------- #
def test_serie_global_tem_dados(repo):
    fig = figures.figura_serie_global(repo)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) >= 1


def test_serie_conjunto_tem_dados(repo):
    ids = repo.estacoes_gira["id_estacao"].head(3).tolist()
    fig = figures.figura_serie_conjunto(repo, ids)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) >= 1


def test_serie_conjunto_lista_vazia_e_estado_vazio(repo):
    """Sem GIRA no conjunto, devolve o estado vazio (sem tracos)."""
    fig = figures.figura_serie_conjunto(repo, [])
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 0


# --------------------------------------------------------------------------- #
# Rankings (vista sem selecao)
# --------------------------------------------------------------------------- #
def test_ranking_iic_tem_barras(repo):
    fig = figures.figura_ranking_iic(repo)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) >= 1


def test_ranking_iic_com_pesos_personalizados(repo):
    """O IIC recalculado com pesos diferentes continua a produzir barras."""
    fig = figures.figura_ranking_iic(repo, pesos=(0.5, 0.3, 0.2))
    assert isinstance(fig, go.Figure)
    assert len(fig.data) >= 1


def test_ranking_estacoes_tem_barras(repo):
    fig = figures.figura_ranking_estacoes(
        repo, "gira", "disponibilidade_media", eixo="Disp",
        hover_sufixo=" bicis", titulo="T", casas=1)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) >= 1


# --------------------------------------------------------------------------- #
# Figuras de uma estacao de metro (area de influencia)
# --------------------------------------------------------------------------- #
def test_figuras_de_metro_com_cobertura(repo):
    """As figuras da area de influencia constroem-se para um metro com GIRA."""
    mid = _metro_com_gira(repo)
    for fig in (
        figures.figura_distancia_gira(repo, mid),
        figures.figura_pico_gira(repo, mid),
        figures.figura_distribuicao_gira(repo, mid),
        figures.figura_composicao_iic(repo, mid),
        figures.figura_rede_ciclavel_metro(repo, mid),
        figures.figura_contexto_metro(repo, mid, "comp_ciclavel_m",
                                      eixo="km", titulo="T", escala=0.001),
    ):
        assert isinstance(fig, go.Figure)


def test_distancia_gira_sem_metro_e_estado_vazio(repo):
    """Sem estacao de metro (id None), devolve o estado vazio."""
    fig = figures.figura_distancia_gira(repo, None)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 0


# --------------------------------------------------------------------------- #
# Comparacao entre estacoes de metro
# --------------------------------------------------------------------------- #
def test_comparacao_tem_uma_serie_por_estacao(repo):
    """A comparacao desenha um conjunto de barras por estacao selecionada."""
    ids = repo.estacoes_metro["id_metro"].head(2).astype(int).tolist()
    fig = figures.figura_comparacao(repo, ids)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 2


def test_comparacao_sem_estacoes_e_estado_vazio(repo):
    fig = figures.figura_comparacao(repo, [])
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 0
