<template>
  <div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
      <span style="font-size:14px;color:#666">
        角色定义 = 数据可见范围 + 可访问页面。系统内置 3 个角色（超管不可改），可自定义新角色。
      </span>
      <el-button type="primary" size="small" @click="openCreate">新增角色</el-button>
    </div>

    <el-table :data="roles" border stripe style="width:100%">
      <el-table-column prop="name" label="角色名" width="160">
        <template #default="{ row }">
          <span>{{ row.name }}</span>
          <el-tag v-if="row.isBuiltin" type="info" size="small" style="margin-left:6px">内置</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="code" label="标识" width="140" />
      <el-table-column label="数据范围" width="140">
        <template #default="{ row }">
          <el-tag v-if="row.dataScope === 'all'" type="warning" size="small">全部数据</el-tag>
          <el-tag v-else-if="row.dataScope === 'team'" type="success" size="small">看团队数据</el-tag>
          <el-tag v-else size="small">仅自己创建</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="页面权限" min-width="320">
        <template #default="{ row }">
          <template v-if="row.code === 'super_admin'">
            <el-tag size="small" type="danger">全部页面</el-tag>
          </template>
          <template v-else>
            <el-tag v-for="p in row.pages" :key="p" size="small" style="margin-right:4px;margin-bottom:2px">{{ pageLabel(p) }}</el-tag>
            <span v-if="!row.pages?.length" style="color:#999;font-size:12px">无页面权限</span>
          </template>
        </template>
      </el-table-column>
      <el-table-column prop="userCount" label="用户数" width="80" align="center" />
      <el-table-column prop="description" label="描述" min-width="160" show-overflow-tooltip />
      <el-table-column label="操作" width="160">
        <template #default="{ row }">
          <el-button size="small" :disabled="row.code === 'super_admin'" @click="openEdit(row)">编辑</el-button>
          <el-button size="small" type="danger" :disabled="row.isBuiltin || row.userCount > 0" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 新增 / 编辑 角色 -->
    <el-dialog v-model="dialogVisible" :title="isEditing ? '编辑角色' : '新增角色'" width="min(720px, 92vw)" top="6vh">
      <el-form label-width="100px">
        <el-form-item label="角色名">
          <el-input v-model="form.name" placeholder="如「运营主管」" maxlength="20" show-word-limit />
        </el-form-item>
        <el-form-item v-if="!isEditing" label="标识">
          <el-input v-model="form.code" placeholder="留空自动生成；自定义建议英文小写下划线" maxlength="40" />
          <div style="font-size:12px;color:#999;margin-top:4px">系统内置 super_admin / admin / operator 不可用</div>
        </el-form-item>
        <el-form-item label="数据范围">
          <el-radio-group v-model="form.dataScope">
            <el-radio v-for="ds in registry.dataScopes" :key="ds.value" :value="ds.value">{{ ds.label }}</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" placeholder="可选" maxlength="200" show-word-limit />
        </el-form-item>
        <el-form-item label="页面权限">
          <div style="width:100%">
            <div style="margin-bottom:8px">
              <el-button size="small" link @click="selectAllPages">全选</el-button>
              <el-divider direction="vertical" />
              <el-button size="small" link @click="clearPages">清空</el-button>
              <el-divider direction="vertical" />
              <span style="color:#999;font-size:12px">已选 {{ form.pages.length }} / {{ totalPageCount }}</span>
            </div>
            <el-checkbox-group v-model="form.pages">
              <div v-for="(items, group) in registry.groups" :key="group" style="margin-bottom:12px">
                <div style="font-size:13px;color:#666;font-weight:600;margin-bottom:6px">
                  {{ group }}
                  <el-button size="small" link style="margin-left:8px" @click="toggleGroup(group)">
                    {{ allInGroupSelected(group) ? '取消本组' : '全选本组' }}
                  </el-button>
                </div>
                <el-checkbox v-for="p in items" :key="p.key" :value="p.key" style="margin-right:18px;margin-bottom:6px">
                  {{ p.label }}
                </el-checkbox>
              </div>
            </el-checkbox-group>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible=false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api'

const roles = ref([])
const registry = reactive({ groups: {}, pages: [], dataScopes: [] })
const dialogVisible = ref(false)
const isEditing = ref(false)
const editingId = ref(null)
const saving = ref(false)
const form = reactive({
  name: '',
  code: '',
  dataScope: 'team',
  description: '',
  pages: [],
})

const totalPageCount = computed(() => registry.pages.length)

function pageLabel(key) {
  const found = registry.pages.find(p => p.key === key)
  return found ? found.label : key
}

function allInGroupSelected(group) {
  const items = registry.groups[group] || []
  return items.length > 0 && items.every(p => form.pages.includes(p.key))
}

function toggleGroup(group) {
  const items = registry.groups[group] || []
  const keys = items.map(p => p.key)
  if (allInGroupSelected(group)) {
    form.pages = form.pages.filter(k => !keys.includes(k))
  } else {
    const merged = new Set([...form.pages, ...keys])
    form.pages = [...merged]
  }
}

function selectAllPages() {
  form.pages = registry.pages.map(p => p.key)
}

function clearPages() {
  form.pages = []
}

function resetForm() {
  form.name = ''
  form.code = ''
  form.dataScope = 'team'
  form.description = ''
  form.pages = []
}

async function loadAll() {
  try {
    const [reg, rls] = await Promise.all([api.permissionsRegistry(), api.listRoles()])
    registry.groups = reg.groups || {}
    registry.pages = reg.pages || []
    registry.dataScopes = reg.dataScopes || []
    roles.value = rls || []
  } catch (e) {
    ElMessage.error(e?.response?.data?.error || '加载失败')
  }
}

function openCreate() {
  isEditing.value = false
  editingId.value = null
  resetForm()
  dialogVisible.value = true
}

function openEdit(row) {
  isEditing.value = true
  editingId.value = row.id
  form.name = row.name
  form.code = row.code
  form.dataScope = row.dataScope
  form.description = row.description || ''
  form.pages = [...(row.pages || [])]
  dialogVisible.value = true
}

async function submit() {
  if (!form.name.trim()) { ElMessage.warning('请填写角色名'); return }
  saving.value = true
  try {
    const payload = {
      name: form.name.trim(),
      dataScope: form.dataScope,
      description: form.description.trim(),
      pages: form.pages,
    }
    if (isEditing.value) {
      await api.updateRole(editingId.value, payload)
      ElMessage.success('角色已更新')
    } else {
      if (form.code.trim()) payload.code = form.code.trim().toLowerCase()
      await api.createRole(payload)
      ElMessage.success('角色已创建')
    }
    dialogVisible.value = false
    await loadAll()
  } catch (e) {
    ElMessage.error(e?.response?.data?.error || '保存失败')
  } finally {
    saving.value = false
  }
}

async function handleDelete(row) {
  await ElMessageBox.confirm(`确认删除角色 "${row.name}" ？此操作不可恢复。`, '警告', { type: 'warning' })
  try {
    await api.deleteRole(row.id)
    ElMessage.success('已删除')
    await loadAll()
  } catch (e) {
    ElMessage.error(e?.response?.data?.error || '删除失败')
  }
}

onMounted(loadAll)
</script>
