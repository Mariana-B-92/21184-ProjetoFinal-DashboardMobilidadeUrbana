---
title: Intermodalidade Bicicleta-Metro Lisboa
emoji: 🚲
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
---

# Dashboard de Intermodalidade Bicicleta–Metro — Lisboa

Aplicação web interativa (Dash) para análise da articulação entre o sistema de
bicicletas partilhadas **GIRA**, a **rede ciclável** e o **metro** de Lisboa, a
partir de dados abertos da plataforma Lisboa Aberta. Protótipo desenvolvido no
âmbito do Projeto de Engenharia Informática da Universidade Aberta.

## Execução

A aplicação corre via **Docker** e é servida por **gunicorn** na porta `7860`,
expondo o objeto Flask `server` definido em `app/app.py`. O modelo de dados
integrado (`data/processed/mobilidade.db`, ~230 MB) é versionado com **git-LFS**
e lido em modo só-leitura: as tabelas pequenas são carregadas em memória no
arranque e o histórico de disponibilidade (~1,99 M de registos) é consultado a
pedido a partir do SQLite.

> O cabeçalho YAML acima configura o Space (SDK Docker, porta 7860). Não remover.
