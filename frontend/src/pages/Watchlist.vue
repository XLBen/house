<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import { useAppStore } from '../stores/app'
import PropertyCard from '../components/PropertyCard.vue'

const router = useRouter()
const store = useAppStore()
const items = ref([])
const loading = ref(true)
const error = ref('')

const visible = computed(() =>
  items.value.filter((p) => store.watchedIds.includes(p.id))
)

async function load() {
  loading.value = true
  error.value = ''
  try {
    items.value = await api.watchlist()
    // 以服务端为准，同步 store 里的已收藏集合
    store.watchedIds = items.value.map((p) => p.id)
  } catch (e) {
    error.value = '加载失败：' + (e.message || e)
  } finally {
    loading.value = false
  }
}

// 打开 = 定位到所在区域并高亮房源（不自动弹抽屉）
function open(p) {
  if (p.regions && p.regions.length) {
    router.push({ name: 'region-detail', params: { id: p.regions[0].id }, query: { focus: p.id } })
  }
}

const refreshHandler = () => load()
onMounted(() => {
  load()
  window.addEventListener('regions-refresh', refreshHandler)
})
onBeforeUnmount(() => window.removeEventListener('regions-refresh', refreshHandler))
</script>

<template>
  <div>
    <div class="panel">
      <h2>我的收藏 <span class="muted">{{ visible.length }} 套</span></h2>
      <p class="muted" style="color:var(--rm-muted); font-size:12px;">收藏的房源如有价格变化或消失，可在「变化记录」中追踪。</p>
    </div>
    <div v-if="error" class="panel"><div class="empty">{{ error }}</div></div>
    <div v-if="loading" class="empty">加载中…</div>
    <div v-else-if="!visible.length" class="empty">还没有收藏。在房源卡片上点击 ★ 即可收藏。</div>
    <div v-else class="prop-grid">
      <PropertyCard v-for="p in visible" :key="p.id" :property="p" @open="open" />
    </div>
  </div>
</template>
