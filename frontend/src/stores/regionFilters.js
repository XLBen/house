import { defineStore } from 'pinia'
import { ref } from 'vue'

const DEFAULTS = () => ({
  tab: 'active',
  q: '',
  status: '',
  bedrooms: '',
  property_type: '',
  min_price: '',
  max_price: '',
  new_in_days: '',
  sort: 'newest',
  page: 1
})

export const useRegionFiltersStore = defineStore('regionFilters', () => {
  const f = ref(DEFAULTS())
  const pageSize = ref(18)
  // 已下架总数（独立轻量统计，用于 tab 角标）
  const removedTotal = ref(0)

  function reset() {
    f.value = DEFAULTS()
  }

  function apply(patch) {
    f.value = { ...f.value, ...patch }
  }

  function setTab(tab) {
    if (tab === 'removed') {
      apply({ tab, status: 'removed', new_in_days: '', sort: 'newest', page: 1 })
    } else if (tab === 'new') {
      apply({ tab, status: '', new_in_days: 7, sort: 'newest', page: 1 })
    } else {
      apply({ tab: 'active', status: '', new_in_days: '', page: 1 })
    }
  }

  // 根据当前筛选推断应高亮的 tab（保证 tab 与筛选下拉永不矛盾）
  function deriveTab() {
    if (f.value.status === 'removed') return 'removed'
    if (f.value.new_in_days) return 'new'
    return 'active'
  }

  function toQuery() {
    const q = {}
    const st = f.value
    const tab = deriveTab()
    if (tab !== 'active') q.tab = tab
    if (st.q) q.q = st.q
    if (st.status && tab === 'active') q.status = st.status
    if (st.bedrooms) q.bedrooms = st.bedrooms
    if (st.property_type) q.pt = st.property_type
    if (st.min_price) q.min = st.min_price
    if (st.max_price) q.max = st.max_price
    if (st.sort !== 'newest') q.sort = st.sort
    if (st.page > 1) q.page = String(st.page)
    return q
  }

  function fromQuery(query) {
    const nf = DEFAULTS()
    nf.tab = query.tab || 'active'
    if (nf.tab === 'removed') {
      nf.status = 'removed'
    } else if (nf.tab === 'new') {
      nf.new_in_days = 7
      nf.sort = 'newest'
    } else {
      nf.status = query.status || ''
    }
    nf.q = query.q || ''
    nf.bedrooms = query.bedrooms || ''
    nf.property_type = query.pt || ''
    nf.min_price = query.min || ''
    nf.max_price = query.max || ''
    nf.sort = query.sort || 'newest'
    nf.page = Number(query.page) || 1
    f.value = nf
  }

  return { f, pageSize, removedTotal, reset, apply, setTab, deriveTab, toQuery, fromQuery }
})
