<template>
    <span v-if="showLabel" class="pf-with-label">
      <img v-if="imgSrc" class="pf-ico" :src="imgSrc" :alt="title" :title="title" @error="onImgError"
        :style="{ background: (bg==='\u0023ffffff' ? 'transparent' : bg), width: px, height: px }" />
    <span v-else class="pf-abbr" :title="title" :style="{ width: px, height: px, fontSize: fs }">{{ abbr }}</span>
    <span class="pf-label">{{ title || name }}</span>
  </span>
    <img v-else-if="imgSrc" class="pf-ico" :src="imgSrc" :alt="title" :title="title" @error="onImgError"
      :style="{ background: (bg==='\u0023ffffff' ? 'transparent' : bg), width: px, height: px }" />
  <span v-else class="pf-abbr" :title="title" :style="{ width: px, height: px, fontSize: fs }">{{ abbr }}</span>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { platformIcon, platformIconFallback, platformIconBg, platformAbbr, platformName } from '@/utils/platformIcon.js'

const props = defineProps({
  name: { type: String, default: '' },
  size: { type: Number, default: 22 },
  showLabel: { type: Boolean, default: false },
})
const src = computed(() => platformIcon(props.name))
const fallbackSrc = computed(() => platformIconFallback(props.name))
const bg = computed(() => platformIconBg(props.name))
const abbr = computed(() => platformAbbr(props.name))
const title = computed(() => platformName(props.name))
const px = computed(() => props.size + 'px')
const fs = computed(() => Math.max(10, Math.round(props.size * 0.5)) + 'px')
const imgSrc = ref(src.value)

watch(src, (val) => {
  imgSrc.value = val
}, { immediate: true })

function onImgError() {
  if (!imgSrc.value) return
  if (fallbackSrc.value && imgSrc.value !== fallbackSrc.value) {
    imgSrc.value = fallbackSrc.value
    return
  }
  imgSrc.value = ''
}
</script>

<style scoped>
.pf-with-label {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.pf-ico {
  border-radius: 6px;
  padding: 0;
  object-fit: contain;
  border: none;
  box-sizing: border-box;
  flex: none;
  vertical-align: middle;
}
.pf-abbr {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 5px;
  background: #f1f5f9;
  color: #475569;
  font-weight: 600;
  border: 1px solid #e5e7eb;
  box-sizing: border-box;
  flex: none;
  vertical-align: middle;
}
.pf-label {
  font-size: 11.5px;
  color: #64748b;
  white-space: nowrap;
  line-height: 1;
}
</style>
