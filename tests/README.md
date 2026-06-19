# Testes

Suite de testes do projeto, organizada para corresponder ao Capítulo 4
(Testes) do relatório final.

## Execução

```bash
pip install -r requirements.txt        # inclui o pytest
pytest                                 # corre toda a suite
pytest -s tests/test_desempenho.py     # mostra os tempos medidos
pytest tests/test_unit_kpis.py         # apenas um conjunto
```

A primeira execução constrói o modelo integrado numa base de dados temporária
(uma vez por sessão, via fixtures em `conftest.py`), pelo que demora ~1 min;
os testes unitários puros são quase instantâneos.

## Correspondência com o Capítulo 4

| Ficheiro | Subsecção do relatório | O que cobre |
|----------|------------------------|-------------|
| `test_unit_kpis.py` | Testes unitários | Fórmulas dos indicadores e casos-limite: normalização min-max com max=min, truncatura antes da normalização, TMD e IIC em [0,1], pesos somam 1, disponibilidade nas horas de pico com área de influência vazia |
| `test_unit_etl.py` | Testes unitários | Parsing e limpeza dos dados (GIRA, metro e ciclável); comprimento ciclável por interseção (e não por soma total); clamp da taxa de ocupação a [0,1] |
| `test_unit_app.py` | Testes unitários | Camada de apresentação: formatação de valores ausentes, classes da legenda, parâmetros de cor do mapa por indicador e cartões dos painéis |
| `test_unit_figuras.py` | Testes unitários | Geradores de figuras Plotly: cada `figura_*` devolve uma figura válida com dados, e o estado vazio (sem traços, com mensagem) nos casos-limite |
| `test_analise_vista.py` | Testes unitários | Lógica de seleção da área de análise (par de figuras e `vista` por indicador e seleção), via a função pura extraída do callback `atualizar_analise` |
| `test_sistema.py` | Testes de sistema | Integridade do modelo SQLite; coerência entre os indicadores da app (tempo real) e os persistidos; consultas do repositório nos casos-limite (seleção inexistente, conjuntos vazios, filtro de datas) |
| `test_desempenho.py` | Testes de desempenho | Tempos das operações-chave (arranque, série temporal, heatmap, cobertura, consulta indexada) |
| `test_escalabilidade.py` | Testes de escalabilidade | Evolução do tempo com volume crescente de dados, número de estações e raio de influência |

A exemplificação do funcionamento normal com capturas de ecrã (também pedida no
Capítulo 4) é feita com o dashboard a correr (`python -m app.app`), relacionando
cada captura com o elemento da especificação que demonstra.
