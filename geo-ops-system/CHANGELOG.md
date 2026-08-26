# 更新日志

## V1.1.1 (2026-08-26)

### 新增功能
1. **新增效果分析板块**
   - 新增效果分析布局组件 `EffectAnalysisLayout.vue`，包含侧边栏导航
   - 在 Dashboard 侧边栏中添加效果分析入口
   - 在路由配置中注册效果分析相关路由

2. **新增效果分析-客户效果分析功能**
   - 新增 `CustomerEffectPage.vue` 客户效果分析页面
   - 客户下拉框调用 `GET /api/accounts` 接口，基于当前账户权限（RBAC）自动过滤客户范围
   - 日期选择调用 `GET /api/search/history/{accountId}` 获取真实查词日期
   - KPI 指标从 `GET /api/search/results` + `GET /api/rank-tool/summary` 双数据源计算
   - 各平台上榜率从查词结果按平台分组计算
   - 上榜词/掉线词/排名波动从两期查词结果对比生成
   - 组合图表（上榜率×运营动作）从真实日期数据生成
   - 平台名称映射：将后端 AI 模型标识映射到 6 大标准平台名

### 涉及文件
- `frontend/src/layouts/EffectAnalysisLayout.vue` (新增)
- `frontend/src/views/effect-analysis/CustomerEffectPage.vue` (新增)
- `frontend/src/views/effect-analysis/CitationSourcePage.vue` (新增-占位)
- `frontend/src/views/effect-analysis/CompetitorAnalysisPage.vue` (新增-占位)
- `frontend/src/views/effect-analysis/OfflineKeywordsPage.vue` (新增-占位)
- `frontend/src/views/effect-analysis/OfflineWarningPage.vue` (新增-占位)
- `frontend/src/views/effect-analysis/OnListKeywordsPage.vue` (新增-占位)
- `frontend/src/views/effect-analysis/PlatformComparisonPage.vue` (新增-占位)
- `frontend/src/views/effect-analysis/RankingFluctuationPage.vue` (新增-占位)
- `frontend/src/views/effect-analysis/EffectAnalysisPlaceholder.vue` (新增-占位)
- `frontend/src/layouts/DashboardLayout.vue` (修改-添加侧边栏入口)
- `frontend/src/router/index.js` (修改-添加路由)
