import axios from 'axios'

const http = axios.create({
  baseURL: '/api',
  timeout: 30000,
  withCredentials: true
})

http.interceptors.response.use(
  (res) => {
    const body = res.data
    // 后端 ApiResult 包装识别：必须同时含 code(数字) + message + data 三字段才算
    // 仅检查 'code in body' 会把业务字段叫 code 的响应（如邀请码 {code:'mfs-XXX'}）误判
    if (body && typeof body === 'object'
        && typeof body.code === 'number'
        && 'message' in body
        && 'data' in body) {
      if (body.code === 200) return body.data
      return Promise.reject(new Error(body.message || '请求失败'))
    }
    return body
  },
  (err) => {
    // 401 自动跳转登录页（避免登录接口本身陷入循环 + 外部邀请页面是公开 API，不能踢去 /login）
    const status = err?.response?.status
    const url = err?.config?.url || ''
    const isPublic =
      url.includes('/auth/login') ||
      url.includes('/auth/me') ||
      url.includes('/external/') ||   // 外部邀请所有 API
      url.includes('/share/')          // 分享类公开 API
    if (status === 401 && !isPublic) {
      try {
        localStorage.removeItem('geo_user')
      } catch (_) {}
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    return Promise.reject(err)
  }
)

export default {
  // ========== 鉴权 ==========
  login: (username, password) => http.post('/auth/login', new URLSearchParams({ username, password }), {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
  }),
  logout: () => http.post('/auth/logout'),
  authMe: () => http.get('/auth/me'),
  changePassword: (oldPassword, newPassword) => http.post('/auth/change-password', { oldPassword, newPassword }),

  // ========== 管理员管理 ==========
  listAdminUsers: () => http.get('/admin/users'),
  createAdminUser: (data) => http.post('/admin/users', data),
  deleteAdminUser: (id) => http.delete(`/admin/users/${id}`),
  resetAdminPassword: (id, newPassword) => http.post(`/admin/users/${id}/reset-password`, { newPassword }),
  updateAdminUser: (id, data) => http.put(`/admin/users/${id}`, data),

  // ========== 角色 / RBAC ==========
  permissionsRegistry: () => http.get('/permissions/registry'),
  listRoles: () => http.get('/admin/roles'),
  getRole: (id) => http.get(`/admin/roles/${id}`),
  createRole: (data) => http.post('/admin/roles', data),
  updateRole: (id, data) => http.put(`/admin/roles/${id}`, data),
  deleteRole: (id) => http.delete(`/admin/roles/${id}`),

  // ========== 外部邀请码（管理端）==========
  listInvites: () => http.get('/admin/invites'),
  createInvite: (data) => http.post('/admin/invites', data),
  updateInvite: (id, data) => http.put(`/admin/invites/${id}`, data),
  deleteInvite: (id) => http.delete(`/admin/invites/${id}`),
  listInviteUses: (id) => http.get(`/admin/invites/${id}/uses`),

  // ========== 外部入口（无需登录）==========
  externalVerify: (code) => http.post('/external/verify', { code }),
  externalSubmit: (payload) => http.post('/external/submit', payload),
  externalUseStatus: (useId, code, token) => http.get(`/external/use/${useId}`, { params: { code, token } }),
  externalRetry: (useId, code, token) => http.post(`/external/use/${useId}/retry`, { code, token }),
  externalHistory: (code, token) => http.get('/external/history', { params: { code, token } }),

  // ========== 外部拓词（无需登录，与查词共用邀请码，无次数限制）==========
  extExpandVerify: (code) => http.post('/external/expand/verify', { code }),
  extExpandCreate: (payload) => http.post('/external/expand/tasks', payload),
  extExpandUpload: (taskId, file, code, token) => {
    const fd = new FormData()
    fd.append('file', file)
    return http.post(`/external/expand/tasks/${taskId}/files`, fd, {
      params: { code, token },
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 120000,
    })
  },
  extExpandDeleteFile: (taskId, fileId, code, token) =>
    http.delete(`/external/expand/tasks/${taskId}/files/${fileId}`, { params: { code, token } }),
  extExpandRun: (taskId, payload) => http.post(`/external/expand/tasks/${taskId}/run`, payload),
  extExpandStatus: (taskId, code, token) =>
    http.get(`/external/expand/tasks/${taskId}`, { params: { code, token } }),
  extExpandResults: (taskId, code, token) =>
    http.get(`/external/expand/tasks/${taskId}/results`, { params: { code, token } }),
  extExpandHistory: (code, token) =>
    http.get('/external/expand/history', { params: { code, token } }),

  // ========== 报告相关 ==========
  getShareInfo: (shareCode) => http.get(`/share-info/${shareCode}`),
  getOverview: (shareCode) => http.get(`/overview/${shareCode}`),
  getRanking: (shareCode, platform) => http.get(`/ranking/${shareCode}`, { params: { platform } }),
  getQuestions: (shareCode, platform, page = 1, pageSize = 50) =>
    http.get(`/questions/${shareCode}`, { params: { platform, page, pageSize } }),
  getOptimizeDetail: (id) => http.get(`/optimize-detail/${id}`),

  // ========== 账号管理 ==========
  listAccounts: (params = {}) => http.get('/accounts', { params }),
  getAccounts: (includeTemp = false, includeDraft = false) => http.get('/accounts', { params: { ...(includeTemp ? { include_temp: 1 } : {}), ...(includeDraft ? { include_draft: 1 } : {}) } }),
  getAccount: (id) => http.get(`/accounts/${id}`),
  createAccount: (data) => http.post('/accounts', data),
  updateAccount: (id, data) => http.put(`/accounts/${id}`, data),
  patchAccount: (id, data) => http.patch(`/accounts/${id}`, data),
  promoteAccount: (id, data) => http.post(`/accounts/${id}/promote`, data),
  deleteAccount: (id) => http.delete(`/accounts/${id}`),
  getAccountKeywords: (id) => http.get(`/accounts/${id}/keywords`),
  updateAccountKeywords: (id, keywords) => http.put(`/accounts/${id}/keywords`, keywords),

  // ========== 查词功能 ==========
  getAccountSummary: (includeExternal = false) => http.get('/search/account-summary', { params: includeExternal ? { include_external: 1 } : {} }),
  deleteAllSearchHistory: (accountId) => http.delete(`/search/history/${accountId}/all`),
  // 按 search_task.id 精确删除一次任务（区别于按日期删一整天）
  deleteSearchTask: (taskId) => http.delete(`/search/task/${taskId}`),
  // 回收站
  getRecycleBin: () => http.get('/accounts/recycle-bin'),
  restoreAccount: (accountId) => http.post(`/accounts/${accountId}/restore`),
  purgeAccount: (accountId) => http.delete(`/accounts/${accountId}/purge`),
  // 归档
  archiveAccount: (accountId) => http.post(`/accounts/${accountId}/archive`),
  unarchiveAccount: (accountId) => http.post(`/accounts/${accountId}/unarchive`),
  getArchivedAccounts: () => http.get('/accounts/archived'),
  purgeArchivedAccount: (accountId) => http.delete(`/accounts/${accountId}/purge-archived`),
  // 客户改派（仅 admin/super_admin）
  transferAccount: (accountId, newOwnerId) => http.post(`/accounts/${accountId}/transfer`, { newOwnerId }),
  // 设置多业务负责人（仅 admin/super_admin）
  setAccountOwners: (accountId, ownerIds) => http.post(`/accounts/${accountId}/owners`, { ownerIds }),
  // 团队管理
  listTeams: () => http.get('/teams'),
  createTeam: (data) => http.post('/teams', data),
  updateTeam: (id, data) => http.put(`/teams/${id}`, data),
  deleteTeam: (id) => http.delete(`/teams/${id}`),
  setAccountTeam: (accountId, teamId) => http.post(`/accounts/${accountId}/team`, { teamId }),
  startSearch: (accountId, body = null) => http.post(`/search/start/${accountId}`, body || {}),
  startTempSearch: (body) => http.post(`/search/start-temp`, body || {}),
  getSearchProgress: (taskId) => http.get(`/search/progress/${taskId}`),
  getSearchProgressLog: (taskId) => http.get(`/search/progress-log/${taskId}`),
  cancelSearch: (taskId) => http.post(`/search/cancel/${taskId}`),
  getSearchResults: (accountId, date) => http.get(`/search/results/${accountId}`, { params: { date } }),
  accuracyRun: (accountId, date) => http.post(`/accuracy/run/${accountId}`, { date }),
  accuracyStatus: (accountId, date) => http.get(`/accuracy/status/${accountId}`, { params: { date } }),
  accuracyList: (accountId, date) => http.get(`/accuracy/list/${accountId}`, { params: { date } }),
  getSearchHistory: (accountId) => http.get(`/search/history/${accountId}`),
  getTodayStats: () => http.get('/search/today-stats'),
  getHomeOverview: () => http.get('/home/overview'),
  retryFailed: (taskId) => http.post(`/search/retry-failed/${taskId}`),
  continueSearch: (accountId) => http.post(`/search/continue/${accountId}`),
  getUnsearchedCount: (accountId) => http.get(`/search/unsearched-count/${accountId}`),
  getRunningTask: (accountId) => http.get(`/search/running/${accountId}`),
  exportSearchResults: (accountId, date) => `/api/search/export/${accountId}?date=${date}`,
  exportSearchByAccount: (accountId) => `/api/search/export-account/${accountId}`,

  // ========== 品牌排名 ==========
  getBrandRanking: (accountId, dates) => http.get(`/search/brand-ranking/${accountId}`, { params: { dates } }),
  reanalyzeBrand: (accountId, date) => http.post(`/search/reanalyze/${accountId}`, null, { params: { date } }),

  // ========== 引用源分析 ==========
  getCitationDates: (accountId) => http.get(`/citation/dates/${accountId}`),
  getCitationUrls: (accountId, date, countOnly = false) => http.get(`/citation/urls/${accountId}`, { params: { date, ...(countOnly ? { count_only: 1 } : {}) } }),
  getCitationResults: (accountId, date) => http.get(`/citation/results/${accountId}`, { params: { date } }),
  getCitationResult: (accountId, date, url) => http.get(`/citation/result/${accountId}`, { params: { date, url } }),
  startCitationScrape: (accountId, data) => http.post(`/citation/scrape/start/${accountId}`, data),
  cancelCitationScrape: (taskId) => http.post(`/citation/scrape/cancel/${taskId}`),
  getRunningCitationScrapes: () => http.get('/citation/scrape/running'),
  getCitationScrapeTask: (taskId) => http.get(`/citation/scrape/task/${taskId}`),
  getCitationScrapeEvents: (taskId, after) => http.get(`/citation/scrape/events/${taskId}`, { params: { after } }),
  extractCitationMeta: (accountId, date) => http.post(`/citation/extract/${accountId}`, { date }),

  getQuoteAvailableData: (accountId) => http.get(`/quote/available-data/${accountId}`),

  // ========== 系统设置 ==========
  getSettings: () => http.get('/settings'),
  updateSettings: (data) => http.put('/settings', data),

  // ========== 排名分析 ==========
  getToolTasks: () => http.get('/rank-tool/tasks'),
  submitRankingAnalysis: (formData) => http.post('/rank-tool/submit', formData),
  submitRankingUpload: (formData) => http.post('/ranking/submit-upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } }),
  getRankingProgress: (taskId, after) => http.get(`/rank-tool/progress/${taskId}`, { params: { after } }),
  getRankingResults: (taskId) => http.get(`/rank-tool/results/${taskId}`),
  getRankingDetail: (accountId) => http.get(`/rank-tool/detail/${accountId}`),
  getRankingSummary: (accountId) => http.get(`/rank-tool/summary/${accountId}`),
  retryRanking: (taskId) => http.post(`/rank-tool/retry/${taskId}`),
  getRankingHistory: (params = {}) => http.get('/rank-tool/history', { params: { limit: 500, ...params } }),
  getRankingTrends: (brandName) => http.get('/rank-tool/trends', { params: { brand_name: brandName } }),
  getRankingBrands: () => http.get('/rank-tool/brands'),
  exportRankingCSV: (taskId) => `/api/rank-tool/export/${taskId}`,
  exportRankingByAccount: (accountId) => `/api/rank-tool/export-account/${accountId}`,
  deleteRanking: (taskId) => http.post(`/rank-tool/delete/${taskId}`),
  deleteSearchHistory: (accountId, date) => http.delete(`/search/history/${accountId}`, { params: { date } }),
  deleteCitationTask: (taskId) => http.delete(`/citation/scrape/task/${taskId}`),
  deleteCitationByDate: (accountId, date) => http.delete(`/citation/scrape/by-date/${accountId}`, { params: { date } }),
  deleteQuoteTask: (taskId) => http.delete(`/quote/task/${taskId}`),
  getRunningRanking: () => http.get('/rank-tool/running'),
  cancelRanking: (taskId) => http.post(`/rank-tool/cancel/${taskId}`),
  continueRanking: (taskId) => http.post(`/rank-tool/continue/${taskId}`),
  rerunRanking: (taskId) => http.post(`/rank-tool/rerun/${taskId}`),
  getRankingAccountHistory: (accountId) => http.get(`/rank-tool/account-history/${accountId}`),

  // ========== 定时排名分析 ==========
  listRankingSchedules: () => http.get('/rank-tool/schedule/list'),
  createRankingSchedule: (data) => http.post('/rank-tool/schedule/create', data),
  updateRankingSchedule: (id, data) => http.put(`/rank-tool/schedule/${id}`, data),
  deleteRankingSchedule: (id) => http.delete(`/rank-tool/schedule/${id}`),
  toggleRankingSchedule: (id) => http.post(`/rank-tool/schedule/${id}/toggle`),
  triggerRankingSchedule: (id) => http.post(`/rank-tool/schedule/${id}/trigger`),

  // ========== 定时查词调度 ==========
  triggerScheduledTask: (id) => http.post(`/scheduler/tasks/${id}/trigger`),
  getSchedulerExecutionSummary: () => http.get('/scheduler/execution-summary'),
  getAccountExecutionHistory: (accountId, limit = 10) => http.get(`/search/history/${accountId}`, { params: { limit } }),
  getAccountExecutionHistoryGrouped: (accountId, limitDates = 20) => http.get(`/search/account-history-grouped/${accountId}`, { params: { limitDates } }),

  // ========== 定时引用源分析 ==========
  listCitationSchedules: () => http.get('/citation-tool/schedule/list'),
  createCitationSchedule: (data) => http.post('/citation-tool/schedule/create', data),
  updateCitationSchedule: (id, data) => http.put(`/citation-tool/schedule/${id}`, data),
  deleteCitationSchedule: (id) => http.delete(`/citation-tool/schedule/${id}`),
  toggleCitationSchedule: (id) => http.post(`/citation-tool/schedule/${id}/toggle`),
  triggerCitationSchedule: (id) => http.post(`/citation-tool/schedule/${id}/trigger`),

  // ========== 定时报价 ==========
  listQuoteSchedules: () => http.get('/quote-tool/schedule/list'),
  createQuoteSchedule: (data) => http.post('/quote-tool/schedule/create', data),
  updateQuoteSchedule: (id, data) => http.put(`/quote-tool/schedule/${id}`, data),
  deleteQuoteSchedule: (id) => http.delete(`/quote-tool/schedule/${id}`),
  toggleQuoteSchedule: (id) => http.post(`/quote-tool/schedule/${id}/toggle`),
  triggerQuoteSchedule: (id) => http.post(`/quote-tool/schedule/${id}/trigger`),

  // ========== 批量/流水线任务 ==========
  listPipelineSchedules: () => http.get('/pipeline-tool/schedule/list'),
  createPipelineSchedule: (data) => http.post('/pipeline-tool/schedule/create', data),
  updatePipelineSchedule: (id, data) => http.put(`/pipeline-tool/schedule/${id}`, data),
  deletePipelineSchedule: (id) => http.delete(`/pipeline-tool/schedule/${id}`),
  togglePipelineSchedule: (id) => http.post(`/pipeline-tool/schedule/${id}/toggle`),
  triggerPipelineSchedule: (id) => http.post(`/pipeline-tool/schedule/${id}/trigger`),
  listPipelineExecutions: (id, limit = 20) => http.get(`/pipeline-tool/schedule/${id}/executions`, { params: { limit } }),

  // ========== 周报管理 ==========
  listWeeklyReports: (accountId, limit = 30) => http.get(`/accounts/${accountId}/weekly-reports`, { params: { limit } }),
  listWeeklyModules: (type) => http.get('/weekly-reports/modules', { params: type ? { type } : undefined }),
  generateWeeklyReport: (accountId, periodStart, periodEnd, reportType, modules, allowMissing, brandMode, includeBrandWords) => http.post(`/accounts/${accountId}/weekly-reports/generate`, { periodStart, periodEnd, reportType: reportType || 'weekly', modules: Array.isArray(modules) && modules.length ? modules : undefined, allowMissing: allowMissing || undefined, brandMode: brandMode || undefined, includeBrandWords: includeBrandWords === undefined ? undefined : !!includeBrandWords }),
  getWeeklyReport: (reportId) => http.get(`/weekly-reports/${reportId}`),
  updateWeeklyReportExpiry: (accountId, reportId, days) =>
    http.put(`/accounts/${accountId}/weekly-reports/${reportId}/expiry`, { days }),
  deleteWeeklyReport: (reportId) => http.delete(`/weekly-reports/${reportId}`),
  weeklyReportHtmlUrl: (reportId) => `/api/weekly-reports/${reportId}/html`,
  weeklyReportDownloadUrl: (reportId) => `/api/weekly-reports/${reportId}/download`,

  getShareToken: (accountId) => http.get(`/accounts/${accountId}/share-token`),
  resetShareToken: (accountId) => http.post(`/accounts/${accountId}/share-token/reset`),

  getReportShareToken: (reportId) => http.get(`/weekly-reports/${reportId}/share-token`),
  resetReportShareToken: (reportId) => http.post(`/weekly-reports/${reportId}/share-token/reset`),

  getWeeklySchedule: (accountId) => http.get(`/accounts/${accountId}/weekly-schedule`),
  createWeeklySchedule: (accountId, data) => http.post(`/accounts/${accountId}/weekly-schedule`, data),
  updateWeeklySchedule: (schedId, data) => http.put(`/weekly-schedules/${schedId}`, data),
  deleteWeeklySchedule: (schedId) => http.delete(`/weekly-schedules/${schedId}`),
  triggerWeeklySchedule: (schedId) => http.post(`/weekly-schedules/${schedId}/trigger`),

  // ========== 生文分析(content analysis) ==========
  generateContentAnalysis: (accountId) => http.post('/content-analysis/generate', { accountId }),
  getContentAnalysis: (accountId) => http.get(`/content-analysis/${accountId}`),
  batchContentAnalysis: (ids) => http.get('/content-analysis/batch', { params: { ids: (ids || []).join(',') } }),
  contentAnalysisDownloadUrl: (accountId, docType) => `/api/content-analysis/${accountId}/download/${docType}`,
  generateSourceInsight: (accountId) => http.post(`/content-analysis/${accountId}/source-insight/generate`),
  getSourceInsight: (accountId) => http.get(`/content-analysis/${accountId}/source-insight`),
  // ========== 发稿要求 / 写作心得 / Prompt 预览 ==========
  getWritingRequirements: (accountId) => http.get(`/account/${accountId}/writing-requirements`),
  saveWritingRequirements: (accountId, data) => http.put(`/account/${accountId}/writing-requirements`, data),
  listWritingLessons: (accountId) => http.get(`/account/${accountId}/writing-lessons`),
  createWritingLesson: (accountId, data) => http.post(`/account/${accountId}/writing-lessons`, data),
  updateWritingLesson: (id, data) => http.patch(`/writing-lessons/${id}`, data),
  deleteWritingLesson: (id) => http.delete(`/writing-lessons/${id}`),
  previewPrompt: (data) => http.post('/content/preview-prompt', data),
  refineRules: (accountId, rawText) => http.post(`/account/${accountId}/refine-rules`, { raw_text: rawText }),

  // ========== 定时任务管理 ==========
  listScheduledTasks: (params) => http.get('/scheduled-tasks', { params }),
  getScheduledTask: (id) => http.get(`/scheduled-tasks/${id}`),
  createScheduledTask: (data) => http.post('/scheduled-tasks', data),
  updateScheduledTask: (id, data) => http.put(`/scheduled-tasks/${id}`, data),
  deleteScheduledTask: (id) => http.delete(`/scheduled-tasks/${id}`),
  triggerScheduledTask: (id) => http.post(`/scheduled-tasks/${id}/trigger`),
  toggleScheduledTask: (id, enabled) => http.put(`/scheduled-tasks/${id}/toggle`, { enabled }),
  // 使用查询参数方式获取历史记录（复用任务详情接口，避免路由匹配问题）
  getScheduledTaskHistory: (id, limit = 50) => http.get(`/scheduled-tasks/${id}`, { params: { include_history: '1', history_limit: limit } }),
}
