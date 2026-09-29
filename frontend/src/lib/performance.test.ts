import { describe, expect, it } from 'vitest'
import { SNAPSHOT } from '../mocks/data'
import type { ValuationPoint } from '../types'
import { compound, naiveReturn, splitSubPeriods, timeWeightedReturn } from './performance'

const point = (date: string, value_usd: number, external_flow_usd = 0): ValuationPoint => ({
  date,
  value_usd,
  external_flow_usd,
  daily_return: 0,
})

describe('TWR', () => {
  it('reproduz o exemplo do Manoel: +5% e depois −2% dá +2,9%', () => {
    const history = [point('d0', 200_000), point('d1', 210_000), point('d2', 147_000, -60_000)]
    expect(timeWeightedReturn(history)).toBeCloseTo(0.029, 10)
    expect(naiveReturn(history)).toBeCloseTo(-0.265, 10)
  })

  it('quebra o período em cada depósito ou saque', () => {
    const history = [point('d0', 200_000), point('d1', 210_000), point('d2', 147_000, -60_000)]
    const periods = splitSubPeriods(history)
    expect(periods.map((p) => p.return)).toEqual([expect.closeTo(0.05, 10), expect.closeTo(-0.02, 10)])
    expect(compound(periods.map((p) => p.return))).toBeCloseTo(timeWeightedReturn(history), 10)
  })
})

describe('snapshot da API Python', () => {
  it.each(['maria', 'manoel'] as const)('o TWR calculado em TypeScript bate com o do Python (%s)', (id) => {
    const history = SNAPSHOT.portfolio[id].history
    expect(timeWeightedReturn(history)).toBeCloseTo(SNAPSHOT.performance[id].twr, 5)
  })

  it.each(['maria', 'manoel'] as const)('a série de %s termina na soma das posições', (id) => {
    const p = SNAPSHOT.portfolio[id]
    const sum = p.positions.reduce((s, x) => s + x.market_value_usd, 0)
    expect(p.history[p.history.length - 1].value_usd).toBeCloseTo(sum, 2)
    expect(p.total_usd).toBeCloseTo(sum, 2)
  })
})
