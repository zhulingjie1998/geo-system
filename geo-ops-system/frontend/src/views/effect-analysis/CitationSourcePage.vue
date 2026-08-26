<template>
  <EffectAnalysisPlaceholder
    title="引用源分析"
    description="分析 AI 回答中引用的网页来源、发布日期与内容类型，优化内容策略。"
    :icon="Link"
  />
</template>

<script setup>
import { Link } from '@element-plus/icons-vue'
import EffectAnalysisPlaceholder from './EffectAnalysisPlaceholder.vue'
</script>
