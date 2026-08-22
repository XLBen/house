<script setup>
import { computed } from 'vue'

const props = defineProps({ modelValue: { type: Object, required: true } })
const emit = defineEmits(['update:modelValue'])

const f = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v)
})

function set(key, value) {
  emit('update:modelValue', { ...f.value, [key]: value })
}

const BANDS = [
  { min: '', max: 200000, label: '<£200k' },
  { min: 200000, max: 400000, label: '£200-400k' },
  { min: 400000, max: 700000, label: '£400-700k' },
  { min: 700000, max: '', label: '>£700k' }
]

function bandActive(band) {
  return String(f.value.min_price) === String(band.min) && String(f.value.max_price) === String(band.max)
}

function quickBand(band) {
  // 点击已激活的档位 = 取消该价格筛选
  if (bandActive(band)) {
    set('min_price', '')
    set('max_price', '')
  } else {
    set('min_price', band.min)
    set('max_price', band.max)
  }
}

function reset() {
  emit('update:modelValue', {
    q: '', status: '', bedrooms: '', property_type: '',
    min_price: '', max_price: '', sort: 'newest', new_in_days: ''
  })
}
</script>

<template>
  <div class="filterbar">
    <input :value="f.q" type="search" :aria-label="'地址关键词'" @input="set('q', $event.target.value)" placeholder="地址 / 邮编关键词" class="fb-input" />
    <select :value="f.status" :aria-label="'状态'" @change="set('status', $event.target.value)">
      <option value="">全部状态</option>
      <option value="under_offer">已接受报价</option>
      <option value="removed">已下架</option>
    </select>
    <select :value="f.property_type" :aria-label="'物业类型'" @change="set('property_type', $event.target.value)">
      <option value="">全部类型</option>
      <option value="house">房子（含各类 House）</option>
      <option value="flat">公寓 / Flat</option>
      <option value="apartment">Apartment</option>
      <option value="terraced house">Terraced</option>
      <option value="semi-detached house">Semi-Detached</option>
      <option value="detached house">Detached</option>
      <option value="bungalow">Bungalow</option>
      <option value="maisonette">Maisonette</option>
    </select>
    <select :value="f.bedrooms" :aria-label="'卧室数'" @change="set('bedrooms', $event.target.value)">
      <option value="">卧室不限</option>
      <option v-for="n in [1,2,3,4,5]" :key="n" :value="String(n)">{{ n }} 卧</option>
    </select>
    <input :value="f.min_price" type="number" :aria-label="'最低价'" placeholder="最低价 £" class="fb-num" @input="set('min_price', $event.target.value)" />
    <input :value="f.max_price" type="number" :aria-label="'最高价'" placeholder="最高价 £" class="fb-num" @input="set('max_price', $event.target.value)" />
    <select :value="f.sort" :aria-label="'排序'" @change="set('sort', $event.target.value)">
      <option value="price_desc">价格 高→低</option>
      <option value="price_asc">价格 低→高</option>
      <option value="newest">最新上架</option>
      <option value="reduced">优先降价</option>
      <option value="beds_desc">卧室最多</option>
    </select>
    <div class="fb-bands" role="group" :aria-label="'快捷价格档位'">
      <button
        v-for="b in BANDS"
        :key="b.label"
        class="btn mini"
        :class="{ active: bandActive(b) }"
        type="button"
        @click="quickBand(b)"
      >{{ b.label }}</button>
      <button class="btn mini gray" type="button" @click="reset">重置</button>
    </div>
  </div>
</template>
