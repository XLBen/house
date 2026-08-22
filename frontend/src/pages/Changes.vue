<script setup>
import { ref, watch, onMounted, onBeforeUnmount, computed } from 'vue'
import { useRoute } from 'vue-router'
import { api, fmtPrice } from '../api'
import { useAppStore } from '../stores/app'
import ComparisonSummary from '../components/ComparisonSummary.vue'

const route = useRoute()
const store = useAppStore()
const regionId = ref('')
const date = ref(new Date().toISOString().slice(0, 10))
const mode = ref('date') // date | since
const summary = ref(null)
const loading = ref(false)
const error = ref('')

const currentSummary = computed(() => summary.value)

async function loadChanges() {
  if (!regionId.value) { summary.value = null; return }
  loading.value = true
  error.value = ''
  try {
    const opts = mode.value === 'date' ? { date: date.value } : { since: 'last_sync' }
    summary.value = await api.regionChanges(regionId.value, opts)
  } catch (e) {
    error.value = '加载失败：' + (e.message || e)
    summary.value = null
  } finally {
    loading.value = false
  }
}

function initRegionId() {
  const fromQuery = route.query.region
  const preferred = fromQuery || store.currentRegionId || store.regions[0]?.id
  if (preferred) regionId.value = String(preferred)
}

watch([regionId, date, mode], loadChanges)

function renderItem(item) {
  const ev = item.event
  let txt = ''
  let cls = ''
  if (ev.event_type === 'new') txt = `新增挂牌 ${fmtPrice(ev.new_value)}`
  else if (ev.event_type === 'price_change') {
    const old = Number(ev.old_value), neu = Number(ev.new_value)
    const diff = old - neu
    if (diff > 0) { txt = `降价 ${fmtPrice(diff)}（${fmtPrice(old)} → ${fmtPrice(neu)}）`; cls = 'drop' }
    else { txt = `涨价 ${fmtPrice(Math.abs(diff))}（${fmtPrice(old)} → ${fmtPrice(neu)}）`; cls = 'rise' }
  } else if (ev.event_type === 'delisted') txt = `从市场消失`
  else txt = `${ev.old_value} → ${ev.new_value}`
  return { ...item, txt, cls, time: new Date(ev.occurred_at).toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) }
}

const sections = [
  { key: 'new', title: '新增挂牌', empty: '暂无新增' },
  { key: 'price_changes', title: '价格变化', empty: '暂无价格变化' },
  { key: 'delisted', title: '已下架（可能售出/下架）', empty: '暂无已下架' },
  { key: 'status_changes', title: '状态变化', empty: '暂无状态变化' }
]

const refreshHandler = () => loadChanges()
onMounted(async () => {
  if (!store.regions.length) await store.loadRegions()
  initRegionId()
  await loadChanges()
  window.addEventListener('regions-refresh', refreshHandler)
})
onBeforeUnmount(() => window.removeEventListener('regions-refresh', refreshHandler))
</script>

<template>
  <div>
    <div class="panel">
      <h2>变化记录</h2>
      <div class="filters">
        <select v-model="regionId" aria-label="区域">
          <option v-for="r in store.regions" :key="r.id" :value="String(r.id)">{{ r.name }}</option>
        </select>
        <select v-model="mode" aria-label="查看方式">
          <option value="date">按日期查看</option>
          <option value="since">本次同步对比</option>
        </select>
        <input v-if="mode === 'date'" v-model="date" type="date" aria-label="日期" />
      </div>
      <p class="muted" style="color:var(--rm-muted); margin-top:8px; font-size:12px;">
        说明：价格变化是"有意义的变化"；描述/文案改动不记录。已下架时间 = 系统检测到房源离开市场的 0 点同步时间。
      </p>
    </div>

    <div v-if="error" class="panel"><div class="empty">{{ error }}</div></div>
    <div v-if="loading" class="empty">加载中…</div>

    <template v-if="summary">
      <div class="panel">
        <ComparisonSummary :changes="currentSummary" :compact="false" />
      </div>

      <div class="panel" v-for="sec in sections" :key="sec.key">
        <h2>{{ sec.title }}</h2>
        <div v-if="!summary[sec.key].length" class="empty">{{ sec.empty }}</div>
        <div v-for="item in summary[sec.key].map(renderItem)" :key="item.event.id" class="event-item">
          <span class="time">{{ item.time }}</span>
          <span class="addr">{{ item.address || item.listing_id }}</span>
          <span class="detail" :class="item.cls">{{ item.txt }}</span>
        </div>
      </div>
    </template>
  </div>
</template>
