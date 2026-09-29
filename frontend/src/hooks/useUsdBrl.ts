import { useEffect, useState } from 'react'
import { getUsdBrl, type FxQuote } from '../api/fx'

const REFRESH_MS = 60_000

/** Cotação do dólar, atualizada a cada minuto enquanto a tela estiver aberta. */
export function useUsdBrl(): FxQuote | null {
  const [quote, setQuote] = useState<FxQuote | null>(null)

  useEffect(() => {
    let cancelled = false
    const load = () => getUsdBrl().then((q) => !cancelled && setQuote(q))
    load()
    const id = setInterval(load, REFRESH_MS)
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [])

  return quote
}
