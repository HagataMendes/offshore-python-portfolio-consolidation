// Contratos de dados entre o front e a API Python (FastAPI).
// Os nomes seguem snake_case porque é assim que a API vai devolver o JSON.

export type ClientId = 'maria' | 'manoel'
export type Custodian = 'Pershing' | 'UBS'
export type Currency = 'USD' | 'EUR'
export type AssetClass = 'renda_variavel' | 'renda_fixa' | 'caixa'

export interface Client {
  id: ClientId
  name: string
  full_name: string
  account: string // número da conta offshore
  risk_profile: 'Conservador' | 'Moderado' | 'Arrojado'
  advisor: string
  base_currency: Currency
  custodians: Custodian[]
}

export interface Position {
  isin: string | null
  ticker: string | null
  name: string
  asset_class: AssetClass
  custodian: Custodian
  quantity: number
  price: number
  currency: Currency
  fx_rate: number // cotação para USD
  market_value_usd: number
}

export interface ValuationPoint {
  date: string // ISO: 2026-09-15
  value_usd: number
  daily_return: number // 0.0032 = +0,32%
  external_flow_usd: number // depósito (+) ou saque (-) no início do dia
}

export interface Portfolio {
  client: Client
  as_of: string
  total_usd: number
  positions: Position[]
  history: ValuationPoint[]
}

export type TransactionType =
  | 'deposito'
  | 'saque'
  | 'compra'
  | 'venda'
  | 'dividendo'
  | 'taxa'

export interface Transaction {
  id: string
  date: string
  custodian: Custodian
  type: TransactionType
  description: string
  amount_usd: number // efeito no caixa: positivo entra, negativo sai
  is_external_flow: boolean // depósito/saque mexem no TWR; compra/venda não
}

export interface Statement {
  client: Client
  period_start: string
  period_end: string
  opening_balance_usd: number
  deposits_usd: number
  withdrawals_usd: number
  investment_result_usd: number
  closing_balance_usd: number
  twr: number
  transactions: Transaction[]
}

export interface SubPeriod {
  start: string
  end: string
  return: number
  flow_before_usd: number
}

export interface MonthlyReturn {
  month: string // 2026-01
  twr: number
}

export interface Performance {
  client: Client
  period_start: string
  period_end: string
  twr: number
  naive_return: number
  sub_periods: SubPeriod[]
  monthly: MonthlyReturn[]
  ytd_twr: number
}

export type FileStatus = 'processado' | 'duplicado' | 'erro_dlq' | 'processando'

export interface IngestedFile {
  id: string
  file_name: string
  custodian: Custodian
  format: 'CSV' | 'JSON'
  received_at: string // ISO datetime
  status: FileStatus
  records: number
  duration_ms: number | null
  correlation_id: string
  error: string | null
}

export type BreakStatus = 'aberta' | 'resolvida'

export interface ReconciliationBreak {
  id: string
  date: string
  client_id: ClientId
  custodian: Custodian
  asset: string
  expected_quantity: number
  reported_quantity: number
  status: BreakStatus
  note: string
}

// --- Análise geral (calculada com pandas no back-end) ---

export interface AllocationItem {
  key: string
  label: string
  value_usd: number
  weight: number
}

export interface ClientAnalytics {
  client_id: ClientId
  name: string
  full_name: string
  risk_profile: string
  aum_usd: number
  net_flows_usd: number
  twr: number
  volatility_annual: number
  max_drawdown: number
  sharpe: number | null
  best_day: string
  best_day_return: number
  worst_day: string
  worst_day_return: number
  positive_days: number
  days: number
  top_position: string
  top_weight: number
  hhi: number
  effective_positions: number
  positions: number
  foreign_currency_weight: number
  shock: number
  shock_impact_usd: number
  shock_impact_pct: number
  by_asset_class: AllocationItem[]
  by_currency: AllocationItem[]
}

export interface AnalyticsOverview {
  as_of: string
  period_start: string
  total_aum_usd: number
  risk_free_annual: number
  clients: ClientAnalytics[]
  allocation: Record<'by_asset_class' | 'by_currency' | 'by_custodian', AllocationItem[]>
  contributions: Record<ClientId, { label: string; contribution: number }[]>
  drawdown: Record<ClientId, { date: string; twr_index: number; drawdown: number }[]>
}
