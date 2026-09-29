import type { AssetClass, FileStatus, TransactionType } from '../types'

const usd = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'USD' })
const usdCompact = new Intl.NumberFormat('pt-BR', {
  style: 'currency',
  currency: 'USD',
  notation: 'compact',
  maximumFractionDigits: 1,
})
const num = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 2 })

export const formatUsd = (v: number) => usd.format(v)
const brl = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' })
export const formatBrl = (v: number) => brl.format(v)
export const formatRate = (v: number) =>
  v.toLocaleString('pt-BR', { minimumFractionDigits: 4, maximumFractionDigits: 4 })
export const formatUsdCompact = (v: number) => usdCompact.format(v)
export const formatNumber = (v: number) => num.format(v)

export function formatPercent(v: number, digits = 2, withSign = true): string {
  const s = (v * 100).toLocaleString('pt-BR', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })
  return `${withSign && v > 0 ? '+' : ''}${s}%`
}

/** 2026-09-15 → 15/09/2026 (sem passar por Date para não sofrer com fuso horário) */
export function formatDate(iso: string): string {
  const [y, m, d] = iso.slice(0, 10).split('-')
  return `${d}/${m}/${y}`
}

export function formatDayMonth(iso: string): string {
  const [, m, d] = iso.slice(0, 10).split('-')
  return `${d}/${m}`
}

export function formatDateTime(iso: string): string {
  return `${formatDate(iso)} ${iso.slice(11, 16)}`
}

const MONTHS = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']
export function formatMonth(yyyyMm: string): string {
  const [y, m] = yyyyMm.split('-')
  return `${MONTHS[Number(m) - 1]}/${y.slice(2)}`
}

export const ASSET_CLASS_LABEL: Record<AssetClass, string> = {
  renda_variavel: 'Renda variável',
  renda_fixa: 'Renda fixa',
  caixa: 'Caixa',
}

export const TRANSACTION_LABEL: Record<TransactionType, string> = {
  deposito: 'Depósito',
  saque: 'Saque',
  compra: 'Compra',
  venda: 'Venda',
  dividendo: 'Dividendo',
  taxa: 'Taxa',
}

export const FILE_STATUS_LABEL: Record<FileStatus, string> = {
  processado: 'Processado',
  duplicado: 'Duplicado ignorado',
  erro_dlq: 'Erro · enviado à DLQ',
  processando: 'Processando',
}
