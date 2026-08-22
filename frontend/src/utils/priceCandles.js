const LONDON_DATE = new Intl.DateTimeFormat('en-CA', {
  timeZone: 'Europe/London',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit'
})

function dayKey(value) {
  return LONDON_DATE.format(new Date(value))
}

// Convert point-in-time prices into daily OHLC candles.
export function toPriceCandles(history) {
  const days = new Map()
  for (const item of history || []) {
    if (item.price == null || !item.captured_at) continue
    const date = dayKey(item.captured_at)
    const price = Number(item.price)
    if (!Number.isFinite(price)) continue
    const candle = days.get(date)
    if (!candle) {
      days.set(date, { date, open: price, close: price, low: price, high: price })
      continue
    }
    candle.close = price
    candle.low = Math.min(candle.low, price)
    candle.high = Math.max(candle.high, price)
  }
  return [...days.values()].sort((a, b) => a.date.localeCompare(b.date))
}
