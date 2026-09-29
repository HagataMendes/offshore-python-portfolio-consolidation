import { useCallback } from 'react'
import { X } from 'lucide-react'
import { getPerformance, getPortfolio } from '../api/client'
import { CumulativeTwrChart, MonthlyReturnsChart } from '../components/charts/Charts'
import { Card, ErrorState, Explainer, Loading, StatCard } from '../components/ui'
import { useSelectedClient } from '../context/clientContext'
import { useApi } from '../hooks/useApi'
import { formatDayMonth, formatPercent, formatUsd } from '../lib/format'
import type { Performance, ValuationPoint } from '../types'

export function PerformancePage() {
  const { clientId } = useSelectedClient()
  const perf = useApi(useCallback(() => getPerformance(clientId), [clientId]))
  const portfolio = useApi(useCallback(() => getPortfolio(clientId), [clientId]))

  if (perf.status === 'loading' || portfolio.status === 'loading') return <Loading />
  if (perf.status === 'error') return <ErrorState message={perf.error} />
  if (portfolio.status === 'error') return <ErrorState message={portfolio.error} />

  const p = perf.data
  const history = portfolio.data.history

  return (
    <div className="grid grid-cols-1 gap-6">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard
          label="TWR em setembro"
          value={formatPercent(p.twr)}
          tone={p.twr >= 0 ? 'positive' : 'negative'}
          hint="O número certo"
        />
        <StatCard
          label="TWR no ano"
          value={formatPercent(p.ytd_twr)}
          tone={p.ytd_twr >= 0 ? 'positive' : 'negative'}
          hint="Meses encadeados, jan a set"
        />
        <StatCard
          label="Conta ingênua em setembro"
          value={formatPercent(p.naive_return)}
          tone="muted"
          hint="Errada: mistura depósitos e saques com rendimento"
        />
      </div>

      <TwrExplainer perf={p} history={history} />

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Rentabilidade mês a mês" subtitle="TWR de cada mês de 2026">
          <MonthlyReturnsChart monthly={p.monthly} />
        </Card>
        <Card title="TWR acumulado em setembro" subtitle="Compare com o gráfico do Painel: aqui não há salto no dia do fluxo">
          <CumulativeTwrChart history={history} />
        </Card>
      </div>
    </div>
  )
}

function TwrExplainer({ perf, history }: { perf: Performance; history: ValuationPoint[] }) {
  const start = history[0].value_usd
  const end = history[history.length - 1].value_usd
  const factors = perf.sub_periods.map((sp) => `(1 ${sp.return >= 0 ? '+' : '−'} ${formatPercent(Math.abs(sp.return), 2, false)})`)

  return (
    <Card title="Como o TWR foi calculado" subtitle={`Passo a passo com os números de ${perf.client.name}`}>
      <div className="grid gap-6 xl:grid-cols-[1fr_340px]">
        <div>
          <p className="mb-4 text-sm text-slate-600 dark:text-slate-300">
            1. O mês é cortado em pedaços sempre que entra ou sai dinheiro.
          </p>
          <div className="flex flex-col items-stretch gap-3 md:flex-row md:items-center">
            {perf.sub_periods.map((sp, i) => (
              <div key={sp.start} className="contents">
                {sp.flow_before_usd !== 0 && (
                  <div className="flex shrink-0 items-center justify-center">
                    <span className="rounded-full border border-dashed border-blue-400 px-3 py-1 text-xs font-medium text-blue-700 dark:border-blue-600 dark:text-blue-300">
                      {sp.flow_before_usd > 0 ? 'Depósito' : 'Saque'} de <span className="money">{formatUsd(Math.abs(sp.flow_before_usd))}</span>
                    </span>
                  </div>
                )}
                <div className="flex-1 rounded-xl border border-slate-200 p-4 dark:border-slate-800">
                  <p className="text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">Pedaço {i + 1}</p>
                  <p className="mt-0.5 text-sm text-slate-600 dark:text-slate-300">
                    {formatDayMonth(sp.start)} a {formatDayMonth(sp.end)}
                  </p>
                  <p className={`mt-2 text-xl font-semibold ${sp.return >= 0 ? 'text-emerald-700 dark:text-emerald-400' : 'text-red-700 dark:text-red-400'}`}>
                    {formatPercent(sp.return)}
                  </p>
                </div>
              </div>
            ))}
          </div>

          <p className="mb-2 mt-6 text-sm text-slate-600 dark:text-slate-300">2. Os retornos de cada pedaço são multiplicados.</p>
          <div className="overflow-x-auto rounded-xl bg-slate-50 px-4 py-3 font-mono text-sm dark:bg-slate-800/60">
            {factors.join(' × ')} − 1 ={' '}
            <strong className={perf.twr >= 0 ? 'text-emerald-700 dark:text-emerald-400' : 'text-red-700 dark:text-red-400'}>
              {formatPercent(perf.twr)}
            </strong>
          </div>

          <div className="mt-4 flex items-start gap-3 rounded-xl border border-red-200 bg-red-50/60 px-4 py-3 text-sm dark:border-red-900 dark:bg-red-950/30">
            <X className="mt-0.5 size-4 shrink-0 text-red-600 dark:text-red-400" aria-hidden />
            <div>
              <p className="font-medium text-red-900 dark:text-red-200">Conta ingênua (errada)</p>
              <p className="money mt-0.5 font-mono text-red-800 dark:text-red-300">
                {formatUsd(end)} ÷ {formatUsd(start)} − 1 = {formatPercent(perf.naive_return)}
              </p>
            </div>
          </div>
        </div>

        <Explainer title="Por que não fazer só final ÷ inicial?">
          <p>
            Porque parte da diferença entre o valor final e o inicial não é rendimento: é dinheiro que o próprio cliente
            {perf.naive_return > perf.twr ? ' colocou' : ' tirou'}. O TWR mede só a qualidade dos investimentos, e é o
            padrão de mercado (GIPS) para comparar gestores e carteiras.
          </p>
          <p className="mt-2">
            Na API Python, este mesmo cálculo fica no módulo de domínio e é coberto por testes automatizados.
          </p>
        </Explainer>
      </div>
    </Card>
  )
}
