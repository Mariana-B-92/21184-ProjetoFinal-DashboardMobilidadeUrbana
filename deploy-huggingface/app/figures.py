"""
Geradores de figuras Plotly para a area de analise complementar.

Mantem coerencia visual com o tema do dashboard (tipografia Hanken Grotesk,
acento verde). Cada funcao recebe o repositorio de dados e devolve uma figura
pronta a ligar a um dcc.Graph.
"""

import plotly.graph_objects as go

import config

_FONTE = "Hanken Grotesk, sans-serif"
_TINTA = "#1b211e"
_ACENTO = "#0a9a4a"
_GRELHA = "#e2e6e1"

# Escala SEQUENCIAL amarelo->verde (YlGn, ColorBrewer) para o heatmap. A
# disponibilidade e uma magnitude (0..N bicicletas), nao um desvio, por isso
# pede uma escala sequencial e nao o gradiente vermelho<->verde (confuso e mau
# para daltonicos). Amarelo-claro = pouca, verde-escuro = muita. So aqui; o mapa
# e as legendas usam a paleta de 5 classes.
_ESCALA_HEATMAP = [
    [0.00, "#ffffcc"],
    [0.25, "#c2e699"],
    [0.50, "#78c679"],
    [0.75, "#31a354"],
    [1.00, "#006837"],
]

# Paleta categorica para distinguir estacoes na comparacao.
_PALETA_COMP = config.PALETA_COMPARACAO

# Componentes do IIC a confrontar (todas normalizadas em [0,1]).
_COMPONENTES = [
    ("prox_norm", "Proximidade"),
    ("n_gira_norm", "Densidade GIRA"),
    ("comp_ciclavel_norm", "Rede ciclável"),
    ("iic", "IIC (global)"),
]


def _aplicar_tema(fig, titulo):
    fig.update_layout(
        title=dict(text=titulo, font=dict(size=14, color=_TINTA, family=_FONTE)),
        font=dict(family=_FONTE, color=_TINTA, size=12),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=48, r=16, t=40, b=36),
    )
    fig.update_xaxes(gridcolor=_GRELHA, zeroline=False)
    fig.update_yaxes(gridcolor=_GRELHA, zeroline=False)
    return fig


def _abreviar(nome, limite=26):
    """Trunca um nome comprido (rotulo do eixo) com reticencias, deixando o nome
    completo para o hover. O 'limite' varia conforme o espaco da figura."""
    return nome if len(nome) <= limite else nome[:limite - 1] + "…"


def _scatter_serie(x, y, titulo):
    """Serie diaria simples (linha verde preenchida ate zero) — base partilhada
    pelas series de disponibilidade media global e de conjunto de estacoes."""
    fig = go.Figure(go.Scatter(
        x=x, y=y, mode="lines",
        line=dict(color=_ACENTO, width=1.6),
        fill="tozeroy", fillcolor="rgba(10,154,74,.10)",
        hovertemplate="%{x|%d/%m/%Y}<br>%{y:.1f} bicicletas<extra></extra>",
    ))
    fig.update_yaxes(title_text="Bicicletas (média diária)")
    return _aplicar_tema(fig, titulo)


def figura_vazia(mensagem="Selecione uma estação GIRA no mapa"):
    fig = go.Figure()
    fig.add_annotation(text=mensagem, showarrow=False,
                       font=dict(family=_FONTE, color="#9aa39d", size=13))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        margin=dict(l=10, r=10, t=10, b=10))
    return fig


def figura_serie_temporal(repo, id_estacao, inicio=None, fim=None):
    """Serie temporal da disponibilidade media diaria de uma estacao GIRA.

    Trata estacoes com historico muito escasso (1-2 dias com registos): em vez
    de uma linha que faz o eixo do tempo colapsar, mostra o(s) ponto(s) como
    marcador, mantem o eixo no periodo selecionado, comeca o eixo vertical em
    zero e assinala "historico limitado".
    """
    if id_estacao is None:
        return figura_vazia()
    st = repo.serie_temporal(id_estacao, inicio=inicio, fim=fim, frequencia="D")
    if st.empty:
        return figura_vazia("Sem dados para o período selecionado")

    poucos = len(st) <= 2
    fig = go.Figure(go.Scatter(
        x=st["timestamp"], y=st["numbicicletas"],
        mode="markers" if poucos else "lines",
        line=dict(color=_ACENTO, width=1.6),
        marker=dict(size=7, color=_ACENTO),
        fill=None if poucos else "tozeroy", fillcolor="rgba(10,154,74,.10)",
        hovertemplate="%{x|%d/%m/%Y}<br>%{y:.1f} bicicletas<extra></extra>",
    ))
    # Comeca em zero (bicicletas nao sao negativas) e, havendo periodo, mantem o
    # eixo do tempo no periodo (evita colapsar em microssegundos com 1 ponto).
    fig.update_yaxes(title_text="Bicicletas (média diária)", rangemode="tozero")
    if inicio and fim:
        fig.update_xaxes(range=[inicio, fim])
    if poucos:
        fig.add_annotation(
            text="Histórico limitado nesta estação", xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(family=_FONTE, size=11, color="#9aa39d"))
    return _aplicar_tema(fig, "Disponibilidade ao longo do tempo")


def figura_heatmap(repo, id_estacao, inicio=None, fim=None):
    """Heatmap da disponibilidade media por dia da semana x hora do dia."""
    if id_estacao is None:
        return figura_vazia()
    matriz = repo.heatmap_disponibilidade(id_estacao, inicio=inicio, fim=fim)
    if matriz.empty:
        return figura_vazia("Sem dados suficientes")

    fig = go.Figure(go.Heatmap(
        z=matriz.values, x=list(matriz.columns), y=list(matriz.index),
        colorscale=_ESCALA_HEATMAP,
        # Barra de cor estreita, encurtada e encostada a direita, com a legenda
        # na vertical, para nao ficar cortada em ecras estreitos.
        colorbar=dict(title=dict(text="Bicicletas (média)", side="right"),
                      thickness=10, len=0.82, x=1.0, xpad=2),
        hovertemplate="%{y}, %{x}h<br>%{z:.1f} bicicletas (média)<extra></extra>",
    ))
    fig.update_xaxes(title_text="Hora do dia", dtick=3)
    # Forca uma etiqueta por dia: com pouca altura, o Plotly desbastava os
    # rotulos (mostrava de dois em dois) e pareciam faltar dias.
    fig.update_yaxes(autorange="reversed", tickmode="array",
                     tickvals=list(matriz.index), ticktext=list(matriz.index),
                     tickfont=dict(size=11))
    # Poucas celulas com dados -> assinala historico escasso (coerente com a serie).
    if int(matriz.notna().sum().sum()) < 5:
        fig.add_annotation(
            text="Histórico limitado nesta estação", xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(family=_FONTE, size=11, color="#9aa39d"))
    # A nota de leitura vai como 2.a LINHA do proprio titulo (via <br>), e NAO
    # como title.subtitle nativo: este, com automargin, reposicionava-se mal em
    # re-renders repetidos (ao selecionar varias GIRA seguidas, sobrepunha-se ao
    # titulo). Um titulo de duas linhas e um so bloco de texto, logo nunca se
    # sobrepoe; com margem de topo fixa, a posicao fica deterministica.
    fig = _aplicar_tema(
        fig,
        "Disponibilidade média de bicicletas (hora × dia da semana)"
        "<br><span style='font-size:10.5px;color:#9aa39d'>"
        "Cada célula = média do período · passe o cursor para o valor</span>")
    # Folga a direita para a barra de cor; topo fixo, com espaco para as 2 linhas.
    fig.update_layout(margin=dict(l=48, r=64, t=64, b=36))
    return fig


def figura_serie_global(repo, inicio=None, fim=None):
    """Serie diaria da disponibilidade media em todas as estacoes GIRA."""
    st = repo.serie_global(inicio=inicio, fim=fim)
    if st is None or st.empty:
        return figura_vazia("Sem dados para o período selecionado")
    return _scatter_serie(st["data"], st["media"],
                          "Disponibilidade média — todas as estações GIRA")


def figura_serie_conjunto(repo, ids, inicio=None, fim=None):
    """Serie diaria da disponibilidade media de um CONJUNTO de estacoes GIRA
    (ex.: as contidas na area de influencia de um metro)."""
    if not ids:
        return figura_vazia("Sem estações GIRA na área de influência")
    st = repo.serie_conjunto(ids, inicio=inicio, fim=fim)
    if st is None or st.empty:
        return figura_vazia("Sem dados para o período selecionado")
    return _scatter_serie(
        st["data"], st["media"],
        f"Disponibilidade média — {len(ids)} GIRA na área de influência")


def figura_ranking_iic(repo, n=5, pesos=None):
    """Ranking das estacoes de metro pelo IIC: as 'n' de maior e as 'n' de menor.

    'pesos' = (w_prox, w_dens, w_cicl): o IIC e RECALCULADO a partir das tres
    componentes normalizadas com estes pesos (normalizados para somarem 1). Por
    omissao usa os pesos de referencia (config.PESOS_IIC_REF).
    """
    w = tuple(pesos) if pesos else config.PESOS_IIC_REF
    soma = sum(w)
    if soma <= 0:                       # salvaguarda: pesos todos a zero
        w = (1 / 3, 1 / 3, 1 / 3)
        soma = 1.0
    w = (w[0] / soma, w[1] / soma, w[2] / soma)
    personalizado = tuple(round(x, 2) for x in w) != config.PESOS_IIC_REF

    metro = repo.estacoes_metro.copy()
    metro["iic_calc"] = (w[0] * metro["prox_norm"]
                         + w[1] * metro["n_gira_norm"]
                         + w[2] * metro["comp_ciclavel_norm"])
    metro = metro.dropna(subset=["iic_calc"]).sort_values("iic_calc",
                                                          ascending=True)
    if metro.empty:
        return figura_vazia("Sem dados de IIC")
    metro = metro.reset_index(drop=True)

    total = len(metro)
    dividir = total > 2 * n
    if dividir:
        posicoes = list(range(n)) + list(range(total - n, total))
        sel = metro.iloc[posicoes]
    else:
        sel = metro

    nomes = sel["nome_metro"].astype(str).tolist()
    valores = list(sel["iic_calc"])
    # Cor pela paleta (verde=melhor, vermelho=pior). O IIC=0 fica com barra de
    # comprimento zero: o rotulo "0,00" ao lado ja o identifica, pelo que nao se
    # forca nenhum traco/cor especial.
    cores = [config.cor_classe(v) for v in valores]
    larguras = list(valores)
    curtos = [_abreviar(x, 24) for x in nomes]

    fig = go.Figure(go.Bar(
        x=larguras, y=nomes, orientation="h", marker_color=cores,
        text=[f"{v:.2f}" for v in valores], textposition="outside",
        textfont=dict(family=_FONTE, size=11),
        customdata=valores,             # valor real (hover), mesmo no traco de 0
        hovertemplate="%{y}<br>IIC: %{customdata:.2f}<extra></extra>",
    ))
    # Folga a direita (ate 1.12) para os rotulos exteriores nao cortarem.
    fig.update_xaxes(title_text="IIC", range=[0, 1.12])
    fig.update_yaxes(type="category", tickmode="array",
                     tickvals=nomes, ticktext=curtos,
                     automargin=True, tickfont=dict(size=11))
    if dividir:
        fig.add_hline(y=n - 0.5,
                      line=dict(color="#9aa5a0", width=1, dash="dot"))
    titulo = "Estações de metro por IIC"
    titulo += " · pesos ajustados" if personalizado else " (maior e menor)"
    fig = _aplicar_tema(fig, titulo)
    fig.update_layout(margin=dict(l=8, r=16, t=40, b=44))
    return fig


def figura_perfil_horario(repo, id_estacao, inicio=None, fim=None):
    """Perfil horario de disponibilidade (media por hora, 0-23).

    A linha tracejada e a media do dia; a dispersao da curva em torno dela e o
    que o IVD quantifica.
    """
    if id_estacao is None:
        return figura_vazia("Selecione uma estação GIRA")
    df = repo.perfil_horario(id_estacao, inicio, fim)
    if df is None or df.empty:
        return figura_vazia("Sem dados horários para esta estação")
    df = df.sort_values("hora")
    horas = df["hora"].tolist()
    medias = df["media"].tolist()
    media_dia = sum(medias) / len(medias) if medias else 0.0

    fig = go.Figure(go.Scatter(
        x=horas, y=medias, mode="lines", line=dict(color="#277452", width=2),
        fill="tozeroy", fillcolor="rgba(39,116,82,0.12)",
        hovertemplate="%{x}h<br>%{y:.1f} bicicletas<extra></extra>",
    ))
    # Media do dia: o IVD mede a dispersao das medias horarias em torno dela.
    fig.add_hline(y=media_dia, line=dict(color="#9aa5a0", width=1, dash="dot"))
    fig.add_annotation(x=1.0, y=media_dia, xref="paper", yref="y",
                       xanchor="right", yanchor="bottom",
                       text=f"média {media_dia:.1f}", showarrow=False,
                       font=dict(family=_FONTE, size=10, color="#9aa39d"))
    fig.update_xaxes(title_text="Hora do dia", dtick=3, range=[-0.5, 23.5])
    fig.update_yaxes(title_text="Bicicletas (média)", rangemode="tozero")
    fig = _aplicar_tema(
        fig,
        "Perfil horário de disponibilidade"
        "<br><span style='font-size:10.5px;color:#9aa39d'>"
        "O IVD mede a oscilação destas médias ao longo do dia</span>")
    fig.update_layout(margin=dict(l=8, r=16, t=58, b=44))
    return fig


def figura_ranking_estacoes(repo, fonte, coluna, eixo, hover_sufixo, titulo,
                            n=5, casas=0, escala=1.0, maior_melhor=True):
    """Ranking de estacoes (metro ou GIRA) por um indicador: as 'n' do topo e as
    'n' do fundo, com separador.

    'fonte' ('metro'/'gira') escolhe a tabela e a coluna de nome. A cor segue a
    paleta do mapa, normalizada ao intervalo de TODAS as estacoes (verde =
    melhor); 'maior_melhor=False' inverte-a (ex.: distancia, em que menos e
    melhor). 'escala' converte unidades na apresentacao (ex.: metros->km).
    """
    if fonte == "gira":
        base, col_nome = repo.estacoes_gira, "nome_estacao"
    else:
        base, col_nome = repo.estacoes_metro, "nome_metro"
    metro = base.copy().dropna(subset=[coluna])
    if metro.empty:
        return figura_vazia("Sem dados para este indicador")
    metro = metro.sort_values(coluna, ascending=True).reset_index(drop=True)

    total = len(metro)
    dividir = total > 2 * n
    sel = (metro.iloc[list(range(n)) + list(range(total - n, total))]
           if dividir else metro)

    nomes = sel[col_nome].astype(str).tolist()
    valores = [float(v) * escala for v in sel[coluna]]
    # Cor: normalizacao ao intervalo observado em TODAS as estacoes (nao so nos
    # extremos mostrados), para a paleta refletir a posicao real.
    vmin, vmax = float(metro[coluna].min()), float(metro[coluna].max())
    amp = (vmax - vmin) or 1.0
    norm = [(float(v) - vmin) / amp for v in sel[coluna]]
    if not maior_melhor:
        norm = [1.0 - t for t in norm]
    cores = [config.cor_classe(t) for t in norm]
    curtos = [_abreviar(x, 24) for x in nomes]
    rotulos = [f"{v:.{casas}f}" for v in valores]
    xmax = max(valores) if valores else 1.0

    fig = go.Figure(go.Bar(
        x=valores, y=nomes, orientation="h", marker_color=cores,
        text=rotulos, textposition="outside",
        textfont=dict(family=_FONTE, size=11),
        customdata=rotulos,
        hovertemplate="%{y}<br>%{customdata}" + hover_sufixo + "<extra></extra>",
    ))
    # Folga a direita para os rotulos exteriores nao cortarem.
    fig.update_xaxes(title_text=eixo, range=[0, xmax * 1.18])
    fig.update_yaxes(type="category", tickmode="array",
                     tickvals=nomes, ticktext=curtos,
                     automargin=True, tickfont=dict(size=11))
    if dividir:
        fig.add_hline(y=n - 0.5,
                      line=dict(color="#9aa5a0", width=1, dash="dot"))
    fig = _aplicar_tema(fig, titulo)
    fig.update_layout(margin=dict(l=8, r=16, t=40, b=44))
    return fig


def figura_distancia_gira(repo, id_metro, raio=None, cobertura=None):
    """Distancia de cada GIRA da area ao metro (barras horizontais, da mais perto
    no topo). O comprimento e a distancia; a cor e a proximidade (verde = perto).
    """
    if id_metro is None:
        return figura_vazia("Selecione uma estação de metro")
    if cobertura is None:
        cobertura = repo.cobertura_metro(id_metro, raio=raio)
    if cobertura is None or len(cobertura["gira"]) == 0:
        return figura_vazia("Sem estações GIRA na área de influência")

    gira = cobertura["gira"].copy()
    gira = gira.dropna(subset=["dist_m"]).sort_values("dist_m", ascending=True)
    if gira.empty:
        return figura_vazia("Sem estações GIRA com distância na área")

    raio_area = cobertura.get("raio") or raio or config.RAIO_INFLUENCIA_M
    # Cor por proximidade (perto = verde): menor distancia e melhor, por isso
    # inverte-se em relacao ao raio.
    cores = [config.cor_classe(max(0.0, 1.0 - d / raio_area))
             for d in gira["dist_m"]]
    nomes = gira["nome_estacao"].astype(str).tolist()
    curtos = [_abreviar(n, 26) for n in nomes]

    fig = go.Figure(go.Bar(
        x=gira["dist_m"], y=nomes, orientation="h", marker_color=cores,
        text=[f"{d:.0f} m" for d in gira["dist_m"]], textposition="outside",
        textfont=dict(family=_FONTE, size=11),
        hovertemplate="%{y}<br>%{x:.0f} m do metro<extra></extra>",
    ))
    fig.update_xaxes(title_text="Distância ao metro (m)",
                     range=[0, raio_area * 1.12])
    # autorange invertido: a mais perto fica em CIMA.
    fig.update_yaxes(type="category", tickmode="array",
                     tickvals=nomes, ticktext=curtos, autorange="reversed",
                     automargin=True, tickfont=dict(size=11))
    fig = _aplicar_tema(fig, "Distância de cada GIRA ao metro")
    fig.update_layout(margin=dict(l=8, r=16, t=40, b=44))
    return fig


def figura_pico_gira(repo, id_metro, raio=None, cobertura=None):
    """Disponibilidade na hora de pico de cada GIRA da area (barras).

    Hora de pico = hora de MENOR oferta de cada estacao (leitura de pior caso),
    em bicicletas.
    """
    if id_metro is None:
        return figura_vazia("Selecione uma estação de metro")
    if cobertura is None:
        cobertura = repo.cobertura_metro(id_metro, raio=raio)
    if cobertura is None or len(cobertura["gira"]) == 0:
        return figura_vazia("Sem estações GIRA na área de influência")

    gira = cobertura["gira"].copy()
    if "disponibilidade_hora_pico" not in gira:
        return figura_vazia("Sem dados de hora de pico na área")
    gira = gira.dropna(subset=["disponibilidade_hora_pico"]).sort_values(
        "disponibilidade_hora_pico", ascending=True)
    if gira.empty:
        return figura_vazia("Sem dados de hora de pico na área")

    valores = [float(v) for v in gira["disponibilidade_hora_pico"]]
    vmax = max(valores) or 1.0
    cores = [config.cor_classe(v / vmax) for v in valores]  # verde = mais bicis
    nomes = gira["nome_estacao"].astype(str).tolist()
    curtos = [_abreviar(n, 26) for n in nomes]

    fig = go.Figure(go.Bar(
        x=valores, y=nomes, orientation="h", marker_color=cores,
        text=[f"{v:.1f}" for v in valores], textposition="outside",
        textfont=dict(family=_FONTE, size=11),
        customdata=gira["dist_m"],
        hovertemplate=("%{y}<br>%{x:.1f} bicicletas na hora de pico"
                       " · %{customdata:.0f} m do metro<extra></extra>"),
    ))
    fig.update_xaxes(title_text="Bicicletas na hora de pico",
                     range=[0, vmax * 1.18])
    fig.update_yaxes(type="category", tickmode="array",
                     tickvals=nomes, ticktext=curtos,
                     automargin=True, tickfont=dict(size=11))
    fig = _aplicar_tema(
        fig,
        "Disponibilidade na hora de pico, por GIRA"
        "<br><span style='font-size:10.5px;color:#9aa39d'>"
        "Hora de pico = hora de menor oferta de cada estação</span>")
    fig.update_layout(margin=dict(l=8, r=16, t=58, b=44))
    return fig


def figura_contexto_metro(repo, id_metro, coluna, eixo, titulo,
                          casas=2, escala=1.0):
    """Posiciona o valor de UMA estacao de metro face a todas: tres barras com o
    valor desta estacao, a mediana e o maximo do conjunto. 'escala' converte
    unidades (ex.: m->km)."""
    ind = repo.indicadores_metro(id_metro)
    if ind is None:
        return figura_vazia("Sem indicadores para esta estação")
    col = repo.estacoes_metro[coluna].dropna()
    if col.empty:
        return figura_vazia("Sem dados para este indicador")

    valor = float(ind[coluna]) * escala
    vmed = float(col.median()) * escala
    vmax = float(col.max()) * escala
    nome = str(ind.get("nome_metro", "Esta estação"))

    # Esta estacao (destacada, cor pela sua posicao) vs referencias a cinzento.
    # Ordem y: primeiro fica em baixo, por isso a estacao (ultima) fica em cima.
    rotulos = ["Máximo das estações", "Mediana das estações", nome]
    valores = [vmax, vmed, valor]
    cor_est = config.cor_classe(valor / vmax if vmax else 0.0)
    cores = ["#cdd5cf", "#cdd5cf", cor_est]

    fig = go.Figure(go.Bar(
        x=valores, y=rotulos, orientation="h", marker_color=cores,
        text=[f"{v:.{casas}f}" for v in valores], textposition="outside",
        textfont=dict(family=_FONTE, size=11),
        hovertemplate="%{y}<br>%{x:.2f}<extra></extra>",
    ))
    fig.update_xaxes(title_text=eixo, range=[0, vmax * 1.15])
    fig.update_yaxes(type="category", automargin=True, tickfont=dict(size=11))
    fig = _aplicar_tema(fig, titulo)
    fig.update_layout(margin=dict(l=8, r=16, t=40, b=44))
    return fig


_SEG_ORDEM = [
    ("Pista ciclável (separação física)", "Separação física", "#277452"),
    ("Faixa ciclável (separação visual)", "Separação visual", "#afce65"),
    ("Via banalizada (coexistência)", "Coexistência (s/ separação)", "#ec952e"),
]


def figura_rede_ciclavel_metro(repo, id_metro, raio=None, cobertura=None):
    """Rede ciclavel na area, decomposta por nivel de segregacao: separacao
    fisica (mais segura), separacao visual ou via banalizada (partilha com o
    transito)."""
    if id_metro is None:
        return figura_vazia("Selecione uma estação de metro")
    if cobertura is None:
        cobertura = repo.cobertura_metro(id_metro, raio=raio)
    por_seg = (cobertura or {}).get("ciclavel_por_seg") or {}
    valores_km = [por_seg.get(cat, 0.0) / 1000.0 for cat, _, _ in _SEG_ORDEM]
    if sum(valores_km) <= 0:
        return figura_vazia("Sem rede ciclável na área de influência")

    rotulos = [r for _, r, _ in _SEG_ORDEM]
    cores = [c for _, _, c in _SEG_ORDEM]
    fig = go.Figure(go.Bar(
        x=valores_km, y=rotulos, orientation="h", marker_color=cores,
        text=[f"{v:.2f} km" for v in valores_km], textposition="outside",
        textfont=dict(family=_FONTE, size=11),
        hovertemplate="%{y}<br>%{x:.2f} km<extra></extra>",
    ))
    xmax = max(valores_km) or 1.0
    fig.update_xaxes(title_text="Comprimento (km)", range=[0, xmax * 1.18])
    # autorange invertido: a mais segura (separacao fisica) fica em cima.
    fig.update_yaxes(type="category", autorange="reversed",
                     automargin=True, tickfont=dict(size=11))
    fig = _aplicar_tema(fig, "Rede ciclável na área, por nível de segregação")
    fig.update_layout(margin=dict(l=8, r=16, t=40, b=44))
    return fig


def figura_distribuicao_gira(repo, id_metro, raio=None, cobertura=None):
    """Disponibilidade das estacoes GIRA na area (taxa media, %), em barras
    ordenadas e coloridas pela paleta do mapa; o hover mostra tambem a distancia
    ao metro.

    'cobertura' pode ser passada ja calculada (pelo callback) para nao repetir a
    operacao espacial.
    """
    if id_metro is None:
        return figura_vazia("Selecione uma estação de metro")
    if cobertura is None:
        cobertura = repo.cobertura_metro(id_metro, raio=raio)
    if cobertura is None or len(cobertura["gira"]) == 0:
        return figura_vazia("Sem estações GIRA na área de influência")

    gira = cobertura["gira"].copy()
    gira["tmd_pct"] = gira["taxa_media_disponibilidade"] * 100
    gira = gira.dropna(subset=["tmd_pct"]).sort_values("tmd_pct",
                                                       ascending=True)
    if gira.empty:
        return figura_vazia("Sem dados de disponibilidade na área")

    cores = [config.cor_classe(p / 100.0) for p in gira["tmd_pct"]]
    nomes = gira["nome_estacao"].astype(str).tolist()
    # Barras horizontais: lidam com nomes compridos sem rotacao. Rotulos
    # abreviados (nome completo no hover); 'automargin' ajusta a margem esquerda.
    curtos = [_abreviar(n, 26) for n in nomes]

    fig = go.Figure(go.Bar(
        x=gira["tmd_pct"], y=nomes, orientation="h", marker_color=cores,
        customdata=gira["dist_m"],   # distancia ao metro, mostrada no hover
        hovertemplate=("%{y}<br>%{x:.0f}% disponível"
                       " · %{customdata:.0f} m do metro<extra></extra>"),
    ))
    fig.update_xaxes(title_text="Disponibilidade média (%)", range=[0, 100])
    fig.update_yaxes(type="category", tickmode="array",
                     tickvals=nomes, ticktext=curtos,
                     automargin=True, tickfont=dict(size=11))
    fig = _aplicar_tema(
        fig,
        "Disponibilidade das estações GIRA na área"
        "<br><span style='font-size:10.5px;color:#9aa39d'>"
        "Passe o cursor para o valor exato e a distância ao metro</span>")
    # Margem esquerda a cargo do automargin; topo fixo, com espaco para as 2
    # linhas do titulo (sem automargin no titulo, para nao repetir o problema de
    # sobreposicao do heatmap).
    fig.update_layout(margin=dict(l=8, r=16, t=58, b=44))
    return fig


def figura_composicao_iic(repo, id_metro):
    """Composicao do IIC de uma estacao de metro: as tres componentes.

    Tres barras (Proximidade 40%, Densidade GIRA 35%, Rede ciclavel 25%) com o
    comprimento a dar a pontuacao normalizada (0-1) de cada componente. O peso
    esta no nome, nao no comprimento, para nao confundir peso com forca. Usa o
    IIC oficial (R=500 m).
    """
    if id_metro is None:
        return figura_vazia("Selecione uma estação de metro")
    ind = repo.indicadores_metro(id_metro)
    if ind is None:
        return figura_vazia("Sem indicadores para esta estação")

    def _f(v):
        v = float(v)
        return v if v == v else 0.0   # NaN -> 0

    # Ordem fixa por peso decrescente; a 1.a (Proximidade) fica em cima.
    nomes = ["Proximidade (40%)", "Densidade GIRA (35%)", "Rede ciclável (25%)"]
    scores = [_f(ind["prox_norm"]), _f(ind["n_gira_norm"]),
              _f(ind["comp_ciclavel_norm"])]
    detalhes = [
        f"{_f(ind['dist_gira_min_m']):.0f} m até à GIRA mais próxima",
        f"{int(_f(ind['n_gira_influencia']))} estações GIRA na área",
        f"{_f(ind['comp_ciclavel_m']) / 1000:.2f} km de rede ciclável",
    ]
    # Cor por pontuacao (verde = componente forte), coerente com o mapa.
    cores = [config.cor_classe(s) for s in scores]

    fig = go.Figure(go.Bar(
        x=scores, y=nomes, orientation="h", marker_color=cores,
        text=[f"{s:.2f}" for s in scores], textposition="outside",
        textfont=dict(family=_FONTE, size=12),
        customdata=detalhes,
        hovertemplate="%{y}<br>pontuação %{x:.2f} · %{customdata}<extra></extra>",
    ))
    # Range ate 1.1 para os rotulos exteriores caberem sem cortar.
    fig.update_xaxes(title_text="Pontuação (0 a 1)", range=[0, 1.1],
                     dtick=0.2, zeroline=False)
    fig.update_yaxes(type="category", autorange="reversed",
                     automargin=True, tickfont=dict(size=11))
    fig = _aplicar_tema(
        fig,
        "Composição do IIC"
        "<br><span style='font-size:10.5px;color:#9aa39d'>"
        "Pontuação de cada componente (0–1) · a % é o peso no IIC</span>")
    fig.update_layout(margin=dict(l=8, r=16, t=58, b=44))
    return fig


def figura_comparacao(repo, ids_metro):
    """Barras agrupadas que confrontam o IIC e as suas componentes (todas em
    [0,1]) entre as estacoes de metro selecionadas."""
    if not ids_metro:
        return figura_vazia("Selecione estações de metro para comparar")

    metro = repo.estacoes_metro
    categorias = [rotulo for _, rotulo in _COMPONENTES]

    fig = go.Figure()
    # Componentes a 0 dariam barras de altura nula (invisiveis), passando a ideia
    # de grafico avariado. Desenha-se um TRACO fininho no zero, na cor da estacao;
    # o valor real (0,00) aparece no hover, como nas restantes barras.
    EPS = 0.001
    STUB = 0.015                         # altura visivel minima do traco de valor 0
    for i, id_metro in enumerate(ids_metro):
        sel = metro[metro["id_metro"] == id_metro]
        if sel.empty:
            continue
        linha = sel.iloc[0]
        valores = [float(linha[col]) for col, _ in _COMPONENTES]
        alturas = [STUB if v <= EPS else v for v in valores]
        cor = _PALETA_COMP[i % len(_PALETA_COMP)]
        fig.add_bar(
            name=linha["nome_metro"], x=categorias, y=alturas,
            marker_color=cor, customdata=valores,
            hovertemplate="%{x}<br>%{customdata:.2f}<extra>"
                          + linha["nome_metro"] + "</extra>",
        )

    fig.update_layout(barmode="group")
    fig.update_yaxes(title_text="Valor normalizado", range=[0, 1])
    # O bloco ja tem o cabecalho "Comparar duas estacoes de metro" por cima, por
    # isso dispensa-se o titulo interno (evita repetir e liberta altura). O
    # grafico vive numa celula baixa — tem os seletores por cima —, pelo que as
    # margens grandes faziam o titulo, a legenda e as barras sobreporem-se. Com
    # margens apertadas e a legenda compacta no TOPO (deixa de disputar espaco
    # com o eixo x), passa a caber sem colisoes.
    fig = _aplicar_tema(fig, "")
    fig.update_layout(
        title=None,
        legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0,
                    xanchor="left", font=dict(size=10)),
        margin=dict(l=46, r=12, t=30, b=28),
    )
    return fig