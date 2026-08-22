<script setup>
import { onMounted } from 'vue'
import { useAppStore } from './stores/app'
import RegionSwitcher from './components/RegionSwitcher.vue'
import GlobalSearch from './components/GlobalSearch.vue'
import ToastStack from './components/ToastStack.vue'

const store = useAppStore()

onMounted(() => {
  store.loadRegions()
  store.loadWatched()
})
</script>

<template>
  <div class="site">
    <header class="topbar">
      <div class="topbar-inner">
        <router-link to="/" class="brand">ukhouse<span class="dot">invest</span></router-link>
        <GlobalSearch />
        <div class="topbar-right">
          <RegionSwitcher />
        </div>
      </div>
    </header>

    <nav class="mainnav" aria-label="主导航">
      <router-link to="/">总览</router-link>
      <router-link to="/regions">区域管理</router-link>
      <router-link to="/changes">变化记录</router-link>
      <router-link to="/watchlist">我的收藏</router-link>
    </nav>

    <main class="main">
      <router-view />
    </main>

    <footer class="footer">
      <div class="footer-inner">
        <div>
          <div class="f-title">ukhouseinvest</div>
          <div>英国区域房价监控：捕捉新增 · 调价 · 已下架</div>
        </div>
        <div>
          <div class="f-title">数据源</div>
          <div>OnTheMarket（默认）· Rightmove（备用）· mock（离线演示）</div>
        </div>
      </div>
    </footer>

    <ToastStack />
  </div>
</template>
