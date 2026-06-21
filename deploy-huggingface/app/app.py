"""Aplicacao Dash (camada de apresentacao): define o layout de pagina unica e
instancia a app.

O painel de indicadores e os graficos sao contextuais — adaptam-se a selecao
(GIRA, metro ou nenhuma); essa logica vive nos callbacks (app/callbacks.py).
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
        if (h.esbatido) { raio = 4; peso = 1; }
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
        fillColor: cor, fillOpacity: op, interactive: !h.esbatido,
        pane: h.esbatido ? 'p-contexto' : 'p-gira'});
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
        if (h.esbatido) { raio = 4; peso = 1; }
        else if (h.destaque) { raio = 8; op = 1.0; peso = 2; }  // foco na comparacao
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
        fillColor: cor, fillOpacity: op, interactive: !h.esbatido,
        pane: h.esbatido ? 'p-contexto' : 'p-metro'});
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


# Icone "camadas" (estilo Feather) para o controlo recolhido sobre o mapa.
_ICONE_CAMADAS = (
    "data:image/svg+xml;utf8,"
    "<svg xmlns='http://www.w3.org/2000/svg' width='20' height='20' "
    "viewBox='0 0 24 24' fill='none' stroke='%23277452' stroke-width='2' "
    "stroke-linecap='round' stroke-linejoin='round'>"
    "<polygon points='12 2 2 7 12 12 22 7 12 2'/>"
    "<polyline points='2 17 12 22 22 17'/>"
    "<polyline points='2 12 12 17 22 12'/></svg>"
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
            # Pane do tipo NAO-ativo (esbatido): abaixo dos marcadores base, para
            # o tipo em analise ficar sempre por cima. Sem filhos — os marcadores
            # da camada GIRA/metro entram aqui dinamicamente quando esbatidos.
            dl.Pane(name="p-contexto", id="pane-contexto", style={"zIndex": 400}),
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
    # Sumidouro do callback clientside que redimensiona os sliders dos pesos
    # quando a seccao colapsavel e aberta.
    dcc.Store(id="_pesos-sink"),
    # Estado da area de analise. 'analise-modo': 'analise' (conteudo contextual)
    # ou 'comparar' (ferramenta de comparacao). 'analise-vista': 'intro' (empty
    # state) ou 'graficos'. Juntos decidem o que se mostra em baixo.
    dcc.Store(id="analise-modo", data="analise"),
    dcc.Store(id="analise-vista", data="intro"),
    # Sumidouro do JS que realça a zona-alvo ao passar o rato num cartao da intro.
    dcc.Store(id="_acoes-sink"),

    # 1. Cabecalho (marca + titulo + "Sobre").
    html.Header(className="cabecalho", children=[
        html.Img(src=_MARCA_URI, className="cabecalho-marca",
                 alt="Bicicleta e metro"),
        html.Div(className="cabecalho-texto", children=[
            html.H1("Intermodalidade Bicicleta–Metro · Lisboa"),
            html.P("Análise da articulação entre o sistema GIRA, "
                   "a rede ciclável e o metro"),
        ]),
        html.Div(className="cabecalho-acoes", children=[
            html.Button("Início", id="btn-home", n_clicks=0,
                        className="cabecalho-btn",
                        title="Voltar à vista inicial (limpa estação e indicador)"),
            html.Button("Sobre", id="abrir-sobre", n_clicks=0,
                        className="cabecalho-btn"),
        ]),
    ]),

    html.Div(className="corpo", children=[
        # 2. Painel lateral de filtros
        html.Aside(className="painel-filtros", children=[
            html.H2("Filtros"),
            html.Label("Localizar estação"),
            dcc.Dropdown(id="sel-gira-nome", options=_OPCOES_GIRA, value=None,
                         placeholder="Estação GIRA…",
                         className="dropdown-localizar dropdown-localizar-gira"),
            dcc.Dropdown(id="sel-metro-nome", options=_OPCOES_METRO, value=None,
                         placeholder="Estação de metro…",
                         className="dropdown-localizar dropdown-localizar-metro",
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
                         # Memoriza a escolha na sessao: se a pagina recarregar
                         # (ex.: ao mover a janela para outro monitor), a selecao
                         # e reposta e o mapa volta a colorir-se sozinho.
                         persistence=True, persistence_type="session",
                         options=[
                             {"label": "Metro · IIC (intermodalidade)",
                              "value": "iic"},
                             {"label": "Metro · N.º de estações GIRA",
                              "value": "n_gira_influencia"},
                             {"label": "Metro · Rede ciclável na área",
                              "value": "comp_ciclavel_m"},
                             {"label": "Metro · Disp. nas horas de pico",
                              "value": "disp_pico"},
                             {"label": "GIRA · Disponibilidade média (bicicletas)",
                              "value": "disponibilidade_media"},
                             {"label": "GIRA · Variabilidade diária (IVD)",
                              "value": "indice_variabilidade_diaria"},
                         ]),
            html.Button("Limpar filtros", id="limpar-filtros", n_clicks=0,
                        className="btn-limpar"),
        ]),

        # 3. Mapa interativo (elemento central) + overlays sobrepostos:
        #    controlo de camadas (topo-direito, convencao Leaflet) e legenda
        #    (baixo-direita). Sao divs irmaos do mapa, por isso clicar neles nao
        #    desseleciona estacoes.
        html.Main(className="area-mapa", children=[
            html.Div(id="mapa-camadas", className="mapa-camadas",
                     children=[mapa()]),
            # Controlo de camadas no proprio mapa (canto), onde as ferramentas
            # de mapas convencionalmente o poem. Saiu do painel de filtros, que
            # fica so com filtros de dados.
            html.Div(id="controlo-camadas", className="controlo-camadas",
                     children=[
                # Recolhido (so o icone) por omissao; expande ao passar o rato,
                # a maneira do controlo de camadas nativo do Leaflet
                html.Img(src=_ICONE_CAMADAS, className="controlo-camadas-icone",
                         alt="Camadas"),
                html.Div(className="controlo-camadas-conteudo", children=[
                    html.Div("Camadas", className="controlo-camadas-titulo"),
                    html.Div(className="camadas-atalho", children=[
                        html.Button("Todas", id="camadas-todas", n_clicks=0),
                        html.Button("Nenhuma", id="camadas-nenhuma", n_clicks=0),
                    ]),
                    dcc.Checklist(
                        id="filtro-camadas", className="lista-camadas",
                        persistence=True, persistence_type="session",
                        options=[
                            {"label": "Estações GIRA", "value": "gira"},
                            {"label": "Estações de metro", "value": "metro"},
                            {"label": "Rede ciclável", "value": "ciclavel"},
                            {"label": "Área de influência", "value": "influencia"},
                        ],
                        value=list(config.CAMADAS_MAPA)),
                ]),
            ]),
            html.Div(id="legenda", className="legenda-mapa"),
        ]),

        # 4. Painel de indicadores (CONTEXTUAL: global / GIRA / metro)
        html.Section(className="area-indicadores", children=[
            html.H2("Indicadores"),
            html.Div(id="painel-indicadores"),
        ]),
    ]),

    # 5. Area de analise complementar. A className (modo-* / vista-*) e gerida
    # por callback e decide, via CSS, o que fica visivel — incluindo o titulo da
    # seccao, que acompanha o estado.
    html.Footer(id="area-analise",
                className="area-analise modo-analise vista-intro", children=[
        html.Div(className="analise-cabecalho", children=[
            html.H2("Para começar", id="analise-seccao-titulo"),
            html.Div(id="estacao-titulo", className="estacao-titulo"),
            # Porta de entrada (sempre visivel) da comparacao, para a manter
            # descobrivel sem ter o painel de comparacao montado o tempo todo.
            html.Button("Comparar estações de metro", id="btn-comparar",
                        n_clicks=0, className="btn-comparar"),
        ]),
        # Corpo contextual (os blocos abaixo sao mostrados/escondidos por CSS).
        html.Div(className="analise-corpo", children=[
            # (a) Empty state / onboarding — vista inicial, sem seleção.
            html.Div(className="analise-intro", children=[
                html.H3("Intermodalidade bicicleta–metro em Lisboa"),
                html.P(["Este painel cruza as bicicletas partilhadas ",
                        html.Strong("GIRA"), ", a ",
                        html.Strong("rede ciclável"), " e o ",
                        html.Strong("metro"), " para mostrar onde a ligação "
                        "entre bicicleta e metro é mais forte ou mais fraca. O ",
                        html.Strong("Índice de Intermodalidade Composto"),
                        " (IIC, 0–1) resume esse potencial em cada estação de "
                        "metro."]),
                # Cada cartao aponta (data-alvo) para o controlo real onde a acao
                # se faz; ao passar o rato, esse controlo fica realcado (ver JS).
                html.Div(className="analise-intro-acoes", children=[
                    html.Div(className="acao",
                             **{"data-alvo": ".area-mapa, .dropdown-localizar"},
                             children=[
                        html.Strong("Explorar uma estação"),
                        html.Span(["Clique numa estação no mapa, ou use ",
                                   html.Em("«Localizar estação»"),
                                   " nos filtros, para ver aqui a sua "
                                   "disponibilidade e indicadores."])]),
                    html.Div(className="acao",
                             **{"data-alvo": "#filtro-indicador"}, children=[
                        html.Strong("Ver um indicador"),
                        html.Span(["Escolha um indicador em ",
                                   html.Em("«Indicador no mapa»"),
                                   " para refletir o seu valor nas cores do "
                                   "mapa."])]),
                    html.Div(className="acao", **{"data-alvo": "#btn-comparar"},
                             children=[
                        html.Strong("Comparar estações"),
                        html.Span(["Use ", html.Em("«Comparar estações de "
                                   "metro»"), ", aqui em cima, para confrontar "
                                   "duas estações de metro."])]),
                ]),
            ]),
            # (b) Graficos contextuais — com seleção ou com o indicador IIC.
            html.Div(className="analise-graficos", children=[
                dcc.Graph(id="grafico-serie", className="grafico",
                          responsive=True,
                          config={"displayModeBar": False, "responsive": True}),
                # Slot contextual: heatmap horario (GIRA) / distribuicao das GIRA
                # (metro) / ranking de IIC (indicador IIC).
                dcc.Graph(id="grafico-heatmap", className="grafico",
                          responsive=True,
                          config={"displayModeBar": False, "responsive": True}),
                # Dica ao lado do ranking (so visivel na vista de um grafico, ex.
                # indicador IIC): liga a visao geral ao detalhe — visao geral
                # primeiro, detalhe a pedido. O data-alvo realca o mapa e o
                # localizador de metro ao passar o rato (mesmo mecanismo dos
                # cartoes da introducao).
                html.Div(className="analise-dica", id="dica-geral",
                         **{"data-alvo": ".area-mapa, .dropdown-localizar-metro"},
                         children=[
                    html.Div("Ver uma estação em detalhe",
                             className="analise-dica-titulo"),
                    html.P(["As estações estão ordenadas por este indicador. "
                            "Para ver o detalhe de uma delas, ",
                            html.Strong("clique nessa estação no mapa"),
                            " ou procure-a em ",
                            html.Strong("«Localizar estação»"), "."]),
                ]),
                # Pesos do IIC, ao LADO do ranking (so na vista do indicador IIC).
                # Ficam colados ao grafico que afetam. So recalculam este ranking; 
                # o IIC oficial(0,40 / 0,35 / 0,25) mantem-se no mapa, no medidor 
                # e no detalhe.
                # Coluna 2: painel de PESOS, que estica para a altura do grafico
                # (os sliders distribuem-se por flexbox nesse espaco).
                html.Div(className="analise-pesos", children=[
                    html.Div("Pesos do IIC (ranking)",
                             className="analise-pesos-titulo"),
                    html.P("Só afetam este ranking; o IIC oficial "
                           "mantém-se no mapa e no detalhe.",
                           className="analise-pesos-nota"),
                    html.Div(className="pesos-iic", children=[
                        html.Div(className="peso-bloco", children=[
                            html.Div(className="peso-linha", children=[
                                html.Span("Proximidade", className="peso-rotulo"),
                                html.Span("0,40", id="val-prox",
                                          className="peso-valor"),
                            ]),
                            dcc.Slider(id="peso-prox", min=0, max=1, step=0.05,
                                       value=0.40, marks=None, tooltip=None),
                        ]),
                        html.Div(className="peso-bloco", children=[
                            html.Div(className="peso-linha", children=[
                                html.Span("Densidade GIRA",
                                          className="peso-rotulo"),
                                html.Span("0,35", id="val-dens",
                                          className="peso-valor"),
                            ]),
                            dcc.Slider(id="peso-dens", min=0, max=1, step=0.05,
                                       value=0.35, marks=None, tooltip=None),
                        ]),
                        html.Div(className="peso-bloco", children=[
                            html.Div(className="peso-linha", children=[
                                html.Span("Rede ciclável", className="peso-rotulo"),
                                html.Span("0,25", id="val-cicl",
                                          className="peso-valor"),
                            ]),
                            dcc.Slider(id="peso-cicl", min=0, max=1, step=0.05,
                                       value=0.25, marks=None, tooltip=None),
                        ]),
                    ]),
                ]),
                # Coluna 3: a dica, num painel estreito a direita — tal como na
                # vista de disponibilidade media (3 colunas). Liga a visao geral
                # ao detalhe (clicar numa estacao).
                html.Div(className="analise-dica analise-dica-mini",
                         **{"data-alvo": ".area-mapa, .dropdown-localizar-metro"},
                         children=[
                    html.Div("Ver uma estação em detalhe",
                             className="analise-dica-titulo"),
                    html.P(["Para o detalhe de uma estação, ",
                            html.Strong("clique nela no mapa"),
                            " ou procure-a em ",
                            html.Strong("«Localizar estação»"), "."]),
                ]),
            ]),
            # (c) Ferramenta de comparacao — modo "comparar" (full width).
            html.Div(className="bloco-comparacao", children=[
                html.Div("Escolha duas estações de metro para confrontar o IIC "
                         "e as suas componentes:", className="comp-titulo"),
                html.Div(className="comp-seletores", children=[
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
                    dcc.Checklist(
                        id="comp-no-mapa",
                        options=[{"label": "Localizar no mapa", "value": "on"}],
                        value=[], className="check-mapa"),
                ]),
                html.Div(className="comp-grafico-wrap", children=[
                    dcc.Graph(id="grafico-comparacao", className="grafico-comp",
                              responsive=True,
                              config={"displayModeBar": False,
                                      "responsive": True}),
                ]),
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
            html.H3("Projeto"),
            html.P("Protótipo académico, para fins de demonstração e avaliação, "
                   "desenvolvido na unidade curricular de Projeto de Engenharia "
                   "Informática (Licenciatura em Engenharia Informática, "
                   "Universidade Aberta), no ano letivo 2025/2026."),
        ]),
    ]),
])


app.layout = serve_layout
callbacks.registar_callbacks(app, repo)


if __name__ == "__main__":
    app.run(debug=True)