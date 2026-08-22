<script setup>
import { computed } from 'vue'

const props = defineProps({ data: { type: Object, default: null } })
const emit = defineEmits(['select-type', 'select-band'])

const TYPE_LABELS = { house: '房子', flat: '公寓', other: '其他' }
const typeTotal = computed(() => {
  if (!props.data) return 0
  return Object.values(props.data.by_type).reduce((a, b) => a + b, 0)
})
const bandTotal = computed(() => {
  if (!props.data) return 0
  return (props.data.price_bands || []).reduce((a, b) => a + b.count, 0)
})

function pct(n, total) {
  if (!total) return 0
  return Math.round(n / total * 100)
}
</script>

<template>
  <div v-if="data" class="classbar">
    <div class="cb-block">
      <div class="cb-title">物业类型</div>
      <div class="cb-bars">
        <div
          v-for="(count, type) in data.by_type"
          :key="type"
          class="cb-item"
          :title="`${TYPE_LABELS[type] || type}: ${count}`"
          @click="emit('select-type', type)"
        >
          <div class="cb-label">{{ TYPE_LABELS[type] || type }} {{ count }}</div>
          <div class="cb-track">
            <div class="cb-fill" :style="{ width: pct(count, typeTotal) + '%' }"></div>
          </div>
        </div>
      </div>
    </div>
    <div class="cb-block">
      <div class="cb-title">价格区间（区域自适应）</div>
      <div class="cb-bars">
        <div
          v-for="band in data.price_bands"
          :key="band.label"
          class="cb-item"
          :title="`${band.label}: ${band.count}`"
          @click="emit('select-band', band)"
        >
          <div class="cb-label">{{ band.label }} · {{ band.count }}</div>
          <div class="cb-track">
            <div class="cb-fill" :style="{ width: pct(band.count, bandTotal) + '%' }"></div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
