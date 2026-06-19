"""
Testes da logica de selecao da area de analise (Capitulo 4 - Testes).

Exercitam 'analise_complementar' — a funcao pura extraida do callback
'atualizar_analise' — que decide, conforme a selecao e o indicador ativo, o par
de figuras, o titulo, o realce e a 'vista' (estado que o CSS usa para mostrar o
bloco certo). E o ponto onde uma alteracao a esse mapeamento se pode partir sem
um teste o apanhar.
"""

import plotly.graph_objects as go
import pytest

import config
from app import callbacks

PESOS = config.PESOS_IIC_REF


def _chamar(repo, sel_gira=None, sel_metro=None, prop=None):
    return callbacks.analise_complementar(
        repo, sel_gira, sel_metro, None, None, config.RAIO_INFLUENCIA_M,
        PESOS[0], PESOS[1], PESOS[2], prop)


@pytest.fixture
def sel_gira(repo):
    """Seleccao de uma GIRA com indicadores (como o Store do mapa a preenche)."""
    r = repo.estacoes_gira.dropna(subset=["hora_pico"]).iloc[0]
    return {
        "id_estacao": int(r["id_estacao"]), "nome_estacao": r["nome_estacao"],
        "hora_pico": int(r["hora_pico"]), "total_docas": int(r["total_docas"]),
        "latitude": float(r["latitude"]), "longitude": float(r["longitude"]),
    }


@pytest.fixture
def sel_metro(repo):
    r = repo.estacoes_metro.iloc[0]
    return {"id_metro": int(r["id_metro"]), "nome_metro": r["nome_metro"]}


# --------------------------------------------------------------------------- #
# Vista sem selecao: cada indicador escolhe o seu estado
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("prop, vista_esperada", [
    (None, "intro"),
    ("iic", "grafico1-pesos"),
    ("n_gira_influencia", "grafico1"),
    ("disp_pico", "grafico1"),
    ("comp_ciclavel_m", "grafico1"),
    ("indice_variabilidade_diaria", "grafico1"),
    ("disponibilidade_media", "graficos2"),
])
def test_vista_sem_selecao_por_indicador(repo, prop, vista_esperada):
    """Sem selecao, cada indicador do mapa mapeia para a vista esperada."""
    serie, segundo, titulo, realce, vista = _chamar(repo, prop=prop)
    assert vista == vista_esperada
    assert isinstance(serie, go.Figure) and isinstance(segundo, go.Figure)
    assert realce == []            # sem GIRA selecionada, sem realce no mapa


def test_sem_selecao_sem_indicador_e_intro(repo):
    """O estado inicial (sem selecao, sem indicador) e a introducao."""
    *_, vista = _chamar(repo)
    assert vista == "intro"


# --------------------------------------------------------------------------- #
# Selecao de uma GIRA
# --------------------------------------------------------------------------- #
def test_gira_selecionada_mostra_graficos_e_realce(repo, sel_gira):
    serie, segundo, titulo, realce, vista = _chamar(repo, sel_gira=sel_gira)
    assert vista == "graficos"
    assert isinstance(serie, go.Figure) and isinstance(segundo, go.Figure)
    assert len(realce) == 1        # anel da estacao selecionada no mapa


def test_gira_com_ivd_usa_perfil_horario(repo, sel_gira):
    """Com o indicador IVD, a figura da esquerda e o perfil horario (eixo=hora)."""
    serie, *_ = _chamar(repo, sel_gira=sel_gira,
                        prop="indice_variabilidade_diaria")
    titulo_x = (serie.layout.xaxis.title.text or "").lower()
    assert "hora" in titulo_x


# --------------------------------------------------------------------------- #
# Selecao de uma estacao de metro
# --------------------------------------------------------------------------- #
def test_metro_selecionado_mostra_graficos(repo, sel_metro):
    serie, segundo, titulo, realce, vista = _chamar(repo, sel_metro=sel_metro,
                                                    prop="iic")
    assert vista == "graficos"
    assert isinstance(serie, go.Figure) and isinstance(segundo, go.Figure)
    assert realce == []            # o realce e so da GIRA; o metro tem buffer


@pytest.mark.parametrize("prop", [
    "iic", "n_gira_influencia", "dist_gira_min_m", "disp_pico",
    "comp_ciclavel_m",
])
def test_metro_qualquer_indicador_fica_em_graficos(repo, sel_metro, prop):
    """Com um metro selecionado, a vista e sempre 'graficos' (figuras adaptam-se)."""
    serie, segundo, *_rest, vista = _chamar(repo, sel_metro=sel_metro, prop=prop)
    assert vista == "graficos"
    assert isinstance(serie, go.Figure) and isinstance(segundo, go.Figure)
