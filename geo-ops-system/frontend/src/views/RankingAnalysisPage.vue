<template>
  <div class="ranking-page">
    <!-- ============ KPI 栏 ============ -->
    <section class="kpi-strip">
      <div class="kpi-card" :class="{ active: !filterStatus }" role="button" tabindex="0"
           @click="filterStatus=''" @keydown.enter="filterStatus=''">
        <div class="kpi-icon kpi-icon-blue"><el-icon :size="18"><User /></el-icon></div>
        <div class="kpi-body">
          <div class="kpi-label">分析客户</div>
          <div class="kpi-val">{{ totalCustomers }}</div>
          <div class="kpi-sub">显示全部</div>
        </div>
      </div>
      <div class="kpi-card" role="button" tabindex="0">
        <div class="kpi-icon kpi-icon-orange"><el-icon :size="18"><DataAnalysis /></el-icon></div>
        <div class="kpi-body">
          <div class="kpi-label">总分析次数</div>
          <div class="kpi-val">{{ totalAnalysis }}</div>
          <div class="kpi-sub">累计任务</div>
        </div>
      </div>
      <div class="kpi-card" :class="{ active: filterStatus==='running' }" role="button" tabindex="0"
           @click="filterStatus = filterStatus==='running' ? '' : 'running'"
           @keydown.enter="filterStatus = filterStatus==='running' ? '' : 'running'">
        <div class="kpi-icon kpi-icon-purple"><el-icon :size="18"><Loading /></el-icon></div>
        <div class="kpi-body">
          <div class="kpi-label">进行中</div>
          <div class="kpi-val">{{ runningCount }}</div>
          <div class="kpi-sub" :class="{ 'kpi-sub-live': runningCount > 0 }">
            <span v-if="runningCount">实时分析中</span>
            <span v-else>当前空闲</span>
          </div>
        </div>
      </div>
      <div class="kpi-card" role="button" tabindex="0">
        <div class="kpi-icon kpi-icon-green"><el-icon :size="18"><TrophyBase /></el-icon></div>
        <div class="kpi-body">
          <div class="kpi-label">平均上榜率</div>
          <div class="kpi-val">{{ avgRankingRate }}%</div>
          <div class="kpi-sub">通用词·各客户均值</div>
        </div>
      </div>
    </section>

    <!-- ============ 主面板 ============ -->
    <section class="panel">
      <!-- 类别 tabs -->
      <div class="category-tabs">
        <button class="cat-tab" :class="{ active: scope === 'internal' }" @click="setScope('internal')">
          内部客户 <span class="cat-count">{{ internalCount }}</span>
        </button>
        <button class="cat-tab cat-tab-temp" :class="{ active: scope === 'temp' }" @click="setScope('temp')">
          <span class="cat-tab-dot cat-tab-dot-temp"></span>临时任务 <span class="cat-count">{{ tempCount }}</span>
        </button>
      </div>

      <!-- 工具栏 -->
      <div class="toolbar">
        <div class="toolbar-tabs">
          <button class="seg" :class="{ active: !filterStatus }" @click="filterStatus=''">
            全部 <span class="seg-count">{{ scopedRows.length }}</span>
          </button>
          <button class="seg" :class="{ active: filterStatus==='running' }" @click="filterStatus='running'">
            进行中 <span class="seg-count">{{ runningCount }}</span>
          </button>
          <button class="seg" :class="{ active: filterStatus==='done' }" @click="filterStatus='done'">
            已完成
          </button>
          <button class="seg" :class="{ active: filterStatus==='error' }" @click="filterStatus='error'">
            异常
          </button>
        </div>
        <div class="toolbar-actions">
          <el-input
            v-model="searchText"
            placeholder="搜索客户或品牌..."
            clearable
            :prefix-icon="SearchIcon"
            class="toolbar-search"
          />
          <el-tooltip content="刷新" placement="top">
            <el-button :icon="RefreshIcon" plain @click="loadData" />
          </el-tooltip>
          <el-button type="primary" :icon="PlusIcon" @click="showCreateDialog">新建分析</el-button>
        </div>
      </div>

      <!-- 表格 -->
      <el-table
        :data="pagedRows"
        v-loading="loading"
        row-key="id"
        class="ranking-table"
        :header-cell-style="{ background: 'transparent', color: '#64748b', fontWeight: 600, fontSize: '12px', letterSpacing: '0.3px' }"
        @row-click="onRowClick"
      >
        <el-table-column label="客户" min-width="280" sortable
          :sort-method="(a,b) => (a.customerName||'').localeCompare(b.customerName||'')">
          <template #default="{ row }">
            <div class="customer-cell">
              <div class="ca-name-row">
                <span class="ca-type-dot" :class="row.type === 'temp' ? 'ca-dot-temp' : 'ca-dot-paid'"
                  :title="row.type === 'temp' ? '临时任务' : '正式客户'"></span>
                <span class="ca-name">{{ row.customerName }}</span>
              </div>
              <div class="ca-meta">
                <span class="ca-meta-item">{{ row.analysisCount }} 次分析</span>
                <span class="ca-meta-sep">·</span>
                <span class="ca-meta-item">{{ row.resultCount }} 结果</span>
              </div>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="品牌" min-width="200">
          <template #default="{ row }">
            <div class="brand-cell">
              <template v-if="row.brands && row.brands.length">
                <span v-for="b in row.brands.slice(0, 2)" :key="b" class="brand-tag">{{ b }}</span>
                <el-tooltip
                  v-if="row.brands.length > 2"
                  :content="row.brands.slice(2).join('、')"
                  placement="top">
                  <span class="brand-tag brand-tag-more">+{{ row.brands.length - 2 }}</span>
                </el-tooltip>
              </template>
              <span v-else class="muted">未配置</span>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="上榜率·通用词" min-width="150" sortable
          :sort-method="(a,b) => (a.rankingRate||0) - (b.rankingRate||0)">
          <template #default="{ row }">
            <div class="rr-cell" title="最新一次分析·通用词上榜率(品牌词不计)">
              <div class="rr-bar">
                <div class="rr-fill" :class="rrClass(row.rankingRate)" :style="{ width: (row.rankingRate || 0) + '%' }"></div>
              </div>
              <span class="rr-num" :class="rrClass(row.rankingRate)">{{ row.rankingRate || 0 }}%</span>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="前三率·通用词" min-width="140" sortable
          :sort-method="(a,b) => (a.top3Rate||0) - (b.top3Rate||0)">
          <template #default="{ row }">
            <div class="rr-cell" title="最新一次分析·通用词进前三占比(品牌词不计)">
              <div class="rr-bar">
                <div class="rr-fill" :class="rrClass(row.top3Rate)" :style="{ width: (row.top3Rate || 0) + '%' }"></div>
              </div>
              <span class="rr-num" :class="rrClass(row.top3Rate)">{{ row.top3Rate || 0 }}%</span>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="最新状态" width="120" align="center">
          <template #default="{ row }">
            <span class="status-pill" :class="'status-pill-' + (row.status || '').toLowerCase()">
              <span class="status-dot"></span>{{ statusText(row.status) }}
            </span>
          </template>
        </el-table-column>

        <el-table-column label="最近分析" width="130" sortable
          :sort-method="(a,b) => (a.lastAnalysisTime||'').localeCompare(b.lastAnalysisTime||'')">
          <template #default="{ row }">
            <div v-if="row.lastAnalysisTime" class="last-search">
              <span class="ls-date">{{ formatDate(row.lastAnalysisTime) }}</span>
              <span class="ls-rel">{{ formatTime(row.lastAnalysisTime) }}</span>
            </div>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="150" fixed="right" align="right">
          <template #default="{ row }">
            <button class="act-btn act-btn-primary" @click.stop="viewDetail(row)">查看</button>
            <el-tooltip content="导出" placement="top">
              <button class="act-btn act-btn-more" @click.stop="exportRow(row)">
                <el-icon :size="14"><Download /></el-icon>
              </button>
            </el-tooltip>
          </template>
        </el-table-column>

        <template #empty>
          <div class="table-empty">
            <el-icon :size="40" color="#cbd5e1"><DataAnalysis /></el-icon>
            <p>{{ isFiltering ? '未找到匹配的分析记录' : '暂无排名分析数据' }}</p>
            <el-button v-if="isFiltering" size="small" @click="resetFilters">清除筛选</el-button>
          </div>
        </template>
      </el-table>

      <!-- 分页 -->
      <div v-if="filteredRows.length > pageSize" class="pagination-row">
        <el-pagination
          v-model:current-page="currentPage"
          :page-size="pageSize"
          :total="filteredRows.length"
          layout="total, prev, pager, next, jumper"
          background
          small
        />
      </div>
    </section>

    <!-- ============ 新建分析弹窗 ============ -->
    <el-dialog
      v-model="createDialogVisible"
      title="新建排名分析"
      width="min(520px, 92vw)"
      :close-on-click-modal="false"
      class="create-dialog"
      @closed="resetCreateForm"
    >
      <el-form :model="createForm" label-width="80px" size="default">
        <!-- 数据来源 -->
        <el-form-item label="数据来源">
          <el-radio-group v-model="createForm.dataSource" size="small">
            <el-radio-button value="account">选择客户</el-radio-button>
            <el-radio-button value="manual">手动填写</el-radio-button>
          </el-radio-group>
        </el-form-item>

        <!-- ========== 选择客户模式 ========== -->
        <template v-if="createForm.dataSource === 'account'">
          <!-- 客户选择 -->
          <el-form-item label="客户" required>
            <el-select
              v-model="createForm.accountId"
              filterable
              placeholder="请选择或搜索客户..."
              style="width: 100%"
            >
              <el-option
                v-for="c in customerOptions"
                :key="c.id"
                :label="c.customerName + (c.brands?.length ? ' · ' + c.brands.join('、') : '')"
                :value="c.id"
              />
            </el-select>
          </el-form-item>

          <!-- 查词日期（选择客户后显示，从系统获取已查词日期） -->
          <el-form-item v-if="selectedCustomerInfo" label="查词日期" required>
            <el-select
              v-model="createForm.queryDate"
              placeholder="请选择查词日期"
              style="width: 100%"
              clearable
            >
              <el-option
                v-for="d in availableQueryDates"
                :key="d.value"
                :label="d.label"
                :value="d.value"
              />
            </el-select>
            <div class="form-hint">选择该客户在系统中已有的查词记录日期。</div>
          </el-form-item>

          <!-- 分析品牌（从系统获取客户品牌，支持临时输入新增） -->
          <el-form-item label="分析品牌" required>
            <el-select
              v-model="createForm.brandInput"
              filterable
              allow-create
              default-first-option
              multiple
              placeholder="输入品牌名后回车添加，支持多个"
              style="width: 100%"
              @change="onBrandChange"
            >
              <el-option
                v-for="b in availableBrands"
                :key="b"
                :label="b"
                :value="b"
              />
            </el-select>
            <div class="form-hint">可添加多个品牌，同一回答中出现多个，只记录排名最高的那个。</div>
          </el-form-item>

          <!-- 上次分析信息 -->
          <el-form-item v-if="selectedCustomerInfo" label="上次分析">
            <span class="auto-info">
              {{ formatDate(selectedCustomerInfo.lastAnalysisTime) }} {{ formatTime(selectedCustomerInfo.lastAnalysisTime) }}
              <span class="auto-status">完成</span>
            </span>
          </el-form-item>
        </template>

        <!-- ========== 手动填写模式 ========== -->
        <template v-if="createForm.dataSource === 'manual'">
          <!-- 提示词 -->
          <el-form-item label="提示词" required>
            <el-input
              v-model="createForm.prompt"
              type="textarea"
              :rows="4"
              placeholder="一行一条，例如：&#10;进口床垫品牌推荐&#10;哪个牌子的乳胶床好&#10;护脊床垫怎么选"
            />
            <div class="form-hint">
              一行一条，自动去重。
              已填 <strong>{{ promptLineCount }}</strong> 条 ×
              <strong>{{ createForm.queryPlatforms.length }}</strong> 个平台 =
              <strong>{{ promptLineCount * createForm.queryPlatforms.length }}</strong> 次查询。
            </div>
          </el-form-item>

          <!-- 分析品牌（支持临时输入新增） -->
          <el-form-item label="分析品牌" required>
            <el-select
              v-model="createForm.brandInput"
              filterable
              allow-create
              default-first-option
              multiple
              placeholder="输入品牌名后回车添加，支持多个"
              style="width: 100%"
              @change="onBrandChange"
            >
              <el-option
                v-for="b in availableBrands"
                :key="b"
                :label="b"
                :value="b"
              />
            </el-select>
            <div class="form-hint">同一回答中出现多个品牌时，只记录排名最高的那个。</div>
          </el-form-item>

          <!-- 查询平台（checkbox多选） -->
          <el-form-item label="查询平台" required>
            <div class="platform-checkbox-group">
              <el-checkbox-group v-model="createForm.queryPlatforms">
                <el-checkbox
                  v-for="p in queryPlatformOptions"
                  :key="p.value"
                  :value="p.value"
                >{{ p.label }}</el-checkbox>
              </el-checkbox-group>
            </div>
          </el-form-item>

          <!-- 任务名称 -->
          <el-form-item label="任务名称">
            <el-input
              v-model="createForm.taskName"
              placeholder="选填，默认用品牌名"
              clearable
            />
          </el-form-item>
        </template>

      </el-form>

      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="createLoading" @click="submitCreate">
          {{ createForm.dataSource === 'account' ? '开始分析' : '查词并分析' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- ============ 查看详情右侧抽屉 ============ -->
    <el-drawer
      v-model="detailDrawerVisible"
      direction="rtl"
      size="calc(100% - 210px)"
      :with-header="false"
      class="detail-drawer"
    >
      <div v-if="detailRow" class="drawer-wrapper">
        <!-- 头部（固定） -->
        <div class="cp-header">
          <div class="cp-left">
            <h3>{{ detailRow.customerName }} <span class="cp-brand">{{ detailRow.brands?.join('、') }}</span></h3>
            <span class="cp-task-count">{{ detailRow.analysisCount }} 次分析</span>
          </div>
          <div class="cp-right">
            <el-button type="primary" size="small" @click="openCreateForCustomer">
              <el-icon><Plus /></el-icon>新建分析
            </el-button>
            <el-button size="small" text @click="detailDrawerVisible = false">
              <el-icon><Close /></el-icon>
            </el-button>
          </div>
        </div>

        <!-- 可滚动内容区 -->
        <div class="customer-panel">
        <!-- 历史切换按钮 -->
        <button class="history-toggle" @click="showHistory = !showHistory">
          <el-icon><ArrowRight /></el-icon>
          分析历史（{{ detailRow.analysisCount }} 次）
          <span class="ht-hint">点击展开切换历史</span>
        </button>

        <!-- 历史表格 -->
        <div v-show="showHistory" class="sub-task-table">
          <el-table :data="historyData" size="small" stripe max-height="280" v-loading="detailLoading">
            <el-table-column prop="createdAt" label="创建时间" width="145" />
            <el-table-column prop="queryTime" label="查询数据时间" width="145" />
            <el-table-column prop="brands" label="分析品牌" min-width="130">
              <template #default="{ row }">
                <span v-for="b in row.brands" :key="b" class="brand-chip">{{ b }}</span>
              </template>
            </el-table-column>
            <el-table-column label="进度" width="80" align="center">
              <template #default="{ row }">
                <span v-if="row.status === '完成'" style="color:#16a34a;font-weight:600;">100%</span>
                <span v-else-if="row.status === '进行中'" style="color:#d97706;font-weight:600;">{{ row.progress || 0 }}%</span>
                <span v-else style="color:#94a3b8;">—</span>
              </template>
            </el-table-column>
            <el-table-column prop="totalCount" label="总数" width="65" align="center">
              <template #default="{ row }">
                <span style="font-variant-numeric:tabular-nums;">{{ row.totalCount || 0 }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="85" align="center">
              <template #default="{ row }">
                <el-tag :type="row.status === '完成' ? 'success' : row.status === '进行中' ? 'warning' : 'danger'" size="small" plain>
                  {{ row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="200" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click="viewHistoryTask(row)">详情</el-button>
                <el-button link type="warning" size="small" @click="reanalyzeTask(row)" :disabled="row.status === '进行中'">重新分析</el-button>
                <el-popconfirm title="确定删除该分析记录？" @confirm="deleteTask(row)" confirm-button-text="删除" cancel-button-text="取消">
                  <template #reference>
                    <el-button link type="danger" size="small">删除</el-button>
                  </template>
                </el-popconfirm>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <!-- 排名分布 -->
        <div class="rank-distribution">
          <div class="rd-title">排名分布</div>
          <div class="rd-bar">
            <div class="rd-seg rd-top1" :style="{ width: rankDist.top1.pct + '%' }" :title="`Top1: ${rankDist.top1.count}个`">{{ rankDist.top1.count }}</div>
            <div class="rd-seg rd-top3" :style="{ width: rankDist.top3.pct + '%' }" :title="`Top2-3: ${rankDist.top3.count}个`">{{ rankDist.top3.count }}</div>
            <div class="rd-seg rd-top5" :style="{ width: rankDist.top5.pct + '%' }" :title="`Top4-5: ${rankDist.top5.count}个`">{{ rankDist.top5.count }}</div>
            <div class="rd-seg rd-low" :style="{ width: rankDist.low.pct + '%' }" :title="`6+: ${rankDist.low.count}个`">{{ rankDist.low.count }}</div>
            <div class="rd-seg rd-none" :style="{ width: rankDist.none.pct + '%' }" :title="`未上榜: ${rankDist.none.count}个`">{{ rankDist.none.count }}</div>
          </div>
          <div class="rd-legend">
            <span class="rd-leg"><i class="rd-dot" style="background:#ca8a04"></i>Top 1</span>
            <span class="rd-leg"><i class="rd-dot" style="background:#22c55e"></i>Top 2-3</span>
            <span class="rd-leg"><i class="rd-dot" style="background:#3b82f6"></i>Top 4-5</span>
            <span class="rd-leg"><i class="rd-dot" style="background:#94a3b8"></i>6+</span>
            <span class="rd-leg"><i class="rd-dot" style="background:#ef4444"></i>未上榜</span>
          </div>
        </div>

        <!-- 更多分析数据（折叠） -->
        <div class="more-data-section">
          <button class="md-toggle" @click="showMoreData = !showMoreData">
            <el-icon :class="{ 'is-expanded': showMoreData }"><ArrowDown /></el-icon>
            更多分析数据
          </button>
          <div v-show="showMoreData" class="md-content">
            <!-- 各平台上榜率 -->
            <div class="md-sub-title">各平台上榜率</div>
            <div class="platform-stats">
              <div v-for="p in platformList" :key="p" class="ps-item">
                <span class="ps-name" :style="getModelTagStyle(p)">{{ p }}</span>
                <div class="ps-bar-wrap">
                  <div class="ps-bar" :style="{ width: platformStat(p).rate + '%', background: getModelTagStyle(p).color }"></div>
                </div>
                <span class="ps-val">{{ platformStat(p).ranked }}/{{ platformStat(p).total }} ({{ platformStat(p).rate }}%)</span>
              </div>
            </div>
            <!-- 品牌词详情 -->
            <div class="md-sub-title">品牌词排名明细</div>
            <div class="brand-detail-table" v-if="keywordData.filter(k => k.type === '品牌词').length">
              <div v-for="kw in keywordData.filter(k => k.type === '品牌词')" :key="kw.id" class="bd-row">
                <span class="bd-kw">{{ kw.keyword }}</span>
                <span class="bd-rank" :class="rankBadgeClass(kw.bestRank)">{{ kw.bestRank || '-' }}</span>
                <span class="bd-model" :style="getModelTagStyle(kw.model)">{{ kw.model }}</span>
              </div>
            </div>
            <div v-else class="bd-empty">暂无品牌词数据</div>
          </div>
        </div>

        <!-- 数据概览 -->
        <div class="stats-bar">
          <div class="sb-item">
            <span class="sb-num">{{ detailTotalKeywords }}</span>
            <span class="sb-label">总数</span>
          </div>
          <span class="sb-divider"></span>
          <div class="sb-item sb-success">
            <span class="sb-num">{{ detailTotalRanked }}</span>
            <span class="sb-label">上榜</span>
          </div>
          <span class="sb-divider"></span>
          <div class="sb-item sb-warn">
            <span class="sb-num">{{ detailTotalUnranked }}</span>
            <span class="sb-label">未上榜</span>
          </div>
          <span class="sb-divider"></span>
          <div class="sb-item sb-brand">
            <span class="sb-num">{{ detailAvgRank }}</span>
            <span class="sb-label">平均排名</span>
          </div>
          <span class="sb-divider"></span>
          <div class="sb-item sb-fail">
            <span class="sb-num">{{ detailFailedCount }}</span>
            <span class="sb-label">失败</span>
          </div>
        </div>

        <!-- 词类型上榜率 -->
        <div class="word-split-bar">
          <div class="ws-card ws-general">
            <div class="ws-head"><span class="ws-dot"></span>通用词上榜率</div>
            <div class="ws-body">
              <span class="ws-rate">{{ wordSplit.generic.rate }}%</span>
              <span class="ws-main">{{ wordSplit.generic.ranked }}/{{ wordSplit.generic.total }}</span>
            </div>
          </div>
          <div class="ws-card ws-brand">
            <div class="ws-head"><span class="ws-dot"></span>品牌词上榜率</div>
            <div class="ws-body">
              <span class="ws-rate">{{ wordSplit.brand.rate }}%</span>
              <span class="ws-main">{{ wordSplit.brand.ranked }}/{{ wordSplit.brand.total }}</span>
            </div>
          </div>
          <div class="ws-note">通用词不含品牌名，其上榜率更能体现 GEO 优化效果；品牌词本身就易上榜。</div>
        </div>

        <!-- 关键词排名结果 -->
        <div class="kw-section">
          <div class="kw-section-head">
            <span class="kw-section-title">关键词排名结果</span>
            <div class="kw-section-actions">
              <el-select v-model="detailFilterPlatform" size="small" placeholder="全部平台" style="width: 150px" clearable>
                <el-option v-for="p in platformList" :key="p" :label="p" :value="p" />
              </el-select>
              <el-input v-model="detailKeywordSearch" size="small" placeholder="搜索提示词..." :prefix-icon="SearchIcon" style="width: 160px" clearable />
              <el-button size="small" text @click="exportDetailRow(detailRow)">
                <el-icon><Download /></el-icon>导出
              </el-button>
            </div>
          </div>

          <!-- 快捷筛选按钮 -->
          <div class="result-filter-bar">
            <div class="rf-pills">
              <span class="rf-group-label">排名</span>
              <button class="rf-pill" :class="{ active: detailRankFilter === '' }" @click="detailRankFilter = ''">全部 <em>{{ filteredKeywordData.length }}</em></button>
              <button class="rf-pill rf-pill-top1" :class="{ active: detailRankFilter === 'top1' }" @click="detailRankFilter = 'top1'">Top 1 <em>{{ rankCounts.top1 }}</em></button>
              <button class="rf-pill rf-pill-top3" :class="{ active: detailRankFilter === 'top3' }" @click="detailRankFilter = 'top3'">Top 3 <em>{{ rankCounts.top3 }}</em></button>
              <button class="rf-pill rf-pill-top5" :class="{ active: detailRankFilter === 'top5' }" @click="detailRankFilter = 'top5'">Top 5 <em>{{ rankCounts.top5 }}</em></button>
              <button class="rf-pill rf-pill-none" :class="{ active: detailRankFilter === 'none' }" @click="detailRankFilter = 'none'">未上榜 <em>{{ rankCounts.none }}</em></button>
              <span class="rf-sep"></span>
              <span class="rf-group-label">词类型</span>
              <button class="rf-pill rf-pill-word" :class="{ active: detailWordTypeFilter === '' }" @click="detailWordTypeFilter = ''">全部 <em>{{ filteredKeywordData.length }}</em></button>
              <button class="rf-pill rf-pill-word" :class="{ active: detailWordTypeFilter === 'generic' }" @click="detailWordTypeFilter = 'generic'">通用词 <em>{{ wordTypeCounts.generic }}</em></button>
              <button class="rf-pill rf-pill-word" :class="{ active: detailWordTypeFilter === 'brand' }" @click="detailWordTypeFilter = 'brand'">品牌词 <em>{{ wordTypeCounts.brand }}</em></button>
            </div>
          </div>

          <el-table :data="pagedKeywordData" size="small" stripe row-key="id" v-loading="detailLoading">
            <el-table-column type="expand">
              <template #default="{ row }">
                <div class="expand-detail">
                  <div class="ed-title">各引擎排名快照</div>
                  <div class="ed-grid">
                    <div v-for="eng in row.engines" :key="eng.name" class="ed-engine">
                      <span class="ed-name">{{ eng.name }}</span>
                      <span class="ed-rank" :class="rankBadgeClass(eng.rank)">{{ eng.rank || '-' }}</span>
                    </div>
                  </div>
                  <div v-if="row.snippet" class="ed-snippet">{{ row.snippet }}</div>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="keyword" label="关键词" min-width="200">
              <template #default="{ row }">
                <span style="font-weight: 600;">{{ row.keyword }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="type" label="类型" width="90" align="center">
              <template #default="{ row }">
                <el-tag :type="row.type === '通用词' ? 'success' : 'warning'" size="small" plain>{{ row.type }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="模型" width="120">
              <template #default="{ row }">
                <span class="model-tag" :style="getModelTagStyle(row.model)">{{ row.model }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="bestRank" label="最佳排名" width="95" align="center">
              <template #default="{ row }">
                <span class="rank-badge" :class="rankBadgeClass(row.bestRank)">{{ row.bestRank || '-' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="80" align="center">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click="viewKeywordDetail(row)">查看</el-button>
              </template>
            </el-table-column>
          </el-table>

          <!-- 分页 -->
          <div v-if="filteredKeywordData.length > detailPageSize" class="detail-pagination">
            <el-pagination
              v-model:current-page="detailCurrentPage"
              :page-size="detailPageSize"
              :total="filteredKeywordData.length"
              layout="prev, pager, next, total"
              small
              background
            />
          </div>
        </div>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api/index.js'
import {
  Search as SearchIcon, Refresh as RefreshIcon, Plus as PlusIcon,
  User, DataAnalysis, Loading, Download, TrophyBase,
  Plus, Close, ArrowRight, ArrowDown, QuestionFilled,
} from '@element-plus/icons-vue'

/* ===== 响应式状态 ===== */
const loading = ref(false)
const searchText = ref('')
const filterStatus = ref('')
const scope = ref('internal')
const currentPage = ref(1)
const pageSize = 10

/* ===== 新建分析弹窗状态 ===== */
const createDialogVisible = ref(false)
const createLoading = ref(false)
const createForm = ref({
  dataSource: 'account', // account | manual
  accountId: null,
  prompt: '',
  brandInput: [],
  brands: [],
  includeBrandWords: false,
  queryPlatform: '', // deprecated, use queryPlatforms now
  queryPlatforms: [], // 手动填写时的多选平台
  queryDate: '', // 选择客户模式的查词日期
  taskName: '', // 手动填写模式的任务名称
})

// 查询平台选项（用于手动填写模式的checkbox）
const queryPlatformOptions = [
  { label: 'ChatGPT', value: 'chatgpt' },
  { label: 'Google AIO', value: 'google_aio' },
  { label: 'Google AIM', value: 'google_aim' },
  { label: 'Gemini', value: 'gemini' },
  { label: 'Perplexity', value: 'perplexity' },
  { label: 'Copilot', value: 'copilot' },
]

// 提示词行数计算
const promptLineCount = computed(() => {
  if (!createForm.value.prompt.trim()) return 0
  return createForm.value.prompt.trim().split('\n').filter(l => l.trim()).length
})

// 选择客户后自动带入品牌和日期
const selectedCustomerInfo = computed(() => {
  if (!createForm.value.accountId) return null
  return rows.value.find(r => r.id === createForm.value.accountId)
})

// 可用查词日期列表（从 API 获取当前客户已查词的日期）
const availableQueryDates = ref([])

watch(() => createForm.value.accountId, async (newId) => {
  availableQueryDates.value = []
  if (newId && createForm.value.dataSource === 'account') {
    // 自动带入该客户的所有品牌
    const cust = rows.value.find(r => r.id === newId)
    if (cust) {
      createForm.value.brands = [...(cust.brands || [])]
      createForm.value.brandInput = [...(cust.brands || [])]
    }
    // 从 API 获取查词日期列表
    try {
      const dates = await api.getSearchHistory(newId)
      availableQueryDates.value = (Array.isArray(dates) ? dates : []).map((d, i) => ({
        value: d,
        label: i === 0 ? `${d}（最近一次）` : d,
      }))
    } catch {
      availableQueryDates.value = []
    }
  }
})

/* ===== 查看详情抽屉状态 ===== */
const detailDrawerVisible = ref(false)
const detailRow = ref(null)
const showHistory = ref(false)
const showMoreData = ref(false)
const detailFilterPlatform = ref('')
const detailKeywordSearch = ref('')
const detailRankFilter = ref('')
const detailWordTypeFilter = ref('')
const detailCurrentPage = ref(1)
const detailPageSize = 10

// 筛选变化时重置分页
watch([detailRankFilter, detailWordTypeFilter, detailFilterPlatform, detailKeywordSearch], () => {
  detailCurrentPage.value = 1
})

/* ===== AI 平台列表 ===== */
const platformList = ['ChatGPT', 'Google AIO', 'Google AIM', 'Gemini', 'Perplexity', 'Copilot']

/* ===== 列表数据（由 API 填充） ===== */
const rows = ref([])

/* ===== 客户选项（从客户管理列表获取） ===== */
const customerOptions = ref([])

async function loadCustomerOptions() {
  try {
    const accounts = await api.getAccounts()
    customerOptions.value = (Array.isArray(accounts) ? accounts : []).map(a => ({
      id: a.id,
      customerName: a.customerName || a.companyName || '',
      brands: a.brands || [],
    }))
  } catch (e) {
    console.warn('加载客户列表失败', e)
    customerOptions.value = []
  }
}

/* ===== 可用品牌列表（去重） ===== */
const availableBrands = computed(() => {
  const set = new Set()
  rows.value.forEach(r => (r.brands || []).forEach(b => set.add(b)))
  return [...set].sort()
})

/* ===== 关键词排名数据（由 API 填充） ===== */
const keywordData = ref([])

/* ===== 历史数据（由 API 填充） ===== */
const historyData = ref([])

/* ===== 计算属性 ===== */
const internalRows = computed(() => rows.value.filter(r => r.type === 'paid'))
const tempRows = computed(() => rows.value.filter(r => r.type === 'temp'))

const internalCount = computed(() => internalRows.value.length)
const tempCount = computed(() => tempRows.value.length)

const scopedRows = computed(() => {
  if (scope.value === 'temp') return tempRows.value
  return internalRows.value
})

const totalCustomers = computed(() => rows.value.filter(r => r.type === 'paid').length)
const totalAnalysis = computed(() => rows.value.reduce((s, r) => s + r.analysisCount, 0))
const runningCount = computed(() => scopedRows.value.filter(r => r.status === 'running').length)
const avgRankingRate = computed(() => {
  const done = scopedRows.value.filter(r => r.status === 'done')
  if (!done.length) return 0
  return Math.round(done.reduce((s, r) => s + (r.rankingRate || 0), 0) / done.length)
})

const isFiltering = computed(() => !!(searchText.value || filterStatus.value))

const filteredRows = computed(() => {
  let list = scopedRows.value.slice()

  if (searchText.value.trim()) {
    const kw = searchText.value.trim().toLowerCase()
    list = list.filter(r =>
      (r.customerName || '').toLowerCase().includes(kw) ||
      (r.brands || []).some(b => b.toLowerCase().includes(kw))
    )
  }

  if (filterStatus.value) {
    list = list.filter(r => {
      if (filterStatus.value === 'running') return r.status === 'running'
      if (filterStatus.value === 'done') return r.status === 'done'
      if (filterStatus.value === 'error') return r.status === 'error'
      return true
    })
  }

  // 运行中优先，然后按最近分析时间降序
  list.sort((a, b) => {
    if ((a.status === 'running') !== (b.status === 'running')) return a.status === 'running' ? -1 : 1
    return (b.lastAnalysisTime || '').localeCompare(a.lastAnalysisTime || '')
  })

  return list
})

const pagedRows = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  return filteredRows.value.slice(start, start + pageSize)
})

/* ===== 数据概览统计 ===== */
const totalKeywords = computed(() => {
  return rows.value.reduce((s, r) => s + (r.resultCount || 0), 0)
})
const totalRanked = computed(() => {
  return Math.round(totalKeywords.value * (avgRankingRate.value / 100))
})
const totalUnranked = computed(() => totalKeywords.value - totalRanked.value)
const avgRankOverall = computed(() => {
  const ranked = keywordData.value.filter(k => k.bestRank && k.bestRank <= 10)
  if (!ranked.length) return '-'
  return (ranked.reduce((s, k) => s + k.bestRank, 0) / ranked.length).toFixed(1)
})
const failedCount = computed(() => rows.value.filter(r => r.status === 'error').length)

/* 详情面板 - 多重筛选后的关键词数据 */
const baseFilteredKeywords = computed(() => {
  let list = keywordData.value

  // 平台筛选：根据 engines 中是否有该平台的排名来过滤
  if (detailFilterPlatform.value) {
    const platform = detailFilterPlatform.value
    list = list.filter(k => k.engines && k.engines.some(e => e.name === platform))
  }

  // 关键词搜索
  if (detailKeywordSearch.value.trim()) {
    const kw = detailKeywordSearch.value.trim().toLowerCase()
    list = list.filter(k => k.keyword.toLowerCase().includes(kw))
  }

  // 词类型筛选
  if (detailWordTypeFilter.value) {
    const typeMap = { generic: '通用词', brand: '品牌词' }
    list = list.filter(k => k.type === typeMap[detailWordTypeFilter.value])
  }

  // 排名筛选
  if (detailRankFilter.value) {
    switch (detailRankFilter.value) {
      case 'top1': list = list.filter(k => k.bestRank === 1); break
      case 'top3': list = list.filter(k => k.bestRank >= 1 && k.bestRank <= 3); break
      case 'top5': list = list.filter(k => k.bestRank >= 1 && k.bestRank <= 5); break
      case 'none': list = list.filter(k => !k.bestRank || k.bestRank > 10); break
    }
  }

  return list
})

const filteredKeywordData = computed(() => {
  // 按排名从高到低排序（排名数字越小越靠前，未上榜排最后）
  return baseFilteredKeywords.value.slice().sort((a, b) => {
    const ra = a.bestRank || 999
    const rb = b.bestRank || 999
    return ra - rb
  })
})

/* 详情面板关键词分页 */
const pagedKeywordData = computed(() => {
  const start = (detailCurrentPage.value - 1) * detailPageSize
  return filteredKeywordData.value.slice(start, start + detailPageSize)
})

/* 详情面板数据概览统计 - 基于全部数据，不受筛选影响 */
const detailTotalKeywords = computed(() => keywordData.value.length)
const detailTotalRanked = computed(() => keywordData.value.filter(k => k.bestRank && k.bestRank <= 10).length)
const detailTotalUnranked = computed(() => detailTotalKeywords.value - detailTotalRanked.value)
const detailAvgRank = computed(() => {
  const ranked = keywordData.value.filter(k => k.bestRank && k.bestRank <= 10)
  if (!ranked.length) return '-'
  return (ranked.reduce((s, k) => s + k.bestRank, 0) / ranked.length).toFixed(1)
})
const detailFailedCount = computed(() => 0)

/* 筛选计数 - 基于全部数据计算各段数量 */
const rankCounts = computed(() => {
  const data = keywordData.value.filter(k => !detailWordTypeFilter.value || 
    (detailWordTypeFilter.value === 'generic' && k.type === '通用词') ||
    (detailWordTypeFilter.value === 'brand' && k.type === '品牌词'))
  return {
    top1: data.filter(k => k.bestRank === 1).length,
    top3: data.filter(k => k.bestRank >= 1 && k.bestRank <= 3).length,
    top5: data.filter(k => k.bestRank >= 1 && k.bestRank <= 5).length,
    none: data.filter(k => !k.bestRank || k.bestRank > 10).length,
  }
})

const wordTypeCounts = computed(() => {
  const data = keywordData.value.filter(k => !detailRankFilter.value ||
    (detailRankFilter.value === 'top1' && k.bestRank === 1) ||
    (detailRankFilter.value === 'top3' && k.bestRank >= 1 && k.bestRank <= 3) ||
    (detailRankFilter.value === 'top5' && k.bestRank >= 1 && k.bestRank <= 5) ||
    (detailRankFilter.value === 'none' && (!k.bestRank || k.bestRank > 10)))
  return {
    generic: data.filter(k => k.type === '通用词').length,
    brand: data.filter(k => k.type === '品牌词').length,
  }
})

/* 排名分布 - 基于全部数据，不受筛选影响 */
const rankDist = computed(() => {
  const data = keywordData.value
  const total = data.length || 1
  const top1 = data.filter(k => k.bestRank === 1).length
  const top23 = data.filter(k => k.bestRank >= 2 && k.bestRank <= 3).length
  const top45 = data.filter(k => k.bestRank >= 4 && k.bestRank <= 5).length
  const low = data.filter(k => k.bestRank >= 6 && k.bestRank <= 10).length
  const none = data.filter(k => !k.bestRank || k.bestRank > 10).length
  return {
    top1: { count: top1, pct: Math.round(top1 / total * 100) },
    top3: { count: top23, pct: Math.round(top23 / total * 100) },
    top5: { count: top45, pct: Math.round(top45 / total * 100) },
    low: { count: low, pct: Math.round(low / total * 100) },
    none: { count: none, pct: Math.round(none / total * 100) },
  }
})

/* 词类型分割统计 - 基于全部数据，不受筛选影响 */
const wordSplit = computed(() => {
  const data = keywordData.value
  const generic = data.filter(k => k.type === '通用词')
  const brand = data.filter(k => k.type === '品牌词')
  const calc = (arr) => {
    const total = arr.length
    const ranked = arr.filter(k => k.bestRank && k.bestRank <= 10).length
    const top1 = arr.filter(k => k.bestRank === 1).length
    return { total, ranked, rate: total ? Math.round(ranked / total * 100) : 0, top1 }
  }
  return { generic: calc(generic), brand: calc(brand) }
})

/* 详情面板 - 平均排名 */
const detailAvgRankValue = computed(() => avgRankOverall.value)

/* ===== 方法 ===== */
function setScope(v) {
  scope.value = v
  currentPage.value = 1
}

function resetFilters() {
  searchText.value = ''
  filterStatus.value = ''
}

function rrClass(rate) {
  if (rate >= 50) return 'rr-good'
  if (rate >= 25) return 'rr-warn'
  return 'rr-bad'
}

function statusText(s) {
  return ({ done: '已完成', running: '进行中', error: '异常', pending: '等待中' })[s] || s || '—'
}

function formatDate(dt) {
  if (!dt) return ''
  const d = new Date(dt)
  return `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function formatTime(dt) {
  if (!dt) return ''
  const d = new Date(dt)
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

function rankBadgeClass(rank) {
  if (!rank || rank > 10) return 'rank-low'
  if (rank <= 3) return 'rank-top3'
  if (rank <= 5) return 'rank-top5'
  return 'rank-mid'
}

function getModelTagStyle(model) {
  const map = {
    'ChatGPT': { bg: '#eff6ff', color: '#2563eb', border: '#bfdbfe' },
    'Google AIO': { bg: '#f0fdf4', color: '#16a34a', border: '#bbf7d0' },
    'Google AIM': { bg: '#f0fdf4', color: '#15803d', border: '#86efac' },
    'Gemini': { bg: '#fefce8', color: '#ca8a04', border: '#fde68a' },
    'Perplexity': { bg: '#fdf2f8', color: '#db2777', border: '#fbcfe8' },
    'Copilot': { bg: '#f5f3ff', color: '#7c3aed', border: '#ddd6fe' },
  }
  const style = map[model] || { bg: '#f1f5f9', color: '#475569', border: '#e2e8f0' }
  return `background:${style.bg};color:${style.color};border-color:${style.border}`
}

/* 各平台统计 - 基于 engines 数组统计每个平台的排名情况 */
function platformStat(platform) {
  const allData = keywordData.value
  // 找到该平台有引擎记录的数据
  const platformData = allData.filter(k => k.engines && k.engines.some(e => e.name === platform))
  const total = platformData.length
  const ranked = platformData.filter(k => {
    const eng = k.engines.find(e => e.name === platform)
    return eng && eng.rank && eng.rank <= 10
  }).length
  return { total, ranked, rate: total ? Math.round(ranked / total * 100) : 0 }
}

function onRowClick(row) {
  viewDetail(row)
}

/* ===== 新建分析相关 ===== */
function showCreateDialog() {
  createDialogVisible.value = true
}

function resetCreateForm() {
  createForm.value = {
    dataSource: 'account',
    accountId: null,
    prompt: '',
    brandInput: [],
    brands: [],
    includeBrandWords: false,
    queryPlatform: '',
    queryPlatforms: [],
    queryDate: '',
    taskName: '',
  }
  createLoading.value = false
}

function onBrandChange(val) {
  // el-select allow-create 的 change 会直接返回数组
  createForm.value.brands = val || []
}

function removeBrand(idx) {
  const brands = [...createForm.value.brands]
  brands.splice(idx, 1)
  createForm.value.brands = brands
  createForm.value.brandInput = brands
}

async function submitCreate() {
  // 校验
  if (createForm.value.dataSource === 'account') {
    if (!createForm.value.accountId) {
      ElMessage.warning('请选择客户')
      return
    }
    if (!createForm.value.queryDate) {
      ElMessage.warning('请选择查词日期')
      return
    }
  }
  if (createForm.value.dataSource === 'manual') {
    if (!createForm.value.prompt.trim()) {
      ElMessage.warning('请输入提示词')
      return
    }
    if (!createForm.value.queryPlatforms.length) {
      ElMessage.warning('请至少选择一个查询平台')
      return
    }
  }
  if (!createForm.value.brands.length) {
    ElMessage.warning('请至少添加一个分析品牌')
    return
  }

  createLoading.value = true
  try {
    const payload = {
      accountId: createForm.value.accountId,
      brands: createForm.value.brands,
      queryDate: createForm.value.queryDate,
      taskName: createForm.value.taskName,
    }
    await api.submitRankingAnalysis(payload)
    const actionText = createForm.value.dataSource === 'account' ? '开始分析' : '查词并分析'
    ElMessage.success(`${actionText}任务已创建，正在后台执行...`)
    createDialogVisible.value = false
    loadData()
  } catch (e) {
    ElMessage.error('创建失败：' + (e.message || '未知错误'))
  } finally {
    createLoading.value = false
  }
}

/* ===== 查看详情相关 ===== */
const detailLoading = ref(false)

async function viewDetail(row) {
  detailRow.value = row
  showHistory.value = false
  showMoreData.value = false
  // 重置所有筛选
  detailRankFilter.value = ''
  detailWordTypeFilter.value = ''
  detailFilterPlatform.value = ''
  detailKeywordSearch.value = ''
  detailCurrentPage.value = 1
  detailDrawerVisible.value = true

  // 从 API 加载详情数据
  detailLoading.value = true
  try {
    const detail = await api.getRankingDetail(row.id)
    if (detail) {
      keywordData.value = detail.keywordData || []
      historyData.value = detail.historyData || []
      // 用详情数据更新 detailRow（更准确）
      detailRow.value = {
        ...row,
        brands: detail.brands || row.brands || [],
        analysisCount: detail.analysisCount ?? row.analysisCount,
        resultCount: detail.resultCount ?? row.resultCount,
        rankingRate: detail.rankingRate ?? row.rankingRate,
        top3Rate: detail.top3Rate ?? row.top3Rate,
        status: detail.status || row.status,
        lastAnalysisTime: detail.lastAnalysisTime || row.lastAnalysisTime,
      }
    }
  } catch (e) {
    ElMessage.error('加载详情失败：' + (e.message || '未知错误'))
    keywordData.value = []
    historyData.value = []
  } finally {
    detailLoading.value = false
  }
}

function openCreateForCustomer() {
  detailDrawerVisible.value = false
  // 预填客户信息
  createForm.value.dataSource = 'account'
  createForm.value.accountId = detailRow.value?.id
  createForm.value.brands = detailRow.value?.brands || []
  createForm.value.brandInput = detailRow.value?.brands || []
  createDialogVisible.value = true
}

async function viewHistoryTask(task) {
  // 点击详情后切换到该历史任务的排名分析结果
  showHistory.value = false
  try {
    const results = await api.getRankingResults(task.id)
    if (results && results.results) {
      // 将结果转换为 keywordData 格式
      const kwMap = {}
      for (const r of results.results) {
        const kw = r.keyword || ''
        if (!kwMap[kw]) {
          kwMap[kw] = {
            id: r.id || Date.now(),
            keyword: kw,
            type: r.type || '通用词',
            model: r.model || r.platform || '',
            bestRank: r.brand_rank || null,
            engines: [],
            snippet: r.snippet || '',
          }
        }
        kwMap[kw].engines.push({ name: r.model || r.platform || '', rank: r.brand_rank })
        if (r.brand_rank && (!kwMap[kw].bestRank || r.brand_rank < kwMap[kw].bestRank)) {
          kwMap[kw].bestRank = r.brand_rank
        }
      }
      keywordData.value = Object.values(kwMap)
      ElMessage.success(`已切换到任务 ${task.createdAt} 的排名分析结果`)
    }
  } catch (e) {
    ElMessage.error('加载历史任务结果失败：' + (e.message || '未知错误'))
  }
}

async function reanalyzeTask(task) {
  try {
    await api.rerunRanking(task.id)
    ElMessage.success(`已重新启动「${detailRow.value?.customerName}」的分析任务`)
    // 刷新详情
    if (detailRow.value) {
      viewDetail(detailRow.value)
    }
  } catch (e) {
    ElMessage.error('重新分析失败：' + (e.message || '未知错误'))
  }
}

async function deleteTask(task) {
  try {
    await api.deleteRanking(task.id)
    ElMessage.success('已删除分析记录')
    // 刷新历史数据
    if (detailRow.value) {
      const detail = await api.getRankingDetail(detailRow.value.id)
      historyData.value = detail?.historyData || []
    }
  } catch (e) {
    ElMessage.error('删除失败：' + (e.message || '未知错误'))
  }
}

/* ===== 导出功能 ===== */
function handleExportCmd(cmd) {
  if (cmd === 'current') {
    exportDetailRow(detailRow.value)
  } else if (cmd === 'all') {
    // 导出全部（按客户维度）
    if (!detailRow.value) return
    const url = api.exportRankingByAccount(detailRow.value.id)
    window.open(url, '_blank')
    ElMessage.success('正在导出全部数据...')
  } else if (cmd === 'detail') {
    exportDetailRow(detailRow.value)
  }
}

function viewKeywordDetail(keyword) {
  ElMessage.info(`查看「${keyword.keyword}」的各引擎排名详情`)
}

/* ===== 导出功能 ===== */
function exportRow(row) {
  exportDetailRow(row)
}

function exportDetailRow(row) {
  const data = row || detailRow.value
  if (!data) return

  // 构造导出数据
  const headers = ['客户', '品牌', '上榜率·通用词', '前三率·通用词', '最新状态', '最近分析']
  const exportRows = [headers, [
    data.customerName,
    (data.brands || []).join('、'),
    `${data.rankingRate}%`,
    `${data.top3Rate}%`,
    statusText(data.status),
    data.lastAnalysisTime ? `${formatDate(data.lastAnalysisTime)} ${formatTime(data.lastAnalysisTime)}` : '—',
  ]]

  // 如果是详情抽屉导出，追加关键词数据
  if (filteredKeywordData.value.length) {
    exportRows.push([])
    exportRows.push(['--- 关键词排名明细 ---'])
    exportRows.push(['关键词', '类型', '模型', '最佳排名'])
    filteredKeywordData.value.forEach(k => {
      exportRows.push([k.keyword, k.type, k.model, String(k.bestRank || '-')])
    })
  }

  // 生成 CSV 并下载
  const csvContent = '\uFEFF' + exportRows.map(r => r.map(c => `"${String(c).replace(/"/g, '""')}"`).join(',')).join('\n')
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = `排名分析_${data.customerName}_${new Date().toISOString().slice(0, 10)}.csv`
  link.click()
  URL.revokeObjectURL(link.href)

  ElMessage.success(`已导出「${data.customerName}」的排名分析结果`)
}

async function loadData() {
  loading.value = true
  try {
    const data = await api.getToolTasks()
    rows.value = Array.isArray(data) ? data : []
  } catch (e) {
    ElMessage.error('加载列表失败：' + (e.message || '未知错误'))
    rows.value = []
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadData()
  loadCustomerOptions()
})
</script>

<style scoped>
.ranking-page {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

/* ===== 数据概览 Stats Bar ===== */
.stats-bar {
  display: flex;
  align-items: center;
  gap: 0;
  background: #fff;
  border: 1px solid #eef2f7;
  border-radius: 12px;
  padding: 14px 20px;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
}
.sb-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 0 18px;
}
.sb-num {
  font-size: 22px;
  font-weight: 800;
  color: #0f172a;
  font-variant-numeric: tabular-nums;
  line-height: 1.1;
}
.sb-label {
  font-size: 11.5px;
  color: #94a3b8;
}
.sb-divider {
  width: 1px;
  height: 32px;
  background: #e2e8f0;
}
.sb-success .sb-num { color: #16a34a; }
.sb-warn .sb-num { color: #d97706; }
.sb-brand .sb-num { color: #2563eb; }
.sb-fail .sb-num { color: #dc2626; }

/* ===== 排名分布 ===== */
.rank-distribution {
  background: #fafbfc;
  border: 1px solid #f1f5f9;
  border-radius: 10px;
  padding: 14px 16px;
}
.rd-title {
  font-size: 13px;
  font-weight: 600;
  color: #334155;
  margin-bottom: 10px;
}
.rd-bar {
  display: flex;
  height: 28px;
  border-radius: 6px;
  overflow: hidden;
  gap: 2px;
}
.rd-seg {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  color: #fff;
  min-width: 24px;
  transition: filter .15s;
  cursor: default;
}
.rd-seg:hover { filter: brightness(1.1); }
.rd-top1 { background: linear-gradient(135deg, #ca8a04, #eab308); }
.rd-top3 { background: linear-gradient(135deg, #22c55e, #4ade80); }
.rd-top5 { background: linear-gradient(135deg, #3b82f6, #60a5fa); }
.rd-low { background: linear-gradient(135deg, #94a3b8, #cbd5e1); }
.rd-none { background: linear-gradient(135deg, #ef4444, #f87171); }
.rd-legend {
  display: flex;
  gap: 14px;
  margin-top: 8px;
  flex-wrap: wrap;
}
.rd-leg {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 11.5px;
  color: #64748b;
}
.rd-dot {
  width: 8px; height: 8px;
  border-radius: 2px;
  display: inline-block;
}

/* ===== 更多分析数据（折叠） ===== */
.more-data-section {
  background: #fafbfc;
  border: 1px solid #f1f5f9;
  border-radius: 10px;
  overflow: hidden;
  flex-shrink: 0; /* 防止在flex布局中被压缩 */
}
.md-toggle {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 12px 16px;
  background: none;
  border: none;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  color: #475569;
  transition: background 0.15s;
}
.md-toggle:hover { background: #f1f5f9; }
.md-toggle .el-icon {
  transition: transform 0.25s;
  font-size: 12px;
  color: #94a3b8;
}
.md-toggle .el-icon.is-expanded {
  transform: rotate(180deg);
}
.md-content {
  padding: 0 16px 14px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.md-sub-title {
  font-size: 12.5px;
  font-weight: 700;
  color: #334155;
  padding-top: 4px;
  border-top: 1px solid #eef2f7;
}
.platform-stats {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.ps-item {
  display: flex;
  align-items: center;
  gap: 10px;
}
.ps-name {
  font-size: 11.5px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 4px;
  white-space: nowrap;
  min-width: 85px;
  text-align: center;
}
.ps-bar-wrap {
  flex: 1;
  height: 18px;
  background: #eef2f7;
  border-radius: 4px;
  overflow: hidden;
}
.ps-bar {
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s ease;
  min-width: 2px;
}
.ps-val {
  font-size: 11px;
  color: #64748b;
  white-space: nowrap;
  min-width: 90px;
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.brand-detail-table {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.bd-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 6px 10px;
  background: #fff;
  border-radius: 6px;
  border: 1px solid #f1f5f9;
}
.bd-kw {
  flex: 1;
  font-size: 12.5px;
  font-weight: 500;
  color: #334155;
}
.bd-rank {
  font-size: 13px;
  font-weight: 700;
  min-width: 32px;
  text-align: center;
}
.bd-model {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 4px;
  border: 1px solid;
  white-space: nowrap;
}
.bd-empty {
  text-align: center;
  color: #94a3b8;
  font-size: 12.5px;
  padding: 12px 0;
}

/* ===== 词类型上榜率 ===== */
.word-split-bar {
  display: flex;
  align-items: stretch;
  gap: 10px;
}
.ws-card {
  flex: 1;
  border-radius: 8px;
  padding: 10px 14px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.ws-general {
  background: #eff6ff;
  border: 1px solid #bfdbfe;
}
.ws-brand {
  background: #fffbeb;
  border: 1px solid #fde68a;
}
.ws-head {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: #475569;
}
.ws-dot {
  width: 7px; height: 7px;
  border-radius: 50%;
}
.ws-general .ws-dot { background: #3b82f6; }
.ws-brand .ws-dot { background: #f59e0b; }
.ws-body {
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.ws-main {
  font-size: 13px;
  font-weight: 600;
  color: #64748b;
}
.ws-rate {
  font-size: 22px;
  font-weight: 800;
}
.ws-general .ws-rate { color: #2563eb; }
.ws-brand .ws-rate { color: #d97706; }
.ws-note {
  font-size: 11px;
  color: #94a3b8;
  line-height: 1.4;
  max-width: 280px;
  display: flex;
  align-items: center;
}

/* ===== 快捷筛选栏 ===== */
.result-filter-bar {
  margin-bottom: 10px;
}
.rf-pills {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}
.rf-group-label {
  font-size: 12px;
  color: #94a3b8;
  font-weight: 500;
  margin-right: 2px;
}
.rf-pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  background: #fff;
  font-size: 12px;
  color: #64748b;
  cursor: pointer;
  transition: all .15s;
  font-family: inherit;
  line-height: 1.4;
}
.rf-pill:hover { border-color:#94a3b8; color:#334155; }
.rf-pill.active {
  background: #2563eb;
  color: #fff;
  border-color: #2563eb;
}
.rf-pill em {
  font-style: normal;
  font-size: 11px;
  opacity: 0.85;
  font-weight: 600;
}
.rf-pill.active em { opacity: 1; }
.rf-pill-top1.active { background: #ca8a04; border-color: #ca8a04; }
.rf-pill-top3.active { background: #22c55e; border-color: #22c55e; }
.rf-pill-top5.active { background: #3b82f6; border-color: #3b82f6; }
.rf-pill-none.active { background: #ef4444; border-color: #ef4444; }
.rf-sep {
  width: 1px;
  height: 20px;
  background: #e2e8f0;
  margin: 0 6px;
}
.kpi-strip {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}
.kpi-card {
  display: flex;
  align-items: center;
  gap: 12px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 14px 16px;
  cursor: pointer;
  transition: transform .15s, box-shadow .15s, border-color .15s;
  outline: none;
}
.kpi-card:hover,
.kpi-card:focus-visible {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(15, 23, 42, 0.06);
  border-color: #cbd5e1;
}
.kpi-card.active {
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59,130,246,0.15);
}
.kpi-icon {
  width: 36px; height: 36px;
  border-radius: 9px;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.kpi-icon-blue { background: #eff6ff; color: #2563eb; }
.kpi-icon-purple { background: #f5f3ff; color: #7c3aed; }
.kpi-icon-green { background: #ecfdf5; color: #059669; }
.kpi-icon-orange { background: #fff7ed; color: #ea580c; }
.kpi-body { flex: 1; min-width: 0; }
.kpi-label { font-size: 11px; color: #94a3b8; margin-bottom: 2px; }
.kpi-val {
  font-size: 22px; font-weight: 800; color: #0f172a;
  line-height: 1.1; letter-spacing: -0.3px;
  font-variant-numeric: tabular-nums;
}
.kpi-sub { font-size: 11px; color: #64748b; margin-top: 3px; }
.kpi-sub-live { color: #ea580c; font-weight: 600; }

/* ===== 面板 ===== */
.panel {
  background: #fff;
  border: 1px solid #eef2f7;
  border-radius: 14px;
  padding: 18px 22px;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
}

/* ===== 类别 tabs ===== */
.category-tabs {
  display: inline-flex;
  gap: 4px;
  margin-bottom: 14px;
  padding: 4px;
  background: #f1f5f9;
  border-radius: 10px;
}
.cat-tab {
  background: transparent; border: none; cursor: pointer;
  padding: 8px 18px;
  border-radius: 7px;
  font-size: 13px; font-weight: 600;
  color: #64748b;
  display: inline-flex; align-items: center; gap: 8px;
  transition: all .15s;
  font-family: inherit;
}
.cat-tab:hover { color: #0f172a; }
.cat-tab.active {
  background: #fff; color: #0f172a;
  box-shadow: 0 2px 6px rgba(15, 23, 42, 0.08);
}
.cat-tab-dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: #f59e0b;
  box-shadow: 0 0 6px rgba(245, 158, 11, 0.5);
}
.cat-tab-dot-temp { background: #14b8a6; box-shadow: 0 0 6px rgba(20,184,166,.5); }
.cat-tab-temp.active {
  background: linear-gradient(135deg, #ccfbf1, #99f6e4);
  color: #0f766e;
}
.cat-tab-temp.active .cat-count { background: rgba(15,118,110,.15); color: #0f766e; }
.cat-count {
  font-size: 11px;
  padding: 1px 8px;
  background: rgba(0,0,0,.06);
  border-radius: 99px;
  color: #64748b;
}
.cat-tab.active .cat-count { background: rgba(99, 102, 241, .12); color: #4338ca; }

/* ===== 工具栏 ===== */
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}
.toolbar-tabs {
  display: inline-flex;
  background: #f1f5f9;
  border-radius: 8px;
  padding: 3px;
  gap: 2px;
}
.seg {
  background: transparent;
  border: none;
  padding: 6px 14px;
  border-radius: 6px;
  font-size: 13px;
  color: #64748b;
  font-weight: 500;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  transition: background .15s, color .15s, box-shadow .15s;
}
.seg:hover { color: #0f172a; }
.seg.active {
  background: #fff;
  color: #0f172a;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.08);
}
.seg-count {
  font-size: 11px;
  padding: 1px 7px;
  border-radius: 10px;
  background: rgba(148, 163, 184, 0.15);
  color: #64748b;
  font-weight: 600;
}
.seg.active .seg-count { background: #eff6ff; color: #2563eb; }
.toolbar-actions {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
}
.toolbar-search { width: 240px; }

/* ===== 表格 ===== */
.ranking-table {
  --el-table-border-color: transparent;
  --el-table-header-bg-color: transparent;
  --el-table-row-hover-bg-color: #f8fafc;
  cursor: pointer;
}
.ranking-table :deep(.el-table__header-wrapper) {
  border-bottom: 1px solid #f1f5f9;
}
.ranking-table :deep(.el-table__header th) {
  background: transparent !important;
  padding: 10px 0 !important;
  text-transform: none;
}
.ranking-table :deep(.el-table__body td) {
  border-bottom: 1px solid #f1f5f9 !important;
  padding: 9px 0 !important;
  background: transparent !important;
}
.ranking-table :deep(.el-table__row:hover > td) {
  background: #f8fafc !important;
}
.ranking-table :deep(.el-table::before) { display: none; }

/* 客户单元格 */
.customer-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
  padding-right: 8px;
  padding-left: 2px;
}
.ca-name-row {
  display: flex; align-items: center; gap: 7px; min-width: 0;
}
.ca-type-dot {
  width: 7px; height: 7px; border-radius: 50%;
  flex-shrink: 0;
  box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.8);
}
.ca-dot-paid { background: #22c55e; }
.ca-dot-temp { background: #14b8a6; }
.ca-name {
  font-size: 14px; font-weight: 600; color: #0f172a;
  letter-spacing: -0.1px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  transition: color .15s;
}
.customer-cell:hover .ca-name { color: #2563eb; }
.ca-meta {
  display: flex; align-items: center; gap: 6px;
  font-size: 11.5px; color: #94a3b8; line-height: 1.3;
  padding-left: 14px;
}
.ca-meta-item {
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.1px;
}
.ca-meta-sep { color: #e2e8f0; }

/* 品牌列 */
.brand-cell {
  display: flex; flex-wrap: nowrap; gap: 4px;
  align-items: center; overflow: hidden;
}
.brand-tag {
  font-size: 12px; padding: 2px 8px; border-radius: 5px;
  background: #eff6ff; color: #1d4ed8;
  font-weight: 500; white-space: nowrap; flex-shrink: 0;
  letter-spacing: 0.1px;
  max-width: 120px; overflow: hidden; text-overflow: ellipsis;
}
.brand-tag-more {
  background: #f1f5f9; color: #64748b; cursor: default;
}

/* 上榜率/前三率 */
.rr-cell {
  display: flex; align-items: center; gap: 8px;
  min-width: 0;
}
.rr-bar {
  flex: 1;
  height: 6px;
  background: #f1f5f9;
  border-radius: 3px;
  overflow: hidden;
  min-width: 40px;
}
.rr-fill {
  height: 100%;
  border-radius: 3px;
  transition: width .3s ease;
}
.rr-good { background: #22c55e; }
.rr-warn { background: #f59e0b; }
.rr-bad { background: #ef4444; }
.rr-num {
  font-size: 12px; font-weight: 700;
  font-variant-numeric: tabular-nums;
  min-width: 32px;
  background: transparent !important;
}
.rr-num.rr-good { color: #16a34a; }
.rr-num.rr-warn { color: #d97706; }
.rr-num.rr-bad { color: #dc2626; }

/* 状态 */
.status-pill {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 2px 8px; border-radius: 4px;
  font-size: 11px; font-weight: 600;
  letter-spacing: 0.3px;
  white-space: nowrap;
}
.status-dot {
  display: inline-block; width: 6px; height: 6px; border-radius: 50%;
}
.status-pill-done { background: #dcfce7; color: #15803d; }
.status-pill-done .status-dot { background: #22c55e; }
.status-pill-running { background: #eff6ff; color: #1d4ed8; }
.status-pill-running .status-dot { background: #2563eb; animation: pulse 1.4s ease-in-out infinite; }
.status-pill-error { background: #fee2e2; color: #b91c1c; }
.status-pill-error .status-dot { background: #ef4444; }
.status-pill-pending { background: #fef3c7; color: #b45309; }
.status-pill-pending .status-dot { background: #f59e0b; }
@keyframes pulse { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:.3;transform:scale(.7)} }

/* 最近分析 */
.last-search {
  display: flex; flex-direction: column; gap: 1px;
  white-space: nowrap; font-variant-numeric: tabular-nums;
  line-height: 1.3;
}
.ls-date {
  font-size: 12.5px; font-weight: 500; color: #334155;
}
.ls-rel {
  font-size: 11px; color: #94a3b8; letter-spacing: 0.1px;
}

.muted {
  font-size: 13px; color: #cbd5e1; letter-spacing: 0.2px;
}

/* 操作 */
.act-btn {
  display: inline-flex; align-items: center; justify-content: center;
  background: transparent; border: none;
  padding: 5px 10px; font-size: 13px; font-weight: 500;
  cursor: pointer; border-radius: 5px;
  transition: background .15s, color .15s;
  line-height: 1; vertical-align: middle;
}
.act-btn-primary { color: #2563eb; gap: 3px; }
.act-btn-primary:hover { background: #eff6ff; color: #1d4ed8; }
.act-btn-more {
  width: 28px; height: 28px; padding: 0; color: #94a3b8; margin-left: 4px;
}
.act-btn-more:hover { background: #f1f5f9; color: #0f172a; }

/* 空状态 */
.table-empty {
  padding: 40px 0; text-align: center; color: #94a3b8;
  display: flex; flex-direction: column; align-items: center; gap: 12px;
}
.table-empty p { margin: 0; }

/* 分页 */
.pagination-row {
  display: flex; justify-content: flex-end; padding: 12px 0 2px;
}

/* ===== 响应式 ===== */
@media (max-width: 768px) {
  .kpi-strip {
    grid-template-columns: repeat(2, 1fr);
  }
  .toolbar {
    flex-direction: column;
    align-items: stretch;
  }
  .toolbar-tabs {
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
  }
  .toolbar-actions {
    justify-content: flex-end;
  }
  .toolbar-search { width: 100%; }
}

/* ========== 新建分析弹窗 ========== */
.create-dialog :deep(.el-dialog__body) {
  padding-top: 12px;
}
.create-options {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.auto-info {
  font-size: 13px;
  color: #475569;
  font-weight: 500;
}
.auto-status {
  margin-left: 12px;
  font-size: 12px;
  color: #16a34a;
  font-weight: 500;
}
.no-brand {
  font-size: 12px;
  color: #94a3b8;
}

/* 表单提示文字 */
.form-hint {
  font-size: 11.5px;
  color: #94a3b8;
  line-height: 1.5;
  margin-top: 4px;
}
.form-hint strong {
  color: #64748b;
  font-weight: 600;
}

/* 查询平台 checkbox 组 */
.platform-checkbox-group {
  display: flex;
  flex-wrap: wrap;
  gap: 0;
}
.platform-checkbox-group :deep(.el-checkbox) {
  margin-right: 18px;
  margin-bottom: 6px;
}
.platform-checkbox-group :deep(.el-checkbox__label) {
  font-size: 13px;
}

/* ========== 查看详情抽屉 ========== */
.customer-panel {
  gap: 14px;
  padding: 4px 0;
}

/* 头部 */
.cp-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid #f1f5f9;
}
.cp-left {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}
.cp-left h3 {
  margin: 0;
  font-size: 17px;
  font-weight: 700;
  color: #0f172a;
  line-height: 1.3;
}
.cp-brand {
  font-size: 13px;
  font-weight: 500;
  color: #64748b;
}
.cp-task-count {
  font-size: 12px;
  color: #94a3b8;
}
.cp-right {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}

/* 历史切换 */
.history-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: none;
  border: 1px dashed #e2e8f0;
  border-radius: 7px;
  padding: 7px 14px;
  font-size: 13px;
  color: #64748b;
  cursor: pointer;
  transition: all .15s;
  font-family: inherit;
  width: 100%;
  justify-content: flex-start;
}
.history-toggle:hover {
  border-color: #94a3b8;
  background: #f8fafc;
  color: #334155;
}
.ht-hint {
  font-size: 11px;
  color: #cbd5e1;
  margin-left: auto;
}

/* 历史表格 */
.sub-task-table {
  overflow: hidden;
  border: 1px solid #f1f5f9;
  border-radius: 8px;
  flex-shrink: 0; /* 防止在flex布局中被压缩 */
}
.sub-task-table :deep(.el-table) {
  --el-table-border-color: #f1f5f9;
  font-size: 12.5px;
}
.brand-chip {
  display: inline-block;
  font-size: 11.5px;
  padding: 1px 7px;
  border-radius: 4px;
  background: #eff6ff;
  color: #2563eb;
  margin-right: 4px;
  margin-bottom: 2px;
}

/* KPI 行 */
.cp-kpi-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}
.cp-kpi {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  background: #f8fafc;
  border: 1px solid #f1f5f9;
  border-radius: 10px;
  padding: 12px 8px;
}
.cp-kpi-label {
  font-size: 11.5px;
  color: #94a3b8;
}
.cp-kpi-val {
  font-size: 22px;
  font-weight: 800;
  color: #0f172a;
  font-variant-numeric: tabular-nums;
}
.cp-kpi-good { color: #16a34a; }
.cp-kpi-warn { color: #d97706; }

/* 关键词排名区域 */
.kw-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.kw-section-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}
.kw-section-title {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}
.kw-section-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

/* 排名徽章 */
.rank-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: 6px;
  font-size: 12.5px;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
}
.rank-top3 { background: #dcfce7; color: #15803d; }
.rank-top5 { background: #fef9c3; color: #a16207; }
.rank-mid { background: #fee2e2; color: #b91c1c; }
.rank-low { background: #f1f5f9; color: #64748b; }

/* 模型标签 */
.model-tag {
  display: inline-block;
  font-size: 11px;
  padding: 1px 7px;
  border-radius: 4px;
  font-weight: 600;
  border: 1px solid;
  line-height: 1.6;
}
.dev-tag {
  display: inline-block;
  font-size: 10px;
  padding: 1px 5px;
  border-radius: 3px;
  font-weight: 600;
  margin-left: 4px;
}
.dev-p { background: #eff6ff; color: #2563eb; }

/* 展开行详情 */
.expand-detail {
  padding: 12px 16px;
  background: #fafbfc;
  border-radius: 6px;
}
.ed-title {
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
  margin-bottom: 8px;
}
.ed-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 8px;
  margin-bottom: 8px;
}
.ed-engine {
  display: flex;
  align-items: center;
  gap: 8px;
  background: #fff;
  border: 1px solid #f1f5f9;
  border-radius: 6px;
  padding: 6px 10px;
}
.ed-name {
  font-size: 12px;
  color: #64748b;
}
.ed-rank {
  font-size: 14px;
  font-weight: 700;
  margin-left: auto;
}
.ed-snippet {
  font-size: 12px;
  color: #94a3b8;
  line-height: 1.5;
  padding: 8px;
  background: #f8fafc;
  border-radius: 5px;
  max-height: 80px;
  overflow: hidden;
}

/* 抽屉 wrapper */
.drawer-wrapper {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

/* 抽屉头部固定 */
.drawer-wrapper .cp-header {
  flex-shrink: 0;
  padding: 16px 24px 12px;
  border-bottom: 1px solid #f1f5f9;
  background: #fff;
}

/* 抽屉内容区域可滚动 */
.drawer-wrapper .customer-panel {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 14px 24px 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

/* 详情分页 */
.detail-pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 10px;
}
</style>

<!-- 非scoped样式：el-drawer teleport到body后需要全局生效 -->
<style>
.detail-drawer .el-drawer__body {
  padding: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  height: 100%;
}
</style>
