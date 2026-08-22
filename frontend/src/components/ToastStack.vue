<script setup>
import { useAppStore } from '../stores/app'

const store = useAppStore()
</script>

<template>
  <div class="toast-stack" aria-live="polite">
    <transition-group name="toast">
      <div v-for="t in store.toasts" :key="t.id" class="toast" :class="t.type" @click="store.dismissToast(t.id)">
        <span v-if="t.type === 'success'">✓</span>
        <span v-else-if="t.type === 'error'">✕</span>
        <span>{{ t.message }}</span>
      </div>
    </transition-group>
  </div>
</template>
