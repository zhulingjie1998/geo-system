import axios from 'axios'

const http = axios.create({
  baseURL: '/api/publish',
  timeout: 60000,
  withCredentials: true,
})

http.interceptors.response.use(
  (res) => res.data,
  (err) => {
    console.error('Publish API Error:', err)
    return Promise.reject(err)
  },
)

export default {
  // 配置
  getConfig: () => http.get('/config'),
  saveConfig: (data) => http.post('/config', data),
  testConnect: () => http.post('/config/test'),

  // 余额
  getBalance: () => http.get('/balance'),

  // 首页看板
  getStats: () => http.get('/stats'),

  // 媒体
  listMedia: (params) => http.get('/media', { params }),
  // 异步触发同步，返回 task 行；需配合 syncMediaStatus 轮询
  syncMedia: (type) => http.post('/media/sync', { type }),
  syncMediaStatus: ({ taskId, type } = {}) => {
    const params = taskId ? { task_id: taskId } : { type }
    return http.get('/media/sync/status', { params })
  },

  // 单发
  createOrder: (data) => http.post('/order', data),
  getOrder: (id) => http.get(`/order/${id}`),
  deleteOrder: (id) => http.delete(`/order/${id}`),

  // 订单
  listOrders: (params) => http.get('/orders', { params }),
  // 成本对账：支持时间窗口 + 单客户筛选
  spendStats: ({ accountId = null, dateFrom = '', dateTo = '' } = {}) =>
    http.get('/spend', {
      params: {
        ...(accountId ? { account_id: accountId } : {}),
        ...(dateFrom ? { date_from: dateFrom } : {}),
        ...(dateTo ? { date_to: dateTo } : {}),
      },
    }),
  // 某客户成本明细（按媒体钻取，展开行用）
  spendMediaDetail: ({ accountId, dateFrom = '', dateTo = '' }) =>
    http.get('/spend/media-detail', {
      params: {
        account_id: accountId,
        ...(dateFrom ? { date_from: dateFrom } : {}),
        ...(dateTo ? { date_to: dateTo } : {}),
      },
    }),
  // 导出成本对账 Excel（返回 Blob）
  exportSpend: ({ accountId = null, dateFrom = '', dateTo = '' } = {}) =>
    http.get('/spend/export', {
      responseType: 'blob',
      params: {
        ...(accountId ? { account_id: accountId } : {}),
        ...(dateFrom ? { date_from: dateFrom } : {}),
        ...(dateTo ? { date_to: dateTo } : {}),
      },
    }),
  // 导出媒体资源库 Excel（新闻媒体 + 自媒体，返回 Blob）
  exportMedia: () => http.get('/media/export', { responseType: 'blob' }),
  // 批量发布预览:按媒体 ID 查全量库返回名称+价格
  resolveMedia: (data) => http.post('/media/resolve', data),
  queryOrders: (orderIds) => http.post('/orders/query', { order_ids: orderIds || null }),

  // 批量
  createBatch: (data) => http.post('/batch', data),
  listBatches: (params) => http.get('/batches', { params }),
  getBatch: (id) => http.get(`/batch/${id}`),
  cancelBatch: (id) => http.post(`/batch/${id}/cancel`),
  rescheduleBatch: (id, scheduledAt) => http.patch(`/batch/${id}/schedule`, { scheduled_at: scheduledAt }),
  runBatchNow: (id) => http.post(`/batch/${id}/run-now`),
  retryFailed: (id) => http.post(`/batch/${id}/retry-failed`),
  republishOrders: (items) => http.post('/orders/republish', { items }),
  failedOrders: (id) => http.get(`/batch/${id}/failed-orders`),
  bulkCreateOrders: (data) => http.post('/orders/bulk-create', data),
  checkDuplicates: (data) => http.post('/check-duplicates', data),

  // 图片上传（wangEditor customUpload 调用）
  uploadImg: (file) => {
    const fd = new FormData()
    fd.append('file', file)
    return axios.post('/api/publish/upload-img', fd, {
      withCredentials: true,
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then(r => r.data)
  },

  // Word .docx → HTML（含图片自动上传）
  convertDocx: (file, onProgress = null) => {
    const fd = new FormData()
    fd.append('file', file)
    return axios.post('/api/publish/convert/docx', fd, {
      withCredentials: true,
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 60000,
      onUploadProgress: (e) => {
        if (typeof onProgress === 'function' && e.total) {
          onProgress(Math.round(e.loaded * 100 / e.total))
        }
      },
    }).then(r => r.data)
  },

  // 联系方式/引流关键字扫描
  scanContact: (html) => http.post('/scan/contact', { html }),

  // 官网配置 / Webhook
  officialConfigList: () => axios.get('/api/publish/official-configs', { withCredentials: true }).then(r => r.data),
  officialConfigGet: (accountId) => axios.get(`/api/publish/official-config/${accountId}`, { withCredentials: true }).then(r => r.data),
  officialConfigSave: (accountId, data) => axios.put(`/api/publish/official-config/${accountId}`, data, { withCredentials: true }).then(r => r.data),
  officialConfigClear: (accountId) => axios.delete(`/api/publish/official-config/${accountId}`, { withCredentials: true }).then(r => r.data),
  publishViaWebhook: (payload) => axios.post('/api/publish/webhook/publish', payload, { withCredentials: true }).then(r => r.data),

  // ═══════════ 客户知识库 v2 ═══════════
  // 资料
  kbListSources: (accountId, kbVersionId = null) => {
    const params = { account_id: accountId }
    if (kbVersionId != null) params.kb_version_id = kbVersionId
    return axios.get('/api/kb/source/list', { params, withCredentials: true }).then(r => r.data)
  },
  kbUploadSources: (accountId, files, kbVersionId = null, onProgress = null) => {
    const fd = new FormData()
    fd.append('account_id', accountId)
    if (kbVersionId != null) fd.append('kb_version_id', kbVersionId)
    for (const f of files) fd.append('files', f)
    return axios.post('/api/kb/source/upload', fd, {
      withCredentials: true,
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (e) => {
        if (typeof onProgress === 'function' && e.total) {
          onProgress(Math.round(e.loaded * 100 / e.total))
        }
      },
    }).then(r => r.data)
  },
  kbSourceText: (id) => axios.get(`/api/kb/source/${id}/text`, { withCredentials: true }).then(r => r.data),
  kbDeleteSource: (id) => axios.delete(`/api/kb/source/${id}`, { withCredentials: true }).then(r => r.data),
  kbReparseSource: (id) => axios.post(`/api/kb/source/${id}/reparse`, {}, { withCredentials: true }).then(r => r.data),
  kbRecognizeSource: (id) => axios.post(`/api/kb/source/${id}/recognize`, {}, { withCredentials: true }).then(r => r.data),
  kbSourceAiText: (id) => axios.get(`/api/kb/source/${id}/ai-text`, { withCredentials: true }).then(r => r.data),

  // 版本
  kbListVersions: (accountId) => axios.get('/api/kb/versions', { params: { account_id: accountId }, withCredentials: true }).then(r => r.data),
  kbGetVersion: (id) => axios.get(`/api/kb/version/${id}`, { withCredentials: true }).then(r => r.data),
  kbCurrent: (accountId, followShare) => axios.get('/api/kb/current', { params: { account_id: accountId, ...(followShare ? { follow_share: 1 } : {}) }, withCredentials: true }).then(r => r.data),
  kbSetCurrent: (id) => axios.post(`/api/kb/version/${id}/set-current`, {}, { withCredentials: true }).then(r => r.data),
  kbDeleteVersion: (id) => axios.delete(`/api/kb/version/${id}`, { withCredentials: true }).then(r => r.data),
  kbProofread: (id) => axios.post(`/api/kb/version/${id}/proofread`, {}, { withCredentials: true }).then(r => r.data),

  // AI 生成（异步任务，返回 task_id 让前端轮询）
  kbGenerate: (accountId, instruction, sourceIds, opts = {}) => {
    const { refBrandReportId = null, refReportFile = null } = opts
    if (refReportFile) {
      // multipart：带文件，必须用 FormData
      const fd = new FormData()
      fd.append('account_id', accountId)
      fd.append('instruction', instruction || '')
      fd.append('source_ids', JSON.stringify(sourceIds))
      if (refBrandReportId) fd.append('reference_brand_report_id', refBrandReportId)
      fd.append('ref_report_file', refReportFile.raw || refReportFile)
      return axios.post('/api/kb/generate', fd, { withCredentials: true }).then(r => r.data)
    }
    return axios.post('/api/kb/generate', {
      account_id: accountId, instruction, source_ids: sourceIds,
      reference_brand_report_id: refBrandReportId,
    }, { withCredentials: true }).then(r => r.data)
  },
  kbRefine: (prevKbId, instruction, content, additionalSourceIds = []) =>
    axios.post(`/api/kb/refine/${prevKbId}`, { instruction, content, additional_source_ids: additionalSourceIds },
      { withCredentials: true }).then(r => r.data),
  // AI 扩充:在当前版本基础上新增 N 个全新模块
  kbExpand: (prevKbId, { instruction = '', additionalSourceIds = [], addCount = 3 } = {}) =>
    axios.post(`/api/kb/expand/${prevKbId}`, { instruction, additional_source_ids: additionalSourceIds, add_count: addCount },
      { withCredentials: true }).then(r => r.data),
  kbTaskStatus: (taskId) => axios.get(`/api/kb/task/${taskId}`, { withCredentials: true }).then(r => r.data),

  // Qwen AI 生成（使用通义千问模型）
  kbGenerateQwen: (accountId, { instruction = '', sourceIds = [], model = null } = {}) =>
    axios.post('/api/kb/generate-qwen', {
      account_id: accountId,
      instruction,
      source_ids: sourceIds,
      model,
    }, { withCredentials: true }).then(r => r.data),
  kbActiveTasks: (accountId = null) =>
    axios.get('/api/kb/active-tasks',
      { params: accountId ? { account_id: accountId } : {}, withCredentials: true }
    ).then(r => r.data),
  kbCustomerOverview: () =>
    axios.get('/api/kb/customer-overview', { withCredentials: true }).then(r => r.data),

  // ─── 智能生文 ───
  cntLlmProviders: () =>
    axios.get('/api/content/llm-providers', { withCredentials: true }).then(r => r.data),
  cntListTemplates: (scope = null) =>
    axios.get('/api/content/templates',
      { params: scope ? { scope } : {}, withCredentials: true }
    ).then(r => r.data),
  cntGetTemplate: (id) =>
    axios.get(`/api/content/templates/${id}`, { withCredentials: true }).then(r => r.data),
  cntCreateTemplate: (data) =>
    axios.post('/api/content/templates', data, { withCredentials: true }).then(r => r.data),
  cntUpdateTemplate: (id, data) =>
    axios.patch(`/api/content/templates/${id}`, data, { withCredentials: true }).then(r => r.data),
  cntDeleteTemplate: (id) =>
    axios.delete(`/api/content/templates/${id}`, { withCredentials: true }).then(r => r.data),
  cntAiDraftTemplate: (data) =>
    axios.post('/api/content/templates/ai-draft', data, { withCredentials: true }).then(r => r.data),
  cntGenerate: (data) =>
    axios.post('/api/content/generate', data, { withCredentials: true }).then(r => r.data),
  cntListTasks: (params = {}) =>
    axios.get('/api/content/tasks', { params, withCredentials: true }).then(r => r.data),
  cntGetTask: (id) =>
    axios.get(`/api/content/tasks/${id}`, { withCredentials: true }).then(r => r.data),
  cntGetTaskByUuid: (uuid) =>
    axios.get(`/api/content/tasks/by-uuid/${uuid}`, { withCredentials: true }).then(r => r.data),
  cntDeleteTask: (id) =>
    axios.delete(`/api/content/tasks/${id}`, { withCredentials: true }).then(r => r.data),
  // 主题生成（根据关键词和知识库生成差异化角度的主题列表）
  cntGenerateTopics: (data) =>
    axios.post('/api/content/generate-topics', data, { withCredentials: true }).then(r => r.data),
  // 轮询任务状态（用于 SSE 或长轮询）
  cntPollTaskStatus: (taskUuid) =>
    axios.get(`/api/content/tasks/${taskUuid}/poll`, { withCredentials: true }).then(r => r.data),

  // 人工保存（不调 LLM，直接新版本 created_by=human）
  kbSaveHuman: (prevKbId, content, comment = '') =>
    axios.post('/api/kb/save-human', { prev_kb_id: prevKbId, content, comment },
      { withCredentials: true }).then(r => r.data),

  // 离线 markdown 直接导入为新版本（Excel 手动上传拼装后调用）
  kbImportHuman: (accountId, content, comment = '') =>
    axios.post('/api/kb/import-human', { account_id: accountId, content, comment },
      { withCredentials: true }).then(r => r.data),

  // 入口 A：从已完成竞争分析报告导入 12 类资料清单
  kbListBrandReports: (accountId) =>
    axios.get('/api/kb/brand-reports', { params: { account_id: accountId }, withCredentials: true }).then(r => r.data),
  kbFromBrandReport: (accountId, reportId) =>
    axios.post('/api/kb/from-brand-report', { account_id: accountId, report_id: reportId },
      { withCredentials: true }).then(r => r.data),

  // 入口 B：上传外部分析报告（HTML/PDF/DOCX），LLM 抽取 12 类清单
  kbFromUploadedReport: (accountId, file) => {
    const fd = new FormData()
    fd.append('account_id', accountId)
    fd.append('file', file.raw || file)
    return axios.post('/api/kb/from-uploaded-report', fd, { withCredentials: true }).then(r => r.data)
  },

  // ─── 批量生文 · 草稿池 ───
  cbTopicsAuto: (accountId) =>
    axios.get('/api/content/batch/topics-auto', { params: { account_id: accountId }, withCredentials: true }).then(r => r.data),
  cbTopicsKeyword: (accountId) =>
    axios.get('/api/content/batch/topics-keyword', { params: { account_id: accountId }, withCredentials: true }).then(r => r.data),
  cbContentTypes: (accountId) =>
    axios.get('/api/content/batch/content-types', { params: { account_id: accountId }, withCredentials: true }).then(r => r.data),
  cbContentTypeTemplate: (accountId, typeKey) =>
    axios.post('/api/content/batch/content-type-template', { account_id: accountId, type_key: typeKey }, { withCredentials: true }).then(r => r.data),
  cbCreate: (data) =>
    axios.post('/api/content/batch', data, { withCredentials: true }).then(r => r.data),
  cbListBatches: (params = {}) =>
    axios.get('/api/content/batch', { params, withCredentials: true }).then(r => r.data),
  cbGetBatch: (id) =>
    axios.get(`/api/content/batch/${id}`, { withCredentials: true }).then(r => r.data),
  cbCancelBatch: (id) =>
    axios.post(`/api/content/batch/${id}/cancel`, {}, { withCredentials: true }).then(r => r.data),
  cbGetDraft: (id) =>
    axios.get(`/api/content/batch/draft/${id}`, { withCredentials: true }).then(r => r.data),
  cbPatchDraft: (id, data) =>
    axios.patch(`/api/content/batch/draft/${id}`, data, { withCredentials: true }).then(r => r.data),
  cbRegenDraft: (id, extraInstruction = '', kind = 'regenerate') =>
    axios.post(`/api/content/batch/draft/${id}/regenerate`,
      { extra_instruction: extraInstruction, kind },
      { withCredentials: true }).then(r => r.data),
  cbCommitDraft: (id) =>
    axios.post(`/api/content/batch/draft/${id}/commit`, {}, { withCredentials: true }).then(r => r.data),
  cbUncommitDraft: (id) =>
    axios.post(`/api/content/batch/draft/${id}/uncommit`, {}, { withCredentials: true }).then(r => r.data),
  cbDiscardDraft: (id) =>
    axios.delete(`/api/content/batch/draft/${id}`, { withCredentials: true }).then(r => r.data),
  cbRenameBatch: (id, name) =>
    axios.patch(`/api/content/batch/${id}`, { name }, { withCredentials: true }).then(r => r.data),
  cbDeleteBatch: (id) =>
    axios.delete(`/api/content/batch/${id}`, { withCredentials: true }).then(r => r.data),
  cbBulkDeleteBatches: (ids) =>
    axios.post('/api/content/batch/bulk-delete', { ids }, { withCredentials: true }).then(r => r.data),
  cbCommitAll: (id) =>
    axios.post(`/api/content/batch/${id}/commit-all`, {}, { withCredentials: true }).then(r => r.data),
  cbExportDocx: (id) =>
    axios.get(`/api/content/batch/${id}/export-docx`, { withCredentials: true, responseType: 'blob' }).then(r => r.data),

  // 状态映射
  statusText(status) {
    return { '-2': '已撤稿', '-1': '已拒稿', 0: '待审核', 1: '处理中', 2: '已完成', 99: '提交失败' }[status] ?? '未知'
  },
  statusType(status) {
    if (status === 2) return 'success'
    if (status === 1) return 'primary'
    if (status === 0) return 'warning'
    if (status === -1 || status === 99) return 'danger'
    if (status === -2) return 'info'
    return ''
  },
}
