"""
Callbacks da aplicacao Dash (seccao 2.5.3).

Interacoes implementadas:
- clique numa estacao GIRA: atualiza serie temporal, heatmap e titulo;
- clique numa estacao de metro: ativa a analise de cobertura (desenha a area de
  influencia, destaca as estacoes GIRA e a rede ciclavel contidas, e preenche os
  indicadores do Grupo 2 e o IIC).

As restantes (ajuste do raio, codificacao do mapa por indicador, comparacao
entre estacoes) serao adicionadas a seguir.
"""

import json

import dash_leaflet as dl
import geopandas as gpd
from dash import Input, Output, html

import config
from app import figures

# Cores das linhas de metro (coerentes com o mapa).
CORES_LINHA = {
    "Azul": "#1f6fb2", "Amarela": "#f4c20d", "Verde": "#0a9a4a",
    "Vermelha": "#d6322e",
}

# Escala de cor sequencial (palido -> verde) para a codificacao por indicador.
ESCALA_COR = ["#f4f5f3", "#7fc99b", "#07733a"]
ESCALA_RGB = [[244, 245, 243], [127, 201, 155], [7, 115, 58]]

# Metadados dos indicadores selecionaveis no mapa.
# 'inverter' = True quando valores MAIS BAIXOS sao melhores (distancia): a escala
# e invertida para que "melhor" corresponda sempre ao verde.
INDICADORES_MAPA = {
    "iic": {"unidade": "", "decimais": 2, "inverter": False},
    "n_gira_influencia": {"unidade": "", "decimais": 0, "inverter": False},
    "dist_gira_min_m": {"unidade": "m", "decimais": 0, "inverter": True},
}


def hideout_indicador(repo, prop):
    """Parametros de cor (hideout) para codificar o mapa por um indicador."""
    meta = INDICADORES_MAPA[prop]
    valores = repo.estacoes_metro[prop]
    return {
        "prop": prop,
        "vmin": float(valores.min()),
        "vmax": float(valores.max()),
        "inverter": meta["inverter"],
        "stops": ESCALA_RGB,
    }


def _id_estacao_do_clique(click_data):
    """Extrai o id da estacao GIRA do elemento clicado no mapa."""
    if not click_data:
        return None
    propriedades = click_data.get("properties") or {}
    return propriedades.get("id_estacao")


def _cartao_metro(valor, rotulo):
    return html.Div(className="kpi-card kpi-card--metro", children=[
        html.Div(valor, className="kpi-valor"),
        html.Div(rotulo, className="kpi-rotulo"),
    ])


def registar_callbacks(app, repo):
    @app.callback(
        Output("grafico-serie", "figure"),
        Output("grafico-heatmap", "figure"),
        Output("estacao-titulo", "children"),
        Input("gira", "clickData"),
        Input("filtro-periodo", "start_date"),
        Input("filtro-periodo", "end_date"),
    )
    def atualizar_estacao(click_data, inicio, fim):
        id_estacao = _id_estacao_do_clique(click_data)

        serie = figures.figura_serie_temporal(repo, id_estacao, inicio, fim)
        heatmap = figures.figura_heatmap(repo, id_estacao)

        if id_estacao is None:
            titulo = html.Span("Nenhuma estação selecionada",
                               className="sem-selecao")
        else:
            propriedades = click_data.get("properties", {})
            nome = propriedades.get("nome_estacao", f"Estação {id_estacao}")
            titulo = html.Span([
                html.Strong(nome),
                html.Span(f"  ·  pico às {int(propriedades.get('hora_pico', 0))}h"
                          f"  ·  {propriedades.get('total_docas', '–')} docas",
                          className="estacao-meta"),
            ])
        return serie, heatmap, titulo

    @app.callback(
        Output("camada-cobertura", "children"),
        Output("kpi-metro", "children"),
        Input("metro", "clickData"),
        Input("filtro-raio", "value"),
    )
    def atualizar_cobertura(click_data, raio):
        if not click_data:
            dica = html.Div("Clique numa estação de metro para analisar a "
                            "cobertura na sua área de influência.",
                            className="dica")
            return [], dica

        propriedades = click_data.get("properties", {})
        id_metro = propriedades.get("id_metro")
        cobertura = repo.cobertura_metro(id_metro, raio=raio)
        indicadores = repo.indicadores_metro(id_metro)

        raio_oficial = config.RAIO_INFLUENCIA_M
        exploratorio = raio != raio_oficial

        # --- Camadas de destaque no mapa ---
        camadas = []
        # Area de influencia (buffer).
        buffer_gj = json.loads(
            gpd.GeoSeries([cobertura["buffer"]],
                          crs=config.CRS_GEOGRAFICO).to_json())
        camadas.append(dl.GeoJSON(
            data=buffer_gj,
            style={"color": "#1b211e", "weight": 1.5, "dashArray": "5 5",
                   "fillColor": "#0a9a4a", "fillOpacity": 0.06}))
        # Rede ciclavel contida no buffer (destaque).
        if len(cobertura["ciclavel"]) > 0:
            ciclavel_gj = json.loads(cobertura["ciclavel"].to_json())
            camadas.append(dl.GeoJSON(
                data=ciclavel_gj,
                style={"color": "#1f6fb2", "weight": 4, "opacity": 0.9}))
        # Estacoes GIRA dentro da area (destaque).
        for _, e in cobertura["gira"].iterrows():
            camadas.append(dl.CircleMarker(
                center=[e.geometry.y, e.geometry.x],
                radius=6, color="#ffffff", weight=2,
                fillColor="#07733a", fillOpacity=1.0,
                children=[dl.Tooltip(e["nome_estacao"])]))

        # --- Cartoes de indicadores do Grupo 2 ---
        # As medidas de cobertura refletem o raio escolhido (exploratorio se
        # diferente do oficial); o IIC mantem-se o indicador oficial (R=500 m).
        cor = CORES_LINHA.get(indicadores["linha"], "#6b7280")
        cartoes = [
            _cartao_metro(f"{indicadores['iic']:.2f}",
                          f"IIC (oficial, R={raio_oficial} m)"),
            _cartao_metro(f"{cobertura['dist_gira_min_m']:.0f} m",
                          "GIRA mais próxima"),
            _cartao_metro(f"{cobertura['n_gira']}",
                          "Estações GIRA na área"),
            _cartao_metro(f"{cobertura['comp_ciclavel_m']/1000:.2f} km",
                          "Rede ciclável na área"),
            _cartao_metro(f"{cobertura['disp_pico']:.1f}",
                          "Disponib. nas horas de pico"),
        ]

        titulo_children = [
            html.Span(className="ponto-linha", style={"backgroundColor": cor}),
            html.Strong(indicadores["nome_metro"]),
            html.Span(f"linha {indicadores['linha']}", className="estacao-meta"),
        ]

        corpo = [
            html.Div(className="kpi-metro-titulo", children=titulo_children),
            html.Div(className="painel-kpis", children=cartoes),
        ]
        # Nota de raio: confirma o oficial ou assinala a exploracao.
        if exploratorio:
            corpo.append(html.Div(
                f"Cobertura calculada a R={raio} m (exploratório). "
                f"O IIC mantém-se no raio oficial de {raio_oficial} m.",
                className="nota-raio nota-raio--exploratorio"))
        else:
            corpo.append(html.Div(
                f"Raio de influência: {raio_oficial} m (oficial).",
                className="nota-raio"))

        kpis = html.Div(children=corpo)
        return camadas, kpis

    @app.callback(
        Output("metro", "hideout"),
        Output("legenda", "colorscale"),
        Output("legenda", "min"),
        Output("legenda", "max"),
        Output("legenda", "unit"),
        Output("legenda", "tickDecimals"),
        Input("filtro-indicador", "value"),
    )
    def codificar_mapa(prop):
        meta = INDICADORES_MAPA[prop]
        hideout = hideout_indicador(repo, prop)
        # A legenda inverte a ordem das cores quando o indicador e invertido,
        # mantendo a leitura coerente (verde = melhor).
        colorscale = list(reversed(ESCALA_COR)) if meta["inverter"] else ESCALA_COR
        return (hideout, colorscale, hideout["vmin"], hideout["vmax"],
                meta["unidade"], meta["decimais"])

    @app.callback(
        Output("grafico-comparacao", "figure"),
        Input("filtro-comparacao", "value"),
    )
    def atualizar_comparacao(ids_metro):
        return figures.figura_comparacao(repo, ids_metro or [])
