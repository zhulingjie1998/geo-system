<template>
  <div class="settings-page">
    <div class="settings-layout">
      <!-- 二级导航:大类 + 子项,大类可折叠 -->
      <nav class="settings-nav">
        <div class="nav-head">系统设置</div>
        <div v-for="g in navGroups" :key="g.key" class="nav-group">
          <button class="nav-grp-head" @click="toggleGroup(g.key)">
            <el-icon :size="14" class="nav-grp-icon" :class="'nav-grp-icon-' + g.key">
              <component :is="g.icon" />
            </el-icon>
            <span class="nav-grp-label">{{ g.label }}</span>
            <el-icon :size="11" class="nav-grp-caret" :class="{ collapsed: collapsedGroups[g.key] }">
              <ArrowDown />
            </el-icon>
          </button>
          <transition name="nav-expand">
            <div v-show="!collapsedGroups[g.key]" class="nav-children">
              <button
                v-for="c in g.children" :key="c.key"
                class="nav-child"
                :class="{ on: sec === c.key }"
                @click="goSection(c.key)"
              >
                <span class="nav-child-label">{{ c.label }}</span>
                <span class="nav-child-chip" :class="'chip-' + statusOf(c.key).tone">
                  {{ statusOf(c.key).text }}
                </span>
              </button>
            </div>
          </transition>
        </div>
      </nav>

      <div class="settings-main">
        <!-- 顶部:面包屑 + H1 + 保存按钮 -->
        <div class="main-head">
          <div class="breadcrumb">
            <span>设置</span>
            <el-icon :size="11"><ArrowRight /></el-icon>
            <span>{{ currentGroupLabel }}</span>
            <el-icon :size="11"><ArrowRight /></el-icon>
            <span class="bc-current">{{ currentSectionLabel }}</span>
          </div>
          <div class="head-row">
            <div class="head-text">
              <h1 class="head-title">
                <el-icon :size="20" class="head-icon" :class="'nav-grp-icon-' + currentGroup">
                  <component :is="currentGroupIcon" />
                </el-icon>
                {{ currentSectionLabel }}
              </h1>
              <p class="head-desc">{{ currentSectionDesc }}</p>
            </div>
            <!-- 每张卡片各自有「保存」按钮，顶部不再有全局保存 -->
          </div>
        </div>

      <!-- ===== 查词接口 ===== -->
      <section v-show="sec === 'search'">

      <div class="panel">
        <div class="panel-header">
          <h3>AI 查词接口</h3>
          <el-tag size="small" effect="plain" type="warning">当前接口无需配置（开发阶段已内置）</el-tag>
        </div>
        <div class="panel-body">
          <div class="field-hint" style="margin-bottom:12px;color:#909399">
            <el-icon :size="14"><InfoFilled /></el-icon>
            查词功能已对接底层代码，支持 ChatGPT、Google AIO/AIM、Gemini、Perplexity、Copilot 共 6 个平台。此处保留配置项供后续使用。
          </div>
          <div class="grid-2col">
            <div class="field">
              <label>统一 API URL</label>
              <el-input v-model="form.search_api_url" placeholder="查词接口地址（可选，留空使用默认配置）" />
            </div>
            <div class="field">
              <label>统一 API Key</label>
              <el-input v-model="form.search_api_key" type="password" show-password placeholder="API Key（可选）" />
            </div>
          </div>
        </div>
        <div class="panel-foot">
          <span v-if="savedFlash==='searchApis'" class="pf-saved"><el-icon><CircleCheckFilled /></el-icon> 已保存</span>
          <span v-else-if="cardDirty('searchApis')" class="pf-dirty"><span class="dot dot-dirty"></span> 未保存</span>
          <el-button type="primary" size="small" :loading="cardSaving==='searchApis'" :disabled="!cardDirty('searchApis')" @click="saveCard('searchApis')">保存配置</el-button>
        </div>
      </div>

      </section>

      <!-- ===== AI模型 ===== -->
      <section v-show="sec === 'analysis'">


      <div class="panel">
        <div class="panel-header">
          <h3>AI 模型配置</h3>
          <span class="active-dot">{{ analysisModelLabel }} 启用中</span>
        </div>
        <div class="panel-body">
          <div class="api-tabs">
            <div
              class="api-tab"
              :class="{ active: analysisTab === 'claude' }"
              @click="switchTab('claude')"
            >Claude</div>
            <div
              class="api-tab"
              :class="{ active: analysisTab === 'chatgpt' }"
              @click="switchTab('chatgpt')"
            >ChatGPT</div>
            <div
              class="api-tab"
              :class="{ active: analysisTab === 'qwen' }"
              @click="switchTab('qwen')"
            >通义千问</div>
          </div>

          <!-- Claude 配置 -->
          <div v-show="analysisTab === 'claude'" class="tab-content">
            <div class="grid-2col">
              <div class="field">
                <label>API Base URL</label>
                <el-input v-model="form.llm_base_url" placeholder="https://api.anthropic.com" />
              </div>
              <div class="field">
                <label>超时（秒）</label>
                <el-input v-model="form.llm_timeout" placeholder="120" />
              </div>
            </div>
            <div class="grid-2col" style="margin-top: 8px;">
              <div class="field">
                <label>Model Name</label>
                <el-input v-model="form.claude_model_name" placeholder="claude-sonnet-4-20250514" />
              </div>
              <div class="field">
                <label>API Key</label>
                <el-input v-model="form.claude_api_key" type="password" show-password :placeholder="apiKeyHints.claude || '输入 Anthropic API Key'" />
              </div>
            </div>
          </div>

          <!-- ChatGPT 配置 -->
          <div v-show="analysisTab === 'chatgpt'" class="tab-content">
            <div class="grid-2col">
              <div class="field">
                <label>API Base URL</label>
                <el-input v-model="form.chatgpt_base_url" placeholder="https://api.openai.com/v1" />
              </div>
              <div class="field">
                <label>超时（秒）</label>
                <el-input v-model="form.chatgpt_timeout" placeholder="120" />
              </div>
            </div>
            <div class="grid-2col" style="margin-top: 8px;">
              <div class="field">
                <label>Model Name</label>
                <el-input v-model="form.chatgpt_model_name" placeholder="gpt-4o-mini" />
              </div>
              <div class="field">
                <label>API Key</label>
                <el-input v-model="form.chatgpt_api_key" type="password" show-password :placeholder="apiKeyHints.chatgpt || '输入 OpenAI API Key'" />
              </div>
            </div>
          </div>

          <!-- 通义千问配置 -->
          <div v-show="analysisTab === 'qwen'" class="tab-content">
            <div class="grid-2col">
              <div class="field">
                <label>API Base URL</label>
                <el-input v-model="form.qwen_base_url" placeholder="https://dashscope.aliyuncs.com/compatible-mode/v1" />
              </div>
              <div class="field">
                <label>超时（秒）</label>
                <el-input v-model="form.qwen_timeout" placeholder="300" />
              </div>
            </div>
            <div class="grid-2col" style="margin-top: 8px;">
              <div class="field">
                <label>Model Name</label>
                <el-input v-model="form.qwen_model_name" placeholder="qwen-plus 或 qwen3.7-plus" />
              </div>
              <div class="field">
                <label>API Key</label>
                <el-input v-model="form.qwen_api_key" type="password" show-password :placeholder="apiKeyHints.qwen || '输入 DashScope API Key'" />
              </div>
            </div>
          </div>
        </div>
        <div class="panel-foot">
          <span v-if="savedFlash==='analysis'" class="pf-saved"><el-icon><CircleCheckFilled /></el-icon> 已保存</span>
          <span v-else-if="cardDirty('analysis')" class="pf-dirty"><span class="dot dot-dirty"></span> 未保存</span>
          <el-button type="primary" size="small" :loading="cardSaving==='analysis'" :disabled="!cardDirty('analysis')" @click="saveCard('analysis')">保存</el-button>
        </div>
      </div>

      </section>

      <!-- ===== 引用源抓取 ===== -->

      <!-- ===== 报价配置 ===== -->

      <!-- ===== 自动化 ===== -->
      <!-- ===== 知识库解析指令 ===== -->
      <section v-show="sec === 'kb-instructions'">
        <div class="panel">
          <div class="panel-header">
            <h3>知识库解析指令</h3>
            <el-tag size="small" effect="plain" type="info">AI 生成/优化知识库时使用此提示词模板</el-tag>
          </div>
          <div class="panel-body">
            <div class="field">
              <label>系统提示词（Markdown 格式）</label>
              <el-input
                v-model="form.kb_instruction_md"
                type="textarea"
                :rows="18"
                placeholder="输入知识库解析的系统提示词，支持 Markdown 格式..."
                class="kb-inst-textarea"
              />
              <div class="field-hint">
                此指令包含「资料智能识别指令」和「知识库生成指令」两部分。
                资料识别指令在 AI 识别基础资料时使用；知识库生成指令在 AI 生成或优化知识库时使用。
              </div>
            </div>
          </div>
          <div class="panel-foot">
            <span v-if="savedFlash==='kbInstructions'" class="pf-saved"><el-icon><CircleCheckFilled /></el-icon> 已保存</span>
            <span v-else-if="cardDirty('kbInstructions')" class="pf-dirty"><span class="dot dot-dirty"></span> 未保存</span>
            <el-button type="primary" size="small" :loading="cardSaving==='kbInstructions'" :disabled="!cardDirty('kbInstructions')" @click="saveCard('kbInstructions')">保存</el-button>
          </div>
        </div>
      </section>


      <!-- ===== GEO 拓词指令 ===== -->
      <section v-show="sec === 'geo-expansion'">
        <div class="panel">
          <div class="panel-header">
            <h3>GEO 拓词指令</h3>
            <el-tag size="small" effect="plain" type="info">创建拓词任务时使用此提示词模板</el-tag>
          </div>
          <div class="panel-body">
            <div class="field">
              <label>系统提示词（Markdown 格式）</label>
              <el-input
                v-model="form.geo_expansion_instruction"
                type="textarea"
                :rows="20"
                placeholder="输入 GEO 拓词的系统提示词，支持 Markdown 格式...&#10;&#10;示例：&#10;你是一个GEO(生成式引擎优化)专家。根据用户需求生成搜索提示词。&#10;&#10;## 输出格式要求(JSON数组)&#10;[&#10;  {&#10;    &quot;intent_category&quot;: &quot;意图分类&quot;,&#10;    &quot;core_intent_word&quot;: &quot;核心意图词&quot;,&#10;    &quot;prompt&quot;: &quot;完整的搜索提示词问句&quot;&#10;  }&#10;]"
                class="kb-inst-textarea"
              />
              <div class="field-hint">
                此指令将在创建 GEO 拆词任务时作为系统提示词注入给大模型。
                可定义意图分类体系、输出格式、品牌词/对比词处理规则等。
              </div>
            </div>
          </div>
          <div class="panel-foot">
            <span v-if="savedFlash==='geoExpansion'" class="pf-saved"><el-icon><CircleCheckFilled /></el-icon> 已保存</span>
            <span v-else-if="cardDirty('geoExpansion')" class="pf-dirty"><span class="dot dot-dirty"></span> 未保存</span>
            <el-button type="primary" size="small" :loading="cardSaving==='geoExpansion'" :disabled="!cardDirty('geoExpansion')" @click="saveCard('geoExpansion')">保存</el-button>
          </div>
        </div>
      </section>


      <!-- ===== 通知 ===== -->
      <section v-show="sec === 'notify'">


      <!-- 发件邮箱多账号管理（可切换激活） -->
      <div class="panel" style="margin-bottom: 14px">
        <div class="panel-header">
          <h3>发件邮箱账号</h3>
          <el-button type="primary" size="small" @click="openMailAcctAdd">+ 添加邮箱</el-button>
        </div>
        <div v-if="!mailAccts.length" class="panel-empty">暂无邮箱账号，点右上「+ 添加邮箱」</div>
        <el-radio-group v-else v-model="mailActiveId" @change="onMailAcctActivate" class="mail-acct-list">
          <div v-for="a in mailAccts" :key="a.id" class="mail-acct-row" :class="{ active: mailActiveId === a.id }">
            <el-radio :value="a.id" class="mail-acct-radio">
              <div class="mail-acct-info">
                <div class="mail-acct-name">
                  {{ a.displayName ? `${a.displayName} <${a.email}>` : a.email }}
                  <el-tag v-if="mailActiveId === a.id" type="success" size="small" effect="dark">当前发送</el-tag>
                </div>
                <div class="mail-acct-meta">
                  {{ a.smtpHost }}:{{ a.smtpPort }} · {{ a.smtpUser }}
                  · 密码 {{ a.smtpPassConfigured ? a.smtpPassMasked : '未配置' }}
                </div>
              </div>
            </el-radio>
            <div class="mail-acct-actions">
              <el-button link size="small" @click.stop="testMailAcct(a)">测试连通</el-button>
              <el-button link size="small" type="primary" @click.stop="openMailAcctEdit(a)">编辑</el-button>
              <el-button link size="small" type="danger" @click.stop="delMailAcct(a)">删除</el-button>
            </div>
          </div>
        </el-radio-group>
        <div class="mail-acct-hint">
          <el-icon :size="12"><InfoFilled /></el-icon>
          所有邮件通知（每日日报、报告完成、查词异常等）都从「当前发送」账号发出。可随时切换。
        </div>
      </div>

      <!-- 添加/编辑 邮箱账号 Dialog -->
      <el-dialog v-model="mailAcctDialog.open" :title="mailAcctDialog.id ? '编辑邮箱账号' : '添加邮箱账号'"
                 width="min(520px, 92vw)" append-to-body>
        <el-form :model="mailAcctDialog.form" label-width="100px">
          <el-form-item label="邮箱地址" required>
            <el-input v-model="mailAcctDialog.form.email" placeholder="如 xxx@126.com" :disabled="!!mailAcctDialog.id" />
          </el-form-item>
          <el-form-item label="显示名">
            <el-input v-model="mailAcctDialog.form.displayName" placeholder="选填，如「系统通知」" />
          </el-form-item>
          <el-form-item label="SMTP 主机">
            <el-input v-model="mailAcctDialog.form.smtpHost" placeholder="留空按邮箱后缀自动填（126/163/qq/gmail 等）" />
          </el-form-item>
          <el-form-item label="SMTP 端口">
            <el-input v-model.number="mailAcctDialog.form.smtpPort" placeholder="465 (SSL) / 587 (STARTTLS)" />
          </el-form-item>
          <el-form-item label="SMTP 用户">
            <el-input v-model="mailAcctDialog.form.smtpUser" placeholder="一般同邮箱地址" />
          </el-form-item>
          <el-form-item label="授权码" :required="!mailAcctDialog.id">
            <el-input v-model="mailAcctDialog.form.smtpPass" type="password" show-password
                      :placeholder="mailAcctDialog.id ? '留空保持不变' : '邮箱「客户端授权码」'" />
          </el-form-item>
          <el-form-item label="备注">
            <el-input v-model="mailAcctDialog.form.remark" placeholder="选填" />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="mailAcctDialog.open = false">取消</el-button>
          <el-button type="primary" :loading="mailAcctDialog.saving" @click="saveMailAcct">保存</el-button>
        </template>
      </el-dialog>

      <div class="panel">
        <div class="panel-header">
          <h3>每日系统日报</h3>
          <div style="display:flex;align-items:center;gap:10px">
            <el-tag :type="emailForm.enabled ? 'success' : 'info'" size="small" effect="plain">
              {{ emailForm.enabled ? '已启用' : '未启用' }}
            </el-tag>
            <el-tag v-if="emailForm.last_sent_date" type="info" size="small" effect="plain">
              上次发送：{{ emailForm.last_sent_date }}
            </el-tag>
          </div>
        </div>
        <div class="panel-body">
          <div class="grid-2col">
            <div class="field">
              <label>启用每日邮件</label>
              <el-switch v-model="emailForm.enabled" />
              <div class="field-hint">开启后每天到点自动汇总并发送</div>
            </div>
            <div class="field">
              <label>发送时间</label>
              <el-time-picker
                v-model="emailForm.send_time_picker"
                format="HH:mm"
                value-format="HH:mm"
                placeholder="选择发送时间"
                style="width:100%"
              />
              <div class="field-hint">每日到此时间触发发送（24 小时制）</div>
            </div>
          </div>

          <div class="grid-2col" style="margin-top:14px">
            <div class="field">
              <label>SMTP 主机</label>
              <el-input v-model="emailForm.smtp_host" placeholder="smtp.126.com" />
            </div>
            <div class="field">
              <label>SMTP 端口</label>
              <el-input v-model="emailForm.smtp_port" placeholder="465" />
              <div class="field-hint">126 邮箱 SSL 端口为 465</div>
            </div>
          </div>

          <div class="grid-2col" style="margin-top:14px">
            <div class="field">
              <label>发件人邮箱</label>
              <el-input v-model="emailForm.smtp_user" placeholder="antlers7@126.com" />
              <div class="field-hint">同时作为登录用户名 + From 地址</div>
            </div>
            <div class="field">
              <label>授权码</label>
              <el-input
                v-model="emailForm.smtp_pass"
                type="password"
                show-password
                :placeholder="emailForm.smtp_pass_set ? `已配置 ${emailForm.smtp_pass_masked}（留空保持不变）` : '126 邮箱客户端授权码'"
              />
              <div class="field-hint">126 邮箱后台「客户端授权密码」获取，非登录密码</div>
            </div>
          </div>

          <div class="field" style="margin-top:14px">
            <label>收件人列表</label>
            <el-input
              v-model="emailToInput"
              placeholder="多个邮箱用逗号或换行分隔，例：a@example.com, b@example.com"
              type="textarea"
              :autosize="{ minRows: 2, maxRows: 4 }"
            />
            <div class="field-hint">每天将向以上邮箱同时发送一封日报</div>
          </div>

          <div style="margin-top:14px;display:flex;gap:8px">
            <el-button type="primary" :loading="emailSaving" @click="saveEmailSettings">保存邮件配置</el-button>
            <el-button :loading="emailTesting" @click="sendTestEmail">📨 发送测试邮件</el-button>
            <el-button :loading="emailSending" type="warning" plain @click="sendNowEmail">⚡ 立即发送今日报告</el-button>
          </div>
        </div>
      </div>

      </section>

      <!-- ===== 内容发布 ===== -->

      <!-- 账号 / 角色管理已移至顶部「权限管理」独立页，此处不再重复 -->

      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Search, Tools, Lightning, ArrowDown, ArrowRight,
  Loading, CircleCheckFilled, Select, Refresh, InfoFilled,
} from '@element-plus/icons-vue'
import api from '@/api/index.js'
import geoExpansionApi from '@/api/geoExpansion.js'

const saving = ref(false)

/* ===== 二级分类导航(4 大类 → 9 子项) ===== */
const navGroups = [
  {
    key: 'business-group', label: '业务配置', icon: Tools,
    children: [
      { key: 'kb-instructions', label: '知识库解析指令', desc: '配置知识库生成与解析的系统提示词模板' },
      { key: 'geo-expansion',     label: 'GEO拓词指令',   desc: '配置 GEO 拓词任务使用的系统提示词模板（Markdown 格式）' },
    ],
  },
  {
    key: 'api-group', label: '接口配置', icon: Search,
    children: [
      { key: 'search',      label: '查词接口',     desc: 'AI 查词统一接口配置' },
      { key: 'analysis',    label: 'AI模型',       desc: '配置品牌排名分析使用的 LLM 模型（Gemini / ChatGPT / 通义千问）' },
    ],
  },
  {
    key: 'auto-group', label: '自动化与通知', icon: Lightning,
    children: [
      { key: 'notify', label: '邮件通知',   desc: '发件账号与每日系统日报' },
    ],
  },
]

// 折叠状态(按大类 key 记)
const collapsedGroups = reactive(JSON.parse(localStorage.getItem('settings_nav_collapsed') || '{}'))
function toggleGroup(key) {
  collapsedGroups[key] = !collapsedGroups[key]
  try { localStorage.setItem('settings_nav_collapsed', JSON.stringify(collapsedGroups)) } catch { /* ignore */ }
}

// account/roles/retry-stats 已移除，旧的本地保存值回退到 search，避免空白页
const _savedSec = localStorage.getItem('settings_active_sec')
const sec = ref(_savedSec && !['account', 'roles', 'retry-stats'].includes(_savedSec) ? _savedSec : 'search')

/* ===== 每张卡片独立保存（改哪张存哪张，互不影响）===== */
const CARD_KEYS = {
  searchApis: ['search_api_url', 'search_api_key'],
  kbInstructions: ['kb_instruction_md'],
  geoExpansion: ['geo_expansion_instruction'],
}
const ALL_CARDS = ['searchApis', 'analysis', 'firecrawl', 'quote', 'kbInstructions', 'geoExpansion']
const cardSnap = reactive({})   // cardId -> 已保存时的指纹
const cardSaving = ref('')      // 正在保存的 cardId
const savedFlash = ref('')      // 刚保存成功、绿标高亮的 cardId
let savedFlashTimer = null

function cardFingerprint(id) {
  if (id === 'analysis') {
    return JSON.stringify([analysisTab.value, form.llm_base_url, form.llm_timeout,
      form.claude_model_name, form.claude_api_key,
      form.chatgpt_model_name, form.chatgpt_api_key, form.chatgpt_base_url, form.chatgpt_timeout,
      form.qwen_base_url, form.qwen_timeout, form.qwen_model_name, form.qwen_api_key])
  }
  if (id === 'firecrawl') return JSON.stringify([form.firecrawl_concurrency, form.firecrawl_api_key])
  if (id === 'searchApis') {
    return JSON.stringify([form.search_api_url, form.search_api_key])
  }
  return JSON.stringify((CARD_KEYS[id] || []).map(k => form[k]))
}
function snapshotCards() { for (const id of ALL_CARDS) cardSnap[id] = cardFingerprint(id) }
function cardDirty(id) { return cardSnap[id] !== undefined && cardSnap[id] !== cardFingerprint(id) }

async function saveCard(id) {
  cardSaving.value = id
  try {
    let payload = {}
    if (id === 'analysis') {
      // 根据当前 tab 决定保存哪个模型的配置
      const llm_api_mode = analysisTab.value
      payload = { llm_api_mode }
      
      if (analysisTab.value === 'claude') {
        if (form.llm_base_url) payload.llm_base_url = form.llm_base_url
        if (form.llm_timeout) payload.llm_timeout = form.llm_timeout
        if (form.claude_model_name) payload.claude_model_name = form.claude_model_name
        if (form.claude_api_key) payload.claude_api_key = form.claude_api_key
      } else if (analysisTab.value === 'chatgpt') {
        if (form.chatgpt_base_url) payload.chatgpt_base_url = form.chatgpt_base_url
        if (form.chatgpt_timeout) payload.chatgpt_timeout = form.chatgpt_timeout
        if (form.chatgpt_model_name) payload.chatgpt_model_name = form.chatgpt_model_name
        if (form.chatgpt_api_key) payload.chatgpt_api_key = form.chatgpt_api_key
      } else if (analysisTab.value === 'qwen') {
        if (form.qwen_base_url) payload.qwen_base_url = form.qwen_base_url
        if (form.qwen_timeout) payload.qwen_timeout = form.qwen_timeout
        if (form.qwen_model_name) payload.qwen_model_name = form.qwen_model_name
        if (form.qwen_api_key) payload.qwen_api_key = form.qwen_api_key
      }
    } else if (id === 'firecrawl') {
      payload = { firecrawl_api_url: 'https://api.firecrawl.dev', firecrawl_concurrency: form.firecrawl_concurrency }
      if (form.firecrawl_api_key) payload.firecrawl_api_key = form.firecrawl_api_key
    } else if (id === 'geoExpansion') {
      // GEO 拓词指令使用独立 API 保存
      await geoExpansionApi.saveInstruction(form.geo_expansion_instruction)
      cardSnap[id] = cardFingerprint(id)
      savedFlash.value = id
      if (savedFlashTimer) clearTimeout(savedFlashTimer)
      savedFlashTimer = setTimeout(() => { savedFlash.value = '' }, 2200)
      ElMessage.success('已保存')
      return
    } else {
      for (const k of CARD_KEYS[id]) payload[k] = form[k]
    }
    await api.updateSettings(payload)
    cardSnap[id] = cardFingerprint(id)   // 只把这张卡标记已保存，不重载全表（避免清掉其它卡未存的编辑）
    savedFlash.value = id
    if (savedFlashTimer) clearTimeout(savedFlashTimer)
    savedFlashTimer = setTimeout(() => { savedFlash.value = '' }, 2200)
    ElMessage.success('已保存')
  } catch (err) {
    ElMessage.error('保存失败：' + (err.message || ''))
  } finally {
    cardSaving.value = ''
  }
}

function renderKbInstruction(md) {
  if (!md) return ''
  let raw = String(md)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/^[-*_]{3,}\s*$/gm, '<hr class="kb-hr">')
    .split(/\n\s*\n/).map(p => p.trim()).filter(Boolean)
    .map(p => /<(h[123]|hr)/.test(p) ? p : `<p>${p.replace(/\n/g, '<br>')}</p>`)
    .join('\n')
  return raw
}

function goSection(key) {
  if (key === sec.value) return
  // 每卡独立保存，切换分区不会丢失未保存编辑（表单常驻），直接切
  sec.value = key
  try { localStorage.setItem('settings_active_sec', key) } catch { /* ignore */ }
}

/* 当前选中所在大类(用于面包屑/H1 icon) */
const currentGroup = computed(() => {
  const g = navGroups.find(g => g.children.some(c => c.key === sec.value))
  return g ? g.key : ''
})
const currentGroupLabel = computed(() => navGroups.find(g => g.key === currentGroup.value)?.label || '')
const currentGroupIcon  = computed(() => navGroups.find(g => g.key === currentGroup.value)?.icon)
const currentChild = computed(() => {
  for (const g of navGroups) {
    const c = g.children.find(c => c.key === sec.value)
    if (c) return c
  }
  return null
})
const currentSectionLabel = computed(() => currentChild.value?.label || '')
const currentSectionDesc  = computed(() => currentChild.value?.desc  || '')

/* 子项右侧状态 chip — 接口类看 form 是否填,业务配置看是否已保存 */
function statusOf(key) {
  if (key === 'search') {
    // 查词接口：有任一配置就显示ON（开发阶段默认显示ON）
    const hasConfig = form.search_api_url || form.search_api_key
    return hasConfig ? { tone: 'ok', text: 'ON' } : { tone: 'neutral', text: '—' }
  }
  if (key === 'analysis') {
    // AI模型：只要有一个模型配置了就显示ON
    const hasAnyModel = form.claude_api_key || form.chatgpt_api_key || form.qwen_api_key ||
                       form.claude_model_name || form.chatgpt_model_name || form.qwen_model_name ||
                       form.llm_base_url || form.chatgpt_base_url || form.qwen_base_url
    return hasAnyModel ? { tone: 'ok', text: 'ON' } : { tone: 'off', text: 'OFF' }
  }
  if (key === 'kb-instructions') {
    // 知识库指令：保存过就显示ON
    return form.kb_instruction_md ? { tone: 'ok', text: 'ON' } : { tone: 'off', text: 'OFF' }
  }
  if (key === 'geo-expansion') {
    // GEO拓词指令：保存过就显示ON
    return form.geo_expansion_instruction ? { tone: 'ok', text: 'ON' } : { tone: 'off', text: 'OFF' }
  }
  if (key === 'citation') return form.firecrawl_api_key ? { tone: 'ok', text: 'ON' } : { tone: 'off', text: 'OFF' }
  if (key === 'quote')    return form.quote_base_price ? { tone: 'ok', text: 'ON' } : { tone: 'off', text: 'OFF' }
  if (key === 'publish')  return { tone: 'neutral', text: '配置' }
  if (key === 'auto')     return retryForm.enabled ? { tone: 'ok', text: '启用' } : { tone: 'off', text: '禁用' }
  if (key === 'notify')   return { tone: 'neutral', text: '配置' }
  return { tone: 'neutral', text: '' }
}

/* ===== 凌晨补查状态 ===== */
const retrySaving = ref(false)
const retryRunning = ref(false)
const retryPreviewing = ref(false)
const retryPreview = ref(null)
const retryForm = reactive({
  enabled: false,
  retry_time_picker: '07:00',
  last_run_date: '',
})

/* ===== 邮件通知状态 ===== */
const emailSaving = ref(false)
const emailTesting = ref(false)
const emailSending = ref(false)
const emailToInput = ref('')
// 邮箱多账号管理
const mailAccts = ref([])
const mailActiveId = ref(null)
const mailAcctDialog = reactive({
  open: false, id: null, saving: false,
  form: { email: '', displayName: '', smtpHost: '', smtpPort: 465, smtpUser: '', smtpPass: '', remark: '' },
})
async function loadMailAccts() {
  try {
    const r = await fetch('/api/email-accounts', { credentials: 'include' }).then(r => r.json())
    mailAccts.value = r.items || []
    mailActiveId.value = r.activeId || null
  } catch (e) { ElMessage.error('加载邮箱账号失败') }
}
function openMailAcctAdd() {
  Object.assign(mailAcctDialog.form, { email: '', displayName: '', smtpHost: '', smtpPort: 465, smtpUser: '', smtpPass: '', remark: '' })
  mailAcctDialog.id = null
  mailAcctDialog.open = true
}
function openMailAcctEdit(a) {
  Object.assign(mailAcctDialog.form, {
    email: a.email, displayName: a.displayName || '', smtpHost: a.smtpHost,
    smtpPort: a.smtpPort, smtpUser: a.smtpUser, smtpPass: '', remark: a.remark || '',
  })
  mailAcctDialog.id = a.id
  mailAcctDialog.open = true
}
async function saveMailAcct() {
  mailAcctDialog.saving = true
  try {
    const url = mailAcctDialog.id ? `/api/email-accounts/${mailAcctDialog.id}` : '/api/email-accounts'
    const method = mailAcctDialog.id ? 'PUT' : 'POST'
    const r = await fetch(url, {
      method, credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(mailAcctDialog.form),
    })
    const j = await r.json()
    if (!r.ok) throw new Error(j.error || '保存失败')
    ElMessage.success(mailAcctDialog.id ? '已更新' : '已添加')
    mailAcctDialog.open = false
    await loadMailAccts()
  } catch (e) { ElMessage.error(e.message || '保存失败') }
  finally { mailAcctDialog.saving = false }
}
async function delMailAcct(a) {
  try { await ElMessageBox.confirm(`确认删除邮箱「${a.email}」？`, '删除邮箱账号', { type: 'warning' }) } catch { return }
  await fetch(`/api/email-accounts/${a.id}`, { method: 'DELETE', credentials: 'include' })
  ElMessage.success('已删除')
  await loadMailAccts()
}
async function onMailAcctActivate(id) {
  await fetch(`/api/email-accounts/${id}/activate`, { method: 'POST', credentials: 'include' })
  ElMessage.success('已切换发件账号')
  await loadMailAccts()
}
async function testMailAcct(a) {
  const r = await fetch(`/api/email-accounts/${a.id}/test`, { method: 'POST', credentials: 'include' }).then(r => r.json())
  if (r.ok) ElMessage.success('SMTP 登录成功 ✓')
  else ElMessage.error(`登录失败：${r.error || '未知'}`)
}

const emailForm = reactive({
  enabled: false,
  smtp_host: 'smtp.126.com',
  smtp_port: '465',
  smtp_user: '',
  smtp_pass: '',
  smtp_pass_set: false,
  smtp_pass_masked: '',
  email_from: '',
  send_time_picker: '08:00',
  last_sent_date: '',
})

const analysisTab = ref('claude')
const analysisModelLabel = computed(() => {
  const labels = { claude: 'Claude', chatgpt: 'ChatGPT', qwen: '通义千问' }
  return labels[analysisTab.value] || '未选择'
})
const apiKeyHints = reactive({ claude: '未设置', qwen: '未设置', chatgpt: '未设置' })

// 查词接口（简化为统一接口）
const searchApiTab = ref('chatgpt')  // 保留兼容，但不再使用

const form = reactive({
  // 查词接口（统一）
  search_api_url: '',
  search_api_key: '',
  // AI模型（品牌分析）- Claude
  llm_base_url: '',
  llm_timeout: '120',
  claude_model_name: '',
  claude_api_key: '',
  // AI模型 - ChatGPT
  chatgpt_base_url: '',
  chatgpt_timeout: '120',
  chatgpt_model_name: '',
  chatgpt_api_key: '',
  // AI模型 - 通义千问
  qwen_base_url: '',
  qwen_timeout: '300',
  qwen_model_name: '',
  qwen_api_key: '',
  // 其他
  firecrawl_api_key: '',
  firecrawl_concurrency: '5',
  quote_base_price: '2500000',
  // 业务配置
  kb_instruction_md: '',
  geo_expansion_instruction: '',
})

function switchTab(tab) {
  analysisTab.value = tab
}

function maskKey(val) {
  if (!val || val.length <= 8) return '--------'
  return val.slice(0, 4) + '--------' + val.slice(-4)
}

async function loadSettings() {
  try {
    const data = await api.getSettings()

    // 简单字段直接映射
    const simple = ['search_api_url', 'search_api_key',
                    'llm_base_url', 'llm_timeout',
                    'chatgpt_base_url', 'chatgpt_timeout',
                    'qwen_base_url', 'qwen_timeout',
                    'firecrawl_concurrency',
                    'quote_base_price',
                    'kb_instruction_md']
    simple.forEach(k => { if (data[k] !== undefined) form[k] = data[k] || form[k] })

    // 模型名称
    const models = ['claude', 'qwen', 'chatgpt']
    for (const m of models) {
      form[m + '_model_name'] = data[m + '_model_name'] || ''
      form[m + '_api_key'] = ''
      const ak = data[m + '_api_key']
      apiKeyHints[m] = ak ? '当前：' + maskKey(ak) : '未设置'
    }

    // Firecrawl key（仅显示提示，不回填明文）
    form.firecrawl_api_key = ''

    // 还原当前启用模式
    const mode = data.llm_api_mode || 'claude'
    analysisTab.value = (mode === 'qwen' || mode === 'chatgpt' || mode === 'claude') ? mode : 'claude'

    // 每卡基线快照（在 analysisTab 还原之后）
    snapshotCards()

    // 加载 GEO 拓词指令
    try {
      const geoInst = await geoExpansionApi.getInstruction()
      if (geoInst && geoInst.instruction) {
        form.geo_expansion_instruction = geoInst.instruction
      }
      // 重新快照以包含 geoExpansion
      cardSnap['geoExpansion'] = cardFingerprint('geoExpansion')
    } catch {
      /* ignore: 首次使用可能没有配置 */
    }

    // 知识库解析指令：如果数据库中没有，加载默认模板
    if (!form.kb_instruction_md) {
      try {
        const res = await axios.get('/api/kb/default-instruction', { withCredentials: true })
        const defaultInst = res.data?.instruction || res.data?.data?.instruction || ''
        if (defaultInst) form.kb_instruction_md = defaultInst
      } catch {
        /* ignore: 加载默认模板失败不影响主流程 */
      }
    }
    cardSnap['kbInstructions'] = cardFingerprint('kbInstructions')
  } catch {
    ElMessage.error('加载设置失败')
  }
}

// ========== 内容发布（媒介盒子） ==========
const publishSaving = ref(false)
const publishTesting = ref(false)
const publishRefreshing = ref(false)
const publishSyncing = ref('')
const publishSyncResult = ref(null)
const publishSyncProgress = ref(null)
const publishSyncTimer = ref(null)

// 页面加载时若有正在进行的同步任务则恢复进度显示

/* ===== 邮件通知函数 ===== */
import axios from 'axios'

async function loadEmailSettings() {
  try {
    const r = await axios.get('/api/admin/email-notify/settings', { withCredentials: true })
    const d = r.data || {}
    emailForm.enabled = !!d.enabled
    emailForm.smtp_host = d.smtp_host || 'smtp.126.com'
    emailForm.smtp_port = d.smtp_port || '465'
    emailForm.smtp_user = d.smtp_user || ''
    emailForm.smtp_pass = ''
    emailForm.smtp_pass_set = !!d.smtp_pass_set
    emailForm.smtp_pass_masked = d.smtp_pass_masked || ''
    emailForm.email_from = d.email_from || ''
    emailForm.send_time_picker = d.send_time || '08:00'
    emailForm.last_sent_date = d.last_sent_date || ''
    emailToInput.value = (d.email_to || []).join(', ')
  } catch (e) {
    ElMessage.error('加载邮件配置失败：' + (e.response?.data?.error || e.message))
  }
}

async function saveEmailSettings() {
  emailSaving.value = true
  try {
    const payload = {
      enabled: emailForm.enabled,
      smtp_host: emailForm.smtp_host,
      smtp_port: emailForm.smtp_port,
      smtp_user: emailForm.smtp_user,
      email_from: emailForm.email_from || emailForm.smtp_user,
      send_time: emailForm.send_time_picker,
      email_to: emailToInput.value,
    }
    if (emailForm.smtp_pass) payload.smtp_pass = emailForm.smtp_pass
    await axios.put('/api/admin/email-notify/settings', payload, { withCredentials: true })
    ElMessage.success('已保存邮件配置')
    await loadEmailSettings()
  } catch (e) {
    ElMessage.error('保存失败：' + (e.response?.data?.error || e.message))
  } finally {
    emailSaving.value = false
  }
}

async function sendTestEmail() {
  emailTesting.value = true
  try {
    // 先保存当前配置（避免用户改了没保存就测试）
    await saveEmailSettings()
    const r = await axios.post('/api/admin/email-notify/test', {}, { withCredentials: true })
    const d = r.data || {}
    if (d.ok) ElMessage.success(`测试邮件已发送至 ${(d.sent_to || []).length} 个收件人`)
    else ElMessage.error('测试发送失败：' + (d.error || '未知错误'))
  } catch (e) {
    ElMessage.error('测试发送失败：' + (e.response?.data?.error || e.message))
  } finally {
    emailTesting.value = false
  }
}

async function sendNowEmail() {
  try {
    await ElMessageBox.confirm('立即发送今日日报到所有收件人？', '确认', { type: 'warning' })
  } catch { return }
  emailSending.value = true
  try {
    const r = await axios.post('/api/admin/email-notify/send-now', {}, { withCredentials: true })
    const d = r.data || {}
    if (d.ok) {
      ElMessage.success(`已发送至 ${(d.sent_to || []).length} 个收件人`)
      await loadEmailSettings()
    } else {
      ElMessage.error('发送失败：' + (d.error || d.skipped || '未知错误'))
    }
  } catch (e) {
    ElMessage.error('发送失败：' + (e.response?.data?.error || e.message))
  } finally {
    emailSending.value = false
  }
}

/* ===== 凌晨补查函数 ===== */




onMounted(() => { loadSettings(); loadEmailSettings(); loadMailAccts() })

onUnmounted(() => {
  if (publishSyncTimer.value) clearInterval(publishSyncTimer.value)
})

</script>

<style scoped>
.settings-content { max-width: 800px; }

/* ===== 左深右浅 · 专业控制台 ===== */
/* 负 margin 抵消 DashboardLayout .dashboard-main-body 的 padding(20 24 32)，
   让控制台铺满内容区、紧贴白色页面头底边，消除"浮卡 + 留白"割裂感 */
.settings-layout {
  display: flex; align-items: stretch;
  margin: -20px -24px -32px;
  background: #f8fafc;
  min-height: calc(100vh - 83px);
  height: calc(100vh - 83px);
}
@media (max-width: 900px) {
  .settings-layout { margin: -14px -14px -24px; }
}
/* 二级导航(浅灰白底,清晰层次) */
.settings-nav {
  flex-shrink: 0; width: 240px;
  background: #fff;
  border-right: 1px solid #ebeef5;
  padding: 16px 10px;
  display: flex; flex-direction: column; gap: 4px;
  overflow-y: auto;
}
.nav-head {
  font-size: 11px; font-weight: 700; color: #94a3b8;
  letter-spacing: 1.5px; padding: 6px 12px 10px;
  text-transform: uppercase;
  border-bottom: 1px solid #f1f5f9; margin-bottom: 6px;
}

.nav-group { display: flex; flex-direction: column; margin-bottom: 4px; }
.nav-grp-head {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 12px; border: none; background: transparent;
  border-radius: 6px; cursor: pointer;
  font-size: 12px; color: #475569; font-weight: 600;
  text-align: left; width: 100%;
  transition: background .12s, color .12s;
}
.nav-grp-head:hover { background: #f1f5f9; color: #0f172a; }
.nav-grp-icon { flex-shrink: 0; }
.nav-grp-icon-analysis-group { color: #3b82f6; }
.nav-grp-icon-business-group { color: #10b981; }
.nav-grp-icon-auto-group { color: #f59e0b; }
.nav-grp-icon-user-group { color: #8b5cf6; }
.nav-grp-label { flex: 1; }
.nav-grp-caret {
  color: #94a3b8;
  transition: transform .2s cubic-bezier(.22,1,.36,1);
}
.nav-grp-caret.collapsed { transform: rotate(-90deg); }

.nav-children { display: flex; flex-direction: column; gap: 2px; padding: 2px 0 4px; }
.nav-child {
  display: flex; align-items: center; justify-content: space-between; gap: 6px;
  padding: 8px 12px 8px 30px;
  border: none; background: transparent; cursor: pointer;
  border-left: 3px solid transparent;
  font-size: 13px; color: #475569;
  text-align: left; width: 100%;
  border-radius: 0 6px 6px 0;
  margin-left: 6px;
  transition: background .12s, color .12s, border-color .12s;
}
.nav-child:hover { background: #f8fafc; color: #0f172a; }
.nav-child.on {
  background: #eff6ff; color: #1d4ed8; font-weight: 600;
  border-left-color: #3b82f6;
}
.nav-child-label { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.nav-child-chip {
  font-size: 10px; font-weight: 600;
  padding: 1px 6px; border-radius: 8px;
  letter-spacing: .2px; flex-shrink: 0;
}
.chip-ok { background: #d1fae5; color: #047857; }
.chip-off { background: #fee2e2; color: #b91c1c; }
.chip-neutral { background: #e2e8f0; color: #475569; }

/* nav-expand 过渡 */
.nav-expand-enter-active, .nav-expand-leave-active {
  transition: max-height .25s ease, opacity .15s;
  overflow: hidden;
}
.nav-expand-enter-from, .nav-expand-leave-to { max-height: 0; opacity: 0; }
.nav-expand-enter-to, .nav-expand-leave-from { max-height: 400px; opacity: 1; }

/* 主区域 */
.settings-main {
  flex: 1; min-width: 0; padding: 0 32px 32px; background: #f8fafc;
  overflow-y: auto;
}
.main-head {
  padding: 22px 0 18px;
  border-bottom: 1px solid #ebeef5;
  margin-bottom: 22px;
  position: sticky; top: 0;
  background: #f8fafc;
  z-index: 10;
}
.breadcrumb {
  display: flex; align-items: center; gap: 6px;
  font-size: 12px; color: #94a3b8; margin-bottom: 8px;
}
.bc-current { color: #475569; font-weight: 500; }
.head-row {
  display: flex; align-items: flex-start; justify-content: space-between;
  gap: 16px; flex-wrap: wrap;
}
.head-text { flex: 1; min-width: 0; }
.head-title {
  display: flex; align-items: center; gap: 10px;
  font-size: 22px; font-weight: 800; color: #0f172a; letter-spacing: -.4px;
  margin: 0;
}
.head-icon {
  width: 32px; height: 32px; border-radius: 8px;
  background: rgba(59,130,246,.1);
  display: inline-flex; align-items: center; justify-content: center;
}
.head-desc { font-size: 13px; color: #64748b; margin: 6px 0 0 42px; }
.head-actions {
  display: flex; align-items: center; gap: 10px; flex-shrink: 0;
}
/* 保存状态指示器(4 态:clean / saving / just-saved / dirty) */
.save-status {
  display: inline-flex; align-items: center; gap: 5px;
  font-size: 12px; font-weight: 600;
  padding: 5px 12px; border-radius: 14px;
  letter-spacing: .2px;
  transition: background .15s, color .15s;
}
.save-status.clean { background: #f1f5f9; color: #64748b; }
.save-status.clean .el-icon { color: #10b981; }
.save-status.saved-just {
  background: linear-gradient(135deg, #d1fae5, #ecfdf5);
  color: #047857;
  box-shadow: 0 2px 8px rgba(16,185,129,.18);
  animation: pop-in .35s cubic-bezier(.34,1.56,.64,1);
}
.save-status.dirty {
  background: #fef3c7; color: #b45309;
}
.save-status.saving { background: #eff6ff; color: #1d4ed8; }
.dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.dot-dirty { background: #f59e0b; box-shadow: 0 0 0 3px rgba(245,158,11,.18); animation: pulse-dot 1.4s infinite; }
.rotating { animation: rotate-loading 1s linear infinite; }
@keyframes pop-in {
  0% { transform: scale(.85); opacity: 0; }
  60% { transform: scale(1.04); }
  100% { transform: scale(1); opacity: 1; }
}
@keyframes pulse-dot {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.25); opacity: .6; }
}
@keyframes rotate-loading {
  to { transform: rotate(360deg); }
}
.fade-enter-active, .fade-leave-active { transition: opacity .2s, transform .2s; }
.fade-enter-from, .fade-leave-to { opacity: 0; transform: translateY(-2px); }

.panel {
  background: #fff; border-radius: 14px;
  border: 1px solid #e7edf5; margin-bottom: 18px;
  position: relative; overflow: hidden;
  box-shadow: 0 1px 2px rgba(15,23,42,.04);
  transition: box-shadow .2s, transform .2s;
}
.panel::after {
  content: ''; position: absolute; left: 0; top: 0; bottom: 0;
  width: 3px; background: linear-gradient(180deg,#3b82f6,#93c5fd);
  opacity: 0; transition: opacity .2s;
}
.panel:hover { box-shadow: 0 8px 24px rgba(15,23,42,.09); }
.panel:hover::after { opacity: 1; }
.panel-header {
  padding: 16px 22px 13px; border-bottom: 1px solid #f1f5f9;
  display: flex; justify-content: space-between; align-items: center;
}
.panel-empty { padding: 24px; text-align: center; color: #94a3b8; font-size: 13px; }
/* 邮箱账号列表 */
.mail-acct-list { display: flex; flex-direction: column; padding: 8px 16px; width: 100%; }
.mail-acct-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 14px; border-radius: 8px;
  border: 1px solid #f1f5f9; background: #fafbfc;
  margin-bottom: 8px; transition: all .15s;
}
.mail-acct-row:hover { border-color: #c7d2fe; background: #fafbff; }
.mail-acct-row.active { border-color: #2563eb; background: #eff6ff; }
.mail-acct-radio { flex: 1; min-width: 0; }
.mail-acct-radio :deep(.el-radio__label) { width: 100%; padding-left: 8px; }
.mail-acct-info { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
.mail-acct-name { font-size: 14px; font-weight: 600; color: #0f172a; display: flex; align-items: center; gap: 6px; }
.mail-acct-meta { font-size: 11.5px; color: #94a3b8; font-family: ui-monospace, monospace; }
.mail-acct-actions { display: flex; gap: 2px; flex-shrink: 0; }
.mail-acct-hint {
  display: flex; align-items: center; gap: 5px;
  padding: 10px 22px 0; font-size: 12px; color: #94a3b8;
}
.panel-header h3 {
  font-size: 14px; font-weight: 700; color: #0f172a;
  display: flex; align-items: center; gap: 9px;
}
.panel-header h3::before {
  content: ''; width: 7px; height: 7px; border-radius: 50%;
  background: #3b82f6; box-shadow: 0 0 0 3px rgba(59,130,246,.15); flex-shrink: 0;
}
.panel-body { padding: 18px 22px; }
/* 每张卡片底部独立保存条 */
.panel-foot {
  display: flex; align-items: center; justify-content: flex-end; gap: 12px;
  padding: 12px 22px;
  border-top: 1px solid #f1f5f9;
  background: #fcfdff;
  border-radius: 0 0 14px 14px;
}
.pf-saved { display: inline-flex; align-items: center; gap: 5px; font-size: 12.5px; color: #16a34a; font-weight: 600; }
.pf-dirty { display: inline-flex; align-items: center; gap: 6px; font-size: 12.5px; color: #b45309; }

.grid-2col { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.grid-3col { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; }

.field { margin-bottom: 14px; }
.field label { display: block; font-size: 12px; font-weight: 600; color: #334155; margin-bottom: 6px; }
.field-hint { font-size: 11px; color: #94a3b8; margin-top: 5px; line-height: 1.5; }

.active-dot {
  font-size: 11px;
  color: #22c55e;
  font-weight: 600;
}
.active-dot::before {
  content: '';
  display: inline-block;
  width: 6px; height: 6px;
  border-radius: 50%;
  background: #22c55e;
  margin-right: 4px;
  vertical-align: middle;
}

.api-tabs {
  display: flex;
  gap: 0;
  margin-bottom: 16px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  overflow: hidden;
}
.api-tab {
  flex: 1;
  text-align: center;
  padding: 9px 0;
  font-size: 13px;
  font-weight: 600;
  color: #6b7280;
  cursor: pointer;
  transition: all 0.2s;
  background: #f9fafb;
  border-right: 1px solid #e5e7eb;
  user-select: none;
}
.api-tab:last-child { border-right: none; }
.api-tab:hover { color: #374151; background: #f3f4f6; }
.api-tab.active {
  color: #1d4ed8;
  background: #eff6ff;
  box-shadow: inset 0 -2px 0 #3b82f6;
}

.tab-content { padding-top: 2px; }

.action-bar { display: flex; gap: 10px; padding: 4px 0; }

/* ============ 查词重试分析(精装版) ============ */
.rs-toolbar {
  display: flex; justify-content: space-between; align-items: center; gap: 14px;
  background: #fff; border: 1px solid #e2e8f0; border-radius: 12px;
  padding: 12px 16px; margin-bottom: 14px; flex-wrap: wrap;
}
.rs-toolbar-left { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.rs-toolbar-right { display: flex; align-items: center; gap: 12px; }
.rs-sep { color: #94a3b8; font-size: 12px; }
.rs-meta { font-size: 12.5px; color: #4f46e5; font-weight: 600;
  background: #eef2ff; padding: 4px 10px; border-radius: 999px; }

/* KPI 卡片 */
.rs-kpis {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px;
  margin-bottom: 14px;
}
@media (max-width: 1100px) { .rs-kpis { grid-template-columns: repeat(2, 1fr); } }
.rs-kpi {
  display: flex; align-items: center; gap: 12px;
  background: #fff; border: 1px solid #e2e8f0; border-radius: 12px;
  padding: 14px 16px; position: relative; overflow: hidden;
  transition: all .15s;
}
.rs-kpi:hover { box-shadow: 0 4px 16px -8px rgba(15,23,42,.15); transform: translateY(-1px); }
.rs-kpi::before {
  content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 4px;
}
.rs-kpi-blue::before  { background: linear-gradient(180deg, #3b82f6, #6366f1); }
.rs-kpi-green::before { background: linear-gradient(180deg, #10b981, #14b8a6); }
.rs-kpi-amber::before { background: linear-gradient(180deg, #f59e0b, #f97316); }
.rs-kpi-red::before   { background: linear-gradient(180deg, #dc2626, #b91c1c); }
.rs-kpi-purple::before{ background: linear-gradient(180deg, #8b5cf6, #6d28d9); }
.rs-kpi-gray::before  { background: linear-gradient(180deg, #94a3b8, #64748b); }
.rs-kpi-icon { font-size: 24px; flex-shrink: 0; }
.rs-kpi-body { flex: 1; min-width: 0; }
.rs-kpi-label { font-size: 11.5px; color: #64748b; font-weight: 600; }
.rs-kpi-val { font-size: 26px; font-weight: 800; color: #0f172a; font-variant-numeric: tabular-nums; line-height: 1.1; }
.rs-kpi-val small { font-size: 14px; color: #64748b; font-weight: 600; margin-left: 1px; }
.rs-kpi-sub { font-size: 11px; color: #94a3b8; margin-top: 2px; }

/* 主表 */
.rs-panel {
  background: #fff; border: 1px solid #e2e8f0; border-radius: 12px;
  padding: 14px 16px;
}
.rs-loading, .rs-empty {
  padding: 60px; text-align: center; color: #94a3b8;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
}
.rs-table { display: flex; flex-direction: column; gap: 2px; }
.rs-row {
  display: grid;
  grid-template-columns: 130px 70px 110px 80px 80px 110px 130px 80px 1.2fr 60px;
  gap: 10px; align-items: center;
  font-size: 12.5px; padding: 8px 10px; border-radius: 8px;
  transition: background .12s;
}
.rs-row:not(.rs-header-row):hover { background: #f8fafc; }
.rs-header-row {
  font-size: 11px; color: #64748b; font-weight: 700;
  text-transform: uppercase; letter-spacing: .02em;
  border-bottom: 1px solid #e2e8f0; padding: 10px 10px;
}
.rs-cell.rs-model { display: flex; align-items: center; gap: 6px; min-width: 0; }
.rs-model-tag {
  font-weight: 700; color: #0f172a; font-size: 13px;
  padding: 2px 8px; border-radius: 6px; background: #f1f5f9;
}
.rs-model-tag[data-model="douBao"]   { background: #fee2e2; color: #b91c1c; }
.rs-model-tag[data-model="deepseek"] { background: #dbeafe; color: #1e40af; }
.rs-model-tag[data-model="yuanBao"]  { background: #fef3c7; color: #92400e; }
.rs-model-tag[data-model="kimi"]     { background: #ede9fe; color: #6d28d9; }
.rs-model-tag[data-model="tongYi"]   { background: #dcfce7; color: #166534; }
.rs-model-tag[data-model="wenXin"]   { background: #cffafe; color: #155e75; }
.rs-plat { color: #94a3b8; font-size: 10.5px; }
.rs-cell.rs-num {
  color: #475569; font-variant-numeric: tabular-nums;
  display: flex; flex-direction: column; gap: 1px;
}
.rs-num-main { font-weight: 600; color: #0f172a; }
.rs-cnt { color: #94a3b8; font-size: 10.5px; }
.rs-alert-text { color: #b91c1c !important; font-weight: 700; }

/* 真一次过率胶囊 */
.rs-pct-pill {
  display: inline-block; font-weight: 700; font-size: 12.5px;
  padding: 2px 10px; border-radius: 999px; font-variant-numeric: tabular-nums;
}
.rs-pct-good { background: #dcfce7; color: #166534; }
.rs-pct-mid  { background: #fef9c3; color: #854d0e; }
.rs-pct-warn { background: #ffedd5; color: #c2410c; }
.rs-pct-bad  { background: #fee2e2; color: #b91c1c; }

/* 分布条 */
.rs-bar { display: flex; height: 12px; border-radius: 999px; overflow: hidden; background: #f1f5f9; }
.rs-seg { transition: flex .15s; }
.rs-seg.seg-one { background: #10b981; }
.rs-seg.seg-two { background: #84cc16; }
.rs-seg.seg-three { background: #eab308; }
.rs-seg.seg-four { background: #f97316; }
.rs-seg.seg-bad { background: #dc2626; }
.rs-seg.seg-rescue { background: #8b5cf6; }

/* 跨行救援标签(同一行) */
.rs-rescue-col { display: flex; gap: 4px; flex-wrap: wrap; align-items: center; }
.rs-rescue-tag {
  display: inline-flex; align-items: center; gap: 3px;
  padding: 2px 8px; border-radius: 6px; font-size: 11px;
  font-variant-numeric: tabular-nums; border: 1px solid transparent;
}
.rs-rescue-tag strong { font-weight: 700; font-size: 12px; }
.rs-rescue-sweep { background: #f5f3ff; color: #6d28d9; border-color: #ede9fe; }
.rs-rescue-morning { background: #fff7ed; color: #c2410c; border-color: #fed7aa; }
.rs-rescue-manual { background: #f0f9ff; color: #0369a1; border-color: #bae6fd; }
.rs-rescue-empty { color: #cbd5e1; font-size: 14px; padding-left: 6px; }

/* 指标说明卡 */
.rs-explain {
  background: #fff; border: 1px solid #e2e8f0; border-radius: 12px;
  margin-bottom: 14px; overflow: hidden;
}
.rs-explain-head {
  display: flex; justify-content: space-between; align-items: center;
  padding: 11px 16px; cursor: pointer; font-size: 13px; font-weight: 600; color: #0f172a;
  background: linear-gradient(180deg, #fafbfc 0%, #fff 100%);
}
.rs-explain-head:hover { background: #f8fafc; }
.rs-explain-head .flipped { transform: rotate(-90deg); transition: transform .15s; }
.rs-explain-body {
  padding: 4px 18px 14px; font-size: 12.5px; color: #475569; line-height: 1.7;
}
.rs-formula {
  background: #f1f5f9; border-radius: 8px; padding: 8px 12px; margin: 6px 0 10px;
  font-size: 13px; color: #0f172a;
}
.rs-formula code { background: transparent; padding: 0; font-weight: 600; }
.rs-meta-list { margin: 0; padding-left: 18px; }
.rs-meta-list > li { margin-bottom: 4px; }
.rs-meta-list code { background: #f1f5f9; padding: 1px 5px; border-radius: 3px; font-size: 11.5px; color: #475569; }
.rs-meta-list b { font-weight: 700; }
.rs-meta-list b.dot-good { color: #047857; }
.rs-meta-list b.dot-2    { color: #4d7c0f; }
.rs-meta-list b.dot-3    { color: #a16207; }
.rs-meta-list b.dot-4    { color: #c2410c; }
.rs-meta-list b.dot-rescue { color: #6d28d9; }
.rs-meta-list b.dot-bad  { color: #b91c1c; }
.rs-sub-list { margin: 4px 0 4px 0; padding-left: 18px; list-style: none; }
.rs-sub-list > li { margin-bottom: 3px; display: flex; align-items: baseline; gap: 6px; }
.rs-sub-list .rs-rescue-tag { flex-shrink: 0; }

/* 列头小色点 */
.dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 4px; vertical-align: middle; }
.dot-good   { background: #10b981; }
.dot-2      { background: #84cc16; }
.dot-3      { background: #eab308; }
.dot-4      { background: #f97316; }
.dot-rescue { background: #8b5cf6; }
.dot-bad    { background: #dc2626; }

/* 跨行救援文字 + 细节 */
.rs-rescue-text { color: #6d28d9; font-weight: 700; }
.rs-rescue-detail { color: #94a3b8; font-size: 10px; }
.rs-sub-warn { color: #b91c1c; font-weight: 700; margin-left: 2px; }

/* 校验列 */
.rs-cell.rs-check-col { text-align: center; }
.rs-check {
  display: inline-flex; align-items: center; justify-content: center;
  width: 22px; height: 22px; border-radius: 50%; font-size: 13px; font-weight: 700;
}
.rs-check.rs-check-ok  { background: #dcfce7; color: #166534; }
.rs-check.rs-check-bad { background: #fee2e2; color: #b91c1c; width: auto; padding: 0 6px; border-radius: 999px; font-size: 11px; }

.panel-actions { display: flex; gap: 8px; align-items: center; }

/* 知识库解析指令 */
.kb-inst-textarea :deep(.el-textarea__inner) {
  font-family: ui-monospace, SFMono-Regular, 'Cascadia Code', monospace;
  font-size: 13px; line-height: 1.7;
}
.kb-inst-preview {
  background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px;
  padding: 16px; max-height: 500px; overflow: auto; line-height: 1.7;
  font-size: 13px; color: #334155;
}
.kb-inst-preview h1 { font-size: 18px; margin: 12px 0 6px; color: #1e293b; }
.kb-inst-preview h2 { font-size: 15px; margin: 10px 0 5px; color: #334155; }
.kb-inst-preview h3 { font-size: 14px; margin: 8px 0 4px; color: #475569; }
.kb-inst-preview p { margin: 4px 0; }
.kb-inst-preview hr { border: none; border-top: 1px solid #e2e8f0; margin: 10px 0; }
</style>
