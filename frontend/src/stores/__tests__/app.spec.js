import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const mockApi = vi.hoisted(() => ({
  watchAdd: vi.fn(),
  watchRemove: vi.fn(),
  listRegions: vi.fn(),
  syncAll: vi.fn(),
  syncRegion: vi.fn(),
  watchlist: vi.fn()
}))

vi.mock('../../api', () => ({ api: mockApi }))

import { useAppStore } from '../app'

describe('app store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    mockApi.watchAdd.mockResolvedValue({ watched: true })
    mockApi.watchRemove.mockResolvedValue(null)
  })

  it('toggleWatch 添加收藏并调用 watchAdd', async () => {
    const s = useAppStore()
    await s.toggleWatch(42)
    expect(s.watchedIds).toContain(42)
    expect(mockApi.watchAdd).toHaveBeenCalledWith(42)
    expect(s.toasts.length).toBe(1)
  })

  it('toggleWatch 失败时回滚', async () => {
    mockApi.watchAdd.mockRejectedValueOnce(new Error('boom'))
    const s = useAppStore()
    await s.toggleWatch(42)
    expect(s.watchedIds).not.toContain(42)
    expect(s.toasts.some(t => t.type === 'error')).toBe(true)
  })

  it('toggleWatch 取消收藏', async () => {
    const s = useAppStore()
    s.watchedIds = [42]
    await s.toggleWatch(42)
    expect(s.watchedIds).not.toContain(42)
    expect(mockApi.watchRemove).toHaveBeenCalledWith(42)
  })

  it('toast 自动消失', async () => {
    vi.useFakeTimers()
    const s = useAppStore()
    s.toast('hello', 'success')
    expect(s.toasts.length).toBe(1)
    vi.advanceTimersByTime(4000)
    expect(s.toasts.length).toBe(0)
    vi.useRealTimers()
  })
})
