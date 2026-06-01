"""
Aplicacao Dash - camada de apresentacao.

Esqueleto da aplicacao de pagina unica, organizado nas cinco areas funcionais da
seccao 2.5.1: cabecalho, painel lateral de filtros, mapa interativo, painel de
indicadores e area de analise complementar.

Esta versao estabelece a estrutura e liga o mapa as tres camadas geograficas
reais. A interatividade (callbacks) sera adicionada no passo seguinte.
"""

import json

import dash_leaflet as dl
from dash import Dash, dcc, html
from dash_extensions.javascript import assign

import config
from app import callbacks
from app.data import RepositorioDados

# Cores das linhas de metro de Lisboa (para codificacao visual no mapa).
CORES_LINHA = {
    "Azul": "#1f6fb2", "Amarela": "#f4c20d", "Verde": "#0a9a4a",
    "Vermelha": "#d6322e",
}
COR_GIRA = "#0a9a4a"
COR_METRO_OUTRA = "#6b7280"

# Basemap claro (estetica cartografica/analitica).
TILE_URL = "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
TILE_ATTR = ('&copy; <a href="https://www.openstreetmap.org/copyright">'
             'OpenStreetMap</a> &copy; <a href="https://carto.com/">CARTO</a>')
CENTRO_LISBOA = [38.736, -9.142]

repo = RepositorioDados()

# Renderizacao dos pontos GIRA como circulos (pointToLayer em JS).
_PONTO_GIRA = assign("""function(feature, latlng){
    return L.circleMarker(latlng, {radius: 4, color: '#0a9a4a', weight: 1,
        fillColor: '#0a9a4a', fillOpacity: 0.7});
}""")

# Renderizacao dos pontos de metro, coloridos pelo indicador selecionado.
# Le os parametros de cor do hideout (atualizado por callback).
_PONTO_METRO = assign("""function(feature, latlng, context){
    const h = context.hideout;
    let v = feature.properties[h.prop];
    if (v === null || v === undefined) v = h.vmin;
    let t = (h.vmax > h.vmin) ? (v - h.vmin) / (h.vmax - h.vmin) : 0.5;
    if (h.inverter) t = 1 - t;
    t = Math.max(0, Math.min(1, t));
    const s = h.stops; const n = s.length - 1;
    const seg = Math.min(Math.floor(t * n), n - 1);
    const u = t * n - seg;
    const a = s[seg], b = s[seg + 1];
    const cor = 'rgb(' + Math.round(a[0] + (b[0]-a[0])*u) + ',' +
                         Math.round(a[1] + (b[1]-a[1])*u) + ',' +
                         Math.round(a[2] + (b[2]-a[2])*u) + ')';
    return L.circleMarker(latlng, {radius: 8, color: '#ffffff', weight: 2,
        fillColor: cor, fillOpacity: 1.0});
}""")


# --------------------------------------------------------------------------- #
# Construcao das camadas do mapa a partir do repositorio
# --------------------------------------------------------------------------- #
def _cor_linha(linha):
    return CORES_LINHA.get(linha, COR_METRO_OUTRA)


def camada_gira():
    geojson = json.loads(repo.estacoes_gira.to_json())
    return dl.GeoJSON(
        id="gira", data=geojson, pointToLayer=_PONTO_GIRA,
        children=[dl.Tooltip("Estação GIRA")],
    )


def camada_metro():
    geojson = json.loads(repo.estacoes_metro.drop(columns=["buffer"]).to_json())
    return dl.GeoJSON(id="metro", data=geojson, pointToLayer=_PONTO_METRO,
                      hideout=callbacks.hideout_indicador(repo, "iic"))


def camada_ciclavel():
    geojson = repo.rede_ciclavel.to_json()
    return dl.GeoJSON(
        data=__import__("json").loads(geojson),
        style={"color": "#3b82f6", "weight": 2, "opacity": 0.6},
    )


def mapa():
    return dl.Map(
        id="mapa",
        center=CENTRO_LISBOA, zoom=12,
        children=[
            dl.TileLayer(url=TILE_URL, attribution=TILE_ATTR),
            dl.LayersControl([
                dl.Overlay(camada_ciclavel(), name="Rede ciclável", checked=True),
                dl.Overlay(camada_gira(), name="Estações GIRA", checked=True),
                dl.Overlay(camada_metro(), name="Estações de metro", checked=True),
            ]),
            # Destaque dinamico da analise de cobertura (preenchido por callback).
            dl.LayerGroup(id="camada-cobertura"),
            # Legenda da codificacao por indicador (atualizada por callback).
            dl.Colorbar(id="legenda", colorscale=callbacks.ESCALA_COR,
                        width=200, height=14, position="bottomright",
                        min=float(repo.estacoes_metro["iic"].min()),
                        max=float(repo.estacoes_metro["iic"].max()),
                        unit="", nTicks=4, tickDecimals=2,
                        className="legenda-mapa"),
        ],
        style={"height": "100%", "width": "100%"},
    )


# --------------------------------------------------------------------------- #
# Indicadores de sintese (estaticos por agora; dinamicos via callbacks depois)
# --------------------------------------------------------------------------- #
def cartao_kpi(valor, rotulo):
    return html.Div(className="kpi-card", children=[
        html.Div(valor, className="kpi-valor"),
        html.Div(rotulo, className="kpi-rotulo"),
    ])


def painel_indicadores():
    m = repo.estacoes_metro
    km_ciclavel = repo.rede_ciclavel["comp_km"].sum()
    return html.Div(className="painel-kpis", children=[
        cartao_kpi(f"{len(repo.estacoes_gira)}", "Estações GIRA"),
        cartao_kpi(f"{len(m)}", "Estações de metro"),
        cartao_kpi(f"{km_ciclavel:.0f} km", "Rede ciclável"),
        cartao_kpi(f"{m['iic'].mean():.2f}", "IIC médio"),
    ])


# Opcoes do seletor de comparacao (todas as estacoes, ordenadas por nome) e
# selecao inicial = estacao de maior e de menor IIC (contraste imediato).
_metro_ord = repo.estacoes_metro.sort_values("nome_metro")
_OPCOES_METRO = [{"label": r["nome_metro"], "value": int(r["id_metro"])}
                 for _, r in _metro_ord.iterrows()]
_por_iic = repo.estacoes_metro.sort_values("iic")
_COMPARACAO_INICIAL = [int(_por_iic.iloc[-1]["id_metro"]),
                       int(_por_iic.iloc[0]["id_metro"])]


# --------------------------------------------------------------------------- #
# Layout (cinco areas funcionais)
# --------------------------------------------------------------------------- #
app = Dash(__name__, title="Mobilidade Lisboa")
server = app.server

app.layout = html.Div(className="app", children=[
    # 1. Cabecalho
    html.Header(className="cabecalho", children=[
        html.H1("Intermodalidade Bicicleta–Metro · Lisboa"),
        html.P("Análise da articulação entre o sistema GIRA, "
               "a rede ciclável e o metro"),
    ]),

    html.Div(className="corpo", children=[
        # 2. Painel lateral de filtros
        html.Aside(className="painel-filtros", children=[
            html.H2("Filtros"),
            html.Label("Período de análise"),
            dcc.DatePickerRange(id="filtro-periodo", display_format="YYYY-MM-DD"),
            html.Label("Raio de influência (m)"),
            dcc.Slider(id="filtro-raio", min=250, max=1000, step=50,
                       value=config.RAIO_INFLUENCIA_M,
                       marks={250: "250", 500: "500", 750: "750", 1000: "1000"}),
            html.Label("Indicador no mapa"),
            dcc.Dropdown(id="filtro-indicador", clearable=False, value="iic",
                         options=[
                             {"label": "Índice de Intermodalidade (IIC)",
                              "value": "iic"},
                             {"label": "N.º de estações GIRA", "value": "n_gira_influencia"},
                             {"label": "Distância à GIRA mais próxima",
                              "value": "dist_gira_min_m"},
                         ]),
        ]),

        # 3. Mapa interativo (elemento central)
        html.Main(className="area-mapa", children=[mapa()]),

        # 4. Painel de indicadores
        html.Section(className="area-indicadores", children=[
            html.H2("Indicadores"),
            painel_indicadores(),
            html.Div(id="kpi-metro", className="kpi-metro"),
        ]),
    ]),

    # 5. Area de analise complementar
    html.Footer(className="area-analise", children=[
        html.Div(className="analise-cabecalho", children=[
            html.H2("Análise complementar"),
            html.Div(id="estacao-titulo", className="estacao-titulo"),
        ]),
        html.Div(className="analise-graficos", children=[
            dcc.Graph(id="grafico-serie", className="grafico",
                      config={"displayModeBar": False}),
            dcc.Graph(id="grafico-heatmap", className="grafico",
                      config={"displayModeBar": False}),
            html.Div(className="bloco-comparacao", children=[
                dcc.Dropdown(
                    id="filtro-comparacao", multi=True,
                    options=_OPCOES_METRO, value=_COMPARACAO_INICIAL,
                    placeholder="Estações a comparar…",
                    className="dropdown-comparacao"),
                dcc.Graph(id="grafico-comparacao", className="grafico-comp",
                          config={"displayModeBar": False}),
            ]),
        ]),
    ]),
])

callbacks.registar_callbacks(app, repo)


if __name__ == "__main__":
    app.run(debug=True)
