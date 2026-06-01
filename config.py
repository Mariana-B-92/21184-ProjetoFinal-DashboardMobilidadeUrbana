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
# So sao contabilizados segmentos cicláveis efetivamente executados.
SITUACAO_CICLAVEL_VALIDA = "Executado"
# So sao contabilizadas estacoes de metro em funcionamento.
SITUACAO_METRO_VALIDA = "Linha existente"

# ---------------------------------------------------------------------------
# Decisoes de tratamento de dados (configuraveis; ver relatorio de qualidade)
# Cada escolha fica registada aqui e refletida no relatorio de qualidade,
# de modo a ser justificavel no relatorio final.
# ---------------------------------------------------------------------------
# Excluir registos com estado "repair" do calculo de disponibilidade?
# (refletem indisponibilidade operacional, nao oferta efetiva)
EXCLUIR_ESTADO_REPAIR = True

# Remover registos com numero de docas igual a zero?
# (evita divisao por zero no calculo da taxa media de disponibilidade)
REMOVER_DOCAS_ZERO = True

# Limitar a taxa de ocupacao instantanea a [0, 1]?
# (alguns registos tem numbicicletas > numdocas; TMD e definido em [0,1])
LIMITAR_TAXA_OCUPACAO = True
