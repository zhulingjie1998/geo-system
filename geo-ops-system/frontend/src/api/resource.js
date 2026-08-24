import axios from 'axios'

const http = axios.create({
  baseURL: '/api/resource',
  timeout: 60000,
  withCredentials: true,
})

http.interceptors.response.use(
  (res) => res.data,
  (err) => {
    console.error('Resource API Error:', err)
    return Promise.reject(err)
  },
)

export default {
  // ── 站点 CRUD ──
  listSites: (type) => {
    const params = type ? { type } : {}
    return http.get('/sites', { params })
  },

  createSite: (data) => http.post('/sites', data),

  updateSite: (id, data) => http.put(`/sites/${id}`, data),

  deleteSite: (id) => http.delete(`/sites/${id}`),

  testSite: (id) => http.post(`/sites/${id}/test`),

  // 批量导入（items 为对象数组，支持中文 key）
  batchImport: (items) => http.post('/sites/batch-import', { items }),

  // ── 发布 ──
  publish: (data) => http.post('/publish', {
    site_ids: data.site_ids || [],
    account_id: data.account_id || null,
    article_id: data.article_id || null,
    title: data.title || '',
    content: data.content || '',
    status: data.status || 'publish',
    category_ids: data.category_ids || null,
  }),

  // 发布记录
  listRecords: (params = {}) => http.get('/publish/records', { params }),
}
