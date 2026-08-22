<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { api, fmtDate } from '../api'
import { useAppStore } from '../stores/app'

const router = useRouter()
const store = useAppStore()
const runs = ref([])
const editing = ref(null)
const confirmDelete = ref(null)
const form = ref({ name: '', center_postcode: '', radius_km: 2.0, is_active: true })
const loading = ref(false)
const error = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try {
    await store.loadRegions()
    runs.value = await api.syncRuns({ limit: 15 })
  } catch (e) {
    error.value = '加载失败：' + (e.message || e)
  } finally {
    loading.value = false
  }
}

function startEdit(r) {
  editing.value = r.id
  form.value = { name: r.name, center_postcode: r.center_postcode, radius_km: r.radius_km, is_active: r.is_active }
}

async function saveEdit() {
  await api.updateRegion(editing.value, form.value)
  editing.value = null
  await load()
}

async function toggleActive(r) {
  await api.updateRegion(r.id, { is_active: !r.is_active })
  await load()
}

async function remove(r) {
  await api.deleteRegion(r.id)
  confirmDelete.value = null
  store.toast(`已删除区域「${r.name}」`, 'success')
  await load()
}

async function sync(r) {
  await store.syncRegion(r.id)
  await load()
}

function openDetail(r) {
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
    <div class="panel">
      <div class="management-head">
        <h2>区域管理</h2>
        <div>
          <router-link class="btn" to="/">＋ 添加新区域</router-link>
          <button class="btn-green" type="button" :disabled="store.syncing" @click="store.syncAll">
            {{ store.syncing ? '⏳ 同步中…' : '⏱ 同步全部' }}
          </button>
        </div>
      </div>
      <div v-if="error" class="empty">{{ error }}</div>
      <table v-else>
        <thead>
          <tr>
            <th>名称</th><th>中心邮编</th><th>半径</th><th>状态</th>
            <th>上次同步</th><th>在售</th><th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in store.regions" :key="r.id">
            <td><a class="table-link" href="#" @click.prevent="openDetail(r)">{{ r.name }}</a></td>
            <td>{{ r.center_postcode }}</td>
            <td>{{ r.radius_km }} km</td>
            <td>
              <span class="badge" :class="r.is_active ? '' : 'gray'">{{ r.is_active ? '活跃' : '已停用' }}</span>
            </td>
            <td class="muted">{{ fmtDate(r.last_synced_at) }}</td>
            <td>{{ r.stats?.active_count ?? 0 }}</td>
            <td>
              <template v-if="confirmDelete === r.id">
                <span class="confirm-text">确认删除？</span>
                <button class="btn danger" type="button" @click="remove(r)">确认</button>
                <button class="btn" type="button" @click="confirmDelete = null">取消</button>
              </template>
              <template v-else>
                <span class="row-actions">
                  <button class="btn" type="button" @click="sync(r)">同步</button>
                  <button v-if="editing !== r.id" class="btn" type="button" @click="startEdit(r)">编辑</button>
                  <template v-else>
                    <button class="btn-green" type="button" @click="saveEdit">保存</button>
                    <button class="btn" type="button" @click="editing = null">取消</button>
                  </template>
                  <button class="btn" type="button" @click="toggleActive(r)">{{ r.is_active ? '停用' : '启用' }}</button>
                  <button class="btn danger" type="button" @click="confirmDelete = r.id">删除</button>
                </span>
              </template>
            </td>
          </tr>
          <tr v-if="!store.regions.length"><td colspan="7" class="empty">暂无区域，去「总览」添加一个</td></tr>
        </tbody>
      </table>

      <div v-if="editing" class="edit-form">
        <input v-model="form.name" placeholder="名称" aria-label="名称" />
        <input v-model="form.center_postcode" placeholder="中心邮编" aria-label="中心邮编" />
        <input v-model.number="form.radius_km" type="number" step="0.5" min="0.5" aria-label="半径" />
        <span class="muted">km</span>
      </div>
    </div>

    <div class="panel">
      <h2>同步日志</h2>
      <table>
        <thead>
          <tr><th>时间</th><th>区域</th><th>状态</th><th>新增</th><th>调价</th><th>下架</th><th>错误</th></tr>
        </thead>
        <tbody>
          <tr v-for="run in runs" :key="run.id">
            <td class="muted">{{ fmtDate(run.started_at) }}</td>
            <td>{{ store.regions.find(r => r.id === run.region_id)?.name || (run.region_id ? '#' + run.region_id : '全部') }}</td>
            <td>
              <span class="badge" :class="run.status === 'success' ? '' : run.status === 'error' ? 'red' : 'amber'">
                {{ run.status === 'running' ? '运行中' : run.status === 'success' ? '成功' : '失败' }}
              </span>
            </td>
            <td>{{ run.new_count }}</td>
            <td>{{ run.price_changed_count }}</td>
            <td>{{ run.delisted_count }}</td>
            <td class="muted run-error">{{ run.error || '' }}</td>
          </tr>
          <tr v-if="!runs.length"><td colspan="7" class="empty">还没有同步记录</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
