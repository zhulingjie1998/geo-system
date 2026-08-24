<template>
  <div class="kb-page">
    <!-- ① 客户列表视图：所有客户平铺（像客户管理），点击查看其知识库 -->
    <template v-if="!currentAccountId">
      <!-- KPI 概览 -->
      <div class="kb-kpis">
        <div class="kb-kpi">
          <div class="kb-kpi-ic kpi-ic-blue"><el-icon :size="18"><User /></el-icon></div>
          <div><div class="kb-kpi-num">{{ customerOverview.length }}</div><div class="kb-kpi-lbl">客户总数</div></div>
        </div>
        <div class="kb-kpi">
          <div class="kb-kpi-ic kpi-ic-green"><el-icon :size="18"><Files /></el-icon></div>
          <div><div class="kb-kpi-num">{{ kbBuiltCount }}</div><div class="kb-kpi-lbl">已建知识库</div></div>
        </div>
        <div class="kb-kpi">
          <div class="kb-kpi-ic kpi-ic-amber"><el-icon :size="18"><Plus /></el-icon></div>
          <div><div class="kb-kpi-num">{{ customerOverview.length - kbBuiltCount }}</div><div class="kb-kpi-lbl">待建知识库</div></div>
        </div>
      </div>

      <div class="kb-panel">
        <div class="kb-panel-bar">
          <el-input v-model="overviewSearch" placeholder="搜索品牌名 / 公司名" clearable
                    :prefix-icon="Search" class="kb-list-search" />
          <span class="kb-list-meta">{{ filteredOverview.length }} 个客户</span>
          <div class="kb-panel-bar-right">
            <el-button :icon="Refresh" plain :loading="loadingOverview" @click="loadCustomerOverview">刷新</el-button>
            <el-button :icon="UploadFilled" plain @click="excelImportOpen = true">Excel 导入</el-button>
            <el-button :icon="Plus" type="primary" @click="openCreateDialog">创建知识库</el-button>
          </div>
        </div>

        <el-table :data="filteredOverview" v-loading="loadingOverview" class="kb-table" size="default"
                  @row-click="onPickCustomer"
                  empty-text="还没有客户，或无匹配结果">
          <el-table-column label="客户" min-width="300">
            <template #default="{ row }">
              <div class="kb-cust-cell">
                <span class="kb-avatar" :style="{ background: avatarColor(row) }">{{ avatarText(row) }}</span>
                <div class="kb-cust-txt">
                  <span class="kb-cust-name">{{ brandLabel(row.company_brand) || row.company_name }}</span>
                  <span v-if="brandLabel(row.company_brand) && row.company_name" class="kb-cust-company">{{ row.company_name }}</span>
                </div>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="类型" width="90" align="center">
            <template #default="{ row }">
              <el-tag size="small" effect="light" :type="row.user_type === 'paid' ? 'success' : 'info'">
                {{ row.user_type === 'paid' ? '付费' : '报价' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="知识库" width="120" align="center">
            <template #default="{ row }">
              <span v-if="row.kb_count" class="kb-vcount">{{ row.kb_count }} 个版本</span>
              <span v-else class="kb-none">未建</span>
            </template>
          </el-table-column>
          <el-table-column label="当前版本" width="160" align="center">
            <template #default="{ row }">
              <el-tag v-if="row.kb_count" size="small" :type="row.current_created_by === 'ai' ? 'primary' : 'success'" effect="plain">
                v{{ row.current_version }} · {{ row.current_created_by === 'ai' ? 'AI' : '人工' }}
              </el-tag>
              <span v-else class="cell-muted">—</span>
            </template>
          </el-table-column>
          <el-table-column label="更新时间" width="170">
            <template #default="{ row }">
              <span class="cell-time">{{ row.current_created_at || row.latest_kb_at || '—' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="" width="64" align="center">
            <template #default="{ row }">
              <span class="kb-row-go">{{ row.kb_count ? '查看' : '创建' }} <el-icon :size="12"><ArrowRight /></el-icon></span>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </template>

    <!-- ② 详情视图工具栏：返回客户列表 + 当前客户 -->
    <div v-else class="toolbar">
      <div class="tb-left">
        <el-button :icon="ArrowLeft" plain @click="backToList">返回客户列表</el-button>
        <span class="tb-title">{{ currentAccountLabel }}</span>
        <span v-if="currentVersion" class="tb-current">
          当前 <strong>v{{ currentVersion.version }}</strong>
          <el-tag size="small"
                  :type="currentVersion.created_by === 'ai' ? 'primary' : 'success'"
                  effect="plain" style="margin-left:6px">
            {{ currentVersion.created_by === 'ai' ? 'AI 生成' : '人工编辑' }}
          </el-tag>
        </span>
      </div>
      <div class="tb-right">
        <el-button :icon="Search" plain :disabled="!currentVersion" :loading="proofreading"
                   @click="openProofread">校对规则库</el-button>
        <el-button :icon="UploadFilled" plain @click="excelImportOpen = true">Excel 导入</el-button>
        <el-button :icon="Plus" type="primary" @click="openCreateDialog">+ 创建知识库</el-button>
      </div>
    </div>

    <!-- 主体：左侧版本列表 + 右侧内容区 -->
    <div class="kb-body" v-if="currentAccountId">
      <!-- 左：版本/资料 -->
      <aside class="kb-side">
        <div class="side-section">
          <div class="side-head">版本历史 ({{ versions.length }})</div>
          <div v-if="!versions.length" class="side-empty">还没有版本</div>
          <div v-else class="version-list">
            <div v-for="v in versions" :key="v.id"
                 class="ver-item" :class="{ active: currentVersion?.id === v.id }"
                 @click="loadVersion(v.id)">
              <div class="ver-row1">
                <span class="ver-tag">知识库 v{{ v.version }}</span>
                <el-tag size="small" :type="v.created_by === 'ai' ? 'primary' : 'success'" effect="plain">
                  {{ v.created_by === 'ai' ? 'AI' : '人工' }}
                </el-tag>
                <span v-if="v.is_current" class="ver-current">● 当前</span>
              </div>
              <div class="ver-row2">{{ v.created_at }}</div>
              <div class="ver-actions" @click.stop>
                <el-button v-if="!v.is_current" link size="small" @click="setCurrent(v.id)">设为当前</el-button>
                <el-button link size="small" type="danger" @click="delVersion(v.id)">删</el-button>
              </div>
            </div>
          </div>
        </div>

        <div class="side-section">
          <div class="side-head">基础资料 ({{ baseSources.length }})</div>
          <div v-if="!baseSources.length" class="side-empty">还没上传资料</div>
          <div v-else class="src-list">
            <div v-for="s in baseSources" :key="s.id" class="src-item">
              <div class="src-row1">
                <el-icon class="src-icon" :size="14">
                  <component :is="srcIcon(s.file_type)" />
                </el-icon>
                <span class="src-name" :title="s.file_name">{{ s.file_name }}</span>
              </div>
              <div class="src-row2">
                <el-tag size="small" :type="srcStatusType(s.parser_status)" effect="plain">
                  {{ srcStatusText(s.parser_status) }}
                </el-tag>
                <span class="src-meta">{{ formatSize(s.file_size) }}</span>
                <el-button link size="small" @click="viewSource(s)">看文本</el-button>
                <el-button link size="small" type="danger" @click="delSource(s.id)">删</el-button>
              </div>
            </div>
          </div>
        </div>
      </aside>

      <!-- 右：内容主区 -->
      <section class="kb-main">
        <div v-if="!currentVersion" class="kb-empty">
          <el-empty description="还没有知识库，点击右上角「+ 创建知识库」">
            <el-button type="primary" :icon="Plus" @click="openCreateDialog">+ 创建知识库</el-button>
          </el-empty>
        </div>
        <template v-else>
          <!-- 阅读模式（分模块翻页） -->
          <div v-if="!editing" class="kb-view">
            <div class="kb-view-head">
              <div>
                <strong>知识库 v{{ currentVersion.version }}</strong>
                <span class="kb-view-time">· {{ currentVersion.created_at }}</span>
                <span v-if="currentVersion.instruction" class="kb-view-inst">
                  · {{ truncate(currentVersion.instruction, 50) }}
                </span>
              </div>
              <div class="kb-view-actions">
                <el-button :icon="Download" plain @click="exportKb('pdf')">导出 PDF</el-button>
                <el-button :icon="Download" plain @click="exportKb('docx')">导出 Word</el-button>
                <el-button v-if="currentAccount?.status === 'draft'" type="success" plain @click="promoteOpen = true">转为正式</el-button>
                <el-button type="warning" plain @click="reviewOpen = true">审核标注</el-button>
                <el-button :icon="Plus" plain @click="openAddModule">添加模块</el-button>
                <el-button :icon="MagicStick" plain @click="aiExpandOpen = true">AI 扩充</el-button>
                <el-button type="primary" :icon="EditPen" @click="enterEdit">继续修改</el-button>
              </div>
            </div>

            <!-- 模块导航条 -->
            <div v-if="kbModules.length > 1" class="kb-mod-nav">
              <button v-for="(m, i) in kbModules" :key="m.key"
                      class="kb-mod-tab"
                      :class="{ active: i === currentModuleIdx, warn: m.has_warning }"
                      @click="currentModuleIdx = i"
                      :title="m.title">
                <span class="kb-mod-tab-key">{{ m.key === 'cover' ? '封面' : m.key }}</span>
                <el-tag v-if="m.warning_count" size="small" type="warning" effect="dark"
                        class="kb-mod-warn-badge">{{ m.warning_count }}</el-tag>
              </button>
            </div>

            <!-- 当前模块标题（含 ⚠ 提示） -->
            <div v-if="currentModule" class="kb-mod-header">
              <div class="kb-mod-header-left">
                <span class="kb-mod-header-key">{{ currentModule.key === 'cover' ? '📄' : currentModule.key }}</span>
                <span class="kb-mod-header-title">{{ currentModule.title }}</span>
              </div>
              <span v-if="currentModule.warning_count" class="kb-mod-warn-tip">
                <el-icon :size="12"><Warning /></el-icon>
                本模块有 <strong>{{ currentModule.warning_count }}</strong> 处「待客户确认」事项
              </span>
            </div>

            <div class="kb-content kb-content-single"
                 v-html="renderMarkdown(currentModule ? currentModule.content : currentVersion.content)"></div>

            <!-- 上下页 -->
            <div v-if="kbModules.length > 1" class="kb-mod-pager">
              <el-button :icon="ArrowLeft" :disabled="currentModuleIdx <= 0"
                         @click="currentModuleIdx = Math.max(0, currentModuleIdx - 1)">
                上一模块{{ kbModules[currentModuleIdx-1] ? ' · ' + kbModules[currentModuleIdx-1].key : '' }}
              </el-button>
              <span class="kb-mod-pager-mid">{{ currentModuleIdx + 1 }} / {{ kbModules.length }}</span>
              <el-button type="primary"
                         :disabled="currentModuleIdx >= kbModules.length - 1"
                         @click="currentModuleIdx = Math.min(kbModules.length - 1, currentModuleIdx + 1)">
                下一模块{{ kbModules[currentModuleIdx+1] ? ' · ' + kbModules[currentModuleIdx+1].key : '' }}
                <el-icon class="el-icon--right"><ArrowRight /></el-icon>
              </el-button>
            </div>
          </div>

          <!-- 编辑模式 -->
          <div v-else class="kb-edit">
            <div class="kb-edit-head">
              <strong>编辑 知识库 v{{ currentVersion.version }}</strong>
              <span class="muted">→ 保存或重新优化生成 知识库 v{{ currentVersion.version + 1 }}</span>
            </div>

            <el-input
              v-model="editContent"
              type="textarea"
              :rows="22"
              placeholder="编辑当前知识库内容（markdown）"
              class="edit-textarea"
            />

            <div class="edit-form">
              <el-form label-position="top">
                <el-form-item label="新要求（描述本次想让 AI 怎么改进）">
                  <el-input
                    v-model="editInstruction"
                    type="textarea"
                    :rows="3"
                    placeholder="例：补充竞品分析；M03 要更详细产品参数；删除冗余案例；语气更专业..."
                  />
                </el-form-item>

                <el-form-item label="补充资料（选填，将连同当前内容一起喂给 AI）">
                  <el-upload
                    drag multiple
                    :auto-upload="false"
                    :show-file-list="true"
                    :file-list="addUploadFiles"
                    @change="onAddUploadChange"
                    @remove="onAddUploadRemove"
                  >
                    <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
                    <div class="el-upload__text">拖拽 PDF / Word / Excel / TXT / 图片 到此</div>
                  </el-upload>
                </el-form-item>
              </el-form>
            </div>

            <div class="kb-edit-actions">
              <el-button @click="cancelEdit">取消</el-button>
              <el-button type="success" :icon="Check" :loading="savingHuman" @click="saveHumanEdit">
                💾 仅保存修改 (新版本，不调 AI)
              </el-button>
              <el-button type="primary" :icon="MagicStick" :loading="refining" @click="aiRefine">
                ⚡ AI 重新优化生成 知识库 v{{ currentVersion.version + 1 }}
              </el-button>
            </div>
          </div>
        </template>
      </section>
    </div>


    <!-- ═══ 创建知识库 Dialog ═══ -->
    <el-dialog
      v-model="createOpen"
      width="min(780px, 94vw)"
      :close-on-click-modal="false"
      :show-close="false"
      class="kb-create-dialog"
      align-center
    >
      <template #header>
        <div class="kb-dlg-hero">
          <div class="kb-dlg-hero-bg"></div>
          <div class="kb-dlg-hero-icon">
            <el-icon :size="22"><Files /></el-icon>
          </div>
          <div class="kb-dlg-hero-text">
            <div class="kb-dlg-hero-title">创建客户知识库</div>
            <div class="kb-dlg-hero-sub">上传基础资料 → AI 按 GEO 标准 10 模块（M01–M10）生成知识库</div>
          </div>
          <button class="kb-dlg-close" @click="createOpen = false" aria-label="关闭">
            <el-icon :size="18"><Close /></el-icon>
          </button>
        </div>
      </template>

      <el-form :model="createForm" label-width="92px" class="kb-create-form" @submit.prevent>
        <!-- 目标客户 -->
        <el-form-item label="目标客户" required>
          <div v-if="createLockAccount" class="kb-acct-locked">{{ pickedAccountLabel }}</div>
          <div v-else class="kb-field-row">
            <button type="button" class="kb-acct-picker" :class="{ empty: !createForm.accountId }"
                    @click="openAcctPicker">
              <template v-if="createForm.accountId">
                <span class="kb-acct-picker-name">{{ pickedAccountLabel }}</span>
                <el-icon class="kb-acct-picker-arrow"><ArrowDown /></el-icon>
              </template>
              <template v-else>
                <span class="kb-acct-picker-placeholder">点击选择客户</span>
                <el-icon class="kb-acct-picker-arrow"><ArrowDown /></el-icon>
              </template>
            </button>
            <el-button :icon="Plus" size="large" plain @click="newAccountOpen = true">新建客户</el-button>
          </div>
          <div class="kb-field-hint">
            <el-icon :size="12"><InfoFilled /></el-icon>
            显示初始客户与正式客户（付费客户）。初始客户可在此搭建知识库，搭好后点「转为正式」进入运营；报价客户不在此列。
          </div>
        </el-form-item>

        <!-- 基础资料：历史资料勾选 + 新上传 -->
        <el-form-item label="基础资料" required>
          <div class="kb-upload-card">

            <!-- 历史资料（已上传过的）-->
            <div v-if="createForm.accountId" class="kb-history-section">
              <div class="kb-history-head">
                <el-icon :size="13"><Files /></el-icon>
                <span>历史已上传资料
                  <strong v-if="historySources.length">{{ historySources.length }}</strong>
                  <span v-else class="kb-history-zero">（暂无）</span>
                </span>
                <el-button v-if="historySources.length" text type="primary" size="small"
                           @click="toggleAllHistory">
                  {{ allHistoryChecked ? '全部取消' : '全部勾选' }}
                </el-button>
              </div>
              <div v-if="loadingHistory" class="kb-history-empty">
                <el-icon class="is-loading" :size="14"><Loading /></el-icon> 加载中...
              </div>
              <div v-else-if="historySources.length" class="kb-history-grid">
                <label v-for="s in historySources" :key="s.id"
                       class="kb-history-item"
                       :class="{
                         checked: createForm.historySourceIds.includes(s.id),
                         disabled: s.parser_status !== 'done',
                       }">
                  <input type="checkbox"
                         :value="s.id"
                         v-model="createForm.historySourceIds"
                         :disabled="s.parser_status !== 'done'" />
                  <div class="kb-history-icon" :class="ftClass(s.file_name)">
                    <el-icon :size="14"><component :is="ftIcon(s.file_name)" /></el-icon>
                  </div>
                  <div class="kb-history-meta">
                    <div class="kb-history-name" :title="s.file_name">{{ s.file_name }}</div>
                    <div class="kb-history-sub">
                      <el-tag size="small" :type="srcStatusType(s.parser_status)" effect="light">
                        {{ srcStatusText(s.parser_status) }}
                      </el-tag>
                      <span class="kb-history-size">{{ formatSize(s.file_size) }}</span>
                    </div>
                  </div>
                </label>
              </div>
            </div>

            <!-- 新上传 -->
            <div class="kb-upload-divider" v-if="createForm.accountId && historySources.length">
              <span>或上传新资料</span>
            </div>

            <el-upload
              drag multiple
              class="kb-upload-zone-v2"
              :auto-upload="false"
              :show-file-list="false"
              :file-list="createForm.files"
              @change="onCreateUploadChange"
              @remove="onCreateUploadRemove"
            >
              <div class="kb-upload-inner">
                <div class="kb-upload-icon-wrap">
                  <el-icon :size="28"><UploadFilled /></el-icon>
                </div>
                <div class="kb-upload-main">
                  拖拽文件到此处，或<em>点击上传</em>
                </div>
                <div class="kb-upload-types">
                  <span class="ft-chip ft-pdf">PDF</span>
                  <span class="ft-chip ft-doc">Word</span>
                  <span class="ft-chip ft-xls">Excel</span>
                  <span class="ft-chip ft-img">图片</span>
                  <span class="ft-chip ft-txt">TXT</span>
                </div>
                <div class="kb-upload-foot">单文件 ≤ 30MB · 图片走通义千问 Qwen-VL 智能识别</div>
              </div>
            </el-upload>

            <transition name="kb-fade">
              <div v-if="createForm.files.length" class="kb-file-list">
                <div class="kb-file-list-head">
                  <span>新上传 <strong>{{ createForm.files.length }}</strong> 个文件</span>
                  <el-button text type="danger" size="small" @click="createForm.files = []">全部清空</el-button>
                </div>
                <div class="kb-file-grid">
                  <div v-for="f in createForm.files" :key="f.uid"
                       class="kb-file-card" :class="ftClass(f.name)">
                    <div class="kb-file-icon">
                      <el-icon :size="18"><component :is="ftIcon(f.name)" /></el-icon>
                    </div>
                    <div class="kb-file-meta">
                      <div class="kb-file-name" :title="f.name">{{ f.name }}</div>
                      <div class="kb-file-size">{{ formatSize(f.size) }}</div>
                    </div>
                    <button type="button" class="kb-file-rm" @click="onCreateUploadRemove(f)" aria-label="移除">
                      <el-icon :size="14"><Close /></el-icon>
                    </button>
                  </div>
                </div>
              </div>
            </transition>
          </div>
          <div v-if="createForm.accountId" class="kb-field-hint">
            <el-icon :size="12"><InfoFilled /></el-icon>
            历史资料 + 新上传 至少 1 份；勾选历史不需重复上传，节省时间
          </div>
        </el-form-item>

        <!-- 参考竞争分析报告（必填）-->
        <el-form-item label="参考报告" required>
          <div class="kb-ref-card">
            <div class="kb-ref-card-head">
              <el-icon :size="14"><DocumentCopy /></el-icon>
              <span>必选 1 份「竞争分析报告」作为 LLM 的高优先级 ground truth：报告里的 12 类资料清单会喂给 AI 生成知识库。<strong>从已有报告选 OR 上传新报告，至少一个</strong>（也可叠加两者）。</span>
            </div>

            <!-- 子项 1：从该客户已有报告选 -->
            <div class="kb-ref-row">
              <div class="kb-ref-row-label">从已有报告</div>
              <div class="kb-ref-row-body">
                <el-select v-model="createForm.refReportId" :loading="loadingReports"
                           placeholder="（不参考）或选该客户已完成的报告"
                           clearable
                           size="default" style="width:100%"
                           :disabled="!createForm.accountId">
                  <el-option v-for="r in brandReports" :key="r.id"
                             :label="`#${r.id} · ${r.period_start} ~ ${r.period_end}`"
                             :value="r.id">
                    <div class="kb-report-opt">
                      <span class="kb-report-id">#{{ r.id }}</span>
                      <span class="kb-report-date">{{ r.period_start }} ~ {{ r.period_end }}</span>
                      <el-tag v-if="r.has_checklist" size="small" type="success" effect="light">含 12 类清单</el-tag>
                      <el-tag v-else-if="r.has_html" size="small" type="warning" effect="light">需 HTML 解析</el-tag>
                      <el-tag v-else size="small" type="info" effect="light">无内容</el-tag>
                    </div>
                  </el-option>
                </el-select>
                <div v-if="createForm.accountId && !loadingReports && !brandReports.length"
                     class="kb-ref-empty">该客户暂无已完成报告</div>
              </div>
            </div>

            <!-- 子项 2：上传外部报告 -->
            <div class="kb-ref-row">
              <div class="kb-ref-row-label">上传报告</div>
              <div class="kb-ref-row-body">
                <div v-if="!createForm.refReportFile" class="kb-ref-upload">
                  <el-upload
                    drag
                    class="kb-ref-upload-zone"
                    :auto-upload="false"
                    :show-file-list="false"
                    accept=".html,.htm,.pdf,.docx"
                    :on-change="onRefReportFileChange"
                  >
                    <div class="kb-ref-upload-inner">
                      <el-icon :size="22"><DocumentCopy /></el-icon>
                      <div class="kb-ref-upload-main">
                        拖拽报告到此，或<em>点击选择</em>
                      </div>
                      <div class="kb-ref-upload-sub">
                        <span class="ft-chip ft-doc">HTML</span>
                        <span class="ft-chip ft-pdf">PDF</span>
                        <span class="ft-chip ft-doc">Word</span>
                      </div>
                    </div>
                  </el-upload>
                  <div class="kb-ref-upload-hint">
                    <el-icon :size="11"><InfoFilled /></el-icon>
                    PDF / Word 会走 LLM 抽取，HTML 直接结构化解析
                  </div>
                </div>
                <div v-else class="kb-ref-file">
                  <div class="kb-file-icon" :class="ftClass(createForm.refReportFile.name)">
                    <el-icon :size="16"><component :is="ftIcon(createForm.refReportFile.name)" /></el-icon>
                  </div>
                  <div class="kb-ref-file-meta">
                    <div class="kb-file-name" :title="createForm.refReportFile.name">{{ createForm.refReportFile.name }}</div>
                    <div class="kb-file-size">{{ formatSize(createForm.refReportFile.size) }}</div>
                  </div>
                  <button class="kb-file-rm" @click="createForm.refReportFile = null" aria-label="移除">
                    <el-icon :size="14"><Close /></el-icon>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </el-form-item>

        <!-- 补充说明 -->
        <el-form-item label="补充说明">
          <el-input v-model="createForm.instruction" type="textarea" :rows="3"
            placeholder="可留空。默认即按 GEO 10 模块标准模板生成。如需特殊强调，例：客户简称银联、重点突出适老化产品..." />
          <div class="kb-field-hint kb-hint-success">
            <el-icon :size="12"><Check /></el-icon>
            <strong>已内置 GEO 10 模块标准生成模板（M01–M10）</strong>
            ，留空直接生成；此处仅做客户特殊补充
          </div>
        </el-form-item>
      </el-form>

      <template #footer>
        <div class="kb-footer">
          <el-button size="large" @click="createOpen = false">取消</el-button>
          <div class="kb-footer-actions">
            <el-button size="large" type="success" plain :loading="creating" :disabled="!canCreate"
                       @click="onCreateOnlyUpload">仅上传资料</el-button>
            <el-button size="large" type="primary" :icon="MagicStick" :loading="creating" :disabled="!canCreate"
                       @click="onCreateAndGenerate" class="kb-btn-gen">上传并生成知识库</el-button>
          </div>
        </div>
      </template>
    </el-dialog>

    <!-- ═══ 新建客户 Dialog ═══ -->
    <el-dialog
      v-model="newAccountOpen"
      width="min(560px, 92vw)"
      :close-on-click-modal="false"
      :show-close="false"
      class="kb-create-dialog"
      align-center
    >
      <template #header>
        <div class="kb-dlg-hero kb-dlg-hero-blue">
          <div class="kb-dlg-hero-bg"></div>
          <div class="kb-dlg-hero-icon">
            <el-icon :size="22"><Plus /></el-icon>
          </div>
          <div class="kb-dlg-hero-text">
            <div class="kb-dlg-hero-title">新建客户</div>
            <div class="kb-dlg-hero-sub">新建为「初始客户」，搭好知识库后可转为正式客户</div>
          </div>
          <button class="kb-dlg-close" @click="newAccountOpen = false" aria-label="关闭">
            <el-icon :size="18"><Close /></el-icon>
          </button>
        </div>
      </template>

      <el-form :model="newAccountForm" label-width="92px" class="kb-create-form">
        <!-- 知识库新建客户 = 初始客户(status=draft)；搭好知识库后转正才进运营外层 -->
        <el-form-item label="公司全称" required>
          <el-input v-model="newAccountForm.companyName" size="large" placeholder="如：上海某某科技有限公司" />
        </el-form-item>
        <el-form-item label="品牌名" required>
          <el-select
            v-model="newAccountForm.companyBrands"
            multiple
            filterable
            allow-create
            default-first-option
            :reserve-keyword="false"
            size="large"
            style="width: 100%"
            placeholder="输入品牌名后回车添加，支持多个"
          />
          <div class="kb-field-hint">
            <el-icon :size="12"><InfoFilled /></el-icon>
            可添加多个品牌，每个回车确认；排名分析时会对每个品牌分别检测并取最高排名
          </div>
        </el-form-item>
        <el-form-item label="覆盖平台（选填）">
          <el-checkbox-group v-model="newAccountForm.platforms">
            <el-checkbox v-for="p in PLATFORM_OPTIONS" :key="p" :value="p">{{ p }}</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <div class="kb-field-hint" style="padding-left:92px">
          <el-icon :size="12"><InfoFilled /></el-icon>
          新建为「初始客户」：暂不进入查词/报告等运营功能，覆盖平台可先留空；搭好知识库后点「转为正式」补全平台+关键词即进入运营。
        </div>
      </el-form>
      <template #footer>
        <div class="kb-footer">
          <el-button size="large" @click="newAccountOpen = false">取消</el-button>
          <el-button size="large" type="primary" :loading="creatingAccount" @click="onCreateAccount" class="kb-btn-gen">
            创建并选中
          </el-button>
        </div>
      </template>
    </el-dialog>

    <!-- ═══ 目标客户选择 Dialog（支持搜索 + 列表点选） ═══ -->
    <el-dialog v-model="acctPickerOpen" title="选择正式客户" width="min(560px, 92vw)" :close-on-click-modal="true" append-to-body>
      <div class="acct-picker-body">
        <el-input
          v-model="acctPickerSearch"
          placeholder="搜索公司名 / 品牌名"
          clearable
          size="large"
          :prefix-icon="Search"
          ref="acctPickerSearchRef"
          class="acct-picker-search"
        />
        <div class="acct-picker-count">
          匹配 {{ filteredPickerAccounts.length }} / {{ accounts.length }} 个客户
        </div>
        <div class="acct-picker-list">
          <button v-for="a in filteredPickerAccounts" :key="a.id"
                  type="button" class="acct-picker-row"
                  :class="{ active: createForm.accountId === a.id }"
                  @click="pickAcct(a)">
            <div class="acct-picker-row-main">
              <span class="acct-picker-row-name">{{ a.companyName }}</span>
              <span v-if="a.companyBrand" class="acct-picker-row-brand">{{ brandLabel(a.companyBrand) }}</span>
            </div>
            <el-icon v-if="createForm.accountId === a.id" class="acct-picker-row-check"><Check /></el-icon>
          </button>
          <div v-if="!filteredPickerAccounts.length" class="acct-picker-empty">
            <span v-if="acctPickerSearch">未找到匹配「{{ acctPickerSearch }}」的客户</span>
            <span v-else>暂无正式客户，点右上角「新建客户」创建</span>
          </div>
        </div>
      </div>
    </el-dialog>

    <!-- ═══ 资料文本预览 Dialog ═══ -->
    <el-dialog v-model="srcViewOpen" :title="srcViewRow?.file_name || '资料文本'" width="min(900px, 95vw)">
      <div v-if="srcViewRow">
        <div class="src-meta-bar">
          <el-tag size="small" :type="srcStatusType(srcViewRow.parser_status)">{{ srcStatusText(srcViewRow.parser_status) }}</el-tag>
          <span v-if="srcViewRow.parser_error" class="src-err">⚠ {{ srcViewRow.parser_error }}</span>
        </div>
        <el-tabs v-model="srcViewTab" class="src-view-tabs">
          <el-tab-pane label="解析文本" name="text">
            <pre class="src-text">{{ srcViewRow.parsed_text || '（暂无解析文本）' }}</pre>
          </el-tab-pane>
          <el-tab-pane label="Markdown 预览" name="md">
            <div class="src-md-preview" v-html="renderMarkdown(srcViewRow.parsed_text || '')"></div>
          </el-tab-pane>
        </el-tabs>
      </div>
    </el-dialog>

    <KBReviewDrawer v-model="reviewOpen" :account-id="currentAccountId" :kb-version-id="currentVersion?.id" />
    <PromoteAccountDialog v-model="promoteOpen" :account="currentAccount" @promoted="onAccountPromoted" />

    <!-- 任务进度 widget 已提到 PublishHubLayout 全局，这里不再渲染 -->

    <!-- Excel 手动上传知识库 -->
    <KbExcelImportDialog v-model="excelImportOpen" :default-account-id="currentAccountId"
                         :client-name="currentAccount?.companyName || currentAccount?.company_name || ''" @done="onExcelImported" />

    <!-- AI 扩充模块 -->
    <KbExpandDialog v-model="aiExpandOpen" :prev-kb-id="currentVersion?.id" :account-id="currentAccountId" @done="onExcelImported" />

    <!-- 添加单个模块 -->
    <el-dialog v-model="addModuleOpen" title="添加知识库模块" width="min(640px, 94vw)" :close-on-click-modal="false">
      <el-form label-width="84px">
        <el-form-item label="模块编号"><el-input v-model="addModuleForm.module" placeholder="如 M11（可留空）" style="width:200px" /></el-form-item>
        <el-form-item label="标题" required><el-input v-model="addModuleForm.title" placeholder="模块标题，如 售后服务体系" /></el-form-item>
        <el-form-item label="知识库内容" required>
          <el-input v-model="addModuleForm.content" type="textarea" :autosize="{minRows:5,maxRows:14}" placeholder="该模块的知识库内容（支持 markdown）" />
        </el-form-item>
        <div class="kb-addmod-tip">将追加到当前 v{{ currentVersion?.version }} 之后，生成新版本（旧版保留可回滚）。</div>
      </el-form>
      <template #footer>
        <el-button @click="addModuleOpen = false">取消</el-button>
        <el-button type="primary" :icon="Check" :loading="savingAddModule"
                   :disabled="!addModuleForm.title.trim() || !addModuleForm.content.trim()" @click="submitAddModule">追加为新版本</el-button>
      </template>
    </el-dialog>

    <!-- 规则库校对结果 -->
    <el-dialog v-model="proofreadOpen" title="知识库 × 规则库 校对" width="min(760px, 94vw)" append-to-body>
      <div v-if="proofreading" class="pf-loading">
        <el-icon class="is-loading" :size="22"><Loading /></el-icon>
        <span>正在用最新规则库校对当前知识库…</span>
      </div>
      <template v-else-if="proofreadResult">
        <div class="pf-summary" :class="{ clean: proofreadResult.conflict_count === 0 }">
          <el-icon :size="18"><component :is="proofreadResult.conflict_count ? Warning : Check" /></el-icon>
          <span>{{ proofreadResult.summary }}</span>
        </div>
        <div v-if="!proofreadResult.rules_count" class="pf-empty">
          该客户还没有规则库,请先在「智能生文 · 写作规则库」里录入规则。
        </div>
        <div v-else-if="proofreadConflicts.length" class="pf-list">
          <div v-for="(f, i) in proofreadConflicts" :key="i" class="pf-item">
            <div class="pf-item-head">
              <span class="pf-badge">冲突</span>
              <span class="pf-rule">规则 {{ f.rule_index || '?' }}：{{ f.rule }}</span>
            </div>
            <div v-if="f.evidence" class="pf-evidence"><span class="pf-k">知识库原句</span>{{ f.evidence }}</div>
            <div v-if="f.suggestion" class="pf-suggestion"><span class="pf-k">修改建议</span>{{ f.suggestion }}</div>
          </div>
        </div>
        <div v-else class="pf-clean-box">
          ✓ 当前知识库与全部 {{ proofreadResult.rules_count }} 条规则一致,未发现冲突。
        </div>
      </template>
      <template #footer>
        <el-button @click="proofreadOpen = false">关闭</el-button>
        <el-button type="primary" :icon="Refresh" :loading="proofreading" @click="runProofread">重新校对</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Plus, EditPen, Check, MagicStick, UploadFilled, Loading,
  Document, Picture, Files, DataAnalysis, InfoFilled, Close,
  DocumentCopy, Warning, Connection, Refresh, User,
  ArrowDown, ArrowUp, ArrowLeft, ArrowRight, Download, Search,
} from '@element-plus/icons-vue'
import { useRoute } from 'vue-router'
import publishApi from '../api/publish'
import kbApi from '@/api/knowledge'
import api from '../api'
import KBReviewDrawer from './kb/KBReviewDrawer.vue'
import PromoteAccountDialog from '@/components/common/PromoteAccountDialog.vue'
import KbExcelImportDialog from '@/components/KbExcelImportDialog.vue'
import KbExpandDialog from '@/components/KbExpandDialog.vue'
import { brandsToStorage, brandsDisplay } from '@/utils/brands.js'

const route = useRoute()

const PLATFORM_OPTIONS = ['豆包', 'DeepSeek', '元宝', '文心一言', '通义千问', 'Kimi', '纳米']

// ── 状态 ──
const accounts = ref([])
const currentAccountId = ref(null)
const excelImportOpen = ref(false)
async function onExcelImported({ accountId } = {}) {
  await loadCustomerOverview()
  if (accountId && currentAccountId.value === accountId) await onAccountChange()
}

// 添加单个模块 → 追加到当前版本,存为新版本
const aiExpandOpen = ref(false)
const addModuleOpen = ref(false)
const savingAddModule = ref(false)
const addModuleForm = reactive({ module: '', title: '', content: '' })
function openAddModule() {
  addModuleForm.module = ''; addModuleForm.title = ''; addModuleForm.content = ''
  addModuleOpen.value = true
}
async function submitAddModule() {
  if (!addModuleForm.title.trim() || !addModuleForm.content.trim()) return
  const m = addModuleForm.module.trim()
  const head = m ? `## 【${m}】${addModuleForm.title.trim()}` : `## ${addModuleForm.title.trim()}`
  const section = `${head}\n\n${addModuleForm.content.trim()}`
  savingAddModule.value = true
  try {
    if (currentVersion.value) {
      const combined = (currentVersion.value.content || '').replace(/\s+$/, '') + '\n\n' + section
      await publishApi.kbSaveHuman(currentVersion.value.id, combined, '添加模块：' + addModuleForm.title.trim())
    } else {
      await publishApi.kbImportHuman(currentAccountId.value, section, '添加模块：' + addModuleForm.title.trim())
    }
    ElMessage.success('已追加为新版本')
    addModuleOpen.value = false
    await onAccountChange()
  } catch (e) {
    ElMessage.error('添加失败：' + (e.response?.data?.error || e.message))
  } finally { savingAddModule.value = false }
}
const switchAccountOpen = ref(false)
const customerOverview = ref([])
const loadingOverview = ref(false)
const overviewSearch = ref('')
const kbBuiltCount = computed(() => customerOverview.value.filter(c => c.kb_count).length)
// 客户头像字母章：取品牌/公司首字符 + 稳定配色
const _AVATAR_COLORS = [
  'linear-gradient(135deg,#6366f1,#8b5cf6)', 'linear-gradient(135deg,#0ea5e9,#2563eb)',
  'linear-gradient(135deg,#10b981,#14b8a6)', 'linear-gradient(135deg,#f59e0b,#f97316)',
  'linear-gradient(135deg,#ec4899,#db2777)', 'linear-gradient(135deg,#8b5cf6,#6d28d9)',
  'linear-gradient(135deg,#14b8a6,#0891b2)',
]
function avatarText(row) {
  const s = String(brandLabel(row.company_brand) || row.company_name || '?').trim()
  return s ? s[0] : '?'
}
function avatarColor(row) {
  const s = String(brandLabel(row.company_brand) || row.company_name || '')
  let h = 0
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0
  return _AVATAR_COLORS[h % _AVATAR_COLORS.length]
}
const filteredOverview = computed(() => {
  const q = (overviewSearch.value || '').trim().toLowerCase()
  const filtered = q
    ? customerOverview.value.filter(c => {
        const name = String(c.company_name || '').toLowerCase()
        const brand = String(brandLabel(c.company_brand) || '').toLowerCase()
        return name.includes(q) || brand.includes(q)
      })
    : customerOverview.value
  return [...filtered].sort((a, b) => {
    const ta = a.current_created_at || a.latest_kb_at || a.updated_at || ''
    const tb = b.current_created_at || b.latest_kb_at || b.updated_at || ''
    return tb.localeCompare(ta)
  })
})
const currentAccountLabel = computed(() => {
  const a = accounts.value.find(x => x.id === currentAccountId.value)
  if (!a) return ''
  // 与导出文档命名一致：「品牌 · 知识库」（无品牌时回落公司名）
  const primary = brandLabel(a.companyBrand) || a.companyName
  return primary + ' · 知识库'
})
const currentVersion = ref(null)

// ── 规则库校对 ──
const proofreadOpen = ref(false)
const proofreading = ref(false)
const proofreadResult = ref(null)
const proofreadConflicts = computed(() =>
  (proofreadResult.value?.findings || []).filter(f => f.verdict === 'conflict'))
function openProofread() {
  if (!currentVersion.value) { ElMessage.warning('当前还没有知识库版本'); return }
  proofreadOpen.value = true
  runProofread()
}
async function runProofread() {
  if (!currentVersion.value) return
  proofreading.value = true
  try {
    proofreadResult.value = await publishApi.kbProofread(currentVersion.value.id)
  } catch (e) {
    proofreadResult.value = null
    ElMessage.error('校对失败：' + (e?.response?.data?.error || e?.message || '未知错误'))
  } finally {
    proofreading.value = false
  }
}
const reviewOpen = ref(false)
const promoteOpen = ref(false)
const currentAccount = computed(() => accounts.value.find(a => a.id === currentAccountId.value) || null)
// 分模块翻页：把 currentVersion.modules（后端返）作为唯一来源；切版本时归 0
const kbModules = computed(() => currentVersion.value?.modules || [])
const currentModuleIdx = ref(0)
const currentModule = computed(() => kbModules.value[currentModuleIdx.value] || null)
watch(() => currentVersion.value?.id, () => { currentModuleIdx.value = 0 })
const versions = ref([])
const baseSources = ref([])

// 编辑模式
const editing = ref(false)
const editContent = ref('')
const editInstruction = ref('')
const addUploadFiles = ref([])
const savingHuman = ref(false)
const refining = ref(false)

// 创建知识库 dialog
const createOpen = ref(false)
const createLockAccount = ref(false)
const creating = ref(false)
const createForm = reactive({
  accountId: null,
  files: [],
  historySourceIds: [],  // 勾选的历史资料 source_id
  instruction: '',
  refReportId: null,
  refReportFile: null,
})
const brandReports = ref([])
const loadingReports = ref(false)
const historySources = ref([])
const loadingHistory = ref(false)
const allHistoryChecked = computed(() => {
  const ok = historySources.value.filter(s => s.parser_status === 'done')
  return ok.length > 0 && ok.every(s => createForm.historySourceIds.includes(s.id))
})
// 必填：客户 + 至少 1 份素材（历史 OR 新上传）+ 至少 1 个参考报告
const canCreate = computed(() =>
  !!createForm.accountId
  && (createForm.historySourceIds.length > 0 || createForm.files.length > 0)
  && (!!createForm.refReportId || !!createForm.refReportFile)
)

// 新建客户 dialog
const newAccountOpen = ref(false)

// 目标客户选择弹窗：客户多时下拉难选 → 改成弹窗+搜索+点选
const acctPickerOpen = ref(false)
const acctPickerSearch = ref('')
const acctPickerSearchRef = ref(null)
const filteredPickerAccounts = computed(() => {
  const q = acctPickerSearch.value.trim().toLowerCase()
  if (!q) return accounts.value
  return accounts.value.filter(a => {
    const name = String(a.companyName || '').toLowerCase()
    const brand = String(a.companyBrand || '').toLowerCase()
    return name.includes(q) || brand.includes(q)
  })
})
const pickedAccountLabel = computed(() => {
  const a = accounts.value.find(x => x.id === createForm.accountId)
  if (!a) return ''
  return `${a.companyName}${a.companyBrand ? ' · ' + brandLabel(a.companyBrand) : ''}`
})
function openAcctPicker() {
  acctPickerOpen.value = true
  acctPickerSearch.value = ''
  // 弹出后自动聚焦搜索框
  setTimeout(() => { try { acctPickerSearchRef.value?.focus?.() } catch {} }, 80)
}
function pickAcct(a) {
  createForm.accountId = a.id
  acctPickerOpen.value = false
  try { onCreateAccountChange() } catch {}
}
const creatingAccount = ref(false)
const newAccountForm = reactive({
  companyName: '', companyBrands: [],
  userType: 'paid', platforms: [],
})

// 资料预览
const srcViewOpen = ref(false)
const srcViewRow = ref(null)
const srcViewTab = ref('text')

// AI 生成进度
// 任务进度 widget 已上提到 PublishHubLayout 全局；KB page 不再持有相关 state

// ── helpers ──
function brandLabel(b) {
  // 复用主系统的 parseBrands 逻辑：JSON 数组 / 单字符串 / 数组 都正确解析为 "极核 / 春风"
  return brandsDisplay(b, ' / ')
}
function srcIcon(t) {
  if (t === 'image') return Picture
  if (t === 'xlsx' || t === 'xls') return DataAnalysis
  if (t === 'docx' || t === 'doc') return Document
  return Files
}
function srcStatusText(s) {
  return { pending: '待解析', parsing: '解析中', done: '已解析', failed: '失败' }[s] || s
}
function srcStatusType(s) {
  return { pending: 'info', parsing: 'warning', done: 'success', failed: 'danger' }[s] || ''
}
function formatSize(n) {
  n = Number(n) || 0
  if (n < 1024) return n + 'B'
  if (n < 1024 * 1024) return (n / 1024).toFixed(1) + 'KB'
  return (n / 1024 / 1024).toFixed(1) + 'MB'
}
function _ext(name) {
  const m = String(name || '').toLowerCase().match(/\.([a-z0-9]+)$/)
  return m ? m[1] : ''
}
function ftClass(name) {
  const e = _ext(name)
  if (e === 'pdf') return 'ft-pdf'
  if (['doc', 'docx'].includes(e)) return 'ft-doc'
  if (['xls', 'xlsx', 'csv'].includes(e)) return 'ft-xls'
  if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp'].includes(e)) return 'ft-img'
  return 'ft-txt'
}
function ftIcon(name) {
  const e = _ext(name)
  if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp'].includes(e)) return Picture
  return Document
}
function truncate(s, n) {
  s = String(s || '')
  return s.length > n ? s.slice(0, n) + '...' : s
}
function renderMarkdown(md) {
  // 极简 markdown 渲染（不引入额外库）
  if (!md) return ''
  let raw = String(md).replace(/^﻿/, '')
  // 剥离 LLM 偶发的 YAML/TOML frontmatter 头(--- ... --- 包裹的元数据块)
  raw = raw.replace(/^\s*---\s*\n[\s\S]*?\n---\s*(?:\n|$)/, '')
  // 剥离整段被 ```markdown ... ``` 包裹的情况
  raw = raw.replace(/^\s*```(?:markdown|md)?\s*\n([\s\S]*?)\n```\s*$/, '$1')
  // 去掉文首残余的孤立分隔线(单独一行 3+ 个 -/*/_),避免开头突兀的 ---
  raw = raw.replace(/^(?:\s*[-*_]{3,}\s*\n)+/, '')
  let html = raw
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    // ⚠ 待客户确认 高亮
    .replace(/^&gt; ⚠️ \*\*待客户确认[-—](.+?)\*\*：(.+)$/gm,
      '<div class="kb-warn"><span class="kb-warn-tag">⚠ 待客户确认-$1</span> $2</div>')
    // 标题
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    // 引用
    .replace(/^&gt; (.+)$/gm, '<blockquote>$1</blockquote>')
    // 加粗
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    // 水平分隔符:孤立一行的 ---/***/___ 转 <hr>
    .replace(/^[-*_]{3,}\s*$/gm, '<hr class="kb-hr">')
    // 表格（简单版：连续 | 行）
    .replace(/(?:^\|.+\|$\n?)+/gm, m => {
      const lines = m.trim().split('\n').filter(l => l.trim())
      const rows = lines.map(l => l.replace(/^\||\|$/g, '').split('|').map(c => c.trim()))
      if (rows.length < 2) return m
      const sepRow = rows[1].every(c => /^:?-+:?$/.test(c))
      const head = sepRow ? rows[0] : null
      const body = sepRow ? rows.slice(2) : rows
      let h = '<table class="kb-table">'
      if (head) h += '<thead><tr>' + head.map(c => `<th>${c}</th>`).join('') + '</tr></thead>'
      h += '<tbody>' + body.map(r => '<tr>' + r.map(c => `<td>${c}</td>`).join('') + '</tr>').join('') + '</tbody>'
      h += '</table>'
      return h
    })
    // 段落
    .split(/\n\s*\n/).map(p => p.trim()).filter(Boolean)
    .map(p => /<(h[123]|blockquote|table|div|hr)/.test(p) ? p : `<p>${p.replace(/\n/g, '<br>')}</p>`)
    .join('\n')
  return html
}

// ── 数据加载 ──
async function loadAccounts() {
  // 只显示正式客户（user_type=paid）：知识库/内容发布仅限正式客户使用。
  // 走专用 /api/kb/accounts（后端 list_paid_accounts），避免下拉里出现报价客户
  // 被点选后才报错。后端 _assert_paid_account 是兜底校验。
  try {
    const r = await kbApi.listPaidAccounts()
    accounts.value = (r && r.accounts) || []
  } catch (e) {
    ElMessage.error('加载客户失败')
    accounts.value = []
  }
}

async function loadCurrent(accountId) {
  try {
    const r = await publishApi.kbCurrent(accountId)
    currentVersion.value = r?.item || null
  } catch { currentVersion.value = null }
}

async function loadVersions(accountId) {
  try {
    const r = await publishApi.kbListVersions(accountId)
    versions.value = r?.items || []
  } catch { versions.value = [] }
}

async function loadSources(accountId) {
  try {
    const r = await publishApi.kbListSources(accountId, null)
    baseSources.value = (r?.items || []).filter(s => !s.kb_version_id)
  } catch { baseSources.value = [] }
}

async function onAccountChange() {
  if (!currentAccountId.value) return
  await Promise.all([
    loadCurrent(currentAccountId.value),
    loadVersions(currentAccountId.value),
    loadSources(currentAccountId.value),
  ])
}

async function loadCustomerOverview() {
  loadingOverview.value = true
  try {
    const r = await publishApi.kbCustomerOverview()
    customerOverview.value = r.items || []
  } catch (e) {
    ElMessage.warning('加载客户摘要失败：' + (e.message || e))
    customerOverview.value = []
  } finally {
    loadingOverview.value = false
  }
}

async function openSwitchAccount() {
  switchAccountOpen.value = true
  overviewSearch.value = ''
  await loadCustomerOverview()
}

// 工具栏下拉选客户：v-model 已更新 currentAccountId，这里加载该客户知识库
// 返回客户列表（清空选中 + 刷新摘要，可能刚建了新 KB）
function backToList() {
  currentAccountId.value = null
  currentVersion.value = null
  versions.value = []
  baseSources.value = []
  loadCustomerOverview()
}

async function onPickCustomer(c) {
  switchAccountOpen.value = false
  if (!c.kb_count) {
    // 没 KB → 切换到该客户,展示空态(让用户自己点「创建知识库 / Excel 导入」),不自动弹窗
    currentAccountId.value = c.account_id
    await onAccountChange()
    return
  }
  if (c.account_id === currentAccountId.value) return
  currentAccountId.value = c.account_id
  await onAccountChange()
}

async function loadVersion(kbId) {
  try {
    const v = await publishApi.kbGetVersion(kbId)
    currentVersion.value = v
  } catch { ElMessage.error('加载版本失败') }
}

// ── 版本操作 ──
async function setCurrent(kbId) {
  try {
    await publishApi.kbSetCurrent(kbId)
    await onAccountChange()
    ElMessage.success('已设为当前版本')
  } catch { ElMessage.error('设置失败') }
}

async function delVersion(kbId) {
  try {
    await ElMessageBox.confirm('确认删除此版本？', '提示', { type: 'warning' })
    await publishApi.kbDeleteVersion(kbId)
    await onAccountChange()
    ElMessage.success('已删除')
  } catch (_) {}
}

// ── 资料操作 ──
async function viewSource(s) {
  try {
    const row = await publishApi.kbSourceText(s.id)
    srcViewRow.value = row
    srcViewTab.value = 'text'
    srcViewOpen.value = true
  } catch { ElMessage.error('加载文本失败') }
}

async function delSource(id) {
  try {
    await ElMessageBox.confirm('确认删除此资料？(已生成的知识库不受影响)', '提示', { type: 'warning' })
    await publishApi.kbDeleteSource(id)
    await loadSources(currentAccountId.value)
    ElMessage.success('已删除')
  } catch (_) {}
}

// ── 编辑模式 ──
function enterEdit() {
  if (!currentVersion.value) return
  editContent.value = currentVersion.value.content || ''
  editInstruction.value = ''
  addUploadFiles.value = []
  editing.value = true
}

// 导出 PDF / DOCX：直接 window.open 触发 cookie-auth 下载
function exportKb(fmt) {
  if (!currentVersion.value) return
  const id = currentVersion.value.id
  if (fmt === 'pdf') {
    window.open(`/api/kb/version/${id}/export.pdf`, '_blank')
  } else if (fmt === 'docx') {
    window.open(`/api/kb/version/${id}/export.docx`, '_blank')
  }
}
function cancelEdit() {
  editing.value = false
  addUploadFiles.value = []
}

function onAddUploadChange(file) {
  addUploadFiles.value.push(file)
}
function onAddUploadRemove(file) {
  addUploadFiles.value = addUploadFiles.value.filter(f => f.uid !== file.uid)
}

async function _uploadAdditionalIfAny() {
  // 把补充资料先上传，关联到 prev kb_version_id，返回 ids
  const files = addUploadFiles.value.map(x => x.raw).filter(Boolean)
  if (!files.length) return []
  try {
    const r = await publishApi.kbUploadSources(
      currentAccountId.value, files, currentVersion.value?.id || null)
    return (r.saved || []).map(x => x.id)
  } catch (e) {
    ElMessage.error('补充资料上传失败：' + (e.message || e))
    throw e
  }
}

async function saveHumanEdit() {
  if (!editContent.value.trim()) {
    ElMessage.warning('内容不能为空')
    return
  }
  savingHuman.value = true
  try {
    const r = await publishApi.kbSaveHuman(currentVersion.value.id, editContent.value, editInstruction.value)
    ElMessage.success(`已保存为 v${r.version}（人工版本）`)
    editing.value = false
    await onAccountChange()
  } catch (e) {
    ElMessage.error('保存失败：' + (e.message || e))
  } finally {
    savingHuman.value = false
  }
}

async function aiRefine() {
  if (!editInstruction.value.trim()) {
    ElMessage.warning('请输入「新要求」')
    return
  }
  refining.value = true
  try {
    const additionalIds = await _uploadAdditionalIfAny()
    const r = await publishApi.kbRefine(currentVersion.value.id, editInstruction.value, editContent.value, additionalIds)
    if (!r.task_id) throw new Error('未拿到 task_id')
    // 通知全局 widget 启动轮询；自己关编辑面板
    window.dispatchEvent(new CustomEvent('kb-task-start', {
      detail: {
        phase: 'llm', taskId: r.task_id, accountId: currentAccountId.value,
        hint: 'AI 正在优化知识库...',
        text: '正在分析当前内容 + 补充资料 + 新要求...',
      },
    }))
    editing.value = false
    ElMessage.info('AI 优化任务已提交，可继续做其它事，完成后右下角自动通知')
  } catch (e) {
    ElMessage.error('优化失败：' + (e.message || e))
  } finally {
    refining.value = false
  }
}

// ── 创建知识库 ──
function openCreateDialog() {
  createForm.accountId = currentAccountId.value
  createLockAccount.value = !!currentAccountId.value
  createForm.files = []
  createForm.historySourceIds = []
  createForm.instruction = ''
  createForm.refReportId = null
  createForm.refReportFile = null
  brandReports.value = []
  historySources.value = []
  createOpen.value = true
  if (createForm.accountId) {
    loadBrandReports()
    loadHistorySources()
  }
}

function onCreateAccountChange() {
  createForm.refReportId = null
  createForm.historySourceIds = []
  brandReports.value = []
  historySources.value = []
  loadBrandReports()
  loadHistorySources()
}

async function loadHistorySources() {
  if (!createForm.accountId) return
  loadingHistory.value = true
  try {
    const r = await publishApi.kbListSources(createForm.accountId, null)
    historySources.value = (r.items || []).filter(s => s.text_len > 0 || s.parser_status === 'done')
    // 默认全部勾上已解析的
    createForm.historySourceIds = historySources.value
      .filter(s => s.parser_status === 'done')
      .map(s => s.id)
  } catch (e) {
    historySources.value = []
  } finally {
    loadingHistory.value = false
  }
}

function toggleAllHistory() {
  const okIds = historySources.value
    .filter(s => s.parser_status === 'done')
    .map(s => s.id)
  if (allHistoryChecked.value) {
    createForm.historySourceIds = []
  } else {
    createForm.historySourceIds = okIds
  }
}

async function loadBrandReports() {
  if (!createForm.accountId) return
  loadingReports.value = true
  try {
    const r = await publishApi.kbListBrandReports(createForm.accountId)
    brandReports.value = r.items || []
  } catch (e) {
    ElMessage.warning('拉取报告列表失败：' + (e.message || e))
    brandReports.value = []
  } finally {
    loadingReports.value = false
  }
}

function onCreateUploadChange(file) {
  createForm.files.push(file)
}
function onCreateUploadRemove(file) {
  createForm.files = createForm.files.filter(f => f.uid !== file.uid)
}

function onRefReportFileChange(file) {
  createForm.refReportFile = file
}

async function onCreateOnlyUpload() {
  if (!canCreate.value) return
  creating.value = true
  try {
    const files = createForm.files.map(x => x.raw).filter(Boolean)
    await publishApi.kbUploadSources(createForm.accountId, files, null)
    ElMessage.success(`已上传 ${files.length} 份资料，正在后台解析...`)
    createOpen.value = false
    currentAccountId.value = createForm.accountId
    await onAccountChange()
  } catch (e) {
    ElMessage.error('上传失败：' + (e.message || e))
  } finally {
    creating.value = false
  }
}

async function onCreateAndGenerate() {
  if (!canCreate.value) return
  createOpen.value = false
  currentAccountId.value = createForm.accountId

  const acctId = createForm.accountId
  const instruction = createForm.instruction
  const refReportId = createForm.refReportId
  const refReportFile = createForm.refReportFile
  const newFiles = createForm.files.map(x => x.raw).filter(Boolean)
  const historyIds = [...createForm.historySourceIds]

  let allSourceIds = [...historyIds]

  try {
    // 1. 如果有新文件要上传 → 走上传流程，否则直接跳到 LLM 阶段
    if (newFiles.length) {
      window.dispatchEvent(new CustomEvent('kb-task-start', {
        detail: {
          phase: 'upload', percent: 0, accountId: acctId,
          hint: `上传 ${newFiles.length} 份新素材中 0%`,
          text: `准备上传 ${newFiles.length} 份新素材...`,
        },
      }))
      const upR = await publishApi.kbUploadSources(acctId, newFiles, null, (pct) => {
        window.dispatchEvent(new CustomEvent('kb-task-progress', {
          detail: { phase: 'upload', percent: pct, hint: `上传素材中 ${pct}%` },
        }))
      })
      const newIds = (upR.saved || []).map(x => x.id)
      if (!newIds.length) throw new Error('新素材上传失败')
      allSourceIds = allSourceIds.concat(newIds)
    } else {
      // 仅用历史资料 → 直接弹 LLM 阶段 widget（无上传，秒速进入）
      window.dispatchEvent(new CustomEvent('kb-task-start', {
        detail: {
          phase: 'llm', accountId: acctId,
          hint: 'AI 正在生成知识库...',
          text: `复用 ${historyIds.length} 份历史资料，提交生成中...`,
        },
      }))
    }

    // 2. 提交生成
    const genR = await publishApi.kbGenerate(
      acctId, instruction, allSourceIds,
      { refBrandReportId: refReportId, refReportFile: refReportFile },
    )
    if (!genR.task_id) throw new Error('未拿到 task_id')

    // 3. 切到 LLM 阶段（带 taskId 启动轮询）
    window.dispatchEvent(new CustomEvent('kb-task-start', {
      detail: {
        phase: 'llm', taskId: genR.task_id, accountId: acctId,
        hint: 'AI 正在生成知识库...',
        text: `素材 ${allSourceIds.length} 份（历史 ${historyIds.length} + 新 ${newFiles.length}） + 参考报告 已提交`,
      },
    }))
  } catch (e) {
    const msg = e.response?.data?.error || e.message || String(e)
    ElMessage.error('生成失败：' + msg)
    window.dispatchEvent(new CustomEvent('kb-task-failed', { detail: { error: msg } }))
  }
}

// ── 新建客户 ──
async function onCreateAccount() {
  if (!newAccountForm.companyName.trim() || !(newAccountForm.companyBrands || []).length) {
    ElMessage.warning('公司名和品牌必填')
    return
  }
  creatingAccount.value = true
  try {
    const a = await api.createAccount({
      companyName: newAccountForm.companyName.trim(),
      companyBrand: brandsToStorage(newAccountForm.companyBrands),
      userType: newAccountForm.userType,
      platforms: newAccountForm.platforms,
      status: 'draft',  // 知识库新建即「初始客户」,配好平台+关键词转正才进运营外层
    })
    ElMessage.success(`已创建客户：${a.companyName}`)
    await loadAccounts()
    createForm.accountId = a.id
    newAccountOpen.value = false
    // 重置
    Object.assign(newAccountForm, {
      companyName: '', companyBrands: [], userType: 'paid', platforms: [],
    })
  } catch (e) {
    ElMessage.error('创建失败：' + (e.response?.data?.error || e.message))
  } finally {
    creatingAccount.value = false
  }
}

function onAccountPromoted() {
  loadAccounts()
}

// 任务轮询、widget、localStorage 恢复 全部移交 PublishHubLayout 全局
// KB page 只需要监听 kb-task-done 事件刷新数据
function onKbTaskDone(ev) {
  const { accountId } = ev.detail || {}
  // 当前正在看的客户与刚完成任务的客户匹配 → 刷新当前数据
  if (accountId && accountId === currentAccountId.value) {
    onAccountChange()
  } else if (accountId) {
    // 切到该客户
    currentAccountId.value = accountId
    onAccountChange()
  }
}

// ── 生命周期 ──
onMounted(async () => {
  await Promise.all([loadAccounts(), loadCustomerOverview()])
  // 从「客户管理」深链进入：?account=<id> 直达该客户知识库
  const qa = Number(route.query.account)
  if (qa && accounts.value.some(a => a.id === qa)) {
    currentAccountId.value = qa
    await onAccountChange()
  }
  window.addEventListener('kb-task-done', onKbTaskDone)
})
onBeforeUnmount(() => {
  window.removeEventListener('kb-task-done', onKbTaskDone)
})
</script>

<style scoped>
.kb-page {
  display: flex; flex-direction: column; gap: 12px;
  flex: 1; min-height: 0;
}
.toolbar {
  background: #fff; border-radius: 12px;
  padding: 12px 16px; display: flex; justify-content: space-between; align-items: center;
  box-shadow: 0 1px 3px rgba(0,0,0,.04);
  flex-wrap: wrap; gap: 12px;
}
.tb-left { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }
.tb-right { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.tb-title {
  font-size: 16px; font-weight: 700; color: #0f172a;
  letter-spacing: -0.2px;
}
.tb-current-acct {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 4px 10px;
  background: #eef2ff; border-radius: 999px;
  font-size: 12.5px; color: #4338ca; font-weight: 500;
}
.tb-current-acct .el-icon { color: #6366f1; }
.tb-current { color: #475569; font-size: 12.5px; margin-left: 4px; }
.tb-time { color: #94a3b8; margin-left: 6px; font-size: 12px; }

/* 工具栏客户下拉 */
.kb-acct-select { width: 320px; }
.kb-opt { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.kb-opt-name { color: #0f172a; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.kb-opt-badge { flex-shrink: 0; font-size: 11px; color: #4338ca; background: #eef2ff; border-radius: 999px; padding: 1px 9px; font-weight: 600; }
.kb-opt-badge.empty { color: #94a3b8; background: #f1f5f9; font-weight: 500; }

/* 未选客户轻量空态 */
.kb-empty-hint {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 8px; padding: 80px 20px; color: #94a3b8; text-align: center;
}
.kb-empty-hint .el-icon { color: #cbd5e1; }
.kb-empty-hint-t { font-size: 15px; color: #475569; font-weight: 600; margin-top: 4px; }
.kb-empty-hint-s { font-size: 13px; color: #94a3b8; }

/* ===== Landing 空状态 ===== */
.kb-landing {
  display: flex; align-items: center; justify-content: center;
  min-height: calc(100vh - 220px);
}
.kb-landing-card {
  max-width: 520px; width: 100%;
  text-align: center;
  padding: 48px 36px;
  background: #fff;
  border-radius: 20px;
  box-shadow:
    0 24px 64px -12px rgba(15, 23, 42, .1),
    0 0 0 1px rgba(15, 23, 42, .04);
  position: relative; overflow: hidden;
}
.kb-landing-card::before {
  content: ''; position: absolute; inset: 0;
  background-image:
    radial-gradient(circle at 90% 0%, rgba(139, 92, 246, .1) 0%, transparent 40%),
    radial-gradient(circle at 0% 100%, rgba(99, 102, 241, .08) 0%, transparent 50%);
  pointer-events: none;
}
.kb-landing-icon {
  position: relative; z-index: 1;
  width: 88px; height: 88px;
  margin: 0 auto 20px;
  border-radius: 22px;
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  display: flex; align-items: center; justify-content: center;
  color: #fff;
  box-shadow: 0 18px 36px -10px rgba(99, 102, 241, .55);
  animation: kbFloat 3.5s ease-in-out infinite;
}
.kb-landing-title {
  position: relative; z-index: 1;
  font-size: 24px; font-weight: 700; color: #0f172a;
  letter-spacing: -0.5px; margin-bottom: 10px;
}
.kb-landing-sub {
  position: relative; z-index: 1;
  font-size: 13.5px; color: #64748b; line-height: 1.7;
  max-width: 380px; margin: 0 auto 28px;
}
.kb-landing-actions {
  position: relative; z-index: 1;
  display: flex; gap: 10px; justify-content: center; flex-wrap: wrap;
}

/* ===== 客户 KB 总览 Dialog ===== */
.kb-overview-search {
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px dashed #e2e8f0;
}
.kb-overview-search :deep(.el-input__wrapper) {
  border-radius: 10px;
}
.kb-overview-search-meta {
  margin-top: 8px;
  font-size: 12px; color: #94a3b8;
  display: flex; align-items: center; gap: 4px;
}
.kb-overview-search-stat { color: #6366f1; font-weight: 500; }
.kb-switch-loading {
  display: flex; align-items: center; justify-content: center; gap: 10px;
  padding: 40px 0; color: #6366f1; font-size: 13px;
}
.kb-switch-empty {
  padding: 32px 0; text-align: center;
  color: #94a3b8; font-size: 13px;
}
.kb-overview-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 10px;
  max-height: 540px; overflow-y: auto;
  padding: 2px;
}
/* ===== 客户列表视图：KPI + 专业表格 ===== */
.kb-kpis { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 14px; }
.kb-kpi { display: flex; align-items: center; gap: 12px; background: #fff; border: 1px solid #e7edf5; border-radius: 12px; padding: 14px 18px; }
.kb-kpi-ic { width: 38px; height: 38px; border-radius: 10px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.kpi-ic-blue { background: #eff6ff; color: #2563eb; }
.kpi-ic-green { background: #ecfdf5; color: #059669; }
.kpi-ic-amber { background: #fff7ed; color: #ea580c; }
.kb-kpi-num { font-size: 24px; font-weight: 800; color: #0f172a; line-height: 1.05; font-variant-numeric: tabular-nums; }
.kb-kpi-lbl { font-size: 12px; color: #64748b; margin-top: 2px; }

.kb-panel { background: #fff; border: 1px solid #eef2f7; border-radius: 14px; padding: 16px 18px; box-shadow: 0 1px 3px rgba(15,23,42,.04); }
.kb-panel-bar { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; flex-wrap: wrap; }
.kb-list-search { width: 260px; }
.kb-list-meta { font-size: 12.5px; color: #94a3b8; }
.kb-panel-bar-right { margin-left: auto; display: flex; gap: 8px; }

.kb-table {
  --el-table-border-color: transparent;
  --el-table-header-bg-color: #f8fafc;
  --el-table-row-hover-bg-color: #f5f8ff;
}
.kb-table :deep(th.el-table__cell) { font-size: 12px; color: #64748b; font-weight: 600; }
.kb-table :deep(.el-table__row) { cursor: pointer; }
.kb-cust-cell { display: flex; align-items: center; gap: 11px; min-width: 0; }
.kb-avatar {
  width: 34px; height: 34px; border-radius: 9px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  color: #fff; font-size: 15px; font-weight: 700;
  box-shadow: 0 2px 6px -2px rgba(15,23,42,.3);
}
.kb-cust-txt { display: flex; flex-direction: column; min-width: 0; gap: 1px; }
.kb-cust-name { font-size: 14px; font-weight: 700; color: #0f172a; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.kb-cust-company { font-size: 12px; color: #94a3b8; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.kb-vcount { font-size: 13px; color: #334155; font-weight: 600; font-variant-numeric: tabular-nums; }
.kb-none { font-size: 12.5px; color: #cbd5e1; }
.cell-muted { color: #cbd5e1; }
.cell-time { font-size: 12.5px; color: #64748b; font-variant-numeric: tabular-nums; }
.kb-row-go { display: inline-flex; align-items: center; gap: 3px; font-size: 12.5px; color: #94a3b8; font-weight: 600; }
.kb-table :deep(.el-table__row:hover) .kb-row-go { color: #6366f1; }
@media (max-width: 900px) { .kb-kpis { grid-template-columns: 1fr; } }
.kb-overview-card {
  display: flex; flex-direction: column; gap: 10px;
  padding: 14px;
  background: #fff;
  border: 1px solid #e2e8f0; border-radius: 12px;
  cursor: pointer;
  transition: all .2s;
  position: relative;
}
.kb-overview-card:hover {
  border-color: #c7d2fe;
  box-shadow: 0 8px 18px -6px rgba(99, 102, 241, .25);
  transform: translateY(-2px);
}
.kb-overview-card.active {
  border-color: #818cf8; background: #eef2ff;
  box-shadow: 0 0 0 3px rgba(129, 140, 248, .15);
}
.kb-overview-card.empty {
  background: #fafafa;
}
.kb-overview-card.empty:hover {
  border-color: #cbd5e1; background: #f8fafc;
}
.kb-ov-head {
  display: flex; align-items: flex-start; justify-content: space-between;
  gap: 8px;
}
.kb-ov-name {
  font-size: 14px; font-weight: 700; color: #0f172a; line-height: 1.4;
  flex: 1; min-width: 0;
  word-break: break-all;
}
.kb-ov-brand { color: #64748b; font-weight: 500; font-size: 12.5px; }
.kb-ov-company {
  margin-top: 3px;
  font-size: 11.5px; color: #94a3b8; font-weight: 400;
  letter-spacing: 0.2px;
}
.kb-ov-body {
  display: flex; flex-direction: column; gap: 6px;
  padding-top: 8px;
  border-top: 1px dashed #e2e8f0;
}
.kb-ov-stat {
  display: inline-flex; align-items: baseline; gap: 4px;
}
.kb-ov-stat-num {
  font-size: 20px; font-weight: 800;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.kb-ov-stat-label { color: #94a3b8; font-size: 12px; }
.kb-ov-current {
  display: inline-flex; align-items: center; gap: 6px;
}
.kb-ov-cur-tag {
  padding: 2px 8px;
  background: #eef2ff;
  color: #4338ca;
  border-radius: 6px;
  font-size: 12px; font-weight: 700;
}
.kb-ov-meta {
  display: inline-flex; align-items: center; gap: 4px;
  color: #94a3b8; font-size: 11.5px;
}
.kb-ov-body-empty {
  display: flex; align-items: center; gap: 6px;
  color: #94a3b8; font-size: 12.5px;
  flex-direction: row;
}
.kb-ov-empty-ic { color: #cbd5e1; }
.kb-ov-empty-tip { color: #cbd5e1; font-size: 11px; margin-left: auto; }

.kb-body {
  display: grid; grid-template-columns: 280px 1fr; gap: 12px;
  flex: 1; min-height: 0;
}
.kb-side {
  background: #fff; border-radius: 12px; padding: 14px;
  display: flex; flex-direction: column; gap: 16px;
  box-shadow: 0 1px 3px rgba(0,0,0,.04);
  min-height: 0; overflow-y: auto;
}
.side-section { display: flex; flex-direction: column; gap: 8px; }
.side-head {
  font-size: 12px; font-weight: 700; color: #475569;
  letter-spacing: 0.5px; padding-bottom: 4px; border-bottom: 1px solid #f1f5f9;
}
.side-empty { color: #94a3b8; font-size: 12px; padding: 8px 0; }

.version-list, .src-list { display: flex; flex-direction: column; gap: 6px; }
.ver-item {
  padding: 8px 10px; border-radius: 8px; cursor: pointer;
  border: 1px solid #f1f5f9; transition: all .15s;
}
.ver-item:hover { background: #f8fafc; border-color: #cbd5e1; }
.ver-item.active { background: #eef2ff; border-color: #818cf8; }
.ver-row1 { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; margin-bottom: 4px; }
.ver-tag { font-weight: 700; color: #4f46e5; }
.ver-current { color: #16a34a; font-size: 11px; font-weight: 600; }
.ver-row2 { color: #94a3b8; font-size: 11px; }
.ver-actions { margin-top: 4px; display: flex; gap: 4px; }

.src-item { padding: 8px 10px; border-radius: 8px; border: 1px solid #f1f5f9; }
.src-row1 { display: flex; align-items: center; gap: 6px; margin-bottom: 4px; }
.src-icon { color: #64748b; }
.src-name { font-size: 12px; font-weight: 600; color: #334155;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.src-row2 { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; font-size: 11px; }
.src-meta { color: #94a3b8; }

.kb-main {
  background: #fff; border-radius: 12px; padding: 16px;
  box-shadow: 0 1px 3px rgba(0,0,0,.04);
  min-width: 0;
  min-height: 0; overflow-y: auto;
}
.kb-empty { padding: 60px 0; }
.page-empty { padding: 80px 0; }

.kb-view-head {
  display: flex; justify-content: space-between; align-items: center;
  padding-bottom: 12px; margin-bottom: 12px; border-bottom: 1px solid #f1f5f9;
  gap: 12px; flex-wrap: wrap;
}
.kb-view-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.kb-view-time, .kb-view-inst { color: #94a3b8; font-size: 12px; margin-left: 8px; }

/* ===== 模块导航条 ===== */
.kb-mod-nav {
  display: flex; gap: 6px; flex-wrap: wrap;
  padding: 8px 0;
  margin-bottom: 12px;
  border-bottom: 1px dashed #e2e8f0;
}
.kb-mod-tab {
  position: relative;
  display: inline-flex; align-items: center; gap: 4px;
  padding: 6px 12px;
  background: #f1f5f9; border: 1px solid transparent;
  border-radius: 8px; cursor: pointer;
  font-size: 12.5px; font-weight: 600; color: #475569;
  transition: all .15s;
}
.kb-mod-tab:hover {
  background: #e2e8f0; color: #1e293b;
}
.kb-mod-tab.active {
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #fff; border-color: transparent;
  box-shadow: 0 4px 10px -2px rgba(99,102,241,.45);
}
.kb-mod-tab.warn:not(.active) { background: #fef3c7; color: #92400e; }
.kb-mod-tab-key { letter-spacing: 0.3px; }
.kb-mod-warn-badge {
  margin-left: 2px; padding: 0 6px; min-height: 16px; line-height: 16px;
}

/* ===== 当前模块标题 ===== */
.kb-mod-header {
  display: flex; align-items: center; justify-content: space-between;
  gap: 12px; flex-wrap: wrap;
  padding: 12px 16px;
  background: linear-gradient(135deg, #eef2ff, #faf5ff);
  border-radius: 10px;
  margin-bottom: 16px;
}
.kb-mod-header-left { display: inline-flex; align-items: baseline; gap: 10px; }
.kb-mod-header-key {
  display: inline-block;
  padding: 3px 10px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #fff;
  border-radius: 6px;
  font-size: 13px; font-weight: 700;
  letter-spacing: 0.5px;
  box-shadow: 0 4px 10px -2px rgba(99,102,241,.4);
}
.kb-mod-header-title { font-size: 16px; font-weight: 700; color: #0f172a; }
.kb-mod-warn-tip {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 4px 10px;
  background: #fef9e7; color: #92400e;
  border-radius: 6px;
  font-size: 12.5px;
  border-left: 3px solid #f59e0b;
}
.kb-mod-warn-tip strong { color: #b45309; }

/* ===== 单模块内容（去掉首层 ## 标题，因为已在 kb-mod-header 显示） ===== */
.kb-content-single :deep(h2):first-child {
  display: none;
}

/* ===== 上下页 ===== */
.kb-mod-pager {
  display: flex; justify-content: space-between; align-items: center;
  margin-top: 24px; padding-top: 16px;
  border-top: 1px solid #f1f5f9;
}
.kb-mod-pager-mid {
  font-size: 12.5px; color: #94a3b8; font-variant-numeric: tabular-nums;
}

.kb-content {
  font-size: 14px; line-height: 1.8; color: #0f172a;
  max-width: 900px;
}
.kb-content :deep(h1) { font-size: 24px; font-weight: 700; margin: 24px 0 12px; color: #0f172a; }
.kb-content :deep(h2) { font-size: 18px; font-weight: 700; margin: 20px 0 10px; color: #1e40af;
  padding: 8px 12px; background: linear-gradient(90deg, #eef2ff 0%, transparent 100%);
  border-left: 4px solid #6366f1; }
.kb-content :deep(h3) { font-size: 15px; font-weight: 700; margin: 16px 0 8px; color: #334155; }
.kb-content :deep(p) { margin: 8px 0; }
.kb-content :deep(blockquote) {
  border-left: 4px solid #cbd5e1; padding: 4px 12px; color: #64748b;
  background: #f8fafc; margin: 8px 0;
}
.kb-content :deep(.kb-warn) {
  background: #fef9e7; border: 1.5px solid #e67e22; border-left: 7px solid #c0392b;
  padding: 12px 16px; margin: 16px 0; color: #6e2c00; font-size: 13px;
  border-radius: 6px;
}
.kb-content :deep(.kb-warn-tag) { color: #c0392b; font-weight: 700; margin-right: 6px; }
.kb-content :deep(.kb-table) {
  border-collapse: collapse; margin: 12px 0; width: 100%;
}
.kb-content :deep(.kb-table th), .kb-content :deep(.kb-table td) {
  border: 1px solid #e2e8f0; padding: 6px 12px; font-size: 13px;
}
.kb-content :deep(.kb-table th) { background: #f1f5f9; font-weight: 700; color: #334155; }

.kb-edit-head {
  margin-bottom: 12px; display: flex; align-items: center; gap: 8px;
  padding-bottom: 8px; border-bottom: 1px solid #f1f5f9;
}
.muted { color: #94a3b8; font-size: 13px; }
.edit-textarea :deep(.el-textarea__inner) {
  font-family: ui-monospace, SFMono-Regular, monospace;
  font-size: 13px; line-height: 1.6;
}
.edit-form { margin-top: 16px; }
.kb-edit-actions {
  margin-top: 16px; padding-top: 12px; border-top: 1px solid #f1f5f9;
  display: flex; justify-content: flex-end; gap: 8px;
}

.create-account-row { display: flex; gap: 8px; }

/* ════════════════════════════════════════════════════════
   ===== 创建知识库 / 新建客户 Dialog v2（精装版）=====
   ════════════════════════════════════════════════════════ */
.kb-create-dialog :deep(.el-dialog) {
  border-radius: 20px;
  overflow: hidden;
  box-shadow:
    0 24px 64px -12px rgba(15, 23, 42, .24),
    0 0 0 1px rgba(15, 23, 42, .04);
  border: none;
  background: #fff;
}
.kb-create-dialog :deep(.el-dialog__header) { padding: 0; margin: 0; }
.kb-create-dialog :deep(.el-dialog__body) { padding: 24px 28px 6px; }
.kb-create-dialog :deep(.el-dialog__footer) {
  padding: 16px 24px;
  border-top: 1px solid #f1f5f9;
  background: #fafbfc;
}

/* ── Hero Header（渐变 + 图标） ── */
.kb-dlg-hero {
  position: relative; overflow: hidden;
  display: flex; align-items: center; gap: 14px;
  padding: 20px 24px 22px;
  background: linear-gradient(135deg, #eef2ff 0%, #faf5ff 50%, #fdf2ff 100%);
  border-bottom: 1px solid rgba(99, 102, 241, .12);
}
.kb-dlg-hero-blue {
  background: linear-gradient(135deg, #eff6ff 0%, #f0f9ff 50%, #f0fdff 100%);
}
.kb-dlg-hero-bg {
  position: absolute; inset: 0;
  background-image:
    radial-gradient(circle at 90% 10%, rgba(139, 92, 246, .15) 0%, transparent 40%),
    radial-gradient(circle at 10% 90%, rgba(99, 102, 241, .12) 0%, transparent 40%);
  pointer-events: none;
}
.kb-dlg-hero-icon {
  position: relative; z-index: 1;
  width: 46px; height: 46px; border-radius: 13px;
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  display: flex; align-items: center; justify-content: center;
  color: #fff; flex-shrink: 0;
  box-shadow: 0 8px 18px -4px rgba(99, 102, 241, .55);
}
.kb-dlg-hero-blue .kb-dlg-hero-icon {
  background: linear-gradient(135deg, #3b82f6 0%, #06b6d4 100%);
  box-shadow: 0 8px 18px -4px rgba(59, 130, 246, .5);
}
.kb-dlg-hero-text { position: relative; z-index: 1; flex: 1; min-width: 0; }
.kb-dlg-hero-title {
  font-size: 17px; font-weight: 700; color: #0f172a; line-height: 1.3;
  letter-spacing: -0.2px;
}
.kb-dlg-hero-sub {
  margin-top: 3px;
  font-size: 12.5px; color: #64748b; line-height: 1.5;
}
.kb-dlg-close {
  position: relative; z-index: 1;
  width: 30px; height: 30px; border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  background: transparent; border: none; cursor: pointer;
  color: #94a3b8; transition: all .15s;
}
.kb-dlg-close:hover { background: rgba(15, 23, 42, .06); color: #475569; }

/* ── Form 全局 ── */
.kb-create-form :deep(.el-form-item) { margin-bottom: 22px; }
.kb-create-form :deep(.el-form-item:last-child) { margin-bottom: 8px; }
.kb-create-form :deep(.el-form-item__label) {
  font-weight: 600; color: #1e293b; font-size: 13.5px;
  padding-right: 14px;
}
.kb-create-form :deep(.el-input__wrapper),
.kb-create-form :deep(.el-textarea__inner),
.kb-create-form :deep(.el-select__wrapper) {
  border-radius: 10px;
  box-shadow: 0 0 0 1px #e2e8f0 inset;
  transition: all .2s;
}
.kb-create-form :deep(.el-input__wrapper:hover),
.kb-create-form :deep(.el-select__wrapper:hover),
.kb-create-form :deep(.el-textarea__inner:hover) {
  box-shadow: 0 0 0 1px #cbd5e1 inset;
}
.kb-create-form :deep(.el-input.is-focus .el-input__wrapper),
.kb-create-form :deep(.el-textarea__inner:focus),
.kb-create-form :deep(.el-select.is-focused .el-select__wrapper) {
  box-shadow: 0 0 0 2px #6366f1 inset, 0 0 0 4px rgba(99, 102, 241, .12) !important;
}

.kb-field-row {
  display: flex; gap: 10px; align-items: center;
  width: 100%;
}
.kb-field-row :deep(.el-select) { flex: 1; min-width: 0; }
.kb-field-row :deep(.el-select__wrapper) { width: 100%; }
.kb-create-form :deep(.el-form-item__content) {
  width: 100%; display: block; line-height: normal;
}
.kb-create-form :deep(.el-form-item__content > div),
.kb-create-form :deep(.el-form-item__content > .el-input),
.kb-create-form :deep(.el-form-item__content > .el-textarea) {
  width: 100%;
}
.kb-field-hint {
  display: flex; align-items: center; gap: 5px;
  font-size: 12px; color: #94a3b8;
  margin-top: 6px; line-height: 1.6;
}

/* 目标客户选择 picker（不用 el-select，改弹窗式） */
.kb-acct-locked { font-size: 15px; font-weight: 600; color: #1e293b; padding: 6px 0; }
.kb-acct-picker {
  flex: 1; min-width: 0;
  display: flex; align-items: center; justify-content: space-between;
  gap: 8px;
  height: 40px; padding: 0 14px;
  background: #fff; border: 1px solid #dcdfe6;
  border-radius: 8px;
  font-size: 14px; color: #1e293b;
  cursor: pointer; transition: border-color .15s, box-shadow .15s;
  font-family: inherit;
}
.kb-acct-picker:hover { border-color: #c0c4cc; }
.kb-acct-picker:focus { outline: none; border-color: #409eff; box-shadow: 0 0 0 1px rgba(64,158,255,.2); }
.kb-acct-picker.empty .kb-acct-picker-placeholder { color: #a8abb2; }
.kb-acct-picker-name {
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  font-weight: 500;
}
.kb-acct-picker-arrow { color: #909399; font-size: 12px; flex-shrink: 0; }

/* 选择弹窗内部 */
.acct-picker-body { display: flex; flex-direction: column; gap: 12px; }
.acct-picker-search :deep(.el-input__wrapper) { border-radius: 8px; }
.acct-picker-count { font-size: 12px; color: #94a3b8; padding: 0 4px; }
.acct-picker-list {
  max-height: 50vh; overflow-y: auto;
  display: flex; flex-direction: column; gap: 4px;
  padding: 4px; border: 1px solid #f1f5f9; border-radius: 8px;
  background: #fafbfc;
}
.acct-picker-row {
  display: flex; align-items: center; justify-content: space-between;
  gap: 12px; padding: 12px 14px;
  background: #fff; border: 1px solid transparent; border-radius: 7px;
  cursor: pointer; transition: all .12s;
  font-family: inherit; text-align: left; width: 100%;
}
.acct-picker-row:hover { border-color: #93c5fd; background: #eff6ff; }
.acct-picker-row.active { background: #eff6ff; border-color: #2563eb; }
.acct-picker-row-main { display: flex; flex-direction: column; gap: 3px; min-width: 0; flex: 1; }
.acct-picker-row-name { font-size: 14px; font-weight: 600; color: #0f172a; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.acct-picker-row-brand { font-size: 12px; color: #64748b; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.acct-picker-row-check { color: #2563eb; font-size: 18px; flex-shrink: 0; }
.acct-picker-empty {
  text-align: center; padding: 28px 16px;
  color: #94a3b8; font-size: 13px;
}
.kb-field-hint.kb-hint-success {
  color: #15803d;
  background: linear-gradient(90deg, rgba(34, 197, 94, .08), transparent);
  padding: 6px 10px; border-radius: 6px;
  border-left: 3px solid #22c55e;
}
.kb-field-hint.kb-hint-success strong { color: #166534; }

/* ── 上传卡片（重头戏） ── */
.kb-upload-card {
  background: #f8fafc;
  border-radius: 14px;
  padding: 16px;
  border: 1px solid #e2e8f0;
  width: 100%; box-sizing: border-box;
}

/* ── 历史资料勾选区 ── */
.kb-history-section { margin-bottom: 12px; }
.kb-history-head {
  display: flex; align-items: center; gap: 6px;
  margin-bottom: 8px;
  font-size: 12.5px; color: #475569; font-weight: 600;
}
.kb-history-head .el-icon { color: #6366f1; }
.kb-history-head strong { color: #6366f1; margin-left: 2px; }
.kb-history-head > span { flex: 1; }
.kb-history-zero { color: #94a3b8; font-weight: 400; font-size: 11.5px; }
.kb-history-empty {
  display: flex; align-items: center; gap: 6px;
  color: #94a3b8; font-size: 12px; padding: 8px 0;
}
.kb-history-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 6px;
}
.kb-history-item {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 10px;
  background: #fff; border: 1px solid #e2e8f0; border-radius: 8px;
  cursor: pointer;
  transition: all .15s;
}
.kb-history-item:hover {
  border-color: #c7d2fe;
  background: #fafbff;
}
.kb-history-item.checked {
  border-color: #6366f1; background: #eef2ff;
  box-shadow: 0 4px 10px -4px rgba(99,102,241,.2);
}
.kb-history-item.disabled {
  opacity: .55; cursor: not-allowed;
}
.kb-history-item.disabled:hover { background: #fff; border-color: #e2e8f0; }
.kb-history-item input[type=checkbox] {
  width: 14px; height: 14px;
  accent-color: #6366f1;
  cursor: pointer;
  flex-shrink: 0;
}
.kb-history-item.disabled input[type=checkbox] { cursor: not-allowed; }
.kb-history-icon {
  width: 26px; height: 26px; border-radius: 6px;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.kb-history-icon.ft-pdf { background: #fee2e2; color: #b91c1c; }
.kb-history-icon.ft-doc { background: #dbeafe; color: #1d4ed8; }
.kb-history-icon.ft-xls { background: #d1fae5; color: #047857; }
.kb-history-icon.ft-img { background: #fef3c7; color: #b45309; }
.kb-history-icon.ft-txt { background: #f1f5f9; color: #475569; }
.kb-history-meta { flex: 1; min-width: 0; }
.kb-history-name {
  font-size: 12px; color: #1e293b; font-weight: 500;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.kb-history-sub {
  display: flex; align-items: center; gap: 6px;
  font-size: 10.5px; color: #94a3b8; margin-top: 2px;
}
.kb-history-size { font-variant-numeric: tabular-nums; }

/* 历史 vs 新上传 分隔 */
.kb-upload-divider {
  display: flex; align-items: center; gap: 10px;
  margin: 12px 0;
  color: #94a3b8; font-size: 11.5px;
}
.kb-upload-divider::before,
.kb-upload-divider::after {
  content: ''; flex: 1; height: 1px;
  background: linear-gradient(90deg, transparent, #cbd5e1, transparent);
}
.kb-upload-zone-v2 :deep(.el-upload) { display: block; width: 100%; }
.kb-upload-zone-v2 :deep(.el-upload-dragger) {
  width: 100%;
  padding: 22px 16px;
  border-radius: 12px;
  border: 2px dashed #cbd5e1;
  background: linear-gradient(180deg, #ffffff 0%, #fafbff 100%);
  transition: all .25s cubic-bezier(.4, 0, .2, 1);
  position: relative; overflow: hidden;
  box-sizing: border-box;
}
.kb-upload-zone-v2 :deep(.el-upload-dragger:hover) {
  border-color: #6366f1;
  background: linear-gradient(180deg, #ffffff 0%, #f0f3ff 100%);
  transform: translateY(-2px);
  box-shadow: 0 14px 32px -10px rgba(99, 102, 241, .28);
}
.kb-upload-zone-v2 :deep(.el-upload-dragger.is-dragover) {
  border-color: #6366f1;
  background: #eef2ff;
  transform: scale(1.005);
  box-shadow: 0 0 0 4px rgba(99, 102, 241, .15);
}
.kb-upload-inner {
  display: flex; flex-direction: column; align-items: center; gap: 10px;
}
.kb-upload-icon-wrap {
  width: 56px; height: 56px; border-radius: 16px;
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  display: flex; align-items: center; justify-content: center;
  color: #fff;
  box-shadow: 0 12px 24px -8px rgba(99, 102, 241, .45);
  animation: kbFloat 3.5s ease-in-out infinite;
}
@keyframes kbFloat {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-5px); }
}
.kb-upload-main {
  font-size: 14.5px; color: #1e293b; font-weight: 500;
}
.kb-upload-main em {
  color: #6366f1; font-style: normal; font-weight: 700;
  position: relative;
}
.kb-upload-main em::after {
  content: ''; position: absolute;
  left: 0; right: 0; bottom: -2px; height: 2px;
  background: linear-gradient(90deg, #6366f1, #8b5cf6);
  border-radius: 2px;
}
.kb-upload-types {
  display: flex; gap: 6px; flex-wrap: wrap; justify-content: center;
}
.ft-chip {
  padding: 3px 11px; border-radius: 999px;
  font-size: 11px; font-weight: 700; letter-spacing: 0.3px;
}
.ft-chip.ft-pdf { background: #fee2e2; color: #b91c1c; }
.ft-chip.ft-doc { background: #dbeafe; color: #1d4ed8; }
.ft-chip.ft-xls { background: #d1fae5; color: #047857; }
.ft-chip.ft-img { background: #fef3c7; color: #b45309; }
.ft-chip.ft-txt { background: #f1f5f9; color: #475569; }
.kb-upload-foot {
  font-size: 11.5px; color: #94a3b8; margin-top: 2px;
}

/* ── 已选文件卡片列表 ── */
.kb-fade-enter-active, .kb-fade-leave-active { transition: opacity .25s; }
.kb-fade-enter-from, .kb-fade-leave-to { opacity: 0; }

.kb-file-list {
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px dashed #cbd5e1;
}
.kb-file-list-head {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 10px;
  font-size: 12.5px; color: #475569; font-weight: 500;
}
.kb-file-list-head strong { color: #6366f1; font-weight: 700; }
.kb-file-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 8px;
}
.kb-file-card {
  display: flex; align-items: center; gap: 10px;
  padding: 8px 10px;
  background: #fff; border-radius: 10px;
  border: 1px solid #e2e8f0;
  transition: all .2s;
  position: relative;
}
.kb-file-card:hover {
  border-color: #c7d2fe;
  box-shadow: 0 6px 14px -4px rgba(99, 102, 241, .15);
  transform: translateY(-1px);
}
.kb-file-icon {
  width: 32px; height: 32px; border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.kb-file-card.ft-pdf .kb-file-icon { background: #fee2e2; color: #b91c1c; }
.kb-file-card.ft-doc .kb-file-icon { background: #dbeafe; color: #1d4ed8; }
.kb-file-card.ft-xls .kb-file-icon { background: #d1fae5; color: #047857; }
.kb-file-card.ft-img .kb-file-icon { background: #fef3c7; color: #b45309; }
.kb-file-card.ft-txt .kb-file-icon { background: #f1f5f9; color: #475569; }
.kb-file-meta { flex: 1; min-width: 0; }
.kb-file-name {
  font-size: 12.5px; color: #1e293b; font-weight: 500;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.kb-file-size {
  font-size: 10.5px; color: #94a3b8; margin-top: 2px;
}
.kb-file-rm {
  width: 22px; height: 22px; border-radius: 6px;
  background: transparent; border: none; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  color: #cbd5e1; transition: all .15s; flex-shrink: 0;
}
.kb-file-rm:hover { background: #fee2e2; color: #dc2626; }

/* ── Footer 按钮 ── */
.kb-footer {
  display: flex; justify-content: space-between; align-items: center; gap: 10px;
}
.kb-footer-actions { display: flex; gap: 8px; }
.kb-create-dialog :deep(.el-button) {
  border-radius: 10px;
  font-weight: 500;
  transition: transform .15s, box-shadow .15s, background .2s;
}
.kb-create-dialog :deep(.el-button.el-button--large) {
  height: 40px; padding: 0 18px; font-size: 13.5px;
}
.kb-create-dialog :deep(.el-button:not(.is-disabled):not(.is-text):hover) {
  transform: translateY(-1px);
}
.kb-btn-gen {
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%) !important;
  border-color: transparent !important;
  box-shadow: 0 6px 16px -4px rgba(99, 102, 241, .4);
}
.kb-btn-gen:not(.is-disabled):hover {
  background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%) !important;
  box-shadow: 0 12px 24px -6px rgba(99, 102, 241, .5) !important;
}
.kb-btn-gen.is-disabled {
  background: #cbd5e1 !important; box-shadow: none !important;
}

/* ── radio-button 圆角化 ── */
.kb-create-dialog :deep(.el-radio-button:first-child .el-radio-button__inner) {
  border-radius: 10px 0 0 10px;
}
.kb-create-dialog :deep(.el-radio-button:last-child .el-radio-button__inner) {
  border-radius: 0 10px 10px 0;
}
.kb-create-dialog :deep(.el-radio-button__inner) {
  font-weight: 500; padding: 8px 18px;
}

/* ── 模式切换 ── */
.kb-mode-switch { width: 100%; }
.kb-mode-switch :deep(.el-radio-button) { flex: 1; }
.kb-mode-switch :deep(.el-radio-button__inner) {
  width: 100%; padding: 10px 12px; font-size: 13px;
}
.kb-mode-hint {
  margin-top: 8px;
  font-size: 12.5px; color: #6366f1;
  background: linear-gradient(90deg, rgba(99,102,241,.08), transparent);
  padding: 8px 12px; border-radius: 8px;
  border-left: 3px solid #6366f1;
  line-height: 1.5;
}

/* ── 方式 A：报告下拉选项内嵌布局 ── */
.kb-report-opt {
  display: flex; align-items: center; gap: 10px; width: 100%;
}
.kb-report-id {
  font-weight: 700; color: #6366f1; font-size: 13px;
}
.kb-report-date { flex: 1; color: #475569; font-size: 12.5px; }

/* ── 方式 A 空状态提示 ── */
.kb-empty-tip {
  display: flex; align-items: center; gap: 6px;
  margin-top: 8px;
  padding: 10px 12px;
  background: #fffbeb;
  border-left: 3px solid #f59e0b;
  border-radius: 6px;
  font-size: 12.5px; color: #92400e; line-height: 1.5;
}

/* ── 参考报告（必填）卡片 ── */
.kb-ref-card {
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 14px 16px;
}
.kb-ref-card-head {
  display: flex; align-items: flex-start; gap: 8px;
  font-size: 12.5px; color: #475569; line-height: 1.6;
  padding-bottom: 12px; margin-bottom: 12px;
  border-bottom: 1px dashed #cbd5e1;
}
.kb-ref-card-head .el-icon { color: #6366f1; margin-top: 3px; flex-shrink: 0; }
.kb-ref-card-head strong { color: #6366f1; }
.kb-ref-row {
  display: flex; align-items: flex-start; gap: 10px;
  padding: 8px 0;
}
.kb-ref-row + .kb-ref-row {
  border-top: 1px dashed #e2e8f0;
}
.kb-ref-row-label {
  width: 78px; flex-shrink: 0;
  font-size: 12.5px; font-weight: 600; color: #334155;
  padding-top: 8px;
}
.kb-ref-row-body { flex: 1; min-width: 0; }
.kb-ref-empty {
  margin-top: 4px; font-size: 11.5px; color: #94a3b8;
  font-style: italic;
}
.kb-ref-upload { display: flex; flex-direction: column; gap: 6px; }
.kb-ref-upload-zone :deep(.el-upload),
.kb-ref-upload-zone :deep(.el-upload-dragger) {
  width: 100%; box-sizing: border-box;
}
.kb-ref-upload-zone :deep(.el-upload-dragger) {
  padding: 14px 12px;
  border-radius: 10px;
  border: 1.5px dashed #cbd5e1;
  background: #fff;
  transition: all .2s cubic-bezier(.4,0,.2,1);
}
.kb-ref-upload-zone :deep(.el-upload-dragger:hover) {
  border-color: #6366f1;
  background: #fafbff;
  transform: translateY(-1px);
  box-shadow: 0 8px 18px -6px rgba(99,102,241,.22);
}
.kb-ref-upload-zone :deep(.el-upload-dragger.is-dragover) {
  border-color: #6366f1;
  background: #eef2ff;
  box-shadow: 0 0 0 4px rgba(99,102,241,.15);
}
.kb-ref-upload-inner {
  display: flex; align-items: center; justify-content: center;
  flex-wrap: wrap;
  gap: 8px; color: #475569;
}
.kb-ref-upload-inner .el-icon { color: #6366f1; }
.kb-ref-upload-main {
  font-size: 12.5px; color: #334155; font-weight: 500;
}
.kb-ref-upload-main em {
  color: #6366f1; font-style: normal; font-weight: 700;
}
.kb-ref-upload-sub { display: inline-flex; gap: 4px; }
.kb-ref-upload-sub .ft-chip { padding: 2px 8px; font-size: 10.5px; }
.kb-ref-upload-hint {
  display: flex; align-items: center; gap: 4px;
  font-size: 11.5px; color: #94a3b8;
}
.kb-ref-file {
  display: flex; align-items: center; gap: 10px;
  padding: 8px 10px;
  background: #fff; border: 1px solid #c7d2fe; border-radius: 10px;
  box-shadow: 0 4px 10px -4px rgba(99,102,241,.18);
}
.kb-ref-file-meta { flex: 1; min-width: 0; }

.src-meta-bar { display: flex; align-items: center; gap: 12px; margin-bottom: 8px; }
.src-err { color: #dc2626; font-size: 12px; }
.src-text {
  background: #0f172a; color: #cbd5e1; padding: 14px;
  border-radius: 8px; font-size: 12px; line-height: 1.6;
  max-height: 500px; overflow: auto; white-space: pre-wrap;
  font-family: ui-monospace, SFMono-Regular, monospace;
}
.src-view-tabs .el-tabs__content { padding-top: 10px; }
.src-md-preview {
  background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px;
  padding: 16px; max-height: 500px; overflow: auto; line-height: 1.7;
  font-size: 13px; color: #334155;
}

.task-running { text-align: center; padding: 16px 0; }
.task-spinner { color: #6366f1; margin-bottom: 12px; }
.task-text { color: #334155; font-size: 13px; margin-bottom: 6px; }
.task-elapsed { color: #94a3b8; font-size: 12px; }

/* ===== 浮动任务 widget（无蒙版） ===== */
.kb-task-float {
  position: fixed; right: 20px; bottom: 20px; z-index: 2000;
  width: 320px;
  background: #fff; border-radius: 14px;
  box-shadow:
    0 24px 64px -12px rgba(15, 23, 42, .25),
    0 0 0 1px rgba(99, 102, 241, .15);
  border: 1px solid rgba(99, 102, 241, .1);
  overflow: hidden;
}
.kb-task-float.minimized { width: 240px; }
.kb-task-float-tr-enter-active,
.kb-task-float-tr-leave-active { transition: transform .25s, opacity .25s; }
.kb-task-float-tr-enter-from,
.kb-task-float-tr-leave-to {
  opacity: 0; transform: translateY(20px) scale(.95);
}
.kb-task-float-head {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 12px;
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  color: #fff;
  cursor: pointer;
}
.kb-task-float-spin { display: flex; align-items: center; }
.kb-task-float-title {
  flex: 1; font-size: 13px; font-weight: 600;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.kb-task-float-elapsed {
  font-size: 11.5px; color: rgba(255,255,255,.85);
  background: rgba(255,255,255,.18); padding: 2px 7px; border-radius: 10px;
  font-variant-numeric: tabular-nums;
}
.kb-task-float-tog { color: rgba(255,255,255,.85); }
.kb-task-float-body { padding: 12px 14px 14px; }
.kb-task-progress { margin-bottom: 10px; }
.kb-task-progress-bar {
  height: 6px; background: #f1f5f9; border-radius: 999px;
  overflow: hidden;
}
.kb-task-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #6366f1, #8b5cf6);
  border-radius: 999px;
  transition: width .2s;
}
.kb-task-progress-text {
  margin-top: 4px;
  font-size: 11.5px; color: #6366f1; font-weight: 600;
}
.kb-task-float-body .kb-task-text {
  font-size: 12.5px; color: #475569; line-height: 1.6;
  margin-bottom: 8px;
}
.kb-task-tip {
  display: flex; align-items: center; gap: 4px;
  font-size: 11px; color: #94a3b8; line-height: 1.5;
  padding-top: 8px; border-top: 1px dashed #e2e8f0;
}

@media (max-width: 900px) {
  .kb-body { grid-template-columns: 1fr; }
  .kb-side { max-height: none; }
}

/* ── 规则库校对 ── */
.pf-loading { display: flex; align-items: center; gap: 10px; padding: 30px; justify-content: center; color: #64748b; }
.pf-summary {
  display: flex; align-items: center; gap: 8px; padding: 10px 14px; border-radius: 8px;
  background: #fffbeb; border: 1px solid #fde68a; color: #92400e; font-size: 13.5px; font-weight: 600;
  margin-bottom: 14px;
}
.pf-summary.clean { background: #ecfdf5; border-color: #a7f3d0; color: #047857; }
.pf-empty { padding: 20px; text-align: center; color: #94a3b8; font-size: 13px; }
.pf-clean-box { padding: 18px; text-align: center; color: #047857; font-size: 13.5px; }
.pf-list { display: flex; flex-direction: column; gap: 10px; max-height: 56vh; overflow-y: auto; }
.pf-item { border: 1px solid #fecaca; border-radius: 10px; padding: 12px 14px; background: #fff; }
.pf-item-head { display: flex; align-items: baseline; gap: 8px; margin-bottom: 8px; }
.pf-badge { flex-shrink: 0; font-size: 11px; font-weight: 700; color: #b91c1c; background: #fee2e2; border-radius: 4px; padding: 1px 7px; }
.pf-rule { font-size: 13px; font-weight: 600; color: #0f172a; }
.pf-evidence, .pf-suggestion { font-size: 12.5px; line-height: 1.6; color: #334155; margin-top: 4px; }
.pf-k { display: inline-block; font-size: 11px; color: #94a3b8; margin-right: 6px; }
.pf-suggestion { color: #047857; }
</style>
