import { useCallback } from 'react'
import { useOutletContext } from 'react-router-dom'
import type { LayoutContext } from '../components/Layout'
import { getPerformance, getPortfolio } from '../api/client'
import { PortfolioValueChart } from '../components/charts/Charts'
import { Badge, Card, ErrorState, Loading } from '../components/ui'
import { useSelectedClient } from '../context/clientContext'
import { useApi } from '../hooks/useApi'
import { ASSET_CLASS_LABEL, formatBrl, formatNumber, formatPercent, formatRate, formatUsd } from '../lib/format'
import type { AssetClass, Custodian, Position } from '../types'

const CLASS_COLOR: Record<AssetClass, string> = {
  renda_variavel: 'bg-series-1',
  renda_fixa: 'bg-series-2',
  caixa: 'bg-series-3',
}

export function Dashboard() {
  const { clientId } = useSelectedClient()
  const { usdBrl } = useOutletContext<LayoutContext>()
  const portfolio = useApi(useCallback(() => getPortfolio(clientId), [clientId]))
  const performance = useApi(useCallback(() => getPerformance(clientId), [clientId]))

  if (portfolio.status === 'loading' || performance.status === 'loading') return <Loading />
  if (portfolio.status === 'error') return <ErrorState message={portfolio.error} />
  if (performance.status === 'error') return <ErrorState message={performance.error} />

  const p = portfolio.data
  const perf = performance.data
  const netFlow = p.history.reduce((s, h) => s + h.external_flow_usd, 0)
  const flowCount = p.history.filter((h) => h.external_flow_usd !== 0).length

  return (
    <div className="grid grid-cols-1 gap-6">
      <section className="overflow-hidden rounded-xl bg-navy-900 text-white">
        <div className="grid gap-6 p-6 sm:p-8 xl:grid-cols-[1.3fr_2fr] xl:items-end">
          <div className="min-w-0">
            <p className="text-xs font-medium uppercase tracking-[0.16em] text-brass-light">Patrimônio consolidado</p>
            <p className="money mt-3 font-display text-4xl font-semibold tracking-tight tabular-nums sm:text-5xl">
              {formatUsd(p.total_usd)}
            </p>
            {usdBrl && (
              <p className="mt-2 text-sm text-navy-200">
                <span className="money tabular-nums">≈ {formatBrl(p.total_usd * usdBrl.rate)}</span>
                <span className="text-navy-300"> · dólar a R$ {formatRate(usdBrl.rate)}</span>
              </p>
            )}
          </div>
          <dl className="grid grid-cols-1 gap-4 sm:grid-cols-3 sm:gap-0 sm:divide-x sm:divide-navy-700">
            <HeroMetric label="Rentabilidade no mês" value={formatPercent(perf.twr)} tone={perf.twr >= 0 ? 'up' : 'down'} note="Setembro · método TWR" />
            <HeroMetric label="Rentabilidade no ano" value={formatPercent(perf.ytd_twr)} tone={perf.ytd_twr >= 0 ? 'up' : 'down'} note="Jan a set/2026" />
            <HeroMetric
              label={netFlow >= 0 ? 'Aportes no mês' : 'Retiradas no mês'}
              value={formatUsd(Math.abs(netFlow))}
              sensitive
              note={`${flowCount} ${netFlow >= 0 ? 'depósito' : 'saque'}${flowCount === 1 ? '' : 's'} em setembro`}
            />
          </dl>
        </div>
        <div className="flex flex-wrap gap-x-6 gap-y-1 border-t border-navy-700 bg-navy-950/40 px-6 py-3 text-xs text-navy-300 sm:px-8">
          <span>Custodiantes: <span className="text-navy-200">{p.client.custodians.join(' · ')}</span></span>
          <span>Moeda base: <span className="text-navy-200">{p.client.base_currency}</span></span>
          <span>Fechamento: <span className="text-navy-200">30/09/2026</span></span>
        </div>
      </section>

      <Card
        title="Evolução do patrimônio"
        subtitle="Setembro de 2026. A linha tracejada marca o dia em que entrou ou saiu dinheiro."
      >
        <PortfolioValueChart history={p.history} />
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Por classe de ativo">
          <AllocationByClass positions={p.positions} total={p.total_usd} />
        </Card>
        <Card title="Por custodiante" subtitle="Onde o dinheiro está guardado">
          <AllocationByCustodian positions={p.positions} total={p.total_usd} />
        </Card>
      </div>

      <Card title="Posição consolidada" subtitle={`${p.positions.length} ativos em ${p.client.custodians.length} custodiante(s)`}>
        <PositionsTable positions={p.positions} total={p.total_usd} />
      </Card>
    </div>
  )
}

function HeroMetric({
  label,
  value,
  note,
  tone,
  sensitive = false,
}: {
  label: string
  value: string
  note: string
  tone?: 'up' | 'down'
  sensitive?: boolean
}) {
  const color = tone === 'up' ? 'text-emerald-300' : tone === 'down' ? 'text-red-300' : 'text-white'
  return (
    <div className="sm:px-6 sm:first:pl-0 sm:last:pr-0 xl:first:pl-6">
      <dt className="text-xs text-navy-300">{label}</dt>
      <dd className={`mt-1 text-2xl font-semibold tabular-nums ${color} ${sensitive ? 'money' : ''}`}>{value}</dd>
      <dd className="mt-0.5 text-xs text-navy-300">{note}</dd>
    </div>
  )
}

function groupBy<K extends string>(positions: Position[], key: (p: Position) => K) {
  const map = new Map<K, number>()
  for (const p of positions) map.set(key(p), (map.get(key(p)) ?? 0) + p.market_value_usd)
  return [...map.entries()].sort((a, b) => b[1] - a[1])
}

function AllocationByClass({ positions, total }: { positions: Position[]; total: number }) {
  const groups = groupBy<AssetClass>(positions, (p) => p.asset_class)
  return (
    <div>
      <div className="flex h-3 gap-0.5 overflow-hidden rounded-full" role="img" aria-label="Distribuição por classe de ativo">
        {groups.map(([cls, value]) => (
          <div key={cls} className={`${CLASS_COLOR[cls]} first:rounded-l-full last:rounded-r-full`} style={{ width: `${(value / total) * 100}%` }} />
        ))}
      </div>
      <ul className="mt-5 grid gap-3">
        {groups.map(([cls, value]) => (
          <li key={cls} className="flex items-center justify-between gap-3 text-sm">
            <span className="flex items-center gap-2">
              <span aria-hidden className={`size-2.5 rounded-full ${CLASS_COLOR[cls]}`} />
              {ASSET_CLASS_LABEL[cls]}
            </span>
            <span className="flex items-baseline gap-3">
              <span className="money font-medium">{formatUsd(value)}</span>
              <span className="w-14 text-right text-slate-500 dark:text-slate-400">{formatPercent(value / total, 1, false)}</span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}

function AllocationByCustodian({ positions, total }: { positions: Position[]; total: number }) {
  const groups = groupBy<Custodian>(positions, (p) => p.custodian)
  return (
    <ul className="grid gap-4">
      {groups.map(([custodian, value]) => (
        <li key={custodian}>
          <div className="mb-1.5 flex items-baseline justify-between text-sm">
            <span className="font-medium">{custodian}</span>
            <span>
              <span className="money">{formatUsd(value)}</span>{' '}
              <span className="ml-2 text-slate-500 dark:text-slate-400">{formatPercent(value / total, 1, false)}</span>
            </span>
          </div>
          <div className="h-2 rounded-full bg-slate-100 dark:bg-slate-800">
            <div className="h-2 rounded-full bg-series-1" style={{ width: `${(value / total) * 100}%` }} />
          </div>
        </li>
      ))}
    </ul>
  )
}

function PositionsTable({ positions, total }: { positions: Position[]; total: number }) {
  const sorted = [...positions].sort((a, b) => b.market_value_usd - a.market_value_usd)
  return (
    <div className="-mx-5 overflow-x-auto">
      <table className="w-full min-w-[720px] text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500 dark:border-slate-800 dark:text-slate-400">
            <th className="px-5 py-2 font-medium">Ativo</th>
            <th className="px-3 py-2 font-medium">Custodiante</th>
            <th className="px-3 py-2 text-right font-medium">Quantidade</th>
            <th className="px-3 py-2 text-right font-medium">Preço</th>
            <th className="px-3 py-2 text-right font-medium">Valor (US$)</th>
            <th className="px-5 py-2 text-right font-medium">% carteira</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((p) => (
            <tr key={`${p.custodian}-${p.name}`} className="border-b border-slate-100 last:border-0 dark:border-slate-800/70">
              <td className="px-5 py-3">
                <p className="font-medium">{p.name}</p>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  {[p.ticker, p.isin, ASSET_CLASS_LABEL[p.asset_class]].filter(Boolean).join(' · ')}
                </p>
              </td>
              <td className="px-3 py-3">
                <Badge>{p.custodian}</Badge>
              </td>
              <td className="money px-3 py-3 text-right">{formatNumber(p.quantity)}</td>
              <td className="px-3 py-3 text-right text-slate-600 dark:text-slate-300">
                {p.asset_class === 'caixa' ? '—' : p.asset_class === 'renda_fixa' ? `${formatNumber(p.price)}%` : formatNumber(p.price)}
                {p.asset_class !== 'caixa' && <span className="ml-1 text-xs text-slate-400">{p.currency}</span>}
                {p.currency !== 'USD' && (
                  <p className="text-xs text-slate-400">câmbio {p.fx_rate.toLocaleString('pt-BR', { minimumFractionDigits: 4 })}</p>
                )}
              </td>
              <td className="money px-3 py-3 text-right font-medium">{formatUsd(p.market_value_usd)}</td>
              <td className="px-5 py-3 text-right text-slate-500 dark:text-slate-400">{formatPercent(p.market_value_usd / total, 1, false)}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className="border-t border-slate-200 dark:border-slate-800">
            <td className="px-5 py-3 font-semibold" colSpan={4}>
              Total consolidado
            </td>
            <td className="money px-3 py-3 text-right font-semibold">{formatUsd(total)}</td>
            <td className="px-5 py-3 text-right text-slate-500 dark:text-slate-400">100%</td>
          </tr>
        </tfoot>
      </table>
    </div>
  )
}
