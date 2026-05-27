# Dashboard Interativo para Análise de Dados de Mobilidade Urbana

Projeto de Engenharia Informática — Universidade Aberta

**Autores:** Ana Filipa Oliveira (2200079), Mariana Barrote (2200640)
**Orientador:** Prof. Doutor Paulo Pombinho

---

## Sobre o projeto

Dashboard web interativo para análise da intermodalidade bicicleta–metro
no município de Lisboa. Integra dados abertos do portal *Lisboa Aberta*
(sistema GIRA, rede ciclável, estações de metro) e calcula indicadores
de micromobilidade e intermodalidade, incluindo um Índice de Intermodalidade
Composto (IIC).

## Estrutura do projeto

```
.
├── config.yaml         # Parâmetros configuráveis (pesos, raios, caminhos)
├── data/               # Dados (não versionados)
│   ├── raw/            # Datasets originais do Lisboa Aberta
│   ├── processed/      # Outputs do ETL (SQLite)
│   └── reports/        # Relatórios de qualidade de dados
├── src/                # Código-fonte
│   ├── etl/            # Pipeline de extração-transformação-carregamento
│   ├── indicators/     # Cálculo de indicadores e IIC
│   └── dashboard/      # Aplicação web (Dash)
├── scripts/            # Pontos de entrada (run_etl.py, etc.)
├── notebooks/          # Análises exploratórias
└── tests/              # Testes unitários
```

## Instalação

1. Clonar o repositório.
2. Criar um ambiente virtual e instalar dependências:

   ```bash
   python -m venv venv
   source venv/bin/activate    # Linux/Mac
   venv\Scripts\activate       # Windows
   pip install -r requirements.txt
   ```

3. Descarregar os datasets do portal [Lisboa Aberta](https://lisboaaberta.cm-lisboa.pt)
   e colocá-los em `data/raw/` com os nomes indicados em `config.yaml`:
   - `GIRA_dados_historicos_S1_2022.csv`
   - `GIRA_dados_historicos_S2_2022.csv`
   - `estacoes_metro.geojson`
   - `rede_ciclavel.geojson`

## Utilização

### Executar o pipeline ETL completo

```bash
python scripts/run_etl.py
```

### Calcular indicadores

```bash
python scripts/run_indicators.py
```

### Executar tudo de uma vez

```bash
python scripts/run_all.py
```

### Lançar o dashboard (Fase 4)

```bash
python -m src.dashboard.app
```

## Configuração

Todos os parâmetros do sistema (caminhos, raios de influência, pesos do IIC,
etc.) estão em `config.yaml`. Pode ser editado sem alterar o código.

## Licença

Trabalho académico no âmbito da Universidade Aberta. Dados de domínio público
do portal Lisboa Aberta.
