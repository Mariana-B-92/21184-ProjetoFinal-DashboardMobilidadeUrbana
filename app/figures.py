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
_ESCALA_VERDE = [[0, "#f4f5f3"], [0.5, "#7fc99b"], [1, "#07733a"]]


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
    """Serie temporal da disponibilidade media diaria de uma estacao GIRA."""
    if id_estacao is None:
        return figura_vazia()
    st = repo.serie_temporal(id_estacao, inicio=inicio, fim=fim, frequencia="D")
    if st.empty:
        return figura_vazia("Sem dados para o período selecionado")

    fig = go.Figure(go.Scatter(
        x=st["timestamp"], y=st["numbicicletas"],
        mode="lines", line=dict(color=_ACENTO, width=1.6),
        fill="tozeroy", fillcolor="rgba(10,154,74,.10)",
        hovertemplate="%{x|%d/%m/%Y}<br>%{y:.1f} bicicletas<extra></extra>",
    ))
    fig.update_yaxes(title_text="Bicicletas (média diária)")
    return _aplicar_tema(fig, "Disponibilidade ao longo do tempo")


def figura_heatmap(repo, id_estacao):
    """Heatmap da disponibilidade media por dia da semana x hora do dia."""
    if id_estacao is None:
        return figura_vazia()
    matriz = repo.heatmap_disponibilidade(id_estacao)
    if matriz.empty:
        return figura_vazia("Sem dados suficientes")

    fig = go.Figure(go.Heatmap(
        z=matriz.values, x=list(matriz.columns), y=list(matriz.index),
        colorscale=_ESCALA_VERDE, colorbar=dict(title="bicis", thickness=12),
        hovertemplate="%{y}, %{x}h<br>%{z:.1f} bicicletas<extra></extra>",
    ))
    fig.update_xaxes(title_text="Hora do dia", dtick=3)
    fig.update_yaxes(autorange="reversed")
    return _aplicar_tema(fig, "Padrão horário (hora × dia da semana)")


# Paleta categorica para distinguir estacoes na comparacao.
_PALETA_COMP = ["#07733a", "#1f6fb2", "#d6322e", "#f4c20d"]

# Componentes do IIC a confrontar (todas normalizadas em [0,1]).
_COMPONENTES = [
    ("prox_norm", "Proximidade"),
    ("n_gira_norm", "Densidade GIRA"),
    ("comp_ciclavel_norm", "Rede ciclável"),
    ("iic", "IIC (global)"),
]


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

    fig.update_layout(barmode="group", legend=dict(
        orientation="h", yanchor="bottom", y=1.02, x=0, font=dict(size=11)))
    fig.update_yaxes(title_text="Valor normalizado", range=[0, 1])
    return _aplicar_tema(fig, "Comparação de intermodalidade")
