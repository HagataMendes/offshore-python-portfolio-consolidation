import { useCallback } from 'react'
import { ArrowDownLeft, ArrowUpRight, Printer } from 'lucide-react'
import { getStatement } from '../api/client'
import { Badge, Card, ErrorState, Explainer, Loading, type BadgeTone } from '../components/ui'
import { useSelectedClient } from '../context/clientContext'
import { useApi } from '../hooks/useApi'
import { formatDate, formatPercent, formatUsd, TRANSACTION_LABEL } from '../lib/format'
import type { TransactionType } from '../types'

const TYPE_TONE: Record<TransactionType, BadgeTone> = {
  deposito: 'blue',
  saque: 'blue',
  compra: 'neutral',
  venda: 'neutral',
  dividendo: 'green',
  taxa: 'amber',
}

export function StatementPage() {
  const { clientId } = useSelectedClient()
  const state = useApi(useCallback(() => getStatement(clientId), [clientId]))

  if (state.status === 'loading') return <Loading />
  if (state.status === 'error') return <ErrorState message={state.error} />
  const s = state.data

  const steps = [
    { label: 'Saldo inicial', hint: formatDate(s.period_start), value: s.opening_balance_usd, sign: '' },
    { label: 'Depósitos', hint: 'dinheiro que o cliente colocou', value: s.deposits_usd, sign: '+' },
    { label: 'Saques', hint: 'dinheiro que o cliente retirou', value: s.withdrawals_usd, sign: '−' },
    { label: 'Resultado dos investimentos', hint: 'ganho ou perda do mercado', value: s.investment_result_usd, sign: '±' },
  ]

  return (
    <div className="grid grid-cols-1 gap-6">
      <Card
        title={`Setembro de 2026 · ${s.client.full_name}`}
        subtitle={`De ${formatDate(s.period_start)} a ${formatDate(s.period_end)} · ${s.client.custodians.join(' + ')}`}
        action={
          <button
            onClick={() => window.print()}
            className="no-print inline-flex items-center gap-2 rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-800"
          >
            <Printer className="size-4" aria-hidden />
            Exportar PDF
          </button>
        }
      >
        <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
          <ol className="divide-y divide-slate-100 rounded-xl border border-slate-200 dark:divide-slate-800 dark:border-slate-800">
            {steps.map((step) => (
              <li key={step.label} className="flex items-center justify-between gap-4 px-4 py-3">
                <div>
                  <p className="text-sm font-medium">
                    {step.sign && <span className="mr-2 inline-block w-3 text-slate-400">{step.sign === '±' ? (step.value >= 0 ? '+' : '−') : step.sign}</span>}
                    {step.label}
                  </p>
                  <p className="text-xs text-slate-500 dark:text-slate-400">{step.hint}</p>
                </div>
                <p className="money font-medium tabular-nums">{formatUsd(Math.abs(step.value))}</p>
              </li>
            ))}
            <li className="flex items-center justify-between gap-4 bg-slate-50 px-4 py-4 dark:bg-slate-800/50">
              <div>
                <p className="font-semibold">
                  <span className="mr-2 inline-block w-3 text-slate-400">=</span>Saldo final
                </p>
                <p className="text-xs text-slate-500 dark:text-slate-400">{formatDate(s.period_end)}</p>
              </div>
              <p className="money font-display text-xl font-semibold tabular-nums">{formatUsd(s.closing_balance_usd)}</p>
            </li>
          </ol>

          <div className="grid content-start gap-4">
            <div className="rounded-xl border border-slate-200 p-4 dark:border-slate-800">
              <p className="text-sm text-slate-500 dark:text-slate-400">Rentabilidade do mês (TWR)</p>
              <p className={`mt-1 text-2xl font-semibold ${s.twr >= 0 ? 'text-emerald-700 dark:text-emerald-400' : 'text-red-700 dark:text-red-400'}`}>
                {formatPercent(s.twr)}
              </p>
            </div>
            <Explainer title="Como ler este extrato">
              O saldo final é o saldo inicial, mais o que o cliente depositou, menos o que ele sacou, mais o que os
              investimentos renderam. Compras e vendas não mudam o total: só trocam caixa por ativo.
            </Explainer>
          </div>
        </div>
      </Card>

      <Card title="Movimentações" subtitle={`${s.transactions.length} lançamentos no período`}>
        <div className="-mx-5 overflow-x-auto">
          <table className="w-full min-w-[680px] text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500 dark:border-slate-800 dark:text-slate-400">
                <th className="px-5 py-2 font-medium">Data</th>
                <th className="px-3 py-2 font-medium">Tipo</th>
                <th className="px-3 py-2 font-medium">Descrição</th>
                <th className="px-3 py-2 font-medium">Custodiante</th>
                <th className="px-5 py-2 text-right font-medium">Valor (US$)</th>
              </tr>
            </thead>
            <tbody>
              {s.transactions.map((t) => (
                <tr key={t.id} className="border-b border-slate-100 last:border-0 dark:border-slate-800/70">
                  <td className="whitespace-nowrap px-5 py-3 text-slate-600 dark:text-slate-300">{formatDate(t.date)}</td>
                  <td className="px-3 py-3">
                    <Badge tone={TYPE_TONE[t.type]}>{TRANSACTION_LABEL[t.type]}</Badge>
                  </td>
                  <td className="px-3 py-3">
                    <p>{t.description}</p>
                    {t.is_external_flow && (
                      <p className="mt-0.5 text-xs text-blue-700 dark:text-blue-300">Fluxo externo: o TWR corta o período aqui</p>
                    )}
                  </td>
                  <td className="px-3 py-3 text-slate-600 dark:text-slate-300">{t.custodian}</td>
                  <td className="whitespace-nowrap px-5 py-3 text-right font-medium">
                    <span className="money inline-flex items-center gap-1">
                      {t.amount_usd >= 0 ? (
                        <ArrowDownLeft className="size-3.5 text-emerald-600 dark:text-emerald-400" aria-label="entrada" />
                      ) : (
                        <ArrowUpRight className="size-3.5 text-red-600 dark:text-red-400" aria-label="saída" />
                      )}
                      {formatUsd(t.amount_usd)}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}
