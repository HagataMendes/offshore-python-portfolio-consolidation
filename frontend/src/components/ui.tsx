// Peças visuais pequenas e reutilizáveis (o "Lego" das telas).
import type { ReactNode } from 'react'

export function Card({
  title,
  subtitle,
  action,
  children,
  className = '',
}: {
  title?: string
  subtitle?: string
  action?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <section
      className={`min-w-0 rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-navy-950 ${className}`}
    >
      {(title || action) && (
        <header className="mb-4 flex items-start justify-between gap-4">
          <div>
            {title && <h2 className="font-display text-lg font-semibold text-navy-900 dark:text-white">{title}</h2>}
            {subtitle && <p className="mt-0.5 text-sm text-slate-500 dark:text-slate-400">{subtitle}</p>}
          </div>
          {action}
        </header>
      )}
      {children}
    </section>
  )
}

export function StatCard({
  label,
  value,
  hint,
  tone = 'default',
}: {
  label: string
  value: string
  hint?: ReactNode
  tone?: 'default' | 'positive' | 'negative' | 'muted'
}) {
  const toneClass = {
    default: 'text-slate-900 dark:text-slate-50',
    positive: 'text-emerald-700 dark:text-emerald-400',
    negative: 'text-red-700 dark:text-red-400',
    muted: 'text-slate-400 line-through decoration-2 dark:text-slate-500',
  }[tone]
  return (
    <div className="min-w-0 rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-navy-950">
      <p className="text-sm text-slate-500 dark:text-slate-400">{label}</p>
      <p className={`mt-2 text-2xl font-semibold tracking-tight ${toneClass}`}>{value}</p>
      {hint && <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{hint}</p>}
    </div>
  )
}

const BADGE_TONES = {
  neutral: 'bg-slate-100 text-slate-700 ring-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:ring-slate-700',
  blue: 'bg-blue-50 text-blue-700 ring-blue-200 dark:bg-blue-950 dark:text-blue-300 dark:ring-blue-900',
  green: 'bg-emerald-50 text-emerald-700 ring-emerald-200 dark:bg-emerald-950 dark:text-emerald-300 dark:ring-emerald-900',
  amber: 'bg-amber-50 text-amber-800 ring-amber-200 dark:bg-amber-950 dark:text-amber-300 dark:ring-amber-900',
  red: 'bg-red-50 text-red-700 ring-red-200 dark:bg-red-950 dark:text-red-300 dark:ring-red-900',
} as const

export type BadgeTone = keyof typeof BADGE_TONES

export function Badge({ tone = 'neutral', icon, children }: { tone?: BadgeTone; icon?: ReactNode; children: ReactNode }) {
  return (
    <span
      className={`inline-flex items-center gap-1 whitespace-nowrap rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${BADGE_TONES[tone]}`}
    >
      {icon}
      {children}
    </span>
  )
}

export function Loading({ label = 'Carregando…' }: { label?: string }) {
  return (
    <div className="grid gap-4" aria-busy="true" aria-label={label}>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="h-28 animate-pulse rounded-xl bg-slate-200/70 dark:bg-slate-800/70" />
        ))}
      </div>
      <div className="h-80 animate-pulse rounded-xl bg-slate-200/70 dark:bg-slate-800/70" />
    </div>
  )
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div className="rounded-2xl border border-red-200 bg-red-50 p-5 text-sm text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-200">
      Não foi possível carregar os dados. {message}
    </div>
  )
}

/** Explicação curta para quem está aprendendo: aparece como uma nota lateral. */
export function Explainer({ title, children }: { title: string; children: ReactNode }) {
  return (
    <aside className="rounded-xl border border-blue-200 bg-blue-50/60 p-4 text-sm leading-relaxed text-blue-950 dark:border-blue-900 dark:bg-blue-950/40 dark:text-blue-100">
      <p className="mb-1 font-semibold">{title}</p>
      {children}
    </aside>
  )
}
