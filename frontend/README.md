# Frontend: painel da carteira offshore

Interface em **React + TypeScript + Tailwind CSS** que consome a API Python do projeto.
Mostra a carteira consolidada de dois clientes fictícios, **Maria** (Pershing + UBS) e **Manoel** (UBS).

## Telas

| Tela | O que mostra |
|---|---|
| Painel | Patrimônio total, rentabilidade, evolução no mês, alocação por classe e por custodiante, posições |
| Extrato | Saldo inicial → depósitos → saques → resultado → saldo final, e todas as movimentações |
| Rentabilidade | Passo a passo do cálculo TWR, rentabilidade mês a mês e TWR acumulado |
| Análise geral | Comparativo de risco entre clientes, contribuição por ativo, drawdown e alocação consolidada (calculados com pandas) |
| Operações | Log de arquivos recebidos (processado, duplicado, DLQ) e quebras de reconciliação |

## Como rodar

```bash
cd frontend
npm install
npm run dev      # abre em http://localhost:5173
npm test         # testes do cálculo de TWR (Vitest)
npm run build    # checa os tipos e gera a versão de produção em dist/
```

## De onde vêm os dados

Os números são calculados pelo back-end Python (`../backend`).

- **Com a API rodando:** crie `frontend/.env.local` com `VITE_API_URL=http://localhost:8000`.
- **Sem a API:** a tela usa `src/mocks/snapshot.json`, uma cópia das respostas da API gerada por
  `cd backend && python -m scripts.export_snapshot`. Serve para prévias estáticas (GitHub Pages).

As telas não mudam: todas chamam as funções de `src/api/client.ts`, que decidem de onde buscar.

## Organização

```
src/
├── api/client.ts        # única porta de saída para a API
├── types.ts             # contratos de dados (espelham os schemas da API)
├── lib/performance.ts   # TWR em TypeScript (testado contra o resultado do Python)
├── mocks/               # snapshot das respostas da API Python
├── components/          # peças reutilizáveis e gráficos (Recharts)
└── pages/               # Painel, Extrato, Rentabilidade, Operações
```
