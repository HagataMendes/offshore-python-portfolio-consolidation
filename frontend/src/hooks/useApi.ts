import { useEffect, useState } from 'react'

type State<T> =
  | { status: 'loading'; data: null; error: null }
  | { status: 'success'; data: T; error: null }
  | { status: 'error'; data: null; error: string }

const LOADING = { status: 'loading', data: null, error: null } as const

/**
 * Chama uma função da API e guarda o resultado, o carregamento e o erro.
 * Passe o `fetcher` com useCallback para ele só mudar quando os parâmetros mudarem
 * (por exemplo, quando troca de Maria para Manoel).
 */
export function useApi<T>(fetcher: () => Promise<T>): State<T> {
  // Guardamos junto de qual `fetcher` veio o resultado: se ele mudou, voltamos a "carregando".
  const [result, setResult] = useState<{ source: () => Promise<T>; state: State<T> } | null>(null)

  useEffect(() => {
    let cancelled = false
    fetcher()
      .then((data) => {
        if (!cancelled) setResult({ source: fetcher, state: { status: 'success', data, error: null } })
      })
      .catch((e: unknown) => {
        const error = e instanceof Error ? e.message : String(e)
        if (!cancelled) setResult({ source: fetcher, state: { status: 'error', data: null, error } })
      })
    return () => {
      cancelled = true
    }
  }, [fetcher])

  if (!result || result.source !== fetcher) return LOADING
  return result.state
}
