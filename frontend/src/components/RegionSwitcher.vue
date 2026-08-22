<script setup>
import { ref, onBeforeUnmount, watch, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAppStore } from '../stores/app'

const router = useRouter()
const route = useRoute()
const store = useAppStore()
const open = ref(false)
const root = ref(null)

function onClickOutside(e) {
  if (root.value && !root.value.contains(e.target)) open.value = false
}

onMounted(() => document.addEventListener('click', onClickOutside))
onBeforeUnmount(() => document.removeEventListener('click', onClickOutside))

// 当前区域单一事实源 = app store；路由变化时回写
watch(
  () => route.params.id,
  (v) => {
    if (route.name === 'region-detail') store.setCurrentRegion(Number(v))
  },
  { immediate: true }
)

function go(r) {
  open.value = false
  store.setCurrentRegion(r.id)
  router.push({ name: 'region-detail', params: { id: r.id } })
}
</script>

<template>
  <div class="region-switch" ref="root">
    <button class="rs-trigger" type="button" aria-haspopup="listbox" @click="open = !open">
      <span class="rs-label">📍 区域</span>
      <span class="rs-value">
        {{ store.currentRegion?.name || '选择区域' }}
      </span>
      <span class="rs-caret">▾</span>
    </button>
    <div v-if="open" class="rs-menu" role="listbox">
      <button
        v-for="r in store.regions"
        :key="r.id"
        type="button"
        class="rs-item"
        :class="{ active: String(r.id) === String(store.currentRegionId) }"
        role="option"
        @click="go(r)"
      >
        <span>{{ r.name }}</span>
        <span class="rs-count">{{ r.stats?.active_count ?? 0 }}</span>
      </button>
      <div v-if="!store.regions.length" class="rs-empty">还没有区域，去「总览」添加</div>
    </div>
  </div>
</template>
