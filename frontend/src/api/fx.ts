// Cotação do dólar em reais (USD/BRL).
// Busca ao vivo na AwesomeAPI (gratuita, sem chave). Se não conseguir
// (sem internet, API fora do ar), usa uma cotação de referência e avisa na tela.

export interface FxQuote {
  pair: 'USD/BRL'
  rate: number // R$ por 1 US$
  pct_change: number // variação no dia, em %: -0.13 = −0,13%
  updated_at: string // ISO: 2026-09-29T11:54:00
  source: 'ao_vivo' | 'referencia'
}

const AWESOME_API = 'https://economia.awesomeapi.com.br/json/last/USD-BRL'

// Dólar comercial em 29/09/2026 às 11h54 (Brasília), usado quando não há conexão.
export const REFERENCE_QUOTE: FxQuote = {
  pair: 'USD/BRL',
  rate: 5.217,
  pct_change: -0.13,
  updated_at: '2026-09-29T11:54:00',
  source: 'referencia',
}

interface AwesomeApiResponse {
  USDBRL: { bid: string; pctChange: string; create_date: string }
}

export async function getUsdBrl(): Promise<FxQuote> {
  try {
    const res = await fetch(AWESOME_API, { signal: AbortSignal.timeout(5000) })
    if (!res.ok) throw new Error(`AwesomeAPI respondeu ${res.status}`)
    const { USDBRL } = (await res.json()) as AwesomeApiResponse
    return {
      pair: 'USD/BRL',
      rate: Number(USDBRL.bid),
      pct_change: Number(USDBRL.pctChange),
      updated_at: USDBRL.create_date.replace(' ', 'T'),
      source: 'ao_vivo',
    }
  } catch {
    return REFERENCE_QUOTE
  }
}
