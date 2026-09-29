// Camada de acesso à API.
// - Se VITE_API_URL estiver definida, chama a API Python (FastAPI) de verdade.
// - Se não estiver, responde com o snapshot gerado pelo próprio back-end (src/mocks).
// As telas não sabem de onde o dado vem: só chamam estas funções.

import { AS_OF, PERIOD_START, SNAPSHOT } from '../mocks/data'
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

const API_URL = import.meta.env.VITE_API_URL as string | undefined
export const isUsingMock = !API_URL

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`)
  if (!res.ok) throw new Error(`A API respondeu ${res.status} em ${path}`)
  return res.json() as Promise<T>
}

// Simula a latência de rede para os estados de carregamento aparecerem.
const delay = <T,>(value: T, ms = 250) => new Promise<T>((r) => setTimeout(() => r(value), ms))

export function getClients(): Promise<Client[]> {
  if (!isUsingMock) return get('/clients')
  return delay(SNAPSHOT.clients)
}

export function getPortfolio(id: ClientId): Promise<Portfolio> {
  if (!isUsingMock) return get(`/clients/${id}/positions?date=${AS_OF}`)
  return delay(SNAPSHOT.portfolio[id])
}

export function getStatement(id: ClientId): Promise<Statement> {
  if (!isUsingMock) return get(`/clients/${id}/statement?month=${AS_OF.slice(0, 7)}`)
  return delay(SNAPSHOT.statement[id])
}

export function getPerformance(id: ClientId): Promise<Performance> {
  if (!isUsingMock) return get(`/clients/${id}/performance?from=${PERIOD_START}&to=${AS_OF}`)
  return delay(SNAPSHOT.performance[id])
}

export function getIngestedFiles(): Promise<IngestedFile[]> {
  if (!isUsingMock) return get('/ingestion/files')
  return delay(SNAPSHOT.ingested_files)
}

export function getReconciliationBreaks(): Promise<ReconciliationBreak[]> {
  if (!isUsingMock) return get('/reconciliation/breaks')
  return delay(SNAPSHOT.reconciliation_breaks)
}

export function getAnalytics(): Promise<AnalyticsOverview> {
  if (!isUsingMock) return get(`/analytics/overview?from=${PERIOD_START}&to=${AS_OF}`)
  return delay(SNAPSHOT.analytics)
}
