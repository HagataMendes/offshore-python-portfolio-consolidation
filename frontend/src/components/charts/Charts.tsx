import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { formatDate, formatDayMonth, formatMonth, formatPercent, formatUsd, formatUsdCompact } from '../../lib/format'
import type { MonthlyReturn, ValuationPoint } from '../../types'

const axisProps = {
  tick: { fill: 'var(--chart-axis)', fontSize: 12 },
  axisLine: false,
  tickLine: false,
} as const

function TooltipBox({ title, rows }: { title: string; rows: { label: string; value: string }[] }) {
  return (
    <div className="min-w-44 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm shadow-lg dark:border-slate-700 dark:bg-slate-900">
      <p className="mb-1 font-medium text-slate-900 dark:text-slate-100">{title}</p>
      {rows.map((r) => (
        <p key={r.label} className="flex justify-between gap-4 text-slate-600 dark:text-slate-300">
          <span>{r.label}</span>
          <span className="font-medium text-slate-900 dark:text-slate-100">{r.value}</span>
        </p>
      ))}
    </div>
  )
}

/** Evolução do patrimônio: aqui depósitos e saques aparecem como "degraus". */
export function PortfolioValueChart({ history }: { history: ValuationPoint[] }) {
  const flows = history.filter((p) => p.external_flow_usd !== 0)
  const values = history.map((p) => p.value_usd)
  // Arredonda os limites do eixo para múltiplos de 10 mil (ou 5 mil), para os rótulos ficarem redondos.
  const range = Math.max(...values) - Math.min(...values)
  const step = range > 40_000 ? 10_000 : 5_000
  const yMin = Math.floor((Math.min(...values) - range * 0.1) / step) * step
  const yMax = Math.ceil((Math.max(...values) + range * 0.1) / step) * step

  return (
    <div className="money-axis h-72">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={history} margin={{ top: 24, right: 12, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id="valueFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--series-1)" stopOpacity={0.18} />
              <stop offset="100%" stopColor="var(--series-1)" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid vertical={false} stroke="var(--chart-grid)" />
          <XAxis dataKey="date" tickFormatter={formatDayMonth} minTickGap={24} {...axisProps} />
          <YAxis
            width={92}
            domain={[yMin, yMax]}
            ticks={Array.from({ length: (yMax - yMin) / step + 1 }, (_, i) => yMin + i * step).filter((_, i, a) => a.length <= 6 || i % 2 === 0)}
            tickFormatter={formatUsdCompact}
            {...axisProps}
          />
          {flows.map((f) => (
            <ReferenceLine
              key={f.date}
              x={f.date}
              stroke="var(--chart-axis)"
              strokeDasharray="4 4"
              label={{
                value: `${f.external_flow_usd > 0 ? 'Depósito' : 'Saque'} ${formatUsdCompact(Math.abs(f.external_flow_usd))}`,
                position: 'top',
                fill: 'var(--chart-axis)',
                fontSize: 12,
              }}
            />
          ))}
          <Tooltip
            cursor={{ stroke: 'var(--chart-axis)', strokeWidth: 1 }}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null
              const p = payload[0].payload as ValuationPoint
              const rows = [{ label: 'Patrimônio', value: formatUsd(p.value_usd) }]
              if (p.daily_return !== 0) rows.push({ label: 'Retorno do dia', value: formatPercent(p.daily_return) })
              if (p.external_flow_usd !== 0)
                rows.push({
                  label: p.external_flow_usd > 0 ? 'Depósito' : 'Saque',
                  value: formatUsd(p.external_flow_usd),
                })
              return <TooltipBox title={formatDate(p.date)} rows={rows} />
            }}
          />
          <Area
            type="monotone"
            dataKey="value_usd"
            stroke="var(--series-1)"
            strokeWidth={2}
            fill="url(#valueFill)"
            animationDuration={600}
            activeDot={{ r: 5, stroke: 'var(--chart-surface)', strokeWidth: 2 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}

/** TWR acumulado dia a dia: repare que ele NÃO dá salto no dia do depósito/saque. */
export function CumulativeTwrChart({ history }: { history: ValuationPoint[] }) {
  // Encadeia os retornos diários: (1 + r1) × (1 + r2) × ... − 1
  const data = history.map((p, i) => ({
    ...p,
    cumulative:
      history
        .slice(1, i + 1)
        .reduce((acc, cur, k) => acc * (cur.value_usd / (history[k].value_usd + cur.external_flow_usd)), 1) - 1,
  }))
  const flows = history.filter((p) => p.external_flow_usd !== 0)

  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 24, right: 12, bottom: 0, left: 0 }}>
          <CartesianGrid vertical={false} stroke="var(--chart-grid)" />
          <XAxis dataKey="date" tickFormatter={formatDayMonth} minTickGap={24} {...axisProps} />
          <YAxis width={56} tickFormatter={(v: number) => formatPercent(v, 1, false)} {...axisProps} />
          <ReferenceLine y={0} stroke="var(--chart-axis)" />
          {flows.map((f) => (
            <ReferenceLine
              key={f.date}
              x={f.date}
              stroke="var(--chart-axis)"
              strokeDasharray="4 4"
              label={{
                value: f.external_flow_usd > 0 ? 'Depósito' : 'Saque',
                position: 'top',
                fill: 'var(--chart-axis)',
                fontSize: 12,
              }}
            />
          ))}
          <Tooltip
            cursor={{ stroke: 'var(--chart-axis)', strokeWidth: 1 }}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null
              const p = payload[0].payload as (typeof data)[number]
              return <TooltipBox title={formatDate(p.date)} rows={[{ label: 'TWR acumulado', value: formatPercent(p.cumulative) }]} />
            }}
          />
          <Line
            type="monotone"
            dataKey="cumulative"
            stroke="var(--series-1)"
            strokeWidth={2}
            dot={false}
            animationDuration={600}
            activeDot={{ r: 5, stroke: 'var(--chart-surface)', strokeWidth: 2 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

/** Rentabilidade mês a mês: azul quando subiu, vermelho quando caiu. */
export function MonthlyReturnsChart({ monthly }: { monthly: MonthlyReturn[] }) {
  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={monthly} margin={{ top: 8, right: 12, bottom: 0, left: 0 }} barCategoryGap="28%">
          <CartesianGrid vertical={false} stroke="var(--chart-grid)" />
          <XAxis dataKey="month" tickFormatter={formatMonth} {...axisProps} />
          <YAxis width={56} tickFormatter={(v: number) => formatPercent(v, 1, false)} {...axisProps} />
          <ReferenceLine y={0} stroke="var(--chart-axis)" />
          <Tooltip
            cursor={{ fill: 'var(--chart-grid)', opacity: 0.5 }}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null
              const m = payload[0].payload as MonthlyReturn
              return <TooltipBox title={formatMonth(m.month)} rows={[{ label: 'TWR do mês', value: formatPercent(m.twr) }]} />
            }}
          />
          <Bar dataKey="twr" radius={[4, 4, 4, 4]} maxBarSize={36} animationDuration={600}>
            {monthly.map((m) => (
              <Cell key={m.month} fill={m.twr >= 0 ? 'var(--series-1)' : 'var(--negative)'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
