/**
 * 根据排名状态值返回 badge 类型和显示文本
 */
export function getBadgeType(status) {
  if (!status || status === '-') return 'empty'
  if (/^\d+$/.test(status)) return 'number'
  if (status === '继续优化') return 'continue'
  if (status.includes('正面')) return 'positive'
  if (status.includes('正确')) return 'correct'
  return 'continue'
}

export function getBadgeClass(status) {
  const type = getBadgeType(status)
  return {
    'rank-badge': true,
    'rank-number': type === 'number',
    'rank-continue': type === 'continue',
    'rank-positive': type === 'positive',
    'rank-correct': type === 'correct',
    'rank-empty': type === 'empty'
  }
}
