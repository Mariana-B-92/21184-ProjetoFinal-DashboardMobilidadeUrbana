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
# Escala de disponibilidade do heatmap: a mesma paleta de 5 classes do config
# (vermelho = pouca disponibilidade -> verde = muita), aqui como colorscale
# continua [posicao, cor] para o Plotly.
_ESCALA_DISP = [[i / (len(config.ESCALA_COR) - 1), cor]
                for i, cor in enumerate(config.ESCALA_COR)]

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
        colorscale=_ESCALA_DISP,
        colorbar=dict(title="Bicicletas<br>disponíveis", thickness=12),
        hovertemplate="%{y}, %{x}h<br>%{z:.1f} bicicletas<extra></extra>",
    ))
    fig.update_xaxes(title_text="Hora do dia", dtick=3)
    fig.update_yaxes(autorange="reversed")
    # Poucas celulas com dados -> assinala historico escasso (coerente com a serie).
    if int(matriz.notna().sum().sum()) < 5:
        fig.add_annotation(
            text="Histórico limitado nesta estação", xref="paper", yref="paper",
            x=0.5, y=1.12, showarrow=False,
            font=dict(family=_FONTE, size=11, color="#9aa39d"))
    return _aplicar_tema(
        fig, "Disponibilidade média de bicicletas (hora × dia da semana)")


def figura_serie_global(repo, inicio=None, fim=None):
    """Serie diaria da disponibilidade media em todas as estacoes GIRA."""
    st = repo.serie_global(inicio=inicio, fim=fim)
    if st is None or st.empty:
        return figura_vazia("Sem dados para o período selecionado")
    fig = go.Figure(go.Scatter(
        x=st["data"], y=st["media"], mode="lines",
        line=dict(color=_ACENTO, width=1.6),
        fill="tozeroy", fillcolor="rgba(10,154,74,.10)",
        hovertemplate="%{x|%d/%m/%Y}<br>%{y:.1f} bicicletas<extra></extra>",
    ))
    fig.update_yaxes(title_text="Bicicletas (média diária)")
    return _aplicar_tema(fig, "Disponibilidade média — todas as estações GIRA")


def figura_serie_conjunto(repo, ids, inicio=None, fim=None):
    """Serie diaria da disponibilidade media do CONJUNTO de estacoes GIRA na
    area de influencia de um metro (a 2.5.2 preve series 'para uma estacao ou
    conjunto de estacoes')."""
    if not ids:
        return figura_vazia("Sem estações GIRA na área de influência")
    st = repo.serie_conjunto(ids, inicio=inicio, fim=fim)
    if st is None or st.empty:
        return figura_vazia("Sem dados para o período selecionado")
    fig = go.Figure(go.Scatter(
        x=st["data"], y=st["media"], mode="lines",
        line=dict(color=_ACENTO, width=1.6),
        fill="tozeroy", fillcolor="rgba(10,154,74,.10)",
        hovertemplate="%{x|%d/%m/%Y}<br>%{y:.1f} bicicletas<extra></extra>",
    ))
    fig.update_yaxes(title_text="Bicicletas (média diária)")
    return _aplicar_tema(
        fig, f"Disponibilidade média — {len(ids)} GIRA na área de influência")


def figura_ranking_iic(repo, n=7, pesos=None):
    """Ranking das estacoes de metro pelo IIC, na vista inicial (sem selecao).

    Mostra os extremos — as 'n' estacoes de maior potencial intermodal e as 'n'
    de menor (estas sao as candidatas a intervencao prioritaria, conforme o
    documento de metricas). Apoia o cenario de 'consulta de indicadores de
    sintese'. Usa os dados de metro ja em memoria, pelo que renderiza de
    imediato (sem consultas pesadas).

    'pesos' = (w_prox, w_dens, w_cicl). O IIC e RECALCULADO a partir das tres
    componentes normalizadas com estes pesos (normalizados para somarem 1),
    permitindo a analise de sensibilidade prevista para a Fase 5. Por omissao
    usa os pesos de referencia 0,40 / 0,35 / 0,25.
    """
    w = tuple(pesos) if pesos else (0.40, 0.35, 0.25)
    soma = sum(w)
    if soma <= 0:                       # salvaguarda: pesos todos a zero
        w = (1 / 3, 1 / 3, 1 / 3)
        soma = 1.0
    w = (w[0] / soma, w[1] / soma, w[2] / soma)
    personalizado = tuple(round(x, 2) for x in w) != (0.40, 0.35, 0.25)

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
    cores = [config.cor_classe(v) for v in sel["iic_calc"]]
    curtos = [x if len(x) <= 24 else x[:23] + "…" for x in nomes]

    fig = go.Figure(go.Bar(
        x=sel["iic_calc"], y=nomes, orientation="h", marker_color=cores,
        hovertemplate="%{y}<br>IIC: %{x:.2f}<extra></extra>",
    ))
    fig.update_xaxes(title_text="IIC", range=[0, 1])
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


def figura_distribuicao_gira(repo, id_metro, raio=None, cobertura=None):
    """Distribuicao da disponibilidade das estacoes GIRA na area de influencia.

    Barras ordenadas por disponibilidade (taxa media, em %), coloridas pela
    mesma paleta de 5 classes do mapa. Reproduz o painel "Distribuicao das
    estacoes GIRA na area" do Storyboard 3.

    'cobertura' pode ser passada ja calculada (pelo callback) para evitar repetir
    a operacao espacial.
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
    curtos = [n if len(n) <= 26 else n[:25] + "…" for n in nomes]

    fig = go.Figure(go.Bar(
        x=gira["tmd_pct"], y=nomes, orientation="h", marker_color=cores,
        hovertemplate="%{y}<br>%{x:.0f}%<extra></extra>",
    ))
    fig.update_xaxes(title_text="Disponibilidade média (%)", range=[0, 100])
    fig.update_yaxes(type="category", tickmode="array",
                     tickvals=nomes, ticktext=curtos,
                     automargin=True, tickfont=dict(size=11))
    fig = _aplicar_tema(fig, "Distribuição das estações GIRA na área")
    # Margem esquerda fica a cargo do automargin; a base e pequena.
    fig.update_layout(margin=dict(l=8, r=16, t=40, b=44))
    return fig


def figura_comparacao(repo, ids_metro):
    """Compara o IIC e as suas componentes normalizadas entre estacoes de metro.

    Grafico de barras agrupadas: cada categoria (componente) confronta as
    estacoes selecionadas. Por as componentes estarem todas em [0,1], a leitura
    e direta e evidencia que dimensao explica as diferencas de IIC.
    """
    if not ids_metro:
        return figura_vazia("Selecione estações de metro para comparar")

    metro = repo.estacoes_metro
    categorias = [rotulo for _, rotulo in _COMPONENTES]

    fig = go.Figure()
    for i, id_metro in enumerate(ids_metro):
        sel = metro[metro["id_metro"] == id_metro]
        if sel.empty:
            continue
        linha = sel.iloc[0]
        valores = [float(linha[col]) for col, _ in _COMPONENTES]
        cor = _PALETA_COMP[i % len(_PALETA_COMP)]
        fig.add_bar(
            name=linha["nome_metro"], x=categorias, y=valores,
            marker_color=cor,
            hovertemplate="%{x}<br>%{y:.2f}<extra>" + linha["nome_metro"] + "</extra>",
        )

    fig.update_layout(barmode="group")
    fig.update_yaxes(title_text="Valor normalizado", range=[0, 1])
    fig = _aplicar_tema(fig, "Comparação de intermodalidade")
    # Legenda no fundo (afasta-a do titulo, que ficava colado) e margens folgadas.
    fig.update_layout(
        legend=dict(orientation="h", yanchor="top", y=-0.18, x=0.5,
                    xanchor="center", font=dict(size=11)),
        margin=dict(l=48, r=16, t=44, b=72))
    return fig