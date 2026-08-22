import { describe, it, expect } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useRegionFiltersStore } from '../regionFilters'

describe('regionFilters store', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('默认值：sort=newest，tab=active', () => {
    const s = useRegionFiltersStore()
    expect(s.f.sort).toBe('newest')
    expect(s.deriveTab()).toBe('active')
  })

  it('setTab(removed) 与 deriveTab 一致', () => {
    const s = useRegionFiltersStore()
    s.setTab('removed')
    expect(s.f.status).toBe('removed')
    expect(s.deriveTab()).toBe('removed')
  })

  it('setTab(new) 设置 7 天窗口', () => {
    const s = useRegionFiltersStore()
    s.setTab('new')
    expect(s.f.new_in_days).toBe(7)
    expect(s.deriveTab()).toBe('new')
  })

  it('筛选下拉选择 removed 时 tab 自动高亮（状态一致）', () => {
    const s = useRegionFiltersStore()
    s.apply({ status: 'removed' })
    expect(s.deriveTab()).toBe('removed')
  })

  it('reset 恢复为默认值（sort 回到 newest，而非 price_desc）', () => {
    const s = useRegionFiltersStore()
    s.apply({ q: 'foo', sort: 'price_desc', status: 'removed' })
    s.reset()
    expect(s.f).toEqual({
      tab: 'active', q: '', status: '', bedrooms: '', property_type: '',
      min_price: '', max_price: '', new_in_days: '', sort: 'newest', page: 1
    })
  })

  it('toQuery / fromQuery 往返一致', () => {
    const s = useRegionFiltersStore()
    s.fromQuery({ tab: 'removed', q: 'park', min: '300000', sort: 'price_asc' })
    const q = s.toQuery()
    expect(q).toMatchObject({ tab: 'removed', q: 'park', min: '300000', sort: 'price_asc' })
    const s2 = useRegionFiltersStore()
    s2.fromQuery(q)
    expect(s2.f).toEqual(s.f)
  })
})
