import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ComparisonSummary from '../ComparisonSummary.vue'

describe('ComparisonSummary', () => {
  it('首次同步展示横幅而非数字卡片', () => {
    const w = mount(ComparisonSummary, {
      props: { changes: {}, firstSync: true, activeCount: 5 }
    })
    expect(w.text()).toContain('首次同步')
    expect(w.text()).toContain('5')
  })

  it('新增/已下架卡片可点击并触发 select-tab', async () => {
    const w = mount(ComparisonSummary, {
      props: {
        changes: { new: [1, 2], delisted: [1], price_changes: [] },
        firstSync: false,
        selectable: true
      }
    })
    const cards = w.findAll('.cs-card')
    await cards[0].trigger('click')
    expect(w.emitted('select-tab')[0]).toEqual(['new'])
    await cards[1].trigger('click')
    expect(w.emitted('select-tab')[1]).toEqual(['removed'])
  })

  it('selectable=false 时点击不触发事件（Changes 页仅展示）', async () => {
    const w = mount(ComparisonSummary, {
      props: {
        changes: { new: [], delisted: [], price_changes: [] },
        firstSync: false,
        selectable: false
      }
    })
    await w.find('.cs-card').trigger('click')
    expect(w.emitted('select-tab')).toBeUndefined()
  })

  it('compact 时不渲染状态变化卡片', () => {
    const w = mount(ComparisonSummary, {
      props: {
        changes: { new: [], delisted: [], price_changes: [], status_changes: [] },
        firstSync: false,
        compact: true
      }
    })
    expect(w.text()).not.toContain('状态变化')
  })
})
