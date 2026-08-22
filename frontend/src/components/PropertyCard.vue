<script setup>
import { computed } from 'vue'
import { fmtPrice, fmtDateShort, STATUS_LABELS, statusClass } from '../api'
import { useAppStore } from '../stores/app'

const props = defineProps({ property: { type: Object, required: true } })
const emit = defineEmits(['open', 'focus-prop'])

const store = useAppStore()

const isNew = computed(() => {
  const d = new Date(props.property.first_seen_at)
  return (Date.now() - d.getTime()) < 7 * 24 * 3600 * 1000
})

function openSource(ev) {
  ev.stopPropagation()
  if (props.property.url) window.open(props.property.url, '_blank', 'noopener')
}

function onKeydown(ev) {
  if (ev.key === 'Enter' || ev.key === ' ') {
    ev.preventDefault()
    emit('open', props.property)
  }
}
</script>

<template>
  <div
    class="pc"
    role="button"
    tabindex="0"
    :aria-label="`查看房源 ${property.address}`"
    @click="emit('open', property)"
    @keydown="onKeydown"
  >
    <div class="pc-flag-row">
      <span v-if="isNew" class="badge badge-new">新增</span>
      <span v-if="property.reduced_flag" class="badge badge-red">降价</span>
      <span v-if="property.relisted_at" class="badge badge-blue">重新挂牌</span>
      <span v-if="property.status === 'removed'" class="badge badge-gray">已下架</span>
      <span v-else class="badge" :class="statusClass(property.status)">{{ STATUS_LABELS[property.status] || property.status }}</span>
    </div>
    <div class="pc-body">
      <div class="pc-topline">
        <div class="pc-price">
          {{ fmtPrice(property.current_price) }}
          <span v-if="property.pct_change != null && property.pct_change < 0" class="pc-drop">
            较首挂降 {{ Math.abs(property.pct_change) }}%
          </span>
        </div>
        <button
          class="pc-star"
          :class="{ on: store.isWatched(property.id) }"
          type="button"
          :aria-label="store.isWatched(property.id) ? '取消收藏' : '收藏'"
          :title="store.isWatched(property.id) ? '取消收藏' : '收藏'"
          @click.stop="store.toggleWatch(property.id)"
        >★</button>
      </div>
      <div class="pc-addr">{{ property.address }}</div>
      <div class="pc-meta">
        {{ property.bedrooms ?? '—' }} 卧 · {{ property.bathrooms ?? '—' }} 卫 · {{ property.property_type || '—' }}
        <span v-if="property.floor_area_sqft"> · {{ Number(property.floor_area_sqft).toLocaleString('en-GB') }} sq ft</span>
        <span v-if="property.price_per_sqft"> · £{{ property.price_per_sqft.toLocaleString('en-GB') }}/sqft</span>
      </div>
      <div class="pc-foot">
        <span v-if="property.removed_at" class="pc-removed">于 {{ fmtDateShort(property.removed_at) }} 从市场消失</span>
        <span v-else-if="property.added_hint">{{ property.added_hint }}</span>
        <span v-else>上架 {{ fmtDateShort(property.first_seen_at) }}</span>
      </div>
      <div v-if="property.url" class="pc-actions">
        <button class="btn mini" type="button" @click="openSource">查看原房源 ↗</button>
      </div>
    </div>
  </div>
</template>
