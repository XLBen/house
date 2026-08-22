import { defineStore } from 'pinia'
import { api } from '../api'

let toastSeq = 0

export const useAppStore = defineStore('app', {
  state: () => ({
    regions: [],
    regionsLoading: false,
    currentRegionId: null,
    watchedIds: [],
    syncing: false,
    toasts: []
  }),
  getters: {
    currentRegion: (s) =>
      s.regions.find((r) => String(r.id) === String(s.currentRegionId)) || null,
    isWatched: (s) => (id) => s.watchedIds.includes(Number(id))
  },
  actions: {
    toast(message, type = 'info') {
      const id = ++toastSeq
      this.toasts.push({ id, message, type })
      setTimeout(() => this.dismissToast(id), 3500)
    },
    dismissToast(id) {
      this.toasts = this.toasts.filter((t) => t.id !== id)
    },
    async loadRegions() {
      this.regionsLoading = true
      try {
        this.regions = await api.listRegions()
      } finally {
        this.regionsLoading = false
      }
    },
    async loadWatched() {
      try {
        const items = await api.watchlist()
        this.watchedIds = items.map((p) => p.id)
      } catch (e) {}
    },
    setCurrentRegion(id) {
      this.currentRegionId = id != null ? Number(id) : null
    },
    async syncAll() {
      if (this.syncing) return
      this.syncing = true
      try {
        await api.syncAll()
        await this.loadRegions()
        window.dispatchEvent(new CustomEvent('regions-refresh'))
        this.toast('同步完成', 'success')
      } catch (e) {
        this.toast('同步失败：' + (e.message || e), 'error')
      } finally {
        this.syncing = false
      }
    },
    async syncRegion(id) {
      try {
        await api.syncRegion(id)
        await this.loadRegions()
        window.dispatchEvent(new CustomEvent('regions-refresh'))
        this.toast('同步完成', 'success')
        return true
      } catch (e) {
        this.toast('同步失败：' + (e.message || e), 'error')
        return false
      }
    },
    async toggleWatch(id) {
      const nid = Number(id)
      const watched = this.watchedIds.includes(nid)
      if (watched) {
        this.watchedIds = this.watchedIds.filter((w) => w !== nid)
      } else {
        this.watchedIds = [...this.watchedIds, nid]
      }
      try {
        if (watched) await api.watchRemove(nid)
        else await api.watchAdd(nid)
        this.toast(watched ? '已取消收藏' : '已收藏', 'success')
      } catch (e) {
        // 失败回滚
        if (watched) this.watchedIds = [...this.watchedIds, nid]
        else this.watchedIds = this.watchedIds.filter((w) => w !== nid)
        this.toast('操作失败：' + (e.message || e), 'error')
      }
    }
  }
})
