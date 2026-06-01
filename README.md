# Dashboard Interativo para Análise de Dados de Mobilidade Urbana

Protótipo de dashboard web para análise da intermodalidade bicicleta–metro no
município de Lisboa, a partir de dados abertos da plataforma *Lisboa Aberta*
(histórico GIRA, rede ciclável e estações de metro).

## Arquitetura

O projeto segue uma arquitetura em três camadas (ver secção 2.2 do relatório):

| Camada | Pasta | Responsabilidade |
|--------|-------|------------------|
| Dados | `data/` | Fontes originais e modelo integrado (SQLite) |
| Processamento | `etl/`, `kpis/` | Pipeline de ETL (5 etapas) e cálculo de indicadores — executados *offline* |
| Apresentação | `app/` | Dashboard Dash (consome dados já processados) |

## Estrutura de pastas

```
mobilidade-lisboa/
├── config.py            # Parâmetros externalizados (raio, pesos IIC, CRS, filtros)
├── requirements.txt
├── data/
│   ├── raw/             # Fontes originais (.7z, .geojson). CSV extraídos não versionados.
│   └── processed/       # mobilidade.db (gerado pelo ETL)
├── etl/                 # Pipeline: extract → clean → spatial → derive → load
├── kpis/                # Indicadores: grupo1, grupo2, iic
├── app/                 # Dashboard Dash (Fase 4)
├── notebooks/           # Análise exploratória
├── reports/             # Relatório de qualidade dos dados
└── scripts/             # Utilitários (ex.: extração dos .7z)
```

## Instalação

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Preparação dos dados

Colocar os ficheiros originais em `data/raw/` e extrair os históricos GIRA:

```bash
python scripts/preparar_dados.py
```

## Construção do modelo (fase offline)

Corre o ETL (etapas 1-5), calcula os indicadores (Grupo 1 e Grupo 2 + IIC) e
persiste tudo em `data/processed/mobilidade.db`:

```bash
python construir_modelo.py
```

## Execução do dashboard

```bash
python -m app.app               # servidor local acessível no browser
```
