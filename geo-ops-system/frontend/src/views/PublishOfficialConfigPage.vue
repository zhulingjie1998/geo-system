<template>
  <div class="official-config-page">
    <section class="panel">
      <el-table
        :data="rows"
        v-loading="loading"
        row-key="accountId"
        :header-cell-style="{ background: '#fafbfc', color: '#64748b', fontWeight: 600, fontSize: '13px' }"
      >
        <el-table-column label="客户" min-width="320">
          <template #default="{ row }">
            <div class="customer-cell">
              <div class="avatar" :style="{ background: avatarColor(row) }">{{ avatarLetter(row) }}</div>
              <div class="customer-info">
                <div class="brand-line">{{ displayBrand(row) || '—' }}</div>
                <div class="company-line">{{ row.companyName || '—' }}</div>
              </div>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="对接情况" width="140" align="center">
          <template #default="{ row }">
            <el-tag :type="row.configured ? 'success' : 'info'" effect="plain">
              {{ row.configured ? '已配置' : '未配置' }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="160" align="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" plain @click="openConfig(row)">HTTP设置</el-button>
          </template>
        </el-table-column>

        <template #empty>
          <div class="table-empty">暂无客户数据</div>
        </template>
      </el-table>
    </section>

    <el-dialog v-model="dialogVisible" title="HTTP设置" width="760px" top="6vh" :close-on-click-modal="false">
      <div v-if="currentRow" class="dialog-body">
        <div class="meta-line">
          <strong>{{ displayBrand(currentRow) || '—' }}</strong>
          <span>{{ currentRow.companyName || '—' }}</span>
        </div>

        <el-form label-position="top">
          <el-form-item label="链接地址">
            <el-input v-model="form.webhookUrl" placeholder="请输入 webhook 链接地址，如 https://api.example.com/webhook/publish" />
          </el-form-item>

          <el-form-item label="OAuth2 令牌（每个客户固定，可复制给客户）">
            <el-input :model-value="form.oauthToken || form.oauthTokenMasked || '保存后自动生成'" readonly>
              <template #append>
                <el-button @click="copyToken">复制</el-button>
              </template>
            </el-input>
          </el-form-item>

          <el-form-item label="JSON 示例（按内容格式）">
            <el-radio-group v-model="contentFormat" class="format-switch">
              <el-radio-button label="html">HTML</el-radio-button>
              <el-radio-button label="md">Markdown</el-radio-button>
            </el-radio-group>
            <pre class="json-box">{{ contentFormat === 'html' ? payloadTemplateHtml : payloadTemplateMd }}</pre>
          </el-form-item>
        </el-form>
      </div>

      <template #footer>
        <el-button @click="dialogVisible = false">关闭</el-button>
        <el-button type="primary" @click="saveConfig">保存设置</el-button>
        <el-button
          v-if="currentRow && currentRow.configured"
          type="danger"
          plain
          @click="clearConfig"
        >取消设置</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/api'
import publishApi from '@/api/publish'

const loading = ref(false)
const rows = ref([])
const dialogVisible = ref(false)
const currentRow = ref(null)
const form = ref({ webhookUrl: '', oauthToken: '', oauthTokenMasked: '' })
const contentFormat = ref('html')

const payloadTemplateHtml = JSON.stringify({
  postId: 'aaad5jipsscnxwgq',
  content: '<h2>Understanding QuickCreator AI</h2><h3>What is QuickCreator?</h3><h4>Overview of QuickCreator...</h4>',
  slug: 'page-slug',
  title: 'Post Title',
  seo: {
    title: 'Title for meta tag',
    description: 'Description for meta tag',
    keywords: 'Keywords for meta tag',
    feature_image: 'https://statics.mylandingpages.co/static/af26c522mp/image/5b6f2d2c176d44.png',
  },
}, null, 2)

const payloadTemplateMd = JSON.stringify({
  postId: 'aaad5jipsscnxwgq',
  content: '## Understanding QuickCreator AI\n\n### What is QuickCreator?\n\nQuickCreator is an AI-powered content platform...',
  slug: 'page-slug',
  title: 'Post Title',
  seo: {
    title: 'Title for meta tag',
    description: 'Description for meta tag',
    keywords: 'Keywords for meta tag',
    feature_image: 'https://statics.mylandingpages.co/static/af26c522mp/image/5b6f2d2c176d44.png',
  },
}, null, 2)

function normalizeBrands(raw) {
  if (Array.isArray(raw)) return raw.map(x => String(x || '').trim()).filter(Boolean)
  if (typeof raw !== 'string') return []
  const s = raw.trim()
  if (!s) return []
  if (s.startsWith('[') && s.endsWith(']')) {
    try {
      const arr = JSON.parse(s)
      return Array.isArray(arr) ? arr.map(x => String(x || '').trim()).filter(Boolean) : []
    } catch {
      return [s]
    }
  }
  if (s.includes('/')) return s.split('/').map(x => x.trim()).filter(Boolean)
  if (s.includes('、')) return s.split('、').map(x => x.trim()).filter(Boolean)
  if (s.includes(',')) return s.split(',').map(x => x.trim()).filter(Boolean)
  return [s]
}

function displayBrand(row) {
  const brands = normalizeBrands(row.companyBrand || row.companyBrands || row.brand || '')
  return brands.join(' / ')
}

function avatarLetter(row) {
  const txt = displayBrand(row) || row.companyName || '?'
  return String(txt).charAt(0) || '?'
}

function avatarColor(row) {
  const colors = ['#6366f1', '#10b981', '#ec4899', '#f59e0b', '#14b8a6', '#8b5cf6']
  const seed = displayBrand(row) || row.companyName || ''
  let hash = 0
  for (let i = 0; i < seed.length; i++) hash = seed.charCodeAt(i) + ((hash << 5) - hash)
  return colors[Math.abs(hash) % colors.length]
}

async function loadRows() {
  loading.value = true
  try {
    // 客户列表始终与客户管理同步
    const accounts = await api.listAccounts()
    const baseRows = (Array.isArray(accounts) ? accounts : []).map((acc) => ({
      accountId: Number(acc.id),
      companyName: acc.companyName || '',
      companyBrand: acc.companyBrand || '',
      configured: false,
      webhookUrl: '',
      oauthToken: '',
      oauthTokenMasked: '',
      updatedAt: '',
    }))

    // 官网配置接口可用时再叠加配置状态；不可用时静默保持客户列表
    try {
      const res = await publishApi.officialConfigList()
      const cfgItems = Array.isArray(res?.items) ? res.items : []
      const cfgMap = new Map(cfgItems.map((x) => [Number(x.accountId), x]))
      rows.value = baseRows.map((row) => {
        const cfg = cfgMap.get(Number(row.accountId)) || {}
        return {
          ...row,
          configured: !!cfg.configured,
          webhookUrl: cfg.webhookUrl || '',
          oauthToken: cfg.oauthToken || '',
          oauthTokenMasked: cfg.oauthTokenMasked || '',
          updatedAt: cfg.updatedAt || '',
        }
      }).sort((a, b) => {
        const ta = a.updatedAt || a.createdAt || ''
        const tb = b.updatedAt || b.createdAt || ''
        return tb.localeCompare(ta)
      })
    } catch {
      rows.value = [...baseRows].sort((a, b) => {
        const ta = a.updatedAt || a.createdAt || ''
        const tb = b.updatedAt || b.createdAt || ''
        return tb.localeCompare(ta)
      })
    }
  } catch (e) {
    rows.value = []
    ElMessage.error(e?.response?.data?.error || e?.message || '加载客户数据失败')
  } finally {
    loading.value = false
  }
}

async function openConfig(row) {
  currentRow.value = row
  dialogVisible.value = true
  form.value = {
    webhookUrl: row.webhookUrl || '',
    oauthToken: row.oauthToken || '',
    oauthTokenMasked: row.oauthTokenMasked || '',
  }
  try {
    const detail = await publishApi.officialConfigGet(row.accountId)
    form.value.webhookUrl = detail.webhookUrl || ''
    form.value.oauthToken = detail.oauthToken || form.value.oauthToken
    form.value.oauthTokenMasked = detail.oauthTokenMasked || ''
  } catch {
    // ignore
  }
}

async function copyToken() {
  const token = (form.value.oauthToken || '').trim()
  if (!token) {
    ElMessage.warning('暂无可复制令牌，请先保存设置生成')
    return
  }
  try {
    await navigator.clipboard.writeText(token)
    ElMessage.success('令牌已复制')
  } catch {
    ElMessage.warning('复制失败，请手动复制')
  }
}

async function saveConfig() {
  if (!currentRow.value) return
  if (!form.value.webhookUrl.trim()) {
    ElMessage.warning('请先填写链接地址')
    return
  }
  try {
    const result = await publishApi.officialConfigSave(currentRow.value.accountId, {
      webhookUrl: form.value.webhookUrl.trim(),
    })
    form.value.oauthToken = result.oauthToken || ''
    form.value.oauthTokenMasked = result.oauthTokenMasked || ''
    ElMessage.success('配置保存成功')
    dialogVisible.value = false
    await loadRows()
  } catch (e) {
    if (e?.response?.status === 405) {
      ElMessage.error('保存接口方法不匹配（后端仅允许 GET）。请将后端升级到支持 PUT/POST 保存接口的版本。')
      return
    }
    if (e?.response?.status === 404) {
      ElMessage.error('保存接口不存在，请将后端升级到官网配置接口版本。')
      return
    }
    ElMessage.error(e?.response?.data?.error || e?.message || '保存失败')
  }
}

async function clearConfig() {
  if (!currentRow.value) return
  await ElMessageBox.confirm('确认取消该客户的 HTTP 设置？取消后将清空配置并更新状态。', '二次确认', {
    type: 'warning',
    confirmButtonText: '确认取消',
    cancelButtonText: '返回',
  })
  try {
    await publishApi.officialConfigClear(currentRow.value.accountId)
    ElMessage.success('已取消设置')
    dialogVisible.value = false
    await loadRows()
  } catch (e) {
    if (e?.response?.status === 405) {
      ElMessage.error('取消接口方法不匹配（后端仅允许 GET）。请将后端升级到支持 DELETE 的版本。')
      return
    }
    if (e?.response?.status === 404) {
      ElMessage.error('取消接口不存在，请将后端升级到官网配置接口版本。')
      return
    }
    ElMessage.error(e?.response?.data?.error || e?.message || '取消设置失败')
  }
}

onMounted(loadRows)
</script>

<style scoped>
.official-config-page { display: flex; flex-direction: column; gap: 16px; }
.panel {
  background: #fff;
  border: 1px solid #eef1f6;
  border-radius: 12px;
  padding: 14px 16px;
}

.customer-cell { display: flex; align-items: center; gap: 12px; }
.avatar {
  width: 40px; height: 40px; border-radius: 10px;
  color: #fff; font-weight: 700; font-size: 16px;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.brand-line { font-size: 14px; font-weight: 600; color: #0f172a; line-height: 1.25; }
.company-line { margin-top: 4px; font-size: 13px; color: #94a3b8; line-height: 1.25; }
.table-empty { padding: 28px 0; text-align: center; color: #94a3b8; }

.meta-line {
  display: flex;
  gap: 12px;
  align-items: baseline;
  margin-bottom: 8px;
}
.meta-line strong { color: #0f172a; }
.meta-line span { color: #64748b; font-size: 13px; }

.format-switch {
  margin-bottom: 8px;
}

.json-box {
  margin: 0;
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
  max-height: 240px;
  overflow: auto;
  line-height: 1.5;
  font-size: 12px;
  color: #334155;
}
</style>
