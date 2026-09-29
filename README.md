# Offshore Portfolio: consolidação multi-custodiante em Python

[![CI](https://github.com/HagataMendes/offshore-python-portfolio-consolidation/actions/workflows/ci.yml/badge.svg)](https://github.com/HagataMendes/offshore-python-portfolio-consolidation/actions/workflows/ci.yml)
![Python 3.11](https://img.shields.io/badge/python-3.11-3776AB)
![FastAPI](https://img.shields.io/badge/FastAPI-009688)
![pandas](https://img.shields.io/badge/pandas-150458)
![React + TypeScript](https://img.shields.io/badge/React-TypeScript-3178C6)

**Demo da tela:** https://hagatamendes.github.io/offshore-python-portfolio-consolidation/
(roda com um snapshot das respostas da API Python)

Projeto de estudo que simula a plataforma de um time de tecnologia de wealth management offshore:
receber posições e movimentações de **vários custodiantes**, cada um no seu formato, consolidar
tudo por cliente, **reconciliar**, calcular a **rentabilidade pelo método TWR** e gerar o
**extrato consolidado**, com uma interface web para clientes e backoffice.

Os clientes são fictícios: **Maria** (conta na Pershing e no UBS) e **Manoel** (conta no UBS).

## Stack

| Camada | Tecnologia |
|---|---|
| Back-end | Python 3.11, FastAPI, Pydantic, SQLAlchemy, pytest, ruff |
| Análise | pandas, NumPy, Jupyter (risco, drawdown, concentração, câmbio, contribuição por ativo) |
| Dados | Postgres (posições e movimentações), DynamoDB (arquivos processados) |
| Mensageria | S3 → SQS (com DLQ) → worker → SNS |
| Infra local | Docker Compose, LocalStack |
| Front-end | React, TypeScript, Tailwind CSS, Recharts, Vitest |

## Como funciona

```
Pershing (CSV) ──┐                                  ┌─ DynamoDB: já processei este arquivo?
                 ├─► S3 ─► SQS ─► worker Python ────┼─ adapter do custodiante → modelo único
UBS (JSON) ──────┘          │                       ├─ Postgres: posições, movimentações, quebras
                         DLQ (erros)                └─ SNS: "carteira atualizada"
                                                              │
                                  API FastAPI (TWR, extrato, consolidado) ─► tela React
```

## Rodando

Com Docker, tudo de uma vez:

```bash
docker compose up --build
# tela:  http://localhost:5173
# API:   http://localhost:8000/docs
```

Sem Docker, só Python e Node:

```bash
cd backend && pip install -e ".[dev]" && uvicorn app.api.main:app --reload
cd frontend && npm install && echo "VITE_API_URL=http://localhost:8000" > .env.local && npm run dev
```

Sem a API, a tela usa um snapshot das respostas dela (`frontend/src/mocks/snapshot.json`).

## Testes

```bash
cd backend && pytest        # 62 testes: domínio, adapters, ingestão (memória, SQLite, Postgres), análise, API, AWS
cd frontend && npm test     # TWR em TypeScript conferido contra o resultado do Python
```

## Integração contínua

A cada push, o GitHub Actions roda:

- **Back-end:** ruff (lint e formatação) e os 62 testes, incluindo os de banco num **Postgres 16 de verdade** (serviço do workflow)
- **Front-end:** oxlint, Vitest e o build de produção (TypeScript + Vite)
- **Docker:** valida o `docker-compose.yml`, faz o build da imagem e confere se a API sobe e responde
- **Snapshot:** confere se os números da demo estática ainda batem com o que a API calcula

E a cada push na `main`, a tela é publicada no GitHub Pages.

## Notebook

A análise com pandas está explicada passo a passo em [`backend/notebooks/analise_geral.ipynb`](backend/notebooks/analise_geral.ipynb).

Detalhes de cada parte em [`backend/README.md`](backend/README.md) e [`frontend/README.md`](frontend/README.md).
