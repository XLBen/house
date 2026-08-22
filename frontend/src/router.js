import { createRouter, createWebHistory } from 'vue-router'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'dashboard', component: () => import('./pages/Dashboard.vue') },
    { path: '/regions', name: 'regions', component: () => import('./pages/Regions.vue') },
    { path: '/region/:id', name: 'region-detail', component: () => import('./pages/RegionDetail.vue'), props: true },
    { path: '/changes', name: 'changes', component: () => import('./pages/Changes.vue') },
    { path: '/watchlist', name: 'watchlist', component: () => import('./pages/Watchlist.vue') }
  ]
})
