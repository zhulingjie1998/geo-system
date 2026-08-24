// 全局功能搜索:单例开关 + 权限过滤 + 高速匹配(预编译+排序) + 客户实体 + 最近访问
import { ref } from 'vue'
import axios from 'axios'
import { SEARCH_INDEX, CLIENT_ACTIONS } from '@/config/searchIndex'

const isOpen = ref(false)
const _clients = ref([])      // [{id, name, _hay}]
let _clientsLoaded = false

function open() { isOpen.value = true }
function close() { isOpen.value = false }

const _norm = (s) => (s || '').toLowerCase()

// 模块加载时一次性预编译 haystack(每次按键不再重复 lower,保证检索瞬时)
const ENTRIES = SEARCH_INDEX.map(e => ({
  ...e,
  _hay: _norm([e.title, e.module, e.desc, (e.keywords || []).join(' '), e.path].join(' ')),
  _title: _norm(e.title),
}))

function canAccess(pageKey) {
  if (!pageKey) return true
  if ((localStorage.getItem('geo_role') || '') === 'super_admin') return true
  if (localStorage.getItem('geo_is_super') === '1') return true
  let pages = []
  try { pages = JSON.parse(localStorage.getItem('geo_pages') || '[]') } catch { /* ignore */ }
  return pages.includes(pageKey)
}

let _accessible = null
function accessibleEntries() {
  if (_accessible === null) _accessible = ENTRIES.filter(e => canAccess(e.pageKey))
  return _accessible
}

async function ensureClients() {
  if (_clientsLoaded) return
  _clientsLoaded = true
  try {
    const r = await axios.get('/api/kb/accounts', { withCredentials: true })
    _clients.value = (r.data?.accounts || []).map(a => {
      const name = a.companyName || a.company_name || a.name || ('客户#' + a.id)
      return { id: a.id, name, _hay: _norm(name) }
    })
  } catch { _clients.value = [] }
}

// 相关性打分:标题前缀 < 标题包含 < 关键词/其它(越小越靠前)
function _score(e, q) {
  if (e._title.startsWith(q)) return 0
  if (e._title.includes(q)) return 1
  return 2
}

function search(query) {
  const q = _norm(query).trim()
  // 功能
  let feats
  if (!q) {
    feats = accessibleEntries()
  } else {
    feats = accessibleEntries().filter(e => e._hay.includes(q))
    feats = feats
      .map((e, i) => ({ e, s: _score(e, q), i }))
      .sort((a, b) => a.s - b.s || a.i - b.i)
      .map(x => x.e)
  }
  // 客户实体(有输入时)
  const clientRows = []
  if (q) {
    for (const c of _clients.value) {
      if (!c._hay.includes(q)) continue
      for (const act of CLIENT_ACTIONS) {
        if (!canAccess(act.pageKey)) continue
        clientRows.push({
          isClient: true, client: c, action: act,
          title: `${c.name} · ${act.label}`, module: act.module,
          path: act.path, query: act.query(c),
          desc: `跳转到该客户的「${act.label}」`,
        })
      }
      if (clientRows.length > 18) break
    }
  }
  return { features: feats.slice(0, 40), clients: clientRows.slice(0, 18) }
}

// 最近访问
const RECENT_KEY = 'geo_search_recent'
function getRecent() {
  try { return JSON.parse(localStorage.getItem(RECENT_KEY) || '[]') } catch { return [] }
}
function pushRecent(entry) {
  const slim = { title: entry.title, module: entry.module, path: entry.path, query: entry.query || null, section: entry.section || null }
  let arr = getRecent().filter(x => !(x.path === slim.path && JSON.stringify(x.query) === JSON.stringify(slim.query) && x.section === slim.section))
  arr.unshift(slim)
  arr = arr.slice(0, 8)
  try { localStorage.setItem(RECENT_KEY, JSON.stringify(arr)) } catch { /* ignore */ }
}

// 开发期校验:路由里有、但没登记进搜索索引的页面,控制台告警,避免新功能漏加
export function auditSearchIndex(routes) {
  if (!import.meta.env?.DEV) return
  const paths = new Set(ENTRIES.map(e => e.path))
  const miss = []
  for (const r of routes) {
    const p = r.path || ''
    if (!/^\/(dashboard|publish|effect)\//.test(p)) continue
    if (p.includes(':')) continue // 详情/动态路由跳过
    if (!paths.has(p)) miss.push(`${p}${r.name ? ' (' + r.name + ')' : ''}`)
  }
  if (miss.length) {
    console.warn('[全局搜索] 以下页面未登记进 searchIndex.js,将搜不到,请补充:\n  ' + miss.join('\n  '))
  }
}

export function useGlobalSearch() {
  return { isOpen, open, close, search, ensureClients, getRecent, pushRecent }
}
