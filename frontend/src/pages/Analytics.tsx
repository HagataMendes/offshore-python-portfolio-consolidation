import { useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { getAnalytics } from '../api/client'
import { Card, ErrorState, Explainer, Loading, StatCard } from '../components/ui'
import { useApi } from '../hooks/useApi'
import { formatDate, formatDayMonth, formatNumber, formatPercent, formatUsd } from '../lib/format'
import type { AllocationItem, AnalyticsOverview, ClientAnalytics, ClientId } from '../types'

// Cor fixa por cliente (a mesma em todos os gráficos) e por grupo de alocação.
const CLIENT_COLOR: Record<ClientId, string> = { maria: 'var(--series-1)', manoel: 'var(--series-2)' }
const GROUP_COLORS = ['var(--series-1)', 'var(--series-2)', 'var(--series-3)']

const axisProps = { tick: { fill: 'var(--chart-axis)', fontSize: 12 }, axisLine: false, tickLine: false } as const
const pp = (v: number) => `${v > 0 ? '+' : ''}${(v * 100).toLocaleString('pt-BR', { maximumFractionDigits: 2, minimumFractionDigits: 2 })} p.p.`

export function AnalyticsPage() {
  const state = useApi(getAnalytics)
  if (state.status === 'loading') return <Loading />
  if (state.status === 'error') return <ErrorState message={state.error} />
  const a = state.data

  const foreign = a.allocation.by_currency.filter((c) => c.key !== 'USD').reduce((s, c) => s + c.weight, 0)
  const netFlows = a.clients.reduce((s, c) => s + c.net_flows_usd, 0)

  return (
    <div className="grid grid-cols-1 gap-6">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Patrimônio sob gestão" value={formatUsd(a.total_aum_usd)} hint={`${a.clients.length} clientes em 30/09`} />
        <StatCard
          label="Fluxo líquido no mês"
          value={formatUsd(netFlows)}
          tone={netFlows >= 0 ? 'positive' : 'negative'}
          hint="Depósitos menos saques"
        />
        <StatCard label="Exposição fora do dólar" value={formatPercent(foreign, 1, false)} hint="Ativos e caixa em euro" />
        <StatCard
          label="Maior custodiante"
          value={a.allocation.by_custodian[0].label}
          hint={`${formatPercent(a.allocation.by_custodian[0].weight, 1, false)} do patrimônio`}
        />
      </div>

      <Card title="Risco e retorno lado a lado" subtitle="Setembro de 2026, calculado com pandas a partir das posições diárias">
        <ComparisonTable clients={a.clients} riskFree={a.risk_free_annual} />
      </Card>

      <div className="grid gap-6 xl:grid-cols-2">
        <ContributionCard a={a} />
        <Card title="Distância do topo (drawdown)" subtitle="Quanto cada carteira estava abaixo do seu melhor momento no mês">
          <DrawdownChart a={a} />
        </Card>
      </div>

      <Card title="Alocação consolidada" subtitle="Todos os clientes somados, em 30/09/2026">
        <div className="grid gap-6 md:grid-cols-3">
          <SegmentBar title="Por classe de ativo" items={a.allocation.by_asset_class} />
          <SegmentBar title="Por moeda" items={a.allocation.by_currency} />
          <SegmentBar title="Por custodiante" items={a.allocation.by_custodian} />
        </div>
      </Card>

      <PandasExplainer />
    </div>
  )
}

// --- Comparativo ---------------------------------------------------------------------

function ComparisonTable({ clients, riskFree }: { clients: ClientAnalytics[]; riskFree: number }) {
  const rows: { label: string; hint?: string; value: (c: ClientAnalytics) => React.ReactNode }[] = [
    { label: 'Perfil', value: (c) => c.risk_profile },
    { label: 'Patrimônio', value: (c) => <span className="money">{formatUsd(c.aum_usd)}</span> },
    { label: 'Rentabilidade (TWR)', value: (c) => <Signed v={c.twr} /> },
    { label: 'Volatilidade anualizada', hint: 'Quanto a carteira oscila', value: (c) => formatPercent(c.volatility_annual, 2, false) },
    { label: 'Maior queda (drawdown)', hint: 'Pior distância do topo', value: (c) => <Signed v={c.max_drawdown} /> },
    {
      label: 'Índice de Sharpe',
      hint: 'Retorno acima da taxa livre de risco por unidade de risco',
      value: (c) => (c.sharpe === null ? '—' : formatNumber(Number(c.sharpe.toFixed(2)))),
    },
    { label: 'Melhor dia', value: (c) => <DayCell day={c.best_day} v={c.best_day_return} /> },
    { label: 'Pior dia', value: (c) => <DayCell day={c.worst_day} v={c.worst_day_return} /> },
    { label: 'Dias positivos', value: (c) => `${c.positive_days} de ${c.days}` },
    {
      label: 'Maior posição',
      value: (c) => (
        <span>
          {c.top_position} <span className="text-slate-500 dark:text-slate-400">· {formatPercent(c.top_weight, 1, false)}</span>
        </span>
      ),
    },
    {
      label: 'Número efetivo de ativos',
      hint: 'Diversificação real (1 ÷ HHI)',
      value: (c) => `${formatNumber(Number(c.effective_positions.toFixed(1)))} de ${c.positions}`,
    },
    { label: 'Exposição a moeda estrangeira', value: (c) => formatPercent(c.foreign_currency_weight, 1, false) },
    {
      label: 'Se o euro cair 10%',
      hint: 'Impacto no patrimônio',
      value: (c) =>
        c.shock_impact_usd === 0 ? (
          <span className="text-slate-500 dark:text-slate-400">Sem impacto</span>
        ) : (
          <span className="text-red-700 dark:text-red-400">
            <span className="money">{formatUsd(c.shock_impact_usd)}</span> ({formatPercent(c.shock_impact_pct, 1, true)})
          </span>
        ),
    },
  ]

  return (
    <>
      <div className="-mx-5 overflow-x-auto">
        <table className="w-full min-w-[560px] text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-left dark:border-slate-800">
              <th className="px-5 py-2 text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">Métrica</th>
              {clients.map((c) => (
                <th key={c.client_id} className="px-5 py-2 text-right font-medium">
                  <span className="inline-flex items-center gap-2">
                    <span aria-hidden className="size-2.5 rounded-full" style={{ background: CLIENT_COLOR[c.client_id] }} />
                    {c.full_name}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.label} className="border-b border-slate-100 last:border-0 dark:border-slate-800/70">
                <td className="px-5 py-2.5">
                  <p>{r.label}</p>
                  {r.hint && <p className="text-xs text-slate-500 dark:text-slate-400">{r.hint}</p>}
                </td>
                {clients.map((c) => (
                  <td key={c.client_id} className="px-5 py-2.5 text-right tabular-nums">
                    {r.value(c)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-4 text-xs leading-relaxed text-slate-500 dark:text-slate-400">
        Volatilidade e Sharpe foram anualizados a partir de 21 dias úteis, com taxa livre de risco de{' '}
        {formatPercent(riskFree, 1, false)} ao ano: servem como ilustração, não como medida definitiva. O pior dia da Maria
        (23/09) vem da correção das 2 cotas de VOO que a Pershing informou a mais em 22/09, a quebra de reconciliação que
        segue aberta em Operações.
      </p>
    </>
  )
}

function Signed({ v }: { v: number }) {
  return <span className={v >= 0 ? 'text-emerald-700 dark:text-emerald-400' : 'text-red-700 dark:text-red-400'}>{formatPercent(v)}</span>
}

function DayCell({ day, v }: { day: string; v: number }) {
  return (
    <span>
      <Signed v={v} /> <span className="text-slate-500 dark:text-slate-400">em {formatDate(day).slice(0, 5)}</span>
    </span>
  )
}

// --- Contribuição por ativo ----------------------------------------------------------------

function ContributionCard({ a }: { a: AnalyticsOverview }) {
  const [clientId, setClientId] = useState<ClientId>('maria')
  const data = a.contributions[clientId]
  const twr = a.clients.find((c) => c.client_id === clientId)!.twr

  return (
    <Card
      title="De onde veio o resultado"
      subtitle={`Contribuição de cada ativo para os ${formatPercent(twr)} do mês`}
      action={
        <div role="radiogroup" aria-label="Cliente" className="inline-flex rounded-lg border border-slate-200 bg-slate-100 p-0.5 dark:border-slate-700 dark:bg-slate-800">
          {a.clients.map((c) => (
            <button
              key={c.client_id}
              role="radio"
              aria-checked={c.client_id === clientId}
              onClick={() => setClientId(c.client_id)}
              className={[
                'rounded-md px-3 py-1 text-sm font-medium',
                c.client_id === clientId ? 'bg-navy-900 text-white dark:bg-navy-700' : 'text-slate-600 dark:text-slate-300',
              ].join(' ')}
            >
              {c.name}
            </button>
          ))}
        </div>
      }
    >
      <div style={{ height: 56 + data.length * 44 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ top: 4, right: 104, bottom: 4, left: 0 }}>
            <CartesianGrid horizontal={false} stroke="var(--chart-grid)" />
            <XAxis type="number" tickFormatter={(v: number) => formatPercent(v, 1, false)} {...axisProps} />
            <YAxis type="category" dataKey="label" width={136} {...axisProps} />
            <ReferenceLine x={0} stroke="var(--chart-axis)" />
            <Tooltip
              cursor={{ fill: 'var(--chart-grid)', opacity: 0.5 }}
              formatter={(v) => [pp(Number(v)), 'Contribuição']}
              contentStyle={{ borderRadius: 8, fontSize: 13 }}
            />
            <Bar dataKey="contribution" radius={4} maxBarSize={22}>
              {data.map((d) => (
                <Cell
                  key={d.label}
                  fill={d.label === 'Outros efeitos' ? 'var(--chart-axis)' : d.contribution >= 0 ? 'var(--series-1)' : 'var(--negative)'}
                />
              ))}
              <LabelList dataKey="contribution" position="right" formatter={(v) => pp(Number(v))} style={{ fill: 'var(--chart-axis)', fontSize: 12 }} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
        Contribuição = peso do ativo no dia anterior × retorno do ativo no dia, somado no mês. "Outros efeitos" junta
        dividendos, taxas e o efeito dos juros compostos, e fecha a conta exata do TWR.
      </p>
    </Card>
  )
}

// --- Drawdown --------------------------------------------------------------------------

function DrawdownChart({ a }: { a: AnalyticsOverview }) {
  const ids = a.clients.map((c) => c.client_id)
  const dates = a.drawdown[ids[0]].map((p) => p.date)
  const data = dates.map((date, i) => ({ date, ...Object.fromEntries(ids.map((id) => [id, a.drawdown[id][i]?.drawdown ?? null])) }))

  return (
    <>
      <div className="mb-2 flex gap-4 text-sm">
        {a.clients.map((c) => (
          <span key={c.client_id} className="inline-flex items-center gap-2">
            <span aria-hidden className="h-0.5 w-4 rounded" style={{ background: CLIENT_COLOR[c.client_id] }} />
            {c.name} <span className="text-slate-500 dark:text-slate-400">· pior {formatPercent(c.max_drawdown)}</span>
          </span>
        ))}
      </div>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
            <CartesianGrid vertical={false} stroke="var(--chart-grid)" />
            <XAxis dataKey="date" tickFormatter={formatDayMonth} minTickGap={24} {...axisProps} />
            <YAxis width={56} tickFormatter={(v: number) => formatPercent(v, 1, false)} {...axisProps} />
            <ReferenceLine y={0} stroke="var(--chart-axis)" />
            <Tooltip
              cursor={{ stroke: 'var(--chart-axis)', strokeWidth: 1 }}
              labelFormatter={(d) => formatDate(String(d))}
              formatter={(v, name) => [formatPercent(Number(v)), a.clients.find((c) => c.client_id === name)?.name ?? name]}
              contentStyle={{ borderRadius: 8, fontSize: 13 }}
            />
            {ids.map((id) => (
              <Line key={id} type="linear" dataKey={id} stroke={CLIENT_COLOR[id]} strokeWidth={2} dot={false} animationDuration={600} />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </>
  )
}

// --- Alocação --------------------------------------------------------------------------

function SegmentBar({ title, items }: { title: string; items: AllocationItem[] }) {
  return (
    <div>
      <p className="mb-3 text-sm font-medium">{title}</p>
      <div className="flex h-3 gap-0.5 overflow-hidden rounded-full" role="img" aria-label={title}>
        {items.map((it, i) => (
          <div key={it.key} style={{ width: `${it.weight * 100}%`, background: GROUP_COLORS[i % GROUP_COLORS.length] }} />
        ))}
      </div>
      <ul className="mt-4 grid gap-2">
        {items.map((it, i) => (
          <li key={it.key} className="flex items-center justify-between gap-3 text-sm">
            <span className="flex items-center gap-2">
              <span aria-hidden className="size-2.5 rounded-full" style={{ background: GROUP_COLORS[i % GROUP_COLORS.length] }} />
              {it.label}
            </span>
            <span className="flex items-baseline gap-3 tabular-nums">
              <span className="money">{formatUsd(it.value_usd)}</span>
              <span className="w-12 text-right text-slate-500 dark:text-slate-400">{formatPercent(it.weight, 1, false)}</span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}

// --- Como foi feito ------------------------------------------------------------------------

function PandasExplainer() {
  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
      <Card title="Como a análise é feita" subtitle="app/analytics.py, no back-end Python">
        <pre className="overflow-x-auto rounded-lg bg-navy-950 p-4 text-[13px] leading-relaxed text-navy-200">
          <code>{`# posição de cada dia: o arquivo mais recente de cada custodiante
panel = pd.merge_asof(calendario, arquivos, left_on="day",
                      right_on="file_date", by=["client_id", "custodian"])

# valor diário e retorno descontando depósitos e saques
valores = panel.groupby(["client_id", "day"])["value_usd"].sum()
df["ret"] = df["value_usd"] / (anterior + df["flow_usd"]) - 1

# risco
vol = df["ret"].std() * np.sqrt(252)
crescimento = (1 + df["ret"]).cumprod()
drawdown = crescimento / crescimento.cummax() - 1`}</code>
        </pre>
      </Card>
      <Explainer title="Por que pandas aqui, e Decimal no resto?">
        <p>
          O extrato e o saldo são contábeis: cada centavo precisa bater, então usam Decimal. Aqui o objetivo é estatístico
          (volatilidade, correlação, concentração), e o pandas trabalha com a carteira inteira como uma tabela.
        </p>
        <p className="mt-2">
          Um teste automático confere que o TWR calculado pelo pandas bate com o do domínio até a sétima casa decimal.
        </p>
      </Explainer>
    </div>
  )
}
