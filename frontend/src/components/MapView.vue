<script setup>
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import L from 'leaflet'

const props = defineProps({ data: { type: Object, default: null } })
const mapEl = ref(null)
let map = null
let layer = null

function colorFor(price, min, max) {
  if (price == null) return '#888888'
  const ratio = max > min ? (price - min) / (max - min) : 0.5
  const r = Math.round(239 - ratio * 205)
  const g = Math.round(68 - ratio * 0)
  const b = Math.round(72 + ratio * 151)
  return `rgb(${r},${g},${b})`
}

function render() {
  if (!map || !props.data) return
  if (layer) { map.removeLayer(layer); layer = null }
  const { points, center_lat, center_lng, radius_km } = props.data
  const prices = points.map(p => p.price).filter(v => v != null)
  const min = prices.length ? Math.min(...prices) : 0
  const max = prices.length ? Math.max(...prices) : 1

  layer = L.layerGroup().addTo(map)
  for (const p of points) {
    if (p.lat == null || p.lng == null) continue
    const active = p.status === 'listed' || p.status === 'under_offer'
    L.circleMarker([p.lat, p.lng], {
      radius: p.status === 'removed' ? 6 : 9,
      color: active ? colorFor(p.price, min, max) : '#888888',
      fillColor: active ? colorFor(p.price, min, max) : '#888888',
      fillOpacity: 0.75,
      weight: 1
    }).addTo(layer).bindPopup(
      `<strong>${p.address || p.listing_id}</strong><br/><b style="color:#087f7b;">£${p.price != null ? p.price.toLocaleString('en-GB') : '—'}</b> · ${p.status}`
    )
  }
  if (center_lat != null && center_lng != null) {
    L.circle([center_lat, center_lng], { radius: radius_km * 1000, color: '#0ba6a0', dashArray: '6 6', fillOpacity: 0.04 }).addTo(layer)
  }
  if (center_lat != null && center_lng != null) {
    map.setView([center_lat, center_lng], 12)
  } else if (points.length) {
    map.setView([points[0].lat, points[0].lng], 12)
  }
}

onMounted(() => {
  map = L.map(mapEl.value).setView([53.8, -1.5], 12)
  L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
    attribution: '© OpenStreetMap © CARTO',
    maxZoom: 18
  }).addTo(map)
  render()
})

watch(() => props.data, render)
onBeforeUnmount(() => { if (map) map.remove() })
</script>

<template>
  <div class="map-wrap">
    <div ref="mapEl" id="map"></div>
    <div v-if="data && !data.points.some(p => p.lat != null && p.lng != null)" class="map-empty">
      该区域房源暂无坐标，地图只显示区域中心圈
    </div>
  </div>
</template>
