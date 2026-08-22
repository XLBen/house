<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { api, fmtPrice, fmtDate } from '../api'
import { useAppStore } from '../stores/app'
import { useRegionFiltersStore } from '../stores/regionFilters'
import FilterBar from '../components/FilterBar.vue'
import ClassificationBar from '../components/ClassificationBar.vue'
import ComparisonSummary from '../components/ComparisonSummary.vue'
import PropertyCard from '../components/PropertyCard.vue'
import PropertyDrawer from '../components/PropertyDrawer.vue'
import MapView from '../components/MapView.vue'

const props = defineProps({ id: { type: [String, Number], required: true } })
const router = useRouter()
const route = useRoute()
const store = useAppStore()
const filters = useRegionFiltersStore()

const region = ref(null)
const stats = ref(null)
const classification = ref(null)
const changes = ref(null)
const properties = ref([])
const total = ref(0)
const syncing = ref(false)
const firstSync = ref(false)
const selected = ref(null)
const showMap = ref(false)
const mapData = ref(null)
const focusId = ref(null)
const listLoading = ref(false)
let filterTimer = null

const activeTab = computed(() => filters.deriveTab())

async function loadRegions() {
  await store.loadRegions()
}

async function loadRegion() {
  region.value = await api.getRegion(props.id)
  store.setCurrentRegion(props.id)
}

async function loadStats() {
  stats.value = await api.regionStats(props.id)
}

async function loadChanges() {
  changes.value = await api.regionChanges(props.id, { since: 'last_sync' })
  firstSync.value = changes.value?.is_first_sync ?? false
}

async function loadRemovedTotal() {
  try {
    const res = await api.regionProperties(props.id, { status: 'removed', page_size: 1 })
    filters.removedTotal = res.total
  } catch (e) {
    filters.removedTotal = 0
  }
}

async function loadProperties() {
  listLoading.value = true
  try {
    const st = filters.f
    const params = { sort: st.sort, page: st.page, page_size: filters.pageSize }
    if (st.status) params.status = st.status
    if (st.bedrooms) params.bedrooms = st.bedrooms
    if (st.property_type) params.property_type = st.property_type
    if (st.min_price) params.min_price = st.min_price
    if (st.max_price) params.max_price = st.max_price
    if (st.new_in_days) params.new_in_days = st.new_in_days
    if (st.q) params.q = st.q
    const res = await api.regionProperties(props.id, params)
    properties.value = res.items
    total.value = res.total
    maybeFocusCard()
  } finally {
    listLoading.value = false
  }
}

async function loadAll() {
  await Promise.all([loadRegions(), loadRegion(), loadStats(), loadChanges()])
  await Promise.all([loadProperties(), loadRemovedTotal()])
}

// —— 搜索/收藏定位：滚动高亮卡片；若不在当前列表则打开详情（带加载态）——
function maybeFocusCard() {
  if (!focusId.value) return
  requestAnimationFrame(() => {
    const el = document.querySelector(`[data-prop-id="${focusId.value}"]`)
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' })
      el.classList.add('focused')
      setTimeout(() => el.classList.remove('focused'), 2000)
    } else {
      selected.value = Number(focusId.value)
    }
    focusId.value = null
  })
}

function handleQuery(q) {
  const clean = { ...q }
  if (clean.focus != null) {
    focusId.value = Number(clean.focus)
    delete clean.focus
    router.replace({ query: clean })
  }
  // 避免在自身写入 URL 引起的回环中重复解析
  if (JSON.stringify(clean) !== JSON.stringify(filters.toQuery())) {
    filters.fromQuery(clean)
  }
}

// 深度监听筛选 → 防抖加载列表 + 同步 URL（单一触发路径，杜绝双重 fetch）
watch(() => filters.f, () => {
  clearTimeout(filterTimer)
  filterTimer = setTimeout(() => {
    loadProperties()
    router.replace({ query: filters.toQuery() })
  }, 350)
}, { deep: true })

watch(() => props.id, async () => {
  filters.reset()
  loadAll()
  showMap.value = false
  mapData.value = null
  selected.value = null
})

watch(() => route.query, (next) => handleQuery(next), { deep: true })

async function sync() {
  syncing.value = true
  try {
    await store.syncRegion(props.id)
    await loadAll()
  } finally {
    syncing.value = false
  }
}

async function exportXlsx() {
  const res = await api.exportRegion(props.id)
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${region.value.name}.xlsx`
  a.click()
  URL.revokeObjectURL(url)
}

function openDrawer(p) {
  selected.value = p.id
}

// ComparisonSummary 的 新增/已下架 → 切 tab；调价/状态 → 去变化记录页
function selectTab(tab) {
  if (tab === 'new' || tab === 'removed') {
    filters.setTab(tab)
  } else {
    router.push({ name: 'changes', query: { region: props.id, since: 'last_sync' } })
  }
}

function prevNext(dir) {
  const idx = store.regions.findIndex(r => r.id === Number(props.id))
  if (idx === -1) return
  const next = store.regions[(idx + dir + store.regions.length) % store.regions.length]
  router.push({ name: 'region-detail', params: { id: next.id } })
}

async function toggleMap() {
  showMap.value = !showMap.value
  if (showMap.value && !mapData.value) {
    mapData.value = await api.regionMap(props.id)
  }
}

const activeCount = computed(() => stats.value?.active_count ?? 0)
const refreshHandler = () => loadAll()

onMounted(() => {
  window.addEventListener('regions-refresh', refreshHandler)
  loadAll()
})
onBeforeUnmount(() => window.removeEventListener('regions-refresh', refreshHandler))
</script>

<template>
  <div v-if="region">
    <!-- 面包屑 + 标题 + 操作 -->
    <div class="panel region-head">
      <nav class="crumbs" aria-label="面包屑">
        <router-link to="/">总览</router-link>
        <span class="crumb-sep">›</span>
        <span>{{ region.name }}</span>
      </nav>
      <div class="ws-title-row">
        <button class="btn mini gray" type="button" aria-label="上一个区域" @click="prevNext(-1)">‹</button>
        <h2 class="region-title">{{ region.name }}</h2>
        <button class="btn mini gray" type="button" aria-label="下一个区域" @click="prevNext(1)">›</button>
        <span v-if="firstSync" class="badge amber">首次同步</span>
        <span v-if="region.last_sync && region.last_sync.status === 'error'" class="badge red" title="上次同步失败，数据可能过旧">
          ⚠️ 上次同步失败
        </span>
        <span v-if="region.last_sync && region.last_sync.complete === false" class="badge red" title="超过抓取页数上限或翻页失败，可能未覆盖全部房源">
          ⚠️ 结果可能不完整
        </span>
      </div>
      <div class="ws-sub">
        {{ region.center_postcode }} · 半径 {{ region.radius_km }}km ·
        上次同步 {{ fmtDate(region.last_synced_at) }}
      </div>
      <div class="region-actions">
        <button class="btn-green" type="button" @click="sync" :disabled="syncing || store.syncing">
          {{ syncing ? '⏳ 同步中…' : '⏱ 立即同步' }}
        </button>
        <button class="btn" type="button" @click="exportXlsx">⬇ 导出</button>
      </div>

      <div class="stat-row">
        <div class="stat"><div class="v">{{ stats?.active_count }}</div><div class="k">挂牌中</div></div>
        <div class="stat"><div class="v">{{ fmtPrice(stats?.avg_price) }}</div><div class="k">均价</div></div>
        <div class="stat"><div class="v">{{ fmtPrice(stats?.median_price) }}</div><div class="k">中位数</div></div>
        <div class="stat"><div class="v">{{ fmtPrice(stats?.min_price) }}</div><div class="k">最低</div></div>
        <div class="stat"><div class="v">{{ fmtPrice(stats?.max_price) }}</div><div class="k">最高</div></div>
        <div class="stat"><div class="v">{{ stats?.new_today }}</div><div class="k">今日新增</div></div>
        <div class="stat"><div class="v">{{ stats?.delisted_today }}</div><div class="k">今日已下架</div></div>
      </div>
    </div>

    <!-- 房源列表（主内容） -->
    <div class="panel">
      <h2 class="list-heading">
        房源列表
        <span class="muted">{{ total }} 套</span>
      </h2>

      <ComparisonSummary
        :changes="changes"
        :first-sync="firstSync"
        :active-count="activeCount"
        :selectable="true"
        @select-tab="selectTab"
      />

      <div class="tabs" role="tablist">
        <button
          v-for="t in [
            { key: 'active', label: '挂牌中' },
            { key: 'new', label: '新增' },
            { key: 'removed', label: `已下架(${filters.removedTotal})` }
          ]"
          :key="t.key"
          type="button"
          role="tab"
          :class="{ on: activeTab === t.key }"
          :aria-selected="activeTab === t.key"
          @click="filters.setTab(t.key)"
        >{{ t.label }}</button>
      </div>

      <FilterBar v-model="filters.f" />

      <div v-if="listLoading" class="empty">加载中…</div>
      <div v-else class="prop-grid">
        <PropertyCard
          v-for="p in properties"
          :key="p.id"
          :property="p"
          :data-prop-id="p.id"
          @open="openDrawer"
        />
      </div>
      <div v-if="!listLoading && !properties.length" class="empty">没有符合条件的房源</div>

      <div class="pager">
        <button class="btn" type="button" :disabled="filters.f.page <= 1" @click="filters.f.page--">上一页</button>
        <span class="muted">第 {{ filters.f.page }} 页</span>
        <button class="btn" type="button" :disabled="filters.f.page * filters.pageSize >= total" @click="filters.f.page++">下一页</button>
      </div>
    </div>

    <!-- 次级数据（可折叠） -->
    <details class="panel" open>
      <summary>降价榜<template v-if="stats?.biggest_drops?.length">（{{ stats.biggest_drops.length }}）</template></summary>
      <div v-if="!stats?.biggest_drops?.length" class="empty">暂无可比降价房源</div>
      <div v-else class="drop-list">
        <div v-for="d in stats.biggest_drops" :key="d.id" class="drop-item" role="button" tabindex="0" @click="openDrawer(d)" @keydown.enter="openDrawer(d)">
          <div>
            <div class="drop-addr">{{ d.address }}</div>
            <div class="drop-meta">{{ fmtPrice(d.current_price) }} <span class="drop-bad">▼ {{ fmtPrice(d.drop_amount) }}（{{ d.drop_pct }}%）</span></div>
          </div>
        </div>
      </div>
    </details>

    <details class="panel">
      <summary>房源分类</summary>
      <ClassificationBar :data="classification" @select-type="(t) => { filters.apply({ property_type: t }); }" @select-band="(b) => { filters.apply({ min_price: String(b.min), max_price: String(b.max) }); }" />
      <div v-if="!classification" class="empty">暂无分类数据</div>
    </details>

    <details class="panel">
      <summary>地图（区域范围）</summary>
      <button class="map-toggle" type="button" @click="toggleMap">
        {{ showMap ? '▲ 收起地图' : '▼ 加载地图' }}
      </button>
      <div v-if="showMap"><MapView :data="mapData" /></div>
      <div v-if="!showMap" class="map-hint">房源坐标由数据源决定；OnTheMarket 不提供坐标时地图只显示区域圈。</div>
    </details>
  </div>
  <div v-else class="empty">加载中…</div>

  <PropertyDrawer v-if="selected" :property-id="selected" @close="selected = null" />
</template>
