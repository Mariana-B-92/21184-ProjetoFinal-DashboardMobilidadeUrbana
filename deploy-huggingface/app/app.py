"""
Aplicacao Dash - camada de apresentacao.

Aplicacao de pagina unica, organizada nas cinco areas funcionais da seccao
2.5.1: cabecalho, painel lateral de filtros, mapa interativo, painel de
indicadores e area de analise complementar.

O painel de indicadores (coluna direita) e CONTEXTUAL, como nos storyboards:
mostra os KPIs globais sem selecao, os indicadores da estacao GIRA quando uma e
escolhida (Storyboard 2) e os indicadores do Grupo 2 da estacao de metro quando
e essa a selecao (Storyboard 3). As camadas do mapa sao controladas por
checkboxes no painel lateral (Storyboard 1 / seccao 2.5.1 e 2.5.3).
"""

import base64
import json

import dash_leaflet as dl
from dash import Dash, dcc, html
from dash_extensions.javascript import assign

import config
from app import callbacks
from app.data import RepositorioDados

# Basemap claro SEM rotulos + camada de rotulos por cima: cartografia mais limpa
# (os pontos coloridos passam a destacar-se sobre um fundo neutro).
TILE_BASE = "https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png"
TILE_ROTULOS = ("https://{s}.basemaps.cartocdn.com/light_only_labels/"
                "{z}/{x}/{y}{r}.png")
TILE_ATTR = ('&copy; <a href="https://www.openstreetmap.org/copyright">'
             'OpenStreetMap</a> &copy; <a href="https://carto.com/">CARTO</a>')
CENTRO_LISBOA = [38.736, -9.142]

repo = RepositorioDados()

# Marca do cabecalho (bicicleta + metro), embutida como SVG. base64 evita
# problemas de escape no data URI.
_MARCA_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="62" height="32" '
    'viewBox="0 0 62 32">'
    '<g fill="none" stroke="#ffffff" stroke-width="1.7" '
    'stroke-linecap="round" stroke-linejoin="round">'
    '<circle cx="9" cy="22" r="6.5"/><circle cx="29" cy="22" r="6.5"/>'
    '<path d="M9 22 L18 22 L24 11 L28 22"/><path d="M18 22 L22 11 L15 11"/>'
    '</g>'
    '<circle cx="49" cy="16" r="11" fill="none" stroke="#ffffff" '
    'stroke-width="1.7"/>'
    '<text x="49" y="21" text-anchor="middle" font-family="Archivo, sans-serif"'
    ' font-size="13" font-weight="800" fill="#ffffff">M</text></svg>'
)
_MARCA_URI = ("data:image/svg+xml;base64,"
              + base64.b64encode(_MARCA_SVG.encode()).decode())

# Renderizacao dos pontos GIRA. Como o metro, le os parametros de cor do hideout:
# em modo "categorico" (sem indicador GIRA escolhido) usa o verde de categoria;
# com um indicador do Grupo 1 selecionado, colore por classe (RdYlGn) e cresce.
_PONTO_GIRA = assign("""function(feature, latlng, context){
    const h = (context && context.hideout) ? context.hideout : {};
    let cor, raio, op, peso;
    if (h.categorico || !h.prop) {
        cor = h.cor_fixa || '#0a9a4a'; raio = 6; op = 0.9; peso = 1.5;
    } else {
        let v = feature.properties[h.prop];
        if (v === null || v === undefined) v = h.vmin;
        let t = (h.vmax > h.vmin) ? (v - h.vmin) / (h.vmax - h.vmin) : 0.5;
        if (h.inverter) t = 1 - t;
        t = Math.max(0, Math.min(1, t));
        const s = h.stops;
        const idx = Math.min(Math.floor(t * s.length), s.length - 1);
        const c = s[idx];
        cor = 'rgb(' + c[0] + ',' + c[1] + ',' + c[2] + ')';
        raio = 8; op = 1.0; peso = 2;
    }
    const _m = L.circleMarker(latlng, {radius: raio, color: '#ffffff', weight: peso,
        fillColor: cor, fillOpacity: op, pane: 'p-gira'});
    try { (window._giraLayers = window._giraLayers || {})[feature.properties.id_estacao] = _m; } catch (e) {}
    return _m;
}""")

# Pontos de metro: leem a cor do hideout (atualizado por callback). Em modo
# "categorico" usam cor unica; com indicador, classe discreta (RdYlGn), como nas
# legendas.
_PONTO_METRO = assign("""function(feature, latlng, context){
    const h = context.hideout;
    let cor, raio, op, peso;
    if (h.categorico) {
        // Vista inicial: igual a GIRA (so muda a cor), para coerencia estetica.
        cor = h.cor_fixa; raio = 6; op = 0.9; peso = 1.5;
    } else {
        let v = feature.properties[h.prop];
        if (v === null || v === undefined) v = h.vmin;
        let t = (h.vmax > h.vmin) ? (v - h.vmin) / (h.vmax - h.vmin) : 0.5;
        if (h.inverter) t = 1 - t;
        t = Math.max(0, Math.min(1, t));
        const s = h.stops;
        const idx = Math.min(Math.floor(t * s.length), s.length - 1);
        const c = s[idx];
        cor = 'rgb(' + c[0] + ',' + c[1] + ',' + c[2] + ')';
        // Modo indicador: o metro e o foco, fica maior.
        raio = 8; op = 1.0; peso = 2;
    }
    const _m = L.circleMarker(latlng, {radius: raio, color: '#ffffff', weight: peso,
        fillColor: cor, fillOpacity: op, pane: 'p-metro'});
    try { (window._metroLayers = window._metroLayers || {})[feature.properties.id_metro] = _m; } catch (e) {}
    return _m;
}""")

# Ao passar o rato: tooltip com o NOME da estacao (hover). Ao clicar: popup leve
# (nome + 1 indicador-chave) com o "x" de fecho do Leaflet. GIRA -> disp. media;
# metro -> IIC. O detalhe completo continua no painel lateral.
_POPUP_GIRA = assign("""function(feature, layer){
    const p = feature.properties || {};
    if (p.nome_estacao) layer.bindTooltip(p.nome_estacao, {direction: 'top'});
    const pct = (p.taxa_media_disponibilidade == null) ? '–'
        : Math.round(p.taxa_media_disponibilidade * 100) + '%';
    layer.bindPopup(
        '<div class="popup-mapa">'
        + '<div class="popup-tipo">Estação GIRA</div>'
        + '<div class="popup-nome">' + (p.nome_estacao || 'Estação') + '</div>'
        + '<div class="popup-linha"><span>Disponibilidade média</span><b>' + pct + '</b></div>'
        + '</div>');
    layer.on('popupclose', function(){
        if (window._abrindoPopup) return;   // fecho ao abrir outro popup: nao desselecciona
        const c = window.dash_clientside;
        if (c && c.set_props) {
            c.set_props('sel-gira', {data: null});
            c.set_props('sel-metro', {data: null});
            c.set_props('sel-gira-nome', {value: null});
            c.set_props('sel-metro-nome', {value: null});
        }
    });
}""")

_POPUP_METRO = assign("""function(feature, layer){
    const p = feature.properties || {};
    if (p.nome_metro) layer.bindTooltip(p.nome_metro, {direction: 'top'});
    const iic = (p.iic == null) ? '–' : p.iic.toFixed(2).replace('.', ',');
    layer.bindPopup(
        '<div class="popup-mapa">'
        + '<div class="popup-tipo">Estação de metro</div>'
        + '<div class="popup-nome">' + (p.nome_metro || 'Estação') + '</div>'
        + '<div class="popup-linha"><span>IIC</span><b>' + iic + '</b></div>'
        + '</div>');
    layer.on('popupclose', function(){
        if (window._abrindoPopup) return;   // fecho ao abrir outro popup: nao desselecciona
        const c = window.dash_clientside;
        if (c && c.set_props) {
            c.set_props('sel-gira', {data: null});
            c.set_props('sel-metro', {data: null});
            c.set_props('sel-gira-nome', {value: null});
            c.set_props('sel-metro-nome', {value: null});
        }
    });
}""")


# --------------------------------------------------------------------------- #
# Construcao das camadas do mapa a partir do repositorio
# --------------------------------------------------------------------------- #
def camada_gira():
    geojson = json.loads(repo.estacoes_gira.to_json())
    return dl.GeoJSON(
        id="gira", data=geojson, pointToLayer=_PONTO_GIRA, pane="p-gira",
        onEachFeature=_POPUP_GIRA,
        hideout=callbacks.hideout_categorico_gira(),
    )


def camada_metro():
    geojson = json.loads(repo.estacoes_metro.drop(columns=["buffer"]).to_json())
    return dl.GeoJSON(id="metro", data=geojson, pointToLayer=_PONTO_METRO,
                      pane="p-metro", onEachFeature=_POPUP_METRO,
                      hideout=callbacks.hideout_categorico_metro())


def camada_ciclavel():
    geojson = json.loads(repo.rede_ciclavel.to_json())
    return dl.GeoJSON(
        id="ciclavel", data=geojson, pane="p-ciclavel",
        style={"color": "#3b82f6", "weight": 2, "opacity": 0.6},
    )


def mapa():
    return dl.Map(
        id="mapa",
        center=CENTRO_LISBOA, zoom=12,
        children=[
            dl.TileLayer(url=TILE_BASE, attribution=TILE_ATTR),
            dl.TileLayer(url=TILE_ROTULOS),
            # Cada camada vive no seu pane. Os panes definem o empilhamento
            # (z-index): os realces ficam ABAIXO dos pontos base, para o clique
            # chegar sempre aos marcadores. A VISIBILIDADE e controlada por CSS
            # (classe no contentor do mapa esconde o pane), o que e fiavel e
            # mantem as camadas montadas — os callbacks de clique dependem dos
            # IDs "gira"/"metro" existirem sempre.
            dl.Pane(name="p-cobertura", id="pane-cobertura",
                    style={"zIndex": 350},
                    children=[dl.LayerGroup(id="camada-cobertura")]),
            dl.Pane(name="p-selecao", id="pane-selecao", style={"zIndex": 352},
                    children=[dl.LayerGroup(id="camada-gira-selecao")]),
            dl.Pane(name="p-comparacao", id="pane-comparacao",
                    style={"zIndex": 353},
                    children=[dl.LayerGroup(id="camada-comparacao")]),
            dl.Pane(name="p-ciclavel", id="pane-ciclavel",
                    style={"zIndex": 360}, children=[camada_ciclavel()]),
            dl.Pane(name="p-gira", id="pane-gira", style={"zIndex": 410},
                    children=[camada_gira()]),
            dl.Pane(name="p-metro", id="pane-metro", style={"zIndex": 420},
                    children=[camada_metro()]),
        ],
        style={"height": "100%", "width": "100%"},
    )


# --------------------------------------------------------------------------- #
# Opcoes / valores iniciais derivados dos dados
# --------------------------------------------------------------------------- #
# Opcoes do seletor de comparacao (todas as estacoes, ordenadas por nome) e
# selecao inicial = estacao de maior e de menor IIC (contraste imediato).
_metro_ord = repo.estacoes_metro.sort_values("nome_metro")
_OPCOES_METRO = [{"label": r["nome_metro"], "value": int(r["id_metro"])}
                 for _, r in _metro_ord.iterrows()]
_por_iic = repo.estacoes_metro.sort_values("iic")
_COMPARACAO_INICIAL = [int(_por_iic.iloc[-1]["id_metro"]),
                       int(_por_iic.iloc[0]["id_metro"])]

# Opcoes do seletor "Localizar estacao" GIRA (todas, ordenadas por nome).
_gira_ord = repo.estacoes_gira.sort_values("nome_estacao")
_OPCOES_GIRA = [{"label": r["nome_estacao"], "value": int(r["id_estacao"])}
                for _, r in _gira_ord.iterrows()]

# Periodo realmente coberto pelo historico GIRA (limita o seletor de datas).
_DATA_INICIO, _DATA_FIM = repo.intervalo_datas()


# --------------------------------------------------------------------------- #
# Layout (cinco areas funcionais)
# --------------------------------------------------------------------------- #
app = Dash(__name__, title="Mobilidade Lisboa")
server = app.server

def serve_layout():
    # Layout construido a pedido (serve_layout), nao no import: evita o import
    # circular figures<->callbacks (no 1.o pedido ja tudo esta carregado).
    return html.Div(className="app", children=[
    # Estado de selecao (estacao GIRA / metro escolhida; None = nenhuma).
    dcc.Store(id="sel-gira"),
    dcc.Store(id="sel-metro"),
    # Sumidouro do callback clientside que fecha o popup ao limpar a selecao.
    dcc.Store(id="_popup-sink"),
    # Sumidouro do callback clientside que fecha o "Sobre" (Esc / clique fora).
    dcc.Store(id="_sobre-sink"),

    # 1. Cabecalho (marca + titulo + "Sobre"), no tom azul-marinho dos
    # storyboards.
    html.Header(className="cabecalho", children=[
        html.Img(src=_MARCA_URI, className="cabecalho-marca",
                 alt="Bicicleta e metro"),
        html.Div(className="cabecalho-texto", children=[
            html.H1("Intermodalidade Bicicleta–Metro · Lisboa"),
            html.P("Análise da articulação entre o sistema GIRA, "
                   "a rede ciclável e o metro"),
        ]),
        html.Button("Sobre", id="abrir-sobre", n_clicks=0,
                    className="cabecalho-sobre"),
    ]),

    html.Div(className="corpo", children=[
        # 2. Painel lateral de filtros
        html.Aside(className="painel-filtros", children=[
            html.H2("Filtros"),
            html.Label("Localizar estação"),
            dcc.Dropdown(id="sel-gira-nome", options=_OPCOES_GIRA, value=None,
                         placeholder="Estação GIRA…",
                         className="dropdown-localizar"),
            dcc.Dropdown(id="sel-metro-nome", options=_OPCOES_METRO, value=None,
                         placeholder="Estação de metro…",
                         className="dropdown-localizar",
                         style={"marginTop": "6px"}),
            html.Label("Período de análise"),
            dcc.DatePickerRange(id="filtro-periodo", display_format="YYYY-MM-DD",
                                min_date_allowed=_DATA_INICIO,
                                max_date_allowed=_DATA_FIM,
                                start_date=_DATA_INICIO, end_date=_DATA_FIM),
            html.Label("Raio de influência (m)"),
            dcc.Slider(id="filtro-raio", min=250, max=1000, step=50,
                       value=config.RAIO_INFLUENCIA_M, updatemode="mouseup",
                       marks={250: "250", 500: "500", 750: "750", 1000: "1000"}),
            html.Label("Indicador no mapa"),
            dcc.Dropdown(id="filtro-indicador", clearable=True, value=None,
                         placeholder="Escolha um indicador",
                         options=[
                             {"label": "Metro · IIC (intermodalidade)",
                              "value": "iic"},
                             {"label": "Metro · N.º de estações GIRA",
                              "value": "n_gira_influencia"},
                             {"label": "Metro · Distância à GIRA mais próxima",
                              "value": "dist_gira_min_m"},
                             {"label": "Metro · Rede ciclável na área",
                              "value": "comp_ciclavel_m"},
                             {"label": "Metro · Disp. nas horas de pico",
                              "value": "disp_pico"},
                             {"label": "GIRA · Taxa média de disponibilidade",
                              "value": "taxa_media_disponibilidade"},
                             {"label": "GIRA · Disp. média (bicicletas)",
                              "value": "disponibilidade_media"},
                             {"label": "GIRA · Variabilidade diária (IVD)",
                              "value": "indice_variabilidade_diaria"},
                         ]),
            html.Label("Camadas do mapa"),
            dcc.Checklist(
                id="filtro-camadas", className="lista-camadas",
                options=[
                    {"label": "Estações GIRA", "value": "gira"},
                    {"label": "Estações de metro", "value": "metro"},
                    {"label": "Rede ciclável", "value": "ciclavel"},
                    {"label": "Área de influência", "value": "influencia"},
                ],
                value=["gira", "metro", "ciclavel", "influencia"]),
            html.Label("Pesos do IIC — ranking"),
            html.P("Afetam apenas o ranking de IIC (análise de sensibilidade). "
                   "O IIC de referência (0,40 / 0,35 / 0,25) mantém-se no mapa, "
                   "no medidor e na comparação.",
                   className="filtro-ajuda"),
            html.Div(className="pesos-iic", children=[
                html.Span("Proximidade", className="peso-rotulo"),
                dcc.Slider(id="peso-prox", min=0, max=1, step=0.05, value=0.40,
                           marks=None,
                           tooltip={"placement": "bottom",
                                    "always_visible": True}),
                html.Span("Densidade GIRA", className="peso-rotulo"),
                dcc.Slider(id="peso-dens", min=0, max=1, step=0.05, value=0.35,
                           marks=None,
                           tooltip={"placement": "bottom",
                                    "always_visible": True}),
                html.Span("Rede ciclável", className="peso-rotulo"),
                dcc.Slider(id="peso-cicl", min=0, max=1, step=0.05, value=0.25,
                           marks=None,
                           tooltip={"placement": "bottom",
                                    "always_visible": True}),
            ]),
            html.Button("Limpar filtros", id="limpar-filtros", n_clicks=0,
                        className="btn-limpar"),
        ]),

        # 3. Mapa interativo (elemento central) + legenda discreta sobreposta
        html.Main(className="area-mapa", children=[
            html.Div(id="mapa-camadas", className="mapa-camadas",
                     children=[mapa()]),
            html.Div(id="legenda", className="legenda-mapa"),
        ]),

        # 4. Painel de indicadores (CONTEXTUAL: global / GIRA / metro)
        html.Section(className="area-indicadores", children=[
            html.H2("Indicadores"),
            html.Div(id="painel-indicadores"),
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
            # Slot contextual: heatmap horario (GIRA) OU distribuicao das GIRA na
            # area de influencia (metro), conforme a selecao (Storyboards 2 e 3).
            dcc.Graph(id="grafico-heatmap", className="grafico",
                      config={"displayModeBar": False}),
            html.Div(className="bloco-comparacao", children=[
                html.Div(style={"display": "flex", "gap": "8px",
                                "alignItems": "center"}, children=[
                    dcc.Dropdown(
                        id="filtro-comp-a", options=_OPCOES_METRO,
                        value=_COMPARACAO_INICIAL[0], clearable=False,
                        className="dropdown-comparacao",
                        style={"flex": "1", "minWidth": "0"}),
                    html.Span("vs", style={"color": "var(--tinta-suave)",
                                           "fontSize": "12px",
                                           "fontWeight": "600"}),
                    dcc.Dropdown(
                        id="filtro-comp-b", options=_OPCOES_METRO,
                        value=_COMPARACAO_INICIAL[1], clearable=False,
                        className="dropdown-comparacao",
                        style={"flex": "1", "minWidth": "0"}),
                ]),
                dcc.Checklist(
                    id="comp-no-mapa",
                    options=[{"label": "Localizar no mapa", "value": "on"}],
                    value=[], className="check-mapa"),
                dcc.Graph(id="grafico-comparacao", className="grafico-comp",
                          config={"displayModeBar": False}),
            ]),
        ]),
    ]),

    # Painel "Sobre" (sobreposto), aberto pelo botao do cabecalho. A
    # visibilidade e controlada por className (ver alternar_sobre / CSS).
    html.Div(id="sobre-modal", className="sobre-modal", children=[
        html.Div(className="sobre-caixa", children=[
            html.Button("×", id="fechar-sobre", n_clicks=0,
                        className="sobre-fechar"),
            html.H2("Sobre este painel"),
            html.P("Analisa a articulação entre o sistema de bicicletas "
                   "partilhadas GIRA, a rede ciclável e a rede de metro de "
                   "Lisboa, para apoiar a leitura da intermodalidade e a "
                   "identificação de zonas prioritárias."),
            html.H3("Dados"),
            html.P("Estações GIRA e respetiva disponibilidade histórica, "
                   "estações de metro e rede ciclável executada. Os "
                   "indicadores são pré-calculados e persistidos; o histórico "
                   "de disponibilidade é consultado a pedido."),
            html.H3("Índice de Intermodalidade Composto (IIC)"),
            html.P("Média ponderada de três componentes normalizadas (0–1): "
                   "proximidade à GIRA mais próxima (0,40), densidade de "
                   "estações GIRA na área de influência (0,35) e comprimento "
                   "de rede ciclável na área (0,25). Valores próximos de 1 "
                   "indicam maior potencial intermodal."),
        ]),
    ]),
])


app.layout = serve_layout
callbacks.registar_callbacks(app, repo)


if __name__ == "__main__":
    app.run(debug=True)