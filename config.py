"""
Configuracao central do projeto.

Reune todos os parametros externalizados do pipeline, em conformidade com o
principio de "externalizacao de parametros" definido na seccao 2.4 do relatorio
intermedio. Alterar valores aqui nao exige tocar no codigo do ETL nem dos KPIs.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Caminhos
# ---------------------------------------------------------------------------
RAIZ = Path(__file__).resolve().parent
DIR_RAW = RAIZ / "data" / "raw"
DIR_PROCESSED = RAIZ / "data" / "processed"
DIR_REPORTS = RAIZ / "reports"

# Ficheiros de origem (plataforma Lisboa Aberta)
FICHEIROS_GIRA = [
    DIR_RAW / "gira_1semestre_2022.csv",
    DIR_RAW / "gira_2semestre_2022.csv",
]
FICHEIRO_METRO = DIR_RAW / "estacoes_metro.geojson"
FICHEIRO_CICLAVEL = DIR_RAW / "rede_ciclavel.geojson"

# Base de dados integrada (saida do ETL)
BASE_DADOS = DIR_PROCESSED / "mobilidade.db"
RELATORIO_QUALIDADE = DIR_REPORTS / "relatorio_qualidade.json"

# ---------------------------------------------------------------------------
# Sistemas de coordenadas
# ---------------------------------------------------------------------------
# CRS geografico das fontes (graus). Persistencia final em WGS84.
CRS_GEOGRAFICO = "EPSG:4326"
# CRS metrico para operacoes de distancia/buffer em metros.
# ETRS89 / Portugal TM06: projecao oficial de Portugal Continental.
CRS_METRICO = "EPSG:3763"

# Fuso horario para conversao dos timestamps UTC do historico GIRA.
FUSO_HORARIO = "Europe/Lisbon"

# ---------------------------------------------------------------------------
# Parametros espaciais (Grupo 2 de indicadores)
# ---------------------------------------------------------------------------
# Raio da area de influencia em torno de cada estacao de metro (metros).
RAIO_INFLUENCIA_M = 500

# Truncatura da distancia minima antes da normalizacao do IIC (metros).
# A normalizacao min-max e aplicada SOBRE a distancia ja truncada.
DISTANCIA_MAX_TRUNCATURA_M = 1000

# ---------------------------------------------------------------------------
# Pesos do Indice de Intermodalidade Composto (IIC)
# Devem somar 1. Parametrizaveis para a analise de sensibilidade da Fase 5.
# ---------------------------------------------------------------------------
PESOS_IIC = {
    "proximidade": 0.40,
    "densidade": 0.35,
    "ciclavel": 0.25,
}

# Valor neutro atribuido na normalizacao min-max quando max(x) == min(x),
# evitando divisao por zero (caso-limite documentado nas metricas).
VALOR_NEUTRO_NORMALIZACAO = 0.5

# ---------------------------------------------------------------------------
# Filtros aplicados na limpeza (Etapa 2 do ETL)
# ---------------------------------------------------------------------------
# So sao contabilizados segmentos ciclaveis efetivamente executados.
SITUACAO_CICLAVEL_VALIDA = "Executado"
# So sao contabilizadas estacoes de metro em funcionamento.
SITUACAO_METRO_VALIDA = "Linha existente"

# ---------------------------------------------------------------------------
# Decisoes de tratamento de dados (configuraveis; ver relatorio de qualidade)
# Cada escolha fica registada aqui e refletida no relatorio de qualidade,
# de modo a ser justificavel no relatorio final.
# ---------------------------------------------------------------------------
# Restringir o calculo de disponibilidade aos registos em estado "active"?
# Apenas "active" representa oferta efetiva; os restantes estados (incluindo
# "repair", que reflete indisponibilidade operacional) sao excluidos. O nome da
# flag e mantido por coerencia com o relatorio.
EXCLUIR_ESTADO_REPAIR = True

# Remover registos com numero de docas igual a zero?
# (evita divisao por zero no calculo da taxa media de disponibilidade)
REMOVER_DOCAS_ZERO = True

# Limitar a taxa de ocupacao instantanea a [0, 1]?
# (alguns registos tem numbicicletas > numdocas; TMD e definido em [0,1])
LIMITAR_TAXA_OCUPACAO = True

# ---------------------------------------------------------------------------
# Paleta do dashboard: escala sequencial de 5 classes (RdYlGn, vermelho->verde),
# fonte unica do mapa, legendas e graficos. ESCALA_RGB e a versao [R,G,B] para
# o JS dos marcadores.
# ---------------------------------------------------------------------------
ESCALA_COR = ["#c6402b", "#ec952e", "#f1df64", "#afce65", "#277452"]


def _hex_para_rgb(cor):
    cor = cor.lstrip("#")
    return [int(cor[i:i + 2], 16) for i in (0, 2, 4)]


ESCALA_RGB = [_hex_para_rgb(c) for c in ESCALA_COR]


def cor_classe(t, escala=None):
    """Cor discreta da paleta para um valor normalizado t em [0, 1].

    Trunca t a [0, 1] e mapeia-o a uma das classes da escala sequencial. Fonte
    unica do mapeamento valor->cor, usada pelo medidor do IIC e pelas barras dos
    graficos (coerente com os marcadores do mapa e as legendas).
    """
    escala = escala or ESCALA_COR
    t = max(0.0, min(1.0, float(t)))
    return escala[min(int(t * len(escala)), len(escala) - 1)]

# Paleta qualitativa da comparacao entre estacoes (1.a = A, 2.a = B, ...).
# Partilhada pelas barras do grafico e pelos aneis de destaque no mapa, para
# que a cor de cada estacao seja a mesma nos dois sitios.
PALETA_COMPARACAO = ["#07733a", "#1f6fb2", "#d6322e", "#f4c20d"]