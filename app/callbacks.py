"""
Callbacks da aplicacao Dash (seccao 2.5.3).

Interacoes implementadas:
- selecao de estacao (GIRA ou metro): mutuamente exclusiva, gerida num unico
  callback que alimenta os dois Stores. Permite tambem DESSELECIONAR (botao
  "Limpar selecao"), porque o clickData por si nunca se "desliga".
- clique numa GIRA: atualiza serie temporal, heatmap, titulo e realce no mapa,
  e preenche o painel direito com os indicadores do Grupo 1 (Storyboard 2);
- clique numa estacao de metro: desenha a area de influencia, destaca as GIRA e
  a rede ciclavel contidas, preenche os indicadores do Grupo 2 e o IIC, e mostra
  a distribuicao das GIRA na area no slot de analise (Storyboard 3);
- ajuste do raio, codificacao do mapa por indicador, comparacao entre duas
  estacoes, e ativacao/desativacao de camadas.
"""

import json

import dash_leaflet as dl
import geopandas as gpd
from dash import Input, Output, State, ctx, html, no_update

import config
from app import figures

# Cores das linhas de metro (coerentes com o mapa).
CORES_LINHA = {
    "Azul": "#1f6fb2", "Amarela": "#f4c20d", "Verde": "#0a9a4a",
    "Vermelha": "#d6322e",
}

# Cores de CATEGORIA (modo "Tipo de estacao", sem indicador): distinguir o que
# e cada coisa no mapa, mas com tom coerente. GIRA verde, metro azul (tom
# semelhante ao verde, nao o marinho escuro), rede ciclavel azul claro.
COR_GIRA = "#0a9a4a"
COR_METRO_CAT = "#2563b0"
COR_CICLAVEL = "#3b82f6"

# Escala de 5 classes (vermelho = baixo -> verde = alto). Centralizada no
# config (fonte unica), partilhada com os graficos. ESCALA_RGB e a versao
# [R,G,B] para o JS dos marcadores.
ESCALA_COR = config.ESCALA_COR
ESCALA_RGB = config.ESCALA_RGB

# Metadados dos indicadores do mapa.
# 'inverter': valores mais baixos = melhores (distancia) -> escala invertida
#   (verde = melhor). 'dominio': fixa o intervalo (ex.: IIC em [0,1]); sem ele,
#   usa-se o minimo/maximo reais dos dados.
INDICADORES_MAPA = {
    # --- Grupo 2: codificam as ESTACOES DE METRO ---
    "iic": {"fonte": "metro", "unidade": "", "decimais": 2, "inverter": False,
            "titulo": "IIC (0–1)", "dominio": (0.0, 1.0), "dec_legenda": 1},
    "n_gira_influencia": {"fonte": "metro", "unidade": "", "decimais": 0,
                          "inverter": False, "titulo": "N.º de estações GIRA",
                          "dec_legenda": 0},
    "dist_gira_min_m": {"fonte": "metro", "unidade": "m", "decimais": 0,
                        "inverter": True, "titulo": "Distância à GIRA (m)",
                        "dec_legenda": 0},
    "comp_ciclavel_m": {"fonte": "metro", "unidade": "m", "decimais": 0,
                        "inverter": False, "titulo": "Rede ciclável na área (m)",
                        "dec_legenda": 0},
    "disp_pico": {"fonte": "metro", "unidade": "", "decimais": 1,
                  "inverter": False, "titulo": "Disp. nas horas de pico",
                  "dec_legenda": 1},
    # --- Grupo 1: codificam as ESTACOES GIRA ---
    "taxa_media_disponibilidade": {
        "fonte": "gira", "unidade": "", "decimais": 2, "inverter": False,
        "titulo": "Taxa média de disponibilidade", "dominio": (0.0, 1.0),
        "dec_legenda": 2},
    "disponibilidade_media": {
        "fonte": "gira", "unidade": "", "decimais": 1, "inverter": False,
        "titulo": "Disp. média (bicicletas)", "dec_legenda": 1},
    "indice_variabilidade_diaria": {
        "fonte": "gira", "unidade": "", "decimais": 2, "inverter": False,
        "titulo": "Variabilidade diária (IVD)", "dec_legenda": 2},
}


def hideout_categorico_metro():
    """Hideout do metro no modo categorico (sem indicador, ou quando o indicador
    ativo e de GIRA): cor unica de categoria.

    Inclui tambem campos de gradiente validos (prop existente, vmin/vmax/stops),
    para que, mesmo que o JS dos marcadores esteja desatualizado e ignore o modo
    categorico, os pontos continuem a aparecer em vez de falharem em silencio.
    """
    return {"categorico": True, "cor_fixa": COR_METRO_CAT,
            "prop": "iic", "vmin": 0.0, "vmax": 1.0, "inverter": False,
            "stops": ESCALA_RGB}


def hideout_categorico_gira():
    """Hideout das GIRA no modo categorico (verde de categoria), com os mesmos
    campos de gradiente de reserva."""
    return {"categorico": True, "cor_fixa": COR_GIRA,
            "prop": "taxa_media_disponibilidade", "vmin": 0.0, "vmax": 1.0,
            "inverter": False, "stops": ESCALA_RGB}


def hideout_indicador(repo, prop):
    """Parametros de cor (hideout) para codificar o mapa por um indicador.

    Le os valores da fonte correta (GIRA ou metro) consoante o indicador.
    """
    meta = INDICADORES_MAPA[prop]
    fonte = repo.estacoes_gira if meta["fonte"] == "gira" else repo.estacoes_metro
    valores = fonte[prop]
    dominio = meta.get("dominio")
    vmin = float(dominio[0]) if dominio else float(valores.min())
    vmax = float(dominio[1]) if dominio else float(valores.max())
    return {
        "prop": prop,
        "vmin": vmin,
        "vmax": vmax,
        "inverter": meta["inverter"],
        "stops": ESCALA_RGB,
    }


def classes_legenda(vmin, vmax, n=None):
    """Limites inferiores das classes para a legenda discreta (faixas iguais)."""
    n = n or len(ESCALA_COR)
    if vmax <= vmin:
        return [vmin]
    passo = (vmax - vmin) / n
    return [vmin + i * passo for i in range(n)]


def _num_pt(v, decimais):
    """Formata um numero com virgula decimal (convencao portuguesa)."""
    return f"{v:.{decimais}f}".replace(".", ",")


def _legenda_categorica():
    """Legenda do modo 'Tipo de estacao': o que significa cada elemento no mapa."""
    itens = [
        ("Estações GIRA", COR_GIRA, "ponto"),
        ("Estações de metro", COR_METRO_CAT, "ponto"),
        ("Rede ciclável", COR_CICLAVEL, "traco"),
    ]
    linhas = []
    for rotulo, cor, forma in itens:
        classe = "legenda-traco" if forma == "traco" else "legenda-cor"
        linhas.append(html.Div(className="legenda-linha", children=[
            html.Span(className=classe, style={"backgroundColor": cor}),
            html.Span(rotulo, className="legenda-rotulo"),
        ]))
    return [html.Div("Tipo de estação", className="legenda-titulo"), *linhas]


def construir_legenda(prop, hideout, meta):
    """Legenda discreta por indicador (estilo storyboards): titulo + subtitulo
    ("estacoes de metro", para deixar claro que e o metro que esta colorido) +
    uma linha por classe (cor + intervalo).

    A ordem das cores acompanha a do mapa: invertida quando valores mais baixos
    sao melhores (distancia), de modo que verde = melhor.
    """
    vmin, vmax = hideout["vmin"], hideout["vmax"]
    cores = list(reversed(ESCALA_COR)) if meta["inverter"] else ESCALA_COR
    limites = classes_legenda(vmin, vmax) + [vmax]
    dec = meta.get("dec_legenda", meta["decimais"])
    sufixo = f" {meta['unidade']}" if meta["unidade"] else ""
    alvo = "estações GIRA" if meta.get("fonte") == "gira" else "estações de metro"

    linhas = [
        html.Div(meta["titulo"], className="legenda-titulo"),
        html.Div(alvo, className="legenda-subtitulo"),
    ]
    for i in range(len(ESCALA_COR)):
        lo, hi = limites[i], limites[i + 1]
        rotulo = f"{_num_pt(lo, dec)} – {_num_pt(hi, dec)}{sufixo}"
        linhas.append(html.Div(className="legenda-linha", children=[
            html.Span(className="legenda-cor",
                      style={"backgroundColor": cores[i]}),
            html.Span(rotulo, className="legenda-rotulo"),
        ]))
    return linhas


def gauge_iic(valor):
    """Mini-medidor 0–1 para o IIC, colorido pela classe (mesma paleta do mapa)."""
    v = max(0.0, min(1.0, float(valor)))
    return html.Div(className="gauge", children=[
        html.Div(className="gauge-trilho", children=[
            html.Div(className="gauge-fill",
                     style={"width": f"{v * 100:.0f}%",
                            "backgroundColor": config.cor_classe(v)})]),
        html.Div(className="gauge-escala", children=[
            html.Span("0"), html.Span("1")]),
    ])


# --------------------------------------------------------------------------- #
# Cartoes de indicadores (painel direito contextual)
# --------------------------------------------------------------------------- #
def _fmt(valor, sufixo="", decimais=1):
    """Formata um valor numerico, devolvendo '–' quando ausente."""
    if valor is None:
        return "–"
    try:
        if valor != valor:  # NaN
            return "–"
    except TypeError:
        return "–"
    if decimais == 0:
        return f"{valor:.0f}{sufixo}"
    return f"{valor:.{decimais}f}{sufixo}"


def _cartao(valor, rotulo, classe=""):
    return html.Div(className=f"kpi-card {classe}".strip(), children=[
        html.Div(valor, className="kpi-valor"),
        html.Div(rotulo, className="kpi-rotulo"),
    ])


def _cartao_iic(valor, rotulo):
    """Cartao do IIC com medidor 0–1, para leitura imediata do nivel."""
    return html.Div(className="kpi-card kpi-card--metro kpi-card--iic",
                    children=[
                        html.Div(_fmt(valor, decimais=2), className="kpi-valor"),
                        html.Div(rotulo, className="kpi-rotulo"),
                        gauge_iic(valor if valor is not None else 0.0),
                    ])


def painel_global(repo):
    """KPIs globais (vista inicial, sem selecao) — Storyboard 1.

    Disponibilidade media usa a taxa media de disponibilidade (TMD, em [0,1]),
    apresentada em percentagem. Para usar a media de bicicletas, substituir a
    coluna por 'disponibilidade_media' (ver nota no relatorio das metricas).
    """
    g = repo.estacoes_gira
    m = repo.estacoes_metro
    km_ciclavel = repo.rede_ciclavel["comp_km"].sum()
    tmd = g["taxa_media_disponibilidade"].mean(skipna=True)
    return html.Div(className="painel-kpis", children=[
        html.Div(className="kpi-card kpi-card--iic", children=[
            html.Div(_fmt(m["iic"].mean(), decimais=2), className="kpi-valor"),
            html.Div("IIC médio (0–1)", className="kpi-rotulo"),
            gauge_iic(m["iic"].mean()),
        ]),
        _cartao(f"{len(g)}", "Estações GIRA"),
        _cartao(f"{len(m)}", "Estações de metro"),
        _cartao(_fmt(tmd * 100, sufixo="%", decimais=0)
                if tmd == tmd else "–", "Disponibilidade média"),
        _cartao(f"{km_ciclavel:.0f} km", "Rede ciclável"),
    ])


def painel_gira(props):
    """Indicadores do Grupo 1 da estacao GIRA selecionada — Storyboard 2.

    Mostra os indicadores do Grupo 1 definidos no documento das metricas:
    disponibilidade media, TMD, IVD e hora de pico.
    """
    tmd = props.get("taxa_media_disponibilidade")
    hora = props.get("hora_pico")
    cartoes = [
        _cartao(_fmt(props.get("disponibilidade_media"), decimais=1),
                "Disponibilidade média (bicicletas)", "kpi-card--metro"),
        _cartao(_fmt(tmd * 100 if isinstance(tmd, (int, float)) else None,
                     sufixo="%", decimais=0),
                "Taxa média de disponibilidade", "kpi-card--metro"),
        _cartao(_fmt(props.get("indice_variabilidade_diaria"), decimais=2),
                "Índice de variabilidade diária", "kpi-card--metro"),
        _cartao(_fmt(hora, sufixo="h", decimais=0),
                "Hora de menor disponibilidade", "kpi-card--metro"),
        _cartao(_fmt(props.get("disponibilidade_hora_pico"), decimais=1),
                "Disponib. na hora de pico", "kpi-card--metro"),
        _cartao(_fmt(props.get("total_docas"), decimais=0),
                "Total de docas", "kpi-card--metro"),
    ]
    titulo = [
        html.Span(className="ponto-linha",
                  style={"backgroundColor": "#0a9a4a"}),
        html.Strong(props.get("nome_estacao",
                              f"Estação {props.get('id_estacao')}")),
        html.Span("estação GIRA", className="estacao-meta"),
    ]
    return html.Div(children=[
        html.Div(className="kpi-metro-titulo", children=titulo),
        html.Div(className="painel-kpis", children=cartoes),
    ])


def _camadas_cobertura(cobertura, indicadores):
    """Constroi as camadas de realce da area de influencia (mapa).

    Puramente visuais: ficam em panes abaixo dos marcadores base e sao
    interactive=False, para o clique chegar sempre ao ponto GIRA por baixo.
    """
    camadas = []
    buffer_gj = json.loads(
        gpd.GeoSeries([cobertura["buffer"]],
                      crs=config.CRS_GEOGRAFICO).to_json())
    camadas.append(dl.GeoJSON(
        data=buffer_gj, interactive=False, pane="p-cobertura",
        style={"color": "#1b211e", "weight": 1.5, "dashArray": "5 5",
               "fillColor": "#0a9a4a", "fillOpacity": 0.06}))
    if len(cobertura["ciclavel"]) > 0:
        ciclavel_gj = json.loads(cobertura["ciclavel"].to_json())
        camadas.append(dl.GeoJSON(
            data=ciclavel_gj, interactive=False, pane="p-cobertura",
            style={"color": "#1f6fb2", "weight": 4, "opacity": 0.9}))
    for _, e in cobertura["gira"].iterrows():
        camadas.append(dl.CircleMarker(
            center=[e.geometry.y, e.geometry.x],
            radius=6, color="#ffffff", weight=2,
            fillColor="#07733a", fillOpacity=1.0,
            interactive=False, pane="p-cobertura"))
    ponto_metro = indicadores["geometry"]
    camadas.append(dl.CircleMarker(
        center=[ponto_metro.y, ponto_metro.x], radius=16,
        color="#1b211e", weight=3, fill=False,
        interactive=False, pane="p-cobertura",
        children=[dl.Tooltip(indicadores["nome_metro"], permanent=True,
                             direction="top", pane="tooltipPane")]))
    return camadas


def painel_metro(repo, props, raio):
    """Indicadores do Grupo 2 da estacao de metro + camadas do mapa — SB 3."""
    id_metro = props.get("id_metro")
    cobertura = repo.cobertura_metro(id_metro, raio=raio)
    indicadores = repo.indicadores_metro(id_metro)
    raio_oficial = config.RAIO_INFLUENCIA_M
    exploratorio = raio != raio_oficial

    cor = CORES_LINHA.get(indicadores["linha"], "#6b7280")
    cartoes = [
        _cartao_iic(indicadores["iic"], f"IIC (oficial · R={raio_oficial} m)"),
        _cartao(f"{cobertura['dist_gira_min_m']:.0f} m",
                "GIRA mais próxima", "kpi-card--metro"),
        _cartao(f"{cobertura['n_gira']}",
                "Estações GIRA na área", "kpi-card--metro"),
        _cartao(f"{cobertura['comp_ciclavel_m'] / 1000:.2f} km",
                "Rede ciclável na área", "kpi-card--metro"),
        _cartao(f"{cobertura['disp_pico']:.1f}",
                "Disponib. nas horas de pico", "kpi-card--metro"),
    ]
    titulo = [
        html.Span(className="ponto-linha", style={"backgroundColor": cor}),
        html.Strong(indicadores["nome_metro"]),
        html.Span(f"linha {indicadores['linha']}", className="estacao-meta"),
    ]
    corpo = [
        html.Div(className="kpi-metro-titulo", children=titulo),
        html.Div(className="painel-kpis", children=cartoes),
    ]
    if exploratorio:
        corpo.append(html.Div(
            f"Cobertura calculada a R={raio} m (exploratório). "
            f"O IIC mantém-se no raio oficial de {raio_oficial} m.",
            className="nota-raio nota-raio--exploratorio"))
    else:
        corpo.append(html.Div(
            f"Raio de influência: {raio_oficial} m (oficial).",
            className="nota-raio"))

    painel = html.Div(children=corpo)
    camadas = _camadas_cobertura(cobertura, indicadores)
    return painel, camadas


# --------------------------------------------------------------------------- #
# Registo dos callbacks
# --------------------------------------------------------------------------- #
def registar_callbacks(app, repo):

    @app.callback(
        Output("sel-gira", "data"),
        Output("sel-metro", "data"),
        Output("sel-gira-nome", "value"),
        Output("sel-metro-nome", "value"),
        Output("mapa", "center"),
        Input("gira", "clickData"),
        Input("metro", "clickData"),
        Input("mapa", "clickData"),
        Input("sel-gira-nome", "value"),
        Input("sel-metro-nome", "value"),
        State("sel-gira", "data"),
        State("sel-metro", "data"),
        prevent_initial_call=True,
    )
    def gerir_selecao(click_gira, click_metro, _click_mapa, nome_gira,
                      nome_metro, sel_gira_atual, sel_metro_atual):
        # Seleccao mutuamente exclusiva, sincronizada entre o mapa e o seletor
        # "Localizar estacao" da esquerda:
        #  - clicar numa estacao seleciona-a E preenche o seletor com o seu nome;
        #  - escolher um nome seleciona-a e centra o mapa nela;
        #  - LIMPAR o seletor (x) desseleciona e volta a vista inicial;
        #  - clicar no fundo do mapa desseleciona tudo.
        # O State (selecao atual) evita lacos quando preenchemos o seletor
        # programaticamente apos um clique no mapa.
        acionados = {t["prop_id"].split(".")[0] for t in ctx.triggered}

        # Fundo do mapa -> limpa tudo.
        if "mapa" in acionados:
            return None, None, None, None, no_update

        # Clique numa estacao GIRA -> seleciona e mostra o nome no seletor.
        if "gira" in acionados and click_gira:
            props = click_gira.get("properties")
            gid = int(props["id_estacao"]) if props and props.get(
                "id_estacao") is not None else None
            return props, None, gid, None, no_update

        # Clique numa estacao de metro.
        if "metro" in acionados and click_metro:
            props = click_metro.get("properties")
            mid = int(props["id_metro"]) if props and props.get(
                "id_metro") is not None else None
            return None, props, None, mid, no_update

        # Seletor de NOME da GIRA.
        if "sel-gira-nome" in acionados:
            if not nome_gira:                       # x do seletor -> desseleciona
                if sel_gira_atual is not None:
                    return None, None, no_update, no_update, no_update
                return (no_update,) * 5
            props = repo.props_gira(nome_gira)
            if not props:
                return (no_update,) * 5
            # Ja selecionada (seletor preenchido por um clique no mapa): nao
            # repetir nem voltar a centrar.
            if (sel_gira_atual
                    and sel_gira_atual.get("id_estacao") == props.get("id_estacao")):
                return (no_update,) * 5
            centro = [props.get("latitude"), props.get("longitude")]
            return props, None, no_update, None, centro

        # Seletor de NOME do metro.
        if "sel-metro-nome" in acionados:
            if not nome_metro:
                if sel_metro_atual is not None:
                    return None, None, no_update, no_update, no_update
                return (no_update,) * 5
            props = repo.props_metro(nome_metro)
            if not props:
                return (no_update,) * 5
            if (sel_metro_atual
                    and sel_metro_atual.get("id_metro") == props.get("id_metro")):
                return (no_update,) * 5
            return None, props, None, no_update, repo.centro_metro(nome_metro)

        return (no_update,) * 5

    @app.callback(
        Output("filtro-periodo", "start_date"),
        Output("filtro-periodo", "end_date"),
        Output("filtro-raio", "value"),
        Output("filtro-indicador", "value"),
        Output("filtro-camadas", "value"),
        Output("peso-prox", "value"),
        Output("peso-dens", "value"),
        Output("peso-cicl", "value"),
        Input("limpar-filtros", "n_clicks"),
        prevent_initial_call=True,
    )
    def limpar_filtros(_n):
        # Repoe os filtros nos valores iniciais (nao mexe na selecao, que se
        # limpa clicando no fundo do mapa). Os pesos do IIC voltam aos de
        # referencia (0,40 / 0,35 / 0,25).
        inicio, fim = repo.intervalo_datas()
        return (inicio, fim, config.RAIO_INFLUENCIA_M, None,
                ["gira", "metro", "ciclavel", "influencia"], 0.40, 0.35, 0.25)

    @app.callback(
        Output("painel-indicadores", "children"),
        Output("camada-cobertura", "children"),
        Input("sel-gira", "data"),
        Input("sel-metro", "data"),
        Input("filtro-raio", "value"),
    )
    def atualizar_indicadores(sel_gira, sel_metro, raio):
        # Painel direito contextual + camadas de cobertura no mapa.
        if sel_metro:
            painel, camadas = painel_metro(repo, sel_metro, raio)
            return painel, camadas
        if sel_gira:
            return painel_gira(sel_gira), []
        return painel_global(repo), []

    @app.callback(
        Output("grafico-serie", "figure"),
        Output("grafico-heatmap", "figure"),
        Output("estacao-titulo", "children"),
        Output("camada-gira-selecao", "children"),
        Input("sel-gira", "data"),
        Input("sel-metro", "data"),
        Input("filtro-periodo", "start_date"),
        Input("filtro-periodo", "end_date"),
        Input("filtro-raio", "value"),
        Input("peso-prox", "value"),
        Input("peso-dens", "value"),
        Input("peso-cicl", "value"),
    )
    def atualizar_analise(sel_gira, sel_metro, inicio, fim, raio,
                          w_prox, w_dens, w_cicl):
        id_gira = sel_gira.get("id_estacao") if sel_gira else None

        # Slots de analise conforme a selecao:
        # - GIRA: serie + heatmap dessa estacao (SB 2);
        # - metro: serie do CONJUNTO de GIRA na area + distribuicao (SB 3);
        # - nada: serie GLOBAL + ranking das estacoes de metro por IIC (sintese,
        #   sensivel aos pesos escolhidos).
        if id_gira is not None:
            serie = figures.figura_serie_temporal(repo, id_gira, inicio, fim)
            segundo = figures.figura_heatmap(repo, id_gira, inicio, fim)
        elif sel_metro:
            # Cobertura calculada uma so vez e reutilizada nas duas figuras.
            cob = repo.cobertura_metro(sel_metro.get("id_metro"), raio=raio)
            ids = (cob["gira"]["id_estacao"].tolist()
                   if cob and len(cob["gira"]) else [])
            serie = figures.figura_serie_conjunto(repo, ids, inicio, fim)
            segundo = figures.figura_distribuicao_gira(
                repo, sel_metro.get("id_metro"), raio, cobertura=cob)
        else:
            serie = figures.figura_serie_global(repo, inicio, fim)
            segundo = figures.figura_ranking_iic(
                repo, pesos=(w_prox, w_dens, w_cicl))

        # Titulo da analise complementar.
        if id_gira is not None:
            nome = sel_gira.get("nome_estacao", f"Estação {id_gira}")
            titulo = html.Span([
                html.Strong(nome),
                html.Span(
                    f"  ·  menor disp. às {int(sel_gira.get('hora_pico', 0) or 0)}h"
                    f"  ·  {sel_gira.get('total_docas', '–')} docas",
                    className="estacao-meta"),
            ])
        elif sel_metro:
            titulo = html.Span([
                html.Strong(sel_metro.get("nome_metro", "Estação de metro")),
                html.Span(f"  ·  área de influência (R={raio} m)",
                          className="estacao-meta"),
            ])
        else:
            titulo = html.Span("Nenhuma estação selecionada",
                               className="sem-selecao")

        # Realce da GIRA selecionada no mapa (anel + etiqueta permanente).
        realce = []
        if id_gira is not None:
            lat = sel_gira.get("latitude")
            lon = sel_gira.get("longitude")
            nome = sel_gira.get("nome_estacao", f"Estação {id_gira}")
            if lat is not None and lon is not None:
                realce = [dl.CircleMarker(
                    center=[lat, lon], radius=11, color="#1b211e", weight=3,
                    fill=False, interactive=False, pane="p-selecao",
                    children=[dl.Tooltip(nome, permanent=True,
                                         direction="top", pane="tooltipPane")])]
        return serie, segundo, titulo, realce

    @app.callback(
        Output("gira", "hideout"),
        Output("metro", "hideout"),
        Output("legenda", "children"),
        Input("filtro-indicador", "value"),
    )
    def codificar_mapa(prop):
        # Sem indicador (None): mapa em modo "tipo de estacao" (ambos categoricos).
        if not prop:
            return (hideout_categorico_gira(), hideout_categorico_metro(),
                    _legenda_categorica())
        meta = INDICADORES_MAPA[prop]
        hideout = hideout_indicador(repo, prop)
        legenda = construir_legenda(prop, hideout, meta)
        # O indicador colore a sua fonte; a outra camada fica em modo categorico
        # (cor de categoria, marcador menor) para servir de contexto.
        if meta["fonte"] == "gira":
            return hideout, hideout_categorico_metro(), legenda
        return hideout_categorico_gira(), hideout, legenda

    @app.callback(
        Output("grafico-comparacao", "figure"),
        Output("camada-comparacao", "children"),
        Input("filtro-comp-a", "value"),
        Input("filtro-comp-b", "value"),
        Input("comp-no-mapa", "value"),
    )
    def atualizar_comparacao(id_a, id_b, no_mapa):
        ids = list(dict.fromkeys(i for i in (id_a, id_b) if i is not None))
        figura = figures.figura_comparacao(repo, ids)
        # Destaque no mapa opcional (desligado por defeito). Com "Localizar no
        # mapa" ativo, desenha um anel por estacao, na cor da sua barra.
        if "on" not in (no_mapa or []):
            return figura, []
        metro = repo.estacoes_metro
        realces = []
        for i, id_m in enumerate(ids):
            sel = metro[metro["id_metro"] == int(id_m)]
            if sel.empty:
                continue
            linha = sel.iloc[0]
            cor = config.PALETA_COMPARACAO[i % len(config.PALETA_COMPARACAO)]
            realces.append(dl.CircleMarker(
                center=[linha.geometry.y, linha.geometry.x],
                radius=13, color=cor, weight=3, fill=False, interactive=False,
                pane="p-comparacao",
                children=[dl.Tooltip(linha["nome_metro"], permanent=True,
                                     direction="top", pane="tooltipPane")]))
        return figura, realces

    @app.callback(
        Output("mapa-camadas", "className"),
        Input("filtro-camadas", "value"),
    )
    def alternar_camadas(ativas):
        # A visibilidade e dada por CSS: para cada camada DESLIGADA, adiciona-se
        # uma classe "cam-oculta-<x>" ao contentor, e o style.css esconde o pane
        # correspondente. Mantem as camadas montadas (cliques continuam a
        # funcionar) e aplica-se sempre (ao contrario de alterar o style do pane).
        ativas = set(ativas or [])
        todas = ["gira", "metro", "ciclavel", "influencia"]
        ocultas = [f"cam-oculta-{c}" for c in todas if c not in ativas]
        return " ".join(["mapa-camadas", *ocultas])

    @app.callback(
        Output("sobre-modal", "className"),
        Input("abrir-sobre", "n_clicks"),
        Input("fechar-sobre", "n_clicks"),
        prevent_initial_call=True,
    )
    def alternar_sobre(_abrir, _fechar):
        # Abre o painel se o disparo veio do botao do cabecalho; fecha caso
        # contrario (botao de fechar). A visibilidade efetiva e dada pelo CSS.
        acionados = {t["prop_id"].split(".")[0] for t in ctx.triggered}
        if "abrir-sobre" in acionados:
            return "sobre-modal aberto"
        return "sobre-modal"

    # Sincroniza o popup do mapa com a selecao (em ambos os sentidos), do lado do
    # cliente porque o popup e gerido pelo Leaflet:
    #  - selecao vazia -> fecha o popup aberto (clicando no seu botao de fecho);
    #  - estacao selecionada (por nome ou clique) -> abre o popup dessa estacao,
    #    usando o indice de marcadores criado no pointToLayer. A bandeira
    #    "_abrindoPopup" evita que o fecho automatico do popup anterior
    #    (ao abrir outro) seja interpretado como desselecao.
    app.clientside_callback(
        """
        function(g, m) {
            var c = window.dash_clientside;
            if (!g && !m) {
                document.querySelectorAll('.leaflet-popup-close-button')
                        .forEach(function(b) { b.click(); });
                return c.no_update;
            }
            try {
                var layer = null;
                if (g && window._giraLayers) layer = window._giraLayers[g.id_estacao];
                else if (m && window._metroLayers) layer = window._metroLayers[m.id_metro];
                if (layer) {
                    window._abrindoPopup = true;
                    layer.openPopup();
                    setTimeout(function() { window._abrindoPopup = false; }, 0);
                }
            } catch (e) {}
            return c.no_update;
        }
        """,
        Output("_popup-sink", "data"),
        Input("sel-gira", "data"),
        Input("sel-metro", "data"),
        prevent_initial_call=True,
    )

    # Fecho do painel "Sobre" por Esc ou clique no fundo (alem do botao x), como
    # se espera de um modal. Os ouvintes sao ligados ao documento uma unica vez
    # (no primeiro clique de abertura) e fecham via set_props, em coerencia com o
    # botao de fechar (que tambem repoe a className "sobre-modal").
    app.clientside_callback(
        """
        function(_n) {
            if (!window._sobreInit) {
                window._sobreInit = true;
                var fechar = function() {
                    var m = document.getElementById('sobre-modal');
                    if (m && m.classList.contains('aberto')) {
                        window.dash_clientside.set_props(
                            'sobre-modal', {className: 'sobre-modal'});
                    }
                };
                document.addEventListener('keydown', function(e) {
                    if (e.key === 'Escape') fechar();
                });
                var m = document.getElementById('sobre-modal');
                if (m) m.addEventListener('click', function(e) {
                    if (e.target === m) fechar();   // so o fundo, nao a caixa
                });
            }
            return window.dash_clientside.no_update;
        }
        """,
        Output("_sobre-sink", "data"),
        Input("abrir-sobre", "n_clicks"),
        prevent_initial_call=True,
    )