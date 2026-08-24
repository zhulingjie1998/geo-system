// 统一时间显示工具(中文相对时间 / 短格式 / 陈旧判断)
// 各页面原本各写一份,这里收口,避免实现漂移。

export const STALE_DAYS = 7

// 兼容 Safari:把 "2026-06-05 12:00:00" 的 - 换成 / 再 new Date
function toDate(timeStr) {
  if (!timeStr) return null
  try {
    const d = new Date(String(timeStr).replace(/-/g, '/'))
    return isNaN(d.getTime()) ? null : d
  } catch {
    return null
  }
}

// 相对时间:刚刚 / N 分钟前 / N 小时前 / N 天前 / N 个月前
export function relativeTime(timeStr) {
  const d = toDate(timeStr)
  if (!d) return timeStr || ''
  const diff = Date.now() - d.getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return '刚刚'
  if (mins < 60) return `${mins} 分钟前`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours} 小时前`
  const days = Math.floor(hours / 24)
  if (days < 30) return `${days} 天前`
  return `${Math.floor(days / 30)} 个月前`
}

// 短格式:取 "MM-DD HH:mm"(从 "YYYY-MM-DD HH:mm:ss" 截取)
export function formatShortTime(s) {
  if (!s) return ''
  return String(s).slice(5, 16)
}

// 是否超过 staleDays 天未更新
export function isStale(timeStr, staleDays = STALE_DAYS) {
  const d = toDate(timeStr)
  if (!d) return false
  return Date.now() - d.getTime() > staleDays * 24 * 3600 * 1000
}
