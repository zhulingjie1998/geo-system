<template>
  <div class="publish-home">
    <!-- KPI 卡片 -->
    <section class="kpi-strip">
      <div class="kpi-card" @click="$router.push('/publish/customers')">
        <div class="kpi-icon kpi-icon-blue"><el-icon><User /></el-icon></div>
        <div class="kpi-body">
          <div class="kpi-label">客户总数</div>
          <div class="kpi-val">{{ stats.customers }}</div>
          <div class="kpi-sub">内容发布服务客户</div>
        </div>
      </div>

      <div class="kpi-card" @click="$router.push('/publish/knowledge')">
        <div class="kpi-icon kpi-icon-violet"><el-icon><Notebook /></el-icon></div>
        <div class="kpi-body">
          <div class="kpi-label">知识库条目</div>
          <div class="kpi-val">{{ stats.knowledge }}</div>
          <div class="kpi-sub">品牌知识素材</div>
        </div>
      </div>

      <div class="kpi-card" @click="$router.push('/publish/content-library')">
        <div class="kpi-icon kpi-icon-green"><el-icon><Document /></el-icon></div>
        <div class="kpi-body">
          <div class="kpi-label">内容文章</div>
          <div class="kpi-val">{{ stats.articles }}</div>
          <div class="kpi-sub">已生成内容</div>
        </div>
      </div>

      <div class="kpi-card">
        <div class="kpi-icon kpi-icon-orange"><el-icon><Clock /></el-icon></div>
        <div class="kpi-body">
          <div class="kpi-label">待发布</div>
          <div class="kpi-val">{{ stats.pending }}</div>
          <div class="kpi-sub">等待审核发布</div>
        </div>
      </div>
    </section>

    <!-- 快捷操作 -->
    <section class="panel">
      <div class="panel-head"><h3>快捷操作</h3></div>
      <div class="quick-actions">
        <a class="quick-action" @click="$router.push('/publish/customers')">
          <div class="qa-icon qa-blue"><el-icon><User /></el-icon></div>
          <span>管理客户</span>
        </a>
        <a class="quick-action" @click="$router.push('/publish/knowledge')">
          <div class="qa-icon qa-violet"><el-icon><Notebook /></el-icon></div>
          <span>知识库管理</span>
        </a>
        <a class="quick-action" @click="$router.push('/publish/content-library')">
          <div class="qa-icon qa-green"><el-icon><Document /></el-icon></div>
          <span>内容库管理</span>
        </a>
      </div>
    </section>

    <!-- 最近动态 -->
    <section class="panel">
      <div class="panel-head"><h3>最近动态</h3></div>
      <div v-if="recentActivities.length" class="activity-list">
        <div v-for="(item, i) in recentActivities" :key="i" class="activity-item">
          <div class="activity-dot" :class="'activity-' + item.type"></div>
          <div class="activity-info">
            <span class="activity-text">{{ item.text }}</span>
            <span class="activity-time">{{ item.time }}</span>
          </div>
        </div>
      </div>
      <div v-else class="panel-empty">暂无动态</div>
    </section>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { User, Notebook, Document, Clock } from '@element-plus/icons-vue'
import api from '../api'

const stats = ref({ customers: 0, knowledge: 0, articles: 0, pending: 0 })
const recentActivities = ref([])

onMounted(async () => {
  try {
    // 尝试获取首页数据，失败则使用默认值
    const data = await api.getHomeOverview()
    stats.value = {
      customers: data.stats?.accounts || 0,
      knowledge: 0,
      articles: 0,
      pending: 0,
    }
  } catch {
    // 使用默认值
  }
})
</script>

<style scoped>
/* ===== KPI 卡片（与HomePage一致） ===== */
.publish-home { display: flex; flex-direction: column; gap: 18px; }

.kpi-strip { display: grid; grid-template-columns: repeat(auto-fit, minmax(215px, 1fr)); gap: 16px; }
.kpi-card {
  display: flex; align-items: center; gap: 14px; cursor: pointer;
  background: #fff; border: 1px solid #eef1f6; border-radius: 12px; padding: 18px 20px;
  transition: box-shadow .2s ease, transform .12s ease;
}
.kpi-card:hover { box-shadow: 0 8px 24px rgba(15, 23, 42, .07); transform: translateY(-1px); }
.kpi-icon {
  width: 42px; height: 42px; border-radius: 10px; flex: none;
  display: flex; align-items: center; justify-content: center; font-size: 19px;
}
.kpi-icon-blue { background: #eef4ff; color: #3b82f6; }
.kpi-icon-violet { background: #f2eefe; color: #7c5cf6; }
.kpi-icon-green { background: #eafaf1; color: #10b981; }
.kpi-icon-orange { background: #fff3e8; color: #f59e0b; }
.kpi-label { font-size: 12.5px; color: #8a94a6; }
.kpi-val { font-size: 26px; font-weight: 700; line-height: 1.25; color: #0f172a; }
.kpi-sub { font-size: 12px; color: #9aa3b2; }

/* ===== 面板（与DashboardLayout一致） ===== */
.panel {
  background: #fff; border: 1px solid #eef1f6; border-radius: 12px;
  padding: 20px 24px;
}
.panel-head {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 16px;
}
.panel-head h3 {
  font-size: 15px; font-weight: 600; color: #1e293b; margin: 0;
}

/* 快捷操作 */
.quick-actions { display: flex; gap: 14px; flex-wrap: wrap; }
.quick-action {
  display: flex; align-items: center; gap: 10px;
  padding: 12px 20px; border-radius: 10px;
  background: #f8fafc; border: 1px solid #eef2f7;
  cursor: pointer; text-decoration: none; transition: all .18s ease;
  font-size: 13.5px; color: #334155; font-weight: 500;
}
.quick-action:hover { background: #f1f5f9; border-color: #e2e8f0; transform: translateY(-1px); box-shadow: 0 4px 12px rgba(15,23,42,.06); }
.qa-icon {
  width: 34px; height: 34px; border-radius: 8px;
  display: flex; align-items: center; justify-content: center; font-size: 16px;
}
.qa-blue { background: #eef4ff; color: #3b82f6; }
.qa-violet { background: #f2eefe; color: #7c5cf6; }
.qa-green { background: #eafaf1; color: #10b981; }

/* 动态列表 */
.activity-list { display: flex; flex-direction: column; gap: 10px; }
.activity-item {
  display: flex; align-items: flex-start; gap: 12px;
  padding: 10px 0; border-bottom: 1px solid #f1f5f9;
}
.activity-item:last-child { border-bottom: none; }
.activity-dot {
  width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; margin-top: 5px;
}
.activity-customer { background: #3b82f6; }
.activity-knowledge { background: #7c5cf6; }
.activity-content { background: #10b981; }
.activity-publish { background: #f59e0b; }
.activity-info { flex: 1; min-width: 0; }
.activity-text { font-size: 13.5px; color: #334155; }
.activity-time { font-size: 12px; color: #94a3b8; margin-left: 10px; }

.panel-empty {
  text-align: center; padding: 28px 0; color: #94a3b8; font-size: 13.5px;
}

@media (max-width: 600px) {
  .kpi-strip { grid-template-columns: 1fr 1fr; }
  .quick-actions { flex-direction: column; }
}
</style>
