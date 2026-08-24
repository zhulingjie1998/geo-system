<template>
  <transition name="gs-fade">
    <div v-if="isOpen" class="gs-mask" @click.self="close">
      <transition name="gs-pop" appear>
        <div v-if="isOpen" class="gs-panel" @keydown.down.prevent="move(1)" @keydown.up.prevent="move(-1)"
             @keydown.enter.prevent="go(flat[active])" @keydown.esc="close">
          <!-- 输入 -->
          <div class="gs-input-wrap">
            <svg class="gs-input-ic" viewBox="0 0 24 24" width="18" height="18"><path fill="currentColor" d="M15.5 14h-.79l-.28-.27a6.5 6.5 0 1 0-.7.7l.27.28v.79l5 4.99L20.49 19zm-6 0A4.5 4.5 0 1 1 14 9.5 4.5 4.5 0 0 1 9.5 14"/></svg>
            <input ref="inputEl" v-model="q" class="gs-input" placeholder="搜索功能 / 客户…  例:运营复盘、订单、攻坚作战、客户名" />
            <kbd class="gs-esc">Esc</kbd>
          </div>

          <!-- 结果 -->
          <div ref="bodyEl" class="gs-body">
            <template v-if="!q.trim()">
              <div v-if="recent.length" class="gs-group">
                <div class="gs-group-h">最近访问</div>
                <button v-for="(r, i) in recent" :key="'r'+i" class="gs-row" :class="{ on: flat[active] === r }"
                        @mouseenter="active = flat.indexOf(r)" @click="go(r)">
                  <span class="gs-dot" :class="modClass(r.module)"></span>
                  <span class="gs-row-title">{{ r.title }}</span>
                  <span class="gs-row-mod" :class="modClass(r.module)">{{ r.module }}</span>
                  <span class="gs-row-path">{{ r.path }}</span>
                </button>
              </div>
              <div class="gs-tips">
                <span>🔍 搜功能名 / 别名（如"复盘""花费"）</span>
                <span>👤 搜客户名直达其分析/订单</span>
              </div>
            </template>

            <template v-else>
              <div v-if="res.features.length" class="gs-group">
                <div class="gs-group-h">功能 · {{ res.features.length }}</div>
                <button v-for="(e, i) in res.features" :key="'f'+i" class="gs-row" :class="{ on: flat[active] === e }"
                        @mouseenter="active = flat.indexOf(e)" @click="go(e)">
                  <span class="gs-dot" :class="modClass(e.module)"></span>
                  <span class="gs-row-title" v-html="hl(e.title)"></span>
                  <em v-if="e.section" class="gs-sec">区块</em>
                  <span class="gs-row-desc">{{ e.desc }}</span>
                  <span class="gs-row-mod" :class="modClass(e.module)">{{ e.module }}</span>
                </button>
              </div>
              <div v-if="res.clients.length" class="gs-group">
                <div class="gs-group-h">客户 · {{ res.clients.length }}</div>
                <button v-for="(c, i) in res.clients" :key="'c'+i" class="gs-row" :class="{ on: flat[active] === c }"
                        @mouseenter="active = flat.indexOf(c)" @click="go(c)">
                  <span class="gs-dot client"></span>
                  <span class="gs-row-title" v-html="hl(c.title)"></span>
                  <span class="gs-row-mod" :class="modClass(c.module)">{{ c.module }}</span>
                </button>
              </div>
              <div v-if="!res.features.length && !res.clients.length" class="gs-empty">
                没有匹配「{{ q }}」的功能或客户
              </div>
            </template>
          </div>

          <!-- 底栏快捷键 -->
          <div class="gs-foot">
            <span><kbd>↑</kbd><kbd>↓</kbd> 选择</span>
            <span><kbd>↵</kbd> 打开</span>
            <span><kbd>esc</kbd> 关闭</span>
            <span class="gs-foot-r">{{ flat.length }} 个结果</span>
          </div>
        </div>
      </transition>
    </div>
  </transition>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useGlobalSearch } from '@/composables/useGlobalSearch'

const router = useRouter()
const { isOpen, open, close, search, ensureClients, getRecent, pushRecent } = useGlobalSearch()

const q = ref('')
const active = ref(0)
const inputEl = ref(null)
const bodyEl = ref(null)
const recent = ref([])

const res = computed(() => search(q.value))
const flat = computed(() => q.value.trim()
  ? [...res.value.features, ...res.value.clients]
  : recent.value)

function modClass(m) { return ({ '运营系统': 'm-ops', '内容发布': 'm-pub', '效果分析': 'm-eff' })[m] || '' }

function _esc(s) { return (s || '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])) }
function hl(text) {
  const t = text || ''
  const query = q.value.trim()
  if (!query) return _esc(t)
  const idx = t.toLowerCase().indexOf(query.toLowerCase())
  if (idx < 0) return _esc(t)
  return _esc(t.slice(0, idx)) + '<mark>' + _esc(t.slice(idx, idx + query.length)) + '</mark>' + _esc(t.slice(idx + query.length))
}

function move(d) {
  const n = flat.value.length
  if (!n) return
  active.value = (active.value + d + n) % n
  nextTick(scrollActive)
}
function scrollActive() {
  const rows = bodyEl.value?.querySelectorAll('.gs-row')
  rows?.[active.value]?.scrollIntoView({ block: 'nearest' })
}
function go(item) {
  if (!item) return
  pushRecent(item)
  const loc = { path: item.path }
  const query = { ...(item.query || {}) }
  if (item.section) query.focus = item.section
  if (Object.keys(query).length) loc.query = query
  close()
  router.push(loc)
}

watch(isOpen, async (v) => {
  if (v) {
    q.value = ''; active.value = 0
    recent.value = getRecent()
    ensureClients()
    await nextTick()
    inputEl.value?.focus()
  }
})
watch(q, () => { active.value = 0 })

function onKey(e) {
  if ((e.metaKey || e.ctrlKey) && (e.key === 'k' || e.key === 'K')) {
    e.preventDefault()
    isOpen.value ? close() : open()
  }
}
onMounted(() => window.addEventListener('keydown', onKey))
onUnmounted(() => window.removeEventListener('keydown', onKey))
</script>

<style scoped>
.gs-mask { position: fixed; inset: 0; z-index: 3000; background: rgba(15,23,42,.45); backdrop-filter: blur(3px);
  display: flex; justify-content: center; align-items: flex-start; padding-top: 11vh; }
.gs-panel { width: min(660px, 92vw); background: #fff; border-radius: 16px;
  box-shadow: 0 32px 80px -16px rgba(15,23,42,.5), 0 0 0 1px rgba(15,23,42,.04);
  overflow: hidden; display: flex; flex-direction: column; max-height: 72vh; }

/* 输入 */
.gs-input-wrap { display: flex; align-items: center; gap: 12px; padding: 16px 20px; border-bottom: 1px solid #f1f5f9; }
.gs-input-ic { color: #94a3b8; flex-shrink: 0; }
.gs-input { flex: 1; border: 0; outline: none; font-size: 16.5px; font-family: inherit; color: #0f172a; background: transparent; }
.gs-input::placeholder { color: #cbd5e1; }
.gs-esc { font-size: 11px; color: #94a3b8; background: #f1f5f9; border-radius: 6px; padding: 3px 8px; }

/* 结果区 */
.gs-body { overflow-y: auto; padding: 8px; flex: 1; }
.gs-group { padding: 4px 2px 8px; }
.gs-group-h { font-size: 11px; color: #94a3b8; font-weight: 700; letter-spacing: .4px; padding: 8px 12px 6px; text-transform: none; }
.gs-row { display: flex; align-items: center; gap: 11px; width: 100%; text-align: left; border: 0; background: transparent;
  cursor: pointer; font-family: inherit; padding: 11px 12px; border-radius: 11px; transition: background .1s; }
.gs-row.on { background: linear-gradient(90deg, #eff6ff, #f5f9ff); }
.gs-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; background: #cbd5e1; }
.gs-dot.m-ops { background: #2563eb; } .gs-dot.m-pub { background: #059669; } .gs-dot.m-eff { background: #8b5cf6; } .gs-dot.client { background: #f59e0b; }
.gs-row-title { flex-shrink: 0; font-size: 14px; font-weight: 600; color: #1e293b; max-width: 240px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.gs-row-title :deep(mark) { background: transparent; color: #2563eb; font-weight: 800; padding: 0; }
.gs-sec { flex-shrink: 0; font-style: normal; font-size: 10px; color: #d97706; background: #fef3c7; border-radius: 5px; padding: 1px 6px; }
.gs-row-desc { flex: 1; font-size: 12px; color: #94a3b8; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.gs-row-mod { flex-shrink: 0; font-size: 10.5px; font-weight: 600; border-radius: 6px; padding: 2px 8px; }
.gs-row-mod.m-ops { background: #eff6ff; color: #2563eb; } .gs-row-mod.m-pub { background: #ecfdf5; color: #059669; } .gs-row-mod.m-eff { background: #faf5ff; color: #8b5cf6; }
.gs-row-path { flex-shrink: 0; font-size: 11px; color: #cbd5e1; }

.gs-tips { display: flex; flex-direction: column; gap: 6px; padding: 14px 14px 18px; font-size: 12.5px; color: #cbd5e1; }
.gs-empty { font-size: 13.5px; color: #94a3b8; text-align: center; padding: 38px 0; }

/* 底栏 */
.gs-foot { display: flex; align-items: center; gap: 16px; padding: 10px 18px; border-top: 1px solid #f1f5f9;
  background: #fafbfc; font-size: 11.5px; color: #94a3b8; }
.gs-foot kbd { font-size: 11px; background: #fff; border: 1px solid #e2e8f0; border-radius: 5px; padding: 1px 6px; margin-right: 2px; color: #64748b; }
.gs-foot-r { margin-left: auto; }

/* 动效 */
.gs-fade-enter-active, .gs-fade-leave-active { transition: opacity .16s ease; }
.gs-fade-enter-from, .gs-fade-leave-to { opacity: 0; }
.gs-pop-enter-active { transition: transform .2s cubic-bezier(.16,1,.3,1), opacity .2s; }
.gs-pop-enter-from { transform: translateY(-12px) scale(.97); opacity: 0; }
</style>
