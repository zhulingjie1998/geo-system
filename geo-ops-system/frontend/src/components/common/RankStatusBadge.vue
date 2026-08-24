<template>
  <el-tooltip
    v-if="remark"
    :content="remark"
    placement="top"
    :show-after="200"
  >
    <span :class="badgeClass">{{ displayText }}</span>
  </el-tooltip>
  <span v-else :class="badgeClass">{{ displayText }}</span>
</template>

<script setup>
import { computed } from 'vue'
import { getBadgeClass } from '@/utils/statusMap'

const props = defineProps({
  status: { type: String, default: '-' },
  remark: { type: String, default: '' }
})

const badgeClass = computed(() => getBadgeClass(props.status))
const displayText = computed(() => props.status || '-')
</script>
