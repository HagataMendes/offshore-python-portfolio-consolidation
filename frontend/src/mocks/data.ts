// Dados usados quando a tela roda SEM a API (por exemplo, numa prévia estática).
// Não são inventados à mão: snapshot.json é gerado pelo back-end Python com
//   cd backend && python -m scripts.export_snapshot
// Então os números aqui são exatamente os que a API calcula.

import type {
  AnalyticsOverview,
  Client,
  ClientId,
  IngestedFile,
  Performance,
  Portfolio,
  ReconciliationBreak,
  Statement,
} from '../types'
import snapshot from './snapshot.json'

interface Snapshot {
  clients: Client[]
  portfolio: Record<ClientId, Portfolio>
  statement: Record<ClientId, Statement>
  performance: Record<ClientId, Performance>
  ingested_files: IngestedFile[]
  reconciliation_breaks: ReconciliationBreak[]
  analytics: AnalyticsOverview
}

export const SNAPSHOT = snapshot as unknown as Snapshot

export const AS_OF = SNAPSHOT.portfolio.maria.as_of
export const PERIOD_START = SNAPSHOT.performance.maria.period_start

export const CLIENTS = Object.fromEntries(SNAPSHOT.clients.map((c) => [c.id, c])) as Record<ClientId, Client>
