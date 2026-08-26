<template>
  <EffectAnalysisPlaceholder
    title="掉线预警"
    description="对即将掉线的关键词进行预警，提前介入维护，保障品牌持续露出。"
    :icon="WarningFilled"
  />
</template>

<script setup>
import { WarningFilled } from '@element-plus/icons-vue'
import EffectAnalysisPlaceholder from './EffectAnalysisPlaceholder.vue'
</script>
