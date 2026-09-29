import type { SubPeriod, ValuationPoint } from '../types'

// Convenção: o fluxo externo (depósito/saque) entra no INÍCIO do dia,
// antes do mercado mexer. Então:
//   valor_hoje = (valor_ontem + fluxo_hoje) × (1 + retorno_do_dia)
// e o retorno do dia é recuperado a partir dos valores:
//   retorno_do_dia = valor_hoje / (valor_ontem + fluxo_hoje) − 1

export function dailyReturnFromValues(prevValue: number, value: number, flow: number): number {
  return value / (prevValue + flow) - 1
}

/** Encadeia retornos: (1 + r1) × (1 + r2) × ... − 1 */
export function compound(returns: number[]): number {
  return returns.reduce((acc, r) => acc * (1 + r), 1) - 1
}

/**
 * TWR (Time-Weighted Return): mede o desempenho dos investimentos
 * sem ser distorcido por depósitos e saques do cliente.
 */
export function timeWeightedReturn(history: ValuationPoint[]): number {
  const returns: number[] = []
  for (let i = 1; i < history.length; i++) {
    const prev = history[i - 1]
    const cur = history[i]
    returns.push(dailyReturnFromValues(prev.value_usd, cur.value_usd, cur.external_flow_usd))
  }
  return compound(returns)
}

/** Conta "ingênua": só compara o valor final com o inicial. Serve para mostrar o erro. */
export function naiveReturn(history: ValuationPoint[]): number {
  const first = history[0].value_usd
  const last = history[history.length - 1].value_usd
  return last / first - 1
}

/**
 * Quebra o período em pedaços, cortando em cada depósito ou saque.
 * Cada pedaço tem o seu retorno; o TWR é esses retornos multiplicados.
 */
export function splitSubPeriods(history: ValuationPoint[]): SubPeriod[] {
  const periods: SubPeriod[] = []
  let chunk: number[] = []
  let chunkStart = history[0].date
  let flowBefore = 0

  for (let i = 1; i < history.length; i++) {
    const prev = history[i - 1]
    const cur = history[i]
    if (cur.external_flow_usd !== 0 && chunk.length > 0) {
      periods.push({ start: chunkStart, end: prev.date, return: compound(chunk), flow_before_usd: flowBefore })
      chunk = []
      chunkStart = prev.date
    }
    if (chunk.length === 0) flowBefore = cur.external_flow_usd
    chunk.push(dailyReturnFromValues(prev.value_usd, cur.value_usd, cur.external_flow_usd))
  }
  if (chunk.length > 0) {
    periods.push({
      start: chunkStart,
      end: history[history.length - 1].date,
      return: compound(chunk),
      flow_before_usd: flowBefore,
    })
  }
  return periods
}
