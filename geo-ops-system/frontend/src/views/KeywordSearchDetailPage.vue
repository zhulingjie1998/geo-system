<template>
  <div class="search-page">

    <!-- ===== 面包屑 + 顶部操作区 ===== -->
    <div class="top-bar">
      <div class="bar-left">
        <el-button text @click="$router.push('/dashboard/keyword-search')" class="back-btn">
          <el-icon><ArrowLeft /></el-icon><span>返回列表</span>
        </el-button>
        <span class="bar-divider"></span>
        <span v-if="currentAccount" class="bar-company">{{ currentAccount.companyName }}</span>
        <span v-if="currentAccount?.companyBrand" class="bar-brand">{{ brandsDisplay(currentAccount.companyBrand) }}</span>
        <template v-if="currentAccount">
          <span class="bar-meta">{{ keywords.length }} 个关键词</span>
          <PlatformIcon v-for="p in platformsArray" :key="p" :name="p" :size="20" />
        </template>
      </div>

      <div class="bar-right">
        <el-select
          v-if="historyDates.length"
          v-model="selectedDate"
          placeholder="历史记录"
          style="width: 180px"
          clearable
          @change="onSelectedDateChange"
        >
          <el-option
            v-for="d in historyDatesWithCount"
            :key="d.date"
            :label="d.label"
            :value="d.date"
          />
        </el-select>
        <el-button
          v-if="selectedDate"
          type="danger"
          plain
          :loading="deletingHistory"
          @click="deleteHistoryByDate"
        >
          <el-icon><Delete /></el-icon>删除此日期
        </el-button>

        <template v-if="!taskRunning">
          <el-button
            type="primary"
            :disabled="!selectedAccountId"
            @click="confirmStartSearch"
          >
            <el-icon><VideoPlay /></el-icon>{{ startBtnLabel }}
          </el-button>
          <el-tooltip
            v-if="unsearchedCount > 0"
            :content="unsearchedTooltip"
            placement="bottom"
            :show-after="300"
          >
            <el-button
              type="warning"
              @click="continueSearch"
            >
              <el-icon><VideoPlay /></el-icon>继续查词 ({{ unsearchedCount }})
            </el-button>
          </el-tooltip>
        </template>
        <el-button
          v-else
          type="danger"
          :loading="cancelling"
          @click="cancelSearch"
        >
          <el-icon v-if="!cancelling"><VideoPause /></el-icon>停止
        </el-button>

      </div>
    </div>

    <!-- ===== 执行记录面�� ===== -->
    <div v-if="execHistory.length" class="exec-history-panel">
      <div class="eh-header" @click="execHistoryCollapsed = !execHistoryCollapsed">
        <span class="eh-title">📋 执行记录</span>
        <el-icon class="eh-arrow" :class="{ rotated: !execHistoryCollapsed }"><ArrowDown /></el-icon>
      </div>
      <transition name="slide-down">
        <div v-show="!execHistoryCollapsed" class="eh-body">
          <div
            v-for="(g, gidx) in pagedExecGroups"
            :key="g.date"
            class="eh-group"
            :class="{ 'eh-latest': gidx === 0 && execPage === 1 }"
          >
            <!-- 日期分组头：可独立展开 -->
            <div class="eh-group-header" @click="toggleExecGroup(g.date)">
              <div class="eh-item-left">
                <el-icon class="eh-group-arrow" :class="{ rotated: expandedExecGroups.has(g.date) }">
                  <ArrowRight />
                </el-icon>
                <span :class="['eh-status', 'ehs-' + g.status.toLowerCase()]">{{ ehStatusText(g.status) }}</span>
                <span class="eh-date">{{ g.date }}</span>
                <span v-if="g.tasks.length > 1" class="eh-task-count">{{ g.tasks.length }} 次执行</span>
                <span class="eh-queries">{{ g.modelCount }} 模型</span>
                <span class="eh-queries eh-queries-ok">成功 {{ g.success }}<span class="eh-sep">/</span>{{ g.target || g.execTotal }}</span>
                <span v-if="g.pending > 0" class="eh-fail-badge">{{ g.pending }} 未完成</span>
              </div>
              <div class="eh-item-right">
                <el-button
                  v-if="g.pending > 0 && g.isToday && !taskRunning"
                  size="small"
                  type="warning"
                  plain
                  @click.stop="continueSearch"
                >重试失败</el-button>
                <span v-if="g.totalInDb > 0" class="eh-db-ok">✅ {{ g.totalInDb }} 条入库</span>
              </div>
            </div>

            <!-- 分组展开内容 -->
            <div v-if="expandedExecGroups.has(g.date)" class="eh-group-body">
              <!-- 模型聚合 -->
              <div v-if="g.modelStats.length" class="eh-models">
                <div v-for="ms in g.modelStats" :key="ms.model" class="eh-model-chip" :style="ehModelStyle(ms.model)">
                  <PlatformIcon :name="ms.model" :size="15" />
                  <span class="ehmc-num">{{ ms.success }}条</span>
                  <span v-if="ms.fail > 0" class="ehmc-fail">{{ ms.fail }}失败</span>
                  <span v-else class="ehmc-ok">✓</span>
                </div>
              </div>

              <!-- 当天每次任务的详情，可独立展开 -->
              <div v-if="g.tasks.length > 1 || g.errorMessage" class="eh-subtasks">
                <div
                  v-for="ex in g.tasks"
                  :key="ex.taskId"
                  class="eh-subtask"
                >
                  <div class="eh-subtask-header" @click="toggleExecTask(ex.taskId)">
                    <el-icon class="eh-group-arrow" :class="{ rotated: expandedExecTasks.has(ex.taskId) }">
                      <ArrowRight />
                    </el-icon>
                    <span :class="['eh-status', 'ehs-' + (ex.status||'').toLowerCase()]">{{ ehStatusText(ex.status) }}</span>
                    <span class="eh-run-type">{{ ex.runType }}</span>
                    <span class="eh-time">{{ ex.createdAt?.slice(11, 16) }}</span>
                    <span v-if="ex.completedAt" class="eh-time">→ {{ ex.completedAt?.slice(11, 16) }}</span>
                    <span class="eh-queries">本次 {{ ex.completedQueries }}<span class="eh-sep">/</span>{{ ex.totalQueries }}</span>
                    <span v-if="ex.totalInDb > 0" class="eh-db-ok">✅ {{ ex.totalInDb }}</span>
                    <el-tooltip content="精确删除该次查词任务（同一天其他任务保留）" placement="top">
                      <el-button
                        size="small" type="danger" plain
                        class="eh-task-del"
                        :icon="Delete"
                        :disabled="['RUNNING','QUEUED'].includes((ex.status||'').toUpperCase())"
                        @click.stop="deleteSingleTask(g, ex)"
                      >删除此次</el-button>
                    </el-tooltip>
                  </div>
                  <div v-if="expandedExecTasks.has(ex.taskId)" class="eh-subtask-body">
                    <div v-if="ex.modelStats?.length" class="eh-models">
                      <div v-for="ms in ex.modelStats" :key="ms.model" class="eh-model-chip" :style="ehModelStyle(ms.model)">
                        <PlatformIcon :name="ms.model" :size="15" />
                        <span class="ehmc-num">{{ ms.success }}条</span>
                        <span v-if="ms.fail > 0" class="ehmc-fail">{{ ms.fail }}失败</span>
                        <span v-else class="ehmc-ok">✓</span>
                      </div>
                    </div>
                    <div v-if="ex.errorMessage" class="eh-error">
                      <el-icon class="eh-error-icon"><WarningFilled /></el-icon>
                      <span class="eh-error-label">失败原因：</span>
                      <span class="eh-error-text">{{ ex.errorMessage }}</span>
                      <span v-if="ex.totalQueries > ex.completedQueries" class="eh-error-pending">还有 {{ ex.totalQueries - ex.completedQueries }} 个查询未执行</span>
                    </div>
                  </div>
                </div>
              </div>

              <!-- 单次任务时直接显示错误 -->
              <div v-else-if="g.errorMessage" class="eh-error">
                <el-icon class="eh-error-icon"><WarningFilled /></el-icon>
                <span class="eh-error-label">失败原因：</span>
                <span class="eh-error-text">{{ g.errorMessage }}</span>
              </div>
            </div>
          </div>
          <div v-if="groupedExecHistory.length > execPageSize" class="eh-pagination">
            <el-pagination
              v-model:current-page="execPage"
              :page-size="execPageSize"
              :total="groupedExecHistory.length"
              layout="prev, pager, next"
              background
              small
            />
          </div>
        </div>
      </transition>
    </div>

    <!-- ===== 进度面板 ===== -->
    <transition name="slide-down">
      <div v-if="showProgress" class="prog-panel" :class="progPanelCls">
        <!-- 折叠/展开 -->
        <div class="prog-head">
          <div class="prog-title">
            <span v-if="taskRunning" class="pulse-dot"></span>
            <template v-if="taskProgress.status === 'COMPLETED'">查词完成</template>
            <template v-else-if="taskProgress.status === 'ERROR'">查词出错</template>
            <template v-else-if="taskProgress.status === 'CANCELLED'">已停止</template>
            <template v-else-if="retrySession.active && retrySession.type === 'failed'">
              重试失败查询
            </template>
            <template v-else-if="retrySession.active && retrySession.type === 'continue'">
              继续未完成查询
            </template>
            <template v-else>查词进行中</template>
            <span v-if="retrySession.active && taskRunning" class="prog-retry-badge">
              {{ retrySession.type === 'failed' ? '补查' : '续查' }}
              {{ retrySession.total - retryRemaining }}<span class="prog-sep">/</span>{{ retrySession.total }}
            </span>
            <span v-if="taskRunning && taskProgress.currentKeyword" class="prog-cur-kw">
              · 当前：{{ taskProgress.currentKeyword.length > 18 ? taskProgress.currentKeyword.slice(0,18) + '...' : taskProgress.currentKeyword }}
            </span>
          </div>
          <div class="prog-head-right">
            <div class="prog-meta">
              <span class="prog-nums">{{ displayCompleted }}<span class="prog-sep">/</span>{{ fullDenominator }}</span>
              <span v-if="logInflightCount > 0" class="prog-inflightbadge" :class="{ 'prog-stalledbadge': logStalledCount > 0 }">
                {{ logStalledCount > 0 ? `⚠ ${logStalledCount} 卡死 / ` : '' }}{{ logInflightCount }} 查询中
              </span>
              <span v-if="logFailCount > 0" class="prog-failbadge">{{ logFailCount }} 失败</span>
              <span class="prog-elapsed">{{ elapsedTime }}</span>
              <span v-if="finishedAt" class="prog-finished">{{ finishedAt }}</span>
            </div>
            <el-button
              v-if="progressCollapsed && !taskRunning && logFailCount > 0"
              type="warning"
              size="small"
              :loading="retrying"
              @click="retryFailedSearch"
              style="margin-left:8px"
            >重试失败</el-button>
            <el-button
              v-if="!taskRunning && ['COMPLETED','ERROR','CANCELLED'].includes(taskProgress.status)"
              text
              size="small"
              @click="dismissProgress"
              style="margin-left:8px"
            >
              <el-icon><Close /></el-icon>
            </el-button>
            <el-button text size="small" @click="progressCollapsed = !progressCollapsed" style="margin-left:4px">
              <el-icon><component :is="progressCollapsed ? 'ArrowDown' : 'ArrowUp'" /></el-icon>
            </el-button>
          </div>
        </div>

        <template v-if="!progressCollapsed">
          <!-- 整体进度（主视觉） -->
          <div class="prog-overall-label">
            <span>整体进度</span>
            <span class="prog-overall-pct">{{ progressPercentage }}%</span>
          </div>
          <el-progress
            :percentage="progressPercentage"
            :status="progressBarStatus"
            :stroke-width="12"
            :striped="taskRunning"
            :striped-flow="taskRunning"
            :duration="12"
            text-inside
          />

          <!-- 正在查询 / 待查（醒目） -->
          <div v-if="taskRunning" class="prog-now">
            <div class="prog-now-head">
              <span class="prog-now-dot"></span>
              <span class="prog-now-label">正在查询</span>
              <span class="prog-now-kw">{{ taskProgress.currentKeyword || '调度中…' }}</span>
              <span v-if="runningPlats.length" class="prog-now-plats">@ {{ runningPlats.join(' · ') }}</span>
            </div>
            <div v-if="pendingKeywords.length" class="prog-now-pending">
              <span class="pn-label">待查 {{ pendingKeywords.length }}</span>
              <span v-for="kw in pendingKeywords.slice(0, 8)" :key="kw" class="pn-tag">{{ kw.length > 14 ? kw.slice(0, 14) + '…' : kw }}</span>
              <span v-if="pendingKeywords.length > 8" class="pn-more">+{{ pendingKeywords.length - 8 }}</span>
            </div>
          </div>

          <!-- 卡死检测提示：区分"慢"和"死" -->
          <div v-if="progressStalled" class="prog-stall-hint">
            <el-icon><WarningFilled /></el-icon>
            <span>
              查询仍在进行，已超 45 秒无新结果——通常是
              <b v-if="slowPlatforms.length">{{ slowPlatforms.join('、') }}</b><b v-else>部分平台</b>
              上游响应慢/拥堵，系统正自动重试，请耐心等待（非卡死）。
            </span>
          </div>

          <!-- 分平台独立进度条 -->
          <div v-if="platformProgress.length" class="plat-prog-list">
            <div
              v-for="pp in platformProgress"
              :key="pp.plat"
              class="plat-prog-item"
              :class="'ppi-' + pp.state"
            >
              <span class="ppi-name">{{ pp.plat }}</span>
              <div class="ppi-bar">
                <div class="ppi-fill" :style="{ width: pp.pct + '%' }"></div>
              </div>
              <span class="ppi-num">{{ pp.done }}<span class="ppi-sep">/</span>{{ pp.total }}</span>
              <span v-if="pp.fail > 0" class="ppi-fail">{{ pp.fail }}失败</span>
              <span class="ppi-ic">
                <template v-if="pp.state === 'done'">✓</template>
                <template v-else-if="pp.state === 'partial'">!</template>
                <template v-else-if="pp.state === 'running'">⟳</template>
                <template v-else>·</template>
              </span>
            </div>
          </div>

          <!-- 统计栏 -->
          <div class="prog-cards">
            <div class="prog-card">
              <div class="pc-label">成功率</div>
              <div class="pc-val pc-rate">
                {{ successRate }}%
              </div>
            </div>
            <div class="prog-card">
              <div class="pc-label">已完成</div>
              <div class="pc-stats">
                <span class="pc-s-ok">{{ logSuccessCount }} 成功</span>
                <span class="pc-s-fail">{{ logFailCount }} 失败</span>
              </div>
            </div>
            <div class="prog-card">
              <div class="pc-label">{{ taskRunning ? '预计剩余' : '平均耗时' }}</div>
              <div class="pc-val" :title="taskRunning ? ('平均每条 ' + avgDuration) : ''">
                {{ taskRunning ? etaText : avgDuration }}
              </div>
            </div>
          </div>

          <!-- 实时日志 -->
          <div v-if="progressLog.length || taskRunning" class="prog-log">
            <div class="prog-log-head">
              <span>实时查询日志</span>
              <div class="prog-log-actions">
                <el-switch
                  v-model="logOnlyFailed"
                  size="small"
                  inline-prompt
                  active-text="只看失败"
                  inactive-text="全部"
                  style="--el-switch-on-color:#f56c6c"
                />
                <el-select
                  v-if="logPlatforms.length > 1"
                  v-model="logPlatFilter"
                  size="small"
                  clearable
                  placeholder="全部平台"
                  style="width:108px"
                >
                  <el-option v-for="p in logPlatforms" :key="p" :label="p" :value="p" />
                </el-select>
                <span class="prog-log-cnt">{{ visibleProgressLog.length }} / {{ progressLog.length }}</span>
                <el-button v-if="!taskRunning && progressLog.length" text size="small" @click="exportLog">导出日志</el-button>
                <el-button text size="small" @click="logExpanded = !logExpanded">
                  {{ logExpanded ? '收起' : '展开' }}
                </el-button>
              </div>
            </div>
            <div class="prog-log-body" :class="{ 'log-expanded': logExpanded }" ref="logListRef">
              <div v-if="!progressLog.length && taskRunning" class="log-row log-row-waiting">
                <span class="pc-dot pc-dot-run" style="margin-right:8px"></span>
                <span style="color:#909399">正在并发查询中，等待第一条结果返回...</span>
              </div>
              <div v-else-if="!visibleProgressLog.length" class="log-row log-row-waiting">
                <span style="color:#909399">无匹配筛选条件的日志</span>
              </div>
              <div
                v-for="(item, idx) in visibleProgressLog"
                :key="idx"
                class="log-row"
                :class="{
                  'log-row-fail': !item.inflight && item.success === false,
                  'log-row-inflight': item.inflight,
                  'log-row-stalled': item.inflight && item.stalled
                }"
              >
                <span class="log-no">{{ idx + 1 }}</span>
                <span v-if="item.inflight" class="log-dot log-dot-inflight" :class="{ 'log-dot-stalled': item.stalled }"></span>
                <span v-else class="log-dot" :class="item.success ? 'log-dot-ok' : 'log-dot-err'"></span>
                <span class="log-kw">{{ item.keyword }}</span>
                <span class="log-plat" :style="platformTagStyle(item.platform)">{{ item.platform }}</span>
                <span v-if="item.inflight" class="log-saved log-saved-inflight"
                      :class="{
                        'log-saved-waiting': liveStatus(item).kind === 'wait',
                        'log-saved-queued': liveStatus(item).kind === 'queued',
                      }">
                  {{ liveStatus(item).label }}
                  <span v-if="item.attempts > 1" class="log-attempts">· 第{{ item.attempts }}次尝试</span>
                  <span v-if="item.lastError" class="log-lasterr" :title="item.lastError">· {{ item.lastError.slice(0,40) }}</span>
                </span>
                <span v-else class="log-saved" :class="item.success ? 'log-saved-ok' : 'log-saved-no'">{{ item.success ? '已入库' : (item.error || '失败') }}</span>
                <span class="log-dur" :class="{ 'log-dur-stalled': item.inflight && item.stalled }">
                  {{ item.inflight ? fmtSec(liveSecs(item)) : (item.duration ? item.duration.toFixed(1) + 's' : '-') }}
                </span>
              </div>
            </div>
            <!-- 新日志提示 -->
            <div v-if="hasNewLogs && !autoScroll" class="new-log-tip" @click="scrollToBottom">
              <el-icon><ArrowDown /></el-icon> 有新日志
            </div>
          </div>

          <div v-if="taskProgress.errorMessage" class="prog-err">{{ taskProgress.errorMessage }}</div>

          <!-- 完成/终止后操作按钮 -->
          <div v-if="!taskRunning && ['COMPLETED','CANCELLED','ERROR'].includes(taskProgress.status) && logFailCount > 0" class="prog-actions">
            <el-button type="warning" size="small" :loading="retrying" @click="retryFailedSearch">
              重试 {{ logFailCount }} 个失败项
            </el-button>
          </div>
        </template>
      </div>
    </transition>

    <!-- ===== 品牌提及分析 ===== -->
    <div v-if="results.length && !taskRunning && brandMentionData.platforms.length" class="brand-panel">
      <div class="brand-head">
        <div class="brand-title">
          <el-icon style="margin-right:4px"><TrendCharts /></el-icon>品牌提及分析
        </div>
        <span class="brand-summary">
          品牌「{{ brandsDisplay(currentAccount?.companyBrand) || '-' }}」在 {{ brandMentionData.total }} 条结果中被提及 {{ brandMentionData.mentioned }} 次，
          提及率 <strong :style="{ color: brandMentionData.rate >= 50 ? '#10b981' : '#f59e0b' }">{{ brandMentionData.rate }}%</strong>
        </span>
      </div>
      <div class="brand-platforms">
        <div v-for="bp in brandMentionData.platforms" :key="bp.name" class="bp-item" :class="{ 'bp-failed': !bp.hasData }">
          <span class="bp-name" :style="platformTagStyle(bp.name)">{{ bp.name }}</span>
          <template v-if="bp.hasData">
            <div class="bp-bar-wrap">
              <div class="bp-bar" :style="{ width: bp.rate + '%', background: bp.rate >= 50 ? '#10b981' : bp.rate >= 25 ? '#f59e0b' : '#ef4444' }"></div>
            </div>
            <span class="bp-rate">{{ bp.mentioned }}/{{ bp.total }} ({{ bp.rate }}%)</span>
          </template>
          <template v-else>
            <span class="bp-failed-text">查询失败 ({{ bp.failed }}条)</span>
          </template>
        </div>
      </div>
    </div>

    <!-- ===== 空状态：无关键词 ===== -->
    <div v-if="!keywords.length && !taskRunning && !results.length" class="empty-state">
      <div class="es-icon">
        <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="#cbd5e1" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/>
        </svg>
      </div>
      <div class="es-title">暂无关键词</div>
      <div class="es-desc">请先在「账号管理」中为该账号配置关键词</div>
      <el-button type="primary" size="small" style="margin-top:12px" @click="$router.push('/dashboard/accounts')">去配置关键词</el-button>
    </div>

    <!-- ===== 主内容 ===== -->
    <template v-else>

      <!-- 待查关键词（无结果且未在查词时） -->
      <div v-if="!results.length && !taskRunning" class="kw-preview-card">
        <div class="kpc-head">
          <div class="kpc-title">待查关键词</div>
          <span class="kpc-count">{{ keywords.length }} 条</span>
        </div>
        <el-table :data="keywords" max-height="480" size="small" stripe>
          <el-table-column type="index" label="#" width="50" align="center" />
          <el-table-column prop="intentCategory" label="类型" width="110">
            <template #default="{ row }">
              <span class="kpc-cat-tag">{{ row.intentCategory || '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="coreIntentWord" label="搜索意图" width="160" show-overflow-tooltip />
          <el-table-column prop="intentPrompt" label="AI 提示词" min-width="300" show-overflow-tooltip />
        </el-table>
      </div>

      <!-- 有结果时（查词中隐藏） -->
      <template v-if="results.length && !taskRunning">
        <!-- 统计栏 -->
        <div class="stats-bar">
          <div class="sb-item">
            <span class="sb-num">{{ stats.total }}</span>
            <span class="sb-label">总查询</span>
          </div>
          <span class="sb-divider"></span>
          <div class="sb-item sb-success">
            <span class="sb-num">{{ stats.success }}</span>
            <span class="sb-label">成功</span>
          </div>
          <span class="sb-divider"></span>
          <div class="sb-item sb-fail">
            <span class="sb-num">{{ stats.failed }}</span>
            <span class="sb-label">失败</span>
          </div>
          <span class="sb-divider"></span>
          <div class="sb-item">
            <span class="sb-num sb-num-sm">{{ stats.avgDuration }}</span>
            <span class="sb-label">平均耗时</span>
          </div>
          <span class="sb-divider"></span>
          <div class="sb-item">
            <span class="sb-num sb-num-sm">{{ stats.coverage }}</span>
            <span class="sb-label">覆盖率</span>
          </div>
          <div style="margin-left:auto; display:flex; gap:8px">
            <el-button
              v-if="stats.failed > 0 && latestFailedTaskId"
              size="small" type="warning" plain :loading="retrying"
              @click="retryFailedFromResults"
            >
              <el-icon><Refresh /></el-icon>重试 {{ stats.failed }} 个失败项
            </el-button>
            <el-button size="small" type="primary" plain @click="handleExport">
              <el-icon><Download /></el-icon>导出压缩包（按模型分目录）
            </el-button>
          </div>
        </div>

        <!-- 筛选 -->
        <div class="filter-bar">
          <div class="fb-platforms">
            <button
              class="fb-btn"
              :class="{ active: filterPlatform === '' }"
              @click="filterPlatform = ''"
            >全部 <em>{{ results.length }}</em></button>
            <span class="fb-group-label">平台</span>
            <button
              v-for="p in allPlatforms"
              :key="p"
              class="fb-btn"
              :class="{ active: filterPlatform === p }"
              :style="filterPlatform === p ? platformPillActiveStyle(p) : {}"
              @click="filterPlatform = p"
            >{{ p }} <em>{{ platformCountMap[p] || 0 }}</em></button>
            <template v-if="wordSplit.hasBrand">
              <span class="fb-sep"></span>
              <span class="fb-group-label">词类型</span>
              <button class="fb-btn fb-btn-word" :class="{ active: filterWord === 'general' }"
                      @click="filterWord = filterWord === 'general' ? '' : 'general'">通用词 <em>{{ wordSplit.general }}</em></button>
              <button class="fb-btn fb-btn-word" :class="{ active: filterWord === 'brand' }"
                      @click="filterWord = filterWord === 'brand' ? '' : 'brand'">品牌词 <em>{{ wordSplit.brand }}</em></button>
            </template>
          </div>
          <div class="fb-controls">
            <el-select
              v-model="filterCategory"
              placeholder="分类"
              clearable
              size="small"
              style="width: 120px"
            >
              <el-option v-for="c in allCategories" :key="c" :label="c" :value="c" />
            </el-select>
            <el-input
              v-model="searchKeyword"
              placeholder="搜索关键词..."
              clearable
              size="small"
              style="width: 160px"
            >
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
            <el-button size="small" type="warning" plain :loading="accRunning" @click="runAccuracy">
              {{ accRunning ? `检查中 ${accProgress.done}/${accProgress.total}` : '准确度检查' }}
            </el-button>
            <el-checkbox v-if="accIssueCount" v-model="onlyAccIssues" size="small">
              仅看问题答案（{{ accIssueCount }}）
            </el-checkbox>
          </div>
        </div>

        <!-- 结果表格 -->
        <div class="result-card">
          <el-table
            v-if="filteredResults.length"
            :data="pagedResults"
            size="small"
            stripe
            row-key="rowKey"
            class="result-table"
          >
            <el-table-column type="expand" width="32">
              <template #default="{ row }">
                <div class="row-expand">
                  <div v-if="accOf(row)?.status === 'issue'" class="acc-issue-list">
                    <div class="acc-issue-title">⚠ 发现 {{ accOf(row).issues.length }} 处问题（正文中已高亮）</div>
                    <div v-for="(it, i) in accOf(row).issues" :key="i" class="acc-issue-row">
                      <el-tag size="small" :type="it.type === 'negative' ? 'warning' : 'danger'" effect="plain">
                        {{ it.type === 'negative' ? '负面表述' : '事实错误' }}
                      </el-tag>
                      <span class="acc-issue-quote">“{{ it.quote }}”</span>
                      <span class="acc-issue-reason">{{ it.reason }}</span>
                    </div>
                  </div>
                  <div
                    v-if="row.success && (row.answerText || row.answerHtml)"
                    class="expand-text"
                    v-html="renderAnswerWithIssues(row)"
                  ></div>
                  <div v-else class="expand-empty">无回答内容</div>
                </div>
              </template>
            </el-table-column>

            <el-table-column label="意图分类" width="100">
              <template #default="{ row }">
                <span class="cat-badge">{{ row.intentCategory || '-' }}</span>
              </template>
            </el-table-column>

            <el-table-column label="关键词" min-width="220">
              <template #default="{ row }">
                <div class="kw-cell">
                  <div class="kw-main" :title="row.keyword || row.intentPrompt">{{ row.keyword || row.intentPrompt }}</div>
                  <div
                    v-if="row.intentPrompt && row.intentPrompt !== (row.keyword || row.intentPrompt)"
                    class="kw-sub"
                  >{{ row.intentPrompt }}</div>
                </div>
              </template>
            </el-table-column>

            <el-table-column v-if="wordSplit.hasBrand" label="词类型" width="84" align="center">
              <template #default="{ row }">
                <el-tag size="small" effect="plain" :type="isBrandWord(row) ? 'warning' : 'success'">
                  {{ isBrandWord(row) ? '品牌词' : '通用词' }}
                </el-tag>
              </template>
            </el-table-column>

            <el-table-column label="平台" width="88" align="center">
              <template #default="{ row }">
                <PlatformIcon :name="row.platform" :size="22" />
              </template>
            </el-table-column>

            <el-table-column v-if="Object.keys(accMap).length" label="准确度" width="86" align="center">
              <template #default="{ row }">
                <el-tag v-if="accOf(row)?.status === 'issue'" size="small" type="danger" effect="light">
                  ⚠ {{ accOf(row).issues.length }} 处
                </el-tag>
                <span v-else-if="accOf(row)?.status === 'ok'" style="color:#16a34a">✓</span>
                <span v-else style="color:#cbd5e1">—</span>
              </template>
            </el-table-column>

            <el-table-column label="回答摘要" min-width="280">
              <template #default="{ row }">
                <div
                  v-if="row.success"
                  class="answer-line"
                >{{ truncateText(row.answerText, 100) }}</div>
                <span v-else class="answer-fail">
                  <el-icon style="margin-right:2px"><CircleCloseFilled /></el-icon>
                  {{ row.error || '查询失败' }}
                </span>
              </template>
            </el-table-column>

            <el-table-column label="截图" width="84" align="center">
              <template #default="{ row }">
                <div v-if="row.screenshotUrl" class="shot-cell" @click.stop="openShot(row)" title="点击查看大图">
                  <img :src="row.screenshotUrl" loading="lazy" referrerpolicy="no-referrer"
                       class="shot-thumb" :alt="row.keyword" />
                  <div class="shot-overlay">
                    <el-icon><ZoomIn /></el-icon>
                  </div>
                </div>
                <span v-else class="cell-muted">-</span>
              </template>
            </el-table-column>

            <el-table-column label="耗时" width="60" align="right">
              <template #default="{ row }">
                <span class="dur-text">{{ row.duration ? row.duration.toFixed(1) + 's' : '-' }}</span>
              </template>
            </el-table-column>
          </el-table>

          <el-empty v-else description="当前筛选无结果" :image-size="80" />

          <!-- 截图大图 modal（放在 v-if/v-else 之外避免破坏配对） -->
          <el-dialog
            v-model="shotDialogVisible"
            :title="shotDialogTitle"
            width="min(960px, 92vw)"
            class="shot-dialog"
            append-to-body
            destroy-on-close
          >
            <div class="shot-dialog-meta">
              <PlatformIcon v-if="shotRow?.platform" :name="shotRow.platform" :size="22" />
              <span class="shot-meta-kw">{{ shotRow?.keyword || shotRow?.intentPrompt }}</span>
              <span v-if="shotRow?.intentCategory" class="cat-badge" style="margin-left:auto">{{ shotRow.intentCategory }}</span>
            </div>
            <div class="shot-dialog-body">
              <img v-if="shotRow?.screenshotUrl" :src="shotRow.screenshotUrl"
                   referrerpolicy="no-referrer" class="shot-fullimg" :alt="shotRow.keyword" />
            </div>
            <template #footer>
              <el-button @click="shotDialogVisible = false">关闭</el-button>
              <el-button type="primary" tag="a" :href="shotRow?.screenshotUrl" target="_blank" :icon="Download">
                下载原图
              </el-button>
            </template>
          </el-dialog>

          <div v-if="filteredResults.length" class="result-footer">
            <span class="rf-count">{{ filteredResults.length }} 条结果<span v-if="filteredResults.length < results.length">（共 {{ results.length }} 条）</span></span>
            <el-pagination
              v-model:current-page="currentPage"
              v-model:page-size="pageSize"
              :page-sizes="[20, 50, 100]"
              :total="filteredResults.length"
              layout="sizes, prev, pager, next"
              small
              background
            />
          </div>
        </div>
      </template>
    </template>

    <!-- ===== 查词确认弹窗 ===== -->
    <el-dialog v-model="confirmDialogVisible" title="确认开始查词" width="min(440px, 90vw)" :close-on-click-modal="false">
      <div class="confirm-body">
        <div class="confirm-row"><span class="confirm-label">客户</span><span class="confirm-val">{{ currentAccount?.companyName }} · {{ brandsDisplay(currentAccount?.companyBrand) }}</span></div>
        <div class="confirm-row"><span class="confirm-label">关键词</span><span class="confirm-val">{{ keywords.length }} 条</span></div>
        <div class="confirm-row"><span class="confirm-label">覆盖平台</span><span class="confirm-val">{{ platformsArray.join('、') }} ({{ platformsArray.length }} 个)</span></div>
        <div class="confirm-row confirm-total">
          <span class="confirm-label">总查询量</span>
          <span class="confirm-val"><strong>{{ keywords.length }} × {{ platformsArray.length }} = {{ keywords.length * platformsArray.length }}</strong> 条</span>
        </div>
        <div class="confirm-est">预计耗时约 {{ estimatedTime }}</div>
      </div>
      <template #footer>
        <el-button @click="confirmDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="doStartSearch">确认开始</el-button>
      </template>
    </el-dialog>

    <!-- ===== 选择性查词弹窗 ===== -->
    <el-dialog v-model="selectiveDialogVisible" title="选择性查词" width="min(680px, 90vw)" :close-on-click-modal="false">
      <div class="selective-body">
        <div class="selective-section">
          <div class="sel-title">选择平台</div>
          <el-checkbox-group v-model="selectivePlatforms">
            <el-checkbox v-for="p in platformsArray" :key="p" :value="p">{{ p }}</el-checkbox>
          </el-checkbox-group>
        </div>
        <div class="selective-section">
          <div class="sel-title">选择关键词 <span class="sel-hint">（不选则查全部）</span></div>
          <div class="sel-kw-actions">
            <el-button size="small" text @click="selectiveKeywords = keywords.map(k => k.intentPrompt)">全选</el-button>
            <el-button size="small" text @click="selectiveKeywords = []">清空</el-button>
          </div>
          <div class="sel-kw-list">
            <el-checkbox-group v-model="selectiveKeywords">
              <el-checkbox v-for="kw in keywords" :key="kw.intentPrompt" :value="kw.intentPrompt" class="sel-kw-item">
                <span class="sel-kw-text">{{ kw.intentPrompt }}</span>
                <span v-if="kw.intentCategory" class="sel-kw-cat">{{ kw.intentCategory }}</span>
              </el-checkbox>
            </el-checkbox-group>
          </div>
        </div>
        <div class="selective-summary">
          将查询 <strong>{{ selectiveKeywords.length || keywords.length }}</strong> 个关键词 ×
          <strong>{{ selectivePlatforms.length }}</strong> 个平台 =
          <strong>{{ (selectiveKeywords.length || keywords.length) * selectivePlatforms.length }}</strong> 条
        </div>
      </div>
      <template #footer>
        <el-button @click="selectiveDialogVisible = false">取消</el-button>
        <el-button type="primary" :disabled="!selectivePlatforms.length" @click="doSelectiveSearch">开始查词</el-button>
      </template>
    </el-dialog>

  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  VideoPlay, VideoPause, Search, Delete, ArrowLeft, ArrowDown, ArrowUp,
  ArrowRight, Download, Close, TrendCharts, CircleCheckFilled, CircleCloseFilled,
  WarningFilled, Refresh, ZoomIn,
} from '@element-plus/icons-vue'
import api from '@/api/index.js'
import PlatformIcon from '@/components/PlatformIcon.vue'
import { parseBrands, brandsDisplay } from '@/utils/brands.js'

// ── 平台颜色 ──
const platformColorMap = {
  '豆包':    { bg: '#fff7ed', color: '#ea580c', border: '#fed7aa' },
  'DeepSeek': { bg: '#eff6ff', color: '#2563eb', border: '#bfdbfe' },
  '元宝':    { bg: '#fdf2f8', color: '#db2777', border: '#fbcfe8' },
  '文心一言': { bg: '#f0fdf4', color: '#16a34a', border: '#bbf7d0' },
  '千问':    { bg: '#faf5ff', color: '#9333ea', border: '#e9d5ff' },
  '通义千问': { bg: '#faf5ff', color: '#9333ea', border: '#e9d5ff' },
  'kimi':    { bg: '#f0f9ff', color: '#0284c7', border: '#bae6fd' },
  'Kimi':    { bg: '#f0f9ff', color: '#0284c7', border: '#bae6fd' },
  '纳米':    { bg: '#fefce8', color: '#ca8a04', border: '#fef08a' },
  '纳米 AI': { bg: '#fefce8', color: '#ca8a04', border: '#fef08a' },
}
function platformTagStyle(name) {
  const c = platformColorMap[name]
  if (!c) return {}
  return { background: c.bg, color: c.color, borderColor: c.border }
}
function platformPillActiveStyle(name) {
  const c = platformColorMap[name]
  if (!c) return {}
  return { background: c.color, borderColor: c.color, color: '#fff' }
}

const platformModelMap = {
  '豆包': 'douBao',
  'DeepSeek': 'deepseek',
  '元宝': 'yuanBao',
  '文心一言': 'wenXin',
  '通义千问': 'tongYi',
  'Kimi': 'kimi',
  '纳米': 'naMi',
}

function modelLabel(code) {
  for (const [name, c] of Object.entries(platformModelMap)) { if (c === code) return name }
  return code
}

// ── 执行记录 ──
const execHistory = ref([])
const execHistoryCollapsed = ref(true)
// 执行记录翻页(从近到远;后端已按 search_date DESC 返回)
const execPage = ref(1)
const execPageSize = ref(8)
const expandedExecGroups = ref(new Set())   // 展开的日期分组
const expandedExecTasks = ref(new Set())    // 展开的单次任务（taskId）

function toggleExecGroup(date) {
  const s = new Set(expandedExecGroups.value)
  if (s.has(date)) s.delete(date); else s.add(date)
  expandedExecGroups.value = s
}
function toggleExecTask(taskId) {
  const s = new Set(expandedExecTasks.value)
  if (s.has(taskId)) s.delete(taskId); else s.add(taskId)
  expandedExecTasks.value = s
}

async function deleteSingleTask(group, ex) {
  if (!ex?.taskId) return
  const status = (ex.status || '').toUpperCase()
  if (['RUNNING', 'QUEUED'].includes(status)) {
    ElMessage.warning('运行中的任务不能直接删除，请先停止')
    return
  }
  const dateStr = group?.date || ex.createdAt?.slice(0, 10) || ''
  const timeStr = ex.createdAt?.slice(11, 16) || ''
  try {
    await ElMessageBox.confirm(
      `<p>确认<b style="color:#dc2626">精确删除该次查词任务</b>？</p>
       <p style="color:#64748b;font-size:12px;line-height:1.7;margin-top:8px">
         · 任务时间：<b>${dateStr} ${timeStr}</b><br/>
         · 本次查询：${ex.completedQueries}/${ex.totalQueries}<br/>
         · 同一天的<b>其他任务保留不动</b><br/>
         · 会级联删除：本次的查词结果、关联的排名分析<br/>
         · 此操作<b style="color:#dc2626">不可恢复</b>
       </p>`,
      '删除该次查词任务',
      {
        type: 'warning',
        dangerouslyUseHTMLString: true,
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
      },
    )
  } catch { return }
  try {
    const r = await api.deleteSearchTask(ex.taskId)
    ElMessage.success(`已删除：查词结果 ${r?.results_deleted ?? 0} 条 · 排名任务 ${r?.ranking_tasks_deleted ?? 0} 个`)
    await loadExecHistory?.()
    await loadResults?.()
  } catch (e) {
    ElMessage.error(e?.response?.data?.error || e?.message || '删除失败')
  }
}

// 子任务按 createdAt 升序标注类型，并按 subtask 合计真实执行次数
const groupedExecHistory = computed(() => {
  return (execHistory.value || []).map(g => {
    const sortedTasks = [...(g.tasks || [])].sort((a, b) => (b.createdAt || '').localeCompare(a.createdAt || ''))
    const maxTotal = sortedTasks.reduce((m, t) => Math.max(m, t.totalQueries || 0), 0)
    const tasks = sortedTasks.map((t, idx) => {
      let runType = '初次查询'
      if (idx > 0) runType = (t.totalQueries || 0) < maxTotal ? '补差/重试' : '重新执行'
      return { ...t, runType }
    })
    const execTotal = sortedTasks.reduce((a, t) => a + (t.totalQueries || 0), 0)
    const execDone = sortedTasks.reduce((a, t) => a + (t.completedQueries || 0), 0)
    const target = g.targetQueries || 0
    const success = g.successQueries || 0
    const pending = Math.max(0, (g.pendingQueries != null ? g.pendingQueries : target - success))
    const todayStr = new Date().toISOString().slice(0, 10)
    return {
      ...g,
      tasks,
      successCount: success,
      failCount: g.failQueries || 0,
      execTotal,
      execDone,
      execFail: Math.max(0, execTotal - execDone),
      target,
      success,
      pending,
      isToday: g.date === todayStr,
      modelCount: (g.modelStats || []).length,
    }
  })
})

// 执行记录当前页(从近到远,每页 execPageSize 天)
const pagedExecGroups = computed(() => {
  const all = groupedExecHistory.value || []
  const start = (execPage.value - 1) * execPageSize.value
  return all.slice(start, start + execPageSize.value)
})

const ehModelColorMap = {
  douBao:    { bg: '#fff7ed', color: '#ea580c' },
  deepseek:  { bg: '#eff6ff', color: '#2563eb' },
  yuanbao:   { bg: '#fdf2f8', color: '#db2777' },
  yuanBao:   { bg: '#fdf2f8', color: '#db2777' },
  kimi:      { bg: '#f0f9ff', color: '#0284c7' },
  qianwen:   { bg: '#faf5ff', color: '#9333ea' },
  tongYi:    { bg: '#faf5ff', color: '#9333ea' },
  wenxin:    { bg: '#f0fdf4', color: '#16a34a' },
  wenXin:    { bg: '#f0fdf4', color: '#16a34a' },
  naMi:      { bg: '#fefce8', color: '#ca8a04' },
  zhipu:     { bg: '#fefce8', color: '#ca8a04' },
  tiangong:  { bg: '#fff1f2', color: '#e11d48' },
  xunfei:    { bg: '#f0f9ff', color: '#0284c7' },
  hailuo:    { bg: '#f8fafc', color: '#475569' },
}
const ehModelNameMap = {
  douBao: '豆包', deepseek: 'DeepSeek',
  yuanbao: '元宝', yuanBao: '元宝',
  kimi: 'Kimi',
  qianwen: '通义千问', tongYi: '通义千问',
  wenxin: '文心一言', wenXin: '文心一言',
  naMi: '纳米',
  zhipu: '智谱清言',
  tiangong: '天工', xunfei: '讯飞星火', hailuo: '海螺AI',
}
function ehModelStyle(model) {
  const c = ehModelColorMap[model]
  return c ? { background: c.bg, color: c.color } : { background: '#f5f7fa', color: '#606266' }
}
function ehModelName(model) { return ehModelNameMap[model] || model }
function ehStatusText(s) {
  return { COMPLETED: '成功', RUNNING: '运行中', CANCELLED: '已取消', ERROR: '失败' }[s] || s || '-'
}

async function loadExecHistory() {
  if (!selectedAccountId.value) return
  try {
    execHistory.value = await api.getAccountExecutionHistoryGrouped(selectedAccountId.value, 60)
    execPage.value = 1
    // 默认展开最近一天
    const latestDate = execHistory.value[0]?.date
    if (latestDate) expandedExecGroups.value = new Set([latestDate])
    const latest = execHistory.value[0]
    if (latest && (latest.status === 'ERROR' || latest.errorMessage)) {
      execHistoryCollapsed.value = false
    }
  } catch { execHistory.value = [] }
}

// ── 核心状态 ──
const route = useRoute()
const accounts = ref([])
const selectedAccountId = ref(null)
const currentAccount = ref(null)
const accountId = computed(() => Number(route.params.accountId))
const keywords = ref([])
const results = ref([])
const historyDates = ref([])
const selectedDate = ref('')

const filterPlatform = ref('')
const filterCategory = ref('')
const filterWord = ref('')   // ''=全部 / brand=品牌词 / general=通用词
const searchKeyword = ref('')
const currentPage = ref(1)

// 品牌词 = 提示词含本品牌名(含括号别名拆分);通用词 = 不含。通用词更能体现 GEO 效果。
const brandWordTokens = computed(() => {
  const toks = []
  for (const b of parseBrands(currentAccount.value?.companyBrand)) {
    const s = (b || '').trim()
    if (!s) continue
    toks.push(s)
    for (const p of s.split(/[（(）)]/).map(x => x.trim()).filter(Boolean)) {
      if (p && p !== s) toks.push(p)
    }
  }
  return [...new Set(toks)].filter(t => t.length >= 2)
})
function isBrandWord(r) {
  const text = (r?.intentPrompt || r?.keyword || '')
  if (!text) return false
  return brandWordTokens.value.some(t => text.includes(t))
}
const wordSplit = computed(() => {
  const hasBrand = brandWordTokens.value.length > 0
  const brand = results.value.filter(r => isBrandWord(r)).length
  return { hasBrand, brand, general: results.value.length - brand }
})
const pageSize = ref(20)
const unsearchedCount = ref(0)

// 当所选日期是"今天"且已有查词结果时，"开始查词"按钮含义变为"重新查词"，
// 点击后直接弹出选择性弹框，让用户决定按平台/按关键词重查的范围（覆盖式）
const hasTodayData = computed(() => {
  const today = new Date().toISOString().slice(0, 10)
  return selectedDate.value === today && results.value.length > 0
})
const startBtnLabel = computed(() => hasTodayData.value ? '重新查词' : '开始查词')

const taskRunning = ref(false)
const cancelling = ref(false)
const currentTaskId = ref(null)
const taskProgress = ref({ status: '', total: 0, completed: 0, currentKeyword: '', percentage: 0 })
let progressTimer = null
let startTime = null
const elapsedTime = ref('0s')
const finishedAt = ref('')
let elapsedTimer = null

const progressLog = ref([])
const logListRef = ref(null)
const retrying = ref(false)
const progressCollapsed = ref(false)
const progressDismissed = ref(false)
const logExpanded = ref(false)
const autoScroll = ref(true)
const hasNewLogs = ref(false)

// 确认弹窗
const confirmDialogVisible = ref(false)
// 选择性查词
const selectiveDialogVisible = ref(false)
const selectivePlatforms = ref([])
const selectiveKeywords = ref([])

// 注意：in-flight 行（success===null, inflight=true）既不算成功也不算失败
const logSuccessCount = computed(() => progressLog.value.filter(i => !i.inflight && i.success === true).length)
const logFailCount = computed(() => progressLog.value.filter(i => !i.inflight && i.success === false).length)
const logInflightCount = computed(() => progressLog.value.filter(i => i.inflight).length)
const logStalledCount = computed(() => progressLog.value.filter(i => i.inflight && i.stalled).length)
const latestFailedTaskId = computed(() => {
  const failed = results.value.filter(r => !r.success)
  if (!failed.length) return ''
  let best = failed[0]
  for (const r of failed) { if ((r.id || 0) > (best.id || 0)) best = r }
  return best.taskId || ''
})
const successRate = computed(() => {
  // 成功率分母只含已完成（含成功/失败），不含 in-flight 的"查询中"
  const total = logSuccessCount.value + logFailCount.value
  if (!total) return '0'
  if (logFailCount.value === 0) return '100'
  const pct = logSuccessCount.value / total * 100
  if (pct >= 99.95) return '99.9'
  return pct.toFixed(1)
})
const avgDuration = computed(() => {
  // 平均耗时只看已完成查询，不含 in-flight 的累计已等待时间
  const items = progressLog.value.filter(i => !i.inflight && i.duration > 0)
  if (!items.length) return '--'
  const avg = items.reduce((s, i) => s + i.duration, 0) / items.length
  return avg.toFixed(1) + 's'
})
const doneKeywordSet = computed(() => new Set(progressLog.value.map(i => i.keyword)))
// 重试 / 继续查询会话信息：后端在 startRetry/continue 时返回，前端用来精确显示"待补查"
const retrySession = ref({ active: false, type: '', total: 0, pendingPairs: [] })
// 已完成的 (keyword, model) 集合，用于过滤出仍在补查队列里的
const donePairSet = computed(() => {
  const s = new Set()
  for (const i of progressLog.value) s.add(`${i.keyword}||${i.model}`)
  return s
})
const pendingKeywords = computed(() => {
  if (!taskRunning.value) return []
  // 重试 / 继续模式：以后端返回的 pendingPairs 为准，过滤掉已完成
  if (retrySession.value.active && retrySession.value.pendingPairs.length) {
    return retrySession.value.pendingPairs
      .filter(p => !donePairSet.value.has(`${p.keyword}||${p.model}`))
      .map(p => p.keyword)
  }
  // 全量查词：从账号关键词减去已完成
  return keywords.value
    .map(kw => kw.intentPrompt || kw.coreIntentWord || '')
    .filter(k => k && !doneKeywordSet.value.has(k))
})
const retryRemaining = computed(() => {
  if (!retrySession.value.active) return 0
  return retrySession.value.pendingPairs.filter(p => !donePairSet.value.has(`${p.keyword}||${p.model}`)).length
})

// ── 计算属性 ──
const showProgress = computed(() => !progressDismissed.value && (taskRunning.value || ['COMPLETED','ERROR','CANCELLED'].includes(taskProgress.value.status)))
const progPanelCls = computed(() => ({
  'prog-ok': taskProgress.value.status === 'COMPLETED',
  'prog-err': taskProgress.value.status === 'ERROR',
  'prog-cancel': taskProgress.value.status === 'CANCELLED',
  'pp-collapsed': progressCollapsed.value,
}))
const progressBarStatus = computed(() => {
  if (taskProgress.value.status === 'COMPLETED') return 'success'
  if (taskProgress.value.status === 'ERROR') return 'exception'
  return ''
})
// 显示完成数：取后端 completed_queries 与前端实时日志(success+fail)的较大值。
// 后端 done 现为全局单调计数(searcher 跨平台不重置)，此处取 max 仅作轮询时序的
// 防御(后端写库滞后于日志推送)，并非修复计数 bug。
const displayCompleted = computed(() => {
  const fromLog = logSuccessCount.value + logFailCount.value
  // F4: 重试/续查会话也把 in-flight 计入"已发出"，避免 deepseek 全卡时
  // 进度条永久 0% 与日志里转动的 inflight 行视觉矛盾。
  if (isRetrySession.value) return fromLog + logInflightCount.value
  return Math.max(fromLog + logInflightCount.value, taskProgress.value.completed || 0)
})
// 真实总分母：重试/继续会话用本次会话总数；全量查词用「关键词×平台」固定值，
// 不被后端在重试时把 total 缩成失败子集导致进度条跳到 100%（承接查词口径修正）。
const isRetrySession = computed(() => !!retrySession.value.active)
const fullDenominator = computed(() => {
  if (isRetrySession.value && retrySession.value.total) return retrySession.value.total
  const k = keywords.value.length
  const p = platformsArray.value.length
  if (k > 0 && p > 0) return k * p
  return taskProgress.value.total || 0
})
const progressPercentage = computed(() => {
  const d = fullDenominator.value
  return d === 0 ? 0 : Math.min(100, Math.round(displayCompleted.value / d * 100))
})

// ── 改1 分平台进度 ──
const platformProgress = computed(() => {
  const map = {}
  const retrying = isRetrySession.value && retrySession.value.pendingPairs.length
  if (retrying) {
    // 重试/续查：每平台 total = 本次该平台待补 pair 数（modelLabel 转中文名，与 progressLog.platform 对齐）
    for (const pp of retrySession.value.pendingPairs) {
      const plat = modelLabel(pp.model) || pp.model
      if (!map[plat]) map[plat] = { plat, done: 0, ok: 0, fail: 0, total: 0 }
      map[plat].total++
    }
  } else {
    const perTotal = keywords.value.length || 0
    for (const p of platformsArray.value) map[p] = { plat: p, done: 0, ok: 0, fail: 0, total: perTotal }
  }
  for (const it of progressLog.value) {
    const m = map[it.platform]
    if (!m) continue
    if (it.inflight) continue   // 正在查询中,不计入已完成/失败(否则会把 in-flight 误算成失败)
    m.done++
    if (it.success) m.ok++; else m.fail++
  }
  return Object.values(map).map(m => {
    let state = 'wait'
    if (m.done >= m.total && m.total > 0) state = m.fail > 0 ? 'partial' : 'done'
    else if (m.done > 0) state = 'running'
    else if (taskRunning.value) state = 'running'
    const pct = m.total > 0 ? Math.min(100, Math.round(m.done / m.total * 100)) : 0
    return { ...m, state, pct }
  })
})
// 仍在查/待查的平台（未完成），用于"正在查询"醒目区
const runningPlats = computed(() =>
  platformProgress.value.filter(p => p.done < p.total).map(p => p.plat))

// ── 卡死检测：整体进度长时间无推进 → 区分"慢"和"死" ──
const nowTick = ref(Date.now())
// 始终运行的 1s tick:解决 polling 2s 间隔导致 in-flight duration 视觉跳 +2 的问题。
// 后端返回 startedAt(unix float),前端用 nowTick 实时算 elapsed。每 2s polling
// 仍 snap 到服务器值(防漂)。轻量,只更新一个 ref,不读 DOM。
let _alwaysTickTimer = null
onMounted(() => {
  _alwaysTickTimer = setInterval(() => { nowTick.value = Date.now() }, 1000)
})
onUnmounted(() => {
  if (_alwaysTickTimer) { clearInterval(_alwaysTickTimer); _alwaysTickTimer = null }
})

// in-flight 行实时显示辅助函数(用 nowTick 驱动每秒更新)
function liveSecs(item) {
  if (!item.inflight) return item.duration || 0
  if (item.startedAt && item.startedAt > 0) {
    return Math.max(0, Math.floor(nowTick.value / 1000 - item.startedAt))
  }
  return item.duration || 0
}
function liveStatus(item) {
  if (!item.inflight) return { kind: 'done', label: '' }
  // wait_until > now → 当前正在 busy backoff sleep,不是在 query
  const nowSec = nowTick.value / 1000
  if (item.waitUntil && item.waitUntil > nowSec + 0.5) {
    const left = Math.max(0, Math.ceil(item.waitUntil - nowSec))
    return { kind: 'wait', label: `等待 ${left}s 重试` }
  }
  if (item.stalled) {
    // 重试链上限 8 (retry_attempts=3 + MAX_BUSY_RETRIES=5)
    // attempts >= 8: 重试链彻底用完仍挂着 → 真卡死警告
    // attempts < 8 但 stalled: worker 还在跑,可能上游慢、可能 busy backoff、可能 slot 排队 ——
    // 三者从单条 inflight 行不可区分。统一标"响应慢",避免"排队中"在无队列时误导。
    const MAX_RETRY_CHAIN = 8
    if ((item.attempts || 0) >= MAX_RETRY_CHAIN) {
      return { kind: 'stalled', label: '⚠ 疑似卡死' }
    }
    return { kind: 'queued', label: '响应慢' }
  }
  return { kind: 'querying', label: '查询中' }
}
function fmtSec(s) {
  s = Math.max(0, Math.floor(s))
  return s >= 60 ? `${Math.floor(s/60)}m${s%60}s` : `${s}s`
}

const lastAdvanceAt = ref(Date.now())
const _lastDoneSnap = ref(-1)
watch(displayCompleted, (v) => {
  if (v !== _lastDoneSnap.value) {
    _lastDoneSnap.value = v
    lastAdvanceAt.value = Date.now()
  }
})
const STALL_MS = 45000  // 45s 无任何新结果 → 视为卡顿
// F6: 排除"有 in-flight 在等待"的场景——in-flight 行说明 worker 还在跑，
// 只是上游慢/卡，不算真"卡死"。卡死徽标已在 in-flight 行上单独显示。
const progressStalled = computed(() =>
  taskRunning.value
  && logInflightCount.value === 0
  && (nowTick.value - lastAdvanceAt.value > STALL_MS))
const slowPlatforms = computed(() =>
  platformProgress.value
    .filter(p => p.state === 'running' && p.done < p.total)
    .map(p => p.plat))

// ── 改4 预计剩余时间（线性外推：已耗时/已完成 × 待查）──
function _fmtMs(ms) {
  const s = Math.round(ms / 1000)
  if (s < 60) return s + ' 秒'
  const m = Math.floor(s / 60)
  const r = s % 60
  return r ? `${m} 分 ${r} 秒` : `${m} 分`
}
const etaText = computed(() => {
  if (!taskRunning.value) return ''
  const done = displayCompleted.value
  const remain = Math.max(0, fullDenominator.value - done)
  if (done <= 0 || remain <= 0 || !startTime) return '估算中'
  const per = (Date.now() - startTime) / done
  return '约 ' + _fmtMs(per * remain)
})

// ── 改5 实时日志筛选 ──
const logOnlyFailed = ref(false)
const logPlatFilter = ref('')
const logPlatforms = computed(() =>
  Array.from(new Set(progressLog.value.map(i => i.platform).filter(Boolean))).sort())
const visibleProgressLog = computed(() => {
  let l = progressLog.value
  if (logOnlyFailed.value) l = l.filter(i => !i.success)
  if (logPlatFilter.value) l = l.filter(i => i.platform === logPlatFilter.value)
  return l
})
const platformsArray = computed(() => {
  const p = currentAccount.value?.platforms
  if (!p) return []
  if (Array.isArray(p)) return p
  try { return JSON.parse(p) } catch { return String(p).split(/[,，]/).filter(Boolean) }
})
const stats = computed(() => {
  const total = results.value.length
  const success = results.value.filter(r => r.success).length
  const failed = total - success
  const durations = results.value.filter(r => r.duration > 0).map(r => r.duration)
  const avgDur = durations.length ? (durations.reduce((a, b) => a + b, 0) / durations.length).toFixed(1) + 's' : '--'
  const kwCount = keywords.value.length || 1
  const platCount = platformsArray.value.length || 1
  const coverage = Math.round(success / (kwCount * platCount) * 100) + '%'
  return { total, success, failed, avgDuration: avgDur, coverage }
})
// 所有平台（包含配置的平台 + 结果中实际出现的平台）
const allPlatforms = computed(() => {
  const resultPlats = Array.from(new Set(results.value.map(r => r.platform).filter(Boolean)))
  const configPlats = platformsArray.value || []
  // 合并去重：优先保留配置的顺序
  const merged = [...new Set([...configPlats, ...resultPlats])]
  return merged
})
const allCategories = computed(() => Array.from(new Set(results.value.map(r => r.intentCategory).filter(Boolean))).sort())
// 各平台结果计数（包含所有平台，包括0结果的）
const platformCountMap = computed(() => {
  const m = {}
  // 先初始化所有配置的平台
  for (const p of platformsArray.value) {
    m[p] = 0
  }
  // 再统计实际结果
  results.value.forEach(r => {
    if (r.platform) m[r.platform] = (m[r.platform] || 0) + 1
  })
  return m
})
const indexedResults = computed(() => results.value.map((r, i) => ({ ...r, rowKey: `row-${i}` })))
const filteredResults = computed(() => {
  let list = indexedResults.value
  if (filterPlatform.value) list = list.filter(r => r.platform === filterPlatform.value)
  if (filterWord.value === 'brand') list = list.filter(r => isBrandWord(r))
  else if (filterWord.value === 'general') list = list.filter(r => !isBrandWord(r))
  if (filterCategory.value) list = list.filter(r => r.intentCategory === filterCategory.value)
  if (onlyAccIssues.value) list = list.filter(r => accOf(r)?.status === 'issue')
  if (searchKeyword.value.trim()) {
    const kw = searchKeyword.value.trim().toLowerCase()
    list = list.filter(r => (r.keyword||'').toLowerCase().includes(kw) || (r.intentPrompt||'').toLowerCase().includes(kw))
  }
  return list
})

// ── 信息准确度检查(事实错误/负面表述,答案内高亮) ──
const accMap = ref({})          // {result_id: {status, issues}}
const accRunning = ref(false)
const accProgress = ref({ done: 0, total: 0 })
const onlyAccIssues = ref(false)
let accTimer = null
const accIssueCount = computed(() =>
  Object.values(accMap.value).filter(v => v.status === 'issue').length)
function accOf(row) { return accMap.value[String(row.id)] }
async function loadAccuracy() {
  if (!accountId.value || !selectedDate.value) return
  try {
    const r = await api.accuracyList(accountId.value, selectedDate.value)
    accMap.value = r.items || {}
  } catch { accMap.value = {} }
}
async function pollAccuracy() {
  try {
    const s = await api.accuracyStatus(accountId.value, selectedDate.value)
    accRunning.value = !!s.running
    accProgress.value = { done: s.done || 0, total: s.total || 0 }
    if (!s.running) {
      clearInterval(accTimer); accTimer = null
      await loadAccuracy()
      ElMessage.success(`准确度检查完成:${s.issueCount} 条答案存在问题`)
    }
  } catch { clearInterval(accTimer); accTimer = null; accRunning.value = false }
}
async function runAccuracy() {
  try {
    const r = await api.accuracyRun(accountId.value, selectedDate.value)
    if (r.error) { ElMessage.warning(r.error); return }
    if (!r.total) { ElMessage.info(r.message || '无待检答案'); await loadAccuracy(); return }
    accRunning.value = true
    accProgress.value = { done: 0, total: r.total }
    ElMessage.success(`已开始检查 ${r.total} 条答案`)
    accTimer = setInterval(pollAccuracy, 3000)
  } catch (e) {
    ElMessage.error('启动失败:' + (e.response?.data?.error || e.message))
  }
}
watch(selectedDate, () => { accMap.value = {}; onlyAccIssues.value = false; loadAccuracy() })
function escapeHtml(s) {
  return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}
// 有问题的答案:用纯文本渲染并把问题片段高亮(fact 红 / negative 橙),title 提示原因
function renderAnswerWithIssues(row) {
  const acc = accOf(row)
  const base = row.answerText || ''
  if (!acc || acc.status !== 'issue' || !acc.issues?.length) {
    return highlightBrand(row.answerHtml || base)
  }
  let html = escapeHtml(base)
  acc.issues.forEach(it => {
    const q = escapeHtml(it.quote || '')
    if (!q) return
    const cls = it.type === 'negative' ? 'acc-mark acc-neg' : 'acc-mark acc-fact'
    html = html.split(q).join(`<mark class="${cls}" title="${escapeHtml(it.reason || '')}">${q}</mark>`)
  })
  return html.replace(/\n/g, '<br>')
}

// 重置分页
watch([filterPlatform, filterCategory, filterWord, searchKeyword], () => { currentPage.value = 1 })

// 改6: 查词完成/终止 3 秒后自动收起进度面板为悬浮小结条
watch(() => taskProgress.value.status, (s) => {
  if (['COMPLETED', 'ERROR', 'CANCELLED'].includes(s) && !progressCollapsed.value) {
    setTimeout(() => {
      if (['COMPLETED', 'ERROR', 'CANCELLED'].includes(taskProgress.value.status)) {
        progressCollapsed.value = true
      }
    }, 3000)
  }
})

const pagedResults = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return filteredResults.value.slice(start, start + pageSize.value)
})

// 历史日期带数量
const historyDatesWithCount = computed(() => {
  return historyDates.value.map(d => ({
    date: d,
    label: d
  }))
})

// ── 品牌提及分析 ──
const brandMentionData = computed(() => {
  const brands = parseBrands(currentAccount.value?.companyBrand)
  if (!brands.length || !results.value.length) return { total: 0, mentioned: 0, rate: 0, platforms: [] }

  const brandsLower = brands.map(b => b.toLowerCase())
  const answerHas = (ans) => {
    const s = (ans || '').toLowerCase()
    return brandsLower.some(b => s.includes(b))
  }
  // 统计所有结果（包括失败的），按平台分组
  const platMap = {}
  // 先初始化所有配置的平台
  for (const p of platformsArray.value) {
    platMap[p] = { total: 0, mentioned: 0, failed: 0 }
  }
  // 遍历所有结果（不仅限成功的）
  results.value.forEach(r => {
    if (!r.platform) return
    // 如果平台不在配置中（历史数据可能包含已删除的平台），也初始化
    if (!platMap[r.platform]) platMap[r.platform] = { total: 0, mentioned: 0, failed: 0 }
    if (r.success) {
      platMap[r.platform].total++
      if (answerHas(r.answerText)) platMap[r.platform].mentioned++
    } else {
      platMap[r.platform].failed++
    }
  })
  // 构建平台列表：只显示有数据（成功或失败）的平台
  const platforms = Object.entries(platMap)
    .filter(([, d]) => d.total > 0 || d.failed > 0)
    .map(([name, d]) => ({
      name,
      total: d.total,
      mentioned: d.mentioned,
      failed: d.failed,
      rate: d.total ? Math.round(d.mentioned / d.total * 100) : 0,
      hasData: d.total > 0
    }))
    .sort((a, b) => {
      // 有数据的排前面，然后按提及率排序
      if (a.hasData !== b.hasData) return b.hasData - a.hasData
      return b.rate - a.rate
    })

  // 总统计只计算成功的结果
  const successResults = results.value.filter(r => r.success)
  const total = successResults.length
  const mentioned = successResults.filter(r => answerHas(r.answerText)).length
  const rate = total ? Math.round(mentioned / total * 100) : 0

  return { total, mentioned, rate, platforms }
})

function hasBrandMention(row) {
  const brands = parseBrands(currentAccount.value?.companyBrand)
  if (!brands.length) return false
  const s = (row.answerText || '').toLowerCase()
  return brands.some(b => s.includes(b.toLowerCase()))
}

function highlightBrand(html) {
  const brands = parseBrands(currentAccount.value?.companyBrand)
  if (!brands.length || !html) return html || ''
  const escaped = brands
    .map(b => b.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
    .sort((a, b) => b.length - a.length)  // 长品牌优先匹配
    .join('|')
  const regex = new RegExp(`(${escaped})`, 'gi')
  return html.replace(regex, '<mark class="brand-highlight">$1</mark>')
}

// 未查词tooltip
const unsearchedTooltip = computed(() => {
  const pending = pendingKeywords.value
  if (!pending.length) return `${unsearchedCount.value} 个未查词`
  const shown = pending.slice(0, 5).join('、')
  return pending.length > 5 ? `${shown}...等 ${unsearchedCount.value} 个` : shown
})

// 预计耗时
const estimatedTime = computed(() => {
  const total = keywords.value.length * platformsArray.value.length
  const avgSec = 8
  const minutes = Math.ceil(total * avgSec / 60)
  return minutes <= 1 ? '1 分钟' : `${minutes} 分钟`
})

// ── 方法 ──
async function loadAccounts() { try { accounts.value = await api.getAccounts() || [] } catch { ElMessage.error('加载账号失败') } }
async function handleAccountChange(accountId) {
  if (!accountId) { currentAccount.value = null; keywords.value = []; results.value = []; historyDates.value = []; return }
  filterPlatform.value = ''; filterCategory.value = ''; searchKeyword.value = ''
  try {
    currentAccount.value = accounts.value.find(a => a.id === accountId) || null
    keywords.value = await api.getAccountKeywords(accountId) || []
    await loadHistory()
    if (historyDates.value.length) {
      const qDate = route.query?.date
      if (qDate && historyDates.value.includes(qDate)) selectedDate.value = qDate
      else selectedDate.value = historyDates.value[0]
      await loadResults()
    } else { results.value = []; selectedDate.value = '' }
    await checkUnsearched()
  } catch { ElMessage.error('加载账号信息失败') }
}
async function loadHistory() {
  if (!selectedAccountId.value) return
  try { historyDates.value = await api.getSearchHistory(selectedAccountId.value) || [] } catch { historyDates.value = [] }
}
async function loadResults() {
  if (!selectedAccountId.value) return
  try { results.value = await api.getSearchResults(selectedAccountId.value, selectedDate.value || undefined) || [] } catch { results.value = [] }
}

/* ============ 截图大图 ============ */
const shotDialogVisible = ref(false)
const shotRow = ref(null)
const shotDialogTitle = computed(() => {
  if (!shotRow.value) return '查询截图'
  return `${shotRow.value.platform || ''} · ${shotRow.value.keyword || shotRow.value.intentPrompt || ''}`
})
function openShot(row) {
  if (!row?.screenshotUrl) return
  shotRow.value = row
  shotDialogVisible.value = true
}

async function onSelectedDateChange() {
  if (!taskRunning.value) {
    progressDismissed.value = true
    progressLog.value = []
    taskProgress.value = { status: '', total: 0, completed: 0, currentKeyword: '', percentage: 0 }
    currentTaskId.value = null
    finishedAt.value = ''
  }
  await loadResults()
}

const deletingHistory = ref(false)
async function deleteHistoryByDate() {
  if (!selectedAccountId.value || !selectedDate.value) return
  const date = selectedDate.value
  try {
    await ElMessageBox.confirm(
      `确认删除「${date}」的查词记录？该日期下所有查词结果及关联的排名分析都会被删除，不可恢复。`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', confirmButtonClass: 'el-button--danger' }
    )
  } catch { return }
  deletingHistory.value = true
  try {
    const res = await api.deleteSearchHistory(selectedAccountId.value, date)
    ElMessage.success(`已删除 ${res?.deleted || 0} 条查词记录`)
    selectedDate.value = ''
    results.value = []
    await loadHistory()
    if (historyDates.value.length) {
      selectedDate.value = historyDates.value[0]
      await loadResults()
    }
  } catch (e) {
    ElMessage.error(e?.response?.data?.error || e?.message || '删除失败')
  } finally {
    deletingHistory.value = false
  }
}
function saveRunningTask(taskId, accountId) {
  try { sessionStorage.setItem('geo_running_task', JSON.stringify({ taskId, accountId, startTime: Date.now() })) } catch {}
}
function clearRunningTask() {
  try { sessionStorage.removeItem('geo_running_task') } catch {}
}
function getSavedRunningTask() {
  try { return JSON.parse(sessionStorage.getItem('geo_running_task') || 'null') } catch { return null }
}

function attachTask(taskId, total, accountId, opts = {}) {
  currentTaskId.value = taskId; taskRunning.value = true; cancelling.value = false
  // F5: 不强写 status='RUNNING'——保持空字符串占位，等首次 poll 拿到后端真实
  // 状态后赋值，避免"详情页打开瞬间显示运行中但其实任务早已 COMPLETED"的错位。
  taskProgress.value = {
    status: '',
    total: total || 0,
    completed: opts.completed || 0,
    currentKeyword: '',
    percentage: 0,
  }
  progressLog.value = []; finishedAt.value = ''; startTime = Date.now()
  progressCollapsed.value = false; progressDismissed.value = false
  autoScroll.value = true; hasNewLogs.value = false
  // 重试 / 继续模式：保留 pendingPairs 以便实时显示剩余待查
  if (opts.retryType && Array.isArray(opts.pendingPairs) && opts.pendingPairs.length) {
    retrySession.value = {
      active: true,
      type: opts.retryType,
      total: opts.retryCount || opts.pendingPairs.length,
      pendingPairs: opts.pendingPairs,
    }
  } else {
    retrySession.value = { active: false, type: '', total: 0, pendingPairs: [] }
  }
  startElapsedTimer(); startProgressPolling()
  saveRunningTask(taskId, accountId)
}

function confirmStartSearch() {
  if (!selectedAccountId.value) return
  if (!keywords.value.length) { ElMessage.warning('该账号尚未添加关键词'); return }
  if (hasTodayData.value) {
    // 已查过 → 走选择性弹框（默认全选所有平台/全部关键词，用户可勾减）
    selectivePlatforms.value = [...platformsArray.value]
    selectiveKeywords.value = []
    selectiveDialogVisible.value = true
  } else {
    confirmDialogVisible.value = true
  }
}

async function doStartSearch() {
  confirmDialogVisible.value = false
  try {
    const resp = await api.startSearch(selectedAccountId.value, {
      platforms: platformsArray.value,
    })
    attachTask(resp.taskId, resp.total, selectedAccountId.value)
    ElMessage.success(resp.overwrite ? '已覆盖当天查词任务' : '查词已启动')
  } catch (e) { ElMessage.error('启动失败：' + (e.response?.data?.error || e.message)) }
}

async function doSelectiveSearch() {
  selectiveDialogVisible.value = false
  const body = { platforms: selectivePlatforms.value }
  if (selectiveKeywords.value.length) body.keywords = selectiveKeywords.value
  try {
    const resp = await api.startSearch(selectedAccountId.value, body)
    attachTask(resp.taskId, resp.total, selectedAccountId.value)
    ElMessage.success(resp.overwrite ? '已覆盖当天查词任务' : '已新建查词任务')
  } catch (e) { ElMessage.error('启动失败：' + (e.response?.data?.error || e.message)) }
}

async function cancelSearch() {
  if (!currentTaskId.value) return
  cancelling.value = true
  try { await api.cancelSearch(currentTaskId.value); ElMessage.info('正在停止...') } catch { ElMessage.error('停止失败'); cancelling.value = false }
}

function dismissProgress() {
  progressDismissed.value = true
}

// 日志滚动检测
function onLogScroll() {
  if (!logListRef.value) return
  const el = logListRef.value
  const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 30
  autoScroll.value = atBottom
  if (atBottom) hasNewLogs.value = false
}
function scrollToBottom() {
  if (logListRef.value) {
    logListRef.value.scrollTop = logListRef.value.scrollHeight
    autoScroll.value = true
    hasNewLogs.value = false
  }
}

// 监听logListRef挂载
watch(logListRef, (el) => {
  if (el) el.addEventListener('scroll', onLogScroll)
}, { immediate: true })

function startProgressPolling() {
  stopProgressPolling()
  progressTimer = setInterval(async () => {
    if (!currentTaskId.value) { stopProgressPolling(); return }
    try {
      const prog = await api.getSearchProgress(currentTaskId.value)
      taskProgress.value = prog
      try {
        const log = await api.getSearchProgressLog(currentTaskId.value)
        const prevLen = progressLog.value.length
        progressLog.value = log || []
        if (progressLog.value.length > prevLen) {
          if (autoScroll.value && logListRef.value) {
            nextTick(() => { if (logListRef.value) logListRef.value.scrollTop = logListRef.value.scrollHeight })
          } else {
            hasNewLogs.value = true
          }
        }
      } catch {}
      if (['COMPLETED','CANCELLED','ERROR'].includes(prog.status)) {
        taskRunning.value = false; cancelling.value = false; stopProgressPolling(); stopElapsedTimer()
        retrySession.value = { active: false, type: '', total: 0, pendingPairs: [] }
        clearRunningTask()
        const now = new Date()
        finishedAt.value = `${now.getHours().toString().padStart(2,'0')}:${now.getMinutes().toString().padStart(2,'0')}:${now.getSeconds().toString().padStart(2,'0')} 完成`
        if (prog.status === 'COMPLETED') ElMessage.success('查词完成')
        else if (prog.status === 'ERROR') ElMessage.error('查词出错：' + (prog.errorMessage || ''))
        else ElMessage.info('查词已停止')
        await loadHistory()
        // 仅当用户还没选择日期时才自动选最近日期；若用户正在查看历史某天，保持不变
        if (!selectedDate.value && historyDates.value.length) {
          selectedDate.value = historyDates.value[0]
        }
        await loadResults()
        await checkUnsearched()
      }
    } catch {}
  }, 2000)
}
function stopProgressPolling() { if (progressTimer) { clearInterval(progressTimer); progressTimer = null } }
function startElapsedTimer() {
  stopElapsedTimer()
  elapsedTimer = setInterval(() => {
    nowTick.value = Date.now()   // 驱动卡死检测
    if (!startTime) return
    const sec = Math.floor((Date.now() - startTime) / 1000)
    elapsedTime.value = sec < 60 ? sec + 's' : Math.floor(sec/60) + 'm ' + (sec%60) + 's'
  }, 1000)
}
function stopElapsedTimer() { if (elapsedTimer) { clearInterval(elapsedTimer); elapsedTimer = null } }

function handleExport() {
  if (!selectedAccountId.value || !selectedDate.value) { ElMessage.warning('无可导出的数据'); return }
  window.open(api.exportSearchResults(selectedAccountId.value, selectedDate.value), '_blank')
  ElMessage.success('正在导出压缩包...')
}

function exportLog() {
  if (!progressLog.value.length) return
  const lines = progressLog.value.map((item, i) =>
    `${i+1}\t${item.keyword}\t${item.platform}\t${item.success ? '成功' : '失败'}\t${item.duration ? item.duration.toFixed(1) + 's' : '-'}\t${item.error || ''}`
  )
  const csv = '序号\t关键词\t平台\t状态\t耗时\t错误信息\n' + lines.join('\n')
  const blob = new Blob(['\uFEFF' + csv], { type: 'text/tab-separated-values;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = `查词日志_${new Date().toISOString().slice(0,10)}.tsv`
  a.click(); URL.revokeObjectURL(url)
  ElMessage.success('日志已导出')
}

function truncateText(text, maxLen) { return !text ? '' : text.length > maxLen ? text.substring(0, maxLen) + '...' : text }

async function checkUnsearched() {
  if (!selectedAccountId.value) { unsearchedCount.value = 0; return }
  try {
    const resp = await api.getUnsearchedCount(selectedAccountId.value)
    unsearchedCount.value = resp.count || 0
  } catch { unsearchedCount.value = 0 }
}

async function continueSearch() {
  if (!selectedAccountId.value) return
  try {
    const resp = await api.continueSearch(selectedAccountId.value)
    attachTask(resp.taskId, resp.total, selectedAccountId.value, {
      completed: resp.completed,
      retryType: resp.retryType || 'continue',
      retryCount: resp.retryCount,
      pendingPairs: resp.pendingPairs || [],
    })
    ElMessage.success(`继续查词已启动，待查 ${resp.retryCount || resp.total} 项`)
  } catch (e) { ElMessage.error('继续查词失败：' + (e.response?.data?.error || e.message)) }
}

async function retryFailedSearch() {
  if (!currentTaskId.value) return
  retrying.value = true
  try {
    const resp = await api.retryFailed(currentTaskId.value)
    attachTask(resp.taskId, resp.total, selectedAccountId.value, {
      completed: resp.completed,
      retryType: resp.retryType || 'failed',
      retryCount: resp.retryCount,
      pendingPairs: resp.pendingPairs || [],
    })
    ElMessage.success(`正在重试 ${resp.retryCount || 0} 个失败查询...`)
  } catch (e) {
    ElMessage.error('重试失败：' + (e.response?.data?.error || e.message))
  } finally {
    retrying.value = false
  }
}

async function retryFailedFromResults() {
  const tid = latestFailedTaskId.value
  if (!tid) { ElMessage.warning('未找到失败项对应的任务'); return }
  retrying.value = true
  try {
    const resp = await api.retryFailed(tid)
    attachTask(resp.taskId, resp.total, selectedAccountId.value, {
      completed: resp.completed,
      retryType: resp.retryType || 'failed',
      retryCount: resp.retryCount,
      pendingPairs: resp.pendingPairs || [],
    })
    ElMessage.success(`正在重试 ${resp.retryCount || 0} 个失败查询...`)
  } catch (e) {
    ElMessage.error('重试失败：' + (e.response?.data?.error || e.message))
  } finally {
    retrying.value = false
  }
}

// 带有 ?date= 查询参数表示用户从任务列表进入，想查看历史数据 — 不自动弹出运行中任务面板
function _cameFromHistoryLink() {
  const qDate = route.query?.date
  if (!qDate) return false
  const today = new Date().toISOString().slice(0, 10)
  return qDate !== today
}

onMounted(async () => {
  await loadAccounts()
  if (accountId.value) {
    selectedAccountId.value = accountId.value
    await handleAccountChange(accountId.value)
  }
  loadExecHistory().catch(() => {})
  if (_cameFromHistoryLink()) {
    progressDismissed.value = true
  } else {
    await tryResumeTask()
  }
})

// 路由切换到同一组件的另一个客户时，清理旧状态再加载新客户
watch(accountId, async (newId, oldId) => {
  if (!newId || newId === oldId) return
  stopProgressPolling(); stopElapsedTimer()
  currentTaskId.value = null
  taskRunning.value = false
  cancelling.value = false
  taskProgress.value = { status: '', total: 0, completed: 0, currentKeyword: '', percentage: 0 }
  progressLog.value = []
  retrySession.value = { active: false, type: '', total: 0, pendingPairs: [] }
  finishedAt.value = ''
  progressDismissed.value = _cameFromHistoryLink()
  selectedAccountId.value = newId
  await handleAccountChange(newId)
  loadExecHistory().catch(() => {})
  if (!progressDismissed.value) await tryResumeTask()
})

async function tryResumeTask() {
  // 仅复用与当前账号一致的 session 任务，避免跨客户串扰
  const saved = getSavedRunningTask()
  if (saved && saved.taskId && saved.accountId && saved.accountId === selectedAccountId.value) {
    try {
      const prog = await api.getSearchProgress(saved.taskId)
      if (prog && (prog.status === 'RUNNING' || prog.status === 'PENDING')) {
        currentTaskId.value = saved.taskId; taskRunning.value = true
        taskProgress.value = prog; startTime = saved.startTime || Date.now()
        startElapsedTimer(); startProgressPolling()
        return
      }
    } catch {}
    clearRunningTask()
  }
  if (selectedAccountId.value) {
    try {
      const running = await api.getRunningTask(selectedAccountId.value)
      if (running && running.taskId && (running.status === 'RUNNING' || running.status === 'PENDING')) {
        currentTaskId.value = running.taskId; taskRunning.value = true
        taskProgress.value = running; startTime = Date.now()
        startElapsedTimer(); startProgressPolling()
        saveRunningTask(running.taskId, selectedAccountId.value)
      }
    } catch {}
  }
}
onUnmounted(() => {
  stopProgressPolling(); stopElapsedTimer()
  if (accTimer) { clearInterval(accTimer); accTimer = null }
  if (logListRef.value) logListRef.value.removeEventListener('scroll', onLogScroll)
})
</script>

<style scoped>
/* ===== 页面 ===== */
.search-page { min-height: 400px; }

/* ===== 执行记录面板 ===== */
.exec-history-panel {
  background: #fff; border-radius: 10px; border: 1px solid #e8eef5;
  margin-bottom: 12px; overflow: hidden;
}
.eh-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px 16px; cursor: pointer; user-select: none; transition: background .15s;
}
.eh-header:hover { background: #f8fafc; }
.eh-title { font-size: 14px; font-weight: 600; color: #0f172a; }
.eh-arrow { transition: transform .2s; color: #94a3b8; }
.eh-arrow.rotated { transform: rotate(180deg); }
.eh-body { padding: 0 16px 14px; }
.eh-pagination { display: flex; justify-content: center; padding: 10px 0 2px; }

.eh-item {
  padding: 12px; background: #f8fafc; border-radius: 8px;
  border-left: 3px solid #e2e8f0; margin-bottom: 8px;
}
.eh-item:last-child { margin-bottom: 0; }
.eh-item.eh-latest { border-left-color: #3b82f6; background: #f0f7ff; }

/* ===== 日期分组 ===== */
.eh-group {
  background: #f8fafc; border-radius: 8px;
  border-left: 3px solid #e2e8f0; margin-bottom: 8px; overflow: hidden;
}
.eh-group:last-child { margin-bottom: 0; }
.eh-group.eh-latest { border-left-color: #3b82f6; background: #f0f7ff; }
.eh-group-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 10px 12px; cursor: pointer; user-select: none;
  transition: background .15s;
}
.eh-group-header:hover { background: rgba(0,0,0,.025); }
.eh-group-arrow {
  color: #94a3b8; transition: transform .15s; font-size: 12px;
}
.eh-group-arrow.rotated { transform: rotate(90deg); }
.eh-group-body {
  padding: 8px 12px 12px; border-top: 1px dashed #e2e8f0;
}
.eh-date {
  font-size: 13px; font-weight: 700; color: #0f172a;
  font-variant-numeric: tabular-nums;
}
.eh-task-count {
  font-size: 11px; padding: 1px 8px; border-radius: 10px;
  background: #e0e7ff; color: #4338ca; font-weight: 600;
}
.eh-fail-badge {
  font-size: 11px; padding: 1px 8px; border-radius: 10px;
  background: #fee2e2; color: #b91c1c; font-weight: 600;
}

.eh-subtasks { margin-top: 10px; display: flex; flex-direction: column; gap: 6px; }
.eh-subtask {
  background: #fff; border-radius: 6px; border: 1px solid #e8eef5;
}
.eh-subtask-header {
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
  padding: 8px 10px; cursor: pointer; user-select: none;
}
.eh-subtask-header:hover { background: #f8fafc; }
.eh-subtask-body {
  padding: 8px 10px 10px; border-top: 1px dashed #eef2f7;
}

.eh-item-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; flex-wrap: wrap; gap: 6px; }
.eh-item-left { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.eh-item-right { font-size: 12px; }

.eh-status { padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; }
.ehs-completed { background: #dcfce7; color: #15803d; }
.ehs-running { background: #dbeafe; color: #1d4ed8; }
.ehs-cancelled { background: #f1f5f9; color: #64748b; }
.ehs-error { background: #fee2e2; color: #dc2626; }

.eh-time { font-size: 12px; color: #64748b; font-variant-numeric: tabular-nums; }
.eh-queries { font-size: 12px; color: #475569; font-weight: 600; font-variant-numeric: tabular-nums; }
.eh-queries-ok { color: #16a34a; }
.eh-sep { color: #94a3b8; margin: 0 2px; font-weight: normal; }
.eh-run-type {
  display: inline-block; padding: 1px 8px; border-radius: 3px; font-size: 11px;
  background: #f1f5f9; color: #64748b; margin: 0 4px;
}

.eh-db-ok { color: #15803d; font-size: 12px; }
.eh-db-warn { color: #d97706; font-size: 12px; }

.eh-models { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }
.eh-model-chip {
  display: flex; align-items: center; gap: 6px;
  padding: 4px 10px; border-radius: 6px; font-size: 11px; font-weight: 600;
}
.ehmc-name { font-weight: 700; }
.ehmc-num { font-variant-numeric: tabular-nums; }
.ehmc-fail { color: #dc2626; font-weight: 700; }
.ehmc-ok { color: #16a34a; font-size: 13px; }

.eh-error {
  font-size: 12px; color: #b91c1c; margin-top: 8px;
  padding: 8px 12px; background: #fef2f2; border-radius: 6px;
  border-left: 3px solid #dc2626;
  display: flex; align-items: flex-start; gap: 6px; flex-wrap: wrap;
  line-height: 1.5;
}
.eh-error-icon { color: #dc2626; margin-top: 1px; flex-shrink: 0; }
.eh-error-label { font-weight: 600; color: #991b1b; flex-shrink: 0; }
.eh-error-text { word-break: break-word; flex: 1; min-width: 0; }
.eh-error-pending {
  display: inline-block; margin-left: 6px; padding: 1px 8px;
  background: #fee2e2; color: #991b1b; border-radius: 10px;
  font-size: 11px; font-weight: 600; flex-shrink: 0;
}

/* ===== 顶部操作栏 ===== */
.top-bar {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px 16px; background: #fff; border-radius: 8px;
  border: 1px solid #ebeef5; margin-bottom: 12px; gap: 12px; flex-wrap: wrap;
}
.bar-left { display: flex; align-items: center; gap: 10px; flex: 1; flex-wrap: wrap; }
.bar-right { display: flex; align-items: center; gap: 8px; flex-shrink: 0; flex-wrap: wrap; }
.back-btn { padding: 4px 8px; font-size: 13px; color: #606266; }
.back-btn span { margin-left: 2px; }
.bar-company { font-size: 15px; font-weight: 700; color: #303133; }
.bar-brand { font-size: 13px; color: #606266; background: #f0f2f5; padding: 2px 8px; border-radius: 4px; }
.bar-divider { width: 1px; height: 18px; background: #e4e7ed; }
.bar-meta { font-size: 12px; color: #909399; font-weight: 500; }
.bar-platform {
  font-size: 11px; padding: 2px 8px; border-radius: 10px;
  background: #ecf5ff; color: #409eff; font-weight: 500;
  border: 1px solid transparent;
}
.bar-sched-tag { margin-left: 4px; }

/* ===== 进度面板 ===== */
.prog-panel {
  background: #fff; border-radius: 8px; padding: 16px;
  border: 1px solid #e4e7ed; margin-bottom: 12px;
  border-left: 3px solid #409eff; transition: border-color .3s;
}
.prog-panel.prog-ok { border-left-color: #67c23a; }
.prog-panel.prog-err { border-left-color: #f56c6c; }
.prog-panel.prog-cancel { border-left-color: #909399; }
/* 改6: 折叠态悬浮顶部，滚动时小结常驻 */
.prog-panel.pp-collapsed {
  position: sticky; top: 8px; z-index: 20;
  box-shadow: 0 4px 16px rgba(0,0,0,.10);
  padding: 10px 16px;
}
.prog-panel.pp-collapsed .prog-head { margin-bottom: 0; }

/* 整体进度标签 */
.prog-overall-label {
  display: flex; justify-content: space-between; align-items: baseline;
  font-size: 13px; font-weight: 600; color: #303133; margin: 4px 0 6px;
}
.prog-overall-pct { font-size: 15px; color: #409eff; font-variant-numeric: tabular-nums; }
.prog-panel.prog-ok .prog-overall-pct { color: #67c23a; }
.prog-panel.prog-err .prog-overall-pct { color: #f56c6c; }

/* 卡死检测提示（区分慢 vs 死） */
.prog-now {
  margin: 12px 0 4px; padding: 10px 14px;
  background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px;
}
.prog-now-head { display: flex; align-items: center; gap: 8px; font-size: 13px; flex-wrap: wrap; }
.prog-now-dot {
  width: 7px; height: 7px; border-radius: 50%; background: #3b82f6; flex-shrink: 0;
  animation: pn-pulse 1.2s ease-in-out infinite;
}
@keyframes pn-pulse { 0%,100%{opacity:1} 50%{opacity:.3} }
.prog-now-label { color: #1d4ed8; font-weight: 700; flex-shrink: 0; }
.prog-now-kw { color: #0f172a; font-weight: 600; }
.prog-now-plats { color: #2563eb; font-size: 12px; }
.prog-now-pending { margin-top: 8px; display: flex; flex-wrap: wrap; gap: 5px; align-items: center; }
.prog-now-pending .pn-label { font-size: 12px; color: #64748b; font-weight: 600; margin-right: 2px; }
.prog-now-pending .pn-tag {
  font-size: 11px; color: #475569; background: #fff;
  border: 1px solid #dbeafe; border-radius: 4px; padding: 1px 7px;
}
.prog-now-pending .pn-more { font-size: 11px; color: #94a3b8; }

.prog-stall-hint {
  display: flex; align-items: flex-start; gap: 6px;
  background: #fdf6ec; color: #b88230; border: 1px solid #f5dab1;
  border-radius: 6px; padding: 7px 10px; font-size: 12px;
  line-height: 1.6; margin: 10px 0 2px;
}
.prog-stall-hint .el-icon { margin-top: 2px; flex-shrink: 0; }
.prog-stall-hint b { color: #e6a23c; }

/* 分平台独立 mini 进度条 */
.plat-prog-list { display: flex; flex-direction: column; gap: 7px; margin: 12px 0 4px; }
.plat-prog-item {
  display: flex; align-items: center; gap: 10px; font-size: 12px; color: #606266;
}
.plat-prog-item .ppi-name { width: 64px; font-weight: 600; flex-shrink: 0; text-align: right; }
.plat-prog-item .ppi-bar {
  flex: 1; height: 8px; border-radius: 4px; background: #ebeef5; overflow: hidden;
}
.plat-prog-item .ppi-fill {
  height: 100%; border-radius: 4px; background: #409eff; transition: width .4s ease;
}
.plat-prog-item .ppi-num { width: 56px; text-align: right; font-variant-numeric: tabular-nums; flex-shrink: 0; }
.plat-prog-item .ppi-sep { color: #c0c4cc; margin: 0 1px; }
.plat-prog-item .ppi-fail { color: #f56c6c; font-size: 11px; flex-shrink: 0; }
.plat-prog-item .ppi-ic { width: 14px; text-align: center; font-weight: 700; flex-shrink: 0; }
.plat-prog-item.ppi-done .ppi-fill { background: #67c23a; }
.plat-prog-item.ppi-done .ppi-ic { color: #67c23a; }
.plat-prog-item.ppi-partial .ppi-fill { background: #e6a23c; }
.plat-prog-item.ppi-partial .ppi-ic { color: #e6a23c; }
.plat-prog-item.ppi-running .ppi-fill { background: #409eff; }
.plat-prog-item.ppi-running .ppi-ic { color: #409eff; animation: pp-spin 1.1s linear infinite; display: inline-block; }
@keyframes pp-spin { from { transform: rotate(0); } to { transform: rotate(360deg); } }

.prog-failbadge {
  background: #fef0f0; color: #f56c6c; border: 1px solid #fbc4c4;
  border-radius: 10px; padding: 1px 7px; font-size: 11px; margin-left: 6px;
}
.prog-inflightbadge {
  background: #ecf5ff; color: #409eff; border: 1px solid #b3d8ff;
  border-radius: 10px; padding: 1px 7px; font-size: 11px; margin-left: 6px;
}
.prog-stalledbadge {
  background: #fdf6ec !important; color: #b45309 !important; border-color: #f5dc8c !important;
  font-weight: 600;
}

/* ── in-flight 行（查询中 / 卡死预警）── */
.log-row-inflight { background: #f4f9ff; }
.log-row-stalled { background: #fdf6ec; }
.log-dot-inflight {
  background: #409eff !important;
  box-shadow: 0 0 0 2px rgba(64,158,255,0.18);
  animation: log-dot-pulse 1.4s ease-in-out infinite;
}
.log-dot-stalled {
  background: #d97706 !important;
  box-shadow: 0 0 0 2px rgba(217,119,6,0.22);
  animation: none;
}
@keyframes log-dot-pulse {
  0%,100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.35); opacity: 0.55; }
}
.log-saved-inflight {
  background: #ecf5ff; color: #1d4ed8;
  font-weight: 500;
}
/* 等待重试中(busy backoff):用灰色冷色让用户一眼看出"没在查,在等"  */
.log-saved-waiting {
  background: #f1f5f9 !important; color: #64748b !important;
}
/* 排队中(slot 满,worker 在等 Redis 队列):浅蓝中性色,不是警告 */
.log-saved-queued {
  background: #e0f2fe !important; color: #0369a1 !important;
}
.log-row-stalled .log-saved-inflight {
  background: #fef3c7; color: #b45309;
}
.log-attempts { color: #94a3b8; font-weight: 400; margin-left: 4px; }
.log-lasterr { color: #94a3b8; font-weight: 400; margin-left: 4px; }
.log-dur-stalled { color: #b45309 !important; font-weight: 600; }

.prog-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.prog-head-right { display: flex; align-items: center; }
.prog-title { display: flex; align-items: center; gap: 8px; font-size: 14px; font-weight: 600; color: #303133; }
.prog-meta { display: flex; align-items: center; gap: 14px; }
.prog-nums { font-size: 14px; font-weight: 700; color: #303133; font-variant-numeric: tabular-nums; }
.prog-sep { color: #c0c4cc; margin: 0 1px; font-weight: 400; }
.prog-elapsed { font-size: 12px; color: #909399; font-variant-numeric: tabular-nums; }
.prog-finished { font-size: 12px; color: #67c23a; font-weight: 500; }
.prog-retry-badge {
  font-size: 12px; font-weight: 600; padding: 2px 8px; border-radius: 10px;
  background: #fef3c7; color: #b45309; font-variant-numeric: tabular-nums;
}
.prog-cur-kw { font-size: 12px; color: #909399; font-weight: 400; }

.pulse-dot {
  width: 8px; height: 8px; border-radius: 50%; background: #409eff;
  animation: pulse 1.4s ease-in-out infinite;
  box-shadow: 0 0 0 3px rgba(64,159,255,.15);
}
@keyframes pulse { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:.3;transform:scale(.7)} }

.prog-cards { display: flex; gap: 8px; margin-top: 12px; flex-wrap: wrap; }
.prog-card {
  flex: 1; min-width: 120px; padding: 10px 12px;
  background: #f5f7fa; border-radius: 6px;
}
.pc-label { font-size: 11px; color: #909399; font-weight: 600; margin-bottom: 4px; }
.pc-val {
  font-size: 13px; font-weight: 600; color: #303133;
  display: flex; align-items: center; gap: 6px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.pc-rate { font-size: 18px; font-weight: 700; color: #409eff; }
.pc-empty { color: #c0c4cc; font-weight: 400; }
.pc-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.pc-dot-run { background: #409eff; animation: pulse 1.4s ease-in-out infinite; }
.pc-stats { display: flex; gap: 12px; margin-top: 2px; }
.pc-s-ok { font-size: 13px; font-weight: 600; color: #67c23a; }
.pc-s-fail { font-size: 13px; font-weight: 600; color: #f56c6c; }

.pc-pending { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 4px; }
.pc-pending-tag {
  font-size: 11px; padding: 2px 8px; border-radius: 10px;
  background: #ecf5ff; color: #409eff; font-weight: 500;
  white-space: nowrap; max-width: 140px; overflow: hidden; text-overflow: ellipsis;
}
.pc-pending-more { font-size: 11px; color: #909399; line-height: 22px; }

/* 日志 */
.prog-log { margin-top: 12px; border: 1px solid #ebeef5; border-radius: 6px; overflow: hidden; position: relative; }
.prog-log-head {
  display: flex; justify-content: space-between; align-items: center;
  padding: 7px 12px; background: #f5f7fa; border-bottom: 1px solid #ebeef5;
  font-size: 12px; font-weight: 600; color: #606266;
}
.prog-log-actions { display: flex; align-items: center; gap: 8px; }
.prog-log-cnt { font-weight: 400; color: #909399; }
.prog-log-body { max-height: 200px; overflow-y: auto; transition: max-height .3s; }
.prog-log-body.log-expanded { max-height: 500px; }
.log-row {
  display: flex; align-items: center; gap: 8px;
  padding: 5px 12px; font-size: 12px;
  border-bottom: 1px solid #f5f7fa; transition: background .15s;
}
.log-row:last-child { border-bottom: none; }
.log-row:hover { background: #f5f7fa; }
.log-row-fail { background: #fef0f0; }
.log-no { width: 24px; text-align: right; color: #c0c4cc; font-variant-numeric: tabular-nums; flex-shrink: 0; }
.log-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.log-dot-ok { background: #67c23a; }
.log-dot-err { background: #f56c6c; }
.log-kw { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #303133; font-weight: 500; }
.log-plat {
  flex-shrink: 0; font-size: 11px; padding: 1px 6px;
  background: #f0f2f5; border-radius: 3px; color: #606266;
  border: 1px solid transparent;
}
.log-dur { width: 44px; text-align: right; color: #909399; flex-shrink: 0; font-variant-numeric: tabular-nums; }
.log-saved {
  flex-shrink: 0; font-size: 11px; padding: 1px 6px;
  border-radius: 3px; font-weight: 500;
}
.log-saved-ok { background: #f0f9eb; color: #67c23a; }
.log-saved-no { background: #fef0f0; color: #f56c6c; }

.new-log-tip {
  position: absolute; bottom: 8px; left: 50%; transform: translateX(-50%);
  padding: 4px 14px; background: #409eff; color: #fff; border-radius: 12px;
  font-size: 12px; cursor: pointer; display: flex; align-items: center; gap: 4px;
  box-shadow: 0 2px 8px rgba(64,159,255,.3); z-index: 10;
  animation: fadeIn .3s;
}
@keyframes fadeIn { from { opacity: 0; transform: translateX(-50%) translateY(4px); } to { opacity: 1; transform: translateX(-50%) translateY(0); } }

.prog-actions { margin-top: 12px; display: flex; gap: 8px; }
.prog-err {
  margin-top: 10px; padding: 8px 12px; background: #fef0f0;
  border: 1px solid #fde2e2; border-radius: 6px; color: #f56c6c; font-size: 13px;
}

.slide-down-enter-active, .slide-down-leave-active { transition: opacity .25s, transform .25s; }
.slide-down-enter-from, .slide-down-leave-to { opacity: 0; transform: translateY(-8px); }

/* ===== 品牌提及分析 ===== */
.brand-panel {
  background: #fff; border-radius: 8px; border: 1px solid #ebeef5;
  padding: 16px; margin-bottom: 12px;
}
.brand-head { margin-bottom: 12px; }
.brand-title {
  display: flex; align-items: center;
  font-size: 14px; font-weight: 600; color: #303133; margin-bottom: 6px;
}
.brand-summary { font-size: 13px; color: #606266; line-height: 1.6; }
.brand-platforms { display: flex; flex-direction: column; gap: 8px; }
.bp-item { display: flex; align-items: center; gap: 10px; }
.bp-item.bp-failed { opacity: 0.7; }
.bp-name {
  width: 70px; flex-shrink: 0; font-size: 12px; font-weight: 500;
  padding: 2px 8px; border-radius: 4px; text-align: center;
  border: 1px solid transparent;
}
.bp-bar-wrap {
  flex: 1; height: 18px; background: #f5f7fa; border-radius: 9px; overflow: hidden;
}
.bp-bar {
  height: 100%; border-radius: 9px; transition: width .6s ease;
  min-width: 2px;
}
.bp-rate { width: 100px; font-size: 12px; color: #606266; text-align: right; font-variant-numeric: tabular-nums; }
.bp-failed-text { font-size: 12px; color: #f56c6c; margin-left: auto; }

/* ===== 空状态 ===== */
.empty-state { text-align: center; padding: 80px 24px; background: #fff; border-radius: 8px; border: 1px solid #ebeef5; }
.es-icon { margin-bottom: 16px; }
.es-title { font-size: 16px; font-weight: 600; color: #303133; margin-bottom: 6px; }
.es-desc { font-size: 13px; color: #909399; max-width: 340px; margin: 0 auto; line-height: 1.6; }

/* ===== 关键词预览 ===== */
.kw-preview-card {
  background: #fff; border-radius: 8px; border: 1px solid #ebeef5;
  overflow: hidden;
}
.kpc-head {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px 16px; border-bottom: 1px solid #ebeef5;
}
.kpc-title { font-size: 14px; font-weight: 600; color: #303133; }
.kpc-count { font-size: 12px; color: #909399; background: #f5f7fa; padding: 2px 10px; border-radius: 10px; }
.kpc-cat-tag {
  display: inline-block; padding: 2px 8px; border-radius: 4px;
  background: #fdf6ec; color: #e6a23c; font-size: 12px; font-weight: 500;
}

/* ===== 统计栏 ===== */
.stats-bar {
  display: flex; align-items: center; gap: 16px;
  padding: 14px 20px; background: #fff; border-radius: 8px;
  border: 1px solid #ebeef5; margin-bottom: 12px; flex-wrap: wrap;
}
.sb-item { display: flex; align-items: baseline; gap: 6px; }
.sb-num { font-size: 20px; font-weight: 700; color: #303133; font-variant-numeric: tabular-nums; }
.sb-num-sm { font-size: 15px; }
.sb-label { font-size: 12px; color: #909399; }
.sb-divider { width: 1px; height: 24px; background: #ebeef5; }
.sb-success .sb-num { color: #67c23a; }
.sb-fail .sb-num { color: #e6a23c; }

/* ===== 筛选栏 ===== */
.filter-bar {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 10px; gap: 10px; flex-wrap: wrap;
}
.fb-platforms { display: flex; gap: 4px; flex-wrap: wrap; }
.fb-btn {
  padding: 4px 12px; border: 1px solid #dcdfe6; border-radius: 14px;
  background: #fff; font-size: 12px; color: #606266;
  cursor: pointer; transition: all .18s;
  display: inline-flex; align-items: center; gap: 4px;
}
.fb-btn em {
  font-style: normal; font-size: 11px; background: #f0f2f5;
  border-radius: 8px; padding: 0 5px; color: #909399;
}
.fb-btn:hover { border-color: #409eff; color: #409eff; }
.fb-btn.active { background: #409eff; border-color: #409eff; color: #fff; }
.fb-btn.active em { background: rgba(255,255,255,.2); color: #fff; }
.fb-sep { width: 1px; height: 18px; background: #e2e8f0; margin: 0 4px; align-self: center; }
.fb-group-label { font-size: 11px; color: #94a3b8; align-self: center; margin-right: 2px; }
.fb-btn-word.active { background: #7c3aed; border-color: #7c3aed; }
.fb-controls { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }

/* ===== 结果表格 ===== */
.result-card {
  background: #fff; border-radius: 8px; border: 1px solid #ebeef5; overflow: hidden;
}
.result-table { --el-table-border-color: #f0f2f5; }

.cat-badge {
  display: inline-block; padding: 2px 8px; border-radius: 4px;
  background: #fdf6ec; color: #e6a23c; font-size: 11px; font-weight: 500;
  max-width: 90px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.kw-cell { line-height: 1.4; }
.kw-main {
  font-size: 13px; font-weight: 600; color: #303133;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 300px;
}
.kw-sub {
  font-size: 12px; color: #909399; margin-top: 2px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 300px;
}
.plat-tag {
  display: inline-block; padding: 2px 8px; border-radius: 4px;
  background: #f0f2f5; color: #606266; font-size: 12px; font-weight: 500;
  border: 1px solid transparent;
}
.brand-yes { font-size: 16px; color: #10b981; }
.brand-no { font-size: 12px; color: #c0c4cc; }
.cell-muted { font-size: 12px; color: #c0c4cc; }
.answer-line { font-size: 13px; color: #606266; line-height: 1.5; word-break: break-word; }
.answer-fail { font-size: 12px; color: #f56c6c; display: inline-flex; align-items: center; }
.dur-text { font-size: 12px; color: #909399; font-variant-numeric: tabular-nums; }

/* ===== 截图缩略图 ===== */
.shot-cell {
  position: relative;
  display: inline-block;
  width: 60px; height: 40px;
  border-radius: 5px; overflow: hidden;
  cursor: zoom-in;
  border: 1px solid #e5e7eb;
  background: #f8fafc;
  transition: all 0.15s;
}
.shot-cell:hover {
  border-color: #6366f1;
  box-shadow: 0 4px 10px rgba(99, 102, 241, 0.2);
  transform: scale(1.04);
}
.shot-thumb {
  width: 100%; height: 100%;
  object-fit: cover;
  display: block;
}
.shot-overlay {
  position: absolute; inset: 0;
  display: flex; align-items: center; justify-content: center;
  background: rgba(15, 23, 42, 0.55);
  color: #fff; font-size: 14px;
  opacity: 0; transition: opacity 0.15s;
}
.shot-cell:hover .shot-overlay { opacity: 1; }

/* ===== 大图 dialog ===== */
.shot-dialog :deep(.el-dialog__body) {
  padding: 12px 16px 4px;
}
.shot-dialog-meta {
  display: flex; align-items: center; gap: 12px;
  padding: 8px 12px; margin-bottom: 12px;
  background: #f8fafc; border-radius: 6px;
  font-size: 13px;
}
.shot-meta-kw { color: #0f172a; font-weight: 500; flex: 1;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.shot-dialog-body {
  background: #0f172a; border-radius: 8px;
  display: flex; align-items: flex-start; justify-content: center;
  max-height: 70vh; overflow: auto; padding: 12px;
}
.shot-fullimg {
  max-width: 100%; height: auto; display: block;
  border-radius: 4px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);
}

.row-expand { padding: 14px 24px 14px 44px; background: #f8faff; border-left: 3px solid #409eff; }
.expand-text { font-size: 13px; line-height: 1.8; color: #303133; word-break: break-word; white-space: pre-wrap; }
.expand-text :deep(.brand-highlight) { background: #fef08a; color: #92400e; padding: 1px 4px; border-radius: 3px; font-weight: 600; }
.expand-empty { color: #909399; font-size: 13px; }

.result-footer {
  display: flex; justify-content: space-between; align-items: center;
  padding: 10px 16px; font-size: 12px; color: #909399;
  border-top: 1px solid #f0f2f5; flex-wrap: wrap; gap: 8px;
}

/* ===== 确认弹窗 ===== */
.confirm-body { padding: 4px 0; }
.confirm-row {
  display: flex; align-items: center; padding: 8px 0;
  border-bottom: 1px solid #f5f7fa;
}
.confirm-row:last-of-type { border-bottom: none; }
.confirm-label { width: 80px; flex-shrink: 0; font-size: 13px; color: #909399; }
.confirm-val { font-size: 13px; color: #303133; font-weight: 500; }
.confirm-total { background: #f0f9ff; margin: 8px -4px; padding: 10px 4px; border-radius: 6px; border: none; }
.confirm-total .confirm-val strong { font-size: 15px; color: #409eff; }
.confirm-est { text-align: center; margin-top: 12px; font-size: 12px; color: #909399; }

/* ===== 选择性查词弹窗 ===== */
.selective-body { max-height: 500px; overflow-y: auto; }
.selective-section { margin-bottom: 16px; }
.sel-title { font-size: 13px; font-weight: 600; color: #303133; margin-bottom: 8px; }
.sel-hint { font-size: 12px; color: #909399; font-weight: 400; }
.sel-kw-actions { margin-bottom: 6px; }
.sel-kw-list { max-height: 260px; overflow-y: auto; border: 1px solid #ebeef5; border-radius: 6px; padding: 8px; }
.sel-kw-item { display: flex; align-items: center; width: 100%; margin-bottom: 4px; }
.sel-kw-text { font-size: 13px; }
.sel-kw-cat { font-size: 11px; color: #e6a23c; background: #fdf6ec; padding: 1px 6px; border-radius: 3px; margin-left: 6px; }
.selective-summary {
  padding: 10px 12px; background: #f0f9ff; border-radius: 6px;
  font-size: 13px; color: #409eff; text-align: center;
}
.selective-summary strong { font-weight: 700; }

/* ===== 响应式 ===== */
@media (max-width: 768px) {
  .top-bar { flex-direction: column; align-items: stretch; }
  .bar-right { flex-wrap: wrap; justify-content: flex-start; }
  .bar-left { flex-wrap: wrap; }
  .prog-cards { flex-direction: column; }
  .stats-bar { flex-direction: column; align-items: flex-start; gap: 8px; }
  .sb-divider { display: none; }
  .filter-bar { flex-direction: column; align-items: stretch; }
  .brand-platforms { gap: 6px; }
  .bp-name { width: 60px; font-size: 11px; }
}

/* ===== 信息准确度:答案内问题高亮 + 问题清单 ===== */
:deep(.acc-mark) { padding: 1px 3px; border-radius: 3px; font-weight: 600; cursor: help; }
:deep(.acc-fact) { background: #fee2e2; color: #b91c1c; box-shadow: 0 1px 0 #fca5a5; }
:deep(.acc-neg)  { background: #ffedd5; color: #c2410c; box-shadow: 0 1px 0 #fdba74; }
.acc-issue-list {
  margin-bottom: 12px; padding: 10px 14px; background: #fff7f7;
  border: 1px solid #fecaca; border-radius: 10px;
}
.acc-issue-title { font-size: 12.5px; font-weight: 700; color: #b91c1c; margin-bottom: 8px; }
.acc-issue-row { display: flex; align-items: baseline; gap: 8px; padding: 3px 0; font-size: 12.5px; flex-wrap: wrap; }
.acc-issue-quote { color: #334155; max-width: 480px; }
.acc-issue-reason { color: #94a3b8; }
</style>
