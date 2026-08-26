<template>
  <div class="ea-placeholder">
    <div class="placeholder-card">
      <div class="placeholder-icon">
        <el-icon :size="48"><component :is="icon" /></el-icon>
      </div>
      <h2>{{ title }}</h2>
      <p>{{ description }}</p>
      <div class="placeholder-badge">功能开发中</div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  title: { type: String, default: '' },
  description: { type: String, default: '' },
  icon: { type: [String, Object], default: null },
})
</script>

<style scoped>
.ea-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 60vh;
}
.placeholder-card {
  text-align: center;
  padding: 48px 40px;
  background: #fff;
  border-radius: 16px;
  border: 1px solid #e5eaf3;
  box-shadow: 0 4px 24px rgba(15, 23, 42, 0.06);
  max-width: 480px;
}
.placeholder-icon {
  width: 80px; height: 80px;
  margin: 0 auto 20px;
  display: flex; align-items: center; justify-content: center;
  border-radius: 20px;
  background: linear-gradient(135deg, rgba(45, 212, 191, 0.12), rgba(20, 184, 166, 0.08));
  color: #14b8a6;
}
.placeholder-card h2 {
  font-size: 22px; font-weight: 700; color: #0f172a;
  margin: 0 0 8px;
}
.placeholder-card p {
  font-size: 14px; color: #64748b; line-height: 1.6;
  margin: 0 0 20px;
}
.placeholder-badge {
  display: inline-block;
  padding: 4px 14px;
  font-size: 12px; font-weight: 600;
  color: #14b8a6;
  background: rgba(45, 212, 191, 0.1);
  border: 1px solid rgba(45, 212, 191, 0.2);
  border-radius: 20px;
}
</style>
