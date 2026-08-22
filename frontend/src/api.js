const BASE = '/api'

async function request(path, options = {}) {
  const res = await fetch(BASE + path, {
    headers: { 'Content-Type': 'application/json' },
    ...options
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || `HTTP ${res.status}`)
  }
  if (res.status === 204) return null
  const ct = res.headers.get('content-type') || ''
  return ct.includes('json') ? res.json() : res
}

export const api = {
  listRegions: () => request('/regions'),
  getRegion: (id) => request(`/regions/${id}`),
  createRegion: (data) => request('/regions', { method: 'POST', body: JSON.stringify(data) }),
  updateRegion: (id, data) => request(`/regions/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  deleteRegion: (id) => request(`/regions/${id}`, { method: 'DELETE' }),
  syncRegion: (id) => request(`/regions/${id}/sync`, { method: 'POST' }),
  syncAll: () => request('/sync/all', { method: 'POST' }),
  exportRegion: (id) => request(`/regions/${id}/export`, { method: 'POST' }),
  exportAll: () => request('/export/all'),

  regionProperties: (id, params) => request(`/regions/${id}/properties?` + new URLSearchParams(params)),
  getProperty: (id) => request(`/properties/${id}`),
  propertyHistory: (id) => request(`/properties/${id}/history`),
  propertyEvents: (id) => request(`/properties/${id}/events`),

  regionStats: (id) => request(`/regions/${id}/stats`),
  regionMap: (id) => request(`/regions/${id}/map`),
  regionClassification: (id) => request(`/regions/${id}/classification`),
  regionChanges: (id, { date, since } = {}) => {
    const p = new URLSearchParams()
    if (date) p.set('date', date)
    if (since) p.set('since', since)
    const qs = p.toString()
    return request(`/regions/${id}/changes` + (qs ? `?${qs}` : ''))
  },
  syncRuns: (params) => request('/sync/runs?' + new URLSearchParams(params)),

  search: (q) => request('/search?q=' + encodeURIComponent(q)),
  watchlist: () => request('/watchlist'),
  watchCheck: (id) => request(`/watch/check/${id}`),
  watchAdd: (id) => request(`/watch/${id}`, { method: 'POST' }),
  watchRemove: (id) => request(`/watch/${id}`, { method: 'DELETE' })
}

export function fmtPrice(n) {
  if (n == null) return '—'
  return '£' + n.toLocaleString('en-GB')
}

export function fmtDate(s) {
  if (!s) return '—'
  return new Date(s).toLocaleString('en-GB', { dateStyle: 'medium', timeStyle: 'short' })
}

export function fmtDateShort(s) {
  if (!s) return '—'
  return new Date(s).toLocaleDateString('en-GB', { day: '2-digit', month: 'short' })
}

export const STATUS_LABELS = {
  listed: '挂牌中',
  under_offer: '已接受报价',
  sold: '已售',
  removed: '已下架'
}

export function statusClass(s) {
  if (s === 'removed') return 'gray'
  if (s === 'sold' || s === 'under_offer') return 'amber'
  return ''
}
