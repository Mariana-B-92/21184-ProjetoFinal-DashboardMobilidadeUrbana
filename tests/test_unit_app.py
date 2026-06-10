"""
Testes unitarios da camada de apresentacao (Capitulo 4 - Testes).

Cobrem as funcoes puras dos callbacks do dashboard: formatacao de valores
(incluindo ausentes), construcao das classes da legenda, parametros de cor do
mapa (hideout) e os cartoes de indicadores. Nao exercitam os decoradores
@app.callback nem o codigo do lado do cliente, que exigiriam um navegador.
"""

import types

import pandas as pd
import pytest

import config
from app import callbacks


# Caractere usado para representar um valor ausente nos cartoes.
TRACO = "–"


def _textos(componente):
    """Recolhe recursivamente todas as cadeias de texto de um componente Dash."""
    if isinstance(componente, str):
        return [componente]
    if isinstance(componente, (list, tuple)):
        return [t for filho in componente for t in _textos(filho)]
    if hasattr(componente, "children"):
        return _textos(componente.children)
    return []


def _repo_falso():
    """Repositorio minimo com apenas as colunas lidas por hideout_indicador."""
    return types.SimpleNamespace(
        estacoes_gira=pd.DataFrame({
            "taxa_media_disponibilidade": [0.3, 0.9],
            "disponibilidade_media": [2.0, 8.0],
        }),
        estacoes_metro=pd.DataFrame({
            "iic": [0.2, 0.8],
            "n_gira_influencia": [1, 5],
            "dist_gira_min_m": [100.0, 500.0],
        }),
    )


# --------------------------------------------------------------------------- #
# Formatacao de valores
# --------------------------------------------------------------------------- #
def test_fmt_valor_ausente_none():
    """None e apresentado como traco, nao como erro."""
    assert callbacks._fmt(None) == TRACO


def test_fmt_valor_ausente_nan():
    """NaN e apresentado como traco (mesmo tratamento de None)."""
    assert callbacks._fmt(float("nan")) == TRACO


def test_fmt_inteiro_sem_casas_decimais():
    """Com decimais=0 o valor sai sem parte decimal e com o sufixo."""
    assert callbacks._fmt(7.4, sufixo="h", decimais=0) == "7h"


def test_fmt_com_casas_decimais_e_sufixo():
    """Com decimais>0 respeita o numero de casas e o sufixo."""
    assert callbacks._fmt(0.5, sufixo="%", decimais=2) == "0.50%"


def test_num_pt_usa_virgula_decimal():
    """A formatacao numerica da legenda usa virgula como separador decimal."""
    assert callbacks._num_pt(1.5, 1) == "1,5"


# --------------------------------------------------------------------------- #
# Classes da legenda
# --------------------------------------------------------------------------- #
def test_classes_legenda_numero_e_limite_inferior():
    """Devolve tantos limites quantas as classes da escala, comecando em vmin."""
    classes = callbacks.classes_legenda(0.0, 10.0)
    assert len(classes) == len(config.ESCALA_COR)
    assert classes[0] == 0.0
    assert classes == sorted(classes)


def test_classes_legenda_intervalo_degenerado():
    """Quando vmax <= vmin (todos os valores iguais) devolve um unico limite."""
    assert callbacks.classes_legenda(5.0, 5.0) == [5.0]


# --------------------------------------------------------------------------- #
# Parametros de cor do mapa (hideout)
# --------------------------------------------------------------------------- #
def test_hideout_indicador_dominio_fixo():
    """Indicador com dominio definido (IIC) fixa vmin/vmax em [0, 1]."""
    h = callbacks.hideout_indicador(_repo_falso(), "iic")
    assert h["vmin"] == 0.0
    assert h["vmax"] == 1.0
    assert h["prop"] == "iic"


def test_hideout_indicador_dominio_pelos_dados():
    """Sem dominio definido, vmin/vmax vem do minimo/maximo reais dos dados."""
    h = callbacks.hideout_indicador(_repo_falso(), "n_gira_influencia")
    assert h["vmin"] == 1.0
    assert h["vmax"] == 5.0


def test_hideout_indicador_le_a_fonte_correta():
    """Um indicador de GIRA le os valores das estacoes GIRA."""
    h = callbacks.hideout_indicador(_repo_falso(), "disponibilidade_media")
    assert h["vmin"] == 2.0
    assert h["vmax"] == 8.0


def test_hideout_indicador_inversao_da_distancia():
    """A distancia tem escala invertida (valores menores = melhores)."""
    h = callbacks.hideout_indicador(_repo_falso(), "dist_gira_min_m")
    assert h["inverter"] is True


def test_hideout_categorico_marca_categoria():
    """O modo categorico assinala-se com a flag 'categorico' e uma cor fixa."""
    h = callbacks.hideout_categorico_metro()
    assert h["categorico"] is True
    assert h["cor_fixa"] == callbacks.COR_METRO_CAT


def test_construir_legenda_titulo_subtitulo_e_classes():
    """A legenda por indicador tem titulo, subtitulo e uma linha por classe."""
    meta = callbacks.INDICADORES_MAPA["dist_gira_min_m"]
    hideout = callbacks.hideout_indicador(_repo_falso(), "dist_gira_min_m")
    legenda = callbacks.construir_legenda("dist_gira_min_m", hideout, meta)
    assert len(legenda) == 2 + len(config.ESCALA_COR)
    assert "estações de metro" in _textos(legenda)


# --------------------------------------------------------------------------- #
# Cartoes de indicadores
# --------------------------------------------------------------------------- #
def test_painel_gira_propriedades_em_falta():
    """Sem indicadores na selecao, os cartoes mostram traco em vez de falhar."""
    painel = callbacks.painel_gira({"id_estacao": 1, "nome_estacao": "X"})
    textos = _textos(painel)
    assert TRACO in textos
    assert "X" in textos


def test_gauge_iic_limita_dominio():
    """O medidor do IIC satura a largura em 100% para valores acima de 1."""
    largura = _largura_gauge(callbacks.gauge_iic(1.5))
    assert largura == "100%"


def _largura_gauge(componente):
    """Extrai a largura (style.width) do preenchimento do medidor."""
    trilho = componente.children[0]
    fill = trilho.children[0]
    return fill.style["width"]


# --------------------------------------------------------------------------- #
# Paleta partilhada (mapa, legendas e graficos)
# --------------------------------------------------------------------------- #
def test_cor_classe_extremos():
    """t=0 mapeia a primeira classe e t=1 a ultima da escala."""
    assert config.cor_classe(0.0) == config.ESCALA_COR[0]
    assert config.cor_classe(1.0) == config.ESCALA_COR[-1]


def test_cor_classe_satura_fora_do_intervalo():
    """Valores fora de [0, 1] sao truncados antes do mapeamento."""
    assert config.cor_classe(-2.0) == config.ESCALA_COR[0]
    assert config.cor_classe(9.0) == config.ESCALA_COR[-1]
