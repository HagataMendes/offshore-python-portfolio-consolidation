import { AlertTriangle, CheckCircle2, ChevronRight, Copy, Database, FolderInput, Inbox, Loader2, Megaphone, Cpu, XCircle } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { getIngestedFiles, getReconciliationBreaks } from '../api/client'
import { Badge, Card, ErrorState, Explainer, Loading, StatCard, type BadgeTone } from '../components/ui'
import { useApi } from '../hooks/useApi'
import { FILE_STATUS_LABEL, formatDate, formatDateTime, formatNumber } from '../lib/format'
import { CLIENTS } from '../mocks/data'
import type { FileStatus } from '../types'

const STATUS_STYLE: Record<FileStatus, { tone: BadgeTone; icon: ReactNode }> = {
  processado: { tone: 'green', icon: <CheckCircle2 className="size-3.5" aria-hidden /> },
  duplicado: { tone: 'amber', icon: <Copy className="size-3.5" aria-hidden /> },
  erro_dlq: { tone: 'red', icon: <XCircle className="size-3.5" aria-hidden /> },
  processando: { tone: 'blue', icon: <Loader2 className="size-3.5 animate-spin" aria-hidden /> },
}

export function Operations() {
  const files = useApi(getIngestedFiles)
  const [showAll, setShowAll] = useState(false)
  const breaks = useApi(getReconciliationBreaks)

  if (files.status === 'loading' || breaks.status === 'loading') return <Loading />
  if (files.status === 'error') return <ErrorState message={files.error} />
  if (breaks.status === 'error') return <ErrorState message={breaks.error} />

  const count = (s: FileStatus) => files.data.filter((f) => f.status === s).length
  const openBreaks = breaks.data.filter((b) => b.status === 'aberta').length

  return (
    <div className="grid grid-cols-1 gap-6">
      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <StatCard label="Arquivos processados" value={String(count('processado'))} hint={`de ${files.data.length} recebidos`} />
        <StatCard label="Duplicados ignorados" value={String(count('duplicado'))} hint="Barrados pela idempotência" />
        <StatCard label="Mensagens na DLQ" value={String(count('erro_dlq'))} tone={count('erro_dlq') ? 'negative' : 'default'} hint="Precisam de análise" />
        <StatCard label="Quebras abertas" value={String(openBreaks)} tone={openBreaks ? 'negative' : 'default'} hint="Reconciliação de posições" />
      </div>

      <Card title="Caminho de um arquivo" subtitle="Da chegada do custodiante até a API">
        <Pipeline />
      </Card>

      <Card title="Arquivos recebidos" subtitle="Log da ingestão, do mais recente para o mais antigo">
        <div className="-mx-5 overflow-x-auto">
          <table className="w-full min-w-[820px] text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500 dark:border-slate-800 dark:text-slate-400">
                <th className="px-5 py-2 font-medium">Arquivo</th>
                <th className="px-3 py-2 font-medium">Recebido em</th>
                <th className="px-3 py-2 font-medium">Status</th>
                <th className="px-3 py-2 text-right font-medium">Registros</th>
                <th className="px-3 py-2 text-right font-medium">Tempo</th>
                <th className="px-5 py-2 font-medium">Correlation ID</th>
              </tr>
            </thead>
            <tbody>
              {(showAll ? files.data : files.data.slice(0, 10)).map((f) => (
                <tr key={f.id} className="border-b border-slate-100 align-top last:border-0 dark:border-slate-800/70">
                  <td className="px-5 py-3">
                    <p className="font-mono text-xs">{f.file_name}</p>
                    <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                      {f.custodian} · {f.format}
                    </p>
                    {f.error && <p className="mt-1 text-xs text-red-700 dark:text-red-300">{f.error}</p>}
                  </td>
                  <td className="whitespace-nowrap px-3 py-3 text-slate-600 dark:text-slate-300">{formatDateTime(f.received_at)}</td>
                  <td className="px-3 py-3">
                    <Badge tone={STATUS_STYLE[f.status].tone} icon={STATUS_STYLE[f.status].icon}>
                      {FILE_STATUS_LABEL[f.status]}
                    </Badge>
                  </td>
                  <td className="px-3 py-3 text-right">{f.records}</td>
                  <td className="px-3 py-3 text-right text-slate-600 dark:text-slate-300">
                    {f.duration_ms === null ? '—' : `${formatNumber(f.duration_ms)} ms`}
                  </td>
                  <td className="px-5 py-3 font-mono text-xs text-slate-500 dark:text-slate-400">{f.correlation_id}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {files.data.length > 10 && (
          <button
            onClick={() => setShowAll((v) => !v)}
            className="mt-3 text-sm font-medium text-navy-700 hover:underline dark:text-navy-200"
          >
            {showAll ? 'Mostrar só os 10 mais recentes' : `Ver todos os ${files.data.length} arquivos`}
          </button>
        )}
      </Card>

      <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
        <Card title="Quebras de reconciliação" subtitle="Posição de ontem + movimentações de hoje deveria bater com a posição de hoje">
          <ul className="grid gap-3">
            {breaks.data.map((b) => {
              const diff = b.reported_quantity - b.expected_quantity
              return (
                <li key={b.id} className="rounded-xl border border-slate-200 p-4 dark:border-slate-800">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="font-medium">
                      {b.asset} · {CLIENTS[b.client_id].name} · {b.custodian}
                    </p>
                    {b.status === 'aberta' ? (
                      <Badge tone="red" icon={<AlertTriangle className="size-3.5" aria-hidden />}>Aberta</Badge>
                    ) : (
                      <Badge tone="green" icon={<CheckCircle2 className="size-3.5" aria-hidden />}>Resolvida</Badge>
                    )}
                  </div>
                  <dl className="mt-3 grid grid-cols-3 gap-3 text-sm">
                    <div>
                      <dt className="text-xs text-slate-500 dark:text-slate-400">Esperado</dt>
                      <dd className="font-medium">{formatNumber(b.expected_quantity)}</dd>
                    </div>
                    <div>
                      <dt className="text-xs text-slate-500 dark:text-slate-400">Custodiante informou</dt>
                      <dd className="font-medium">{formatNumber(b.reported_quantity)}</dd>
                    </div>
                    <div>
                      <dt className="text-xs text-slate-500 dark:text-slate-400">Diferença</dt>
                      <dd className="font-medium text-red-700 dark:text-red-400">
                        {diff > 0 ? '+' : ''}
                        {formatNumber(diff)}
                      </dd>
                    </div>
                  </dl>
                  <p className="mt-3 text-sm text-slate-600 dark:text-slate-300">
                    {formatDate(b.date)} · {b.note}
                  </p>
                </li>
              )
            })}
          </ul>
        </Card>
        <Explainer title="Por que isso importa?">
          <p>
            Se o custodiante diz que a Maria tem 52 cotas, mas a conta dá 50, algo está errado: um arquivo atrasado, um
            evento corporativo não informado ou um erro do próprio custodiante.
          </p>
          <p className="mt-2">
            Em vez de mostrar um número possivelmente errado para o cliente, o sistema registra a quebra e alerta o
            backoffice.
          </p>
        </Explainer>
      </div>
    </div>
  )
}

const STEPS = [
  { icon: FolderInput, title: 'S3', text: 'Arquivo chega' },
  { icon: Inbox, title: 'Fila SQS', text: 'Aviso enfileirado' },
  { icon: Cpu, title: 'Worker', text: 'Adapter + validação' },
  { icon: Database, title: 'Postgres', text: 'Posições gravadas' },
  { icon: Megaphone, title: 'SNS', text: 'Evento publicado' },
]

function Pipeline() {
  return (
    <ol className="flex flex-col gap-2 md:flex-row md:items-center">
      {STEPS.map((s, i) => (
        <li key={s.title} className="flex flex-1 flex-col items-stretch gap-2 md:flex-row md:items-center">
          <div className="flex flex-1 items-center gap-3 rounded-xl border border-slate-200 px-3 py-3 dark:border-slate-800">
            <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300">
              <s.icon className="size-4.5" aria-hidden />
            </span>
            <div className="min-w-0">
              <p className="text-sm font-medium">{s.title}</p>
              <p className="truncate text-xs text-slate-500 dark:text-slate-400">{s.text}</p>
            </div>
          </div>
          {i < STEPS.length - 1 && (
            <ChevronRight className="mx-auto size-4 shrink-0 rotate-90 text-slate-400 md:rotate-0" aria-hidden />
          )}
        </li>
      ))}
    </ol>
  )
}
