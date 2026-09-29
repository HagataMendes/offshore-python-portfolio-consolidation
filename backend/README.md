# Back-end: consolidação offshore em Python

Recebe os arquivos de posições e movimentações dos custodiantes (Pershing e UBS),
traduz cada formato para um modelo único, reconcilia as posições, calcula a
rentabilidade pelo método TWR e expõe tudo numa API REST com FastAPI.

## Como rodar

### Tudo junto, com Docker (recomendado)

Na raiz do repositório:

```bash
docker compose up --build
```

Sobe Postgres, LocalStack (S3, SQS, SNS e DynamoDB locais), o worker, a API e a tela.
O serviço `aws-setup` cria os recursos e "entrega" os 53 arquivos de setembro no S3,
como se fossem os custodiantes. O worker processa um por um.

- Tela: http://localhost:5173
- API e documentação: http://localhost:8000/docs
- Postgres: `psql postgresql://offshore:offshore@localhost:5432/offshore`

### Só o Python, sem Docker

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

uvicorn app.api.main:app --reload     # API em http://localhost:8000/docs
pytest                                 # testes
ruff check .                           # lint
```

Sem `DATABASE_URL` e sem `USE_AWS`, tudo fica em memória e a própria API carrega os
arquivos de exemplo ao subir. Bom para desenvolver e para os testes.

### Configuração

| Variável | O que faz | Padrão |
|---|---|---|
| `DATABASE_URL` | Banco das posições (`postgresql+psycopg://...`) | vazio = memória |
| `USE_AWS` | Usa DynamoDB, SNS e S3 (e o worker via SQS) | `false` |
| `AWS_ENDPOINT_URL` | Endereço do LocalStack; vazio na AWS real | vazio |
| `LOAD_SAMPLES` | A API carrega os arquivos de exemplo ao subir | `true` sem AWS |
| `TEST_DATABASE_URL` | Roda os testes também num Postgres real | vazio |

## Endpoints

| Método | Rota | O que devolve |
|---|---|---|
| GET | `/clients` | Clientes cadastrados |
| GET | `/clients/{id}/positions?date=2026-09-30` | Carteira consolidada na data + série do mês |
| GET | `/clients/{id}/statement?month=2026-09` | Extrato consolidado do mês |
| GET | `/clients/{id}/performance?from=2026-08-31&to=2026-09-30` | TWR, sub-períodos, meses e acumulado do ano |
| GET | `/analytics/overview?from=2026-08-31&to=2026-09-30` | Análise geral com pandas: risco, concentração, câmbio, contribuição |
| GET | `/ingestion/files` | Log dos arquivos recebidos e o que aconteceu com cada um |
| POST | `/ingestion/files` | Envio manual de um arquivo de custodiante |
| GET | `/reconciliation/breaks` | Quebras de reconciliação |
| GET | `/health` | Saúde do serviço |

## Arquitetura

```
                  ┌────────── worker (app/worker.py) ───────────┐
custodiante → S3 ─┤ SQS → baixa do S3 → IngestionService         ├─→ SNS "carteira-atualizada"
   (inbox/)       │         │ idempotência: DynamoDB             │
                  │         │ adapter → Postgres → reconciliação │
                  └─────────┴────────────────────────────────────┘
                                          │
                              API FastAPI (app/api) → tela React
```

```
app/
├── domain/        # regras de negócio em Python puro: não conhece banco, AWS nem HTTP
│   ├── models.py          # Holding, Transaction, ValuationPoint... (valores em Decimal)
│   ├── performance.py     # TWR, sub-períodos, conta ingênua
│   ├── reconciliation.py  # posição contábil × posição do custodiante
│   ├── statement.py       # extrato do mês
│   └── valuation.py       # quantidade × preço × câmbio
├── adapters/      # um adapter por custodiante, todos com o mesmo contrato
│   ├── pershing.py        # CSV, datas MM/DD/AAAA, ticker
│   └── ubs.py             # JSON, datas ISO, ISIN, renda fixa em %
├── ports.py       # interfaces: repositório, registro de arquivos, eventos
├── infra/         # implementações das interfaces
│   ├── memory.py          # em memória (testes e demo)
│   ├── sql.py             # Postgres (SQLAlchemy Core, NUMERIC exato)
│   └── aws.py             # DynamoDB (idempotência) e SNS (eventos)
├── ingestion/     # o caminho do arquivo: idempotência → adapter → gravação → reconciliação → evento
├── worker.py      # consome a SQS, com DLQ para arquivos inválidos
├── services.py    # casos de uso usados pela API
├── analytics.py   # análise geral com pandas (risco, concentração, câmbio, contribuição)
├── container.py   # monta as peças conforme a configuração
└── api/           # FastAPI + schemas Pydantic
scripts/
├── generate_sample_data.py  # gera os arquivos dos custodiantes
├── bootstrap_aws.py         # cria bucket, filas, tópico e tabela
├── upload_samples.py        # simula os custodiantes enviando para o S3
└── export_snapshot.py       # salva as respostas da API para a prévia estática do front
notebooks/
└── analise_geral.ipynb      # a mesma análise, passo a passo, com tabelas e gráficos
```

**Por que Postgres e DynamoDB?** Posições e movimentações são dados relacionados, com
consultas por cliente, data e ativo: banco relacional. O controle de arquivos processados é
uma consulta por chave (o hash do arquivo), com escrita condicional atômica: DynamoDB.

**Como a idempotência funciona com vários workers?** Antes de processar, o worker faz um
`put_item` condicional no DynamoDB (`attribute_not_exists`). Só um consegue. Se o
processamento falhar, a reserva é desfeita para a nova tentativa.

**Erros:** arquivo com layout errado é erro permanente e vai direto para a DLQ. Erro
temporário (banco fora do ar) deixa a mensagem na fila; a SQS tenta de novo e, depois de 3
vezes, move para a DLQ sozinha (redrive policy).

**Ordem dos arquivos:** a demo processa uma mensagem por vez. Em produção, a ordem por conta
seria garantida com uma fila FIFO (`MessageGroupId` = conta no custodiante), já que a
notificação do S3 não publica direto em FIFO: o caminho seria S3 → EventBridge → SQS FIFO.

**Por que o domínio é separado?** As regras de negócio (TWR, reconciliação) são o que
mais importa e o que mais precisa de teste. Isoladas, rodam sem banco nem AWS, e trocar a
infraestrutura não mexe nelas.

**Por que `Decimal` e não `float`?** Em `float`, `0.1 + 0.2` dá `0.30000000000000004`.
Em dinheiro isso vira centavos sumindo. O arredondamento usa o modo bancário (meio para o par).

## Os dados de exemplo

`scripts/generate_sample_data.py` gera setembro/2026 inteiro para dois clientes fictícios:

- **Maria:** Pershing (Apple, ETF VOO, caixa em dólar) e UBS (título em euro, caixa em euro).
  Depositou US$ 20 mil em 15/09 e comprou 30 cotas de VOO no dia seguinte.
- **Manoel:** só UBS (T-Note, título corporativo, Microsoft, caixa). Vendeu parte do T-Note
  em 14/09 e sacou US$ 60 mil em 15/09.

E quatro situações que o time de consolidação vive no dia a dia:

| Situação | O que o sistema faz |
|---|---|
| Pershing reenvia o arquivo de 30/09 | Hash repetido: **duplicado ignorado** |
| UBS manda o arquivo de 29/09 sem o campo `asOf` | Arquivo rejeitado e enviado para a **DLQ**; o reenvio correto é processado |
| Movimentação da venda do Manoel chega 2h depois da posição | Abre **quebra** de reconciliação, que se **resolve sozinha** quando o arquivo chega |
| Pershing informa 52 cotas de VOO em 22/09 (o certo é 50) | **Quebra aberta** para o backoffice investigar |

## Resultados de setembro/2026

| | Maria | Manoel |
|---|---|---|
| Patrimônio em 30/09 | US$ 113.994,25 | US$ 146.000,00 |
| TWR do mês | +2,64% | +0,62% |
| Conta ingênua (errada) | +24,73% | −28,64% |

## Análise geral com pandas

`app/analytics.py` transforma as posições diárias num painel pandas e calcula, para cada cliente
e para a casa como um todo:

| Pergunta | Como |
|---|---|
| Qual a posição de cada dia, se um custodiante atrasar? | `merge_asof` com o último arquivo de cada custodiante |
| Quanto rendeu? | retornos diários descontando fluxos, `(1 + r).prod() − 1` |
| Quanto oscila? | `std() × √252` (volatilidade anualizada) |
| Qual a pior queda? | `crescimento / crescimento.cummax() − 1` (drawdown) |
| O risco compensou? | índice de Sharpe, com taxa livre de risco de 4,5% a.a. |
| Depende de um ativo só? | HHI e número efetivo de ativos (`1 / HHI`) |
| E se o euro cair 10%? | exposição por moeda × choque |
| Quem puxou o resultado? | contribuição = peso de ontem × retorno do ativo hoje |

**Por que float aqui e Decimal no resto?** Saldo e extrato são contábeis: cada centavo tem que
bater. Métricas estatísticas não precisam disso, e o pandas é feito para trabalhar a carteira
inteira como tabela. Um teste confere que o TWR do pandas bate com o do domínio (diferença na
8ª casa decimal, por causa do arredondamento em centavos do domínio).

O notebook `notebooks/analise_geral.ipynb` mostra cada passo com tabelas e gráficos:

```bash
pip install -e ".[dev,notebook]"
jupyter lab notebooks/analise_geral.ipynb
```

## Testes

62 testes, em cinco níveis:

- **Domínio:** TWR, sub-períodos, reconciliação (sem banco nem rede)
- **Adapters e ingestão:** rodam em memória, SQLite e Postgres, e o resultado precisa ser igual
- **Análise (pandas):** TWR igual ao do domínio, contribuições somando o TWR, alocação somando 100%
- **API:** endpoints com o `TestClient` do FastAPI
- **AWS:** S3 → SQS → worker → DynamoDB → SNS com o `moto`, que simula a AWS dentro do teste

```bash
pytest                                                                   # memória + SQLite + AWS simulada
TEST_DATABASE_URL=postgresql+psycopg://offshore:offshore@localhost:5432/offshore pytest   # + Postgres
```

## Próximas etapas

1. GitHub Actions rodando lint e testes (com Postgres como serviço)
2. Migrações de banco com Alembic
3. Fila FIFO por conta de custodiante
