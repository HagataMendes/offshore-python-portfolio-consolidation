import {
  ChartNoAxesCombined,
  Eye,
  EyeOff,
  FileText,
  LayoutDashboard,
  PieChart,
  ServerCog,
  TrendingDown,
  TrendingUp,
  UserRound,
} from 'lucide-react'
import { useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { isUsingMock } from '../api/client'
import type { FxQuote } from '../api/fx'
import { useSelectedClient } from '../context/clientContext'
import { useUsdBrl } from '../hooks/useUsdBrl'
import { formatRate } from '../lib/format'
import { CLIENTS } from '../mocks/data'
import type { ClientId } from '../types'

const NAV = [
  { to: '/', label: 'Visão geral', icon: LayoutDashboard, title: 'Carteira consolidada', group: 'Carteira' },
  { to: '/extrato', label: 'Extrato', icon: FileText, title: 'Extrato consolidado', group: 'Carteira' },
  { to: '/rentabilidade', label: 'Rentabilidade', icon: ChartNoAxesCombined, title: 'Rentabilidade', group: 'Carteira' },
  { to: '/analise', label: 'Análise geral', icon: PieChart, title: 'Análise geral das carteiras', group: 'Gestão' },
  { to: '/operacoes', label: 'Operações', icon: ServerCog, title: 'Operações e ingestão', group: 'Backoffice' },
] as const

type NavEntry = (typeof NAV)[number]

/** O que o Layout compartilha com as telas (lido com useOutletContext). */
export interface LayoutContext {
  usdBrl: FxQuote | null
}

export function Layout() {
  const { pathname } = useLocation()
  const current = NAV.find((n) => n.to === pathname) ?? NAV[0]
  const isBackoffice = current.group === 'Backoffice'
  const isCrossClient = current.group !== 'Carteira' // telas que olham todos os clientes
  const usdBrl = useUsdBrl()
  const [hideValues, setHideValues] = useState(false)

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[256px_1fr]" data-hide-values={hideValues || undefined}>
      {/* Menu lateral (computador): a coluna é marinho de cima a baixo; o menu fica fixo ao rolar */}
      <div className="no-print hidden bg-navy-900 lg:block">
        <aside className="sticky top-0 flex h-screen flex-col px-4 py-7 text-navy-200">
          <Brand />
          <nav className="mt-10 grid gap-6" aria-label="Principal">
            {(['Carteira', 'Gestão', 'Backoffice'] as const).map((group) => (
              <div key={group}>
                <p className="mb-2 px-3 text-[11px] font-medium uppercase tracking-[0.14em] text-navy-300/70">{group}</p>
                <div className="grid gap-0.5">
                  {NAV.filter((n) => n.group === group).map((item) => (
                    <NavItem key={item.to} item={item} />
                  ))}
                </div>
              </div>
            ))}
          </nav>
          <div className="mt-auto grid gap-3">
            <AdvisorCard />
            <DataSourceNote />
          </div>
        </aside>
      </div>

      <div className="min-w-0">
        {/* Topo no celular: marca + menu em abas */}
        <div className="no-print bg-navy-900 lg:hidden">
          <div className="px-4 pb-3 pt-4">
            <Brand />
          </div>
          <nav className="flex gap-1 overflow-x-auto px-3 pb-3" aria-label="Principal">
            {NAV.map((item) => (
              <NavItem key={item.to} item={item} compact />
            ))}
          </nav>
        </div>

        {/* Barra do cliente */}
        <header
          className="no-print sticky z-10 border-b border-slate-200 bg-white/90 backdrop-blur dark:border-slate-800 dark:bg-navy-950/90"
          style={{ top: 'env(safe-area-inset-top, 0px)' }}
        >
          <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-8">
            {isBackoffice ? <BackofficeIdentity /> : isCrossClient ? <ManagementIdentity /> : <ClientIdentity />}
            <div className="flex flex-wrap items-center gap-2">
              <FxTicker quote={usdBrl} />
              <button
                onClick={() => setHideValues((v) => !v)}
                aria-pressed={hideValues}
                className="inline-flex h-11 items-center gap-2 rounded-lg border border-slate-200 px-3 text-sm font-medium text-slate-700 hover:bg-slate-50 focus-visible:outline-2 focus-visible:outline-navy-700 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
              >
                {hideValues ? <EyeOff className="size-4" aria-hidden /> : <Eye className="size-4" aria-hidden />}
                <span className="hidden sm:inline">{hideValues ? 'Mostrar valores' : 'Ocultar valores'}</span>
              </button>
              {!isCrossClient && <ClientSwitcher />}
            </div>
          </div>
        </header>

        <main className="mx-auto max-w-7xl px-4 py-6 sm:px-8 sm:py-8">
          <div className="mb-6 flex flex-wrap items-end justify-between gap-2">
            <h1 className="font-display text-[28px] font-semibold leading-tight tracking-tight text-navy-900 dark:text-white">
              {current.title}
            </h1>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              {isBackoffice
                ? 'Todos os clientes · atualizado às 07h42'
                : isCrossClient
                  ? 'Setembro de 2026 · todos os clientes · valores em dólar (US$)'
                  : 'Posição de 30/09/2026 · valores em dólar (US$)'}
            </p>
          </div>
          <Outlet context={{ usdBrl } satisfies LayoutContext} />
        </main>

        <footer className="no-print px-4 pb-8 text-center text-xs text-slate-400 sm:px-8 dark:text-slate-500">
          Projeto de estudo com dados fictícios. Maria e Manoel não são clientes reais.
        </footer>
      </div>
    </div>
  )
}

function Brand() {
  return (
    <div className="flex items-center gap-3 px-2">
      <svg viewBox="0 0 36 36" className="size-9 shrink-0" aria-hidden>
        <rect x="0.75" y="0.75" width="34.5" height="34.5" rx="4" fill="none" stroke="currentColor" className="text-brass-light" strokeWidth="1.5" />
        <path d="M9 25h18M11 25V14M18 25V11M25 25v-8" stroke="currentColor" className="text-brass-light" strokeWidth="2" strokeLinecap="round" />
      </svg>
      <div className="leading-tight">
        <p className="font-display text-lg font-semibold text-white">Offshore</p>
        <p className="text-[10px] font-medium uppercase tracking-[0.22em] text-brass-light">Private wealth</p>
      </div>
    </div>
  )
}

function NavItem({ item, compact = false }: { item: NavEntry; compact?: boolean }) {
  const Icon = item.icon
  return (
    <NavLink
      to={item.to}
      end
      className={({ isActive }) =>
        [
          'relative flex items-center gap-3 text-sm transition-colors',
          compact ? 'shrink-0 rounded-md px-3 py-1.5' : 'rounded-md px-3 py-2.5',
          isActive ? 'bg-navy-800 font-medium text-white' : 'text-navy-200 hover:bg-navy-800/60 hover:text-white',
        ].join(' ')
      }
    >
      {({ isActive }) => (
        <>
          {isActive && !compact && <span aria-hidden className="absolute inset-y-2 left-0 w-0.5 bg-brass-light" />}
          <Icon className="size-4" aria-hidden />
          {item.label}
        </>
      )}
    </NavLink>
  )
}

function initials(fullName: string) {
  const parts = fullName.split(' ')
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

function ClientIdentity() {
  const { clientId } = useSelectedClient()
  const c = CLIENTS[clientId]
  return (
    <div className="flex min-w-0 items-center gap-3">
      <span
        aria-hidden
        className="grid size-10 shrink-0 place-items-center rounded-full bg-navy-900 font-display text-sm font-semibold text-brass-light dark:bg-navy-800"
      >
        {initials(c.full_name)}
      </span>
      <div className="min-w-0 leading-tight">
        <p className="truncate font-medium">{c.full_name}</p>
        <p className="truncate text-xs text-slate-500 dark:text-slate-400">
          Conta {c.account} · Perfil {c.risk_profile.toLowerCase()}
        </p>
      </div>
    </div>
  )
}

function BackofficeIdentity() {
  return (
    <div className="flex items-center gap-3">
      <span aria-hidden className="grid size-10 place-items-center rounded-full bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300">
        <ServerCog className="size-4.5" />
      </span>
      <div className="leading-tight">
        <p className="font-medium">Backoffice offshore</p>
        <p className="text-xs text-slate-500 dark:text-slate-400">Ingestão de custodiantes e reconciliação</p>
      </div>
    </div>
  )
}

function ManagementIdentity() {
  return (
    <div className="flex items-center gap-3">
      <span aria-hidden className="grid size-10 place-items-center rounded-full bg-navy-900 text-brass-light dark:bg-navy-800">
        <PieChart className="size-4.5" />
      </span>
      <div className="leading-tight">
        <p className="font-medium">Gestão de carteiras</p>
        <p className="text-xs text-slate-500 dark:text-slate-400">Visão consolidada de todos os clientes</p>
      </div>
    </div>
  )
}

function ClientSwitcher() {
  const { clientId, setClientId } = useSelectedClient()
  return (
    <div
      role="radiogroup"
      aria-label="Carteira do cliente"
      className="inline-flex h-11 items-center rounded-lg border border-slate-200 bg-slate-100 p-1 dark:border-slate-700 dark:bg-slate-800"
    >
      {(Object.keys(CLIENTS) as ClientId[]).map((id) => {
        const active = id === clientId
        return (
          <button
            key={id}
            role="radio"
            aria-checked={active}
            onClick={() => setClientId(id)}
            className={[
              'h-full rounded-md px-4 text-sm font-medium transition focus-visible:outline-2 focus-visible:outline-navy-700',
              active
                ? 'bg-navy-900 text-white dark:bg-navy-700'
                : 'text-slate-600 hover:text-slate-900 dark:text-slate-300 dark:hover:text-white',
            ].join(' ')}
          >
            {CLIENTS[id].name}
          </button>
        )
      })}
    </div>
  )
}

function AdvisorCard() {
  const { clientId } = useSelectedClient()
  const c = CLIENTS[clientId]
  return (
    <div className="rounded-lg bg-navy-800/70 p-3">
      <p className="text-[11px] uppercase tracking-[0.14em] text-navy-300/70">Assessor</p>
      <p className="mt-1 flex items-center gap-2 text-sm font-medium text-white">
        <UserRound className="size-4 text-brass-light" aria-hidden />
        {c.advisor}
      </p>
      <p className="mt-0.5 text-xs text-navy-300">Atendimento offshore · {c.name}</p>
    </div>
  )
}

function DataSourceNote() {
  return (
    <div className="px-1 text-[11px] leading-relaxed text-navy-300/80">
      <p className="font-medium text-navy-200">Fonte: {isUsingMock ? 'snapshot da API Python' : 'API Python ao vivo'}</p>
      <p className="mt-0.5">
        {isUsingMock
          ? 'Números gerados pelo back-end. Defina VITE_API_URL para consultar a API ao vivo.'
          : `Conectado em ${import.meta.env.VITE_API_URL}`}
      </p>
    </div>
  )
}

function FxTicker({ quote }: { quote: FxQuote | null }) {
  if (!quote) {
    return <div className="h-11 w-52 animate-pulse rounded-lg bg-slate-100 dark:bg-slate-800" aria-label="Carregando cotação" />
  }
  const up = quote.pct_change > 0
  const live = quote.source === 'ao_vivo'
  const when = `${quote.updated_at.slice(8, 10)}/${quote.updated_at.slice(5, 7)} ${quote.updated_at.slice(11, 16)}`
  return (
    <div
      className="flex h-11 items-center gap-3 rounded-lg border border-slate-200 px-3 dark:border-slate-700"
      title={live ? 'Cotação ao vivo (AwesomeAPI), atualizada a cada minuto' : 'Sem conexão com a fonte ao vivo: mostrando a última cotação de referência'}
    >
      <div className="leading-tight">
        <p className="text-[11px] uppercase tracking-wide text-slate-500 dark:text-slate-400">USD/BRL</p>
        <p className="text-sm font-semibold tabular-nums">R$ {formatRate(quote.rate)}</p>
      </div>
      <div className="leading-tight">
        <p className="flex items-center gap-1 text-xs font-medium tabular-nums text-slate-700 dark:text-slate-300">
          {up ? <TrendingUp className="size-3.5" aria-hidden /> : <TrendingDown className="size-3.5" aria-hidden />}
          {up ? '+' : ''}
          {quote.pct_change.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%
        </p>
        <p className="flex items-center gap-1 text-[11px] text-slate-500 dark:text-slate-400">
          <span aria-hidden className={`size-1.5 rounded-full ${live ? 'bg-emerald-500' : 'bg-slate-400'}`} />
          {live ? 'Ao vivo' : `Ref. ${when}`}
        </p>
      </div>
    </div>
  )
}
