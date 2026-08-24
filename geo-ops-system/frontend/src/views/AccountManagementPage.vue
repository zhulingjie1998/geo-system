<template>
  <div class="account-page">

    <!-- ============ 主面板：工具栏 + 表格 ============ -->
    <section class="panel">
      <!-- 工具栏 -->
      <div class="toolbar">
        <div class="toolbar-tabs">
          <button class="seg active">
            正式客户 <span class="seg-count">{{ filteredAccounts.length }}</span>
          </button>
        </div>
        <div class="toolbar-actions">
          <el-input
            v-model="searchText"
            placeholder="搜索公司或品牌..."
            clearable
            :prefix-icon="SearchIcon"
            class="toolbar-search"
          />
          <el-tooltip content="回收站（30 天内可恢复）" placement="top">
            <el-button plain :icon="Delete" @click="openRecycleBin" />
          </el-tooltip>
          <el-tooltip content="归档客户（到期保留数据）" placement="top">
            <el-button plain @click="openArchiveDialog">
              <el-icon><FolderOpened /></el-icon>
              <span class="archive-btn-text">归档</span>
            </el-button>
          </el-tooltip>
          <el-dropdown trigger="click" @command="handleBulkCommand" :disabled="!selectedRows.length">
            <el-button plain :disabled="!selectedRows.length">
              批量操作 <span v-if="selectedRows.length" class="bulk-cnt">{{ selectedRows.length }}</span>
              <el-icon class="el-icon--right"><ArrowDown /></el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="export"><el-icon><Download /></el-icon>导出选中</el-dropdown-item>
                <el-dropdown-item command="delete" divided>
                  <el-icon style="color:#dc2626"><Delete /></el-icon>
                  <span style="color:#dc2626">删除选中</span>
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          <el-button :icon="Download" plain @click="exportCsv">导出</el-button>
          <el-button type="primary" :icon="Plus" @click="openAddDialog">添加账号</el-button>
          <el-button type="primary" plain :icon="TimerIcon" @click="showScheduledTasks = true">定时任务</el-button>
        </div>
      </div>

      <!-- 定时任务管理面板（右侧滑出） -->
      <ScheduledTasksPanel
        v-model:visible="showScheduledTasks"
        @refresh="loadData"
      />

      <!-- 筛选条：健康度 + 负责人 + 平台 -->
      <div class="filter-bar">
        <div class="fb-segs">
          <button class="fb-seg" :class="{ active: !filterHealth }" @click="filterHealth = ''">
            全部<span class="fb-n">{{ accounts.filter(a => (a.userType || 'paid') !== 'quote').length }}</span>
          </button>
          <button class="fb-seg fb-warn" :class="{ active: filterHealth === 'warn' }" @click="filterHealth = filterHealth === 'warn' ? '' : 'warn'">
            告警<span class="fb-n">{{ warnCount }}</span>
          </button>
          <button class="fb-seg fb-bad" :class="{ active: filterHealth === 'bad' }" @click="filterHealth = filterHealth === 'bad' ? '' : 'bad'">
            异常<span class="fb-n">{{ badCount }}</span>
          </button>
        </div>
        <el-select v-model="filterOwner" clearable filterable placeholder="按负责人筛选" size="small" class="fb-select">
          <el-option v-for="u in adminUserList" :key="u.id" :label="u.username" :value="u.id" />
        </el-select>
        <el-select v-model="filterPlatform" clearable placeholder="按平台筛选" size="small" class="fb-select">
          <el-option v-for="p in allPlatforms" :key="p" :label="p" :value="p" />
        </el-select>
        <span v-if="isFiltering" class="fb-result">{{ filteredAccounts.length }} 个结果</span>
        <el-button v-if="isFiltering" link type="primary" size="small" @click="resetFilters">清除筛选</el-button>
      </div>


      <!-- 表格 -->
      <el-table
        :data="pagedAccounts"
        v-loading="loading"
        row-key="id"
        :class="['account-table', { 'account-table-dense': dense }]"
        :header-cell-style="{ background: 'transparent', color: '#64748b', fontWeight: 600, fontSize: '12px', letterSpacing: '0.3px' }"
        @row-dblclick="(row) => openDetail(row)"
        @selection-change="onSelectionChange"
      >
        <el-table-column type="selection" width="40" />
        <el-table-column label="" width="40" align="center">
          <template #default="{ row }">
            <el-tooltip :content="isPinned(row.id) ? '取消置顶' : '置顶'" placement="top">
              <button class="pin-btn" :class="{ 'pin-on': isPinned(row.id) }" @click.stop="togglePin(row.id)">
                <el-icon :size="14"><StarFilled v-if="isPinned(row.id)" /><Star v-else /></el-icon>
              </button>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column label="客户" min-width="170" sortable :sort-method="(a,b) => (a.companyName||'').localeCompare(b.companyName||'')">
          <template #default="{ row }">
            <div class="customer-cell" @click.stop="openDetail(row)">
              <div class="ca-name-row">
                <span class="ca-type-dot ca-dot-paid"></span>
                <span class="ca-name">{{ row.companyName }}</span>
                <el-icon class="ca-edit-hint"><EditPen /></el-icon>
                <el-tooltip v-if="healthInfo(row).level !== 'good'" :content="healthInfo(row).detail" placement="top">
                  <span class="ca-health" :class="'ca-health-' + healthInfo(row).level"></span>
                </el-tooltip>
                <span v-if="row.isTemp" class="ca-temp" title="外部邀请码生成的临时账号，7 天自动清理">外部</span>
                <el-tooltip v-if="accountSummaryMap.get(row.id)?.running" content="正在查词中" placement="top">
                  <span class="ca-running">
                    <span class="ca-running-pulse"></span>
                    {{ accountSummaryMap.get(row.id)?.runningProgress || 0 }}%
                  </span>
                </el-tooltip>
              </div>
              <div class="ca-meta">
                <span class="ca-meta-item">{{ row.keywordCount || 0 }} 词</span>
                <span class="ca-meta-sep">·</span>
                <span class="ca-meta-item">{{ row.platforms?.length || 0 }} 平台</span>
              </div>
            </div>
          </template>
        </el-table-column>

        <!-- 品牌不在列表展示,移入客户资料(编辑信息/详情);搜索仍可按品牌匹配 -->

        <el-table-column label="覆盖平台" min-width="130">
          <template #default="{ row }">
            <el-popover
              :visible="platformEditId === row.id"
              trigger="manual"
              placement="bottom-start"
              :width="360"
              @hide="onPlatformPopoverHide(row)">
              <template #reference>
                <div class="platforms-cell platforms-cell-clickable"
                     @click.stop="openPlatformEdit(row)"
                     :title="(row.platforms || []).join('、') || '点击编辑覆盖平台'">
                  <template v-if="row.platforms?.length">
                    <PlatformIcon v-for="p in row.platforms" :key="p" :name="p" :size="24" />
                  </template>
                  <span v-else class="muted">点击设置</span>
                  <el-icon class="platform-edit-icon"><EditPen /></el-icon>
                </div>
              </template>
              <div class="platform-edit-popover">
                <PlatformSelector v-model="platformEditDraft" />
                <div class="platform-edit-actions">
                  <el-button size="small" @click="cancelPlatformEdit">取消</el-button>
                  <el-button size="small" type="primary" :loading="platformEditSaving" @click="savePlatformEdit(row)">保存</el-button>
                </div>
              </div>
            </el-popover>
          </template>
        </el-table-column>

        <el-table-column label="业务负责人" width="200" sortable :sort-method="(a,b) => (a.ownerName||'').localeCompare(b.ownerName||'')">
          <template #default="{ row }">
            <el-popover v-if="canTransfer" :visible="ownerEditId === row.id" trigger="manual" placement="bottom-start" :width="340" @hide="onOwnerPopoverHide(row)">
              <template #reference>
                <div class="owner-cell" @click.stop="openOwnerEdit(row)" :title="'点击设置业务负责人(可多选)'">
                  <template v-if="(row.owners || []).length">
                    <span v-for="o in row.owners.slice(0, 2)" :key="o.id" class="owner-tag" :style="ownerTagStyle(o)" :title="`运营人员 ID: ${o.id}`">
                      <span class="owner-avatar" :style="ownerAvatarStyle(o)">{{ (o.username || '?')[0] }}</span>
                      {{ o.username }}
                    </span>
                    <el-popover v-if="row.owners.length > 2" trigger="click" :width="220" placement="top">
                      <template #reference>
                        <span class="owner-more" @click.stop>+{{ row.owners.length - 2 }}</span>
                      </template>
                      <div class="owner-more-list">
                        <span v-for="o in row.owners" :key="o.id" class="owner-tag" :style="ownerTagStyle(o)">
                          <span class="owner-avatar" :style="ownerAvatarStyle(o)">{{ (o.username || '?')[0] }}</span>{{ o.username }}
                        </span>
                      </div>
                    </el-popover>
                  </template>
                  <span v-else class="muted">未指派</span>
                  <el-icon class="owner-edit-icon"><EditPen /></el-icon>
                </div>
              </template>
              <div>
                <div style="font-size:12px;color:#64748b;margin-bottom:6px">设置业务负责人(可多选,均可查看/管理该客户):</div>
                <el-select v-model="ownerEditDraft" multiple collapse-tags collapse-tags-tooltip
                           placeholder="选择运营人员" filterable style="width:100%" size="small">
                  <el-option v-for="u in adminUserList" :key="u.id" :value="u.id" :label="`${u.username} (${u.role || 'operator'})`" />
                </el-select>
                <div style="text-align:right;margin-top:10px;display:flex;gap:6px;justify-content:flex-end">
                  <el-button size="small" @click="cancelOwnerEdit">取消</el-button>
                  <el-button size="small" type="primary" :loading="ownerEditSaving" @click="saveOwnerEdit(row)">保存</el-button>
                </div>
              </div>
            </el-popover>
            <div v-else class="owner-cell">
              <template v-if="(row.owners || []).length">
                <span v-for="o in row.owners.slice(0, 2)" :key="o.id" class="owner-tag" :style="ownerTagStyle(o)">
                  <span class="owner-avatar" :style="ownerAvatarStyle(o)">{{ (o.username || '?')[0] }}</span>
                  {{ o.username }}
                </span>
                <el-popover v-if="row.owners.length > 2" trigger="click" :width="220" placement="top">
                  <template #reference>
                    <span class="owner-more" @click.stop>+{{ row.owners.length - 2 }}</span>
                  </template>
                  <div class="owner-more-list">
                    <span v-for="o in row.owners" :key="o.id" class="owner-tag" :style="ownerTagStyle(o)">
                      <span class="owner-avatar" :style="ownerAvatarStyle(o)">{{ (o.username || '?')[0] }}</span>{{ o.username }}
                    </span>
                  </div>
                </el-popover>
              </template>
              <span v-else class="muted">未指派</span>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="最近排名分析" width="150" sortable :sort-method="(a,b) => (a.lastRankingAt||'').localeCompare(b.lastRankingAt||'')">
          <template #default="{ row }">
            <span v-if="row.lastRankingAt" class="ymd-cell">{{ String(row.lastRankingAt).slice(0, 16) }}</span>
            <span v-else class="muted">未分析</span>
          </template>
        </el-table-column>


        <el-table-column prop="lastSearchDate" label="最后查词" width="160" sortable>
          <template #default="{ row }">
            <div v-if="row.lastSearchDate" class="last-search">
              <span class="ls-date" :class="lastSearchClass(row.lastSearchDate)" :title="row.lastSearchAt || row.lastSearchDate">
                {{ formatLastSearch(row) }}
              </span>
              <span class="ls-rel">{{ daysSinceLabel(row.lastSearchDate) }}</span>
            </div>
            <span v-else class="muted">从未查询</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="470" fixed="right" align="right">
          <template #default="{ row }">
            <button v-if="row.status === 'draft'" class="act-btn act-btn-promote"
                    @click.stop="openPromote(row)" title="补全覆盖平台+关键词,转为正式客户">转为正式</button>
            <button v-if="row.status !== 'draft'" class="act-btn act-btn-primary" @click.stop="goToSearch(row)">查词管理</button>
            <button v-if="row.status !== 'draft'" class="act-btn act-btn-rank"
                    @click.stop="showDeveloping('排名分析')" title="查看/创建该客户排名分析">排名分析</button>
            <button
              v-if="canSeeReports && row.status !== 'draft'"
              class="act-btn act-btn-report"
              @click.stop="showDeveloping('报告管理')"
              title="查看/生成该客户报告"
            >报告管理</button>
            <button v-if="row.status !== 'draft'" class="act-btn act-btn-kb"
                    @click.stop="goKnowledge(row)" title="该客户知识库">知识库</button>
            <!-- 内容库按钮已隐藏 -->
            <!-- <button v-if="row.status !== 'draft'" class="act-btn act-btn-lib"
                    @click.stop="goContentLibrary(row)" title="该客户内容库">内容库</button> -->
            <el-dropdown trigger="click" @command="(cmd) => handleCommand(cmd, row)">
              <button class="act-btn act-btn-more" @click.stop>
                <el-icon :size="14"><MoreFilled /></el-icon>
              </button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="edit"><el-icon><Edit /></el-icon>编辑信息</el-dropdown-item>
                  <el-dropdown-item command="keywords"><el-icon><Key /></el-icon>关键词管理</el-dropdown-item>
                  <el-dropdown-item command="archive" divided style="color:#d97706">
                    <el-icon><FolderOpened /></el-icon>归档客户
                  </el-dropdown-item>
                  <el-dropdown-item command="delete">
                    <el-icon style="color:#dc2626"><Delete /></el-icon>
                    <span style="color:#dc2626">删除账号</span>
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
        </el-table-column>

        <template #empty>
          <div class="table-empty">
            <el-icon :size="40" color="#cbd5e1"><OfficeBuilding /></el-icon>
            <p>{{ isFiltering ? '没有匹配的客户' : '暂无客户账号' }}</p>
            <el-button v-if="!isFiltering" type="primary" size="small" @click="openAddDialog">添加第一个客户</el-button>
            <el-button v-else size="small" @click="resetFilters">清除筛选</el-button>
          </div>
        </template>
      </el-table>

      <!-- 分页 -->
      <div v-if="filteredAccounts.length > pageSize" class="pagination-row">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :total="filteredAccounts.length"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          background
          small
        />
      </div>
    </section>

    <PromoteAccountDialog v-model="promoteVisible" :account="promoteRow" @promoted="onPromoted" />

    <!-- ============ 添加账号弹窗 ============ -->
    <el-dialog v-model="addVisible" class="add-dialog"
               width="min(760px, 92vw)" top="5vh"
               :close-on-click-modal="false"
               @opened="onAddOpened">
      <template #header>
        <div class="ad-banner">
          <div class="ad-banner-ic"><el-icon :size="20"><OfficeBuilding /></el-icon></div>
          <div class="ad-banner-tx">
            <div class="ad-banner-title">添加正式客户</div>
            <div class="ad-banner-sub">录入公司 · 品牌 · 查询关键词</div>
          </div>
        </div>
      </template>
      <div class="ad-steps">
        <div class="ad-step" :class="{ on: addStep === 1, done: addStep > 1 }">
          <span class="ad-step-no">1</span><span>基础信息</span>
        </div>
        <span class="ad-step-line" :class="{ on: addStep > 1 }"></span>
        <div class="ad-step" :class="{ on: addStep === 2 }">
          <span class="ad-step-no">2</span><span>关键词（可空）</span>
        </div>
      </div>
      <el-form v-show="addStep === 1" :model="addForm" label-position="top" class="ad-form">
        <el-form-item label="公司名称" required>
          <el-input ref="addCompanyInput" v-model="addForm.companyName" placeholder="请输入公司名称" />
        </el-form-item>
        <el-form-item label="公司品牌" required>
          <el-select
            v-model="addForm.companyBrands"
            multiple
            filterable
            allow-create
            default-first-option
            :reserve-keyword="false"
            placeholder="输入品牌名后回车添加，支持多个"
            style="width: 100%"
          >
            <el-option v-for="b in brandSuggestions(addForm.companyBrands)" :key="b" :label="b" :value="b" />
          </el-select>
          <div class="field-hint">
            <el-icon :size="12"><InfoFilled /></el-icon>
            可添加多个品牌，回车确认。排名分析时会对每个品牌分别检测，并取最高排名。
          </div>
        </el-form-item>
        <template v-if="addForm.userType === 'paid'">
          <el-form-item label="优化开始时间">
            <div class="date-row">
              <el-input v-model="addForm.optimizeStartDate" placeholder="如 2026-05-18，支持 / - 或空格分隔" style="flex:1"
                        @blur="addForm.optimizeStartDate = normalizeDateInput(addForm.optimizeStartDate)" />
              <el-button type="primary" plain @click="addForm.optimizeStartDate = todayStr()">今日</el-button>
            </div>
          </el-form-item>
          <el-form-item label="覆盖平台">
            <PlatformSelector v-model="addForm.platforms" />
          </el-form-item>
          <el-form-item label="KPI 指标（可多选，选中后填写具体目标，用于后期 KPI 结算）">
            <div class="kpi-box">
              <div v-for="opt in KPI_OPTIONS" :key="opt.key" class="kpi-row">
                <el-checkbox v-model="addForm.kpi[opt.key].on">{{ opt.label }}</el-checkbox>
                <el-input v-if="addForm.kpi[opt.key].on" v-model="addForm.kpi[opt.key].text" size="small"
                          class="kpi-input" placeholder="如：命中率 ≥ 80% / 本月 TOP3 数 ≥ 50" />
              </div>
            </div>
          </el-form-item>
        </template>
      </el-form>

      <div v-show="addStep === 2" class="add-step2">
        <div class="import-hint">
          <span>每行一条，格式：<code>AI提示词｜类型｜搜索意图</code>（半角 <code>|</code> 全角 <code>｜</code> Tab 都支持，类型和搜索意图可省略）</span>
          <el-button link type="primary" size="small" @click="downloadTemplate">下载模板</el-button>
        </div>
        <el-input v-model="keywordBatchText" type="textarea" :autosize="{ minRows: 3, maxRows: 6 }" placeholder="粘贴关键词，每行一条..." />
        <div class="keyword-row-actions">
          <el-button type="primary" size="small" @click="importBatchKeywords">批量导入</el-button>
        </div>
        <div class="kw-table-head">关键词列表（{{ keywordDraftRows.length }} 条）</div>
        <el-table :data="keywordDraftRows" height="200" border size="small">
          <el-table-column type="index" label="#" width="42" />
          <el-table-column prop="intentPrompt" label="AI 提示词" min-width="280" show-overflow-tooltip />
          <el-table-column prop="intentCategory" label="类型" width="100" />
          <el-table-column prop="coreIntentWord" label="搜索意图" width="130" />
          <el-table-column label="" width="50">
            <template #default="{ $index }">
              <el-button link type="danger" size="small" @click="keywordDraftRows.splice($index, 1)">删</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <template #footer>
        <el-button @click="addVisible = false">取消</el-button>
        <el-button v-if="addStep === 2" :icon="ArrowLeft" @click="addStep = 1">上一步</el-button>
        <el-button v-if="addStep === 1" type="primary" @click="onAddNextStep">
          下一步 <el-icon class="el-icon--right"><ArrowRight /></el-icon>
        </el-button>
        <el-button v-if="addStep === 2" type="primary" @click="handleAddSubmit">确认创建</el-button>
      </template>
    </el-dialog>

    <!-- ============ 账号详情弹窗 ============ -->
    <el-dialog v-model="detailVisible" :title="detailAccount?.companyName || '账号详情'" width="min(900px, 90vw)" top="5vh" class="detail-dialog">
      <el-tabs v-model="detailTab">
        <el-tab-pane label="账号信息" name="info">
          <el-form :model="editForm" label-width="100px" style="max-width:640px">
            <div class="form-sec">基础信息</div>
            <el-form-item label="公司名称" required>
              <el-input v-model="editForm.companyName" />
            </el-form-item>
            <el-form-item label="公司品牌" required>
              <el-select
                v-model="editForm.companyBrands"
                multiple
                filterable
                allow-create
                default-first-option
                :reserve-keyword="false"
                placeholder="输入品牌名后回车添加，支持多个"
                style="width: 100%"
              >
                <el-option v-for="b in brandSuggestions(editForm.companyBrands)" :key="b" :label="b" :value="b" />
              </el-select>
              <div class="field-hint">
                <el-icon :size="12"><InfoFilled /></el-icon>
                可添加多个品牌，回车确认。
              </div>
            </el-form-item>
            <el-form-item v-if="editForm.companyBrands.length >= 2" label="品牌报告方式">
              <el-radio-group v-model="editForm.brandReportMode">
                <el-radio-button value="single">同一主体(别名归并)</el-radio-button>
                <el-radio-button value="multi">多品牌矩阵</el-radio-button>
              </el-radio-group>
              <div class="field-hint">
                <el-icon :size="12"><InfoFilled /></el-icon>
                多个品牌名是<b>同一品牌的不同写法</b>(如 Acme/ACME)→选「同一主体」,生成 1 份合并报告;是<b>多个独立品牌</b>(如 品牌A/品牌B/品牌C)→选「多品牌矩阵」。
              </div>
            </el-form-item>
            <el-form-item label="优化开始时间">
              <div class="date-row">
                <el-input v-model="editForm.optimizeStartDate" placeholder="如 2026-05-18，支持 / - 或空格分隔" style="flex:1"
                          @blur="editForm.optimizeStartDate = normalizeDateInput(editForm.optimizeStartDate)" />
                <el-button type="primary" plain @click="editForm.optimizeStartDate = todayStr()">今日</el-button>
              </div>
            </el-form-item>
            <el-form-item label="覆盖平台">
              <PlatformSelector v-model="editForm.platforms" />
            </el-form-item>
            <div class="form-sec">考核指标</div>
            <el-form-item label="KPI 指标">
              <div class="kpi-box">
                <div v-for="opt in KPI_OPTIONS" :key="opt.key" class="kpi-row">
                  <el-checkbox v-model="editForm.kpi[opt.key].on">{{ opt.label }}</el-checkbox>
                  <el-input v-if="editForm.kpi[opt.key].on" v-model="editForm.kpi[opt.key].text" size="small"
                            class="kpi-input" placeholder="如：命中率 ≥ 80% / 本月 TOP3 数 ≥ 50" />
                </div>
                <div class="field-hint" style="margin-top:2px">可多选，选中后填写具体目标，用于后期 KPI 结算。</div>
              </div>
            </el-form-item>
            <div class="form-sec">高级 · 数据共享</div>
            <el-form-item label="数据共享（拆分客户：从其他客户取数据）">
              <div class="kpi-box">
                <el-select v-model="editForm.dataShare.sourceAccountId" clearable filterable
                           placeholder="选择来源客户（不选 = 不共享）" style="width:100%">
                  <el-option v-for="a in shareSourceOptions" :key="a.id" :label="a.companyName" :value="a.id" />
                </el-select>
                <el-checkbox-group v-if="editForm.dataShare.sourceAccountId" v-model="editForm.dataShare.scopes" style="margin-top:8px">
                  <el-checkbox v-for="s in SHARE_SCOPES" :key="s.key" :value="s.key">{{ s.label }}</el-checkbox>
                </el-checkbox-group>
                <div class="field-hint" style="margin-top:2px">
                  本客户报告将从来源客户取所勾选范围的数据（如文章都在老账号发布时，新账号引用追踪从老账号取）。当前「发布内容·AI 引用追踪」已生效，其余范围逐步接入。
                </div>
              </div>
            </el-form-item>
            <el-form-item label="创建时间">
              <span class="muted">{{ detailAccount?.createdAt ? formatYmd(detailAccount.createdAt) : '—' }}</span>
            </el-form-item>
          </el-form>
          <div style="text-align:right;margin-top:12px">
            <el-button type="primary" @click="handleEditSave">保存</el-button>
          </div>
        </el-tab-pane>

        <el-tab-pane name="keywords">
          <template #label>关键词<span v-if="keywordDraftRows.length" class="tab-count">({{ keywordDraftRows.length }})</span></template>
          <div v-loading="detailLoading">
            <div class="import-hint">
              <span>每行一条，格式：<code>AI提示词｜类型｜搜索意图</code>（半角 <code>|</code> 全角 <code>｜</code> Tab 都支持，类型和搜索意图可省略）</span>
              <el-button link type="primary" size="small" @click="downloadTemplate">下载模板</el-button>
            </div>
            <el-input v-model="keywordBatchText" type="textarea" :autosize="{ minRows: 3, maxRows: 6 }" placeholder="粘贴关键词，每行一条..." />
            <div class="keyword-row-actions">
              <el-button type="primary" size="small" @click="importBatchKeywords">批量导入</el-button>
            </div>
            <div class="kw-table-head">关键词列表（{{ keywordDraftRows.length }} 条）</div>
            <el-table :data="keywordDraftRows" height="340" border size="small">
              <el-table-column type="index" label="#" width="42" />
              <el-table-column prop="intentPrompt" label="AI 提示词" min-width="280">
                <template #default="{ row, $index }">
                  <el-input v-if="editingKwIdx === $index" v-model="row.intentPrompt" size="small" />
                  <span v-else :title="row.intentPrompt">{{ row.intentPrompt }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="intentCategory" label="类型" width="110">
                <template #default="{ row, $index }">
                  <el-input v-if="editingKwIdx === $index" v-model="row.intentCategory" size="small" />
                  <span v-else>{{ row.intentCategory || '-' }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="coreIntentWord" label="搜索意图" width="140">
                <template #default="{ row, $index }">
                  <el-input v-if="editingKwIdx === $index" v-model="row.coreIntentWord" size="small" />
                  <span v-else>{{ row.coreIntentWord || '-' }}</span>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="110" fixed="right">
                <template #default="{ $index }">
                  <template v-if="editingKwIdx === $index">
                    <el-button link type="primary" size="small" @click="saveEditKw">确定</el-button>
                    <el-button link size="small" @click="cancelEditKw($index)">取消</el-button>
                  </template>
                  <template v-else>
                    <el-button link type="primary" size="small" @click="startEditKw($index)">编辑</el-button>
                    <el-button link type="danger" size="small" @click="keywordDraftRows.splice($index, 1)">删除</el-button>
                  </template>
                </template>
              </el-table-column>
            </el-table>
            <div class="kw-footer">
              <el-button size="small" @click="clearKeywordDraft">清空</el-button>
              <el-button type="success" plain size="small" @click="handleKeywordAppendSave">追加保存（去重）</el-button>
              <el-button type="primary" size="small" @click="handleKeywordSave">覆盖保存</el-button>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-dialog>

    <!-- 周报抽屉（每个客户独立展示） -->


    <!-- 回收站抽屉 -->
    <el-drawer v-model="recycleBinVisible" title="回收站" size="68%" @open="loadRecycleBin">
      <div class="recycle-hint">
        <el-icon><InfoFilled /></el-icon>
        删除的客户将在此保留 <strong>30 天</strong>，期间可一键恢复。30 天后自动永久删除（含所有关键词、查词记录、报告）。
      </div>
      <el-table :data="deletedAccounts" v-loading="recycleLoading" border size="small" empty-text="回收站为空">
        <el-table-column prop="id" label="#" width="55" />
        <el-table-column label="客户" min-width="180">
          <template #default="{ row }">
            <div>
              <span style="font-weight:600">{{ row.companyName }}</span>
              <span v-if="row.isTemp" class="ca-temp" style="margin-left:6px">外部</span>
            </div>
            <div style="font-size:11px;color:#94a3b8;margin-top:2px">
              {{ parseBrands(row.companyBrand).join('、') || '无品牌' }}
            </div>
          </template>
        </el-table-column>
        <el-table-column label="业务负责人" width="120" prop="businessOwner">
          <template #default="{ row }">{{ row.businessOwner || '—' }}</template>
        </el-table-column>
        <el-table-column label="关键词" width="80" align="center">
          <template #default="{ row }">{{ row.keywordCount || 0 }}</template>
        </el-table-column>
        <el-table-column label="删除时间" width="160">
          <template #default="{ row }">
            <div>{{ formatYmd(row.deletedAt) }}</div>
            <div style="font-size:11px;color:#94a3b8">{{ daysSinceDelete(row.deletedAt) }} 天前 · 还剩 {{ daysUntilPurge(row.deletedAt) }} 天</div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" align="right" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" plain @click="restoreAccount(row)">恢复</el-button>
            <el-button size="small" type="danger" plain @click="purgeAccount(row)">永久删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-drawer>

    <!-- 归档客户弹窗 -->
    <el-dialog v-model="archiveDialogVisible" title="归档客户" width="720px" @open="loadArchivedAccounts">
      <div class="archive-hint">
        <el-icon><InfoFilled /></el-icon>
        归档的客户将<strong>保留所有数据</strong>，但不再显示在客户列表中，也不会执行查词任务。可随时恢复或永久删除。
      </div>
      <el-table :data="archivedAccounts" v-loading="archiveLoading" border size="small" empty-text="暂无归档客户">
        <el-table-column prop="id" label="#" width="55" />
        <el-table-column label="客户" min-width="180">
          <template #default="{ row }">
            <div>
              <span style="font-weight:600">{{ row.companyName }}</span>
            </div>
            <div style="font-size:11px;color:#94a3b8;margin-top:2px">
              {{ parseBrands(row.companyBrand).join('、') || '无品牌' }}
            </div>
          </template>
        </el-table-column>
        <el-table-column label="业务负责人" width="120" prop="businessOwner">
          <template #default="{ row }">{{ row.businessOwner || '—' }}</template>
        </el-table-column>
        <el-table-column label="关键词" width="80" align="center">
          <template #default="{ row }">{{ row.keywordCount || 0 }}</template>
        </el-table-column>
        <el-table-column label="归档时间" width="160">
          <template #default="{ row }">
            <div>{{ formatYmd(row.archivedAt) }}</div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" align="right" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" plain @click="unarchiveAccount(row)">恢复</el-button>
            <el-button size="small" type="danger" plain @click="purgeArchivedAccount(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="archiveDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter, useRoute } from 'vue-router'
import {
  Search as SearchIcon, Plus, Download, Edit, Delete, CopyDocument,
  Promotion, ArrowDown, ArrowRight, ArrowLeft, OfficeBuilding, Money, CircleCheck, Key,
  InfoFilled, MoreFilled, DataAnalysis, Link, Timer as TimerIcon, Timer, Loading, EditPen,
  Refresh, WarningFilled, Star, StarFilled, Upload, DocumentCopy,
  FolderOpened,
} from '@element-plus/icons-vue'
import PlatformSelector from '@/components/common/PlatformSelector.vue'
import PlatformIcon from '@/components/PlatformIcon.vue'
import PromoteAccountDialog from '@/components/common/PromoteAccountDialog.vue'
import ScheduledTasksPanel from '@/components/ScheduledTasksPanel.vue'
import api from '@/api/index.js'
import { parseBrands, brandsToStorage, brandsDisplay } from '@/utils/brands.js'

const router = useRouter()
const route = useRoute()

const userRole = (typeof localStorage !== 'undefined' && localStorage.getItem('geo_role')) || 'operator'
const isSuperAdmin = computed(() => userRole === 'super_admin')
// 三种角色都能看周报（数据由后端 owner_id 隔离）
const canSeeReports = computed(() => ['super_admin', 'admin', 'operator'].includes(userRole))
// 固定紧凑模式（去掉宽松/切换）
const dense = ref(true)
// 表格多选
const selectedRows = ref([])
function onSelectionChange(rows) { selectedRows.value = rows || [] }

const loading = ref(false)
const accounts = ref([])
// 定时任务管理面板
const showScheduledTasks = ref(false)
// 定时任务管理抽屉
const scheduleMgmtVisible = ref(false)
const accountSummaryMap = ref(new Map()) // id -> { running, runningProgress, todayTotal }
const searchText = ref('')
const filterType = ref('')
const filterHealth = ref('')
const filterOwner = ref(null)
const filterPlatform = ref('')
const currentPage = ref(1)
const pageSize = ref(20)
// 业务负责人按【角色】配色:同角色同色(超管/管理员/运营 各一色),不再一人一色
const _ROLE_COLOR = {
  super_admin: { solid: '#e11d48', tint: '#fff1f2', text: '#be123c' }, // 超管 玫红
  admin:       { solid: '#7c3aed', tint: '#f5f3ff', text: '#6d28d9' }, // 管理员 紫
  operator:    { solid: '#0ea5e9', tint: '#eff6ff', text: '#0369a1' }, // 运营 蓝
}
function _ownerColor(o) {
  const role = (o && o.role) || 'operator'
  return _ROLE_COLOR[role] || _ROLE_COLOR.operator
}
function ownerTagStyle(o) {
  const c = _ownerColor(o)
  return { background: c.tint, borderColor: c.solid + '55', color: c.text }
}
function ownerAvatarStyle(o) {
  return { background: _ownerColor(o).solid }
}

// 平台筛选下拉项:从现有客户去重
const allPlatforms = computed(() => {
  const s = new Set()
  for (const a of accounts.value) for (const p of (a.platforms || [])) if (p) s.add(p)
  return [...s]
})

const totalCount = computed(() => accounts.value.length)
// 修正：明确按 'paid' 算（防止 null/undefined 被错算）
const paidCount = computed(() => accounts.value.filter(a => (a.userType || 'paid') === 'paid').length)
const quoteCount = computed(() => accounts.value.filter(a => a.userType === 'quote').length)
const totalKeywords = computed(() => accounts.value.reduce((s, a) => s + (a.keywordCount || 0), 0))
const badCount = computed(() => accounts.value.filter(a => healthInfo(a).level === 'bad').length)
const warnCount = computed(() => accounts.value.filter(a => healthInfo(a).level === 'warn').length)
// 收藏（pin）— localStorage 持久化
const pinnedIds = ref(new Set(JSON.parse(localStorage.getItem('geo_pinned_accounts') || '[]')))
function togglePin(id) {
  if (pinnedIds.value.has(id)) pinnedIds.value.delete(id)
  else pinnedIds.value.add(id)
  pinnedIds.value = new Set(pinnedIds.value)
  localStorage.setItem('geo_pinned_accounts', JSON.stringify([...pinnedIds.value]))
}
const isPinned = (id) => pinnedIds.value.has(id)

const isFiltering = computed(() => !!(searchText.value || filterType.value || filterHealth.value || filterOwner.value || filterPlatform.value))

const filteredAccounts = computed(() => {
  // 报价客户(user_type=quote)归报价管理私有，账号管理只管正式客户
  let list = accounts.value.filter(a => (a.userType || 'paid') !== 'quote')
  if (filterHealth.value) list = list.filter(a => healthInfo(a).level === filterHealth.value)
  if (filterOwner.value) list = list.filter(a => (a.owners || []).some(o => o.id === filterOwner.value))
  if (filterPlatform.value) list = list.filter(a => (a.platforms || []).includes(filterPlatform.value))
  if (searchText.value) {
    const q = searchText.value.toLowerCase()
    list = list.filter(a =>
      (a.companyName || '').toLowerCase().includes(q) ||
      parseBrands(a.companyBrand).some(b => b.toLowerCase().includes(q))
    )
  }
  return list
})

// 排序：pinned 优先，其余按最后查词倒序
const sortedAccounts = computed(() => {
  return [...filteredAccounts.value].sort((a, b) => {
    const pa = pinnedIds.value.has(a.id) ? 0 : 1
    const pb = pinnedIds.value.has(b.id) ? 0 : 1
    if (pa !== pb) return pa - pb
    return (b.lastSearchDate || '').localeCompare(a.lastSearchDate || '')
  })
})

const pagedAccounts = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return sortedAccounts.value.slice(start, start + pageSize.value)
})

// 风险预警：30 天未查词的付费 / 关键词为 0 的付费 / 平台为空的付费
const riskAlerts = computed(() => {
  const list = []
  for (const a of accounts.value) {
    if (a.userType === 'quote') continue
    let reason = ''
    if (!a.platforms || !a.platforms.length) reason = '未配置平台'
    else if (!a.keywordCount) reason = '无关键词'
    else if (a.lastSearchDate) {
      const d = daysSince(a.lastSearchDate)
      if (d > 30) reason = `${d} 天未查词`
    } else reason = '从未查词'
    if (reason) list.push({ ...a, _riskReason: reason })
  }
  return list
})

// 批量操作
async function handleBulkCommand(cmd) {
  if (!selectedRows.value.length) return
  if (cmd === 'export') {
    bulkExport()
  } else if (cmd === 'copy') {
    bulkCopy()
  } else if (cmd === 'delete') {
    bulkDelete()
  }
}

function bulkExport() {
  const headers = ['公司名称', '品牌', '类型', '关键词数', '平台', '最后查词', '健康度']
  const rows = selectedRows.value.map(a => [
    a.companyName || '', parseBrands(a.companyBrand).join(' | '),
    '正式',
    a.keywordCount || 0, (a.platforms || []).join(' | '),
    a.lastSearchDate || '', healthInfo(a).text,
  ])
  const csv = [headers, ...rows].map(r => r.map(c => `"${String(c).replace(/"/g, '""')}"`).join(',')).join('\n')
  const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = `客户列表_选中${selectedRows.value.length}条_${todayStr()}.csv`; a.click()
  URL.revokeObjectURL(url)
  ElMessage.success(`已导出 ${selectedRows.value.length} 条`)
}

function bulkCopy() {
  const lines = selectedRows.value.map(a => `${a.companyName} · ${parseBrands(a.companyBrand).join('、') || '-'}`)
  navigator.clipboard?.writeText(lines.join('\n')).then(() => ElMessage.success('已复制概览'))
}

async function bulkDelete() {
  const n = selectedRows.value.length
  try {
    await ElMessageBox.confirm(
      `确认删除选中的 <b style="color:#dc2626">${n}</b> 个客户？此操作不可恢复，所有关键词、查词记录、报告将一并删除。`,
      '批量删除',
      { type: 'error', dangerouslyUseHTMLString: true, confirmButtonText: '确认删除', cancelButtonText: '取消' }
    )
  } catch { return }
  let ok = 0, fail = 0
  for (const a of selectedRows.value) {
    try { await api.deleteAccount(a.id); ok++ } catch { fail++ }
  }
  await loadAccounts()
  ElMessage[fail ? 'warning' : 'success'](`已删除 ${ok} 个${fail ? `，失败 ${fail} 个` : ''}`)
}

watch([searchText, filterType, filterHealth, filterOwner, filterPlatform], () => { currentPage.value = 1 })
// 翻页时滚顶
watch(currentPage, () => {
  nextTick(() => document.querySelector('.account-table .el-scrollbar__wrap')?.scrollTo({ top: 0, behavior: 'smooth' }))
})

/* ============ 健康度 ============ */
function daysSince(date) {
  if (!date) return Infinity
  const d = new Date(String(date).replace(' ', 'T'))
  if (Number.isNaN(d.getTime())) return Infinity
  return Math.floor((Date.now() - d.getTime()) / 86400000)
}
function daysSinceLabel(date) {
  const d = daysSince(date)
  if (d === 0) return '今天'
  if (d === 1) return '昨天'
  if (d < 30) return `${d} 天前`
  if (d < 365) return `${Math.floor(d / 30)} 月前`
  return `${Math.floor(d / 365)} 年前`
}

function healthInfo(row) {
  const issues = []
  let level = 'good'

  const brands = parseBrands(row.companyBrand)
  if (!brands.length) { issues.push('缺少品牌'); level = 'bad' }

  if (!row.keywordCount) {
    issues.push('无关键词')
    if (level !== 'bad') level = 'warn'
  } else if (row.keywordCount < 5) {
    issues.push(`关键词偏少 (${row.keywordCount})`)
    if (level === 'good') level = 'warn'
  }

  if (row.userType === 'paid') {
    if (!row.platforms || !row.platforms.length) { issues.push('未配置平台'); level = 'bad' }
    if (!row.lastSearchDate) {
      issues.push('从未查词')
      if (level === 'good') level = 'warn'
    } else {
      const days = daysSince(row.lastSearchDate)
      if (days > 30) { issues.push(`${days} 天未查词`); level = 'bad' }
      else if (days > 7) {
        issues.push(`${days} 天未查词`)
        if (level === 'good') level = 'warn'
      }
    }
  }

  const textMap = { good: '健康', warn: '告警', bad: '异常' }
  return {
    level,
    text: textMap[level],
    detail: issues.length ? issues.join('、') : '一切正常',
  }
}

const HEALTH_RANK = { good: 0, warn: 1, bad: 2 }
function sortHealth(a, b) {
  return HEALTH_RANK[healthInfo(a).level] - HEALTH_RANK[healthInfo(b).level]
}

function lastSearchClass(date) {
  const d = daysSince(date)
  if (d > 30) return 'ls-bad'
  if (d > 7) return 'ls-warn'
  return 'ls-good'
}

function formatLastSearch(row) {
  // 优先用 lastSearchAt（含时分）；回退到 lastSearchDate
  const raw = row.lastSearchAt || row.lastSearchDate || ''
  if (!raw) return ''
  const s = String(raw).trim()
  // 形如 2026-04-23 09:15:32 → MM-DD HH:MM
  const m = s.match(/^(\d{4})-(\d{2})-(\d{2})[\sT](\d{2}):(\d{2})/)
  if (m) return `${m[2]}-${m[3]} ${m[4]}:${m[5]}`
  // 只有日期 → MM-DD
  const d = s.match(/^(\d{4})-(\d{2})-(\d{2})/)
  if (d) return `${d[2]}-${d[3]}`
  return s.slice(5)
}

/* ============ 品牌就地编辑 ============ */
const brandEditId = ref(null)
const brandEditDraft = ref([])
const brandEditSaving = ref(false)
const brandEditCancelling = ref(false)   // 主动取消标志，避免 @hide 误判

function openBrandEdit(row) {
  brandEditCancelling.value = false
  brandEditId.value = row.id
  brandEditDraft.value = parseBrands(row.companyBrand)
}
function cancelBrandEdit() {
  brandEditCancelling.value = true
  brandEditId.value = null
  brandEditDraft.value = []
}
async function onBrandPopoverHide(row) {
  // 主动点「取消」触发的隐藏：直接退出，不弹保存确认
  if (brandEditCancelling.value) { brandEditCancelling.value = false; return }
  // 用户编辑后点外部关闭：检测是否有未保存的修改，提示挽救
  if (brandEditSaving.value) return
  const original = parseBrands(row.companyBrand)
  const draft = (brandEditDraft.value || []).map(b => String(b).trim()).filter(Boolean)
  const changed = original.length !== draft.length || original.some((b, i) => b !== draft[i])
  if (!changed) { cancelBrandEdit(); return }
  // 有未保存改动 → 询问
  try {
    await ElMessageBox.confirm(
      `品牌已有未保存的修改，是否保存？`,
      '保存修改',
      { confirmButtonText: '保存', cancelButtonText: '丢弃', type: 'warning' }
    )
    await saveBrandEdit(row)
  } catch {
    cancelBrandEdit()
  }
}
async function saveBrandEdit(row) {
  const brands = (brandEditDraft.value || []).map(b => String(b).trim()).filter(Boolean)
  if (!brands.length) {
    ElMessage.warning('品牌不能为空')
    return
  }
  brandEditSaving.value = true
  try {
    const updated = await api.patchAccount(row.id, { companyBrand: brandsToStorage(brands) })
    // 本地刷新行
    const idx = accounts.value.findIndex(a => a.id === row.id)
    if (idx >= 0) accounts.value[idx] = { ...accounts.value[idx], ...updated }
    ElMessage.success('品牌已更新')
    cancelBrandEdit()
  } catch (e) {
    ElMessage.error('更新失败：' + (e?.message || '未知错误'))
  } finally {
    brandEditSaving.value = false
  }
}

/* ============ 覆盖平台就地编辑 ============ */
const platformEditId = ref(null)
const platformEditDraft = ref([])
const platformEditSaving = ref(false)
const platformEditCancelling = ref(false)   // 用户主动取消标志，避免 @hide 误判为"改动未保存"

function openPlatformEdit(row) {
  platformEditCancelling.value = false
  platformEditId.value = row.id
  platformEditDraft.value = [...(row.platforms || [])]
}
function cancelPlatformEdit() {
  platformEditCancelling.value = true
  platformEditId.value = null
  platformEditDraft.value = []
}
async function onPlatformPopoverHide(row) {
  // 主动点「取消」触发的隐藏：直接退出，不弹保存确认
  if (platformEditCancelling.value) { platformEditCancelling.value = false; return }
  if (platformEditSaving.value) return
  const original = (row.platforms || [])
  const draft = (platformEditDraft.value || []).map(p => String(p).trim()).filter(Boolean)
  const changed = original.length !== draft.length || original.some((p, i) => p !== draft[i])
  if (!changed) { cancelPlatformEdit(); return }
  try {
    await ElMessageBox.confirm(
      `覆盖平台已有未保存的修改，是否保存？`,
      '保存修改',
      { confirmButtonText: '保存', cancelButtonText: '丢弃', type: 'warning' }
    )
    await savePlatformEdit(row)
  } catch {
    cancelPlatformEdit()
  }
}
async function savePlatformEdit(row) {
  const platforms = (platformEditDraft.value || []).map(p => String(p).trim()).filter(Boolean)
  platformEditSaving.value = true
  try {
    const updated = await api.patchAccount(row.id, { platforms })
    const idx = accounts.value.findIndex(a => a.id === row.id)
    if (idx >= 0) accounts.value[idx] = { ...accounts.value[idx], ...updated }
    ElMessage.success('覆盖平台已更新')
    cancelPlatformEdit()
  } catch (e) {
    ElMessage.error('更新失败：' + (e?.message || '未知错误'))
  } finally {
    platformEditSaving.value = false
  }
}

/* ============ 业务负责人 = 运营 owner（仅 admin/super 可改派）============ */
const canTransfer = computed(() => ['super_admin', 'admin'].includes(userRole))
const adminUserList = ref([])
async function loadAdminUsers() {
  if (!canTransfer.value) return
  try { adminUserList.value = await api.listAdminUsers() || [] }
  catch { adminUserList.value = [] }
}

const ownerEditId = ref(null)
const ownerEditDraft = ref([])  // 多负责人:user_id 数组
const ownerEditSaving = ref(false)
function openOwnerEdit(row) {
  if (!canTransfer.value) return
  ownerEditId.value = row.id
  ownerEditDraft.value = (row.owners || []).map(o => o.id)
  // 懒加载 admin user list
  if (!adminUserList.value.length) loadAdminUsers()
}
function cancelOwnerEdit() {
  ownerEditId.value = null
  ownerEditDraft.value = []
}
function onOwnerPopoverHide(row) {
  // 关闭就直接取消,不静默保存
  if (!ownerEditSaving.value) cancelOwnerEdit()
}
async function saveOwnerEdit(row) {
  const draft = Array.isArray(ownerEditDraft.value) ? [...ownerEditDraft.value] : []
  const current = (row.owners || []).map(o => o.id)
  const same = draft.length === current.length && draft.every(id => current.includes(id))
  if (same) { cancelOwnerEdit(); return }
  const names = adminUserList.value.filter(u => draft.includes(u.id)).map(u => u.username)
  const desc = names.length
    ? `负责人设为 <b style="color:#6366f1">${names.join('、')}</b>`
    : '清空业务负责人'
  try {
    await ElMessageBox.confirm(
      `<p>确认将客户「${row.companyName}」的${desc}？</p><p style="color:#64748b;font-size:12px">所选运营人员都能看到/管理此客户;未选中的将看不到。</p>`,
      '设置业务负责人',
      { type: 'warning', dangerouslyUseHTMLString: true, confirmButtonText: '确认保存', cancelButtonText: '取消' }
    )
  } catch { return }
  ownerEditSaving.value = true
  try {
    await api.setAccountOwners(row.id, draft)
    ElMessage.success(names.length ? `已设置负责人:${names.join('、')}` : '已清空负责人')
    cancelOwnerEdit()
    await loadAccounts()
  } catch (e) {
    ElMessage.error('保存失败：' + (e?.message || ''))
  } finally {
    ownerEditSaving.value = false
  }
}

/* ============ 日期格式化 ============ */
function formatYmd(s) {
  if (!s) return ''
  const m = String(s).match(/^(\d{4})-(\d{2})-(\d{2})/)
  return m ? `${m[1].slice(2)}-${m[2]}-${m[3]}` : String(s).slice(0, 10)
}

/* ============ 客户类型就地切换 ============ */
async function onTypeChange(row, next) {
  const current = row.userType || 'paid'
  if (next === current) return
  const nextLabel = next === 'quote' ? '报价用户' : '正式用户'

  // ── 切到 paid 时，校验是否有 platforms + optimizeStartDate；缺失则引导补齐
  if (next === 'paid') {
    const missing = []
    if (!row.platforms || !row.platforms.length) missing.push('覆盖平台')
    if (!row.optimizeStartDate) missing.push('优化开始时间')
    if (missing.length) {
      ElMessage.warning(`切换为正式用户前，请先补齐：${missing.join('、')}。已为你打开详情页`)
      detailAccount.value = row
      openUpgrade()
      return
    }
  }

  try {
    await ElMessageBox.confirm(
      `确认将「${row.companyName}」切换为「${nextLabel}」？`,
      '切换客户类型',
      { confirmButtonText: '确认', cancelButtonText: '取消', type: 'warning' },
    )
  } catch { return }
  try {
    const updated = await api.patchAccount(row.id, { userType: next })
    const idx = accounts.value.findIndex(a => a.id === row.id)
    if (idx >= 0) accounts.value[idx] = { ...accounts.value[idx], ...updated }
    ElMessage.success('已切换为 ' + nextLabel)
  } catch (e) {
    ElMessage.error('切换失败：' + (e?.message || '未知错误'))
  }
}

/* ============ 品牌建议 ============ */
const allBrands = computed(() => {
  const set = new Set()
  for (const a of accounts.value) parseBrands(a.companyBrand).forEach(b => set.add(b))
  return [...set]
})
function brandSuggestions(current = []) {
  const merged = new Set([...allBrands.value, ...(current || [])])
  return [...merged]
}

/* ============ 初始客户转正 ============ */
const promoteVisible = ref(false)
const promoteRow = ref(null)
function openPromote(row) {
  promoteRow.value = row
  promoteVisible.value = true
}
function onPromoted() {
  loadAccounts()
}

/* ============ 添加弹窗（两步表单）============ */
const addVisible = ref(false)
const addStep = ref(1)   // 1=基础信息  2=关键词
const addForm = ref(defaultAddForm())
const keywordBatchText = ref('')
const keywordDraftRows = ref([])
const addCompanyInput = ref(null)

function onAddNextStep() {
  if (!addForm.value.companyName?.trim()) {
    ElMessage.warning('请填写公司名称')
    return
  }
  if (!(addForm.value.companyBrands || []).length) {
    ElMessage.warning('请至少添加一个公司品牌')
    return
  }
  addStep.value = 2
}

// KPI 三选项(支持多选,选中后填纯文本目标,用于后期 KPI 结算)
const KPI_OPTIONS = [
  { key: 'hit',   label: '命中数 / 命中率' },
  { key: 'top3',  label: 'TOP3 数 / TOP3 率' },
  { key: 'first', label: '首位数 / 首位率' },
]
function emptyKpi() {
  return { hit: { on: false, text: '' }, top3: { on: false, text: '' }, first: { on: false, text: '' } }
}
function kpiFromStored(arr) {
  const k = emptyKpi()
  ;(arr || []).forEach(it => { if (it && k[it.type]) { k[it.type].on = true; k[it.type].text = it.text || '' } })
  return k
}

function defaultAddForm() {
  return { userType: 'paid', companyName: '', businessOwner: '', companyBrands: [], optimizeStartDate: '', platforms: [], kpi: emptyKpi() }
}

function openAddDialog() {
  addForm.value = defaultAddForm()
  keywordDraftRows.value = []
  keywordBatchText.value = ''
  addStep.value = 1   // 每次打开都从 step1 开始
  addVisible.value = true
}
function onAddOpened() {
  nextTick(() => { addCompanyInput.value?.focus?.() })
}

async function handleAddSubmit() {
  if (!addForm.value.companyName || !addForm.value.companyBrands?.length) {
    ElMessage.warning('请填写公司名称和品牌'); addStep.value = 1; return
  }
  // 关键词允许 0 条（统一两步流程，运营可后补）
  try {
    const created = await api.createAccount({
      ...addForm.value,
      companyBrand: brandsToStorage(addForm.value.companyBrands),
    })
    if (keywordDraftRows.value.length && created?.id) {
      try { await api.updateAccountKeywords(created.id, keywordDraftRows.value) }
      catch { ElMessage.warning('账号已创建，但关键词保存失败，请补录') }
    }
    addVisible.value = false
    await loadAccounts()

    // 已经配置了关键词 → 直接成功提示，不再追问
    // 没配置 + 是正式客户 → 引导去配置
    const hasKeywords = keywordDraftRows.value.length > 0
    if (addForm.value.userType === 'paid' && created?.id && !hasKeywords) {
      try {
        await ElMessageBox.confirm('账号添加成功，是否立即配置关键词？', '提示', {
          confirmButtonText: '去配置', cancelButtonText: '稍后再说', type: 'success',
        })
        const acc = accounts.value.find(a => a.id === created.id)
        if (acc) openDetail(acc, 'keywords')
      } catch { /* 稍后 */ }
    } else {
      ElMessage.success(hasKeywords ? `账号添加成功，已配置 ${keywordDraftRows.value.length} 条关键词` : '账号添加成功')
    }
  } catch { ElMessage.error('添加账号失败') }
}

/* ============ 详情弹窗 ============ */
const detailVisible = ref(false)
const detailLoading = ref(false)
const detailTab = ref('info')
const detailAccount = ref(null)
const SHARE_SCOPES = [
  { key: 'publish_cite', label: '发布内容·AI引用追踪' },
  { key: 'kb', label: '知识库' },
  { key: 'search_rank', label: '查词/排名' },
  { key: 'publish_spend', label: '发布花销/订单' },
]
const editForm = ref({ companyName: '', businessOwner: '', companyBrands: [], optimizeStartDate: '', platforms: [], kpi: emptyKpi(), brandReportMode: 'single', dataShare: { sourceAccountId: null, scopes: [] } })
const shareSourceOptions = computed(() => (accounts.value || []).filter(a => a.id !== detailAccount.value?.id))
const editingKwIdx = ref(-1)
const editingKwBackup = ref(null)

async function openDetail(account, tab) {
  detailAccount.value = account
  detailTab.value = tab || 'info'
  editForm.value = {
    companyName: account.companyName || '',
    businessOwner: account.businessOwner || '',
    companyBrands: parseBrands(account.companyBrand),
    optimizeStartDate: account.optimizeStartDate || '',
    platforms: Array.isArray(account.platforms) ? [...account.platforms] : [],
    kpi: kpiFromStored(account.kpi),
    brandReportMode: account.brandReportMode === 'multi' ? 'multi' : 'single',
    dataShare: {
      sourceAccountId: account.dataShare?.sourceAccountId || null,
      scopes: Array.isArray(account.dataShare?.scopes) ? [...account.dataShare.scopes] : [],
    },
  }
  editingKwIdx.value = -1
  keywordBatchText.value = ''
  detailLoading.value = true
  detailVisible.value = true
  try {
    const kws = await api.getAccountKeywords(account.id)
    keywordDraftRows.value = (kws || []).map(item => ({
      intentPrompt: item.intentPrompt || '',
      intentCategory: item.intentCategory || '',
      coreIntentWord: item.coreIntentWord || '',
    }))
  } catch { keywordDraftRows.value = [] }
  finally { detailLoading.value = false }
}

async function handleEditSave() {
  if (!detailAccount.value) return
  if (!editForm.value.companyName || !editForm.value.companyBrands?.length) {
    ElMessage.warning('公司名称和品牌不能为空'); return
  }
  try {
    await api.updateAccount(detailAccount.value.id, {
      ...detailAccount.value,
      companyName: editForm.value.companyName,
      businessOwner: editForm.value.businessOwner,
      companyBrand: brandsToStorage(editForm.value.companyBrands),
      optimizeStartDate: editForm.value.optimizeStartDate,
      platforms: editForm.value.platforms,
      kpi: editForm.value.kpi,
      brandReportMode: editForm.value.companyBrands.length >= 2 ? editForm.value.brandReportMode : 'single',
      dataShare: (editForm.value.dataShare.sourceAccountId && editForm.value.dataShare.scopes.length)
        ? { sourceAccountId: editForm.value.dataShare.sourceAccountId, scopes: editForm.value.dataShare.scopes }
        : null,
    })
    detailVisible.value = false
    await loadAccounts()
    ElMessage.success('账号信息已保存')
  } catch { ElMessage.error('保存失败') }
}

/* ============ 转付费 ============ */
const upgradeVisible = ref(false)
const upgradeForm = ref({ optimizeStartDate: '', platforms: [] })

function openUpgrade() {
  upgradeForm.value = {
    optimizeStartDate: todayStr(),
    platforms: Array.isArray(detailAccount.value?.platforms) ? [...detailAccount.value.platforms] : [],
  }
  upgradeVisible.value = true
}

async function handleUpgradeSubmit() {
  if (!detailAccount.value) return
  if (!upgradeForm.value.optimizeStartDate || !upgradeForm.value.platforms.length) {
    ElMessage.warning('请选择优化开始时间和覆盖平台'); return
  }
  try {
    await api.updateAccount(detailAccount.value.id, {
      ...detailAccount.value,
      userType: 'paid',
      optimizeStartDate: upgradeForm.value.optimizeStartDate,
      platforms: upgradeForm.value.platforms,
    })
    upgradeVisible.value = false
    detailVisible.value = false
    await loadAccounts()
    ElMessage.success('已转为正式用户')
  } catch { ElMessage.error('转换失败') }
}

/* ============ 关键词 ============ */
function importBatchKeywords() {
  const lines = String(keywordBatchText.value || '').split(/\n+/).map(l => l.trim()).filter(Boolean)
  if (!lines.length) { ElMessage.warning('请先输入关键词内容'); return }
  const existing = new Set(keywordDraftRows.value.map(k => k.intentPrompt.trim()))
  let success = 0, failed = 0, duped = 0
  for (const line of lines) {
    // 兼容半角 | 全角 ｜ 制表符 \t（Excel 复制场景）
    const parts = line.split(/[|｜\t]/)
    const prompt = (parts[0] || '').trim()
    if (!prompt) { failed++; continue }
    if (existing.has(prompt)) { duped++; continue }
    keywordDraftRows.value.push({
      intentPrompt: prompt,
      intentCategory: (parts[1] || '').trim(),
      coreIntentWord: (parts[2] || '').trim(),
    })
    existing.add(prompt)
    success++
  }
  keywordBatchText.value = ''
  let msg = `导入成功 ${success} 条`
  if (duped) msg += `，跳过重复 ${duped} 条`
  if (failed) msg += `，格式错误 ${failed} 条`
  ElMessage.success(msg)
}

function startEditKw(idx) {
  editingKwIdx.value = idx
  editingKwBackup.value = { ...keywordDraftRows.value[idx] }
}
function saveEditKw() {
  const row = keywordDraftRows.value[editingKwIdx.value]
  if (!row?.intentPrompt?.trim()) { ElMessage.warning('AI 提示词不能为空'); return }
  editingKwIdx.value = -1
  editingKwBackup.value = null
}
function cancelEditKw(idx) {
  if (editingKwBackup.value) keywordDraftRows.value[idx] = { ...editingKwBackup.value }
  editingKwIdx.value = -1
  editingKwBackup.value = null
}

async function clearKeywordDraft() {
  if (!keywordDraftRows.value.length) return
  try {
    await ElMessageBox.confirm(`确定清空全部 ${keywordDraftRows.value.length} 条关键词？`, '提示', { type: 'warning' })
    keywordDraftRows.value = []
  } catch { /* cancelled */ }
}

async function handleKeywordSave() {
  if (!detailAccount.value) return
  const targetName = detailAccount.value.companyName || `#${detailAccount.value.id}`
  const n = keywordDraftRows.value.length
  const msg = n
    ? `即将把 <b style="color:#2563eb">${n}</b> 条关键词<b>覆盖</b>保存到客户 <b style="color:#dc2626">「${targetName}」</b>。<br/><span style="color:#64748b;font-size:12px">保存会替换该客户原有全部关键词。如需追加，请使用「追加保存」</span>`
    : `即将清空客户 <b style="color:#dc2626">「${targetName}」</b> 的全部关键词（列表为空），确定继续？`
  try {
    await ElMessageBox.confirm(msg, '覆盖保存', { type: 'warning', dangerouslyUseHTMLString: true, confirmButtonText: '确认覆盖', cancelButtonText: '取消' })
  } catch { return }
  try {
    await api.updateAccountKeywords(detailAccount.value.id, keywordDraftRows.value)
    await loadAccounts()
    ElMessage.success('关键词已保存')
  } catch { ElMessage.error('保存失败') }
}

async function handleKeywordAppendSave() {
  if (!detailAccount.value) return
  if (!keywordDraftRows.value.length) {
    ElMessage.warning('当前列表为空，无法追加')
    return
  }
  // 拉取已有关键词，合并去重，再保存
  try {
    const existing = await api.getAccountKeywords(detailAccount.value.id) || []
    const seen = new Set(existing.map(k => (k.intentPrompt || '').trim()))
    const toAdd = keywordDraftRows.value.filter(k => k.intentPrompt && !seen.has(k.intentPrompt.trim()))
    const merged = [...existing, ...toAdd]
    if (!toAdd.length) {
      ElMessage.warning(`列表中 ${keywordDraftRows.value.length} 条全部已存在，无需追加`)
      return
    }
    await ElMessageBox.confirm(
      `将向「${detailAccount.value.companyName}」追加 <b style="color:#10b981">${toAdd.length}</b> 条新关键词（已自动去重）。`,
      '追加保存', { type: 'info', dangerouslyUseHTMLString: true, confirmButtonText: '确认追加', cancelButtonText: '取消' }
    )
    await api.updateAccountKeywords(detailAccount.value.id, merged)
    keywordDraftRows.value = merged.map(k => ({
      intentPrompt: k.intentPrompt, intentCategory: k.intentCategory || '', coreIntentWord: k.coreIntentWord || ''
    }))
    await loadAccounts()
    ElMessage.success(`已追加 ${toAdd.length} 条关键词`)
  } catch (e) {
    if (e === 'cancel' || e === undefined) return
    ElMessage.error('保存失败')
  }
}

// 删除关键词带 undo
let _kwTrash = []
function deleteKwWithUndo(idx) {
  const removed = keywordDraftRows.value.splice(idx, 1)
  _kwTrash.push({ idx, item: removed[0] })
  ElMessage({
    message: `已删除「${removed[0]?.intentPrompt || ''}」`,
    type: 'success', duration: 4000,
    showClose: true,
    customClass: 'kw-undo-msg',
    onClose: () => { _kwTrash = [] },
    grouping: false,
  })
}

function downloadTemplate() {
  // 用 CSV 格式 + BOM，Excel 直接打开。同时支持 ｜ 全角和 | 半角分隔
  const rows = [
    ['AI提示词', '类型（可选）', '搜索意图（可选）'],
    ['帮我推荐一款好用的手推车', '产品推荐', '手推车推荐'],
    ['哪家公司的物流设备比较好', '品牌对比', '物流设备品牌'],
    ['我需要找有丰富经验的设备供应商', '供应商寻找', '设备供应商'],
  ]
  const csv = rows.map(r => r.map(c => `"${String(c).replace(/"/g, '""')}"`).join(',')).join('\n')
  const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = '关键词导入模板.csv'; a.click()
  URL.revokeObjectURL(url)
}

/* ============ 回收站 ============ */
const recycleBinVisible = ref(false)
const recycleLoading = ref(false)
const deletedAccounts = ref([])
function openRecycleBin() { recycleBinVisible.value = true }
async function loadRecycleBin() {
  recycleLoading.value = true
  try {
    deletedAccounts.value = await api.getRecycleBin() || []
  } catch (e) {
    ElMessage.error('加载回收站失败')
    deletedAccounts.value = []
  } finally {
    recycleLoading.value = false
  }
}
function daysSinceDelete(deletedAt) {
  if (!deletedAt) return 0
  const d = new Date(String(deletedAt).replace(' ', 'T'))
  if (Number.isNaN(d.getTime())) return 0
  return Math.floor((Date.now() - d.getTime()) / 86400000)
}
function daysUntilPurge(deletedAt) {
  return Math.max(0, 30 - daysSinceDelete(deletedAt))
}
async function restoreAccount(row) {
  try {
    await api.restoreAccount(row.id)
    ElMessage.success(`已恢复「${row.companyName}」`)
    await Promise.all([loadAccounts(), loadRecycleBin()])
  } catch { ElMessage.error('恢复失败') }
}
async function purgeAccount(row) {
  try {
    await ElMessageBox.confirm(
      `<p>确定<b style="color:#dc2626">永久删除</b>「${row.companyName}」？</p><p style="color:#64748b;font-size:12px">将清除所有关键词、查词记录、报告，<b>不可恢复</b>。</p>`,
      '永久删除确认',
      { type: 'error', dangerouslyUseHTMLString: true, confirmButtonText: '永久删除', cancelButtonText: '取消' }
    )
    await api.purgeAccount(row.id)
    ElMessage.success('已永久删除')
    await loadRecycleBin()
  } catch { /* cancelled */ }
}

/* ============ 归档 ============ */
const archiveDialogVisible = ref(false)
const archiveLoading = ref(false)
const archivedAccounts = ref([])

function openArchiveDialog() { archiveDialogVisible.value = true }

async function loadArchivedAccounts() {
  archiveLoading.value = true
  try {
    archivedAccounts.value = await api.getArchivedAccounts() || []
  } catch (e) {
    ElMessage.error('加载归档列表失败')
    archivedAccounts.value = []
  } finally {
    archiveLoading.value = false
  }
}

async function archiveAccountFn(acc) {
  if (!acc) return
  try {
    await ElMessageBox.confirm(
      `<p>确定归档客户「<b>${acc.companyName}</b>」？</p><p style="color:#64748b;font-size:12px">归档后该客户将不再显示在列表中，也不会执行查词任务，但所有数据将被保留。可随时恢复。</p>`,
      '确认归档',
      { type: 'warning', dangerouslyUseHTMLString: true, confirmButtonText: '确认归档', cancelButtonText: '取消' }
    )
    await api.archiveAccount(acc.id)
    await loadAccounts()
    ElMessage.success(`「${acc.companyName}」已归档`)
  } catch { /* cancelled */ }
}

async function unarchiveAccount(row) {
  try {
    await api.unarchiveAccount(row.id)
    ElMessage.success(`已恢复「${row.companyName}」`)
    await Promise.all([loadAccounts(), loadArchivedAccounts()])
  } catch { ElMessage.error('恢复失败') }
}

async function purgeArchivedAccount(row) {
  try {
    await ElMessageBox.confirm(
      `<p>确定<b style="color:#dc2626">永久删除</b>「${row.companyName}」？</p><p style="color:#64748b;font-size:12px">将清除所有关键词、查词记录、报告，<b>不可恢复</b>。</p>`,
      '永久删除确认',
      { type: 'error', dangerouslyUseHTMLString: true, confirmButtonText: '永久删除', cancelButtonText: '取消' }
    )
    await api.purgeArchivedAccount(row.id)
    ElMessage.success('已永久删除')
    await loadArchivedAccounts()
  } catch { /* cancelled */ }
}

function showDeveloping(feature) {
  ElMessage.info(`「${feature}」功能正在开发中，敬请期待`)
}

/* ============ 删除 / 复制 / 导出 ============ */
async function removeAccount(acc) {
  if (!acc) return
  const kwHint = acc.keywordCount ? `（含 ${acc.keywordCount} 条关键词）` : ''
  try {
    await ElMessageBox.confirm(
      `<p>确定删除账号「${acc.companyName}」${kwHint}？</p><p style="color:#64748b;font-size:12px">账号将进入<b style="color:#0891b2">回收站保留 30 天</b>，期间可在右上角"回收站"中恢复。</p>`,
      '删除到回收站',
      { type: 'warning', dangerouslyUseHTMLString: true, confirmButtonText: '移到回收站', cancelButtonText: '取消' }
    )
    await api.deleteAccount(acc.id)
    if (detailAccount.value?.id === acc.id) detailVisible.value = false
    await loadAccounts()
    ElMessage.success('已移入回收站，30 天内可恢复')
  } catch { /* cancelled */ }
}

async function copyAccount(row) {
  const brands = parseBrands(row.companyBrand).join('、')
  const info = [
    `公司：${row.companyName}`,
    `品牌：${brands || '-'}`,
    `类型：正式`,
    `关键词：${row.keywordCount || 0} 条`,
    `平台：${(row.platforms || []).join('、') || '-'}`,
    `最后查词：${row.lastSearchDate || '从未查询'}`,
    `优化开始：${row.optimizeStartDate || '-'}`,
  ].join('\n')
  try {
    await navigator.clipboard.writeText(info)
    ElMessage.success('已复制到剪贴板')
  } catch { ElMessage.error('复制失败，请手动选择') }
}

function exportCsv() {
  if (!filteredAccounts.value.length) {
    ElMessage.warning('没有数据可导出'); return
  }
  const headers = ['公司名称', '品牌', '类型', '关键词数', '平台', '最后查词', '优化开始', '健康度']
  const rows = filteredAccounts.value.map(a => [
    a.companyName || '',
    parseBrands(a.companyBrand).join(' | '),
    '正式',
    a.keywordCount || 0,
    (a.platforms || []).join(' | '),
    a.lastSearchDate || '',
    a.optimizeStartDate || '',
    healthInfo(a).text,
  ])
  const csv = [headers, ...rows]
    .map(r => r.map(c => `"${String(c).replace(/"/g, '""')}"`).join(','))
    .join('\n')
  const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `客户列表_${todayStr()}.csv`
  a.click()
  URL.revokeObjectURL(url)
  ElMessage.success(`已导出 ${rows.length} 条记录`)
}

function resetFilters() {
  searchText.value = ''
  filterType.value = ''
  filterHealth.value = ''
  filterOwner.value = null
  filterPlatform.value = ''
}

/* ============ 操作菜单 ============ */
function handleCommand(cmd, row) {
  switch (cmd) {
    case 'edit': openDetail(row, 'info'); break
    case 'keywords': openDetail(row, 'keywords'); break
    case 'copy': copyAccount(row); break
    case 'upgrade':
      detailAccount.value = row
      openUpgrade()
      break
    case 'archive': archiveAccountFn(row); break
    case 'delete': removeAccount(row); break
  }
}

function goToSearch(account) {
  router.push(`/dashboard/keyword-search/${account.id}`)
}

function goRanking(row) {
  router.push(`/dashboard/ranking-analysis?accountId=${row.id}`)
}
function goKnowledge(row) {
  router.push(`/publish/knowledge?account=${row.id}`)
}
function goContentLibrary(row) {
  router.push(`/publish/content-library?account=${row.id}`)
}

// 平台 logo 统一走 <PlatformIcon> 组件 + utils/platformIcon.js(单一可信源)

function goCitation(row) {
  router.push(`/dashboard/citation-analysis?accountId=${row.id}`)
}

/* ============ 工具 ============ */
function todayStr() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
// 优化开始时间自由输入规范化：支持 / - . 空格 分隔 或 8 位连写 → YYYY-MM-DD
function normalizeDateInput(v) {
  if (!v) return ''
  const s = String(v).trim()
  let y, mo, d
  let m = s.match(/^(\d{4})(\d{2})(\d{2})$/)
  if (m) { [, y, mo, d] = m }
  else {
    const parts = s.split(/[/\-.\s]+/).filter(Boolean)
    if (parts.length !== 3) return s   // 解析不了，保留原值让用户改
    ;[y, mo, d] = parts
  }
  if (!/^\d{4}$/.test(y)) return s
  const mn = +mo, dn = +d
  if (mn < 1 || mn > 12 || dn < 1 || dn > 31) return s
  return `${y}-${String(mn).padStart(2, '0')}-${String(dn).padStart(2, '0')}`
}

async function loadAccounts() {
  loading.value = true
  try {
    const [accs, summary] = await Promise.all([
      api.getAccounts(false, true),  // includeDraft:账户管理显示初始客户+转正入口(不含临时账号)
      api.getAccountSummary().catch(() => []),
    ])
    accounts.value = accs || []
    const map = new Map()
    for (const s of summary || []) {
      map.set(s.id, {
        running: !!s.running,
        runningProgress: Number(s.runningProgress) || 0,
        todayTotal: Number(s.todayTotal) || 0,
      })
    }
    accountSummaryMap.value = map
  } catch {
    ElMessage.error('加载客户列表失败')
  } finally {
    loading.value = false
  }
}

/* ============ 调度 / 运行状态 ============ */

let _summaryTimer = null
function startSummaryPoll() {
  stopSummaryPoll()
  _summaryTimer = setInterval(async () => {
    try {
      const summary = await api.getAccountSummary()
      const map = new Map()
      for (const s of summary || []) {
        map.set(s.id, {
          running: !!s.running,
          runningProgress: Number(s.runningProgress) || 0,
          todayTotal: Number(s.todayTotal) || 0,
        })
      }
      accountSummaryMap.value = map
    } catch { /* 静默 */ }
  }, 8000)
}
function stopSummaryPoll() {
  if (_summaryTimer) { clearInterval(_summaryTimer); _summaryTimer = null }
}

onMounted(async () => {
  await loadAccounts()
  startSummaryPoll()
  loadAdminUsers()
  // 从查词管理「前往配置关键词」跳转过来:自动打开该客户的关键词配置
  const cfgId = Number(route.query.config)
  if (cfgId) {
    const acc = accounts.value.find(a => a.id === cfgId)
    if (acc) openDetail(acc, 'keywords')
  }
})
onBeforeUnmount(stopSummaryPoll)
</script>

<style scoped>
.account-page {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* ===== 页头 ===== */
.page-header {
  display: flex; align-items: center; justify-content: space-between;
}
.page-title {
  font-size: 20px; font-weight: 700; color: #0f172a;
  margin: 0; letter-spacing: -0.3px;
}
.page-sub {
  font-size: 12px; color: #94a3b8;
  margin: 4px 0 0;
}

/* ===== KPI ===== */
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
.kpi-card:focus-visible { box-shadow: 0 0 0 3px rgba(59,130,246,0.25); }
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
.kpi-icon-red { background: #fef2f2; color: #dc2626; }
.kpi-card-bad { border-color: rgba(220, 38, 38, 0.2); }
.kpi-sub-warn { color: #d97706; font-weight: 600; }

/* 风险预警 banner */
.risk-banner {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 16px; margin: 12px 0;
  background: linear-gradient(135deg, #fffbeb, #fef3c7);
  border: 1px solid #fcd34d;
  border-left: 4px solid #f59e0b;
  border-radius: 8px;
  color: #92400e; font-size: 13px;
}
.risk-banner .el-icon { color: #d97706; flex-shrink: 0; }
.risk-text { flex: 1; line-height: 1.6; }
.risk-text strong { color: #b45309; }
.risk-link {
  color: #b45309; font-weight: 600; cursor: pointer;
  text-decoration: underline; text-decoration-style: dotted;
}
.risk-link:hover { color: #7c2d12; }
.risk-show {
  background: #f59e0b; color: #fff; border: none;
  padding: 5px 12px; border-radius: 5px; cursor: pointer;
  font-size: 12px; font-weight: 600; flex-shrink: 0;
  font-family: inherit;
}
.risk-show:hover { background: #d97706; }

/* 批量操作计数 */
.bulk-cnt {
  display: inline-block;
  background: #6366f1; color: #fff;
  padding: 1px 7px; border-radius: 99px;
  font-size: 11px; margin-left: 4px;
}

/* 收藏 / pin 按钮 */
.pin-btn {
  background: transparent; border: none; cursor: pointer;
  width: 26px; height: 26px; border-radius: 5px;
  color: #cbd5e1;
  display: inline-flex; align-items: center; justify-content: center;
  transition: all 0.15s;
}
.pin-btn:hover { color: #f59e0b; background: #fffbeb; }
.pin-btn.pin-on { color: #f59e0b; }

/* 客户名行：定时 / 运行状态 */
.ca-sched {
  font-size: 13px; cursor: help; color: #94a3b8; vertical-align: middle;
}
.ca-running {
  display: inline-flex; align-items: center; gap: 4px;
  background: linear-gradient(135deg, rgba(99,102,241,0.15), rgba(139,92,246,0.1));
  color: #4338ca;
  padding: 2px 8px; border-radius: 4px;
  font-size: 11px; font-weight: 600;
  margin-left: 4px;
}
.ca-running-pulse {
  width: 5px; height: 5px; border-radius: 50%;
  background: #4338ca;
  animation: rp 1.4s ease-in-out infinite;
}
@keyframes rp {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.4; transform: scale(0.7); }
}

/* 紧凑模式 */
.account-table-dense :deep(.el-table__row) td { padding: 11px 0 !important; }
.account-table-dense :deep(.ca-meta) { display: none; }

/* 业务负责人 cell - 改派模式 */
.owner-cell {
  display: flex; align-items: center; flex-wrap: nowrap; gap: 5px;
  padding: 2px 6px; border-radius: 6px;
  cursor: pointer; transition: background .15s;
  font-size: 13px; color: #334155;
  overflow: hidden;            /* 多负责人不换行,放不下横向裁剪(title 仍显示全名),保证行高一致 */
}
.owner-cell:hover { background: #eef2ff; }
.owner-cell:hover .owner-edit-icon { opacity: 1; }
.owner-tag {
  display: inline-flex; align-items: center; flex: 0 0 auto; gap: 4px;
  white-space: nowrap;
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  padding: 1px 8px 1px 3px; border-radius: 99px;
  font-size: 12px; color: #475569; font-weight: 500;
}
.owner-avatar {
  display: inline-flex; align-items: center; justify-content: center;
  flex: 0 0 auto;
  width: 18px; height: 18px; border-radius: 50%;
  background: #64748b;
  color: #fff; font-size: 10px; font-weight: 700;
}
.owner-edit-icon { opacity: 0; color: #6366f1; transition: opacity .15s; font-size: 12px; }
.muted { color: #cbd5e1; font-size: 12px; }
.ymd-cell { font-family: ui-monospace, monospace; font-size: 12px; color: #475569; }

/* 回收站 */
.recycle-hint {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 14px; margin-bottom: 14px;
  background: linear-gradient(135deg, #ecfeff, #cffafe);
  border-left: 3px solid #06b6d4;
  border-radius: 6px;
  color: #0e7490; font-size: 12px; line-height: 1.6;
}
.recycle-hint strong { color: #0891b2; }

/* 归档 */
.archive-hint {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 14px; margin-bottom: 14px;
  background: linear-gradient(135deg, #fef3c7, #fde68a);
  border-left: 3px solid #d97706;
  border-radius: 6px;
  color: #92400e; font-size: 12px; line-height: 1.6;
}
.archive-hint strong { color: #b45309; }
.archive-btn-text { margin-left: 4px; }
.kpi-body { flex: 1; min-width: 0; }
.kpi-label { font-size: 11px; color: #94a3b8; margin-bottom: 2px; }
.kpi-val {
  font-size: 22px; font-weight: 800; color: #0f172a;
  line-height: 1.1; letter-spacing: -0.3px;
}
.kpi-sub { font-size: 11px; color: #64748b; margin-top: 3px; }
.kpi-sub-good { color: #16a34a; font-weight: 600; }
.kpi-sub-bad { color: #dc2626; font-weight: 600; }

/* ===== 面板 ===== */
.panel {
  background: #fff;
  border: 1px solid #eef2f7;
  border-radius: 14px;
  padding: 18px 22px;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
}

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
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.toolbar-search { width: 240px; }
.toolbar-filter { width: 130px; }

/* ===== 表格：premium ===== */
.account-table {
  --el-table-border-color: transparent;
  --el-table-header-bg-color: transparent;
  --el-table-row-hover-bg-color: #f8fafc;
}
.account-table :deep(.el-table__header-wrapper) {
  border-bottom: 1px solid #f1f5f9;
}
.account-table :deep(.el-table__header th) {
  background: transparent !important;
  padding: 8px 0 !important;
  text-transform: none;
}
.account-table :deep(.el-table__body td) {
  border-bottom: 1px solid #f1f5f9 !important;
  padding: 11px 0 !important;
  background: transparent !important;
}
.account-table :deep(.el-table__row:hover > td) {
  background: #f8fafc !important;
}
.account-table :deep(.el-table::before) { display: none; }

/* 客户单元格 - 两行式，无头像 */
.customer-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
  cursor: pointer;
  min-width: 0;
  padding-right: 8px;
  padding-left: 2px;
}
.ca-name-row {
  display: flex;
  align-items: center;
  gap: 7px;
  min-width: 0;
}
.ca-type-dot {
  width: 7px; height: 7px; border-radius: 50%;
  flex-shrink: 0;
  box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.8);
}
.ca-dot-paid { background: #22c55e; }
.ca-dot-quote { background: #f59e0b; }
.ca-name {
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
  letter-spacing: -0.1px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  transition: color .15s;
}
.customer-cell:hover .ca-name { color: #2563eb; }
.ca-temp {
  display: inline-flex; align-items: center;
  font-size: 10px; padding: 1px 6px; border-radius: 4px;
  background: linear-gradient(135deg, rgba(249, 115, 22, 0.18), rgba(244, 63, 94, 0.15));
  color: #ea580c; border: 1px solid rgba(249, 115, 22, 0.3);
  font-weight: 600; letter-spacing: 0.3px;
  flex-shrink: 0; white-space: nowrap;
  margin-left: 4px;
}
.ca-type {
  display: inline-flex;
  align-items: center;
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 4px;
  background: rgba(217, 119, 6, 0.12);
  color: #c2410c;
  font-weight: 600;
  letter-spacing: 0.3px;
  flex-shrink: 0;
  white-space: nowrap;
  line-height: 1.4;
}
.ca-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11.5px;
  color: #94a3b8;
  line-height: 1.3;
  padding-left: 14px;
}
.ca-meta-item {
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.1px;
}
.ca-meta-sep { color: #e2e8f0; }

/* 品牌列 */
.brand-cell {
  display: flex;
  flex-wrap: nowrap;
  gap: 4px;
  align-items: center;
  overflow: hidden;
}
.brand-tag {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 5px;
  background: #eff6ff;
  color: #1d4ed8;
  font-weight: 500;
  white-space: nowrap;
  flex-shrink: 0;
  letter-spacing: 0.1px;
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
}
.brand-tag-more {
  background: #f1f5f9;
  color: #64748b;
  cursor: default;
}
.brand-cell-clickable {
  cursor: pointer;
  padding: 2px 4px;
  border-radius: 6px;
  transition: background .15s;
  position: relative;
}
.brand-cell-clickable:hover {
  background: #f8fafc;
}
.brand-cell-clickable:hover .brand-edit-icon {
  opacity: 1;
}
.brand-edit-icon {
  opacity: 0;
  color: #94a3b8;
  margin-left: 2px;
  transition: opacity .15s;
  font-size: 12px;
}
.brand-edit-popover {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.brand-edit-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

/* 平台 chip - 中性灰 */
.platforms-cell {
  display: flex;
  flex-wrap: wrap;
  gap: 3px;
  align-items: center;
}
.platforms-cell .pf-ico {
  border-radius: 6px;
  padding: 2px;
}
.platforms-cell .pf-abbr {
  border-radius: 6px;
}
.platform-chip {
  font-size: 11px;
  padding: 3px 10px;
  border-radius: 5px;
  background: #f1f5f9;
  color: #475569;
  white-space: nowrap;
  flex-shrink: 0;
  font-weight: 500;
}
.platform-chip-more {
  background: #e2e8f0;
  color: #64748b;
  cursor: default;
}
.platforms-cell-clickable {
  cursor: pointer;
  padding: 2px 4px;
  border-radius: 6px;
  transition: background .15s;
}
.platforms-cell-clickable:hover {
  background: #f8fafc;
}
.platforms-cell-clickable:hover .platform-edit-icon {
  opacity: 1;
}
.platform-edit-icon {
  opacity: 0;
  color: #94a3b8;
  margin-left: 2px;
  transition: opacity .15s;
  font-size: 12px;
}
.platform-edit-popover {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.platform-edit-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

/* 健康度 - 小方块 */
.health-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 10px;
  border-radius: 5px;
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
  cursor: default;
  letter-spacing: 0.3px;
}
.health-dot {
  display: inline-block;
  width: 6px; height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
  box-shadow: 0 0 0 2px rgba(255,255,255,0.6);
}
.health-good { background: rgba(22, 163, 74, 0.1); color: #15803d; }
.health-good .health-dot { background: #16a34a; }
.health-warn { background: rgba(217, 119, 6, 0.1); color: #b45309; }
.health-warn .health-dot { background: #d97706; }
.health-bad { background: rgba(220, 38, 38, 0.1); color: #b91c1c; }
.health-bad .health-dot { background: #dc2626; }

:deep(.el-select-dropdown__item) .health-dot { margin-right: 8px; }

/* 分析入口 - 双链接 */
.entry-cell {
  display: inline-flex;
  align-items: center;
  gap: 2px;
}
.entry-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: transparent;
  border: none;
  padding: 5px 10px;
  font-size: 12px;
  color: #2563eb;
  font-weight: 500;
  cursor: pointer;
  border-radius: 5px;
  transition: background .15s, color .15s;
  letter-spacing: 0.1px;
}
.entry-link:hover {
  background: #eff6ff;
  color: #1d4ed8;
}
.entry-link .el-icon { opacity: 0.85; }
.entry-sep {
  width: 1px;
  height: 12px;
  background: #e2e8f0;
  flex-shrink: 0;
}

/* 操作按钮 - 极简 */
/* 操作按钮 — 静止统一中性灰,hover 才显各自主题色(平时干净、交互有色) */
.act-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: 1px solid transparent;
  padding: 5px 11px;
  font-size: 12.5px;
  font-weight: 500;
  color: #64748b;
  cursor: pointer;
  border-radius: 7px;
  transition: all .15s ease;
  line-height: 1;
  vertical-align: middle;
  margin-left: 2px;
}
.act-btn:hover { background: #f1f5f9; color: #0f172a; }
/* 主操作:查词管理 — 默认描边强调一点 */
.act-btn-primary { color: #334155; border-color: #e2e8f0; }
.act-btn-primary:hover { background: #eff6ff; color: #1d4ed8; border-color: #bfdbfe; }
.act-btn-report:hover { background: #f5f3ff; color: #6d28d9; }
.act-btn-rank:hover { background: #f0fdfa; color: #0f766e; }
.act-btn-kb:hover { background: #fefce8; color: #a16207; }
.act-btn-lib:hover { background: #fdf2f8; color: #be185d; }
/* 转为正式:唯一实心 CTA(草稿态) */
.act-btn-promote { color: #fff; background: #16a34a; padding: 5px 12px; font-weight: 600; }
.act-btn-promote:hover { background: #15803d; color: #fff; }
.act-btn-more { width: 28px; height: 28px; padding: 0; color: #94a3b8; }
.act-btn-more:hover { background: #f1f5f9; color: #0f172a; }

/* 客户类型 列 */
.type-pill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 9px;
  border-radius: 5px;
  font-size: 11.5px;
  font-weight: 600;
  white-space: nowrap;
  letter-spacing: 0.2px;
}
.type-pill-dot {
  width: 6px; height: 6px; border-radius: 50%;
  flex-shrink: 0;
}
.type-pill-paid {
  background: rgba(22, 163, 74, 0.10);
  color: #15803d;
}
.type-pill-paid .type-pill-dot { background: #16a34a; }
.type-pill-quote {
  background: rgba(217, 119, 6, 0.12);
  color: #b45309;
}
.type-pill-quote .type-pill-dot { background: #d97706; }
.type-pill-clickable {
  cursor: pointer;
  transition: filter .15s;
}
.type-pill-clickable:hover {
  filter: brightness(0.96);
}
.type-pill-caret {
  font-size: 10px;
  margin-left: 2px;
  opacity: 0.7;
}

/* 调度 / 运行 列 */
.sched-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}
.sched-running {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #15803d;
  font-weight: 600;
}
.sched-running-label { color: #15803d; }
.sched-running-pct {
  margin-left: auto;
  font-variant-numeric: tabular-nums;
  color: #0f172a;
  font-weight: 700;
  font-size: 12px;
}
.sched-on {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #2563eb;
  font-weight: 600;
}
.sched-on-label { letter-spacing: 0.2px; }
.sched-next {
  font-size: 11px;
  color: #64748b;
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.1px;
}
.muted-tiny { color: #cbd5e1; }
.live-dot {
  width: 7px; height: 7px; border-radius: 50%;
  background: #16a34a;
  box-shadow: 0 0 0 3px rgba(22,163,74,0.18);
  animation: dot-blink 1.4s ease-in-out infinite;
  flex-shrink: 0;
}
@keyframes dot-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

/* 最后查词 - 两行垂直 */
.last-search {
  display: flex;
  flex-direction: column;
  gap: 1px;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
  line-height: 1.3;
}
.ls-date {
  font-size: 12.5px;
  font-weight: 500;
  letter-spacing: -0.1px;
}
.ls-rel {
  font-size: 11px;
  color: #94a3b8;
  letter-spacing: 0.2px;
}
.ls-good { color: #15803d; }
.ls-warn { color: #b45309; }
.ls-bad { color: #b91c1c; font-weight: 600; }

.muted {
  color: #cbd5e1;
  font-size: 13px;
  letter-spacing: 0.2px;
}

.table-empty {
  padding: 40px 0;
  text-align: center;
  color: #94a3b8;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}
.table-empty p { margin: 0; }

/* ===== 添加客户弹窗 · 高级控制台风 ===== */
.add-dialog :deep(.el-dialog) { border-radius: 16px; overflow: hidden; padding: 0; }
.add-dialog :deep(.el-dialog__header) { margin: 0; padding: 0; }
.add-dialog :deep(.el-dialog__headerbtn) { top: 20px; right: 20px; z-index: 3; }
.add-dialog :deep(.el-dialog__headerbtn .el-dialog__close) { color: rgba(255,255,255,.85); font-size: 18px; }
.add-dialog :deep(.el-dialog__headerbtn:hover .el-dialog__close) { color: #fff; }
.add-dialog :deep(.el-dialog__body) { padding: 22px 26px 6px; }
.add-dialog :deep(.el-dialog__footer) { padding: 14px 26px 20px; border-top: 1px solid #f1f5f9; }

.ad-banner {
  display: flex; align-items: center; gap: 14px;
  padding: 22px 26px; color: #fff;
  background: linear-gradient(135deg, #1e3a8a 0%, #2563eb 58%, #3b82f6 100%);
}
.ad-banner-ic {
  width: 42px; height: 42px; border-radius: 11px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  background: rgba(255,255,255,.16);
}
.ad-banner-title { font-size: 17px; font-weight: 700; letter-spacing: .3px; }
.ad-banner-sub { font-size: 12px; opacity: .82; margin-top: 3px; }

.ad-steps { display: flex; align-items: center; margin: 2px 0 22px; }
.ad-step { display: flex; align-items: center; gap: 8px; font-size: 13px; color: #94a3b8; font-weight: 600; }
.ad-step-no {
  width: 22px; height: 22px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 12px; background: #e2e8f0; color: #94a3b8; transition: all .2s;
}
.ad-step.on { color: #2563eb; }
.ad-step.on .ad-step-no { background: #2563eb; color: #fff; box-shadow: 0 0 0 4px rgba(37,99,235,.15); }
.ad-step.done { color: #16a34a; }
.ad-step.done .ad-step-no { background: #16a34a; color: #fff; }
.ad-step-line { flex: 1; height: 2px; background: #e2e8f0; margin: 0 14px; border-radius: 2px; transition: background .2s; }
.ad-step-line.on { background: #16a34a; }

.ad-form :deep(.el-form-item) { margin-bottom: 18px; }
.ad-form :deep(.el-form-item__label) {
  font-size: 12px; font-weight: 600; color: #334155;
  padding-bottom: 6px; line-height: 1.4;
}
.ad-form :deep(.el-input__wrapper),
.ad-form :deep(.el-select__wrapper),
.ad-form :deep(.el-textarea__inner) {
  border-radius: 8px; box-shadow: 0 0 0 1px #e2e8f0 inset; transition: box-shadow .15s;
}
.ad-form :deep(.el-input__wrapper:hover),
.ad-form :deep(.el-select__wrapper:hover) { box-shadow: 0 0 0 1px #cbd5e1 inset; }
.ad-form :deep(.el-input__wrapper.is-focus),
.ad-form :deep(.el-select__wrapper.is-focused) { box-shadow: 0 0 0 2px #3b82f6 inset; }

/* 下拉菜单 icon */
:deep(.el-dropdown-menu__item .el-icon) {
  margin-right: 6px;
  vertical-align: middle;
}

/* 分页 */
.pagination-row {
  display: flex;
  justify-content: flex-end;
  padding: 12px 0 2px;
}

/* ===== 弹窗内细节 ===== */
.field-hint {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #94a3b8;
  margin-top: 4px;
  line-height: 1.5;
}
.date-row { display: flex; align-items: center; gap: 8px; width: 100%; }
.import-hint {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  color: #94a3b8;
  margin-bottom: 8px;
  line-height: 1.5;
}
.import-hint code {
  background: #f1f5f9;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 12px;
  color: #475569;
}
.keyword-row-actions { margin-top: 10px; margin-bottom: 8px; display: flex; justify-content: flex-end; }
.kw-table-head {
  font-size: 13px; font-weight: 600; color: #475569;
  margin-bottom: 8px; padding-bottom: 8px;
  border-bottom: 1px solid #f1f5f9;
}
.kw-footer {
  display: flex; justify-content: flex-end; gap: 8px; margin-top: 12px;
}
.tab-count { color: #909399; margin-left: 4px; font-weight: 400; }

/* ===== 响应式 ===== */
@media (max-width: 1180px) {
  .kpi-strip { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 768px) {
  .toolbar { flex-direction: column; align-items: stretch; }
  .toolbar-actions { flex-direction: column; align-items: stretch; }
  .toolbar-search, .toolbar-filter { width: 100%; }
  .kpi-strip { grid-template-columns: 1fr; }
}
.kpi-box { display: flex; flex-direction: column; gap: 8px; width: 100%; }
.kpi-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.kpi-row .kpi-input { flex: 1; min-width: 220px; }

/* ===== 精雕:筛选条 / 健康标记 / 编辑可点提示 ===== */
.filter-bar { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; padding: 10px 4px 4px; margin-bottom: 4px; }
.fb-segs { display: inline-flex; background: #f1f5f9; border-radius: 9px; padding: 3px; gap: 2px; }
.fb-seg { border: 0; background: transparent; cursor: pointer; padding: 5px 12px; border-radius: 7px; font-size: 13px; color: #64748b; display: inline-flex; align-items: center; gap: 5px; transition: all .15s; }
.fb-seg:hover { color: #0f172a; }
.fb-seg.active { background: #fff; color: #1e293b; font-weight: 600; box-shadow: 0 1px 3px rgba(15,23,42,.1); }
.fb-seg.fb-warn.active { color: #b45309; }
.fb-seg.fb-bad.active { color: #b91c1c; }
.fb-n { font-size: 11px; min-width: 18px; height: 16px; padding: 0 5px; border-radius: 8px; background: #e2e8f0; color: #475569; display: inline-flex; align-items: center; justify-content: center; margin-left: 1px; }
.fb-seg.fb-warn .fb-n { background: #fef3c7; color: #b45309; }
.fb-seg.fb-bad .fb-n { background: #fee2e2; color: #b91c1c; }
.fb-select { width: 150px; }
.fb-result { font-size: 12px; color: #94a3b8; margin-left: auto; }
.ca-health { display: inline-block; width: 7px; height: 7px; border-radius: 50%; flex: 0 0 auto; }
.ca-health-warn { background: #f59e0b; box-shadow: 0 0 0 3px #fef3c7; }
.ca-health-bad { background: #ef4444; box-shadow: 0 0 0 3px #fee2e2; }
.ca-edit-hint { opacity: 0; color: #2563eb; font-size: 12px; transition: opacity .15s; flex: 0 0 auto; }
.customer-cell { cursor: pointer; }
.customer-cell:hover .ca-edit-hint { opacity: 1; }
.customer-cell:hover .ca-name { text-decoration: underline; text-underline-offset: 2px; }

/* 筛选条:整体做成一条带质感的控制条 */
.filter-bar { background: #fafbfc; border: 1px solid #eef2f6; border-radius: 12px; padding: 8px 12px !important; }
.fb-select :deep(.el-select__wrapper) {
  border-radius: 9px; box-shadow: 0 0 0 1px #e2e8f0 inset; background: #fff;
  min-height: 32px; transition: box-shadow .15s ease;
}
.fb-select :deep(.el-select__wrapper:hover) { box-shadow: 0 0 0 1px #cbd5e1 inset; }
.fb-select :deep(.el-select__wrapper.is-focused) { box-shadow: 0 0 0 2px rgba(48,193,180,.4) inset; }
.fb-seg { transition: all .18s cubic-bezier(.16, 1, .3, 1); }
.fb-seg:hover:not(.active) { background: rgba(255,255,255,.7); }
.fb-seg.active { transform: translateY(-0.5px); }

/* 覆盖平台占位:虚线胶囊,hover 主色 */
.platforms-cell .muted { border: 1px dashed #cbd5e1; border-radius: 99px; padding: 2px 10px; color: #94a3b8; font-size: 12px; transition: all .15s; }
.platforms-cell-clickable:hover .muted { border-color: var(--primary, #30c1b4); color: var(--primary, #30c1b4); }

/* 业务负责人 tag:配色由内联 style 控制(按角色),这里只管形状/阴影质感 */
.owner-tag { box-shadow: 0 1px 2px rgba(15,23,42,.04); }
/* 负责人超过 2 个:+N 胶囊,点击查看全部 */
.owner-more {
  display: inline-flex; align-items: center; justify-content: center;
  min-width: 26px; height: 20px; padding: 0 7px; border-radius: 99px;
  background: #e2e8f0; color: #475569; font-size: 12px; font-weight: 600;
  cursor: pointer; transition: all .15s;
}
.owner-more:hover { background: #cbd5e1; color: #1e293b; }
.owner-more-list { display: flex; flex-wrap: wrap; gap: 6px; }

/* 编辑弹窗:分组分区标题 */
.form-sec {
  font-size: 13px; font-weight: 700; color: #1e293b; margin: 6px 0 12px;
  padding-left: 9px; border-left: 3px solid var(--primary, #30c1b4); line-height: 1.2;
}
.form-sec:not(:first-child) { margin-top: 20px; }
</style>

<!-- 非 scoped:el-dialog 正文被 teleport 到 body,scoped :deep 难命中,这里用唯一类名全局兜住。
     弹窗内容超出视口时正文区滚动,头部/底部按钮(下一步/确认)始终可见。 -->
<style>
.add-dialog .el-dialog__body,
.detail-dialog .el-dialog__body { max-height: calc(100vh - 230px); overflow-y: auto; }

/* ══════════ 客户弹窗 · 高级化样式 ══════════ */
.detail-dialog .el-dialog,
.add-dialog .el-dialog{
  border-radius:18px; overflow:hidden; padding:0;
  box-shadow:0 40px 90px -36px rgba(15,23,42,.45), 0 0 0 1px rgba(15,23,42,.04);
}
.detail-dialog .el-dialog__header,
.add-dialog .el-dialog__header{
  margin:0; padding:22px 28px 18px; border-bottom:1px solid #eef0f4;
  background:linear-gradient(180deg,#fcfdfe,#fff);
}
.detail-dialog .el-dialog__title,
.add-dialog .el-dialog__title{
  font-size:19px; font-weight:800; color:#0f172a; letter-spacing:-.4px; line-height:1.3;
}
.detail-dialog .el-dialog__headerbtn,
.add-dialog .el-dialog__headerbtn{ top:20px; right:22px; width:30px; height:30px; border-radius:8px; transition:background .15s; }
.detail-dialog .el-dialog__headerbtn:hover,
.add-dialog .el-dialog__headerbtn:hover{ background:#f1f5f9; }
.detail-dialog .el-dialog__close,
.add-dialog .el-dialog__close{ color:#94a3b8; font-size:18px; }
.detail-dialog .el-dialog__body,
.add-dialog .el-dialog__body{ padding:6px 28px 24px; }

/* 页签 */
.detail-dialog .el-tabs__header{ margin:0 0 20px; }
.detail-dialog .el-tabs__nav-wrap::after{ height:1px; background:#eef0f4; }
.detail-dialog .el-tabs__item{ font-size:15px; font-weight:600; color:#9aa3b2; padding:0 4px; height:46px; margin-right:26px; transition:color .15s; }
.detail-dialog .el-tabs__item.is-active{ color:#0f172a; font-weight:700; }
.detail-dialog .el-tabs__item:hover{ color:#475569; }
.detail-dialog .el-tabs__active-bar{ height:2.5px; border-radius:3px; background:var(--primary,#30c1b4); }

/* 分区标题 —— 圆点 + 标题 + 分隔线(提高特异性压过 scoped 的左竖条) */
.detail-dialog .el-dialog__body .form-sec,
.add-dialog .el-dialog__body .form-sec{
  display:flex; align-items:center; gap:9px;
  border-left:0 !important; padding:0 0 10px !important;
  margin:28px 0 18px; font-size:14px; font-weight:800; color:#0f172a; letter-spacing:-.2px;
  border-bottom:1px solid #eef0f4; line-height:1.2;
}
.detail-dialog .el-dialog__body .form-sec::before,
.add-dialog .el-dialog__body .form-sec::before{
  content:''; width:15px; height:15px; border-radius:5px; flex-shrink:0;
  background:linear-gradient(135deg,#34d3c4,#0ea5a0); box-shadow:0 2px 6px -1px rgba(14,165,160,.4);
}
.detail-dialog .el-dialog__body .form-sec:first-child,
.add-dialog .el-dialog__body .form-sec:first-child{ margin-top:6px; }

/* 表单 label / 间距 */
.detail-dialog .el-form-item{ margin-bottom:20px; }
.detail-dialog .el-form-item__label{ color:#475569; font-weight:600; font-size:13.5px; padding-right:14px; }
.detail-dialog .el-form-item.is-required .el-form-item__label::before{ color:#ef4444; }

/* 输入框 / 下拉 / 文本域 统一圆角描边 */
.detail-dialog .el-input__wrapper,
.detail-dialog .el-select__wrapper,
.detail-dialog .el-textarea__inner{
  border-radius:10px; box-shadow:0 0 0 1px #e4e8ee inset; background:#fff; transition:box-shadow .15s;
}
.detail-dialog .el-input__wrapper:hover,
.detail-dialog .el-select__wrapper:hover,
.detail-dialog .el-textarea__inner:hover{ box-shadow:0 0 0 1px #cbd5e1 inset; }
.detail-dialog .el-input__wrapper.is-focus,
.detail-dialog .el-select__wrapper.is-focused,
.detail-dialog .el-textarea__inner:focus{ box-shadow:0 0 0 2px rgba(48,193,180,.5) inset; }

/* KPI / 数据共享 卡片化 */
.detail-dialog .kpi-box{
  background:#fafbfc; border:1px solid #eef0f4; border-radius:12px; padding:14px 16px; gap:11px;
}
.detail-dialog .kpi-row{ gap:12px; }
.detail-dialog .kpi-row .el-checkbox__label{ font-weight:600; color:#334155; }

/* 字段提示 */
.detail-dialog .field-hint{ color:#94a3b8; }

/* 保存按钮区 → 底部条 */
.detail-dialog .el-tab-pane > div[style*="text-align"]{
  border-top:1px solid #eef0f4; margin:22px -28px -8px; padding:16px 28px 6px;
}
.detail-dialog .el-button--primary{ border-radius:9px; font-weight:600; }
.detail-dialog .el-button{ border-radius:9px; }

/* 关键词 tab 的小细节 */
.detail-dialog .kw-footer .el-button{ border-radius:8px; }
</style>
