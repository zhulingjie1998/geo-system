<template>
  <EffectAnalysisPlaceholder
    title="排名波动"
    description="监控关键词排名波动情况，识别异常变化与趋势走向。"
    :icon="TrendCharts"
  />
</template>

<script setup>
import { TrendCharts } from '@element-plus/icons-vue'
import EffectAnalysisPlaceholder from './EffectAnalysisPlaceholder.vue'
</script>
