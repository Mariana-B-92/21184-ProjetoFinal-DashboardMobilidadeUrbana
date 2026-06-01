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
| `test_unit_kpis.py` | Testes unitários | Fórmulas dos indicadores e casos-limite: normalização min-max com max=min, truncatura antes da normalização, TMD e IIC em [0,1], pesos somam 1 |
| `test_unit_etl.py` | Testes unitários | Parsing e limpeza dos dados; comprimento ciclável por interseção (e não por soma total) |
| `test_sistema.py` | Testes de sistema | Integridade do modelo SQLite; coerência entre os indicadores da app (tempo real) e os persistidos |
| `test_desempenho.py` | Testes de desempenho | Tempos das operações-chave (arranque, série temporal, heatmap, cobertura, consulta indexada) |
| `test_escalabilidade.py` | Testes de escalabilidade | Evolução do tempo com volume crescente de dados, número de estações e raio de influência |

A exemplificação do funcionamento normal com capturas de ecrã (também pedida no
Capítulo 4) é feita com o dashboard a correr (`python -m app.app`), relacionando
cada captura com o elemento da especificação que demonstra.
