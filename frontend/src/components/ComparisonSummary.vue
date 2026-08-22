<script setup>
import { computed } from 'vue'

const props = defineProps({
  changes: { type: Object, default: null },
  firstSync: { type: Boolean, default: false },
  activeCount: { type: Number, default: 0 },
  compact: { type: Boolean, default: false },
  selectable: { type: Boolean, default: false }
})
const emit = defineEmits(['select-tab'])

const added = computed(() => props.changes?.new?.length ?? 0)
const removed = computed(() => props.changes?.delisted?.length ?? 0)
const priced = computed(() => props.changes?.price_changes?.length ?? 0)
const status = computed(() => props.changes?.status_changes?.length ?? 0)
</script>

<template>
  <div v-if="firstSync" class="cs cs-first">
    <strong>首次同步</strong>：共发现 {{ activeCount }} 套挂牌房源。接下来每天 0 点自动对比，报告新增、调价与已下架。
  </div>
  <div v-else class="cs">
    <div class="cs-card cs-new" :class="{ selectable }" @click="selectable && emit('select-tab', 'new')">
      <div class="cs-num">{{ added }}</div>
      <div class="cs-label">本次新增</div>
    </div>
    <div class="cs-card cs-removed" :class="{ selectable }" @click="selectable && emit('select-tab', 'removed')">
      <div class="cs-num">{{ removed }}</div>
      <div class="cs-label">本次已下架</div>
    </div>
    <div class="cs-card cs-price" :class="{ selectable }" @click="selectable && emit('select-tab', 'price')">
      <div class="cs-num">{{ priced }}</div>
      <div class="cs-label">本次调价</div>
    </div>
    <div v-if="!compact" class="cs-card" :class="{ selectable }" @click="selectable && emit('select-tab', 'status')">
      <div class="cs-num">{{ status }}</div>
      <div class="cs-label">状态变化</div>
    </div>
  </div>
</template>
