<script setup>
import { ref, watch, onBeforeUnmount } from 'vue'
import { api, fmtPrice, fmtDate, STATUS_LABELS, statusClass } from '../api'
import { useAppStore } from '../stores/app'
import PriceTrend from './PriceTrend.vue'

const props = defineProps({ propertyId: { type: [Number, String], default: null } })
const emit = defineEmits(['close'])

const store = useAppStore()
const prop = ref(null)
const history = ref([])
const events = ref([])
const loading = ref(false)
const maskEl = ref(null)

watch(() => props.propertyId, async (id) => {
  if (!id) { prop.value = null; return }
  loading.value = true
  try {
    const [p, h, e] = await Promise.all([
      api.getProperty(id),
      api.propertyHistory(id),
      api.propertyEvents(id)
    ])
    prop.value = p
    history.value = h
    events.value = e
  } finally {
    loading.value = false
  }
}, { immediate: true })

function onKeydown(e) {
  if (e.key === 'Escape') emit('close')
}

function dropInfo() {
  if (!prop.value) return null
  const { first_price, current_price } = prop.value
  if (first_price && current_price && current_price < first_price) {
    return {
      amount: first_price - current_price,
      pct: Math.round((first_price - current_price) / first_price * 100)
    }
  }
  return null
}

const EVENT_TXT = {
  new: '新增挂牌',
  price_change: '价格变化',
  status_change: '状态变化',
  delisted: '从市场消失'
}

onBeforeUnmount(() => document.removeEventListener('keydown', onKeydown))
</script>

<template>
  <teleport to="body">
    <transition name="drawer">
      <div v-if="props.propertyId" class="drawer-mask" @click="emit('close')">
        <div
          ref="maskEl"
          class="drawer"
          role="dialog"
          aria-modal="true"
          aria-label="房源详情"
          tabindex="-1"
          @click.stop
          @keydown="onKeydown"
        >
          <div class="drawer-head">
            <div class="drawer-title">
              <div v-if="loading || !prop" class="drawer-loading">加载中…</div>
              <template v-else>
                <div class="drawer-price">{{ fmtPrice(prop.current_price) }}</div>
                <div class="drawer-addr">{{ prop.address }}</div>
              </template>
            </div>
            <button class="btn" type="button" @click="emit('close')">✕ 关闭</button>
          </div>

          <template v-if="!loading && prop">
            <div class="drawer-actions">
              <span class="badge" :class="statusClass(prop.status)">{{ STATUS_LABELS[prop.status] || prop.status }}</span>
              <button class="btn" type="button" @click="store.toggleWatch(prop.id)">
                {{ store.isWatched(prop.id) ? '★ 已收藏' : '☆ 收藏' }}
              </button>
              <a v-if="prop.url" class="btn btn-ext" :href="prop.url" target="_blank" rel="noopener">查看原房源 ↗</a>
            </div>

            <div v-if="dropInfo()" class="drop-banner">
              价格较首次挂牌下调 {{ fmtPrice(dropInfo().amount) }}（{{ dropInfo().pct }}%）
            </div>

            <div class="drawer-meta">
              {{ prop.bedrooms ?? '—' }} 卧室 · {{ prop.bathrooms ?? '—' }} 卫浴 · {{ prop.property_type || '—' }}
              <span v-if="prop.floor_area_sqft"> · {{ Number(prop.floor_area_sqft).toLocaleString('en-GB') }} sq ft</span>
              <span v-if="prop.price_per_sqft"> · £{{ prop.price_per_sqft.toLocaleString('en-GB') }}/sqft</span>
              <span v-if="prop.removed_at"> · 于 {{ fmtDate(prop.removed_at) }} 从市场消失</span>
              <span v-if="prop.relisted_at"> · {{ fmtDate(prop.relisted_at) }} 重新挂牌</span>
            </div>

            <p v-if="prop.description" class="drawer-desc">{{ prop.description }}</p>

            <div v-if="history.length" class="drawer-sec">
               <h3>价格 K 线</h3>
              <PriceTrend :history="history" />
            </div>

            <div class="drawer-sec">
              <h3>事件时间线</h3>
              <div v-if="!events.length" class="empty">暂无事件</div>
              <div v-for="e in events" :key="e.id" class="event-item">
                <span class="time">{{ fmtDate(e.occurred_at) }}</span>
                <span class="detail">{{ EVENT_TXT[e.event_type] || e.event_type }} <template v-if="e.event_type === 'price_change'">{{ e.old_value }} → {{ e.new_value }}</template></span>
              </div>
            </div>
          </template>
        </div>
      </div>
    </transition>
  </teleport>
</template>
