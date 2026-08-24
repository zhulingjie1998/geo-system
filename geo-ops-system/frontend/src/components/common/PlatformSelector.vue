<template>
  <div class="platform-selector">
    <div class="platform-header">
      <el-button link type="primary" size="small" @click="selectAll">全选</el-button>
      <el-button link size="small" @click="clearAll">清空</el-button>
      <span class="selected-count">已选 {{ modelValue.length }}/{{ options.length }}</span>
    </div>
    <div class="platform-grid">
      <div
        v-for="item in options"
        :key="item"
        class="platform-item"
        :class="{ 'is-active': modelValue.includes(item) }"
        @click="toggleItem(item)"
      >
        <!-- 平台名称 -->
        <span class="platform-name">{{ item }}</span>
        <!-- 选中状态指示器 -->
        <span class="check-indicator">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="20 6 9 17 4 12"></polyline>
          </svg>
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
// 纯文字模式选择器，图标在列表中展示即可
const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  options: {
    type: Array,
    default: () => ['ChatGPT', 'Gemini', 'Google AIO', 'Google AIM', 'Perplexity', 'Copilot']
  }
})

const emit = defineEmits(['update:modelValue'])

function toggleItem(item) {
  const list = [...props.modelValue]
  const idx = list.indexOf(item)
  if (idx >= 0) {
    list.splice(idx, 1)
  } else {
    list.push(item)
  }
  emit('update:modelValue', list)
}

function selectAll() {
  emit('update:modelValue', [...props.options])
}

function clearAll() {
  emit('update:modelValue', [])
}
</script>

<style scoped>
.platform-selector {
  width: 100%;
}

.platform-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 10px;
}

.selected-count {
  margin-left: auto;
  font-size: 12px;
  color: #94a3b8;
}

.platform-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.platform-item {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 10px 12px;
  border: 2px solid #e5e7eb;
  border-radius: 10px;
  background: #ffffff;
  cursor: pointer;
  transition: all 0.2s ease;
  user-select: none;
  min-width: 0;
}

.platform-item:hover {
  border-color: #30c1b4;
  background: #f0fdfa;
}

.platform-item.is-active {
  border-color: #30c1b4;
  background: linear-gradient(135deg, #f0fdfa 0%, #e6fffa 100%);
}

/* 选中状态指示器 */
.check-indicator {
  position: absolute;
  top: -6px;
  right: -6px;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #30c1b4;
  color: white;
  display: none;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 4px rgba(48, 193, 180, 0.3);
}

.check-indicator svg {
  width: 11px;
  height: 11px;
}

.platform-item.is-active .check-indicator {
  display: flex;
}

/* 平台图标 - 固定大小不压缩 (保留给列表使用) */
.platform-item :deep(img),
.platform-item :deep(svg) {
  flex-shrink: 0;
}

/* 平台名称 - 纯文字模式居中显示 */
.platform-name {
  font-size: 13px;
  font-weight: 500;
  color: #334155;
  text-align: center;
}

.platform-item.is-active .platform-name {
  color: #0d9488;
  font-weight: 600;
}
</style>
