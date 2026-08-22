import { describe, expect, it } from 'vitest'
import { toPriceCandles } from '../priceCandles'

describe('toPriceCandles', () => {
  it('groups intraday prices into daily OHLC data', () => {
    const candles = toPriceCandles([
      { price: 400000, captured_at: '2026-08-22T08:00:00Z' },
      { price: 390000, captured_at: '2026-08-22T12:00:00Z' },
      { price: 395000, captured_at: '2026-08-23T00:00:00Z' }
    ])
    expect(candles).toEqual([
      { date: '2026-08-22', open: 400000, close: 390000, low: 390000, high: 400000 },
      { date: '2026-08-23', open: 395000, close: 395000, low: 395000, high: 395000 }
    ])
  })
})
