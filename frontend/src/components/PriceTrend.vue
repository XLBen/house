<script setup>
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import * as echarts from 'echarts'
import { toPriceCandles } from '../utils/priceCandles'

const props = defineProps({
  trend: { type: Array, default: () => [] },
  history: { type: Array, default: null }
})
const el = ref(null)
let chart = null

const TEXT = '#555555'
const GRID = '#e8e8e8'
const TEAL = '#0ba6a0'

function render() {
  if (!chart) return
  chart.clear()
  if (props.history) {
    const candles = toPriceCandles(props.history)
    chart.setOption({
      tooltip: {
        trigger: 'axis',
        formatter: params => {
          const candle = candles[params[0]?.dataIndex]
          if (!candle) return ''
          return [
            candle.date,
            `开 £${candle.open.toLocaleString('en-GB')}`,
            `高 £${candle.high.toLocaleString('en-GB')}`,
            `低 £${candle.low.toLocaleString('en-GB')}`,
            `收 £${candle.close.toLocaleString('en-GB')}`
          ].join('<br>')
        }
      },
      grid: { left: 60, right: 20, top: 30, bottom: 40 },
      xAxis: { type: 'category', data: candles.map(c => c.date), axisLabel: { color: TEXT } },
      yAxis: { type: 'value', axisLabel: { color: TEXT, formatter: v => '£' + (v / 1000).toFixed(0) + 'k' }, splitLine: { lineStyle: { color: GRID } } },
      series: [{
        type: 'candlestick',
        data: candles.map(c => [c.open, c.close, c.low, c.high]),
        itemStyle: {
          color: '#d95c5c',
          color0: TEAL,
          borderColor: '#d95c5c',
          borderColor0: TEAL
        }
      }]
    })
    return
  }
  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { textStyle: { color: TEXT } },
    grid: { left: 60, right: 20, top: 30, bottom: 40 },
    xAxis: { type: 'category', data: props.trend.map(t => t.date), axisLabel: { color: TEXT } },
    yAxis: [
      { type: 'value', axisLabel: { color: TEXT, formatter: v => '£' + (v / 1000).toFixed(0) + 'k' }, splitLine: { lineStyle: { color: GRID } } },
      { type: 'value', splitLine: { show: false } }
    ],
    series: [
      { name: '均价', type: 'line', smooth: true, data: props.trend.map(t => t.avg_price), lineStyle: { color: TEAL, width: 3 }, itemStyle: { color: TEAL } },
      { name: '在售数', type: 'bar', yAxisIndex: 1, data: props.trend.map(t => t.active_count), itemStyle: { color: 'rgba(15,143,79,.35)' } }
    ]
  })
}

onMounted(() => { chart = echarts.init(el.value); render() })
watch(() => [props.trend, props.history], render, { deep: true })
onBeforeUnmount(() => { if (chart) chart.dispose() })
</script>

<template>
  <div ref="el" style="width: 100%; height: 280px;"></div>
</template>
