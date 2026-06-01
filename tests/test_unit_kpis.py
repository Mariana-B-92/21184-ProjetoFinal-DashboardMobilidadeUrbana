"""
Testes unitarios dos indicadores (Capitulo 4 - Testes).

Verificam as formulas e os casos-limite definidos no documento das metricas,
usando casos sinteticos controlados (resultado conhecido) e validacao sobre os
dados reais. Cobrem em particular as questoes metodologicas levantadas pelo
orientador: normalizacao min-max com max == min, truncatura da distancia antes
da normalizacao e garantia de TMD em [0, 1].
"""

import numpy as np
import pandas as pd
import pytest

import config
from kpis import iic


# --------------------------------------------------------------------------- #
# Normalizacao min-max e casos-limite
# --------------------------------------------------------------------------- #
def test_normalizacao_minmax_basica():
    """Normalizacao mapeia o minimo a 0 e o maximo a 1."""
    s = pd.Series([0.0, 5.0, 10.0])
    resultado = iic.normalizar_minmax(s)
    assert resultado.iloc[0] == 0.0
    assert resultado.iloc[-1] == 1.0
    assert resultado.iloc[1] == pytest.approx(0.5)


def test_normalizacao_minmax_todos_iguais():
    """Caso-limite (orientador): max == min devolve o valor neutro 0,5,
    evitando divisao por zero."""
    s = pd.Series([7.0, 7.0, 7.0])
    resultado = iic.normalizar_minmax(s)
    assert (resultado == config.VALOR_NEUTRO_NORMALIZACAO).all()


def test_normalizacao_minmax_sem_divisao_por_zero():
    """Nenhum valor NaN/inf quando a serie e constante."""
    s = pd.Series([3.0, 3.0])
    resultado = iic.normalizar_minmax(s)
    assert resultado.notna().all()
    assert np.isfinite(resultado).all()


# --------------------------------------------------------------------------- #
# IIC: truncatura, pesos e dominio
# --------------------------------------------------------------------------- #
def test_iic_truncatura_antes_da_normalizacao():
    """A distancia e truncada a d_max ANTES de normalizar (orientador).

    Duas estacoes acima do limiar (1500 m e 3000 m) devem ficar com a mesma
    proximidade, pois ambas sao truncadas a 1000 m antes da normalizacao.
    """
    dist = pd.Series([100.0, 1500.0, 3000.0])
    n_gira = pd.Series([1, 1, 1])
    comp = pd.Series([0.0, 0.0, 0.0])
    resultado = iic.calcular_iic(dist, n_gira, comp)

    assert resultado["dist_truncada_m"].max() <= config.DISTANCIA_MAX_TRUNCATURA_M
    # As duas distancias truncadas (ambas 1000) -> mesma proximidade.
    assert resultado["prox_norm"].iloc[1] == pytest.approx(
        resultado["prox_norm"].iloc[2])


def test_iic_proximidade_decrescente_com_distancia():
    """Maior distancia -> menor proximidade."""
    dist = pd.Series([0.0, 500.0, 1000.0])
    n_gira = pd.Series([0, 0, 0])
    comp = pd.Series([0.0, 0.0, 0.0])
    prox = iic.calcular_iic(dist, n_gira, comp)["prox_norm"]
    assert prox.iloc[0] > prox.iloc[1] > prox.iloc[2]


def test_iic_no_intervalo_unitario(indicadores_g2):
    """Sobre os dados reais, o IIC fica sempre em [0, 1]."""
    assert indicadores_g2["iic"].min() >= 0.0
    assert indicadores_g2["iic"].max() <= 1.0


def test_pesos_iic_somam_um():
    """Os pesos do IIC somam 1 (media ponderada bem definida)."""
    assert sum(config.PESOS_IIC.values()) == pytest.approx(1.0)


def test_iic_combina_pesos_corretamente():
    """Com componentes conhecidas, o IIC e a media ponderada esperada."""
    # Uma unica estacao -> todas as componentes caem no caso neutro (0,5),
    # exceto a proximidade (dist unica -> truncada -> normalizada a 0 -> prox=1).
    dist = pd.Series([200.0])
    n_gira = pd.Series([3])
    comp = pd.Series([500.0])
    r = iic.calcular_iic(dist, n_gira, comp).iloc[0]
    esperado = (config.PESOS_IIC["proximidade"] * r["prox_norm"]
                + config.PESOS_IIC["densidade"] * r["n_gira_norm"]
                + config.PESOS_IIC["ciclavel"] * r["comp_ciclavel_norm"])
    assert r["iic"] == pytest.approx(esperado)


# --------------------------------------------------------------------------- #
# Grupo 1: TMD em [0,1] e hora de pico
# --------------------------------------------------------------------------- #
def test_tmd_no_intervalo_unitario(indicadores_g1):
    """Taxa media de disponibilidade em [0, 1] (por construcao)."""
    tmd = indicadores_g1["taxa_media_disponibilidade"]
    assert tmd.min() >= 0.0
    assert tmd.max() <= 1.0


def test_hora_pico_valida(indicadores_g1):
    """A hora de pico e uma hora valida do dia (0-23)."""
    hp = indicadores_g1["hora_pico"]
    assert hp.min() >= 0
    assert hp.max() <= 23


def test_ivd_nao_negativo(indicadores_g1):
    """O indice de variabilidade diaria e nao-negativo (e uma raiz de RMS)."""
    assert (indicadores_g1["indice_variabilidade_diaria"] >= 0).all()
