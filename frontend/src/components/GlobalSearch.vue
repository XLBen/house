<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { api, fmtPrice, STATUS_LABELS } from '../api'

const router = useRouter()
const q = ref('')
const results = ref([])
const show = ref(false)
const searched = ref(false)
const root = ref(null)
let timer = null

function onClickOutside(e) {
  if (root.value && !root.value.contains(e.target)) show.value = false
}

onMounted(() => document.addEventListener('click', onClickOutside))
onBeforeUnmount(() => document.removeEventListener('click', onClickOutside))

async function onInput() {
  clearTimeout(timer)
  searched.value = false
  if (q.value.trim().length < 2) { results.value = []; return }
  timer = setTimeout(async () => {
    try {
      results.value = await api.search(q.value.trim())
      searched.value = true
      show.value = true
    } catch (e) {
      results.value = []
      searched.value = true
    }
  }, 300)
}

// 搜索只负责定位：跳转到区域并滚动高亮该房源，不自动弹抽屉
function open(p) {
  show.value = false
  q.value = ''
  if (p.regions && p.regions.length) {
    router.push({ name: 'region-detail', params: { id: p.regions[0].id }, query: { focus: p.id } })
  }
}
</script>

<template>
  <div class="gsearch" ref="root">
    <input
      v-model="q"
      type="search"
      role="searchbox"
      :aria-label="'跨区域搜索'"
      @input="onInput"
      @focus="results.length && (show = true)"
      placeholder="🔍 跨区域搜索地址 / 邮编…"
    />
    <div v-if="show" class="gs-results">
      <div v-for="p in results" :key="p.id" class="gs-item" role="button" tabindex="0" @click="open(p)" @keydown.enter="open(p)">
        <div>
          <div class="gs-addr">{{ p.address }}</div>
          <div class="gs-meta">{{ p.bedrooms ?? '—' }} 卧 · {{ p.property_type || '—' }} · {{ STATUS_LABELS[p.status] || p.status }}</div>
        </div>
        <span class="gs-price">{{ fmtPrice(p.price) }}</span>
      </div>
      <div v-if="searched && !results.length" class="gs-empty">没有匹配的房源</div>
    </div>
  </div>
</template>
