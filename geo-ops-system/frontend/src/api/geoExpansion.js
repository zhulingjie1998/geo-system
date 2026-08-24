import axios from 'axios'

const http = axios.create({
  baseURL: '/api/geo-expansion',
  timeout: 120000, // 拓词可能耗时较长
  withCredentials: true,
})

http.interceptors.response.use(
  (res) => {
    const body = res.data
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
    console.error('GeoExpansion API Error:', err)
    return Promise.reject(err)
  },
)

export default {
  // ── 数据概览 ──
  getOverview: () => http.get('/overview'),

  // ── 任务列表 ──
  listTasks: (status) => {
    const params = status ? { status } : {}
    return http.get('/tasks', { params })
  },

  // ── 创建任务 ──
  createTask: (data) => http.post('/tasks', data),

  // ── 执行任务 ──
  runTask: (taskId) => http.post(`/tasks/${taskId}/run`),

  // ── 任务详情（含提示词） ──
  getTaskDetail: (taskId) => http.get(`/tasks/${taskId}`),

  // ── 删除任务 ──
  deleteTask: (taskId) => http.delete(`/tasks/${taskId}`),

  // ── 导出 Excel/CSV ──
  exportTask: (taskId) => {
    return axios.get(`/api/geo-expansion/tasks/${taskId}/export`, {
      responseType: 'blob',
      withCredentials: true,
    })
  },

  // ── 客户列表 ──
  getAccounts: () => http.get('/accounts'),

  // ── 拓词指令配置 ──
  getInstruction: () => http.get('/instruction'),
  saveInstruction: (instruction) => http.put('/instruction', { instruction }),
}
