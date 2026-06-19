"""Registo dos callbacks da aplicacao Dash."""

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

# Cores de CATEGORIA (modo "Tipo de estacao", sem indicador).
COR_GIRA = "#0a9a4a"
COR_METRO_CAT = "#2563b0"
COR_CICLAVEL = "#3b82f6"

# Escala de 5 classes (vermelho = baixo -> verde = alto), centralizada no config
# para a partilhar com os graficos. ESCALA_RGB e a versao [R,G,B] para o JS dos
# marcadores.
ESCALA_COR = config.ESCALA_COR
ESCALA_RGB = config.ESCALA_RGB


def _acionados():
    """Ids dos componentes que dispararam o callback atual."""
    return {t["prop_id"].split(".")[0] for t in ctx.triggered}

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

# Indicadores cuja vista SEM selecao e um unico ranking de extremos. Partilham a
# mesma forma, por isso ficam aqui num so sitio (em vez de repetidos no bloco de
# figuras E no de titulos). 'painel' e o titulo mostrado por cima.
RANKINGS_SEM_SELECAO = {
    "n_gira_influencia": dict(
        fonte="metro", eixo="N.º de estações GIRA na área",
        hover_sufixo=" estações GIRA na área",
        titulo="Estações de metro por n.º de GIRA na área (maior e menor)",
        casas=0, painel="Ranking por n.º de GIRA na área"),
    "disp_pico": dict(
        fonte="metro", eixo="Bicicletas na hora de pico",
        hover_sufixo=" bicicletas na hora de pico",
        titulo="Estações de metro por disponibilidade na hora de pico "
               "(maior e menor)",
        casas=1, painel="Ranking por disponibilidade na hora de pico"),
    "comp_ciclavel_m": dict(
        fonte="metro", eixo="Rede ciclável na área (km)",
        hover_sufixo=" km de rede ciclável",
        titulo="Estações de metro por rede ciclável na área (maior e menor)",
        casas=2, escala=0.001, painel="Ranking por rede ciclável na área"),
    "indice_variabilidade_diaria": dict(
        fonte="gira", eixo="Variabilidade diária (IVD)",
        hover_sufixo=" de IVD",
        titulo="Estações GIRA por variabilidade diária (maior e menor)",
        casas=2, painel="Ranking por variabilidade diária (IVD)"),
}


def hideout_categorico_metro(contexto=False, destaque=False):
    """Hideout do metro no modo categorico: cor unica. 'contexto=True' esbate a
    camada (tipo nao-ativo); 'destaque=True' aumenta ligeiramente os pontos (foco
    na comparacao de estacoes de metro).

    Inclui campos de gradiente de reserva (prop existente, vmin/vmax/stops) para
    que, se o JS dos marcadores ignorar o modo categorico, os pontos ainda
    aparecam em vez de falharem em silencio.
    """
    return {"categorico": True, "cor_fixa": COR_METRO_CAT, "esbatido": contexto,
            "destaque": destaque,
            "prop": "iic", "vmin": 0.0, "vmax": 1.0, "inverter": False,
            "stops": ESCALA_RGB}


def hideout_categorico_gira(contexto=False):
    """Hideout das GIRA no modo categorico (verde), com os mesmos campos de
    gradiente de reserva. 'contexto=True' esbate (tipo nao-ativo)."""
    return {"categorico": True, "cor_fixa": COR_GIRA, "esbatido": contexto,
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
    """Legenda do modo 'Tipo de estacao'."""
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
    """Legenda discreta por indicador (titulo + subtitulo + uma linha por classe).

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


# Texto de ajuda do IIC, mostrado num tooltip nativo (nunca cortado pelo
# overflow do painel).
_AJUDA_IIC = (
    "Índice de Intermodalidade Composto (0–1): média ponderada da proximidade "
    "à GIRA mais próxima (0,40), da densidade de estações GIRA na área de "
    "influência (0,35) e do comprimento de rede ciclável na área (0,25). "
    "Valores próximos de 1 indicam maior potencial de ligação bicicleta–metro."
)


def _ajuda(texto):
    """'?' de ajuda: a explicacao surge no hover via tooltip nativo (nao cortado
    pelo overflow do painel)."""
    return html.Span("?", className="ajuda-info", title=texto)


def _cartao_iic(valor, rotulo):
    """Cartao do IIC com medidor 0–1, para leitura imediata do nivel."""
    return html.Div(className="kpi-card kpi-card--metro kpi-card--iic",
                    children=[
                        html.Div(_fmt(valor, decimais=2), className="kpi-valor"),
                        html.Div([rotulo, _ajuda(_AJUDA_IIC)],
                                 className="kpi-rotulo"),
                        gauge_iic(valor if valor is not None else 0.0),
                    ])


def _cartao_componente(rotulo, valor):
    """Cartao de uma componente do IIC: media 0-1 + barra proporcional, na
    mesma paleta do mapa (vermelho->verde)."""
    ok = valor is not None and valor == valor          # exclui None e NaN
    v = max(0.0, min(1.0, float(valor))) if ok else 0.0
    return html.Div(className="kpi-card kpi-card--metro", children=[
        html.Div(_fmt(valor, decimais=2), className="kpi-valor"),
        html.Div(rotulo, className="kpi-rotulo"),
        html.Div(className="gauge gauge--mini", children=[
            html.Div(className="gauge-trilho", children=[
                html.Div(className="gauge-fill",
                         style={"width": f"{v * 100:.0f}%",
                                "backgroundColor": config.cor_classe(v)})]),
        ]),
    ])


def painel_global(repo):
    """KPIs da vista inicial (sem selecao): IIC medio da rede e, por estacao de
    metro, a media das condicoes que o determinam.

    A escala da rede (contagens e km totais) vai na frase de introducao, nao em
    cartoes; a taxa de disponibilidade GIRA fica fora (nao e sobre a articulacao
    metro-bicicleta).
    """
    g = repo.estacoes_gira
    m = repo.estacoes_metro
    km_ciclavel = repo.rede_ciclavel["comp_km"].sum()
    intro = html.Div(className="painel-intro", children=[
        html.P(f"Rede com {len(m)} estações de metro, {len(g)} GIRA e "
               f"{km_ciclavel:.0f} km de ciclovia. Clique numa estação no mapa "
               "para ver os seus indicadores."),
    ])
    cartoes = [
        # IIC medio da rede (com medidor).
        html.Div(className="kpi-card kpi-card--iic", children=[
            html.Div(_fmt(m["iic"].mean(), decimais=2), className="kpi-valor"),
            html.Div(["IIC médio (0–1)", _ajuda(_AJUDA_IIC)],
                     className="kpi-rotulo"),
            gauge_iic(m["iic"].mean()),
        ]),
        # Condicoes medias que determinam o IIC, por estacao de metro.
        html.Div("Por estação de metro (média)",
                 className="painel-subcabecalho"),
        _cartao(_fmt(m["n_gira_influencia"].mean(), decimais=1),
                "N.º de GIRA na área", "kpi-card--metro"),
        _cartao(_fmt(m["dist_gira_min_m"].mean(), sufixo=" m", decimais=0),
                "Distância à GIRA mais próxima", "kpi-card--metro"),
        _cartao(_fmt(m["comp_ciclavel_m"].mean() * 0.001, sufixo=" km",
                     decimais=2), "Rede ciclável na área", "kpi-card--metro"),
        _cartao(_fmt(m["disp_pico"].mean(), decimais=1),
                "Disp. na hora de pico", "kpi-card--metro"),
    ]
    return html.Div(children=[
        intro, html.Div(className="painel-kpis", children=cartoes)])


def painel_indicador(repo, prop):
    """Resumo do indicador ATIVO na rede (sem estacao selecionada).

    Da a tendencia central (media, mediana) e a amplitude (min-max) do indicador
    em todas as estacoes, complementando o ranking da area de analise (que mostra
    os extremos COM nomes). Assim o painel da direita acompanha o indicador
    escolhido, em vez de ficar sempre nos valores globais da vista inicial.
    """
    meta = INDICADORES_MAPA.get(prop)
    if meta is None:
        return painel_global(repo)
    base = repo.estacoes_gira if meta["fonte"] == "gira" else repo.estacoes_metro
    serie = base[prop].dropna()
    if serie.empty:
        return painel_global(repo)

    # Apresentacao alinhada com o ranking (ex.: rede ciclavel em km).
    if prop == "comp_ciclavel_m":
        escala, sufixo, casas = 0.001, " km", 2
    elif prop == "taxa_media_disponibilidade":
        escala, sufixo, casas = 100.0, "%", 0
    else:
        escala, casas = 1.0, meta["decimais"]
        unid = meta.get("unidade", "")
        sufixo = (" " + unid) if unid else ""

    media = float(serie.mean())
    mediana = float(serie.median())
    vmin, vmax = float(serie.min()), float(serie.max())
    n = len(serie)
    tipo = "Estações GIRA" if meta["fonte"] == "gira" else "Estações de metro"
    intervalo = (f"{_fmt(vmin * escala, decimais=casas)}–"
                 f"{_fmt(vmax * escala, sufixo=sufixo, decimais=casas)}")

    if prop == "iic":
        # Na vista do IIC, o ranking ao lado ja mostra a distribuicao (extremos
        # com nomes), pelo que o painel ACRESCENTA a decomposicao: o IIC medio
        # da rede e a media de cada uma das tres componentes normalizadas (0-1).
        # Revela onde a rede esta, em media, mais forte ou mais fraca — o gargalo
        # da intermodalidade — em vez de repetir a distribuicao.
        m = repo.estacoes_metro
        intro = html.Div(className="painel-intro", children=[
            html.P(["Visão geral do ", html.Strong("IIC"), " na rede: o valor "
                    "médio e a média de cada componente (0–1). Clique numa "
                    "estação para ver o detalhe dela."]),
        ])
        componentes = [
            ("Proximidade", m["prox_norm"].mean()),
            ("Densidade GIRA", m["n_gira_norm"].mean()),
            ("Rede ciclável", m["comp_ciclavel_norm"].mean()),
        ]
        cartoes = [_cartao_iic(media, "IIC médio (0–1)")]
        cartoes.append(html.Div("Composição média da rede (0–1)",
                                className="painel-subcabecalho"))
        cartoes += [_cartao_componente(rot, val) for rot, val in componentes]
        cartoes.append(_cartao(f"{n}", tipo))
        return html.Div(children=[
            intro, html.Div(className="painel-kpis", children=cartoes)])

    # Restantes indicadores: resumo da DISTRIBUICAO (media, mediana, amplitude),
    # que complementa o ranking dos extremos no lado esquerdo.
    intro = html.Div(className="painel-intro", children=[
        html.P(["Visão geral de ", html.Strong(meta["titulo"]),
                " na rede. Clique numa estação para ver o detalhe dela."]),
    ])
    principal = _cartao(
        _fmt(media * escala, sufixo=sufixo, decimais=casas), "Média na rede")
    kpis = html.Div(className="painel-kpis", children=[
        principal,
        _cartao(_fmt(mediana * escala, sufixo=sufixo, decimais=casas), "Mediana"),
        _cartao(intervalo, "Intervalo (mín–máx)"),
        _cartao(f"{n}", tipo),
    ])
    return html.Div(children=[intro, kpis])


def painel_gira(props):
    """Cartoes com os indicadores do Grupo 1 da GIRA selecionada:
    disponibilidade media, TMD, IVD e hora de pico."""
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
    """Indicadores do Grupo 2 da estacao de metro + camadas do mapa."""
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


def analise_complementar(repo, sel_gira, sel_metro, inicio, fim, raio,
                         w_prox, w_dens, w_cicl, prop):
    """Decide as duas figuras, o titulo e o realce da area de analise, e a
    'vista' (estado lido pelo CSS para mostrar/esconder os blocos).

    Funcao pura extraida do callback 'atualizar_analise', para poder ser testada
    diretamente. Devolve (serie, segundo, titulo, realce, vista).
    """
    id_gira = sel_gira.get("id_estacao") if sel_gira else None

    # O par de figuras (e a 'vista') depende da selecao e do indicador ativo.
    # Sem nada relevante para mostrar, fica em "intro": o CSS esconde os
    # graficos e deixa so a introducao.
    if id_gira is not None:
        # A esquerda adapta-se ao indicador GIRA ativo: para o IVD, o perfil
        # horario; para os restantes, a serie temporal. O heatmap mantem-se.
        if prop == "indice_variabilidade_diaria":
            serie = figures.figura_perfil_horario(repo, id_gira, inicio, fim)
        else:
            serie = figures.figura_serie_temporal(repo, id_gira, inicio, fim)
        segundo = figures.figura_heatmap(repo, id_gira, inicio, fim)
        vista = "graficos"
    elif sel_metro:
        # Cobertura calculada uma so vez (usada pelas figuras da estacao).
        cob = repo.cobertura_metro(sel_metro.get("id_metro"), raio=raio)
        id_m = sel_metro.get("id_metro")
        # A vista de detalhe ADAPTA-SE ao indicador ativo (os dois graficos).
        if prop in ("n_gira_influencia", "dist_gira_min_m"):
            serie = figures.figura_distancia_gira(repo, id_m, raio,
                                                  cobertura=cob)
            segundo = figures.figura_distribuicao_gira(repo, id_m, raio,
                                                       cobertura=cob)
        elif prop == "disp_pico":
            serie = figures.figura_pico_gira(repo, id_m, raio, cobertura=cob)
            segundo = figures.figura_distancia_gira(repo, id_m, raio,
                                                    cobertura=cob)
        elif prop == "comp_ciclavel_m":
            serie = figures.figura_rede_ciclavel_metro(repo, id_m, raio,
                                                       cobertura=cob)
            segundo = figures.figura_contexto_metro(
                repo, id_m, "comp_ciclavel_m",
                eixo="Rede ciclável na área (km)",
                titulo="Rede ciclável: esta estação vs. as outras",
                casas=2, escala=0.001)
        else:
            # Caso geral (IIC): composicao do IIC + serie temporal do conjunto
            # de GIRA na area de influencia.
            ids_gira = (cob["gira"]["id_estacao"].tolist()
                        if cob is not None else [])
            serie = figures.figura_composicao_iic(repo, id_m)
            segundo = figures.figura_serie_conjunto(repo, ids_gira,
                                                    inicio, fim)
        vista = "graficos"
    elif prop == "iic":
        # Ranking de IIC + painel de PESOS ao lado (os pesos recalculam-no).
        serie = figures.figura_ranking_iic(
            repo, pesos=(w_prox, w_dens, w_cicl))
        segundo = figures.figura_vazia()
        vista = "grafico1-pesos"
    elif prop in RANKINGS_SEM_SELECAO:
        # Indicadores cuja vista sem selecao e um unico ranking de extremos
        # (parametros na tabela). A coluna do indicador coincide com 'prop'.
        m = RANKINGS_SEM_SELECAO[prop]
        serie = figures.figura_ranking_estacoes(
            repo, m["fonte"], prop, eixo=m["eixo"],
            hover_sufixo=m["hover_sufixo"], titulo=m["titulo"],
            casas=m["casas"], escala=m.get("escala", 1.0))
        segundo = figures.figura_vazia()
        vista = "grafico1"
    elif prop == "disponibilidade_media":
        # Sem selecao: DOIS rankings lado a lado (bicicletas e taxa media).
        serie = figures.figura_ranking_estacoes(
            repo, "gira", "disponibilidade_media",
            eixo="Disponibilidade média (bicicletas)",
            hover_sufixo=" bicicletas (média)",
            titulo="GIRA por disponibilidade média (maior e menor)",
            casas=1, maior_melhor=True)
        segundo = figures.figura_ranking_estacoes(
            repo, "gira", "taxa_media_disponibilidade",
            eixo="Taxa média de disponibilidade",
            hover_sufixo=" de taxa média",
            titulo="GIRA por taxa de disponibilidade (maior e menor)",
            casas=2, maior_melhor=True)
        vista = "graficos2"
    else:
        # Sem nada relevante: empty state (figuras vazias, escondidas pelo CSS).
        serie = figures.figura_vazia()
        segundo = figures.figura_vazia()
        vista = "intro"

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
    elif prop == "iic":
        titulo = html.Span("Ranking de intermodalidade (IIC)",
                           className="sem-selecao")
    elif prop in RANKINGS_SEM_SELECAO:
        titulo = html.Span(RANKINGS_SEM_SELECAO[prop]["painel"],
                           className="sem-selecao")
    elif prop == "disponibilidade_media":
        titulo = html.Span(
            "Disponibilidade das estações GIRA: bicicletas e taxa",
            className="sem-selecao")
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
    return serie, segundo, titulo, realce, vista


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
        Output("gira", "clickData"),
        Output("metro", "clickData"),
        Input("gira", "clickData"),
        Input("metro", "clickData"),
        Input("mapa", "clickData"),
        Input("sel-gira-nome", "value"),
        Input("sel-metro-nome", "value"),
        Input("filtro-indicador", "value"),
        State("sel-gira", "data"),
        State("sel-metro", "data"),
        prevent_initial_call=True,
    )
    def gerir_selecao(click_gira, click_metro, _click_mapa, nome_gira,
                      nome_metro, prop, sel_gira_atual, sel_metro_atual):
        # Seleccao mutuamente exclusiva, sincronizada entre o mapa e o seletor
        # "Localizar estacao" da esquerda:
        #  - clicar numa estacao seleciona-a E preenche o seletor com o seu nome;
        #  - escolher um nome seleciona-a e centra o mapa nela;
        #  - LIMPAR o seletor (x) desseleciona e volta a vista inicial;
        #  - clicar no fundo do mapa desseleciona tudo.
        # O State (selecao atual) evita lacos quando preenchemos o seletor
        # programaticamente apos um clique no mapa.
        #
        # IMPORTANTE: cada ramo ATIVO limpa o clickData das duas camadas para
        # None. O clickData do dash-leaflet so muda quando se clica numa estacao
        # DIFERENTE; sem esta limpeza, depois de desselecionar, clicar outra vez
        # na MESMA estacao nao mudava o clickData e o callback nao disparava (os
        # graficos nao reabriam). Ao repor None, o clique seguinte e sempre uma
        # transicao None->estacao. Os ramos "sem efeito" devolvem no_update no
        # clickData (repor None quando ja e None nao re-dispara; so os ativos o
        # fazem, e o re-disparo cai num ramo sem efeito e estabiliza).
        SEM = (no_update,) * 7
        acionados = _acionados()
        # Tipo de estacao "ativo" = o que o indicador codifica. O outro tipo fica
        # como contexto (esbatido no mapa) e os seus cliques sao ignorados, para a
        # analise nao saltar para um tipo que nao se esta a analisar.
        fonte_ativa = (INDICADORES_MAPA[prop]["fonte"]
                       if prop in INDICADORES_MAPA else None)

        # Fundo do mapa -> limpa tudo.
        if "mapa" in acionados:
            return None, None, None, None, no_update, None, None

        # Mudou o INDICADOR: se a estacao selecionada e do tipo agora nao-ativo
        # (contexto esbatido), limpa-a — a analise volta ao ranking do novo
        # indicador, em vez de manter o detalhe de um tipo que ja nao se analisa.
        if "filtro-indicador" in acionados:
            if fonte_ativa == "metro" and sel_gira_atual is not None:
                return None, no_update, None, no_update, no_update, \
                    no_update, no_update
            if fonte_ativa == "gira" and sel_metro_atual is not None:
                return no_update, None, no_update, None, no_update, \
                    no_update, no_update
            return SEM

        # Clique numa estacao GIRA -> seleciona e mostra o nome no seletor.
        if "gira" in acionados and click_gira:
            if fonte_ativa == "metro":      # GIRA e contexto: ignora o clique
                return (no_update,) * 5 + (None, no_update)
            props = click_gira.get("properties")
            gid = int(props["id_estacao"]) if props and props.get(
                "id_estacao") is not None else None
            return props, None, gid, None, no_update, None, None

        # Clique numa estacao de metro.
        if "metro" in acionados and click_metro:
            if fonte_ativa == "gira":       # metro e contexto: ignora o clique
                return (no_update,) * 5 + (no_update, None)
            props = click_metro.get("properties")
            mid = int(props["id_metro"]) if props and props.get(
                "id_metro") is not None else None
            return None, props, None, mid, no_update, None, None

        # Seletor de NOME da GIRA.
        if "sel-gira-nome" in acionados:
            if not nome_gira:                       # x do seletor -> desseleciona
                if sel_gira_atual is not None:
                    return None, None, no_update, no_update, no_update, None, None
                return SEM
            props = repo.props_gira(nome_gira)
            if not props:
                return SEM
            # Ja selecionada (seletor preenchido por um clique no mapa): nao
            # repetir nem voltar a centrar.
            if (sel_gira_atual
                    and sel_gira_atual.get("id_estacao") == props.get("id_estacao")):
                return SEM
            centro = [props.get("latitude"), props.get("longitude")]
            return props, None, no_update, None, centro, None, None

        # Seletor de NOME do metro.
        if "sel-metro-nome" in acionados:
            if not nome_metro:
                if sel_metro_atual is not None:
                    return None, None, no_update, no_update, no_update, None, None
                return SEM
            props = repo.props_metro(nome_metro)
            if not props:
                return SEM
            if (sel_metro_atual
                    and sel_metro_atual.get("id_metro") == props.get("id_metro")):
                return SEM
            return (None, props, None, no_update,
                    repo.centro_metro(nome_metro), None, None)

        return SEM

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
                list(config.CAMADAS_MAPA), *config.PESOS_IIC_REF)

    @app.callback(
        Output("filtro-indicador", "value", allow_duplicate=True),
        Output("sel-gira", "data", allow_duplicate=True),
        Output("sel-metro", "data", allow_duplicate=True),
        Output("sel-gira-nome", "value", allow_duplicate=True),
        Output("sel-metro-nome", "value", allow_duplicate=True),
        Input("btn-home", "n_clicks"),
        prevent_initial_call=True,
    )
    def ir_para_inicio(_n):
        # Botao "Início": devolve tudo a vista inicial — limpa o indicador ativo
        # e qualquer estacao selecionada (o painel volta aos valores globais e a
        # area de analise ao empty state).
        return None, None, None, None, None

    @app.callback(
        Output("painel-indicadores", "children"),
        Output("camada-cobertura", "children"),
        Input("sel-gira", "data"),
        Input("sel-metro", "data"),
        Input("filtro-raio", "value"),
        Input("filtro-indicador", "value"),
    )
    def atualizar_indicadores(sel_gira, sel_metro, raio, prop):
        # Painel direito contextual + camadas de cobertura no mapa.
        # Prioridade: estacao selecionada > indicador ativo > vista inicial.
        if sel_metro:
            painel, camadas = painel_metro(repo, sel_metro, raio)
            return painel, camadas
        if sel_gira:
            return painel_gira(sel_gira), []
        if prop:
            # Sem selecao, mas com indicador ativo: resumo desse indicador na
            # rede (acompanha o ranking da area de analise).
            return painel_indicador(repo, prop), []
        return painel_global(repo), []

    @app.callback(
        Output("grafico-serie", "figure"),
        Output("grafico-heatmap", "figure"),
        Output("estacao-titulo", "children"),
        Output("camada-gira-selecao", "children"),
        Output("analise-vista", "data"),
        Input("sel-gira", "data"),
        Input("sel-metro", "data"),
        Input("filtro-periodo", "start_date"),
        Input("filtro-periodo", "end_date"),
        Input("filtro-raio", "value"),
        Input("peso-prox", "value"),
        Input("peso-dens", "value"),
        Input("peso-cicl", "value"),
        Input("filtro-indicador", "value"),
    )
    def atualizar_analise(sel_gira, sel_metro, inicio, fim, raio,
                          w_prox, w_dens, w_cicl, prop):
        return analise_complementar(repo, sel_gira, sel_metro, inicio, fim,
                                    raio, w_prox, w_dens, w_cicl, prop)

    @app.callback(
        Output("analise-modo", "data"),
        Output("sel-gira", "data", allow_duplicate=True),
        Output("sel-metro", "data", allow_duplicate=True),
        Output("sel-gira-nome", "value", allow_duplicate=True),
        Output("sel-metro-nome", "value", allow_duplicate=True),
        Input("btn-comparar", "n_clicks"),
        Input("sel-gira", "data"),
        Input("sel-metro", "data"),
        State("analise-modo", "data"),
        prevent_initial_call=True,
    )
    def gerir_modo(_n, sel_gira, sel_metro, modo):
        # O botao alterna entre analise e comparacao. Selecionar uma estacao
        # traz sempre a area de volta a analise (a comparacao e uma tarefa a
        # parte, com a sua propria porta de entrada).
        acionados = _acionados()
        if "btn-comparar" in acionados:
            if modo == "comparar":
                # Voltar a analise: nao mexe na selecao.
                return "analise", no_update, no_update, no_update, no_update
            # Entrar em comparacao LIMPA a selecao anterior. Sem isto, o anel, a
            # etiqueta e o popup da estacao selecionada ficavam no mapa e tapavam
            # as estacoes que se localizam na comparacao. Ao zerar a selecao, o
            # sync popup<->selecao fecha o popup e o painel volta ao global — a
            # comparacao passa a ser uma tarefa limpa, sem analise por baixo.
            return "comparar", None, None, None, None
        # Selecionar uma estacao so volta ao modo analise se estivermos em
        # comparacao. Caso contrario NAO toca em 'analise-modo': se o fizesse
        # (mesmo para o valor igual), o codificar_mapa correria, re-renderizava
        # os marcadores e fechava o popup acabado de abrir — e o popupclose
        # desselecionava a estacao logo a seguir ao clique.
        if (sel_gira or sel_metro) and modo == "comparar":
            return "analise", no_update, no_update, no_update, no_update
        return no_update, no_update, no_update, no_update, no_update

    @app.callback(
        Output("area-analise", "className"),
        Output("analise-seccao-titulo", "children"),
        Output("btn-comparar", "children"),
        Output("btn-comparar", "className"),
        Input("analise-modo", "data"),
        Input("analise-vista", "data"),
    )
    def render_modo(modo, vista):
        # Compoe a className do rodape (o CSS decide o bloco visivel e a
        # visibilidade do titulo a partir de modo-* / vista-*), ajusta o titulo
        # da seccao ao estado (deixa de dizer "Análise complementar" sobre a
        # introducao) e o rotulo/estado do botao de comparacao.
        modo = modo or "analise"
        vista = vista or "intro"
        classe = f"area-analise modo-{modo} vista-{vista}"
        if modo == "comparar":
            return (classe, "Comparação de estações de metro",
                    "← Voltar à análise", "btn-comparar ativo")
        titulo = "Para começar" if vista == "intro" else "Análise complementar"
        return classe, titulo, "Comparar estações de metro", "btn-comparar"

    @app.callback(
        Output("gira", "hideout"),
        Output("metro", "hideout"),
        Output("legenda", "children"),
        Input("filtro-indicador", "value"),
        Input("analise-modo", "data"),
    )
    def codificar_mapa(prop, modo):
        # Na comparacao, o foco sao as estacoes de metro: recuam-se as GIRA
        # (contexto, mais pequenas e atras) e destacam-se ligeiramente os metros,
        # independentemente do indicador ativo.
        if modo == "comparar":
            return (hideout_categorico_gira(contexto=True),
                    hideout_categorico_metro(destaque=True),
                    _legenda_categorica())
        # Sem indicador (None): mapa em modo "tipo de estacao" (ambos categoricos).
        if not prop:
            return (hideout_categorico_gira(), hideout_categorico_metro(),
                    _legenda_categorica())
        meta = INDICADORES_MAPA[prop]
        hideout = hideout_indicador(repo, prop)
        legenda = construir_legenda(prop, hideout, meta)
        # O indicador colore a sua fonte; a outra camada fica esbatida (contexto)
        # para recuar e nao se confundir com o tipo em analise.
        if meta["fonte"] == "gira":
            return hideout, hideout_categorico_metro(contexto=True), legenda
        return hideout_categorico_gira(contexto=True), hideout, legenda

    @app.callback(
        Output("grafico-comparacao", "figure"),
        Output("camada-comparacao", "children"),
        Input("filtro-comp-a", "value"),
        Input("filtro-comp-b", "value"),
        Input("comp-no-mapa", "value"),
        Input("analise-modo", "data"),
    )
    def atualizar_comparacao(id_a, id_b, no_mapa, modo):
        ids = list(dict.fromkeys(i for i in (id_a, id_b) if i is not None))
        figura = figures.figura_comparacao(repo, ids)
        # Os aneis so existem em modo de comparacao e com "Localizar no mapa"
        # ativo. Ao sair da comparacao (modo != 'comparar'), este callback volta
        # a correr — porque 'analise-modo' e input — e limpa-os do mapa.
        if modo != "comparar" or "on" not in (no_mapa or []):
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
        ocultas = [f"cam-oculta-{c}" for c in config.CAMADAS_MAPA
                   if c not in ativas]
        return " ".join(["mapa-camadas", *ocultas])

    @app.callback(
        Output("filtro-camadas", "value", allow_duplicate=True),
        Input("camadas-todas", "n_clicks"),
        Input("camadas-nenhuma", "n_clicks"),
        prevent_initial_call=True,
    )
    def atalho_camadas(_todas, _nenhuma):
        # Liga ou desliga todas as camadas de uma vez, poupando quatro cliques
        # individuais no checklist.
        acionados = _acionados()
        if "camadas-todas" in acionados:
            return list(config.CAMADAS_MAPA)
        return []

    @app.callback(
        Output("sobre-modal", "className"),
        Input("abrir-sobre", "n_clicks"),
        Input("fechar-sobre", "n_clicks"),
        prevent_initial_call=True,
    )
    def alternar_sobre(_abrir, _fechar):
        # Abre o painel se o disparo veio do botao do cabecalho; fecha caso
        # contrario (botao de fechar). A visibilidade efetiva e dada pelo CSS.
        acionados = _acionados()
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

    # Os sliders dos pesos (rc-slider) podem ser montados com 0 px de largura
    # enquanto a vista do IIC esta escondida; quando essa vista aparece, eventos
    # de resize forcam o recalculo da largura. Disparam-se varios (incluindo um
    # tardio) porque no PRIMEIRO arranque a montagem do grafico/sliders demora
    # mais — sem isto, a largura so acertava ao alternar de indicador.
    app.clientside_callback(
        """
        function(cls) {
            if (cls && cls.indexOf('vista-grafico1-pesos') >= 0) {
                [60, 250, 600].forEach(function(t){
                    setTimeout(function(){
                        window.dispatchEvent(new Event('resize'));
                    }, t);
                });
            }
            return window.dash_clientside.no_update;
        }
        """,
        Output("_pesos-sink", "data"),
        Input("area-analise", "className"),
    )

    # Valor de cada peso mostrado ao lado do rotulo (em vez de um balao sobre o
    # slider): altura do painel fixa e previsivel.
    app.clientside_callback(
        """
        function(p, d, c) {
            function f(x){ return (x==null?0:x).toFixed(2).replace('.', ','); }
            return [f(p), f(d), f(c)];
        }
        """,
        Output("val-prox", "children"),
        Output("val-dens", "children"),
        Output("val-cicl", "children"),
        Input("peso-prox", "value"),
        Input("peso-dens", "value"),
        Input("peso-cicl", "value"),
    )

    @app.callback(
        Output("dica-geral", "data-alvo"),
        Input("filtro-indicador", "value"),
    )
    def alvo_dica(prop):
        # A dica geral serve indicadores de metro (n.o GIRA, pico, rede) E de
        # GIRA (IVD, disponibilidade). O realce do «Localizar estação» deve
        # apontar so para o seletor do tipo do indicador ativo — nao para ambos.
        fonte = INDICADORES_MAPA.get(prop, {}).get("fonte") if prop else None
        alvo = ".dropdown-localizar-gira" if fonte == "gira" \
            else ".dropdown-localizar-metro"
        return ".area-mapa, " + alvo

    # Realce guiado: ao passar o rato num cartao da introducao, destaca-se (com
    # sombra) o controlo real onde essa acao se faz (mapa / seletor de indicador
    # / botao de comparar). Os alvos vem no atributo data-alvo de cada cartao.
    # Ouvintes ligados uma unica vez.
    app.clientside_callback(
        """
        function(_v) {
            if (!window._acoesInit) {
                window._acoesInit = true;
                var cartoes = document.querySelectorAll(
                    '.analise-intro-acoes .acao[data-alvo], '
                    + '.analise-dica[data-alvo]');
                cartoes.forEach(function(c) {
                    c.addEventListener('mouseenter', function() {
                        var sel = c.getAttribute('data-alvo');  // ao vivo
                        if (!sel) return;
                        document.querySelectorAll(sel).forEach(function(a) {
                            a.classList.add('destacar-alvo');
                        });
                    });
                    c.addEventListener('mouseleave', function() {
                        document.querySelectorAll('.destacar-alvo').forEach(
                            function(a) { a.classList.remove('destacar-alvo'); });
                    });
                });
            }
            return window.dash_clientside.no_update;
        }
        """,
        Output("_acoes-sink", "data"),
        Input("analise-modo", "data"),
    )