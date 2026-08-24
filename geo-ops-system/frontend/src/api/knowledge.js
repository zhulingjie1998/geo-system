import axios from 'axios'

const http = axios.create({
  baseURL: '/api/kb',
  timeout: 60000,
  withCredentials: true,
})

http.interceptors.response.use(
  (res) => res.data,
  (err) => {
    console.error('KB API Error:', err)
    return Promise.reject(err)
  },
)

export const KB_TYPES = [
  { value: 'basic',        label: '基础信息' },
  { value: 'product',      label: '产品/服务' },
  { value: 'case',         label: '案例' },
  { value: 'news',         label: '新闻动态' },
  { value: 'faq',          label: 'FAQ' },
  { value: 'competitor',   label: '竞品' },
  { value: 'brand_story',  label: '品牌故事' },
  { value: 'custom',       label: '自定义' },
]

export const KB_STATUS = [
  { value: 'active',   label: '启用' },
  { value: 'draft',    label: '草稿' },
  { value: 'archived', label: '归档' },
]

export function kbTypeLabel(v) {
  return KB_TYPES.find(t => t.value === v)?.label || v || '-'
}
export function kbStatusLabel(v) {
  return KB_STATUS.find(t => t.value === v)?.label || v || '-'
}

export default {
  listPaidAccounts: (formalOnly = false) => http.get('/accounts', { params: formalOnly ? { formal: 1 } : {} }),
  list: (params) => http.get('', { params }),
  stats: (accountId) => http.get('/stats', { params: { account_id: accountId } }),
  get: (id) => http.get(`/${id}`),
  create: (data) => http.post('', data),
  update: (id, data) => http.put(`/${id}`, data),
  remove: (id) => http.delete(`/${id}`),

  importText: (data) => http.post('/import/text', data),
  importUrl: (data) => http.post('/import/url', data),
  importCsvFile: (file, accountId, kbType = 'basic') => {
    const fd = new FormData()
    fd.append('file', file)
    if (accountId) fd.append('account_id', accountId)
    if (kbType) fd.append('kb_type', kbType)
    return axios.post('/api/kb/import/csv', fd, {
      withCredentials: true,
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then(r => r.data)
  },
  importCsvText: (csvText, accountId, kbType = 'basic') =>
    http.post('/import/csv', { csv: csvText, account_id: accountId, kb_type: kbType }),

  // ── 知识库审核 ──
  reviewStart: (accountId, kbVersionId) =>
    http.post('/review', { account_id: accountId, kb_version_id: kbVersionId }),
  reviewGet: (reviewId) => http.get(`/review/${reviewId}`),
  reviewAddAnno: (reviewId, data) => http.post(`/review/${reviewId}/annotation`, data),
  reviewUpdAnno: (annoId, data) => http.put(`/review/annotation/${annoId}`, data),
  reviewDelAnno: (annoId) => http.delete(`/review/annotation/${annoId}`),
  reviewMaterials: (reviewId, materials) =>
    http.put(`/review/${reviewId}/materials`, { materials }),
  reviewFinalize: (reviewId) => http.post(`/review/${reviewId}/finalize`),
}

// 批注三分类(与后端 CATEGORIES 对应)
export const KB_REVIEW_CATEGORIES = [
  { value: 'numeric', label: '数值类', color: '#d97706' },
  { value: 'discrepancy', label: '出入类', color: '#dc2626' },
  { value: 'promotion', label: '宣传口径', color: '#7c3aed' },
]
export function kbReviewCategoryLabel(v) {
  return KB_REVIEW_CATEGORIES.find(c => c.value === v)?.label || v || '-'
}
export function kbReviewCategoryColor(v) {
  return KB_REVIEW_CATEGORIES.find(c => c.value === v)?.color || '#6b7280'
}
