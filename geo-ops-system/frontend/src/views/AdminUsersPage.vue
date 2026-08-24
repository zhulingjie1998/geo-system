<template>
  <div class="au-page">
    <el-tabs v-model="activeTab" class="au-tabs">
    <el-tab-pane label="账号与团队" name="users">
    <!-- ── 角色总览(三角色卡,参考智能发布框架)── -->
    <section class="au-card">
      <header class="au-head">
        <div class="au-head-l">
          <h3>角色总览</h3>
          <span class="au-badge">团队负责人 / 运营人员</span>
        </div>
        <div v-if="currentRole==='super_admin'" class="au-head-r">
          <el-button size="small" @click="activeTab = 'roles'">编辑角色权限 →</el-button>
        </div>
      </header>

      <div class="role-grid">
        <div
          v-for="r in roleCards"
          :key="r.code"
          class="role-card"
          :style="{ '--role-color': r.color }"
        >
          <div class="role-head">
            <span class="role-icon">{{ r.icon }}</span>
            <div class="role-title">
              <div class="role-name">{{ r.name }}</div>
              <div class="role-summary">{{ r.summary }}</div>
            </div>
            <el-tag :type="r.tagType" effect="light" size="default" class="role-count">{{ r.count }} 人</el-tag>
          </div>

          <div class="role-meta">
            <span :class="['meta-chip', r.code==='super_admin' ? 'danger' : '']">
              {{ r.code==='super_admin' ? '🔒 系统保留,不可在 UI 创建' : ('数据范围 · ' + r.scopeLabel) }}
            </span>
          </div>

          <div class="role-detail">{{ r.description }}</div>

          <div class="role-pages">
            <div class="pages-label">可见模块（{{ r.pages.length }}）</div>
            <div class="pages-groups">
              <div v-for="g in r.groupedPages" :key="g.group" class="pages-group">
                <span class="pages-group-name">{{ g.group }}</span>
                <span class="pages-group-list">
                  <el-tag v-for="p in g.items" :key="p.key" size="small" effect="plain" class="page-pill">{{ p.label }}</el-tag>
                </span>
              </div>
              <div v-if="!r.groupedPages.length" class="pages-empty">按勾选分配,当前无固定页面</div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- ── 团队管理(仅 super_admin)── -->
    <section v-if="currentRole==='super_admin'" class="au-card">
      <header class="au-head">
        <div class="au-head-l">
          <h3>团队管理</h3>
          <span class="au-badge">{{ teams.length }} 个团队</span>
        </div>
        <div class="au-team-create">
          <el-button type="primary" size="small" @click="showTeamDialog = true">+ 建团队</el-button>
        </div>
      </header>

      <div v-if="!teams.length" class="au-empty">还没有团队,在右上方创建。新增账号时把成员分到团队即可。</div>
      <div v-else class="team-grid">
        <div v-for="t in teams" :key="t.id" class="team-card">
          <div class="tc-top">
            <el-input v-model="t.name" size="small" class="tc-name" @change="(v)=>renameTeam(t, v)" />
            <span class="tc-stat">{{ t.memberCount }} 人 · {{ t.accountCount }} 客户</span>
          </div>
          <div class="tc-leader">
            <span class="tc-label">负责人</span>
            <el-select :model-value="t.leaderUserId" size="small" clearable filterable
                       placeholder="设负责人" style="flex:1"
                       @change="(v)=>changeLeader(t, v)">
              <el-option v-for="u in leaderCandidates" :key="u.id" :label="u.username" :value="u.id"
                        :disabled="isLeaderOfOtherTeam(u.id, t.id)" />
            </el-select>
          </div>
          <div class="tc-members">
            <el-tag v-for="m in membersOf(t.id)" :key="m.id"
                    :type="m.id===t.leaderUserId ? 'warning' : 'info'" effect="plain" size="small" class="tc-mtag">
              {{ m.username }}<span v-if="m.id===t.leaderUserId"> · 负责人</span>
            </el-tag>
            <span v-if="!membersOf(t.id).length" class="tc-empty">暂无成员</span>
          </div>
          <div class="tc-bottom">
            <el-button type="danger" text size="small" class="tc-del" @click="handleDeleteTeam(t)">删除</el-button>
          </div>
        </div>
      </div>
    </section>

    <!-- ── 成员账号 ── -->
    <section class="au-card">
      <header class="au-head">
        <div class="au-head-l">
          <h3>{{ currentRole==='super_admin' ? '账号明细' : '团队成员' }}</h3>
          <span class="au-badge">{{ users.length }} 个账号</span>
        </div>
        <div class="au-head-r">
          <el-button type="primary" size="small" @click="openCreate">
            {{ currentRole==='super_admin' ? '+ 新增账号' : '+ 添加运营人' }}
          </el-button>
        </div>
      </header>

      <el-table :data="users" stripe style="width:100%">
        <el-table-column prop="id" label="ID" width="56" />
        <el-table-column prop="username" label="用户名" min-width="130" />
        <el-table-column label="角色" width="120">
          <template #default="{ row }">
            <el-tag v-if="row.role === 'super_admin'" type="danger" size="small">{{ row.roleName || '超级管理员' }}</el-tag>
            <el-tag v-else-if="row.role === 'admin'" type="warning" size="small">{{ row.roleName || '团队负责人' }}</el-tag>
            <el-tag v-else size="small">{{ row.roleName || '运营人员' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="数据范围" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.dataScope === 'all'" type="warning" size="small" effect="plain">看全部</el-tag>
            <el-tag v-else-if="row.dataScope === 'team'" type="success" size="small" effect="plain">本团队</el-tag>
            <el-tag v-else size="small" effect="plain">仅自己</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="团队" width="120">
          <template #default="{ row }">
            <el-tag v-if="row.teamName" size="small" type="info" effect="plain">{{ row.teamName }}</el-tag>
            <span v-else style="color:#c0c4cc">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="lastLoginAt" label="最后登录" width="160" />
        <el-table-column label="操作" width="220">
          <template #default="{ row }">
            <el-button size="small" :disabled="!canManageRow(row)" @click="openEdit(row)">编辑</el-button>
            <el-button size="small" :disabled="!canManageRow(row)" @click="openReset(row)">重置密码</el-button>
            <el-button size="small" type="danger" plain :disabled="!canManageRow(row) || row.id === currentUserId" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>
    </el-tab-pane>

    <el-tab-pane v-if="isSuper" label="角色与权限" name="roles">
      <RolesPage />
    </el-tab-pane>
    </el-tabs>

    <!-- 新增账号 -->
    <el-dialog v-model="createVisible" title="新增账号" width="min(480px, 90vw)">
      <el-form label-width="90px">
        <el-form-item label="用户名"><el-input v-model="createForm.username" placeholder="请输入用户名" /></el-form-item>
        <el-form-item label="密码"><el-input v-model="createForm.password" show-password placeholder="至少 8 位" /></el-form-item>
        <el-form-item label="角色">
          <el-select v-model="createForm.roleId" placeholder="请选择角色" style="width:100%">
            <el-option v-for="r in assignableRoles" :key="r.id" :label="r.name" :value="r.id">
              <span>{{ r.name }}</span>
              <span style="float:right;color:#999;font-size:12px">{{ scopeLabel(r.dataScope) }}</span>
            </el-option>
          </el-select>
          <div v-if="selectedCreateRole" class="role-hint">{{ selectedCreateRole.description || '该角色拥有 ' + selectedCreateRole.pages.length + ' 项页面权限' }}</div>
        </el-form-item>
        <el-form-item label="所属团队">
          <el-select v-if="currentRole==='super_admin'" v-model="createForm.teamId" clearable placeholder="(可选)选择团队" style="width:100%">
            <el-option v-for="t in teams" :key="t.id" :label="t.name" :value="t.id" />
          </el-select>
          <span v-else style="color:#909399;font-size:13px">自动归入你所在的团队</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible=false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitCreate">确定</el-button>
      </template>
    </el-dialog>

    <!-- 编辑账号 -->
    <el-dialog v-model="editVisible" title="编辑账号" width="min(480px, 90vw)">
      <el-form label-width="90px">
        <el-form-item label="用户名"><el-input :model-value="editForm.username" disabled /></el-form-item>
        <el-form-item label="角色">
          <el-select v-model="editForm.roleId" placeholder="请选择角色" style="width:100%">
            <el-option v-for="r in assignableRoles" :key="r.id" :label="r.name" :value="r.id">
              <span>{{ r.name }}</span>
              <span style="float:right;color:#999;font-size:12px">{{ scopeLabel(r.dataScope) }}</span>
            </el-option>
          </el-select>
          <div v-if="selectedEditRole" class="role-hint">{{ selectedEditRole.description || '该角色拥有 ' + selectedEditRole.pages.length + ' 项页面权限' }}</div>
        </el-form-item>
        <el-form-item v-if="currentRole==='super_admin'" label="所属团队">
          <el-select v-model="editForm.teamId" clearable placeholder="(未分配)" style="width:100%">
            <el-option v-for="t in teams" :key="t.id" :label="t.name" :value="t.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible=false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 重置密码 -->
    <el-dialog v-model="resetVisible" title="重置密码" width="min(400px, 90vw)">
      <p style="margin-bottom:12px">目标用户: <strong>{{ resetTarget?.username }}</strong></p>
      <el-input v-model="resetPw" show-password placeholder="新密码（至少 8 位）" />
      <template #footer>
        <el-button @click="resetVisible=false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitReset">确定</el-button>
      </template>
    </el-dialog>

    <!-- ── 建团队弹窗 ── -->
    <el-dialog v-model="showTeamDialog" title="创建新团队" width="420px">
      <el-form label-width="80px">
        <el-form-item label="团队名称" required>
          <el-input v-model="newTeamName" placeholder="请输入团队名称" maxlength="30" show-word-limit />
        </el-form-item>
        <el-form-item label="负责人">
          <el-select v-model="newTeamLeader" clearable filterable placeholder="可选，稍后也可设置" style="width:100%">
            <el-option v-for="u in leaderCandidates" :key="u.id" :label="u.username" :value="u.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showTeamDialog=false">取消</el-button>
        <el-button type="primary" :loading="teamSaving" @click="submitCreateTeam">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api'
import RolesPage from './RolesPage.vue'

// 权限管理合并页：账号与团队 / 角色与权限 两个 Tab；?tab=roles 直达角色 Tab（仅超管）
const route = useRoute()
const currentRole = computed(() => localStorage.getItem('geo_role') || 'operator')
const isSuper = computed(() => currentRole.value === 'super_admin')
const activeTab = ref(route.query.tab === 'roles' && isSuper.value ? 'roles' : 'users')
const currentUserId = computed(() => {
  const v = localStorage.getItem('geo_user_id')
  return v ? Number(v) : null
})

const users = ref([])
const allRoles = ref([])
const registry = reactive({ groups: {}, pages: [] })
const createVisible = ref(false)
const editVisible = ref(false)
const resetVisible = ref(false)
const saving = ref(false)
const createForm = reactive({ username: '', password: '', roleId: null, teamId: null })
const editForm = reactive({ id: null, username: '', roleId: null, teamId: null })
const resetTarget = ref(null)
const resetPw = ref('')

// 团队
const teams = ref([])
const newTeamName = ref('')
const newTeamLeader = ref(null)
const teamSaving = ref(false)
const showTeamDialog = ref(false)
const leaderCandidates = computed(() =>
  users.value.filter(u => ['admin', 'super_admin'].includes((u.role || '').toLowerCase())))

// 角色视觉元数据(icon/颜色/概述),按 code 映射
const ROLE_META = {
  super_admin: { icon: '🛡', color: '#dc2626', tagType: 'danger',
    summary: '系统最高权限,看全部数据',
    description: '所有业务功能 + 团队管理 / 角色管理 / 外部邀请码 / 系统设置;可跨团队查看与操作。只能由数据库引导,不可在界面创建。' },
  admin: { icon: '👔', color: '#d97706', tagType: 'warning',
    summary: '管理本团队 + 全部业务工具',
    description: '本团队所有业务功能 + 团队成员管理(新增 / 删除 / 改密本团队运营人);不可访问角色管理 / 外部邀请码 / 系统设置。' },
  operator: { icon: '🛠', color: '#16a34a', tagType: 'success',
    summary: '执行人员,仅看自己接管的客户',
    description: '按分配的业务页可见,只看自己 owner 的客户数据;不可访问团队管理 / 角色管理 / 系统设置。' },
}

// 各角色人数
const roleCount = computed(() => {
  const m = {}
  for (const u of users.value) {
    const code = (u.role || 'operator').toLowerCase()
    m[code] = (m[code] || 0) + 1
  }
  return m
})

// page key → {label, group}
const pageMeta = computed(() => {
  const map = {}
  for (const p of registry.pages || []) map[p.key] = { label: p.label, group: p.group }
  return map
})

// 角色卡数据(合并 allRoles + meta + count + 分组页面)
const roleCards = computed(() => {
  // 固定顺序:负责人 → 运营(超级管理员不对外展示)
  const order = ['admin', 'operator']
  const byCode = {}
  for (const r of allRoles.value) byCode[r.code] = r
  return order.filter(code => byCode[code]).map(code => {
    const r = byCode[code]
    const meta = ROLE_META[code] || { icon: '•', color: '#64748b', tagType: 'info', summary: '', description: '' }
    // super_admin 看全部,role.pages 可能为空,用 registry 全量
    const pageKeys = (code === 'super_admin' && (!r.pages || !r.pages.length))
      ? (registry.pages || []).map(p => p.key)
      : (r.pages || [])
    // 分组
    const groupMap = {}
    for (const k of pageKeys) {
      const pm = pageMeta.value[k]
      if (!pm) continue
      ;(groupMap[pm.group] = groupMap[pm.group] || []).push({ key: k, label: pm.label })
    }
    const groupedPages = Object.keys(groupMap).map(group => ({ group, items: groupMap[group] }))
    return {
      code, name: r.name, ...meta,
      count: roleCount.value[code] || 0,
      scopeLabel: scopeLabel(r.dataScope),
      pages: pageKeys,
      groupedPages,
    }
  })
})

const assignableRoles = computed(() => allRoles.value.filter(r => {
  if (r.code === 'super_admin') return false
  if (currentRole.value === 'super_admin') return true
  if (currentRole.value === 'admin') return r.code !== 'admin'
  return false
}))
const selectedCreateRole = computed(() => allRoles.value.find(r => r.id === createForm.roleId))
const selectedEditRole = computed(() => allRoles.value.find(r => r.id === editForm.roleId))

function scopeLabel(s) { return s === 'all' ? '看全部' : (s === 'team' ? '本团队' : '仅自己') }

function canManageRow(row) {
  const target = (row.role || '').toLowerCase()
  if (currentRole.value === 'super_admin') return target !== 'super_admin'
  if (currentRole.value === 'admin') return target !== 'super_admin' && target !== 'admin'
  return false
}
function membersOf(teamId) { return users.value.filter(u => u.teamId === teamId) }

// 判断用户是否已是其他团队的负责人
function isLeaderOfOtherTeam(userId, currentTeamId) {
  return teams.value.some(t => t.id !== currentTeamId && t.leaderUserId === userId)
}

// 获取负责人当前负责的团队（用于提示）
function getLeaderCurrentTeam(userId) {
  const t = teams.value.find(t => t.leaderUserId === userId)
  return t ? t.name : ''
}

async function loadAll() {
  try {
    const [u, r] = await Promise.all([api.listAdminUsers(), api.listRoles()])
    users.value = u || []
    allRoles.value = r || []
  } catch (e) {
    ElMessage.error(e?.response?.data?.error || '加载失败')
  }
  try { teams.value = await api.listTeams() || [] } catch { teams.value = [] }
  try {
    const reg = await api.permissionsRegistry()
    registry.groups = reg?.groups || {}
    registry.pages = reg?.pages || []
  } catch { /* 注册表拉取失败不阻塞主功能 */ }
}

function openCreate() {
  createForm.username = ''
  createForm.password = ''
  createForm.teamId = null
  createForm.roleId = assignableRoles.value[0]?.id || null
  createVisible.value = true
}

async function submitCreate() {
  if (!createForm.username || createForm.password.length < 8) {
    ElMessage.warning('用户名不能为空且密码至少 8 位'); return
  }
  if (!createForm.roleId) { ElMessage.warning('请选择角色'); return }
  saving.value = true
  try {
    await api.createAdminUser({
      username: createForm.username,
      password: createForm.password,
      roleId: createForm.roleId,
      teamId: createForm.teamId || undefined,
    })
    ElMessage.success('创建成功')
    createVisible.value = false
    await loadAll()
  } catch (e) {
    ElMessage.error(e?.response?.data?.error || '创建失败')
  } finally { saving.value = false }
}

function openEdit(row) {
  editForm.id = row.id
  editForm.username = row.username
  editForm.roleId = row.roleId || allRoles.value.find(r => r.code === row.role)?.id || null
  editForm.teamId = row.teamId || null
  editVisible.value = true
}

async function submitEdit() {
  saving.value = true
  try {
    const payload = { roleId: editForm.roleId }
    if (currentRole.value === 'super_admin') payload.teamId = editForm.teamId || null
    await api.updateAdminUser(editForm.id, payload)
    ElMessage.success('保存成功')
    editVisible.value = false
    await loadAll()
  } catch (e) {
    ElMessage.error(e?.response?.data?.error || '保存失败')
  } finally { saving.value = false }
}

function openReset(row) { resetTarget.value = row; resetPw.value = ''; resetVisible.value = true }
async function submitReset() {
  if (resetPw.value.length < 8) { ElMessage.warning('密码至少 8 位'); return }
  saving.value = true
  try {
    await api.resetAdminPassword(resetTarget.value.id, resetPw.value)
    ElMessage.success('密码已重置')
    resetVisible.value = false
  } catch (e) {
    ElMessage.error(e?.response?.data?.error || '重置失败')
  } finally { saving.value = false }
}

async function handleDelete(row) {
  await ElMessageBox.confirm(`确认删除账号 "${row.username}" ？`, '警告', { type: 'warning' })
  try {
    await api.deleteAdminUser(row.id)
    ElMessage.success('已删除')
    await loadAll()
  } catch (e) {
    ElMessage.error(e?.response?.data?.error || '删除失败')
  }
}

// ── 团队 ──
async function submitCreateTeam() {
  if (!newTeamName.value.trim()) { ElMessage.warning('请输入团队名称'); return }
  teamSaving.value = true
  try {
    await api.createTeam({ name: newTeamName.value.trim(), leaderUserId: newTeamLeader.value || null })
    ElMessage.success('团队已创建')
    newTeamName.value = ''
    newTeamLeader.value = null
    showTeamDialog.value = false
    await loadAll()
  } catch (e) {
    ElMessage.error(e?.response?.data?.error || '创建失败')
  } finally { teamSaving.value = false }
}
async function changeLeader(row, leaderId) {
  try {
    // 如果选择的新负责人已经是其他团队的负责人
    if (leaderId) {
      const existingTeam = teams.value.find(t => t.id !== row.id && t.leaderUserId === leaderId)
      if (existingTeam) {
        await ElMessageBox.confirm(
          `「${getUsername(leaderId)}」当前是「${existingTeam.name}」的负责人，是否将其转移到本团队？`,
          '转移负责人',
          { type: 'warning', confirmButtonText: '确认转移', cancelButtonText: '取消' }
        )
        // 先清除原团队的负责人
        await api.updateTeam(existingTeam.id, { leaderUserId: null })
      }
    }
    await api.updateTeam(row.id, { leaderUserId: leaderId || null })
    ElMessage.success(`已更新「${row.name}」负责人`)
    await loadAll()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error(e?.response?.data?.error || '更新失败')
    }
  }
}

function getUsername(userId) {
  const u = users.value.find(u => u.id === userId)
  return u ? u.username : ''
}
async function renameTeam(row, name) {
  const nm = (name || '').trim()
  if (!nm) { ElMessage.warning('团队名不能为空'); await loadAll(); return }
  try {
    await api.updateTeam(row.id, { name: nm })
    ElMessage.success('团队名已更新')
    await loadAll()
  } catch (e) {
    ElMessage.error(e?.response?.data?.error || '改名失败')
    await loadAll()
  }
}
async function handleDeleteTeam(row) {
  await ElMessageBox.confirm(`确认删除团队「${row.name}」？删除后不可恢复。`, '删除团队', { type: 'warning' })
  try {
    await api.deleteTeam(row.id)
    ElMessage.success('团队已删除')
    await loadAll()
  } catch (e) {
    ElMessage.error(e?.response?.data?.error || '删除失败')
  }
}

onMounted(loadAll)
</script>

<style scoped>
.au-page { display: flex; flex-direction: column; gap: 16px; }
/* 合并页 Tab：账号与团队 / 角色与权限 */
.au-tabs :deep(.el-tabs__header) { margin-bottom: 16px; }
.au-tabs :deep(.el-tabs__item) { font-size: 14px; font-weight: 600; }
.au-tabs :deep(.el-tab-pane) { display: flex; flex-direction: column; gap: 16px; }
.au-card { background: #fff; border: 1px solid #eef0f4; border-radius: 14px; padding: 18px 20px;
  box-shadow: 0 1px 3px rgba(0,0,0,.03); }
.au-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; gap: 10px; }
.au-head-l { display: flex; align-items: baseline; gap: 10px; }
.au-head-l h3 { margin: 0; font-size: 16px; font-weight: 700; color: #1e1b4b; }
.au-badge { font-size: 12px; color: #6b7280; background: #f1f5f9; padding: 2px 10px; border-radius: 999px; }
.au-head-r { display: flex; gap: 8px; }
.au-team-create { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.au-empty { color: #9ca3af; font-size: 13px; padding: 20px; text-align: center; background: #fafbfc; border-radius: 8px; }

/* —— 角色卡 —— */
.role-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.role-card {
  --role-color: #16a34a;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-top: 4px solid var(--role-color);
  border-radius: 12px;
  padding: 16px 18px;
  display: flex; flex-direction: column; gap: 12px;
  min-height: 240px;
}
.role-head { display: flex; align-items: center; gap: 12px; }
.role-icon { font-size: 28px; line-height: 1; }
.role-title { flex: 1; min-width: 0; }
.role-name { font-size: 15px; font-weight: 600; color: #1e293b; }
.role-summary { font-size: 12.5px; color: var(--role-color); margin-top: 2px; }
.role-count { font-weight: 600; }
.role-meta { font-size: 12px; }
.meta-chip {
  display: inline-block; padding: 3px 8px; border-radius: 6px;
  background: color-mix(in srgb, var(--role-color) 8%, white);
  color: var(--role-color);
}
.meta-chip.danger { background: #fef2f2; color: #b91c1c; }
.role-detail {
  font-size: 12.5px; color: #475569; line-height: 1.7;
  padding: 8px 10px; background: #f8fafc; border-radius: 6px;
}
.role-pages { display: flex; flex-direction: column; gap: 6px; }
.pages-label { font-size: 12px; color: #64748b; font-weight: 600; }
.pages-groups { display: flex; flex-direction: column; gap: 6px; }
.pages-group { display: flex; align-items: flex-start; gap: 8px; font-size: 12px; }
.pages-group-name { flex: 0 0 64px; color: #64748b; padding-top: 4px; }
.pages-group-list { flex: 1; display: flex; flex-wrap: wrap; gap: 4px; }
.page-pill { font-size: 11.5px; }
.pages-empty { font-size: 12px; color: #c0c4cc; }

/* —— 团队卡 —— */
.team-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; }
.team-card { border: 1px solid #eef0f4; border-radius: 12px; padding: 14px; background: linear-gradient(180deg,#fafbff,#fff);
  display: flex; flex-direction: column; gap: 10px; transition: box-shadow .15s, border-color .15s; }
.team-card:hover { border-color: #c4b5fd; box-shadow: 0 2px 10px rgba(124,58,237,.08); }
.tc-top { display: flex; align-items: center; gap: 8px; justify-content: space-between; }
.tc-name { flex: 1; }
.tc-name :deep(.el-input__wrapper) { font-weight: 600; }
.tc-stat { font-size: 11.5px; color: #94a3b8; white-space: nowrap; }
.tc-del { flex-shrink: 0; }
.tc-bottom { display: flex; justify-content: flex-end; padding-top: 8px; border-top: 1px solid #f0f0f0; margin-top: auto; }
.tc-leader { display: flex; align-items: center; gap: 8px; }
.tc-label { font-size: 12.5px; color: #6b7280; white-space: nowrap; }
.tc-members { display: flex; flex-wrap: wrap; gap: 5px; min-height: 24px; }
.tc-mtag { margin: 0; }
.tc-empty { font-size: 12px; color: #c0c4cc; }

.role-hint { background: #f0f9ff; color: #0c5460; font-size: 12px; padding: 6px 10px; border-radius: 4px; margin-top: 4px; line-height: 1.5; }

@media (max-width: 980px) { .role-grid { grid-template-columns: 1fr; } }
</style>
