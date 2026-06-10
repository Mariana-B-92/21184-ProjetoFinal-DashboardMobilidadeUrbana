# Dashboard de Análise de Mobilidade Urbana — Lisboa

Protótipo de uma aplicação web interativa para análise da articulação entre o
sistema de bicicletas partilhadas **GIRA**, a **rede ciclável** e a rede de
**metro** do município de Lisboa, a partir de dados abertos da plataforma
[Lisboa Aberta](https://lisboaaberta.cm-lisboa.pt/).

O projeto transforma dados de mobilidade dispersos num modelo integrado e num
conjunto de indicadores que permitem caracterizar a disponibilidade do sistema
GIRA e avaliar o potencial de intermodalidade bicicleta–metro, apresentando os
resultados num *dashboard* cartográfico.

## Índice

- [Visão geral](#visão-geral)
- [Arquitetura](#arquitetura)
- [Indicadores](#indicadores)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Instalação](#instalação)
- [Utilização](#utilização)
- [Testes](#testes)
- [Configuração](#configuração)
- [Fontes de dados](#fontes-de-dados)

## Visão geral

O sistema está organizado em duas fases. Uma fase de **pré-processamento**
(*offline*), que lê os dados de origem, limpa-os, integra-os no espaço, calcula
os indicadores e persiste tudo numa base de dados local. E uma fase de
**apresentação**, em que o *dashboard* consome o modelo já processado e oferece
exploração interativa através de um mapa e de visualizações complementares.

Esta separação garante que a interface permanece fluida, uma vez que o
processamento pesado (na ordem dos milhões de registos do histórico GIRA) ocorre
uma única vez, antes do arranque da aplicação.

## Arquitetura

O projeto segue uma arquitetura em três camadas:

| Camada | Componentes | Responsabilidade |
|--------|-------------|------------------|
| **Dados** | `data/` | Ficheiros de origem e modelo integrado (SQLite, geometrias em WKT) |
| **Processamento** | `etl/`, `kpis/` | Pipeline de ETL em cinco etapas e cálculo dos indicadores |
| **Apresentação** | `app/` | Dashboard interativo (mapa, séries, comparações) |

O pipeline de ETL desenvolve-se em cinco etapas encadeadas: **extração** dos
ficheiros de origem, **limpeza** e normalização, **integração espacial**
(reprojeção, áreas de influência e medidas de distância), cálculo de
**variáveis derivadas** e **carregamento** do modelo integrado. No final, é
gerado um relatório de qualidade dos dados.

## Indicadores

Os indicadores estão organizados em dois grupos.

O **Grupo 1 — Disponibilidade GIRA** caracteriza cada estação de bicicletas:
disponibilidade média, taxa média de disponibilidade, índice de variabilidade
diária e hora de pico (a hora de menor disponibilidade).

O **Grupo 2 — Cobertura de Infraestrutura** caracteriza cada estação de metro
quanto à sua articulação com a bicicleta: distância à estação GIRA mais próxima,
número de estações GIRA na área de influência, comprimento de rede ciclável na
área de influência e disponibilidade nas horas de pico. Estes integram-se num
**Índice de Intermodalidade Composto (IIC)**, que combina proximidade, densidade
de estações e conectividade ciclável num valor sintético entre 0 e 1.

## Estrutura do projeto

```
mobilidade-lisboa/
├── config.py              # Parâmetros externalizados (raios, pesos, CRS, filtros, paleta)
├── construir_modelo.py    # Orquestrador da fase offline (ETL + KPIs + carregamento)
├── iniciar_dashboard.py   # Lançador simples (arranca o servidor e abre o navegador)
├── iniciar_dashboard.bat  # Atalho de duplo-clique para o lançador (Windows)
├── requirements.txt
├── pytest.ini
├── mypy.ini
│
├── data/
│   ├── raw/               # Ficheiros de origem (.7z, .csv, .geojson)
│   └── processed/         # Base de dados gerada (mobilidade.db)
│
├── etl/                   # Pipeline de ETL
│   ├── extract.py         #   1. Extração
│   ├── clean.py           #   2. Limpeza e normalização
│   ├── spatial.py         #   3. Integração espacial
│   ├── derive.py          #   4. Variáveis derivadas
│   ├── load.py            #   5. Carregamento (SQLite, WKT)
│   └── pipeline.py        #   Orquestrador das etapas
│
├── kpis/                  # Cálculo dos indicadores
│   ├── grupo1.py          #   Disponibilidade GIRA
│   ├── grupo2.py          #   Cobertura de infraestrutura
│   └── iic.py             #   Índice de Intermodalidade Composto
│
├── app/                   # Dashboard
│   ├── app.py             #   Aplicação e layout
│   ├── data.py            #   Camada de acesso a dados
│   ├── callbacks.py       #   Interatividade
│   ├── figures.py         #   Visualizações
│   └── assets/            #   Estilos e recursos
│
├── tests/                 # Testes (unitários, sistema, desempenho, escalabilidade)
├── scripts/               # Utilitários (extração dos dados de origem)
├── notebooks/             # Análise exploratória
└── reports/               # Relatório de qualidade dos dados
```

## Instalação

Requer **Python 3.10+**. Recomenda-se a utilização de um ambiente virtual.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Utilização

**1. Preparar os dados de origem.** Colocar os ficheiros de origem em
`data/raw/` e extrair os históricos GIRA:

```bash
python scripts/preparar_dados.py
```

**2. Construir o modelo integrado.** Corre o pipeline completo (ETL e
indicadores) e persiste o resultado em `data/processed/mobilidade.db`:

```bash
python construir_modelo.py
```

Esta etapa só precisa de ser executada uma vez (ou sempre que os dados de origem
ou os parâmetros mudem). Inclui ainda a pré-agregação da série diária global,
para a vista inicial do *dashboard* abrir instantaneamente.

**3. Arrancar o dashboard.** Para utilização normal, basta o duplo-clique em
`iniciar_dashboard.bat` (Windows) ou, em qualquer sistema:

```bash
python iniciar_dashboard.py
```

O servidor arranca e o navegador abre automaticamente em
`http://127.0.0.1:8050`. Para desenvolvimento (com recarregamento automático e
avisos), pode usar-se o modo *debug*:

```bash
python -m app.app
```

Em qualquer dos casos, a aplicação fica disponível em `http://127.0.0.1:8050`.

## Testes

A suite de testes cobre os indicadores, o pipeline, a camada de apresentação,
a integração, o desempenho e a escalabilidade do sistema:

```bash
pytest                                 # toda a suite
pytest -s tests/test_desempenho.py     # com os tempos medidos
```

Ver `tests/README.md` para a descrição de cada conjunto de testes.

## Configuração

Os parâmetros do sistema estão centralizados em `config.py` e podem ser
ajustados sem alterar o código: raio das áreas de influência, truncatura de
distância, pesos do IIC, sistemas de coordenadas, critérios de filtragem dos
dados e a paleta de cores usada de forma coerente no mapa, nas legendas e nos
gráficos. Esta externalização facilita a análise de sensibilidade e a adaptação
a outros contextos.

## Fontes de dados

Todos os dados provêm da plataforma Lisboa Aberta:

- **Histórico GIRA** — registos de disponibilidade das estações de bicicletas;
- **Rede ciclável** — geometria das ciclovias do município;
- **Estações de metro** — localização das estações da rede de metropolitano.

A qualidade e a cobertura dos dados abertos não são controladas pela equipa; as
limitações identificadas durante o processamento são registadas no relatório de
qualidade gerado pelo pipeline.