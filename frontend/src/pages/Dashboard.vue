<script setup>
import { ref, onMounted, onBeforeUnmount, computed } from 'vue'
import { useRouter } from 'vue-router'
import { api, fmtPrice } from '../api'
import { useAppStore } from '../stores/app'

const router = useRouter()
const store = useAppStore()
const creating = ref(false)
const changes = ref({})
const form = ref({ name: '', center_postcode: '', radius_km: 2.0 })

const GRADIENTS = [
  'linear-gradient(135deg,#0ba6a0,#077f7b)',
  'linear-gradient(135deg,#3f6cff,#6aa0ff)',
  'linear-gradient(135deg,#f5a623,#f7c948)',
  'linear-gradient(135deg,#8e44ad,#c39bd3)',
  'linear-gradient(135deg,#e05555,#f28c8c)',
  'linear-gradient(135deg,#1f8f4d,#4cba6c)'
]

async function load() {
  await store.loadRegions()
  for (const r of store.regions) {
    try {
      changes.value[r.id] = await api.regionChanges(r.id, { since: 'last_sync' })
    } catch (e) {}
  }
}

// 添加区域是明确的"配置"动作，绝不伪装成搜索
async function create() {
  if (!form.value.name || !form.value.center_postcode) {
    store.toast('请填写区域名称和中心邮编', 'error')
    return
  }
  creating.value = true
  try {
    const region = await api.createRegion(form.value)
    store.toast(`已添加区域「${region.name}」，将于下次同步捕捉房源`, 'success')
    form.value = { name: '', center_postcode: '', radius_km: 2.0 }
    router.push({ name: 'region-detail', params: { id: region.id } })
  } catch (e) {
    store.toast('添加失败：' + (e.message || e), 'error')
  } finally {
    creating.value = false
  }
}

function openRegion(r) {
  router.push({ name: 'region-detail', params: { id: r.id } })
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
    <div class="hero">
      <h1>追踪英国任意区域</h1>
      <p>输入中心邮编和半径，系统每天 0 点自动对比，捕捉新增、调价与已下架房源。</p>
      <form class="add-region" @submit.prevent="create">
        <input v-model="form.name" placeholder="区域名称，如：Bermondsey" aria-label="区域名称" />
        <input v-model="form.center_postcode" placeholder="中心邮编，如 SE16 2UG" aria-label="中心邮编" />
        <label class="radius-field">
          <input v-model.number="form.radius_km" type="number" step="0.5" min="0.5" aria-label="半径" />
          <span>km</span>
        </label>
        <button class="btn-green" type="submit" :disabled="creating">
          {{ creating ? '添加中…' : '＋ 添加并追踪区域' }}
        </button>
      </form>
    </div>

    <div v-if="store.regionsLoading" class="empty">加载中…</div>
    <div v-else-if="!store.regions.length" class="empty">
      <p style="font-size:16px; margin-bottom:8px;">还没有追踪任何区域</p>
      <p>在上方填写邮编和区域名称，即可开始捕捉该区域的新挂牌房源。</p>
    </div>

    <div class="prop-grid">
      <div
        v-for="(r, i) in store.regions"
        :key="r.id"
        class="rm-card"
        role="button"
        tabindex="0"
        :aria-label="`查看区域 ${r.name}`"
        @click="openRegion(r)"
        @keydown.enter="openRegion(r)"
      >
        <div class="rm-card-photo" :style="{ background: GRADIENTS[i % GRADIENTS.length] }">
          {{ r.name.slice(0, 1) }}
          <span v-if="r.is_active" class="badge badge-pos">活跃</span>
        </div>
        <div class="rm-card-body">
          <div class="addr">{{ r.name }}</div>
          <div class="meta">{{ r.center_postcode }} · 半径 {{ r.radius_km }}km
            <span v-if="r.last_sync && r.last_sync.status === 'error'" class="badge red">⚠️ 同步失败</span>
            <span v-else-if="r.last_sync && r.last_sync.complete === false" class="badge red">⚠️ 可能不全</span>
          </div>
          <div class="price">{{ fmtPrice(r.stats?.avg_price) }}</div>
          <div class="meta">挂牌 {{ r.stats?.active_count ?? 0 }} · 均价</div>
          <div class="cs-mini">
            <span class="cs-mini-new">新增 {{ changes[r.id]?.new?.length ?? 0 }}</span>
            <span class="cs-mini-removed">已下架 {{ changes[r.id]?.delisted?.length ?? 0 }}</span>
            <span class="cs-mini-price">调价 {{ changes[r.id]?.price_changes?.length ?? 0 }}</span>
          </div>
          <div class="meta" style="margin-top:8px;">
            上次同步：{{ r.last_synced_at ? new Date(r.last_synced_at).toLocaleString('en-GB') : '从未' }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
